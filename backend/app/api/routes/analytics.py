from datetime import timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import AuthUser, DbSession
from app.db.base import utcnow
from app.models import Complaint, Incident
from app.models.enums import IncidentStatus

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
def summary(user: AuthUser, db: DbSession, hours: int = Query(24, ge=1, le=720)) -> dict:
    since = utcnow() - timedelta(hours=hours)
    base = (Complaint.bank_id == user.bank_id) & (Complaint.occurred_at >= since)

    total = db.scalar(select(func.count()).select_from(Complaint).where(base)) or 0
    by_issue = db.execute(
        select(Complaint.issue_type, func.count()).where(base).group_by(Complaint.issue_type)
    ).all()
    by_channel = db.execute(
        select(Complaint.channel, func.count()).where(base).group_by(Complaint.channel)
    ).all()
    open_incidents = db.scalar(
        select(func.count()).select_from(Incident).where(
            Incident.bank_id == user.bank_id,
            Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.INVESTIGATING, IncidentStatus.AWAITING_APPROVAL])
        )
    ) or 0

    return {
        "window_hours": hours,
        "total_complaints": total,
        "by_issue_type": {(k.value if k else "unclassified"): v for k, v in by_issue},
        "by_channel": {k.value: v for k, v in by_channel},
        "open_incidents": open_incidents,
    }
