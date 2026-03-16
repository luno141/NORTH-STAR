from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import SourceReliability
from app.services.security import hash_api_key


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table
              AND column_name = :column
            LIMIT 1
            """
        ),
        {"table": table, "column": column},
    ).first()
    return row is not None


def _column_type(conn: Connection, table: str, column: str) -> str | None:
    row = conn.execute(
        text(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table
              AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    ).first()
    return str(row[0]).lower() if row else None


def _ensure_extensions(conn: Connection) -> None:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))


def _alter_timestamp_to_timestamptz(conn: Connection, table: str, column: str) -> None:
    if not _column_exists(conn, table, column):
        return
    dtype = _column_type(conn, table, column)
    if dtype == "timestamp with time zone":
        return
    conn.execute(
        text(
            f"""
            ALTER TABLE {table}
            ALTER COLUMN {column}
            TYPE TIMESTAMPTZ
            USING {column} AT TIME ZONE 'UTC'
            """
        )
    )


def _ensure_columns(conn: Connection) -> None:
    conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS api_key_hash VARCHAR(128)"))
    conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS key_rotated_at TIMESTAMPTZ"))
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS api_key_hash VARCHAR(128)"))
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS key_rotated_at TIMESTAMPTZ"))
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()"))

    conn.execute(text("ALTER TABLE threat_intel ADD COLUMN IF NOT EXISTS value_canonical VARCHAR(255)"))
    conn.execute(
        text(
            "ALTER TABLE threat_intel ADD COLUMN IF NOT EXISTS classification_labels JSON DEFAULT '[]'::json"
        )
    )
    conn.execute(text("ALTER TABLE threat_intel ADD COLUMN IF NOT EXISTS model_confidence DOUBLE PRECISION DEFAULT 0.0"))
    conn.execute(text("ALTER TABLE threat_intel ADD COLUMN IF NOT EXISTS embedding_semantic VECTOR(384)"))

    conn.execute(text("ALTER TABLE ledger_entries ADD COLUMN IF NOT EXISTS signature VARCHAR(128)"))


def _ensure_indexes(conn: Connection) -> None:
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_organizations_api_key_hash ON organizations (api_key_hash)"))
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_api_key_hash ON users (api_key_hash)"))

    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_threat_intel_value_canonical ON threat_intel (value_canonical)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_threat_intel_timestamp ON threat_intel (timestamp DESC)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_threat_intel_created_at ON threat_intel (created_at DESC)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_threat_intel_value_trgm ON threat_intel USING gin (value gin_trgm_ops)"))

    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ingestion_sources_enabled ON ingestion_sources (enabled)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ingestion_sources_org_id ON ingestion_sources (org_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ingestion_sources_last_polled_at ON ingestion_sources (last_polled_at)"))

    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ingestion_runs_source_id ON ingestion_runs (source_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ingestion_runs_org_id ON ingestion_runs (org_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ingestion_runs_started_at ON ingestion_runs (started_at DESC)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ingestion_runs_status ON ingestion_runs (status)"))

    try:
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_threat_intel_embedding_semantic_ivfflat
                ON threat_intel USING ivfflat (embedding_semantic vector_cosine_ops) WITH (lists = 100)
                """
            )
        )
    except Exception:
        pass


def _backfill_api_key_hashes(conn: Connection) -> None:
    users = conn.execute(text("SELECT id, api_key, api_key_hash FROM users")).all()
    for row in users:
        if row.api_key and not row.api_key_hash:
            conn.execute(
                text("UPDATE users SET api_key_hash = :h WHERE id = :id"),
                {"h": hash_api_key(row.api_key), "id": row.id},
            )

    orgs = conn.execute(text("SELECT id, api_key, api_key_hash FROM organizations")).all()
    for row in orgs:
        if row.api_key and not row.api_key_hash:
            conn.execute(
                text("UPDATE organizations SET api_key_hash = :h WHERE id = :id"),
                {"h": hash_api_key(row.api_key), "id": row.id},
            )

    if not settings.allow_plain_api_keys:
        conn.execute(text("UPDATE users SET api_key = NULL WHERE api_key IS NOT NULL"))
        conn.execute(text("UPDATE organizations SET api_key = NULL WHERE api_key IS NOT NULL"))


def _normalize_value_canonical(conn: Connection) -> None:
    conn.execute(
        text(
            """
            UPDATE threat_intel
            SET value_canonical = lower(regexp_replace(value, '[/\\s]+$', '', 'g'))
            WHERE value_canonical IS NULL
            """
        )
    )


def _migrate_timestamps(conn: Connection) -> None:
    for table, column in (
        ("organizations", "created_at"),
        ("users", "created_at"),
        ("threat_intel", "timestamp"),
        ("threat_intel", "created_at"),
        ("ledger_entries", "created_at"),
        ("reputation_events", "created_at"),
        ("ingestion_sources", "created_at"),
        ("ingestion_sources", "updated_at"),
        ("ingestion_sources", "last_polled_at"),
        ("ingestion_sources", "last_success_at"),
        ("ingestion_runs", "started_at"),
        ("ingestion_runs", "finished_at"),
    ):
        _alter_timestamp_to_timestamptz(conn, table, column)


def _seed_source_reliability(db: Session) -> None:
    defaults = [
        ("openphish", 91.0, 1.25, "Public phishing IOC feed with high signal"),
        ("urlhaus", 90.0, 1.20, "Curated malware URL feed"),
        ("rss:cisa", 85.0, 1.15, "Government advisory feed"),
        ("rss:kb.cert", 83.0, 1.10, "CERT vulnerability feed"),
        ("rss:", 80.0, 1.05, "Generic advisory feed"),
        ("federated:", 78.0, 1.05, "Shared intel from trusted peers"),
        ("csv:", 72.0, 1.00, "Uploaded batch IOC feed"),
        ("paste", 58.0, 0.95, "Unstructured pasted indicators"),
        ("seed", 65.0, 1.00, "Synthetic seeded demo data"),
    ]
    now = datetime.now(timezone.utc)
    for pattern, reliability, weight, notes in defaults:
        row = db.query(SourceReliability).filter(SourceReliability.source_pattern == pattern).first()
        if row:
            continue
        db.add(
            SourceReliability(
                source_pattern=pattern,
                reliability=reliability,
                weight=weight,
                notes=notes,
                enabled=True,
                updated_at=now,
            )
        )
    db.commit()


def run_schema_migrations(db: Session) -> None:
    conn = db.connection()
    _ensure_extensions(conn)
    _ensure_columns(conn)
    _migrate_timestamps(conn)
    _backfill_api_key_hashes(conn)
    _normalize_value_canonical(conn)
    _ensure_indexes(conn)
    db.commit()
    _seed_source_reliability(db)
