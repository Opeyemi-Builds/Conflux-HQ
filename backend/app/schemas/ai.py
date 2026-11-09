import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DraftKind, DraftStatus
from app.ai.schemas import Evidence


class ClassifyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    channel: str = "unknown"


class ClassificationResponse(BaseModel):
    issue_type: str
    severity: str
    sentiment: str
    language: str
    mentioned_amount: float | None
    mentioned_time: str | None
    is_fraud: bool
    short_summary: str
    confidence: float
    payment_category: str | None = None
    explanation: str | None = None
    evidence_phrases: list[str] = Field(default_factory=list)
    review_status: str | None = None
    routing_queue: str | None = None
    source: str = "rules"
    method: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    latency_ms: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class DraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    kind: DraftKind
    content: str
    status: DraftStatus
    needs_review: bool = False
    decided_by: str | None
    decided_at: datetime | None


class DraftDecision(BaseModel):
    decision: DraftStatus


class InvestigationResponse(BaseModel):
    incident_id: uuid.UUID
    likely_cause: str | None
    cause_confidence: float | None
    summary: str | None
    draft_count: int
    source: str = "rules"
    model: str | None = None
    prompt_version: str | None = None
    latency_ms: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    confidence: float | None = None
    supporting_evidence: list[Evidence] = Field(default_factory=list)
    contradicting_evidence: list[Evidence] = Field(default_factory=list)
    affected_systems: list[str] = Field(default_factory=list)
    affected_channels: list[str] = Field(default_factory=list)
    recommended_owner: str | None = None
    recommended_next_step: str | None = None
    method: str = "rules_fallback"
