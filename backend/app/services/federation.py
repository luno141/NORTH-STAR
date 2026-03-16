from sqlalchemy.orm import Session

from app.models.models import FederationPolicy, ThreatIntel, User
from app.services.intel import create_intel_record


def run_federation(db: Session) -> tuple[int, list[dict]]:
    policies = db.query(FederationPolicy).filter(FederationPolicy.enabled.is_(True)).all()
    shared = 0
    details: list[dict] = []

    for policy in policies:
        intel_rows = (
            db.query(ThreatIntel)
            .filter(
                ThreatIntel.org_id == policy.from_org_id,
                ThreatIntel.credibility >= policy.min_credibility,
            )
            .order_by(ThreatIntel.created_at.desc())
            .limit(50)
            .all()
        )

        for intel in intel_rows:
            if intel.contributor_id is None:
                continue
            if intel.visibility == "private":
                continue
            contributor = db.query(User).filter(User.id == intel.contributor_id).first()
            contributor_rep = contributor.reputation if contributor else 50.0
            if contributor_rep < policy.min_reputation:
                continue

            exists = (
                db.query(ThreatIntel)
                .filter(
                    ThreatIntel.org_id == policy.to_org_id,
                    ThreatIntel.value == intel.value,
                    ThreatIntel.indicator_type == intel.indicator_type,
                    ThreatIntel.shared_from_org_id == policy.from_org_id,
                )
                .first()
            )
            if exists:
                continue

            cloned = create_intel_record(
                db=db,
                org_id=policy.to_org_id,
                indicator_type=intel.indicator_type,
                value=intel.value,
                tags=intel.tags,
                source=f"federated:{intel.source}",
                timestamp=intel.timestamp,
                confidence=max(intel.confidence - 5, 10),
                context_text=intel.context_text,
                evidence=intel.evidence,
                contributor_id=intel.contributor_id,
                shared_from_org_id=policy.from_org_id,
                allow_duplicates=False,
            )
            if cloned:
                shared += 1
                details.append({
                    "from_org_id": policy.from_org_id,
                    "to_org_id": policy.to_org_id,
                    "intel_id": cloned.id,
                })

    db.commit()
    return shared, details
