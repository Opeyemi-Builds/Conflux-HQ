"""Bank-scoped machine API keys: JWT-admin management + machine pull/operate surface.

Management (`/api-keys`, bank_admin JWT only): provision (raw token shown once),
list (never exposes hashes or tokens), revoke (immediate, idempotent).

Machine surface (`/machine`, `cfx_api_` bearer): read scope pulls the same
bank-scoped signal the dashboard reads — analytics summary, incident list and
overview, complaints feed, investigation runs, corrective actions, connector
posture, audit trail, plus the versioned `GET /machine/updates` handoff feed
banks poll to mirror Conflux signal into their own dashboards. operate scope
additionally drains the worker queue and requests investigations; all POSTs
are explicit and audited. No Forge GATEWAY_KEY is ever involved, and machine
keys never grant bank_admin powers.
"""
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import AwareDatetime
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession, MachineOperator, MachineReader
from app.models import AuditLog, Complaint, CorrectiveAction, Incident, InvestigationRun
from app.models.enums import Channel, IncidentStatus, IssueType
from app.schemas.api_key import ApiKeyCreateIn, ApiKeyCreateResponse, ApiKeyRead
from app.schemas.complaint import ComplaintRead
from app.schemas.incident import IncidentRead
from app.schemas.remediation import CorrectiveActionRead, InvestigationRunRead, InvestigationRunRequest
from app.services import api_key_service, remediation
from app.services.audit import log_event
from app.services.worker import drain_jobs
from app.api.routes.jobs import DrainRequest

management = APIRouter(prefix="/api-keys", tags=["machine api keys"])


@management.post(
    "",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a machine API key for dashboard integrations (Admin only; token shown once)",
)
def create_key(payload: ApiKeyCreateIn, admin: AdminUser, db: DbSession):
    key, token = api_key_service.create_api_key(
        db,
        bank_id=admin.bank_id,
        name=payload.name.strip(),
        scopes=payload.scopes,
        expires_at=payload.expires_at,
        demo=payload.demo,
        created_by=str(admin.id),
    )
    return {
        "id": key.id,
        "name": key.name,
        "key_prefix": key.key_prefix,
        "scopes": key.scopes,
        "token": token,
        "expires_at": key.expires_at,
        "created_at": key.created_at,
    }


@management.get("", response_model=list[ApiKeyRead], summary="List API keys for the current bank")
def list_keys(admin: AdminUser, db: DbSession):
    return api_key_service.list_api_keys(db, admin.bank_id)


@management.post(
    "/{key_id}/revoke",
    response_model=ApiKeyRead,
    summary="Revoke an API key immediately (idempotent)",
)
def revoke_key(key_id: uuid.UUID, admin: AdminUser, db: DbSession):
    return api_key_service.revoke_api_key(db, bank_id=admin.bank_id, key_id=key_id, actor=str(admin.id))


machine = APIRouter(prefix="/machine", tags=["machine pull"])


@machine.get("/summary", summary="Analytics summary for the key's bank (read scope)")
def machine_summary(key: MachineReader, db: DbSession):
    from app.api.routes.analytics import summary as _summary

    return _summary(key, db)  # only bank_id is read; MachinePrincipal carries it


@machine.get(
    "/incidents", response_model=list[IncidentRead], summary="Incident list for the key's bank (read scope)"
)
def machine_incidents(
    key: MachineReader,
    db: DbSession,
    status_filter: IncidentStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
):
    q = select(Incident).where(Incident.bank_id == key.bank_id)
    q = q.order_by(Incident.priority_score.desc(), Incident.detected_at.desc())
    if status_filter:
        q = q.where(Incident.status == status_filter)
    return db.execute(q.limit(limit)).scalars().all()


@machine.get("/incidents/{incident_id}", summary="Incident detail via overview bundle (read scope)")
def machine_incident(incident_id: uuid.UUID, key: MachineReader, db: DbSession):
    return remediation.incident_overview(db, key.bank_id, incident_id)


@machine.get(
    "/complaints", response_model=list[ComplaintRead], summary="Complaint feed for the key's bank (read scope)"
)
def machine_complaints(
    key: MachineReader,
    db: DbSession,
    channel: Channel | None = None,
    issue_type: IssueType | None = None,
    since: AwareDatetime | None = None,
    until: AwareDatetime | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    if since and until and since >= until:
        raise HTTPException(422, "since must be earlier than until")
    q = select(Complaint).where(Complaint.bank_id == key.bank_id).order_by(
        Complaint.occurred_at.desc(), Complaint.id
    )
    if channel:
        q = q.where(Complaint.channel == channel)
    if issue_type:
        q = q.where(Complaint.issue_type == issue_type)
    if since:
        q = q.where(Complaint.occurred_at >= since)
    if until:
        q = q.where(Complaint.occurred_at < until)
    return db.execute(q.limit(limit).offset(offset)).scalars().all()


@machine.get(
    "/investigations/{run_id}",
    response_model=InvestigationRunRead,
    summary="Investigation run for the key's bank (read scope)",
)
def machine_investigation(run_id: uuid.UUID, key: MachineReader, db: DbSession):
    run = db.get(InvestigationRun, run_id)
    if run is None or run.bank_id != key.bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigation run not found")
    return run


@machine.get(
    "/incidents/{incident_id}/actions",
    response_model=list[CorrectiveActionRead],
    summary="Corrective actions (read scope)",
)
def machine_actions(incident_id: uuid.UUID, key: MachineReader, db: DbSession):
    remediation._own_incident(db, key.bank_id, incident_id)
    return db.scalars(
        select(CorrectiveAction)
        .where(CorrectiveAction.bank_id == key.bank_id, CorrectiveAction.incident_id == incident_id)
        .order_by(CorrectiveAction.created_at.asc())
    ).all()


@machine.get("/health/connectors", summary="Connector posture and queue health (read scope)")
def machine_connector_health(key: MachineReader, db: DbSession):
    return remediation.connector_health(db, key.bank_id)


@machine.get(
    "/updates",
    summary="Versioned handoff feed: changed items since a cursor (read scope)",
)
def machine_updates(
    key: MachineReader,
    db: DbSession,
    since: str | None = Query(
        default=None,
        description="Opaque cursor from the previous poll (ISO-8601 UTC). Omit for the first pull.",
    ),
    limit: int = Query(100, ge=1, le=500),
    collections: str | None = Query(
        default=None,
        description="Comma-separated subset of complaints,incidents,drafts,actions,investigations,audit.",
    ),
):
    """Poll endpoint banks integrate into their own dashboards.

    Recommended cadence is every 5s: the response includes the next cursor,
    and an empty `items` list means "nothing changed". For a live ticker
    prefer `?collections=complaints,incidents&limit=20`; the remaining
    collections (drafts, actions, investigations, audit) change slowly and do
    not need 5s polling. All rows are bank-scoped to the presenting key;
    results are ordered by (updated_at, id) and capped at `limit` with
    `truncated: true` when more remain under the same cursor.
    """
    from app.services import handoff_feed as _feed

    try:
        cursor = _feed.parse_cursor(since)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    wanted: tuple[str, ...] = _feed.COLLECTIONS
    if collections:
        picked = tuple(c.strip().lower() for c in collections.split(",") if c.strip())
        unknown = [c for c in picked if c not in _feed.COLLECTIONS]
        if unknown:
            raise HTTPException(422, f"Unknown collections: {', '.join(unknown)}")
        wanted = picked or _feed.COLLECTIONS
    result = _feed.handoff_updates(db, bank_id=key.bank_id, since=cursor, limit=limit, collections=wanted)
    result["poll_interval_seconds"] = 5
    # At a 5s cadence most polls are empty; only audit polls that carry
    # signal so the audit trail (which the feed itself excludes) stays lean.
    if result["count"] or result["truncated"]:
        log_event(
            db,
            bank_id=key.bank_id,
            actor=f"api_key:{key.key_prefix}",
            action="machine_updates_polled",
            entity_type="handoff_feed",
            entity_id=str(key.bank_id),
            details={"since": result["since"], "count": result["count"], "truncated": result["truncated"]},
        )
        db.commit()
    return result


@machine.get("/audit", summary="Audit trail for the key's bank (read scope)")
def machine_audit(key: MachineReader, db: DbSession, limit: int = Query(100, ge=1, le=500)):
    rows = db.execute(
        select(AuditLog)
        .where(AuditLog.bank_id == key.bank_id)
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


@machine.post(
    "/jobs/drain",
    summary="Drain the bank worker queue via machine credential (operate scope)",
)
def machine_drain(key: MachineOperator, db: DbSession, payload: DrainRequest | None = None):
    limit = payload.limit if payload else 100
    result = drain_jobs(db, bank_id=key.bank_id, limit=limit)
    log_event(
        db,
        bank_id=key.bank_id,
        actor=f"api_key:{key.key_prefix}",
        action="machine_jobs_drained",
        entity_type="job_queue",
        entity_id=str(key.bank_id),
        details={"limit": limit, **result},
    )
    db.commit()
    return result


@machine.post(
    "/investigations",
    response_model=InvestigationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request an incident investigation via machine credential (operate scope)",
)
def machine_investigate(payload: InvestigationRunRequest, key: MachineOperator, db: DbSession):
    return remediation.request_investigation(
        db, bank_id=key.bank_id, incident_id=payload.incident_id, actor=f"api_key:{key.key_prefix}"
    )
