"""Bank-scoped payment exceptions awaiting reconciliation or human review."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.models.enums import ExceptionType, ReconciliationStatus, SettlementStatus, enum_type


class PaymentException(Base):
    __tablename__ = "payment_exceptions"
    __table_args__ = (
        Index("ix_payment_exceptions_bank_status", "bank_id", "status", "created_at"),
        Index("ix_payment_exceptions_bank_type", "bank_id", "exception_type", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True)
    complaint_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("complaints.id"), index=True)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id"), index=True)
    exception_type: Mapped[ExceptionType] = mapped_column(enum_type(ExceptionType), index=True)
    status: Mapped[ReconciliationStatus] = mapped_column(
        enum_type(ReconciliationStatus), default=ReconciliationStatus.REPORTED, index=True
    )
    settlement_status: Mapped[SettlementStatus] = mapped_column(
        enum_type(SettlementStatus), default=SettlementStatus.UNKNOWN, index=True
    )
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    transaction_reference: Mapped[str | None] = mapped_column(String(64))
    processor: Mapped[str | None] = mapped_column(String(64))
    payment_channel: Mapped[str | None] = mapped_column(String(32))
    customer_ref_hash: Mapped[str | None] = mapped_column(String(128))
    match_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    evidence_summary: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String(128))
    priority: Mapped[int] = mapped_column(default=0)
    approval_required: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
