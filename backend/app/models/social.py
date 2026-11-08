"""Monitored identities and tenant-owned social intake receipts."""
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class BankAlias(Base):
    __tablename__ = "bank_aliases"
    __table_args__ = (UniqueConstraint("bank_id", "value", name="uq_bank_alias"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True)
    value: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(16))  # name, handle, hashtag, contextual
    platform: Mapped[str | None] = mapped_column(String(16))


class SocialReceipt(Base):
    __tablename__ = "social_receipts"
    __table_args__ = (UniqueConstraint("bank_id", "platform", "post_id", name="uq_social_receipt"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True)
    platform: Mapped[str] = mapped_column(String(16))
    post_id: Mapped[str] = mapped_column(String(160))
    complaint_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("complaints.id"))
    source_url: Mapped[str | None] = mapped_column(String(500))
    matched_aliases: Mapped[list] = mapped_column(JSON)
    author_ref_hash: Mapped[str | None] = mapped_column(String(128))
    public_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    reputation_flags: Mapped[list] = mapped_column(JSON, default=list)
    reputation_score: Mapped[float] = mapped_column(Float, default=0.0)
    analysis_method: Mapped[str] = mapped_column(String(32), default="demo_rules_v1")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
