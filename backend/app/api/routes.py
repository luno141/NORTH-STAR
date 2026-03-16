from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from redis import Redis
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.observability import metrics_response
from app.db.session import get_db
from app.models.models import (
    FederationPolicy,
    IngestionRun,
    IngestionSource,
    LedgerAnchor,
    LedgerEntry,
    Organization,
    ReputationEvent,
    SourceReliability,
    ThreatIntel,
    User,
)
from app.schemas.schemas import (
    AdminOverviewOut,
    FederationPolicyOut,
    FederationPolicyUpdateRequest,
    FederationRunResponse,
    FeedResponse,
    IngestTextRequest,
    IngestionRunOut,
    IngestionSourceOut,
    IngestionSourceUpdateRequest,
    IntegrityVerifyResponse,
    IntelCreate,
    IntelOut,
    LoginRequest,
    LoginResponse,
    ReputationActionRequest,
    RotateKeyResponse,
    SourceReliabilityUpdateRequest,
    UserContext,
)
from app.services.auth import authenticate_api_key, get_current_user, require_role
from app.services.federation import run_federation
from app.services.ingestion import ingest_csv_bytes, ingest_rss, ingest_text_dump
from app.services.intel import create_intel_record
from app.services.ledger import create_anchor, verify_chain
from app.services.live_feeds import get_due_ingestion_sources
from app.services.security import create_access_token, generate_api_key, hash_api_key
from app.tasks.jobs import run_due_ingestion_sources_job, run_ingestion_source_job


router = APIRouter(prefix="/api", tags=["intel"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "timestamp": _utcnow().isoformat()}


@router.get("/ready")
def readiness(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    redis_client = Redis.from_url(settings.redis_url)
    redis_client.ping()
    return {"status": "ready", "db": "ok", "redis": "ok", "timestamp": _utcnow().isoformat()}


@router.get("/metrics")
def metrics():
    return metrics_response()


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    if not payload.api_key:
        raise HTTPException(status_code=400, detail="api_key is required")
    user_ctx = authenticate_api_key(db, payload.api_key)
    expires = payload.expires_minutes or settings.jwt_expire_minutes
    token = create_access_token(
        subject={
            "user_id": user_ctx.user_id,
            "org_id": user_ctx.org_id,
            "role": user_ctx.role,
            "name": user_ctx.name,
        },
        expires_minutes=expires,
    )
    return LoginResponse(access_token=token, expires_in=expires * 60, user=user_ctx)


@router.get("/auth/whoami")
def whoami(user: UserContext = Depends(get_current_user)):
    return user


@router.post("/auth/rotate-key", response_model=RotateKeyResponse)
def rotate_api_key(
    scope: str = Query(default="user", pattern="^(user|org)$"),
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("org_admin")),
):
    now = _utcnow()
    if scope == "org":
        org = db.query(Organization).filter(Organization.id == user.org_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        new_key = generate_api_key(prefix=f"org{org.id}")
        org.api_key_hash = hash_api_key(new_key)
        org.key_rotated_at = now
        if settings.allow_plain_api_keys:
            org.api_key = new_key
        else:
            org.api_key = None
        db.commit()
        return RotateKeyResponse(scope=scope, subject_id=org.id, new_api_key=new_key, rotated_at=now)

    current_user = db.query(User).filter(User.id == user.user_id).first()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")
    new_key = generate_api_key(prefix=f"user{current_user.id}")
    current_user.api_key_hash = hash_api_key(new_key)
    current_user.key_rotated_at = now
    if settings.allow_plain_api_keys:
        current_user.api_key = new_key
    else:
        current_user.api_key = None
    db.commit()
    return RotateKeyResponse(scope=scope, subject_id=current_user.id, new_api_key=new_key, rotated_at=now)


@router.get("/feed", response_model=FeedResponse)
def feed(
    org_id: int | None = Query(default=None),
    indicator_type: str | None = Query(default=None),
    min_severity: float | None = Query(default=None),
    min_credibility: float | None = Query(default=None),
    hours: int | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    query = db.query(ThreatIntel)

    if user.role not in {"org_admin", "analyst"}:
        query = query.filter(ThreatIntel.org_id == user.org_id)
    elif org_id:
        query = query.filter(ThreatIntel.org_id == org_id)

    if indicator_type:
        query = query.filter(ThreatIntel.indicator_type == indicator_type.lower())
    if min_severity is not None:
        query = query.filter(ThreatIntel.severity >= min_severity)
    if min_credibility is not None:
        query = query.filter(ThreatIntel.credibility >= min_credibility)
    if hours is not None:
        cutoff = _utcnow() - timedelta(hours=hours)
        query = query.filter(ThreatIntel.timestamp >= cutoff)

    total = query.with_entities(func.count(ThreatIntel.id)).scalar() or 0
    items = query.order_by(ThreatIntel.timestamp.desc()).limit(limit).all()
    return FeedResponse(items=items, total=total)


@router.post("/intel", response_model=IntelOut)
def create_intel(
    payload: IntelCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("contributor")),
):
    contributor_id = payload.contributor_id or user.user_id
    intel = create_intel_record(
        db=db,
        org_id=user.org_id,
        contributor_id=contributor_id,
        indicator_type=payload.indicator_type,
        value=payload.value,
        tags=payload.tags,
        source=payload.source,
        timestamp=payload.timestamp,
        confidence=payload.confidence,
        context_text=payload.context_text,
        evidence=payload.evidence,
    )
    if not intel:
        raise HTTPException(status_code=409, detail="Duplicate intel")

    db.commit()
    db.refresh(intel)
    return intel


@router.get("/intel/{intel_id}", response_model=IntelOut)
def intel_detail(
    intel_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    intel = db.query(ThreatIntel).filter(ThreatIntel.id == intel_id).first()
    if not intel:
        raise HTTPException(status_code=404, detail="Not found")
    if user.role in {"viewer", "contributor"} and intel.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return intel


@router.get("/intel/{intel_id}/proof")
def intel_proof(
    intel_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    intel = db.query(ThreatIntel).filter(ThreatIntel.id == intel_id).first()
    if not intel:
        raise HTTPException(status_code=404, detail="Intel not found")
    if user.role in {"viewer", "contributor"} and intel.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    ledger = db.query(LedgerEntry).filter(LedgerEntry.intel_id == intel_id).order_by(LedgerEntry.id.asc()).all()
    return {
        "intel_id": intel_id,
        "entries": [
            {
                "ledger_id": e.id,
                "prev_hash": e.prev_hash,
                "hash": e.hash,
                "signature": e.signature,
                "created_at": e.created_at,
            }
            for e in ledger
        ],
    }


@router.get("/intel/{intel_id}/similar")
def intel_similar(
    intel_id: int,
    limit: int = Query(default=5, le=20),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    intel = db.query(ThreatIntel).filter(ThreatIntel.id == intel_id).first()
    if not intel:
        raise HTTPException(status_code=404, detail="Intel not found")
    if user.role in {"viewer", "contributor"} and intel.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if intel.embedding_semantic is not None:
        distance = ThreatIntel.embedding_semantic.cosine_distance(intel.embedding_semantic).label("distance")
        q = db.query(ThreatIntel, distance).filter(
            ThreatIntel.id != intel_id,
            ThreatIntel.embedding_semantic.is_not(None),
        )
    elif intel.embedding is not None:
        distance = ThreatIntel.embedding.cosine_distance(intel.embedding).label("distance")
        q = db.query(ThreatIntel, distance).filter(ThreatIntel.id != intel_id, ThreatIntel.embedding.is_not(None))
    else:
        return []

    if user.role in {"viewer", "contributor"}:
        q = q.filter(ThreatIntel.org_id == user.org_id)
    rows = q.order_by(distance.asc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "org_id": row.org_id,
            "value": row.value,
            "indicator_type": row.indicator_type,
            "distance": float(dist),
        }
        for row, dist in rows
    ]


@router.get("/source-reliability")
def source_reliability(
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("analyst")),
):
    rows = db.query(SourceReliability).order_by(SourceReliability.reliability.desc()).all()
    return [
        {
            "id": r.id,
            "pattern": r.source_pattern,
            "reliability": r.reliability,
            "weight": r.weight,
            "enabled": r.enabled,
            "notes": r.notes,
        }
        for r in rows
    ]


@router.patch("/source-reliability/{row_id}")
def update_source_reliability(
    row_id: int,
    payload: SourceReliabilityUpdateRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("analyst")),
):
    row = db.query(SourceReliability).filter(SourceReliability.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Source reliability row not found")
    if payload.reliability is not None:
        row.reliability = payload.reliability
    if payload.weight is not None:
        row.weight = payload.weight
    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.notes is not None:
        row.notes = payload.notes
    db.commit()
    return {
        "id": row.id,
        "pattern": row.source_pattern,
        "reliability": row.reliability,
        "weight": row.weight,
        "enabled": row.enabled,
        "notes": row.notes,
    }


@router.get("/admin/overview", response_model=AdminOverviewOut)
def admin_overview(
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("org_admin")),
):
    org = db.query(Organization).filter(Organization.id == user.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    avg_scores = (
        db.query(func.avg(ThreatIntel.credibility), func.avg(ThreatIntel.severity))
        .filter(ThreatIntel.org_id == user.org_id)
        .first()
    )
    source_count = db.query(func.count(IngestionSource.id)).filter(IngestionSource.org_id == user.org_id).scalar() or 0
    source_enabled_count = (
        db.query(func.count(IngestionSource.id))
        .filter(IngestionSource.org_id == user.org_id, IngestionSource.enabled.is_(True))
        .scalar()
        or 0
    )
    source_error_count = (
        db.query(func.count(IngestionSource.id))
        .filter(IngestionSource.org_id == user.org_id, IngestionSource.last_status == "error")
        .scalar()
        or 0
    )
    recent_run_count = (
        db.query(func.count(IngestionRun.id))
        .filter(IngestionRun.org_id == user.org_id, IngestionRun.started_at >= _utcnow() - timedelta(hours=24))
        .scalar()
        or 0
    )
    active_intel_count = db.query(func.count(ThreatIntel.id)).filter(ThreatIntel.org_id == user.org_id).scalar() or 0
    critical_intel_count = (
        db.query(func.count(ThreatIntel.id))
        .filter(ThreatIntel.org_id == user.org_id, ThreatIntel.severity >= 80)
        .scalar()
        or 0
    )
    ready = True
    try:
        db.execute(text("SELECT 1"))
        Redis.from_url(settings.redis_url).ping()
    except Exception:
        ready = False

    return AdminOverviewOut(
        org_id=org.id,
        org_name=org.name,
        user_count=db.query(func.count(User.id)).filter(User.org_id == user.org_id).scalar() or 0,
        contributor_count=(
            db.query(func.count(User.id)).filter(User.org_id == user.org_id, User.role == "contributor").scalar() or 0
        ),
        source_count=source_count,
        source_enabled_count=source_enabled_count,
        source_error_count=source_error_count,
        recent_run_count=recent_run_count,
        policy_count=(
            db.query(func.count(FederationPolicy.id)).filter(FederationPolicy.from_org_id == user.org_id).scalar() or 0
        ),
        active_intel_count=active_intel_count,
        critical_intel_count=critical_intel_count,
        avg_credibility=round(float(avg_scores[0] or 0), 2),
        avg_severity=round(float(avg_scores[1] or 0), 2),
        ready=ready,
        generated_at=_utcnow(),
    )


@router.get("/admin/users")
def admin_users(
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("org_admin")),
):
    rows = db.query(User).filter(User.org_id == user.org_id).order_by(User.role.desc(), User.name.asc()).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "org_id": row.org_id,
            "role": row.role,
            "reputation": round(row.reputation, 2),
            "is_active": row.is_active,
            "key_rotated_at": row.key_rotated_at,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/admin/federation-policies", response_model=list[FederationPolicyOut])
def admin_federation_policies(
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("org_admin")),
):
    return (
        db.query(FederationPolicy)
        .filter(FederationPolicy.from_org_id == user.org_id)
        .order_by(FederationPolicy.to_org_id.asc())
        .all()
    )


@router.patch("/admin/federation-policies/{policy_id}", response_model=FederationPolicyOut)
def update_federation_policy(
    policy_id: int,
    payload: FederationPolicyUpdateRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("org_admin")),
):
    row = (
        db.query(FederationPolicy)
        .filter(FederationPolicy.id == policy_id, FederationPolicy.from_org_id == user.org_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Federation policy not found")
    if payload.min_credibility is not None:
        row.min_credibility = payload.min_credibility
    if payload.min_reputation is not None:
        row.min_reputation = payload.min_reputation
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return row


@router.get("/admin/ingestion-sources", response_model=list[IngestionSourceOut])
def admin_ingestion_sources(
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("org_admin")),
):
    rows = (
        db.query(IngestionSource)
        .filter(IngestionSource.org_id == user.org_id)
        .order_by(IngestionSource.name.asc())
        .all()
    )
    return rows


@router.get("/admin/ingestion-runs", response_model=list[IngestionRunOut])
def admin_ingestion_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("org_admin")),
):
    return (
        db.query(IngestionRun)
        .filter(IngestionRun.org_id == user.org_id)
        .order_by(IngestionRun.started_at.desc())
        .limit(limit)
        .all()
    )


@router.patch("/admin/ingestion-sources/{source_id}", response_model=IngestionSourceOut)
def update_ingestion_source(
    source_id: int,
    payload: IngestionSourceUpdateRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("org_admin")),
):
    row = db.query(IngestionSource).filter(IngestionSource.id == source_id, IngestionSource.org_id == user.org_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Ingestion source not found")

    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.interval_minutes is not None:
        if payload.interval_minutes < 1:
            raise HTTPException(status_code=400, detail="interval_minutes must be >= 1")
        row.interval_minutes = payload.interval_minutes
    if payload.max_rows is not None:
        if payload.max_rows < 1:
            raise HTTPException(status_code=400, detail="max_rows must be >= 1")
        row.max_rows = payload.max_rows
    if payload.config is not None:
        row.config = payload.config

    db.commit()
    db.refresh(row)
    return row


@router.post("/admin/ingestion-sources/{source_id}/run")
def run_ingestion_source_now(
    source_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("org_admin")),
):
    row = db.query(IngestionSource).filter(IngestionSource.id == source_id, IngestionSource.org_id == user.org_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Ingestion source not found")
    task = run_ingestion_source_job.delay(row.id, "manual")
    return {"queued": True, "task_id": task.id, "source_id": row.id, "name": row.name}


@router.post("/admin/ingestion/run-due")
def run_due_ingestion_for_org(
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("org_admin")),
):
    due = get_due_ingestion_sources(db, org_id=user.org_id)
    task = run_due_ingestion_sources_job.delay(user.org_id)
    return {
        "queued": True,
        "task_id": task.id,
        "due_count": len(due),
        "source_ids": [row.id for row in due],
    }


@router.post("/ingest/rss")
def ingest_from_rss(
    urls: list[str] | None = None,
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("contributor")),
):
    created = ingest_rss(db=db, org_id=user.org_id, contributor_id=user.user_id, urls=urls)
    return {"created": created}


@router.post("/ingest/text")
def ingest_text(
    payload: IngestTextRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("contributor")),
):
    created = ingest_text_dump(
        db=db,
        org_id=user.org_id,
        text=payload.text,
        source=payload.source,
        contributor_id=payload.contributor_id or user.user_id,
    )
    return {"created": created}


@router.post("/ingest/csv")
def ingest_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("contributor")),
):
    payload = file.file.read()
    created = ingest_csv_bytes(
        db=db,
        org_id=user.org_id,
        payload=payload,
        contributor_id=user.user_id,
        source=f"csv:{file.filename}",
    )
    return {"created": created}


@router.post("/federation/run", response_model=FederationRunResponse)
def run_federation_now(
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("analyst")),
):
    shared, details = run_federation(db)
    return FederationRunResponse(shared_count=shared, details=details)


@router.post("/integrity/anchor")
def create_integrity_anchor(
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("analyst")),
):
    anchor = create_anchor(db)
    db.commit()
    if not anchor:
        return {"created": False}
    return {
        "created": True,
        "anchor_id": anchor.id,
        "up_to_ledger_id": anchor.up_to_ledger_id,
        "head_hash": anchor.head_hash,
    }


@router.get("/integrity/anchors")
def integrity_anchors(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("analyst")),
):
    rows = db.query(LedgerAnchor).order_by(LedgerAnchor.created_at.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "up_to_ledger_id": row.up_to_ledger_id,
            "head_hash": row.head_hash,
            "anchor_hash": row.anchor_hash,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/integrity/verify", response_model=IntegrityVerifyResponse)
def verify_integrity(
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("analyst")),
):
    status, idx, checked = verify_chain(db)
    return IntegrityVerifyResponse(status=status, first_broken_index=idx, checked_entries=checked)


@router.get("/contributors")
def contributors(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    query = db.query(User).filter(User.role == "contributor")
    if user.role not in {"org_admin", "analyst"}:
        query = query.filter(User.org_id == user.org_id)
    rows = query.order_by(User.reputation.desc()).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "org_id": r.org_id,
            "reputation": round(r.reputation, 2),
            "role": r.role,
        }
        for r in rows
    ]


@router.post("/contributors/action")
def contributor_action(
    payload: ReputationActionRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_role("analyst")),
):
    contributor = db.query(User).filter(User.id == payload.contributor_id, User.role == "contributor").first()
    intel = db.query(ThreatIntel).filter(ThreatIntel.id == payload.intel_id).first()
    if not contributor or not intel:
        raise HTTPException(status_code=404, detail="Contributor or intel not found")

    if payload.action == "approve":
        delta = 4.0
    elif payload.action == "upvote":
        delta = 2.0
    elif payload.action == "flag":
        delta = -6.0
    else:
        raise HTTPException(status_code=400, detail="Action must be approve/upvote/flag")

    contributor.reputation = max(0.0, min(100.0, contributor.reputation + delta))

    event = ReputationEvent(
        contributor_id=contributor.id,
        analyst_id=user.user_id,
        intel_id=intel.id,
        action=payload.action,
        delta=delta,
    )
    db.add(event)
    db.commit()

    return {
        "contributor_id": contributor.id,
        "new_reputation": round(contributor.reputation, 2),
        "delta": delta,
    }
