"""Deterministic evidence used before an LLM is allowed to explain an incident."""
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Complaint, Incident, SystemEvent, Transaction
from app.models.enums import TxnStatus


def build_evidence(db: Session, bank_id, incident: Incident) -> dict:
    incident_complaints = db.execute(
        select(Complaint).where(Complaint.bank_id == bank_id, Complaint.incident_id == incident.id)
    ).scalars().all()

    channels = {channel.value: sum(1 for x in incident_complaints if x.channel == channel)
                for channel in {x.channel for x in incident_complaints}}

    start = incident.started_at
    end = start + timedelta(minutes=60)
    transactions = db.execute(
        select(Transaction).where(Transaction.bank_id == bank_id,
                                  Transaction.occurred_at >= start - timedelta(hours=1),
                                  Transaction.occurred_at <= end)
    ).scalars().all()
    failed = [t for t in transactions if t.status == TxnStatus.FAILED]

    processors = sorted({t.processor for t in transactions if t.processor})
    tx_channels = sorted({t.txn_channel.value for t in failed})
    failed_by_processor = {
        processor: sum(1 for t in failed if t.processor == processor)
        for processor in processors
    }

    events = db.execute(
        select(SystemEvent).where(SystemEvent.bank_id == bank_id,
                                  SystemEvent.starts_at >= start - timedelta(hours=2),
                                  SystemEvent.starts_at <= end)
        .order_by(SystemEvent.starts_at)
    ).scalars().all()

    return {
        "incident": {
            "issue_type": incident.issue_type.value,
            "started_at": start.isoformat(),
            "complaint_count": incident.complaint_count,
            "baseline": incident.baseline,
            "growth_rate": incident.growth_rate,
        },
        "complaints": {"count": len(incident_complaints), "channels": channels},
        "transactions": {
            "observed": len(transactions), "failed": len(failed),
            "channels": tx_channels, "failed_by_processor": failed_by_processor,
        },
        "events": [
            {"type": e.event_type.value, "component": e.component, "version": e.version,
             "description": e.description, "starts_at": e.starts_at.isoformat()}
            for e in events
        ],
    }


def rank_events(evidence: dict) -> list[dict]:
    incident_time = evidence["incident"]["started_at"]
    candidates = []
    for event in evidence["events"]:
        candidates.append({"event": event, "score": 0.7 if event["type"] == "release" else 0.4})
    return sorted(candidates, key=lambda item: item["score"], reverse=True)
