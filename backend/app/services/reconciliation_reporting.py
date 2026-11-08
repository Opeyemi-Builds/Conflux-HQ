"""Read-only reconciliation aggregates and chronologically ordered incident evidence."""
from collections import Counter
from datetime import timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models import Complaint, Incident, PaymentException, SystemEvent, Transaction
from app.models.enums import ReconciliationStatus


def summary(db, bank_id, incident_id=None):
    query = select(PaymentException).where(PaymentException.bank_id == bank_id)
    if incident_id is not None:
        query = query.join(Complaint, PaymentException.complaint_id == Complaint.id).where(
            Complaint.bank_id == bank_id, Complaint.incident_id == incident_id
        )
    cases = db.scalars(query).all()
    amounts = {}
    for case in cases:
        if case.amount is not None and case.status not in {ReconciliationStatus.RESOLVED, ReconciliationStatus.REJECTED}:
            amounts[case.currency] = amounts.get(case.currency, Decimal("0")) + case.amount
    return {
        "total_exceptions": len(cases),
        "by_status": dict(Counter(case.status.value for case in cases)),
        "by_type": dict(Counter(case.exception_type.value for case in cases)),
        "by_settlement_status": dict(Counter(case.settlement_status.value for case in cases)),
        "approval_required": sum(case.approval_required for case in cases),
        "reported_open_amount_by_currency": {currency: str(amount) for currency, amount in amounts.items()},
        "amount_note": "Reported case amounts, not verified losses; duplicate claims may exist.",
    }


def timeline(db, bank_id, incident: Incident):
    complaints = db.scalars(select(Complaint).where(
        Complaint.bank_id == bank_id, Complaint.incident_id == incident.id
    )).all()
    complaint_ids = [complaint.id for complaint in complaints]
    cases = db.scalars(select(PaymentException).where(
        PaymentException.bank_id == bank_id,
        PaymentException.complaint_id.in_(complaint_ids),
    )).all() if complaint_ids else []
    transaction_ids = {case.transaction_id for case in cases if case.transaction_id}
    transaction_ids.update(c.transaction_id for c in complaints if c.transaction_id)
    transactions = db.scalars(select(Transaction).where(
        Transaction.bank_id == bank_id, Transaction.id.in_(transaction_ids)
    )).all() if transaction_ids else []
    events = db.scalars(select(SystemEvent).where(
        SystemEvent.bank_id == bank_id,
        SystemEvent.starts_at >= incident.started_at - timedelta(hours=6),
        SystemEvent.starts_at <= incident.started_at + timedelta(hours=1),
    )).all()
    items = []
    for complaint in complaints:
        items.append({"at": complaint.occurred_at, "kind": "complaint", "id": str(complaint.id),
                      "channel": complaint.channel.value})
    for txn in transactions:
        items.append({"at": txn.occurred_at, "kind": "transaction", "id": str(txn.id),
                      "status": txn.status.value, "processor": txn.processor,
                      "association": "investigative_candidate"})
    for case in cases:
        items.append({"at": case.created_at, "kind": "reconciliation_case", "id": str(case.id),
                      "status": case.status.value, "settlement_status": case.settlement_status.value})
        if case.resolved_at:
            items.append({"at": case.resolved_at, "kind": "case_resolved", "id": str(case.id)})
    for event in events:
        items.append({"at": event.starts_at, "kind": "system_event", "id": str(event.id),
                      "component": event.component, "event_type": event.event_type.value,
                      "association": "time_correlated_not_proven_cause"})
    def timestamp(item):
        value = item["at"]
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return sorted(items, key=timestamp)
