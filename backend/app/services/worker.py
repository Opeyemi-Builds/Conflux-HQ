"""Transactional SQL job queue and bounded worker engine (Concept #3 & #4)."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai.agent import investigate_incident
from app.ai.classifier import classify as ai_classify_text
from app.ai.drafts import create_drafts
from app.core.config import get_settings
from app.db.base import utcnow
from app.models import Complaint, Draft, Incident, Job
from app.models.enums import DraftStatus, IncidentStatus, JobKind, JobStatus
from app.schemas.complaint import ComplaintClassification
from app.services.audit import log_event
from app.services.spike_detection import OPEN_STATUSES, bucket_start, run_detection

LEASE_SECONDS = 60


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def enqueue_job(
    db: Session,
    *,
    bank_id: uuid.UUID,
    kind: JobKind,
    payload: dict,
    idempotency_key: str,
    max_attempts: int = 3,
    reopen_completed: bool = False,
) -> Job:
    """Enqueue a job transactionally in the caller's session without duplicate rows."""
    key = idempotency_key[:160]
    for obj in db.new:
        if isinstance(obj, Job) and obj.bank_id == bank_id and obj.idempotency_key == key:
            return obj

    existing = db.scalar(
        select(Job).where(Job.bank_id == bank_id, Job.idempotency_key == key)
    )
    if existing is not None:
        if reopen_completed and existing.status == JobStatus.COMPLETED:
            existing.status = JobStatus.PENDING
            existing.attempts = 0
            existing.last_error = None
            existing.lease_until = None
            existing.payload = payload
            existing.updated_at = utcnow()
        return existing

    job = Job(
        bank_id=bank_id,
        kind=kind,
        status=JobStatus.PENDING,
        idempotency_key=key,
        payload=payload,
        max_attempts=max_attempts,
    )
    db.add(job)
    return job


def claim_next_job(
    db: Session, bank_id: uuid.UUID | None = None, now: datetime | None = None
) -> Job | None:
    """Claim the oldest pending job or a running job whose lease has expired."""
    current = _aware(now) if now else utcnow()
    q = select(Job).where(
        or_(
            Job.status == JobStatus.PENDING,
            (Job.status == JobStatus.RUNNING) & (Job.lease_until.is_not(None)) & (Job.lease_until < current),
        )
    )
    if bank_id is not None:
        q = q.where(Job.bank_id == bank_id)
    job = db.scalars(q.order_by(Job.created_at.asc(), Job.id.asc()).limit(1)).first()
    if job is None:
        return None

    job.status = JobStatus.RUNNING
    job.attempts += 1
    job.lease_until = current + timedelta(seconds=LEASE_SECONDS)
    job.updated_at = current
    db.commit()
    return job


def _handle_classify_complaint(db: Session, job: Job) -> dict:
    complaint_id = uuid.UUID(str(job.payload["complaint_id"]))
    complaint = db.get(Complaint, complaint_id)
    if complaint is None or complaint.bank_id != job.bank_id:
        return {"skipped": True, "reason": "complaint_not_found"}

    settings = get_settings()
    b_start = bucket_start(complaint.occurred_at, settings.spike_bucket_minutes)
    detect_at = b_start + timedelta(minutes=settings.spike_bucket_minutes - 1, seconds=59)

    if complaint.issue_type is not None:
        enqueue_job(
            db,
            bank_id=job.bank_id,
            kind=JobKind.DETECT_SPIKES,
            payload={"now": detect_at.isoformat()},
            idempotency_key=f"detect:{b_start.isoformat()}",
            reopen_completed=True,
        )
        return {"skipped": True, "reason": "already_classified", "issue_type": complaint.issue_type.value}

    result, source = ai_classify_text(complaint.text, complaint.channel.value)
    runtime = getattr(result, "_runtime", {})
    issue_val = result.issue_type.value if hasattr(result.issue_type, "value") else result.issue_type

    from app.services.complaint_service import apply_classification

    classified = apply_classification(
        db,
        complaint,
        ComplaintClassification(
            issue_type=issue_val,
            severity=result.severity,
            sentiment=result.sentiment,
            language=result.language,
            summary=result.short_summary,
            mentioned_amount=result.mentioned_amount,
            mentioned_time=result.mentioned_time,
            confidence=result.confidence,
            is_fraud=result.is_fraud,
        ),
    )
    log_event(
        db,
        bank_id=job.bank_id,
        actor="worker",
        action="complaint_classified",
        entity_type="complaint",
        entity_id=str(complaint.id),
        details={
            "issue_type": classified.issue_type.value,
            "source": source,
            **{k: v for k, v in runtime.items() if k != "source"},
        },
    )
    enqueue_job(
        db,
        bank_id=job.bank_id,
        kind=JobKind.DETECT_SPIKES,
        payload={"now": detect_at.isoformat()},
        idempotency_key=f"detect:{b_start.isoformat()}",
        reopen_completed=True,
    )
    return {"complaint_id": str(complaint.id), "issue_type": classified.issue_type.value, "source": source}


def _handle_detect_spikes(db: Session, job: Job) -> dict:
    raw_now = job.payload.get("now")
    now = datetime.fromisoformat(raw_now.replace("Z", "+00:00")) if raw_now else None
    created = run_detection(db, job.bank_id, now=now)

    open_incidents = db.scalars(
        select(Incident).where(
            Incident.bank_id == job.bank_id,
            Incident.status.in_(OPEN_STATUSES),
        )
    ).all()

    enqueued_investigations = []
    for incident in open_incidents:
        # Concept #3: Trigger a new agent run only if the evidence (complaint count) changed
        idem_key = f"investigate:{incident.id}:{incident.complaint_count}"
        inv_job = enqueue_job(
            db,
            bank_id=job.bank_id,
            kind=JobKind.INVESTIGATE_INCIDENT,
            payload={"incident_id": str(incident.id), "complaint_count": incident.complaint_count},
            idempotency_key=idem_key,
        )
        if inv_job.status == JobStatus.PENDING:
            enqueued_investigations.append(str(incident.id))

    return {
        "created_incidents": [str(inc.id) for inc in created],
        "investigations_queued": enqueued_investigations,
    }


def _handle_investigate_incident(db: Session, job: Job) -> dict:
    incident_id = uuid.UUID(str(job.payload["incident_id"]))
    incident = db.get(Incident, incident_id)
    if incident is None or incident.bank_id != job.bank_id:
        return {"skipped": True, "reason": "incident_not_found"}

    incident.status = IncidentStatus.INVESTIGATING
    db.commit()
    incident = investigate_incident(db, job.bank_id, incident, actor="worker")
    drafts = create_drafts(db, job.bank_id, incident, actor="worker")
    return {
        "incident_id": str(incident.id),
        "likely_cause": incident.likely_cause,
        "cause_confidence": incident.cause_confidence,
        "draft_count": len(drafts),
    }


def _handle_dispatch_approval(db: Session, job: Job) -> dict:
    draft_id = uuid.UUID(str(job.payload["draft_id"]))
    draft = db.get(Draft, draft_id)
    if draft is None or draft.status != DraftStatus.APPROVED:
        return {"skipped": True, "reason": "draft_not_approved"}

    log_event(
        db,
        bank_id=job.bank_id,
        actor="outbox_worker",
        action="approval_dispatched",
        entity_type="draft",
        entity_id=str(draft.id),
        details={
            "kind": draft.kind.value,
            "incident_id": str(draft.incident_id),
            "decided_by": draft.decided_by,
        },
    )
    return {"dispatched": True, "draft_id": str(draft.id), "kind": draft.kind.value}


def _handle_sync_social_rules(db: Session, job: Job) -> dict:
    from app.adapters.x_adapter import sync_stream_rules

    return sync_stream_rules(db, actor="worker")


def _execute_job(db: Session, job: Job) -> dict:
    if job.payload.get("simulate_failure"):
        raise RuntimeError("Simulated worker failure for dead-letter testing")
    if job.kind == JobKind.CLASSIFY_COMPLAINT:
        return _handle_classify_complaint(db, job)
    if job.kind == JobKind.DETECT_SPIKES:
        return _handle_detect_spikes(db, job)
    if job.kind == JobKind.INVESTIGATE_INCIDENT:
        return _handle_investigate_incident(db, job)
    if job.kind == JobKind.DISPATCH_APPROVAL:
        return _handle_dispatch_approval(db, job)
    if job.kind == JobKind.SYNC_SOCIAL_RULES:
        return _handle_sync_social_rules(db, job)
    raise ValueError(f"Unsupported job kind: {job.kind}")


def process_next_job(
    db: Session, bank_id: uuid.UUID | None = None, now: datetime | None = None
) -> Job | None:
    """Claim and execute a single queued job with bounded retry and dead-letter handling."""
    job = claim_next_job(db, bank_id=bank_id, now=now)
    if job is None:
        return None
    job_id = job.id
    try:
        result = _execute_job(db, job)
        job.status = JobStatus.COMPLETED
        job.result = result
        job.last_error = None
        job.lease_until = None
        job.updated_at = utcnow()
        db.commit()
        return job
    except Exception as exc:
        db.rollback()
        failed_job = db.get(Job, job_id)
        if failed_job is None:
            return None
        failed_job.last_error = str(exc)[:1000]
        failed_job.lease_until = None
        failed_job.updated_at = utcnow()
        if failed_job.attempts >= failed_job.max_attempts:
            failed_job.status = JobStatus.DEAD_LETTER
            log_event(
                db,
                bank_id=failed_job.bank_id,
                actor="worker",
                action="job_dead_lettered",
                entity_type="job",
                entity_id=str(failed_job.id),
                details={
                    "kind": failed_job.kind.value,
                    "attempts": failed_job.attempts,
                    "error": failed_job.last_error,
                },
            )
        else:
            failed_job.status = JobStatus.PENDING
        db.commit()
        return failed_job


def drain_jobs(
    db: Session, bank_id: uuid.UUID | None = None, limit: int = 100
) -> dict:
    """Drain up to `limit` pending jobs synchronously (ideal for demo replay and tests)."""
    processed = 0
    completed = 0
    retried = 0
    dead_lettered = 0
    while processed < limit:
        job = process_next_job(db, bank_id=bank_id)
        if job is None:
            break
        processed += 1
        if job.status == JobStatus.COMPLETED:
            completed += 1
        elif job.status == JobStatus.DEAD_LETTER:
            dead_lettered += 1
        else:
            retried += 1
    return {
        "processed": processed,
        "completed": completed,
        "retried": retried,
        "dead_lettered": dead_lettered,
    }
