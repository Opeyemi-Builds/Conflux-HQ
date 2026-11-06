import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class AuditLog(Base):
    """Every agent step and human decision. Append-only."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("banks.id"), index=True)
    actor: Mapped[str] = mapped_column(String(64))  # "system", "agent", or a user id
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
