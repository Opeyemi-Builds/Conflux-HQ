from typing import Literal
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.ai.agent import investigate_incident
from app.ai.classifier import classify
from app.ai.drafts import create_drafts
from app.ai.eval import evaluate_golden_set
from app.api.deps import AuthUser, DbSession, Operator
from app.db.base import utcnow
from app.models import Draft, Incident
from app.models.enums import DraftKind, DraftStatus, IncidentStatus, JobKind
from app.schemas.ai import (ClassificationResponse, ClassifyRequest, DraftDecision, DraftRead,
                            InvestigationResponse)
from app.services.audit import log_event
from app.services.worker import enqueue_job

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/classify", response_model=ClassificationResponse)
def classify_text(payload: ClassifyRequest, user: Operator, db: DbSession):
    result, source = classify(payload.text, payload.channel)
    data = result.model_dump()
    data["issue_type"] = result.issue_type.value if hasattr(result.issue_type, "value") else result.issue_type
    runtime = getattr(result, "_runtime", {})
    data.update({"source": source, **runtime})
    from app.services.audit import log_event
    log_event(db, bank_id=user.bank_id, actor=str(user.id), action="text_classified", entity_type="ai_classifier",
              entity_id="paste", details={runtime_key: runtime_value for runtime_key, runtime_value in runtime.items()
                                           if runtime_key != "source"})
    db.commit()
    return data


def _incident(db, incident_id: uuid.UUID, bank_id: uuid.UUID) -> Incident:
    incident = db.get(Incident, incident_id)
    if not incident or incident.bank_id != bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    return incident


@router.post("/incidents/{incident_id}/investigate", response_model=InvestigationResponse)
def investigate(incident_id: uuid.UUID, user: Operator, db: DbSession):
    incident = _incident(db, incident_id, user.bank_id)
    incident.status = IncidentStatus.INVESTIGATING
    db.commit()
    incident = investigate_incident(db, user.bank_id, incident, actor=str(user.id))
    drafts = create_drafts(db, user.bank_id, incident, actor=str(user.id))
    return InvestigationResponse(incident_id=incident.id, likely_cause=incident.likely_cause,
                                 cause_confidence=incident.cause_confidence, summary=incident.summary,
                                 draft_count=len(drafts), source=getattr(incident, "_ai_source", "rules"),
                                 model=getattr(incident, "_ai_model", None),
                                 prompt_version=getattr(incident, "_ai_prompt_version", None),
                                 latency_ms=getattr(incident, "_ai_latency_ms", None),
                                 input_tokens=getattr(incident, "_ai_input_tokens", 0),
                                 output_tokens=getattr(incident, "_ai_output_tokens", 0))


@router.get("/incidents/{incident_id}/drafts", response_model=list[DraftRead])
def list_drafts(incident_id: uuid.UUID, user: Operator, db: DbSession):
    _incident(db, incident_id, user.bank_id)
    return db.execute(select(Draft).join(Incident).where(Incident.bank_id == user.bank_id,
                                                         Draft.incident_id == incident_id)).scalars().all()


@router.post("/drafts/{draft_id}/decision", response_model=DraftRead)
def decide_draft(draft_id: uuid.UUID, payload: DraftDecision, user: Operator, db: DbSession):
    if payload.decision not in (DraftStatus.APPROVED, DraftStatus.REJECTED):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Decision must be approved or rejected")
    draft = db.get(Draft, draft_id)
    if not draft:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    incident = db.get(Incident, draft.incident_id)
    if not incident or incident.bank_id != user.bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    if draft.status != DraftStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Draft has already been decided")
    if payload.decision == DraftStatus.APPROVED and draft.kind == DraftKind.REVERSAL_REQUEST:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Reversals cannot be executed by this prototype")

    draft.status = payload.decision
    draft.decided_by = str(user.id)
    draft.decided_at = utcnow()
    all_drafts = db.execute(select(Draft).where(Draft.incident_id == incident.id)).scalars().all()
    if all(d.status == DraftStatus.APPROVED for d in all_drafts):
        incident.status = IncidentStatus.RESOLVED

    log_event(db, bank_id=user.bank_id, actor=str(user.id), action="draft_decided", entity_type="draft",
              entity_id=str(draft.id), details={"decision": payload.decision.value, "kind": draft.kind.value})
    if payload.decision == DraftStatus.APPROVED:
        enqueue_job(
            db,
            bank_id=user.bank_id,
            kind=JobKind.DISPATCH_APPROVAL,
            payload={"draft_id": str(draft.id), "incident_id": str(incident.id), "kind": draft.kind.value},
            idempotency_key=f"outbox:draft:{draft.id}",
        )
    db.commit()
    return draft


@router.get("/audit")
def bank_audit(user: AuthUser, db: DbSession, limit: int = Query(100, ge=1, le=500)):
    from app.models import AuditLog
    rows = db.execute(
        select(AuditLog)
        .where(AuditLog.bank_id == user.bank_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).scalars().all()
    return [
        {
            "id": str(row.id),
            "actor": row.actor,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "details": row.details,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/incidents/{incident_id}/audit")
def incident_audit(incident_id: uuid.UUID, user: Operator, db: DbSession):
    _incident(db, incident_id, user.bank_id)
    from app.models import AuditLog
    rows = db.execute(select(AuditLog).where(AuditLog.bank_id == user.bank_id,
                                            AuditLog.entity_id == str(incident_id))
                      .order_by(AuditLog.created_at)).scalars().all()
    return [{"id": str(row.id), "actor": row.actor, "action": row.action,
             "entity_type": row.entity_type, "entity_id": row.entity_id,
             "details": row.details, "created_at": row.created_at} for row in rows]


@router.get("/evaluate")
def evaluate_classifier(
    user: AuthUser,
    mode: Literal["rules", "auto"] = Query(default="rules", description="Evaluate deterministic fallback rules or active LLM provider against the 100-item golden set."),
):
    return evaluate_golden_set(mode=mode)
