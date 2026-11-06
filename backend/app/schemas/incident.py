import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import IncidentStatus, IssueType


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_type: IssueType
    status: IncidentStatus
    started_at: datetime
    detected_at: datetime
    complaint_count: int
    baseline: float
    growth_rate: float
    priority_score: int
    affected_channels: dict
    likely_cause: str | None
    cause_confidence: float | None
    summary: str | None


class DetectRequest(BaseModel):
    """`now` lets the demo replay a simulated timeline. Omit it for live detection."""

    now: datetime | None = None
