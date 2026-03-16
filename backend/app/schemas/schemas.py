from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    user_id: int
    org_id: int
    role: str
    name: str
    auth_type: str = "api_key"


class IntelBase(BaseModel):
    indicator_type: str
    value: str
    tags: list[str] = Field(default_factory=list)
    source: str
    timestamp: datetime
    confidence: float = 50.0
    severity: Optional[float] = None
    context_text: str
    evidence: str


class IntelCreate(IntelBase):
    contributor_id: Optional[int] = None


class IntelOut(IntelBase):
    id: int
    org_id: int
    credibility: float
    classification: str
    classification_labels: list[str] = Field(default_factory=list)
    model_confidence: float = 0.0
    predicted_probs: dict[str, float]
    explanation_terms: list[str] = Field(default_factory=list)
    visibility: str
    shared_from_org_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FeedResponse(BaseModel):
    items: list[IntelOut]
    total: int


class IngestTextRequest(BaseModel):
    text: str
    source: str = "paste"
    contributor_id: Optional[int] = None


class ReputationActionRequest(BaseModel):
    contributor_id: int
    intel_id: int
    action: str


class IntegrityVerifyResponse(BaseModel):
    status: str
    first_broken_index: Optional[int] = None
    checked_entries: int


class FederationRunResponse(BaseModel):
    shared_count: int
    details: list[dict[str, Any]]


class FederationPolicyOut(BaseModel):
    id: int
    from_org_id: int
    to_org_id: int
    min_credibility: float
    min_reputation: float
    enabled: bool

    class Config:
        from_attributes = True


class FederationPolicyUpdateRequest(BaseModel):
    min_credibility: Optional[float] = None
    min_reputation: Optional[float] = None
    enabled: Optional[bool] = None


class LoginRequest(BaseModel):
    api_key: str
    expires_minutes: Optional[int] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserContext


class RotateKeyResponse(BaseModel):
    scope: str
    subject_id: int
    new_api_key: str
    rotated_at: datetime


class IngestionSourceOut(BaseModel):
    id: int
    name: str
    source_kind: str
    org_id: int
    contributor_id: Optional[int] = None
    enabled: bool
    interval_minutes: int
    max_rows: int
    config: dict[str, Any] = Field(default_factory=dict)
    last_polled_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_status: str
    last_error: Optional[str] = None
    last_created_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IngestionSourceUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_minutes: Optional[int] = None
    max_rows: Optional[int] = None
    config: Optional[dict[str, Any]] = None


class IngestionRunOut(BaseModel):
    id: int
    source_id: int
    org_id: int
    status: str
    trigger: str
    task_id: Optional[str] = None
    created_count: int
    error_message: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SourceReliabilityOut(BaseModel):
    id: int
    pattern: str
    reliability: float
    weight: float
    enabled: bool
    notes: str


class SourceReliabilityUpdateRequest(BaseModel):
    reliability: Optional[float] = None
    weight: Optional[float] = None
    enabled: Optional[bool] = None
    notes: Optional[str] = None


class AdminUserOut(BaseModel):
    id: int
    name: str
    org_id: int
    role: str
    reputation: float
    is_active: bool
    key_rotated_at: Optional[datetime] = None
    created_at: datetime


class AdminOverviewOut(BaseModel):
    org_id: int
    org_name: str
    user_count: int
    contributor_count: int
    source_count: int
    source_enabled_count: int
    source_error_count: int
    recent_run_count: int
    policy_count: int
    active_intel_count: int
    critical_intel_count: int
    avg_credibility: float
    avg_severity: float
    ready: bool
    generated_at: datetime
