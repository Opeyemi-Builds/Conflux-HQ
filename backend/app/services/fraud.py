"""Persistence helpers for bank-scoped, human-reviewed fraud cases."""
from datetime import timedelta
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.fraud import FraudRouting, route_fraud
from app.db.base import utcnow
from app.models import Complaint, FraudCase
from app.services.audit import log_event


def ensure_fraud_case(
    db: Session,
    complaint: Complaint,
    routing: FraudRouting,
    *,
    actor: str,
) -> FraudCase | None:
    if not routing.routed or not routing.fraud_type or not routing.priority:
        return None

    existing = db.scalar(
        select(FraudCase).where(
            FraudCase.bank_id == complaint.bank_id,
            FraudCase.complaint_id == complaint.id,
        )
    )
    if existing is not None:
        return existing

    repeat_count = 1
    prior_cases: list[FraudCase] = []
    if complaint.customer_ref:
        prior_cases = db.scalars(
            select(FraudCase)
            .join(Complaint, Complaint.id == FraudCase.complaint_id)
            .where(
                FraudCase.bank_id == complaint.bank_id,
                Complaint.bank_id == complaint.bank_id,
                Complaint.customer_ref == complaint.customer_ref,
                FraudCase.created_at >= utcnow() - timedelta(hours=24),
            )
        ).all()
        repeat_count += len(prior_cases)

    fraud_case = FraudCase(
        bank_id=complaint.bank_id,
        complaint_id=complaint.id,
        fraud_type=routing.fraud_type,
        priority=routing.priority,
        indicators=list(routing.indicators),
        repeat_count=repeat_count,
    )
    db.add(fraud_case)
    db.flush()
    for prior in prior_cases:
        prior.repeat_count = repeat_count
    log_event(
        db,
        bank_id=complaint.bank_id,
        actor=actor,
        action="fraud_case_created",
        entity_type="fraud_case",
        entity_id=str(fraud_case.id),
        details={
            "complaint_id": str(complaint.id),
            "fraud_type": fraud_case.fraud_type,
            "priority": fraud_case.priority,
            "indicators": fraud_case.indicators,
            "repeat_count": repeat_count,
        },
    )
    return fraud_case


def route_classification_to_fraud(
    db: Session,
    complaint: Complaint,
    *,
    actor: str,
) -> FraudCase | None:
    from app.ai.fallback import rules_classify

    classification = rules_classify(complaint.text)
    classification.payment_category = complaint.payment_category or classification.payment_category
    classification.is_fraud = complaint.is_fraud or classification.is_fraud
    routing = route_fraud(classification, complaint.text)
    if routing.routed:
        complaint.routing_queue = "fraud_security"
        complaint.review_status = "needs_review"
    return ensure_fraud_case(db, complaint, routing, actor=actor)
