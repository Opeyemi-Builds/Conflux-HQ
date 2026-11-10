"""Bank handoff feed: one versioned, bank-scoped cursor poll for dashboards.

Banks integrate Conflux signal into their own systems by polling
``GET /machine/updates?since=<cursor>`` with their ``cfx_api_`` key. The feed
returns only items created or changed since the cursor, newest cursor included,
so a bank loop is cheap: an empty ``items`` list with an unchanged cursor means
"nothing new". This is a read-only pull API, not a webhook and not a file drop.

Cursor format: ``"<iso-utc>:<uuid>"`` per collection is overkill; a single
UTC timestamp cursor plus per-item ``updated_at``/``created_at`` keeps banks'
client code to one stored string. Ties on identical timestamps are broken by
(id) ordering, and the returned cursor always advances past what was sent.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Complaint, CorrectiveAction, Draft, Incident, InvestigationRun

COLLECTIONS = ("complaints", "incidents", "drafts", "actions", "investigations", "audit")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_cursor(raw: str | None) -> datetime | None:
    """Parse the ``since`` cursor; None means 'from the beginning'."""
    if not raw or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("since must be an ISO-8601 UTC timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError("since must include a timezone (use Z or +00:00)")
    return parsed.astimezone(timezone.utc)


def _complaint_item(c: Complaint) -> dict:
    """Ticker row: issue + severity + time + location + text. No analysis fields."""
    return {
        "collection": "complaints",
        "id": str(c.id),
        "updated_at": (_aware(c.classified_at or c.ingested_at) or _aware(c.occurred_at)).isoformat(),
        "data": {
            "id": str(c.id),
            "channel": c.channel.value,
            "issue_type": c.issue_type.value if c.issue_type else None,
            "severity": c.severity.value if c.severity else None,
            "text": c.text,
            "summary": c.summary,
            "region": c.region,
            "occurred_at": c.occurred_at.isoformat() if c.occurred_at else None,
            "incident_id": str(c.incident_id) if c.incident_id else None,
        },
    }


def _incident_item(i: Incident) -> dict:
    """Ticker row: issue + status + count + time. Cause/score/summary live in the report flow."""
    return {
        "collection": "incidents",
        "id": str(i.id),
        "updated_at": _aware(i.detected_at).isoformat(),
        "data": {
            "id": str(i.id),
            "issue_type": i.issue_type.value,
            "status": i.status.value,
            "complaint_count": i.complaint_count,
            "detected_at": i.detected_at.isoformat() if i.detected_at else None,
        },
    }


def _draft_item(d: Draft) -> dict:
    return {
        "collection": "drafts",
        "id": str(d.id),
        "updated_at": (_aware(d.decided_at or d.created_at)).isoformat(),
        "data": {
            "id": str(d.id),
            "incident_id": str(d.incident_id),
            "kind": d.kind.value,
            "status": d.status.value,
            "content": d.content,
            "decided_at": d.decided_at.isoformat() if d.decided_at else None,
        },
    }


def _action_item(a: CorrectiveAction) -> dict:
    return {
        "collection": "actions",
        "id": str(a.id),
        "updated_at": _aware(a.updated_at).isoformat(),
        "data": {
            "id": str(a.id),
            "incident_id": str(a.incident_id),
            "title": a.title,
            "status": a.status.value,
            "owner": a.owner,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        },
    }


def _run_item(r: InvestigationRun) -> dict:
    return {
        "collection": "investigations",
        "id": str(r.id),
        "updated_at": _aware(r.updated_at).isoformat(),
        "data": {
            "id": str(r.id),
            "incident_id": str(r.incident_id),
            "status": r.status.value,
            "provider": r.provider,
            "confidence": r.confidence,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        },
    }


def _audit_item(row: AuditLog) -> dict:
    return {
        "collection": "audit",
        "id": str(row.id),
        "updated_at": _aware(row.created_at).isoformat(),
        "data": {
            "id": str(row.id),
            "actor": row.actor,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "details": row.details or {},
            "created_at": row.created_at.isoformat() if row.created_at else None,
        },
    }


def handoff_updates(
    db: Session,
    *,
    bank_id: uuid.UUID,
    since: datetime | None,
    limit: int = 100,
    collections: tuple[str, ...] = COLLECTIONS,
) -> dict:
    """Collect changed items across handoff collections, ordered, cursor-capped."""
    wanted = [c for c in collections if c in COLLECTIONS]
    items: list[dict] = []

    if "complaints" in wanted:
        q = select(Complaint).where(Complaint.bank_id == bank_id)
        if since is not None:
            q = q.where(
                or_(
                    Complaint.classified_at.is_not(None) & (Complaint.classified_at > since),
                    Complaint.classified_at.is_(None) & (Complaint.ingested_at > since),
                )
            )
        for c in db.scalars(q.order_by(Complaint.ingested_at.asc(), Complaint.id.asc()).limit(limit)).all():
            items.append(_complaint_item(c))

    if "incidents" in wanted:
        q = select(Incident).where(Incident.bank_id == bank_id)
        if since is not None:
            q = q.where(Incident.detected_at > since)
        for i in db.scalars(q.order_by(Incident.detected_at.asc(), Incident.id.asc()).limit(limit)).all():
            items.append(_incident_item(i))

    if "drafts" in wanted:
        q = select(Draft).join(Incident, Draft.incident_id == Incident.id).where(Incident.bank_id == bank_id)
        if since is not None:
            q = q.where(or_(Draft.created_at > since, Draft.decided_at.is_not(None) & (Draft.decided_at > since)))
        for d in db.scalars(q.order_by(Draft.created_at.asc(), Draft.id.asc()).limit(limit)).all():
            items.append(_draft_item(d))

    if "actions" in wanted:
        q = select(CorrectiveAction).where(CorrectiveAction.bank_id == bank_id)
        if since is not None:
            q = q.where(CorrectiveAction.updated_at > since)
        for a in db.scalars(q.order_by(CorrectiveAction.updated_at.asc(), CorrectiveAction.id.asc()).limit(limit)).all():
            items.append(_action_item(a))

    if "investigations" in wanted:
        q = select(InvestigationRun).where(InvestigationRun.bank_id == bank_id)
        if since is not None:
            q = q.where(InvestigationRun.updated_at > since)
        for r in db.scalars(q.order_by(InvestigationRun.updated_at.asc(), InvestigationRun.id.asc()).limit(limit)).all():
            items.append(_run_item(r))

    if "audit" in wanted:
        # The feed's own poll receipts are audit proof, not handoff signal:
        # serving them back would make every poll show up in the next poll.
        q = select(AuditLog).where(
            AuditLog.bank_id == bank_id,
            ~((AuditLog.entity_type == "handoff_feed") & (AuditLog.action == "machine_updates_polled")),
        )
        if since is not None:
            q = q.where(AuditLog.created_at > since)
        for row in db.scalars(q.order_by(AuditLog.created_at.asc(), AuditLog.id.asc()).limit(limit)).all():
            items.append(_audit_item(row))

    items.sort(key=lambda it: (it["updated_at"], it["id"]))
    truncated = items[limit:]
    items = items[:limit]
    cursor = items[-1]["updated_at"] if items else (since.isoformat() if since else None)
    return {
        "bank_id": str(bank_id),
        "since": since.isoformat() if since else None,
        "cursor": cursor,
        "count": len(items),
        "truncated": bool(truncated),
        "collections": sorted(wanted),
        "items": items,
    }
