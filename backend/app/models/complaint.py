import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.models.enums import Channel, IssueType, Sentiment, Severity, enum_type


class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (Index("ix_complaints_bank_issue_time", "bank_id", "issue_type", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True)
    channel: Mapped[Channel] = mapped_column(enum_type(Channel), index=True)
    text: Mapped[str] = mapped_column(Text)  # PII-masked before storage
    customer_ref: Mapped[str | None] = mapped_column(String(64))  # pseudonymised
    region: Mapped[str | None] = mapped_column(String(64), index=True)
    language: Mapped[str | None] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Filled by the AI classifier (or by the simulator for pre-labelled data)
    issue_type: Mapped[IssueType | None] = mapped_column(enum_type(IssueType), index=True)
    severity: Mapped[Severity | None] = mapped_column(enum_type(Severity))
    sentiment: Mapped[Sentiment | None] = mapped_column(enum_type(Sentiment))
    summary: Mapped[str | None] = mapped_column(Text)
    is_fraud: Mapped[bool] = mapped_column(Boolean, default=False)
    mentioned_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    mentioned_time: Mapped[str | None] = mapped_column(String(64))
    classification_confidence: Mapped[float | None] = mapped_column(Float)
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id"), index=True)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("incidents.id"), index=True)
