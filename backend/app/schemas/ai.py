import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DraftKind, DraftStatus


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
    source: str = "rules"
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
