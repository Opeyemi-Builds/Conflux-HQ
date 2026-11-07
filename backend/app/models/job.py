"""Transactional SQL job queue (replaces external Redis/Kafka dependency)."""
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.models.enums import JobKind, JobStatus, enum_type


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("bank_id", "idempotency_key", name="uq_job_bank_idempotency"),
        Index("ix_jobs_bank_status_lease", "bank_id", "status", "lease_until"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True)
    kind: Mapped[JobKind] = mapped_column(enum_type(JobKind), index=True)
    status: Mapped[JobStatus] = mapped_column(enum_type(JobStatus), default=JobStatus.PENDING, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

