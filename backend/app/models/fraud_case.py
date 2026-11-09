import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class FraudCase(Base):
    __tablename__ = "fraud_cases"
    __table_args__ = (
        UniqueConstraint("bank_id", "complaint_id", name="uq_fraud_case_bank_complaint"),
        Index("ix_fraud_cases_bank_status", "bank_id", "status"),
        Index("ix_fraud_cases_bank_priority", "bank_id", "priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True)
    complaint_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("complaints.id"), index=True)
    fraud_type: Mapped[str] = mapped_column(String(32))
    priority: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    indicators: Mapped[list[str]] = mapped_column(JSON, default=list)
    repeat_count: Mapped[int] = mapped_column(Integer, default=1)
    assigned_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
