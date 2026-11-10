"""Opeyemi-owned integration routes: incident overview, investigations, corrective actions."""
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import AdminUser, AuthUser, DbSession, Operator
from app.models import CorrectiveAction, InvestigationRun
from app.schemas.remediation import (
    CorrectiveActionCreate,
    CorrectiveActionRead,
    CorrectiveActionUpdate,
    IncidentOverview,
    InvestigationRunRead,
    InvestigationRunRequest,
)
from app.services import remediation as remediation_service

router = APIRouter(tags=["incident remediation"])


def _own_action(db: DbSession, bank_id: uuid.UUID, action_id: uuid.UUID) -> CorrectiveAction:
    action = db.get(CorrectiveAction, action_id)
    if action is None or action.bank_id != bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Corrective action not found")
    return action


@router.get(
    "/incidents/{incident_id}/overview",
    response_model=IncidentOverview,
    summary="Single incident overview: complaints, evidence, investigation, actions",
)
def get_incident_overview(incident_id: uuid.UUID, user: AuthUser, db: DbSession):
    """Read-only. Never enqueues jobs or calls a model."""
    return remediation_service.incident_overview(db, user.bank_id, incident_id)


@router.post(
    "/incidents/{incident_id}/actions",
    response_model=CorrectiveActionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a corrective action to an incident",
)
def create_action(
    incident_id: uuid.UUID, payload: CorrectiveActionCreate, user: Operator, db: DbSession
):
    return remediation_service.create_corrective_action(
        db, bank_id=user.bank_id, incident_id=incident_id, payload=payload, actor=str(user.id)
    )


@router.get(
    "/incidents/{incident_id}/actions",
    response_model=list[CorrectiveActionRead],
    summary="List corrective actions for an incident",
)
def list_actions(incident_id: uuid.UUID, user: AuthUser, db: DbSession):
    remediation_service._own_incident(db, user.bank_id, incident_id)
    return db.scalars(
        select(CorrectiveAction)
        .where(
            CorrectiveAction.bank_id == user.bank_id,
            CorrectiveAction.incident_id == incident_id,
        )
        .order_by(CorrectiveAction.created_at.asc())
    ).all()


@router.patch(
    "/actions/{action_id}",
    response_model=CorrectiveActionRead,
    summary="Advance or reject a corrective action through its lifecycle",
)
def update_action(
    action_id: uuid.UUID, payload: CorrectiveActionUpdate, user: Operator, db: DbSession
):
    action = _own_action(db, user.bank_id, action_id)
    _ = action  # ownership checked; transition logic lives in the service
    return remediation_service.update_corrective_action(
        db,
        bank_id=user.bank_id,
        action_id=action_id,
        payload=payload,
        actor=str(user.id),
        actor_role=user.role,
    )


@router.post(
    "/investigations",
    response_model=InvestigationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Explicitly request an incident investigation (queues one job)",
)
def request_investigation(payload: InvestigationRunRequest, user: Operator, db: DbSession):
    return remediation_service.request_investigation(
        db, bank_id=user.bank_id, incident_id=payload.incident_id, actor=str(user.id)
    )


@router.get(
    "/incidents/{incident_id}/investigations",
    response_model=list[InvestigationRunRead],
    summary="List persisted investigation runs for an incident",
)
def list_investigations(
    incident_id: uuid.UUID,
    user: AuthUser,
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
):
    remediation_service._own_incident(db, user.bank_id, incident_id)
    return db.scalars(
        select(InvestigationRun)
        .where(
            InvestigationRun.bank_id == user.bank_id,
            InvestigationRun.incident_id == incident_id,
        )
        .order_by(InvestigationRun.created_at.desc())
        .limit(limit)
    ).all()


@router.get(
    "/investigations/{run_id}",
    response_model=InvestigationRunRead,
    summary="Retrieve a persisted investigation run",
)
def get_investigation(run_id: uuid.UUID, user: AuthUser, db: DbSession):
    run = db.get(InvestigationRun, run_id)
    if run is None or run.bank_id != user.bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigation run not found")
    return run


@router.get(
    "/connectors/health",
    summary="Connector posture and queue health (no secrets)",
)
def get_connector_health(user: AuthUser, db: DbSession):
    return remediation_service.connector_health(db, user.bank_id)
