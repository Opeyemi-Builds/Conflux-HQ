"""Deterministic evidence used before an LLM is allowed to explain an incident."""
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Complaint, Incident, PaymentException, SystemEvent, Transaction
from app.models.enums import ReversalStatus, TxnStatus

_ISSUE_COMPONENT_KEYWORDS = {
    "failed_transfer": ("transfer", "switch", "ussd", "nip", "settlement"),
    "double_debit": ("transfer", "debit", "switch", "ledger", "settlement"),
    "card_atm": ("atm", "card", "dispense", "gateway"),
    "pos": ("pos", "terminal", "merchant", "switch"),
    "app_login": ("app", "auth", "login", "mobile", "session"),
    "fees": ("fee", "billing", "tariff", "charge"),
    "loan": ("loan", "credit", "lending"),
}


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _aware(dt)
    except ValueError:
        return None


def match_incident_transactions(db: Session, bank_id, incident: Incident) -> int:
    """Link unlinked incident complaints to failed transactions by amount, region, and time window."""
    complaints = db.execute(
        select(Complaint).where(Complaint.bank_id == bank_id, Complaint.incident_id == incident.id)
    ).scalars().all()
    if not complaints:
        return 0

    start = _aware(incident.started_at)
    candidates = db.execute(
        select(Transaction).where(
            Transaction.bank_id == bank_id,
            Transaction.status == TxnStatus.FAILED,
            Transaction.occurred_at >= start - timedelta(minutes=30),
            Transaction.occurred_at <= start + timedelta(minutes=60),
        )
    ).scalars().all()
    if not candidates:
        return sum(1 for c in complaints if c.transaction_id is not None)

    used_ids = {c.transaction_id for c in complaints if c.transaction_id is not None}
    newly_matched = 0
    for complaint in complaints:
        if complaint.transaction_id is not None:
            continue
        c_time = _aware(complaint.occurred_at)
        best_txn = None
        best_score = -1.0
        for txn in candidates:
            if txn.id in used_ids:
                continue
            delta_seconds = abs((_aware(txn.occurred_at) - c_time).total_seconds())
            if delta_seconds > 1800:
                continue
            score = max(0.0, 1.0 - (delta_seconds / 1800.0))
            if complaint.mentioned_amount is not None and txn.amount == complaint.mentioned_amount:
                score += 3.0
            if complaint.region and txn.region and complaint.region.lower() == txn.region.lower():
                score += 2.0
            if complaint.channel.value == "in_app" and txn.txn_channel.value == "app":
                score += 1.0
            if score > best_score:
                best_score = score
                best_txn = txn
        if best_txn is not None and best_score >= 1.5:
            complaint.transaction_id = best_txn.id
            used_ids.add(best_txn.id)
            newly_matched += 1

    if newly_matched:
        db.flush()
    return sum(1 for c in complaints if c.transaction_id is not None)


def build_evidence(db: Session, bank_id, incident: Incident) -> dict:
    matched_count = match_incident_transactions(db, bank_id, incident)
    incident_complaints = db.execute(
        select(Complaint).where(Complaint.bank_id == bank_id, Complaint.incident_id == incident.id)
    ).scalars().all()

    channels = {
        channel.value: sum(1 for x in incident_complaints if x.channel == channel)
        for channel in {x.channel for x in incident_complaints}
    }
    regions = Counter(x.region for x in incident_complaints if x.region)

    start = _aware(incident.started_at)
    end = start + timedelta(minutes=60)
    transactions = db.execute(
        select(Transaction).where(
            Transaction.bank_id == bank_id,
            Transaction.occurred_at >= start - timedelta(hours=1),
            Transaction.occurred_at <= end,
        )
    ).scalars().all()
    failed = [t for t in transactions if t.status == TxnStatus.FAILED]
    unreversed_failed = [t for t in failed if t.reversal_status == ReversalStatus.PENDING]

    processors = sorted({t.processor for t in transactions if t.processor})
    tx_channels = sorted({t.txn_channel.value for t in failed})
    failed_by_processor = {
        processor: sum(1 for t in failed if t.processor == processor)
        for processor in processors
    }
    dominant_processor = (
        max(failed_by_processor.items(), key=lambda item: item[1])[0]
        if failed_by_processor and max(failed_by_processor.values()) > 0
        else None
    )

    events = db.execute(
        select(SystemEvent)
        .where(
            SystemEvent.bank_id == bank_id,
            SystemEvent.starts_at >= start - timedelta(hours=6),
            SystemEvent.starts_at <= end,
        )
        .order_by(SystemEvent.starts_at)
    ).scalars().all()

    total_complaints = max(len(incident_complaints), 1)
    channel_shares = {ch: round(cnt / total_complaints, 2) for ch, cnt in channels.items()}

    exceptions = db.scalars(
        select(PaymentException).join(Complaint, PaymentException.complaint_id == Complaint.id).where(
            PaymentException.bank_id == bank_id,
            Complaint.bank_id == bank_id,
            Complaint.incident_id == incident.id,
        )
    ).all()

    return {
        "reconciliation": {
            "exception_count": len(exceptions),
            "by_status": dict(Counter(case.status.value for case in exceptions)),
            "approval_required": sum(case.approval_required for case in exceptions),
            "note": "Candidate matches are investigative leads, not proof of settlement or refund eligibility.",
        },
        "incident": {
            "issue_type": incident.issue_type.value,
            "started_at": start.isoformat(),
            "complaint_count": incident.complaint_count,
            "baseline": incident.baseline,
            "growth_rate": incident.growth_rate,
        },
        "complaints": {
            "count": len(incident_complaints),
            "channels": channels,
            "channel_shares": channel_shares,
            "top_region": regions.most_common(1)[0][0] if regions else None,
        },
        "transactions": {
            "observed": len(transactions),
            "failed": len(failed),
            "unreversed_failed": len(unreversed_failed),
            "matched_complaints": matched_count,
            "failure_rate": round(len(failed) / len(transactions), 3) if transactions else 0.0,
            "channels": tx_channels,
            "failed_by_processor": failed_by_processor,
            "dominant_processor": dominant_processor,
        },
        "events": [
            {
                "type": e.event_type.value,
                "component": e.component,
                "version": e.version,
                "description": e.description,
                "starts_at": _aware(e.starts_at).isoformat(),
            }
            for e in events
        ],
    }


def rank_events(evidence: dict) -> list[dict]:
    """Deterministic cause scoring based on time proximity, path/component overlap, and failure rate."""
    incident_info = evidence.get("incident", {})
    incident_time = _parse_iso(incident_info.get("started_at"))
    issue_type = incident_info.get("issue_type", "other")
    tx_info = evidence.get("transactions", {})
    failed_count = tx_info.get("failed", 0)
    observed_count = max(tx_info.get("observed", 0), 1)
    dominant_processor = (tx_info.get("dominant_processor") or "").lower()
    keywords = _ISSUE_COMPONENT_KEYWORDS.get(issue_type, ())

    candidates = []
    for event in evidence.get("events", []):
        score = 0.05
        reasons = []
        event_time = _parse_iso(event.get("starts_at"))

        # 1. Time proximity (0.0 to 0.40): events shortly before the spike score highest
        if incident_time and event_time:
            minutes_before = (incident_time - event_time).total_seconds() / 60.0
            if -5.0 <= minutes_before <= 60.0:
                score += 0.40
                reasons.append(f"started {round(max(0.0, minutes_before))}m before spike")
            elif 60.0 < minutes_before <= 180.0:
                score += 0.20
                reasons.append(f"started {round(minutes_before)}m before spike")
            else:
                reasons.append("outside primary 60m pre-spike window")
        elif event.get("type") == "release":
            score += 0.25

        # 2. Event type & component/path overlap (0.0 to 0.35)
        etype = (event.get("type") or "").lower()
        if etype in ("release", "outage", "config_change"):
            score += 0.15
        blob = f"{event.get('component', '')} {event.get('description', '')}".lower()
        if any(kw in blob for kw in keywords):
            score += 0.12
            reasons.append("component matches issue path")
        if dominant_processor and dominant_processor in blob:
            score += 0.08
            reasons.append(f"matches failing processor {dominant_processor}")
        if "decoy" in blob or "unrelated" in blob:
            score = max(0.10, score - 0.25)

        # 3. Transaction failure-rate delta (0.0 to 0.20)
        if failed_count > 0:
            fail_ratio = failed_count / observed_count
            score += min(0.20, max(0.08, fail_ratio * 0.25))
            reasons.append(f"{failed_count} correlated failed transactions")

        candidates.append({
            "event": event,
            "score": round(min(0.95, max(0.10, score)), 2),
            "reasons": reasons,
        })
    return sorted(candidates, key=lambda item: item["score"], reverse=True)
