"""Immutable XtraDot sandbox webhook receipts."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, LargeBinary, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class XtradotWebhookReceipt(Base):
    __tablename__ = "xtradot_webhook_receipts"
    __table_args__ = (
        Index(
            "uq_xtradot_webhook_scope_event",
            "provider",
            "environment",
            "event_id",
            unique=True,
        ),
        Index(
            "ix_xtradot_webhook_bank_status_created",
            "bank_id",
            "status",
            "received_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("banks.id"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), default="xtradot", nullable=False)
    environment: Mapped[str] = mapped_column(String(16), default="sandbox", nullable=False)
    event_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    raw_body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    raw_timestamp: Mapped[str | None] = mapped_column(String(160), nullable=True)
    signature_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="received", nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(String(256), nullable=True)
