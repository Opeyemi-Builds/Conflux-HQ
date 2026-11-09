import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class ComplaintCluster(Base):
    __tablename__ = "complaint_clusters"
    __table_args__ = (
        UniqueConstraint("bank_id", "cluster_key", name="uq_complaint_cluster_bank_key"),
        Index("ix_complaint_clusters_last_seen", "last_seen"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True)
    cluster_key: Mapped[str] = mapped_column(String(128))
    label: Mapped[str] = mapped_column(String(300))
    label_method: Mapped[str] = mapped_column(String(16), default="rules")
    issue_type: Mapped[str] = mapped_column(String(32))
    payment_category: Mapped[str | None] = mapped_column(String(32), index=True)
    complaint_count: Mapped[int] = mapped_column(Integer, default=0)
    fraud_count: Mapped[int] = mapped_column(Integer, default=0)
    growth_rate: Mapped[float] = mapped_column(Float, default=0.0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    channels: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    regions: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    related_incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("incidents.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
