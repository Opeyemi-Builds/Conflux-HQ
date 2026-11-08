"""Match customer complaints to bank transactions without moving money."""
import uuid
from datetime import timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Complaint, PaymentException, Transaction
from app.models.enums import ExceptionType, ReconciliationStatus, SettlementStatus, TxnStatus
from app.db.base import utcnow


_CHANNEL_MAP = {
    "app": "app",
    "ussd": "ussd",
    "pos": "pos",
    "atm": "atm",
    "web": "web",
}


def _candidate_score(complaint: Complaint, transaction: Transaction) -> tuple[Decimal, list[str]]:
    score = Decimal("0")
    reasons: list[str] = []
    if complaint.mentioned_amount is not None and transaction.amount == complaint.mentioned_amount:
        score += Decimal("0.55")
        reasons.append("amount_matches")
    if complaint.occurred_at and transaction.occurred_at:
        delta = abs((transaction.occurred_at - complaint.occurred_at).total_seconds())
        if delta <= 15 * 60:
            score += Decimal("0.30")
            reasons.append("within_15_minutes")
        elif delta <= 60 * 60:
            score += Decimal("0.15")
            reasons.append("within_1_hour")
    channel = _CHANNEL_MAP.get(complaint.channel.value)
    if channel and transaction.txn_channel.value == channel:
        score += Decimal("0.15")
        reasons.append("channel_matches")
    return min(score, Decimal("1.000")), reasons


def find_transaction_matches(
    db: Session,
    complaint: Complaint,
    *,
    limit: int = 10,
) -> list[tuple[Transaction, Decimal, list[str]]]:
    """Return ranked same-bank transaction candidates using explainable evidence."""
    start = complaint.occurred_at - timedelta(hours=2)
    end = complaint.occurred_at + timedelta(hours=2)
    transactions = db.scalars(
        select(Transaction).where(
            Transaction.bank_id == complaint.bank_id,
            Transaction.occurred_at >= start,
            Transaction.occurred_at <= end,
        )
    ).all()
    ranked = [(txn, *_candidate_score(complaint, txn)) for txn in transactions]
    ranked.sort(key=lambda item: (item[1], item[0].occurred_at), reverse=True)
    return ranked[:limit]


def exception_type_for(complaint: Complaint, transaction: Transaction | None) -> ExceptionType:
    if complaint.issue_type and complaint.issue_type.value == "double_debit":
        return ExceptionType.DUPLICATE_DEBIT
    if complaint.is_fraud:
        return ExceptionType.FRAUD_DISPUTE
    if transaction and transaction.status == TxnStatus.FAILED:
        return ExceptionType.DEBITED_NOT_CREDITED if complaint.mentioned_amount else ExceptionType.FAILED_TRANSFER
    if transaction and transaction.status == TxnStatus.PENDING:
        return ExceptionType.DELAYED_SETTLEMENT
    if transaction and transaction.status == TxnStatus.REVERSED:
        return ExceptionType.REVERSED_NOT_REFUNDED
    return ExceptionType.UNKNOWN_SETTLEMENT


def create_exception_from_complaint(
    db: Session,
    complaint: Complaint,
    *,
    min_confidence: Decimal = Decimal("0.55"),
) -> PaymentException:
    candidates = find_transaction_matches(db, complaint)
    selected = candidates[0] if candidates and candidates[0][1] >= min_confidence else None
    transaction = selected[0] if selected else None
    confidence = selected[1] if selected else None
    reasons = selected[2] if selected else ["no_confident_transaction_match"]
    exception = PaymentException(
        bank_id=complaint.bank_id,
        complaint_id=complaint.id,
        transaction_id=transaction.id if transaction else None,
        exception_type=exception_type_for(complaint, transaction),
        status=(ReconciliationStatus.TRANSACTION_MATCHED if transaction else ReconciliationStatus.REPORTED),
        settlement_status=(
            SettlementStatus.FAILED if transaction and transaction.status == TxnStatus.FAILED
            else SettlementStatus.PENDING if transaction and transaction.status == TxnStatus.PENDING
            else SettlementStatus.REVERSED if transaction and transaction.status == TxnStatus.REVERSED
            else SettlementStatus.UNKNOWN
        ),
        amount=transaction.amount if transaction else complaint.mentioned_amount,
        transaction_reference=transaction.reference if transaction else None,
        processor=transaction.processor if transaction else None,
        payment_channel=transaction.txn_channel.value if transaction else complaint.channel.value,
        customer_ref_hash=complaint.customer_ref,
        match_confidence=confidence,
        evidence_summary="; ".join(reasons),
        priority=80 if complaint.is_fraud else 60 if transaction else 40,
        approval_required=bool(transaction and transaction.status in {TxnStatus.FAILED, TxnStatus.REVERSED}),
    )
    db.add(exception)
    db.flush()
    return exception
