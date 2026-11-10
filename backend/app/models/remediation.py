"""Incident remediation: persisted corrective actions and investigation runs."""
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.models.enums import CorrectiveActionStatus, InvestigationRunStatus, enum_type


class CorrectiveAction(Base):
    """A tracked bank-owned remediation step for an incident.

    Status lifecycle: proposed -> accepted -> in_progress -> monitoring -> verified.
    Any non-terminal state may move to rejected. Only ``verified`` closes the loop
    and it requires recorded validation evidence plus an authorised (bank_admin) actor.
    A falling complaint count alone never auto-closes an action.
    """

    __tablename__ = "corrective_actions"
    __table_args__ = (
        Index("ix_corrective_actions_bank_status", "bank_id", "status", "created_at"),
        Index("ix_corrective_actions_incident", "incident_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True, nullable=False)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[CorrectiveActionStatus] = mapped_column(
        enum_type(CorrectiveActionStatus), default=CorrectiveActionStatus.PROPOSED, nullable=False
    )
    bank_confirmed_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    validation_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_observation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    verified_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class InvestigationRun(Base):
    """A persisted, explicitly-requested incident investigation.

    Runs are created only by an explicit operator POST or an enqueued job — never by
    a dashboard GET. The stored result separates observed facts from hypotheses and
    records every stored evidence ID the brief cites, so Andrew's MaaS slice (or the
    deterministic fallback) can be audited without re-running a model.
    """

    __tablename__ = "investigation_runs"
    __table_args__ = (
        Index("ix_investigation_runs_bank_status", "bank_id", "status", "created_at"),
        Index("ix_investigation_runs_incident", "incident_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True, nullable=False)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), index=True, nullable=False)
    status: Mapped[InvestigationRunStatus] = mapped_column(
        enum_type(InvestigationRunStatus), default=InvestigationRunStatus.REQUESTED, nullable=False
    )
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    facts: Mapped[list] = mapped_column(JSON, default=list)
    hypotheses: Mapped[list] = mapped_column(JSON, default=list)
    missing_evidence: Mapped[list] = mapped_column(JSON, default=list)
    recommended_checks: Mapped[list] = mapped_column(JSON, default=list)
    recommended_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
