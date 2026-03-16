from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
from sqlalchemy.orm import Session

from app.services.intel import create_intel_record


DEFAULT_RSS = [
    "https://www.cisa.gov/uscert/ncas/current-activity.xml",
    "https://www.kb.cert.org/vuls/rss",
]


def _coerce_utc_naive(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    raw = value.strip()
    if not raw:
        return datetime.now(timezone.utc)

    try:
        iso_raw = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_raw)
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc)
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass

    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def ingest_rss(
    db: Session,
    org_id: int,
    contributor_id: int | None,
    urls: list[str] | None = None,
    limit_per_feed: int = 10,
) -> int:
    urls = urls or DEFAULT_RSS
    created = 0
    for url in urls:
        parsed = feedparser.parse(url)
        for item in parsed.entries[: max(1, limit_per_feed)]:
            link = item.get("link", "")
            summary = item.get("summary", "")
            title = item.get("title", "Untitled")
            ts = datetime.now(timezone.utc)
            if item.get("published"):
                try:
                    ts = parsedate_to_datetime(item.get("published")).astimezone(timezone.utc)
                except Exception:
                    pass
            created_row = create_intel_record(
                db=db,
                org_id=org_id,
                contributor_id=contributor_id,
                indicator_type="url",
                value=link or title,
                tags=["rss", "advisory"],
                source=f"rss:{url}",
                timestamp=ts,
                confidence=72,
                context_text=title,
                evidence=summary[:1200],
            )
            if created_row:
                created += 1
    db.commit()
    return created


def ingest_text_dump(db: Session, org_id: int, text: str, source: str, contributor_id: int | None) -> int:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    created = 0
    for line in lines:
        parts = line.split("|")
        value = parts[0].strip()
        ctx = parts[1].strip() if len(parts) > 1 else line
        created_row = create_intel_record(
            db=db,
            org_id=org_id,
            contributor_id=contributor_id,
            indicator_type="text",
            value=value,
            tags=["paste", "dump"],
            source=source,
            timestamp=datetime.now(timezone.utc),
            confidence=60,
            context_text=ctx,
            evidence=line,
        )
        if created_row:
            created += 1
    db.commit()
    return created


def ingest_csv_bytes(
    db: Session,
    org_id: int,
    payload: bytes,
    contributor_id: int | None,
    source: str = "csv_upload",
) -> int:
    text = payload.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    created = 0
    for row in reader:
        value = (row.get("value") or "").strip()
        if not value:
            continue
        created_row = create_intel_record(
            db=db,
            org_id=org_id,
            contributor_id=contributor_id,
            indicator_type=(row.get("indicator_type") or "text").strip(),
            value=value,
            tags=[t.strip() for t in (row.get("tags") or "").split(",") if t.strip()],
            source=source,
            timestamp=_coerce_utc_naive(row.get("timestamp")),
            confidence=float(row.get("confidence") or 58),
            context_text=row.get("context_text") or value,
            evidence=row.get("evidence") or row.get("context_text") or value,
        )
        if created_row:
            created += 1
    db.commit()
    return created
