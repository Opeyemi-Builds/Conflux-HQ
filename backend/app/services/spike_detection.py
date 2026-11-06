"""Deterministic spike detection (no LLM, so the demo is reliable).

For each issue type, complaints are counted in fixed time buckets. The current bucket
is compared with a baseline built from the trailing buckets using the median and the
median absolute deviation (MAD), which a few large past spikes cannot distort.
"""
import statistics
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import Complaint, Incident
from app.models.enums import IncidentStatus, IssueType
from app.services.audit import log_event

OPEN_STATUSES = (IncidentStatus.OPEN, IncidentStatus.INVESTIGATING, IncidentStatus.AWAITING_APPROVAL)


@dataclass
class SpikeResult:
    is_spike: bool
    current: int
    baseline: float
    threshold: float
    growth_rate: float


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def bucket_start(dt: datetime, minutes: int) -> datetime:
    dt = _aware(dt)
    floored = dt.minute - dt.minute % minutes
    return dt.replace(minute=floored, second=0, microsecond=0)


def evaluate_spike(
    history: list[int], current: int, *, k: float = 3.0, min_volume: int = 10
) -> SpikeResult:
    baseline = float(statistics.median(history)) if history else 0.0
    mad = statistics.median([abs(x - baseline) for x in history]) if history else 0.0
    scale = max(mad * 1.4826, 1.0)  # floor of 1 keeps quiet baselines from flagging noise
    threshold = baseline + k * scale
    return SpikeResult(
        is_spike=current >= min_volume and current > threshold,
        current=current,
        baseline=baseline,
        threshold=threshold,
        growth_rate=current / max(baseline, 1.0),
    )


def priority_score(volume: int, growth_rate: float) -> int:
    """0-100. Placeholder blend of volume and growth; money at risk and customer type come later."""
    return round(min(volume / 50, 1.0) * 50 + min(growth_rate / 10, 1.0) * 50)


def run_detection(
    db: Session, bank_id: uuid.UUID, now: datetime | None = None, settings: Settings | None = None
) -> list[Incident]:
    s = settings or get_settings()
    minutes = s.spike_bucket_minutes
    now = _aware(now) if now else datetime.now(timezone.utc)
    current_start = bucket_start(now, minutes)
    current_end = current_start + timedelta(minutes=minutes)
    n_history = s.spike_baseline_hours * 60 // minutes
    window_start = current_start - timedelta(minutes=minutes * n_history)

    rows = db.execute(
        select(Complaint).where(
            Complaint.bank_id == bank_id,
            Complaint.issue_type.is_not(None),
            Complaint.occurred_at >= window_start,
            Complaint.occurred_at < current_end,
        )
    ).scalars().all()

    counts: dict[IssueType, dict[datetime, int]] = defaultdict(lambda: defaultdict(int))
    current_complaints: dict[IssueType, list[Complaint]] = defaultdict(list)
    for c in rows:
        start = bucket_start(c.occurred_at, minutes)
        counts[c.issue_type][start] += 1
        if start == current_start:
            current_complaints[c.issue_type].append(c)

    created: list[Incident] = []
    for issue_type, per_bucket in counts.items():
        history = [per_bucket.get(current_start - timedelta(minutes=minutes * i), 0) for i in range(1, n_history + 1)]
        current = per_bucket.get(current_start, 0)
        result = evaluate_spike(history, current, k=s.spike_mad_multiplier, min_volume=s.spike_min_volume)
        if not result.is_spike:
            continue

        already_open = db.execute(
            select(Incident).where(
                Incident.bank_id == bank_id, Incident.issue_type == issue_type, Incident.status.in_(OPEN_STATUSES)
            )
        ).scalars().first()
        if already_open:
            # Only count newly attached complaints; repeated polling must be idempotent.
            for complaint in current_complaints[issue_type]:
                if complaint.incident_id is None:
                    complaint.incident_id = already_open.id
            db.flush()
            linked = db.scalars(select(Complaint).where(
                Complaint.bank_id == bank_id, Complaint.incident_id == already_open.id
            )).all()
            already_open.complaint_count = len(linked)
            channels = defaultdict(int)
            for complaint in linked:
                channels[complaint.channel.value] += 1
            already_open.affected_channels = dict(channels)
            already_open.growth_rate = round(result.growth_rate, 2)
            already_open.priority_score = priority_score(len(linked), result.growth_rate)
            continue

        channels: dict[str, int] = defaultdict(int)
        for c in current_complaints[issue_type]:
            channels[c.channel.value] += 1

        incident = Incident(
            bank_id=bank_id,
            issue_type=issue_type,
            started_at=current_start,
            detected_at=now,
            complaint_count=current,
            baseline=result.baseline,
            growth_rate=round(result.growth_rate, 2),
            priority_score=priority_score(current, result.growth_rate),
            affected_channels=dict(channels),
        )
        db.add(incident)
        db.flush()
        for c in current_complaints[issue_type]:
            c.incident_id = incident.id
        log_event(
            db, bank_id=bank_id, actor="system", action="spike_detected", entity_type="incident", entity_id=str(incident.id),
            details={"issue_type": issue_type.value, "count": current, "baseline": result.baseline,
                     "threshold": round(result.threshold, 2)},
        )
        created.append(incident)

    db.commit()
    return created
