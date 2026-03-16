from __future__ import annotations

import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.scoring import (
    compute_scores,
    predict_label_probs,
    semantic_embedding,
    text_embedding,
)
from app.models.models import SourceReliability, ThreatIntel, User
from app.services.ledger import append_ledger_entry


def normalize_indicator_type(indicator_type: str, value: str) -> str:
    v = value.lower().strip()
    if indicator_type:
        return indicator_type.lower().strip()
    if v.startswith("http"):
        return "url"
    if "@" in v and "." in v:
        return "email"
    if "." in v and " " not in v:
        return "domain"
    return "text"


def canonicalize_value(indicator_type: str, value: str) -> str:
    raw = value.strip().lower().replace("[.]", ".")
    raw = re.sub(r"\s+", "", raw)
    if indicator_type == "url":
        try:
            parsed = urlparse(raw)
            host = parsed.netloc.lower()
            path = parsed.path.rstrip("/")
            if path:
                return f"{host}{path}"
            return host or raw.rstrip("/")
        except Exception:
            return raw.rstrip("/")
    return raw.rstrip("/")


def infer_visibility(reputation: float) -> str:
    if reputation >= 75:
        return "federated"
    if reputation >= 40:
        return "org"
    return "private"


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _fuzzy_duplicate(
    db: Session,
    org_id: int,
    indicator_type: str,
    normalized_value: str,
    value_canonical: str,
) -> ThreatIntel | None:
    exact = (
        db.query(ThreatIntel)
        .filter(
            ThreatIntel.org_id == org_id,
            ThreatIntel.indicator_type == indicator_type,
            ThreatIntel.value == normalized_value,
        )
        .first()
    )
    if exact:
        return exact

    exact_canonical = (
        db.query(ThreatIntel)
        .filter(
            ThreatIntel.org_id == org_id,
            ThreatIntel.indicator_type == indicator_type,
            ThreatIntel.value_canonical == value_canonical,
        )
        .first()
    )
    if exact_canonical:
        return exact_canonical

    # Trigram candidate shortlist when available.
    prefix = value_canonical[:18]
    candidates = (
        db.query(ThreatIntel)
        .filter(
            ThreatIntel.org_id == org_id,
            ThreatIntel.indicator_type == indicator_type,
            ThreatIntel.value_canonical.is_not(None),
            ThreatIntel.value_canonical.ilike(f"{prefix}%"),
        )
        .limit(settings.dedup_scan_limit)
        .all()
    )

    if not candidates:
        # Broader fallback using trigram similarity if extension/index available.
        try:
            rows = (
                db.query(ThreatIntel, func.similarity(ThreatIntel.value_canonical, value_canonical).label("sim"))
                .filter(
                    ThreatIntel.org_id == org_id,
                    ThreatIntel.indicator_type == indicator_type,
                    ThreatIntel.value_canonical.is_not(None),
                )
                .order_by(func.similarity(ThreatIntel.value_canonical, value_canonical).desc())
                .limit(settings.dedup_scan_limit)
                .all()
            )
            for intel, sim in rows:
                if float(sim or 0.0) >= settings.dedup_similarity_threshold:
                    return intel
        except Exception:
            return None
        return None

    for candidate in candidates:
        ratio = SequenceMatcher(None, candidate.value_canonical or "", value_canonical).ratio()
        if ratio >= settings.dedup_similarity_threshold:
            return candidate
    return None


def _source_reliability(db: Session, source: str) -> tuple[float, float]:
    source_lower = source.lower()
    rows = (
        db.query(SourceReliability)
        .filter(SourceReliability.enabled.is_(True))
        .order_by(func.length(SourceReliability.source_pattern).desc())
        .all()
    )
    for row in rows:
        pattern = row.source_pattern.lower()
        if pattern and pattern in source_lower:
            return float(row.reliability), float(row.weight)
    return settings.source_reliability_default, 1.0


def create_intel_record(
    db: Session,
    org_id: int,
    indicator_type: str,
    value: str,
    tags: list[str],
    source: str,
    timestamp: datetime,
    confidence: float,
    context_text: str,
    evidence: str,
    contributor_id: Optional[int] = None,
    shared_from_org_id: Optional[int] = None,
    allow_duplicates: bool = False,
):
    indicator_type = normalize_indicator_type(indicator_type, value)
    normalized_value = value.strip().lower()
    value_canonical = canonicalize_value(indicator_type, normalized_value)

    if not allow_duplicates:
        duplicate = _fuzzy_duplicate(
            db=db,
            org_id=org_id,
            indicator_type=indicator_type,
            normalized_value=normalized_value,
            value_canonical=value_canonical,
        )
        if duplicate:
            return None

    contributor_rep = 50.0
    if contributor_id:
        c = db.query(User).filter(User.id == contributor_id).first()
        if c:
            contributor_rep = c.reputation

    source_reliability, source_weight = _source_reliability(db, source)

    combined_text = f"{context_text} {evidence} {normalized_value}"
    classification, labels, probs, terms, model_confidence = predict_label_probs(combined_text)
    severity, credibility = compute_scores(
        prob_map=probs,
        labels=labels,
        model_confidence=model_confidence,
        base_confidence=confidence,
        contributor_reputation=contributor_rep,
        source_reliability=source_reliability,
        source_weight=source_weight,
        source=source,
        indicator_type=indicator_type,
        value=normalized_value,
        tags=tags,
        context_text=context_text,
        evidence=evidence,
    )

    legacy_embedding = text_embedding(combined_text)
    semantic = semantic_embedding(combined_text)

    intel = ThreatIntel(
        org_id=org_id,
        contributor_id=contributor_id,
        shared_from_org_id=shared_from_org_id,
        indicator_type=indicator_type,
        value=normalized_value,
        value_canonical=value_canonical,
        tags=tags,
        source=source,
        timestamp=_as_utc(timestamp),
        confidence=confidence,
        severity=severity,
        credibility=credibility,
        context_text=context_text,
        evidence=evidence,
        classification=classification,
        classification_labels=labels,
        model_confidence=model_confidence,
        predicted_probs=probs,
        explanation_terms=terms,
        visibility=infer_visibility(contributor_rep),
        embedding=legacy_embedding,
        embedding_semantic=semantic,
    )

    db.add(intel)
    db.flush()
    append_ledger_entry(db, intel)
    return intel
