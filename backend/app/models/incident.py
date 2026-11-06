import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.enums import DraftKind, DraftStatus, IncidentStatus, IssueType, enum_type


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True)
    issue_type: Mapped[IssueType] = mapped_column(enum_type(IssueType), index=True)
    status: Mapped[IncidentStatus] = mapped_column(
        enum_type(IncidentStatus), default=IncidentStatus.OPEN, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    complaint_count: Mapped[int] = mapped_column(Integer, default=0)
    baseline: Mapped[float] = mapped_column(Float, default=0.0)
    growth_rate: Mapped[float] = mapped_column(Float, default=0.0)
    priority_score: Mapped[int] = mapped_column(Integer, default=0)
    affected_channels: Mapped[dict] = mapped_column(JSON, default=dict)  # channel -> count

    # Filled by the investigation agent
    likely_cause: Mapped[str | None] = mapped_column(Text)
    cause_confidence: Mapped[float | None] = mapped_column(Float)
    summary: Mapped[str | None] = mapped_column(Text)

    drafts: Mapped[list["Draft"]] = relationship(back_populates="incident", cascade="all, delete-orphan")


class Draft(Base):
    """Agent-proposed actions. Nothing here runs until a human approves it."""

    __tablename__ = "drafts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    kind: Mapped[DraftKind] = mapped_column(enum_type(DraftKind))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[DraftStatus] = mapped_column(enum_type(DraftStatus), default=DraftStatus.PENDING)
    decided_by: Mapped[str | None] = mapped_column(String(64))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    incident: Mapped[Incident] = relationship(back_populates="drafts")
