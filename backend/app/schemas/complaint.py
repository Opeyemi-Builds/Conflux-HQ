import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Channel, IssueType, Sentiment, Severity


class ComplaintCreate(BaseModel):
    channel: Channel
    text: str = Field(min_length=1, max_length=5000)
    occurred_at: datetime | None = None
    customer_ref: str | None = None
    region: str | None = None
    language: str | None = None
    # Optional pre-labels (simulator or tests); the AI classifier normally fills these.
    issue_type: IssueType | None = None


class ComplaintBulkCreate(BaseModel):
    complaints: list[ComplaintCreate] = Field(min_length=1, max_length=5000)


class ComplaintClassification(BaseModel):
    """Written by the AI classifier via PATCH /complaints/{id}/classification."""

    issue_type: IssueType
    severity: Severity | None = None
    sentiment: Sentiment | None = None
    language: str | None = None
    summary: str | None = None
    is_fraud: bool = False
    mentioned_amount: Decimal | None = None
    mentioned_time: str | None = None
    confidence: float = Field(0.0, ge=0, le=1)


class ComplaintRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    channel: Channel
    text: str
    customer_ref: str | None
    region: str | None
    language: str | None
    occurred_at: datetime
    issue_type: IssueType | None
    severity: Severity | None
    sentiment: Sentiment | None
    summary: str | None
    is_fraud: bool
    mentioned_amount: Decimal | None
    mentioned_time: str | None
    classification_confidence: float | None
    transaction_id: str | None
    incident_id: uuid.UUID | None


class BulkResult(BaseModel):
    created: int
