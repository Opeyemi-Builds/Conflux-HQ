from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import extract, func, select

from app.api.deps import AuthUser, DbSession
from app.db.base import utcnow
from app.models import Complaint, Incident, SocialReceipt, Transaction
from app.models.enums import IncidentStatus, TxnStatus

router = APIRouter(prefix="/analytics", tags=["analytics"])

Hours = Annotated[int, Query(ge=1, le=720)]
Anchor = Annotated[
    AwareDatetime | None,
    Query(description="Timezone-aware window end; defaults to now. Normalized to UTC."),
]


class WindowResponse(BaseModel):
    window_hours: int
    window_start: datetime = Field(description="Inclusive UTC window start.")
    window_end: datetime = Field(description="Exclusive UTC window end.")


class BreakdownResponse(WindowResponse):
    by_issue_type: dict[str, int]
    by_channel: dict[str, int]
    by_region: dict[str, int]


class SummaryResponse(BreakdownResponse):
    total_complaints: int
    by_severity: dict[str, int]
    open_incidents: int = Field(
        description="Current open statuses, across all time, excluding incidents detected or started after window_end. Not a historical status snapshot."
    )
    fraud_count: int = Field(description="Complaints with is_fraud=true in the window.")
    money_at_risk: Decimal = Field(
        description="Sum of complaint mentioned_amount only (all complaints, nulls ignored). Unverified reported exposure, NOT verified financial loss; may include duplicate reports."
    )
    avg_time_to_detect_seconds: float | None = Field(
        default=None,
        description="Average seconds from incident started_at to detected_at for incidents in the window.",
    )
    repeat_complaint_rate: float = Field(
        default=0.0,
        description="Fraction (0 to 1) of known customer_ref values that submitted more than one complaint in the window.",
    )


class TrendBucket(BaseModel):
    bucket_start: datetime = Field(description="UTC calendar-hour start; edge buckets may be partial.")
    total_complaints: int


class TrendsResponse(WindowResponse):
    buckets: list[TrendBucket]


class SocialAnalyticsResponse(WindowResponse):
    total_posts: int
    unique_authors: int
    total_engagement: int
    high_reach_posts: int
    reputation_risk_posts: int
    average_reputation_score: float
    top_reputation_flags: dict[str, int]
    hourly_velocity: list[dict]


class TransactionsResponse(WindowResponse):
    total_transactions: int
    by_status: dict[str, int]
    failed_rate: float = Field(description="Failed count / total count, a fraction from 0 to 1; zero for an empty window.")
    total_amount: Decimal = Field(description="Sum of transaction amounts across all statuses, not a loss measure.")
    amount_by_status: dict[str, Decimal]


def _window(hours: int, at: datetime | None) -> dict:
    end = (at if at is not None else utcnow()).astimezone(timezone.utc)
    return {
        "window_hours": hours,
        "window_start": end - timedelta(hours=hours),
        "window_end": end,
    }


def _scope(model, user, window):
    return (
        model.bank_id == user.bank_id,
        model.occurred_at >= window["window_start"],
        model.occurred_at < window["window_end"],
    )


def _counts(db, column, scope, missing="unclassified") -> dict[str, int]:
    rows = db.execute(select(column, func.count()).where(*scope).group_by(column)).all()
    return {
        (key.value if hasattr(key, "value") else key) if key is not None else missing: count
        for key, count in rows
    }


def _breakdown(db, scope) -> dict:
    return {
        "by_issue_type": _counts(db, Complaint.issue_type, scope),
        "by_channel": _counts(db, Complaint.channel, scope),
        "by_region": _counts(db, Complaint.region, scope, missing="unknown"),
    }


@router.get("/summary", response_model=SummaryResponse)
def summary(user: AuthUser, db: DbSession, hours: Hours = 24, at: Anchor = None) -> dict:
    window = _window(hours, at)
    scope = _scope(Complaint, user, window)
    total, money_at_risk = db.execute(
        select(func.count(), func.coalesce(func.sum(Complaint.mentioned_amount), 0))
        .select_from(Complaint)
        .where(*scope)
    ).one()
    fraud_count = db.scalar(
        select(func.count()).select_from(Complaint).where(*scope, Complaint.is_fraud.is_(True))
    ) or 0
    open_incidents = db.scalar(
        select(func.count()).select_from(Incident).where(
            Incident.bank_id == user.bank_id,
            Incident.detected_at < window["window_end"],
            Incident.started_at < window["window_end"],
            Incident.status.in_([
                IncidentStatus.OPEN, IncidentStatus.INVESTIGATING, IncidentStatus.AWAITING_APPROVAL
            ]),
        )
    ) or 0
    window_incidents = db.scalars(
        select(Incident).where(
            Incident.bank_id == user.bank_id,
            Incident.started_at >= window["window_start"],
            Incident.started_at < window["window_end"],
        )
    ).all()
    ttd_values = [
        max(0.0, (inc.detected_at - inc.started_at).total_seconds())
        for inc in window_incidents
        if inc.detected_at and inc.started_at
    ]
    avg_ttd = round(sum(ttd_values) / len(ttd_values), 2) if ttd_values else None

    cust_rows = db.execute(
        select(Complaint.customer_ref, func.count())
        .where(*scope, Complaint.customer_ref.is_not(None))
        .group_by(Complaint.customer_ref)
    ).all()
    repeat_rate = (
        round(sum(1 for _, c in cust_rows if c > 1) / len(cust_rows), 4)
        if cust_rows
        else 0.0
    )
    return {
        **window,
        **_breakdown(db, scope),
        "total_complaints": total,
        "by_severity": _counts(db, Complaint.severity, scope),
        "open_incidents": open_incidents,
        "fraud_count": fraud_count,
        "money_at_risk": money_at_risk,
        "avg_time_to_detect_seconds": avg_ttd,
        "repeat_complaint_rate": repeat_rate,
    }


@router.get("/trends", response_model=TrendsResponse)
def trends(user: AuthUser, db: DbSession, hours: Hours = 24, at: Anchor = None) -> dict:
    """Zero-filled UTC calendar hours intersecting [start, end); partial edge hours included.

    A non-hour-aligned window has hours + 1 buckets. Stored timezone-aware timestamps
    are normalized by the database expression so PostgreSQL session timezone cannot
    shift the UTC calendar boundaries. SQLite stores this application's UTC dates
    without offsets.
    """
    window = _window(hours, at)
    timestamp = Complaint.occurred_at
    if db.get_bind().dialect.name == "postgresql":
        timestamp = func.timezone("UTC", timestamp)
    parts = [extract(part, timestamp) for part in ("year", "month", "day", "hour")]
    rows = db.execute(
        select(*parts, func.count())
        .where(*_scope(Complaint, user, window))
        .group_by(*parts)
    ).all()
    counts = {
        datetime(int(year), int(month), int(day), int(hour), tzinfo=timezone.utc): count
        for year, month, day, hour, count in rows
    }
    bucket = window["window_start"].replace(minute=0, second=0, microsecond=0)
    buckets = []
    while bucket < window["window_end"]:
        buckets.append({"bucket_start": bucket, "total_complaints": counts.get(bucket, 0)})
        bucket += timedelta(hours=1)
    return {**window, "buckets": buckets}


@router.get("/breakdown", response_model=BreakdownResponse)
def breakdown(user: AuthUser, db: DbSession, hours: Hours = 24, at: Anchor = None) -> dict:
    window = _window(hours, at)
    return {**window, **_breakdown(db, _scope(Complaint, user, window))}


@router.get("/social", response_model=SocialAnalyticsResponse)
def social_analytics(user: AuthUser, db: DbSession, hours: Hours = 24, at: Anchor = None) -> dict:
    """Summarize received social posts, engagement and reputation-risk velocity."""
    window = _window(hours, at)
    rows = db.scalars(
        select(SocialReceipt).where(
            SocialReceipt.bank_id == user.bank_id,
            SocialReceipt.received_at >= window["window_start"],
            SocialReceipt.received_at < window["window_end"],
        )
    ).all()
    authors = set()
    total_engagement = 0
    high_reach = 0
    risk_posts = 0
    score_total = 0.0
    flags: dict[str, int] = {}
    buckets: dict[datetime, int] = {}
    for row in rows:
        metrics = row.public_metrics or {}
        total_engagement += sum(max(0, int(metrics.get(key, 0) or 0)) for key in ("like_count", "retweet_count", "reply_count", "quote_count"))
        if "high_reach" in (row.reputation_flags or []):
            high_reach += 1
        if row.reputation_score >= 0.35:
            risk_posts += 1
        score_total += float(row.reputation_score or 0)
        for flag in row.reputation_flags or []:
            flags[flag] = flags.get(flag, 0) + 1
        bucket = row.received_at.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        buckets[bucket] = buckets.get(bucket, 0) + 1
        if row.author_ref_hash:
            authors.add(row.author_ref_hash)
        else:
            authors.add(f"{row.bank_id}:{row.post_id}")
    cursor = window["window_start"].replace(minute=0, second=0, microsecond=0)
    velocity = []
    while cursor < window["window_end"]:
        velocity.append({"bucket_start": cursor, "posts": buckets.get(cursor, 0)})
        cursor += timedelta(hours=1)
    return {**window, "total_posts": len(rows), "unique_authors": len(authors),
            "total_engagement": total_engagement, "high_reach_posts": high_reach,
            "reputation_risk_posts": risk_posts,
            "average_reputation_score": round(score_total / len(rows), 4) if rows else 0.0,
            "top_reputation_flags": dict(sorted(flags.items(), key=lambda item: (-item[1], item[0]))[:10]),
            "hourly_velocity": velocity}


@router.get("/transactions", response_model=TransactionsResponse)
def transactions(user: AuthUser, db: DbSession, hours: Hours = 24, at: Anchor = None) -> dict:
    window = _window(hours, at)
    rows = db.execute(
        select(Transaction.status, func.count(), func.coalesce(func.sum(Transaction.amount), 0))
        .where(*_scope(Transaction, user, window))
        .group_by(Transaction.status)
    ).all()
    by_status = {status.value: 0 for status in TxnStatus}
    amount_by_status = {status.value: Decimal("0") for status in TxnStatus}
    for status, count, amount in rows:
        by_status[status.value] = count
        amount_by_status[status.value] = amount
    total = sum(by_status.values())
    return {
        **window,
        "total_transactions": total,
        "by_status": by_status,
        "failed_rate": by_status[TxnStatus.FAILED.value] / total if total else 0.0,
        "total_amount": sum(amount_by_status.values(), Decimal("0")),
        "amount_by_status": amount_by_status,
    }
