"""Grounded, non-executing draft templates for incident communication."""
from sqlalchemy.orm import Session

from app.models import Draft, Incident
from app.models.enums import DraftKind, DraftStatus
from app.services.audit import log_event


def create_drafts(db: Session, bank_id, incident: Incident, actor: str = "agent") -> list[Draft]:
    cause = incident.likely_cause or "An investigation is still in progress"
    count = incident.complaint_count
    customer = (
        f"We are aware of reports from customers affecting {incident.issue_type.value.replace('_', ' ')}. "
        "Our teams are investigating and will share confirmed resolution updates. "
        "No amount or resolution status has been confirmed unless a team member follows up with you directly."
    )
    ticket = (
        f"Incident: {incident.issue_type.value}\n"
        f"Complaint count: {count}\n"
        f"Started: {incident.started_at.isoformat()}\n"
        f"Likely cause: {cause}\n"
        f"Confidence: {incident.cause_confidence or 0:.2f}\n"
        "Evidence: complaint trend and correlated transaction/system records stored in Conflux HQ.\n"
        "Action: verify the affected payment path, review correlated logs, and assign an owner."
    )

    existing = db.query(Draft).filter(Draft.incident_id == incident.id).all()
    if existing:
        return existing

    drafts = [
        Draft(incident_id=incident.id, kind=DraftKind.CUSTOMER_MESSAGE, content=customer,
              status=DraftStatus.PENDING),
        Draft(incident_id=incident.id, kind=DraftKind.IT_TICKET, content=ticket,
              status=DraftStatus.PENDING),
    ]
    db.add_all(drafts)
    db.flush()
    for draft in drafts:
        log_event(db, bank_id=bank_id, actor=actor, action="draft_created", entity_type="draft",
                  entity_id=str(draft.id), details={"kind": draft.kind.value})
    db.commit()
    return drafts
