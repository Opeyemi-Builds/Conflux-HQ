"""Opeyemi-owned integration service: incident overview, corrective actions, investigations, health."""
import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import (
    AuditLog,
    Complaint,
    CorrectiveAction,
    Incident,
    InvestigationRun,
    PaymentException,
    SocialReceipt,
)
from app.models.enums import (
    CorrectiveActionStatus,
    InvestigationRunStatus,
    JobKind,
    JobStatus,
    UserRole,
)
from app.models.ingestion import IngestionConnector
from app.models.job import Job
from app.schemas.remediation import (
    ALLOWED_CORRECTIVE_TRANSITIONS,
    CorrectiveActionCreate,
    CorrectiveActionUpdate,
)
from app.services.audit import log_event
from app.services.reconciliation_reporting import summary as reconciliation_summary
from app.services.reconciliation_reporting import timeline as reconciliation_timeline
from app.services.worker import enqueue_job


def _own_incident(db: Session, bank_id: uuid.UUID, incident_id: uuid.UUID) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None or incident.bank_id != bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    return incident


def incident_overview(db: Session, bank_id: uuid.UUID, incident_id: uuid.UUID) -> dict:
    """Assemble one bank-scoped payload for the incident detail view.

    Read-only: never enqueues jobs, never calls a model, never mutates money.
    Social volume is reported as corroboration counts only — not proof of cause.
    """
    incident = _own_incident(db, bank_id, incident_id)

    complaints = db.scalars(
        select(Complaint)
        .where(Complaint.bank_id == bank_id, Complaint.incident_id == incident.id)
        .order_by(Complaint.occurred_at.desc())
        .limit(200)
    ).all()

    complaint_ids = [c.id for c in complaints]
    receipts = (
        db.scalars(
            select(SocialReceipt).where(
                SocialReceipt.bank_id == bank_id,
                SocialReceipt.complaint_id.in_(complaint_ids),
            )
        ).all()
        if complaint_ids
        else []
    )
    social_corroboration = {
        "linked_complaints": len({r.complaint_id for r in receipts}),
        "post_count": len(receipts),
        "platforms": sorted({r.platform for r in receipts}),
        "note": "Social volume increases triage priority only; it does not prove cause or affected-customer count.",
    }

    payment_evidence = {
        **reconciliation_summary(db, bank_id, incident.id),
        "timeline": reconciliation_timeline(db, bank_id, incident),
    }

    latest_run = db.scalar(
        select(InvestigationRun)
        .where(InvestigationRun.bank_id == bank_id, InvestigationRun.incident_id == incident.id)
        .order_by(InvestigationRun.created_at.desc())
    )

    actions = db.scalars(
        select(CorrectiveAction)
        .where(CorrectiveAction.bank_id == bank_id, CorrectiveAction.incident_id == incident.id)
        .order_by(CorrectiveAction.created_at.asc())
    ).all()

    audit_count = db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.bank_id == bank_id, AuditLog.entity_id == str(incident.id))
    ) or 0

    return {
        "incident_id": incident.id,
        "issue_type": incident.issue_type.value,
        "status": incident.status.value,
        "complaint_count": incident.complaint_count,
        "baseline": incident.baseline,
        "growth_rate": incident.growth_rate,
        "priority_score": incident.priority_score,
        "affected_channels": dict(incident.affected_channels or {}),
        "likely_cause": incident.likely_cause,
        "cause_confidence": incident.cause_confidence,
        "summary": incident.summary,
        "complaints": [
            {
                "id": str(c.id),
                "channel": c.channel.value,
                "issue_type": c.issue_type.value if c.issue_type else None,
                "severity": c.severity.value if c.severity else None,
                "occurred_at": c.occurred_at.isoformat() if c.occurred_at else None,
                "payment_reference": c.payment_reference,
                "transaction_id": str(c.transaction_id) if c.transaction_id else None,
                "region": c.region,
                "language": c.language,
            }
            for c in complaints
        ],
        "social_corroboration": social_corroboration,
        "payment_evidence": payment_evidence,
        "investigation_latest": latest_run,
        "corrective_actions": actions,
        "audit_count": audit_count,
    }


def create_corrective_action(
    db: Session,
    *,
    bank_id: uuid.UUID,
    incident_id: uuid.UUID,
    payload: CorrectiveActionCreate,
    actor: str,
) -> CorrectiveAction:
    _own_incident(db, bank_id, incident_id)
    action = CorrectiveAction(
        bank_id=bank_id,
        incident_id=incident_id,
        title=payload.title.strip(),
        recommendation=payload.recommendation.strip(),
        owner=payload.owner,
        due_date=payload.due_date,
        status=CorrectiveActionStatus.PROPOSED,
        bank_confirmed_cause=payload.bank_confirmed_cause,
        change_reference=payload.change_reference,
        validation_plan=payload.validation_plan,
        created_by=actor,
    )
    db.add(action)
    db.flush()
    log_event(
        db,
        bank_id=bank_id,
        actor=actor,
        action="corrective_action_created",
        entity_type="corrective_action",
        entity_id=str(action.id),
        details={"incident_id": str(incident_id), "title": action.title},
    )
    db.commit()
    db.refresh(action)
    return action


def update_corrective_action(
    db: Session,
    *,
    bank_id: uuid.UUID,
    action_id: uuid.UUID,
    payload: CorrectiveActionUpdate,
    actor: str,
    actor_role: UserRole,
) -> CorrectiveAction:
    action = db.get(CorrectiveAction, action_id)
    if action is None or action.bank_id != bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Corrective action not found")

    if payload.owner is not None:
        action.owner = payload.owner
    if payload.due_date is not None:
        action.due_date = payload.due_date
    if payload.bank_confirmed_cause is not None:
        action.bank_confirmed_cause = payload.bank_confirmed_cause
    if payload.change_reference is not None:
        action.change_reference = payload.change_reference
    if payload.validation_plan is not None:
        action.validation_plan = payload.validation_plan
    if payload.validation_observation is not None:
        action.validation_observation = payload.validation_observation

    if payload.status is not None and payload.status != action.status:
        allowed = ALLOWED_CORRECTIVE_TRANSITIONS.get(action.status, set())
        if payload.status not in allowed:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Cannot move corrective action from {action.status.value} to {payload.status.value}",
            )
        if payload.status == CorrectiveActionStatus.VERIFIED:
            if actor_role != UserRole.BANK_ADMIN:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "Only a bank administrator can verify a corrective action",
                )
            if not (action.validation_observation or "").strip():
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "Verification requires a recorded validation observation",
                )
            if not ((action.bank_confirmed_cause or "").strip() or (action.change_reference or "").strip()):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "Verification requires a bank-confirmed cause or a change reference",
                )
            action.verified_by = actor
            action.verified_at = utcnow()
        action.status = payload.status

    log_event(
        db,
        bank_id=bank_id,
        actor=actor,
        action="corrective_action_updated",
        entity_type="corrective_action",
        entity_id=str(action.id),
        details={"status": action.status.value},
    )
    db.commit()
    db.refresh(action)
    return action


def request_investigation(
    db: Session,
    *,
    bank_id: uuid.UUID,
    incident_id: uuid.UUID,
    actor: str,
) -> InvestigationRun:
    """Persist an explicit investigation request and queue exactly one job for it.

    Called only from POST / explicit operator action — never from a GET.
    """
    incident = _own_incident(db, bank_id, incident_id)
    run = InvestigationRun(
        bank_id=bank_id,
        incident_id=incident.id,
        status=InvestigationRunStatus.REQUESTED,
        requested_by=actor,
    )
    db.add(run)
    db.flush()
    enqueue_job(
        db,
        bank_id=bank_id,
        kind=JobKind.INVESTIGATE_INCIDENT,
        payload={
            "incident_id": str(incident.id),
            "complaint_count": incident.complaint_count,
            "run_id": str(run.id),
        },
        idempotency_key=f"investigate:{incident.id}:{incident.complaint_count}:run:{run.id}",
    )
    log_event(
        db,
        bank_id=bank_id,
        actor=actor,
        action="investigation_requested",
        entity_type="investigation_run",
        entity_id=str(run.id),
        details={"incident_id": str(incident.id)},
    )
    db.commit()
    db.refresh(run)
    return run


def complete_investigation_run(
    db: Session,
    *,
    run_id: uuid.UUID,
    model: str | None,
    provider: str | None,
    prompt_version: str | None,
    confidence: float | None,
    facts: list,
    hypotheses: list,
    evidence_ids: list,
    missing_evidence: list,
    recommended_checks: list,
    recommended_owner: str | None,
    error: str | None = None,
) -> InvestigationRun:
    run = db.get(InvestigationRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigation run not found")
    run.status = InvestigationRunStatus.FAILED if error else InvestigationRunStatus.COMPLETED
    run.model = model
    run.provider = provider
    run.prompt_version = prompt_version
    run.confidence = confidence
    run.facts = facts
    run.hypotheses = hypotheses
    run.evidence_ids = evidence_ids
    run.missing_evidence = missing_evidence
    run.recommended_checks = recommended_checks
    run.recommended_owner = recommended_owner
    run.error = error
    run.completed_at = utcnow()
    db.commit()
    db.refresh(run)
    return run


def connector_health(db: Session, bank_id: uuid.UUID) -> dict:
    """Summarise bank connector posture without leaking secrets or hashes."""
    connectors = db.scalars(
        select(IngestionConnector)
        .where(IngestionConnector.bank_id == bank_id)
        .order_by(IngestionConnector.created_at.desc())
    ).all()
    active = [c for c in connectors if c.status == "active"]
    stale: list[dict] = []
    for connector in connectors:
        stale.append(
            {
                "id": str(connector.id),
                "name": connector.name,
                "source_system": connector.source_system,
                "key_prefix": connector.key_prefix,
                "status": connector.status,
                "synthetic": connector.synthetic,
                "last_used_at": connector.last_used_at.isoformat() if connector.last_used_at else None,
            }
        )
    pending_jobs = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.bank_id == bank_id, Job.status == JobStatus.PENDING)
    ) or 0
    dead_lettered = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.bank_id == bank_id, Job.status == JobStatus.DEAD_LETTER)
    ) or 0
    open_exceptions = db.scalar(
        select(func.count())
        .select_from(PaymentException)
        .where(
            PaymentException.bank_id == bank_id,
            PaymentException.status.not_in(["resolved", "rejected"]),
        )
    ) or 0
    return {
        "connectors": stale,
        "active_connectors": len(active),
        "queue": {"pending": pending_jobs, "dead_lettered": dead_lettered},
        "open_exceptions": open_exceptions,
    }
