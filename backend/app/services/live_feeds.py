from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import IngestionRun, IngestionSource
from app.services.ingestion import DEFAULT_RSS, ingest_rss
from app.services.intel import create_intel_record

OPENPHISH_FEED = "https://openphish.com/feed.txt"
URLHAUS_RECENT = "https://urlhaus.abuse.ch/downloads/csv_recent/"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def fetch_openphish_rows(max_rows: int) -> list[dict[str, object]]:
    resp = requests.get(OPENPHISH_FEED, timeout=settings.live_feed_request_timeout_seconds)
    resp.raise_for_status()

    rows: list[dict[str, object]] = []
    fetched_at = utcnow()
    for idx, line in enumerate(resp.text.splitlines()):
        url = line.strip()
        if not url:
            continue
        rows.append(
            {
                "indicator_type": "url",
                "value": url,
                "tags": ["phishing", "openphish", "real"],
                "timestamp": fetched_at - timedelta(seconds=idx),
                "confidence": 84.0,
                "context_text": "OpenPhish live feed indicator",
                "evidence": "source=openphish_feed",
                "source": "openphish",
            }
        )
        if len(rows) >= max_rows:
            break
    return rows


def fetch_urlhaus_rows(max_rows: int) -> list[dict[str, object]]:
    resp = requests.get(URLHAUS_RECENT, timeout=settings.live_feed_request_timeout_seconds)
    resp.raise_for_status()

    clean_lines = [line for line in resp.text.splitlines() if line and not line.startswith("#")]
    reader = csv.reader(io.StringIO("\n".join(clean_lines)))

    rows: list[dict[str, object]] = []
    for raw in reader:
        if len(raw) < 3:
            continue
        date_added = raw[1].strip() if len(raw) > 1 else ""
        url = raw[2].strip()
        threat = raw[5].strip().lower() if len(raw) > 5 else "malware_download"
        tags = [t.strip() for t in (raw[6].strip() if len(raw) > 6 else "malware,urlhaus").split(",") if t.strip()]
        link = raw[7].strip() if len(raw) > 7 else "source=urlhaus"
        if not url:
            continue

        timestamp = utcnow()
        try:
            if date_added:
                timestamp = datetime.strptime(date_added, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            timestamp = utcnow()

        rows.append(
            {
                "indicator_type": "url",
                "value": url,
                "tags": [*tags, "urlhaus", "real"],
                "timestamp": timestamp,
                "confidence": 88.0,
                "context_text": f"URLhaus threat={threat}",
                "evidence": link,
                "source": "urlhaus",
            }
        )
        if len(rows) >= max_rows:
            break
    return rows


def get_due_ingestion_sources(db: Session, org_id: int | None = None) -> list[IngestionSource]:
    query = db.query(IngestionSource).filter(IngestionSource.enabled.is_(True))
    if org_id is not None:
        query = query.filter(IngestionSource.org_id == org_id)

    now = utcnow()
    due: list[IngestionSource] = []
    for source in query.order_by(IngestionSource.id.asc()).all():
        if source.last_status == "running" and source.last_polled_at and source.last_polled_at >= now - timedelta(
            minutes=max(1, source.interval_minutes)
        ):
            continue
        if source.last_polled_at is None:
            due.append(source)
            continue
        if source.last_polled_at <= now - timedelta(minutes=max(1, source.interval_minutes)):
            due.append(source)
    return due


def _create_run(db: Session, source: IngestionSource, trigger: str, task_id: str | None) -> IngestionRun:
    run = IngestionRun(
        source_id=source.id,
        org_id=source.org_id,
        status="running",
        trigger=trigger,
        task_id=task_id,
        started_at=utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _finish_run(db: Session, run_id: int, status: str, created_count: int = 0, error_message: str | None = None) -> None:
    run = db.query(IngestionRun).filter(IngestionRun.id == run_id).first()
    if not run:
        return
    run.status = status
    run.created_count = created_count
    run.error_message = error_message
    run.finished_at = utcnow()
    db.commit()


def _ingest_rows(db: Session, source: IngestionSource, rows: list[dict[str, object]]) -> int:
    created = 0
    for row in rows:
        try:
            with db.begin_nested():
                created_row = create_intel_record(
                    db=db,
                    org_id=source.org_id,
                    contributor_id=source.contributor_id,
                    indicator_type=str(row["indicator_type"]),
                    value=str(row["value"]),
                    tags=list(row["tags"]),
                    source=str(row["source"]),
                    timestamp=row["timestamp"],
                    confidence=float(row["confidence"]),
                    context_text=str(row["context_text"]),
                    evidence=str(row["evidence"]),
                )
                if created_row:
                    created += 1
        except IntegrityError:
            continue
    db.commit()
    return created


def run_ingestion_source(
    db: Session,
    source: IngestionSource,
    trigger: str = "scheduler",
    task_id: str | None = None,
) -> dict[str, object]:
    now = utcnow()
    if source.last_status == "running" and source.last_polled_at and source.last_polled_at >= now - timedelta(
        minutes=max(1, source.interval_minutes)
    ):
        run = _create_run(db, source, trigger=trigger, task_id=task_id)
        _finish_run(db, run.id, status="skipped_running", error_message="source already running")
        return {"source_id": source.id, "name": source.name, "created": 0, "status": "skipped_running"}

    run = _create_run(db, source, trigger=trigger, task_id=task_id)
    source.last_polled_at = now
    source.last_status = "running"
    source.last_error = None
    db.commit()

    try:
        config = source.config or {}
        max_rows = max(1, int(config.get("max_rows") or source.max_rows or 250))

        if source.source_kind == "openphish":
            created = _ingest_rows(db, source, fetch_openphish_rows(max_rows))
        elif source.source_kind == "urlhaus":
            created = _ingest_rows(db, source, fetch_urlhaus_rows(max_rows))
        elif source.source_kind == "rss":
            urls = config.get("urls") or DEFAULT_RSS
            limit_per_feed = max(1, max_rows // max(1, len(urls)))
            created = ingest_rss(
                db=db,
                org_id=source.org_id,
                contributor_id=source.contributor_id,
                urls=urls,
                limit_per_feed=limit_per_feed,
            )
        else:
            raise ValueError(f"Unsupported source_kind: {source.source_kind}")

        source.last_status = "ok"
        source.last_success_at = utcnow()
        source.last_error = None
        source.last_created_count = created
        db.commit()
        db.refresh(source)
        _finish_run(db, run.id, status="ok", created_count=created)
        return {"source_id": source.id, "name": source.name, "created": created, "status": source.last_status}
    except Exception as exc:
        db.rollback()
        source = db.query(IngestionSource).filter(IngestionSource.id == source.id).first()
        if source:
            source.last_status = "error"
            source.last_error = str(exc)[:1000]
            source.last_created_count = 0
            db.commit()
        _finish_run(db, run.id, status="error", error_message=str(exc)[:1000])
        raise
