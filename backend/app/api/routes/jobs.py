"""API endpoints for inspecting and draining the transactional SQL job queue."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import AuthUser, DbSession, Operator
from app.models import Job
from app.models.enums import JobKind, JobStatus
from app.services.worker import drain_jobs

router = APIRouter(prefix="/jobs", tags=["jobs & workers"])


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: JobKind
    status: JobStatus
    idempotency_key: str
    payload: dict
    result: dict | None
    last_error: str | None
    attempts: int
    max_attempts: int
    lease_until: datetime | None
    created_at: datetime
    updated_at: datetime


class DrainRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)


class DrainResponse(BaseModel):
    processed: int
    completed: int
    retried: int
    dead_lettered: int


@router.get("", response_model=list[JobRead])
def list_jobs(
    user: AuthUser,
    db: DbSession,
    status: JobStatus | None = None,
    kind: JobKind | None = None,
    limit: int = Query(50, ge=1, le=200),
):
    q = select(Job).where(Job.bank_id == user.bank_id).order_by(Job.created_at.desc(), Job.id.desc())
    if status is not None:
        q = q.where(Job.status == status)
    if kind is not None:
        q = q.where(Job.kind == kind)
    return db.scalars(q.limit(limit)).all()


@router.post("/drain", response_model=DrainResponse)
def drain_bank_jobs(user: Operator, db: DbSession, payload: DrainRequest | None = None):
    """Run queued classification, detection, investigation, and outbox jobs for this bank."""
    limit = payload.limit if payload else 100
    return drain_jobs(db, bank_id=user.bank_id, limit=limit)

