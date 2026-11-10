"""Tenant-bound intake connectors and audit-grade complaint receipts."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class IngestionConnector(Base):
    """Authenticated connector credential bound to a single bank tenant.
    
    Never expose the raw secret or hash to clients. The key_prefix is public/logged,
    while key_hash stores the HMAC-SHA256 representation.
    """

    __tablename__ = "ingestion_connectors"
    __table_args__ = (
        UniqueConstraint("key_prefix", name="uq_ingestion_connector_prefix"),
        Index("ix_ingestion_connectors_bank_status", "bank_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_system: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g., 'zendesk_sim', 'crm_call_center'
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)  # e.g., 'cfx_conn_ab12'
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # HMAC-SHA256
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)  # 'active', 'revoked'
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    receipts: Mapped[list["ComplaintReceipt"]] = relationship("ComplaintReceipt", back_populates="connector")


class ComplaintReceipt(Base):
    """Provenance and deduplication record for an ingested bank ticket."""

    __tablename__ = "complaint_receipts"
    __table_args__ = (
        UniqueConstraint("bank_id", "connector_id", "external_id", name="uq_receipt_bank_connector_external"),
        Index("ix_receipt_bank_payment_ref", "bank_id", "payment_reference"),
        Index("ix_receipt_bank_received", "bank_id", "received_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True, nullable=False)
    connector_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_connectors.id"), index=True, nullable=False)
    complaint_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("complaints.id"), unique=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # HMAC-SHA256 of canonical payload
    payment_reference: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    connector: Mapped[IngestionConnector] = relationship("IngestionConnector", back_populates="receipts")

