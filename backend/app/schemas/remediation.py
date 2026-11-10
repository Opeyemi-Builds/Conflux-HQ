"""Pydantic contracts for the Opeyemi integration slice.

Corrective actions are bank-owned remediation tracking — never money movement.
Investigation runs persist explicitly-requested briefs that separate observed
facts from hypotheses and cite stored evidence IDs.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CorrectiveActionStatus, InvestigationRunStatus


ALLOWED_CORRECTIVE_TRANSITIONS: dict[CorrectiveActionStatus, set[CorrectiveActionStatus]] = {
    CorrectiveActionStatus.PROPOSED: {
        CorrectiveActionStatus.ACCEPTED,
        CorrectiveActionStatus.REJECTED,
    },
    CorrectiveActionStatus.ACCEPTED: {
        CorrectiveActionStatus.IN_PROGRESS,
        CorrectiveActionStatus.REJECTED,
    },
    CorrectiveActionStatus.IN_PROGRESS: {
        CorrectiveActionStatus.MONITORING,
        CorrectiveActionStatus.REJECTED,
    },
    CorrectiveActionStatus.MONITORING: {
        CorrectiveActionStatus.VERIFIED,
        CorrectiveActionStatus.IN_PROGRESS,
        CorrectiveActionStatus.REJECTED,
    },
    CorrectiveActionStatus.VERIFIED: set(),
    CorrectiveActionStatus.REJECTED: set(),
}


class CorrectiveActionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    recommendation: str = Field(min_length=10, max_length=4000)
    owner: str | None = Field(default=None, max_length=128)
    due_date: datetime | None = None
    bank_confirmed_cause: str | None = Field(default=None, max_length=4000)
    change_reference: str | None = Field(default=None, max_length=128)
    validation_plan: str | None = Field(default=None, max_length=4000)


class CorrectiveActionUpdate(BaseModel):
    status: CorrectiveActionStatus | None = None
    owner: str | None = Field(default=None, max_length=128)
    due_date: datetime | None = None
    bank_confirmed_cause: str | None = Field(default=None, max_length=4000)
    change_reference: str | None = Field(default=None, max_length=128)
    validation_plan: str | None = Field(default=None, max_length=4000)
    validation_observation: str | None = Field(default=None, max_length=4000)


class CorrectiveActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bank_id: uuid.UUID
    incident_id: uuid.UUID
    title: str
    recommendation: str
    owner: str | None
    due_date: datetime | None
    status: CorrectiveActionStatus
    bank_confirmed_cause: str | None
    change_reference: str | None
    validation_plan: str | None
    validation_observation: str | None
    created_by: str
    verified_by: str | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InvestigationRunRequest(BaseModel):
    """Explicit operator request. GET/dashboard reads never create runs."""

    incident_id: uuid.UUID


class InvestigationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bank_id: uuid.UUID
    incident_id: uuid.UUID
    status: InvestigationRunStatus
    requested_by: str
    model: str | None
    provider: str | None
    prompt_version: str | None
    evidence_ids: list
    facts: list
    hypotheses: list
    missing_evidence: list
    recommended_checks: list
    recommended_owner: str | None
    confidence: float | None
    error: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class IncidentOverview(BaseModel):
    """Single payload for tomorrow's frontend incident detail view."""

    incident_id: uuid.UUID
    issue_type: str
    status: str
    complaint_count: int
    baseline: float
    growth_rate: float
    priority_score: int
    affected_channels: dict
    likely_cause: str | None
    cause_confidence: float | None
    summary: str | None
    complaints: list[dict]
    social_corroboration: dict
    payment_evidence: dict
    investigation_latest: InvestigationRunRead | None
    corrective_actions: list[CorrectiveActionRead]
    audit_count: int
