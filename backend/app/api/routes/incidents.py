import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import AuthUser, DbSession, Operator
from app.models import Incident
from app.models.enums import IncidentStatus
from app.schemas.incident import DetectRequest, IncidentRead
from app.services.spike_detection import run_detection

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentRead])
def list_incidents(
    user: AuthUser,
    db: DbSession,
    status_filter: IncidentStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
):
    q = select(Incident).where(Incident.bank_id == user.bank_id)
    q = q.order_by(Incident.priority_score.desc(), Incident.detected_at.desc())
    if status_filter:
        q = q.where(Incident.status == status_filter)
    return db.execute(q.limit(limit)).scalars().all()


@router.post("/detect", response_model=list[IncidentRead])
def detect_spikes(user: Operator, db: DbSession, payload: DetectRequest | None = None):
    """Run spike detection for your bank now (or at a simulated time) and return new incidents."""
    return run_detection(db, user.bank_id, now=payload.now if payload else None)


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(incident_id: uuid.UUID, user: AuthUser, db: DbSession):
    incident = db.get(Incident, incident_id)
    if not incident or incident.bank_id != user.bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    return incident
