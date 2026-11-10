"""Machine API keys: bank-scoped credentials for pulling Conflux signal into bank dashboards.

Mirrors the ingestion-connector credential pattern: the raw secret is shown once
at creation, only an HMAC-SHA256 hash is stored, and the public key_prefix is
used for lookup/logging. API keys never carry the Forge GATEWAY_KEY and never
grant bank_admin powers — management stays JWT-only.
"""
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow

API_KEY_PREFIX = "cfx_api_"
ALLOWED_API_SCOPES = {"read", "operate"}


class ApiKey(Base):
    """A bank developer credential. Scopes: read (pull) + optional operate (trigger jobs)."""

    __tablename__ = "api_keys"
    __table_args__ = (
        Index("ix_api_keys_bank_status", "bank_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # HMAC-SHA256, never returned
    scopes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # e.g. ["read"] or ["read", "operate"]
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)  # 'active', 'revoked'
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
