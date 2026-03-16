from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import LedgerAnchor, LedgerEntry, ThreatIntel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_payload(prev_hash: str, payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{prev_hash}:{body}".encode("utf-8")).hexdigest()


def _sign_hash(ledger_hash: str) -> str:
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        ledger_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _anchor_digest(prev_anchor_hash: str, up_to_ledger_id: int, head_hash: str) -> str:
    payload = f"{prev_anchor_hash}:{up_to_ledger_id}:{head_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def append_ledger_entry(db: Session, intel: ThreatIntel) -> LedgerEntry:
    last = db.query(LedgerEntry).order_by(LedgerEntry.id.desc()).first()
    prev_hash = last.hash if last else "GENESIS"
    payload = {
        "intel_id": intel.id,
        "org_id": intel.org_id,
        "indicator_type": intel.indicator_type,
        "value": intel.value,
        "classification": intel.classification,
        "classification_labels": intel.classification_labels,
        "severity": intel.severity,
        "credibility": intel.credibility,
        "created_at": intel.created_at.isoformat() if intel.created_at else _utcnow().isoformat(),
    }
    hsh = _hash_payload(prev_hash, payload)
    entry = LedgerEntry(
        intel_id=intel.id,
        org_id=intel.org_id,
        payload=payload,
        prev_hash=prev_hash,
        hash=hsh,
        signature=_sign_hash(hsh),
    )
    db.add(entry)
    db.flush()

    if settings.anchor_interval > 0 and entry.id % settings.anchor_interval == 0:
        create_anchor(db)
    return entry


def create_anchor(db: Session) -> LedgerAnchor | None:
    head = db.query(LedgerEntry).order_by(LedgerEntry.id.desc()).first()
    if not head:
        return None

    last_anchor = db.query(LedgerAnchor).order_by(LedgerAnchor.id.desc()).first()
    if last_anchor and last_anchor.up_to_ledger_id >= head.id:
        return None

    prev_anchor_hash = last_anchor.anchor_hash if last_anchor else "GENESIS"
    anchor_hash = _anchor_digest(prev_anchor_hash, head.id, head.hash)
    anchor = LedgerAnchor(
        up_to_ledger_id=head.id,
        head_hash=head.hash,
        prev_anchor_hash=prev_anchor_hash,
        anchor_hash=anchor_hash,
        created_at=_utcnow(),
    )
    db.add(anchor)
    db.flush()
    return anchor


def verify_chain(db: Session) -> tuple[str, int | None, int]:
    entries = db.query(LedgerEntry).order_by(LedgerEntry.id.asc()).all()
    expected_prev = "GENESIS"
    for i, entry in enumerate(entries):
        calc = _hash_payload(entry.prev_hash, entry.payload)
        signature_ok = entry.signature == _sign_hash(entry.hash) if entry.signature else False
        if entry.prev_hash != expected_prev or calc != entry.hash or not signature_ok:
            return "FAIL", i, len(entries)
        expected_prev = entry.hash

    # Verify anchors against ledger head snapshots.
    anchors = db.query(LedgerAnchor).order_by(LedgerAnchor.id.asc()).all()
    expected_anchor_prev = "GENESIS"
    for anchor in anchors:
        expected_anchor_hash = _anchor_digest(expected_anchor_prev, anchor.up_to_ledger_id, anchor.head_hash)
        if anchor.prev_anchor_hash != expected_anchor_prev or anchor.anchor_hash != expected_anchor_hash:
            return "FAIL", anchor.up_to_ledger_id, len(entries)

        head = db.query(LedgerEntry).filter(LedgerEntry.id == anchor.up_to_ledger_id).first()
        if not head or head.hash != anchor.head_hash:
            return "FAIL", anchor.up_to_ledger_id, len(entries)
        expected_anchor_prev = anchor.anchor_hash

    return "PASS", None, len(entries)
