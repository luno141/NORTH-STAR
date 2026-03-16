from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.ml.scoring import compute_scores, predict_label_probs, semantic_embedding, text_embedding
from app.models.models import SourceReliability, ThreatIntel, User


def _contributor_rep(db: Session, contributor_id: int | None) -> float:
    if not contributor_id:
        return 50.0
    row = db.query(User).filter(User.id == contributor_id).first()
    return float(row.reputation) if row else 50.0


def _source_reliability(db: Session, source: str) -> tuple[float, float]:
    source_lower = source.lower()
    rows = (
        db.query(SourceReliability)
        .filter(SourceReliability.enabled.is_(True))
        .all()
    )
    best = None
    for row in rows:
        pattern = row.source_pattern.lower()
        if pattern in source_lower:
            if best is None or len(pattern) > len(best.source_pattern):
                best = row
    if best:
        return float(best.reliability), float(best.weight)
    return 60.0, 1.0


def main() -> None:
    db: Session = SessionLocal()
    try:
        rows = db.query(ThreatIntel).order_by(ThreatIntel.id.asc()).all()
        updated = 0
        for intel in rows:
            rep = _contributor_rep(db, intel.contributor_id)
            src_rel, src_w = _source_reliability(db, intel.source)
            combined_text = f"{intel.context_text} {intel.evidence} {intel.value}"
            label, labels, probs, terms, model_confidence = predict_label_probs(combined_text)
            severity, credibility = compute_scores(
                prob_map=probs,
                labels=labels,
                model_confidence=model_confidence,
                base_confidence=float(intel.confidence),
                contributor_reputation=rep,
                source_reliability=src_rel,
                source_weight=src_w,
                source=intel.source,
                indicator_type=intel.indicator_type,
                value=intel.value,
                tags=intel.tags or [],
                context_text=intel.context_text,
                evidence=intel.evidence,
            )

            intel.classification = label
            intel.classification_labels = labels
            intel.model_confidence = model_confidence
            intel.predicted_probs = probs
            intel.explanation_terms = terms
            intel.severity = severity
            intel.credibility = credibility
            intel.embedding = text_embedding(combined_text)
            intel.embedding_semantic = semantic_embedding(combined_text)
            updated += 1

        db.commit()
        print(f"Rescored {updated} intel rows")
    finally:
        db.close()


if __name__ == "__main__":
    main()
