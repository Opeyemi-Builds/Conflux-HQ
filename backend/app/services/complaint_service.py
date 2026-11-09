import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.privacy import mask_pii, pseudonymise
from app.db.base import utcnow
from app.models import Complaint
from app.models.enums import JobKind
from app.schemas.complaint import ComplaintClassification, ComplaintCreate
from app.services.spike_detection import bucket_start
from app.services.worker import enqueue_job
from app.services.fraud import route_classification_to_fraud


def build_complaint(bank_id: uuid.UUID, data: ComplaintCreate) -> Complaint:
    """Mask PII before anything is stored."""
    return Complaint(
        bank_id=bank_id,
        channel=data.channel,
        text=mask_pii(data.text),
        customer_ref=pseudonymise(data.customer_ref),
        region=data.region,
        language=data.language,
        occurred_at=data.occurred_at or utcnow(),
        issue_type=data.issue_type,
        classified_at=utcnow() if data.issue_type else None,
    )


def _enqueue_for_complaint(db: Session, bank_id: uuid.UUID, complaint: Complaint) -> None:
    if complaint.issue_type is None:
        enqueue_job(
            db,
            bank_id=bank_id,
            kind=JobKind.CLASSIFY_COMPLAINT,
            payload={"complaint_id": str(complaint.id)},
            idempotency_key=f"classify:{complaint.id}",
        )
    else:
        minutes = get_settings().spike_bucket_minutes
        b_start = bucket_start(complaint.occurred_at, minutes)
        detect_at = b_start + timedelta(minutes=minutes - 1, seconds=59)
        enqueue_job(
            db,
            bank_id=bank_id,
            kind=JobKind.DETECT_SPIKES,
            payload={"now": detect_at.isoformat()},
            idempotency_key=f"detect:{b_start.isoformat()}",
            reopen_completed=True,
        )


def create_complaint(db: Session, bank_id: uuid.UUID, data: ComplaintCreate) -> Complaint:
    complaint = build_complaint(bank_id, data)
    db.add(complaint)
    db.flush()
    _enqueue_for_complaint(db, bank_id, complaint)
    db.commit()
    return complaint


def create_complaints_bulk(db: Session, bank_id: uuid.UUID, items: list[ComplaintCreate]) -> int:
    rows = [build_complaint(bank_id, item) for item in items]
    db.add_all(rows)
    db.flush()
    for row in rows:
        _enqueue_for_complaint(db, bank_id, row)
    db.commit()
    return len(rows)


def apply_classification(db: Session, complaint: Complaint, result: ComplaintClassification) -> Complaint:
    complaint.issue_type = result.issue_type
    complaint.severity = result.severity
    complaint.sentiment = result.sentiment
    complaint.summary = result.summary
    complaint.is_fraud = result.is_fraud
    complaint.mentioned_amount = result.mentioned_amount
    complaint.mentioned_time = result.mentioned_time
    complaint.classification_confidence = result.confidence
    complaint.payment_category = result.payment_category
    complaint.classification_explanation = result.explanation
    complaint.evidence_phrases = result.evidence_phrases
    threshold = get_settings().classification_review_threshold
    if result.is_fraud:
        complaint.review_status = "needs_review"
        complaint.routing_queue = "fraud_security"
    elif result.confidence < threshold:
        complaint.review_status = "needs_review"
        complaint.routing_queue = "human_review"
    else:
        complaint.review_status = "auto"
        complaint.routing_queue = "standard"
    if result.language:
        complaint.language = result.language
    complaint.classified_at = utcnow()
    db.flush()
    route_classification_to_fraud(db, complaint, actor="classifier")
    db.commit()
    return complaint
