from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    api_key: Mapped[Optional[str]] = mapped_column(String(120), unique=True, index=True, nullable=True)
    api_key_hash: Mapped[Optional[str]] = mapped_column(String(128), unique=True, index=True, nullable=True)
    key_rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    users: Mapped[list[User]] = relationship(back_populates="org")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(32), index=True)
    reputation: Mapped[float] = mapped_column(Float, default=50.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    api_key: Mapped[Optional[str]] = mapped_column(String(120), unique=True, nullable=True)
    api_key_hash: Mapped[Optional[str]] = mapped_column(String(128), unique=True, index=True, nullable=True)
    key_rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    org: Mapped[Organization] = relationship(back_populates="users")


class ThreatIntel(Base):
    __tablename__ = "threat_intel"
    __table_args__ = (
        UniqueConstraint("org_id", "indicator_type", "value", "source", name="uq_intel_dedup"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    contributor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    shared_from_org_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    indicator_type: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[str] = mapped_column(String(255), index=True)
    value_canonical: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(120), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=50.0)
    severity: Mapped[float] = mapped_column(Float, default=50.0, index=True)
    credibility: Mapped[float] = mapped_column(Float, default=50.0, index=True)
    context_text: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)

    classification: Mapped[str] = mapped_column(String(64), default="discussion", index=True)
    classification_labels: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_probs: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    visibility: Mapped[str] = mapped_column(String(32), default="org")
    embedding: Mapped[list[float]] = mapped_column(Vector(32), nullable=True)
    embedding_semantic: Mapped[Optional[list[float]]] = mapped_column(Vector(384), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intel_id: Mapped[int] = mapped_column(ForeignKey("threat_intel.id"), index=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    prev_hash: Mapped[str] = mapped_column(String(128), default="GENESIS")
    hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    signature: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class LedgerAnchor(Base):
    __tablename__ = "ledger_anchors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    up_to_ledger_id: Mapped[int] = mapped_column(Integer, index=True)
    head_hash: Mapped[str] = mapped_column(String(128), index=True)
    prev_anchor_hash: Mapped[str] = mapped_column(String(128), default="GENESIS")
    anchor_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class SourceReliability(Base):
    __tablename__ = "source_reliability"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_pattern: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    reliability: Mapped[float] = mapped_column(Float, default=60.0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    notes: Mapped[str] = mapped_column(String(255), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class IngestionSource(Base):
    __tablename__ = "ingestion_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    source_kind: Mapped[str] = mapped_column(String(32), index=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    contributor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    max_rows: Mapped[int] = mapped_column(Integer, default=250)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    last_polled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(String(32), default="idle")
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_created_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("ingestion_sources.id"), index=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="running")
    trigger: Mapped[str] = mapped_column(String(32), default="scheduler")
    task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class FederationPolicy(Base):
    __tablename__ = "federation_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    to_org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    min_credibility: Mapped[float] = mapped_column(Float, default=60.0)
    min_reputation: Mapped[float] = mapped_column(Float, default=50.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ReputationEvent(Base):
    __tablename__ = "reputation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contributor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    analyst_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    intel_id: Mapped[int] = mapped_column(ForeignKey("threat_intel.id"), index=True)
    action: Mapped[str] = mapped_column(String(32))
    delta: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
