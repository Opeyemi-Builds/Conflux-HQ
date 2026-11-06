import uuid

from sqlalchemy.orm import Session

from app.core.privacy import mask_pii, pseudonymise
from app.db.base import utcnow
from app.models import Complaint
from app.schemas.complaint import ComplaintClassification, ComplaintCreate


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


def create_complaint(db: Session, bank_id: uuid.UUID, data: ComplaintCreate) -> Complaint:
    complaint = build_complaint(bank_id, data)
    db.add(complaint)
    db.commit()
    return complaint


def create_complaints_bulk(db: Session, bank_id: uuid.UUID, items: list[ComplaintCreate]) -> int:
    db.add_all([build_complaint(bank_id, item) for item in items])
    db.commit()
    return len(items)


def apply_classification(db: Session, complaint: Complaint, result: ComplaintClassification) -> Complaint:
    complaint.issue_type = result.issue_type
    complaint.severity = result.severity
    complaint.sentiment = result.sentiment
    complaint.summary = result.summary
    complaint.is_fraud = result.is_fraud
    complaint.mentioned_amount = result.mentioned_amount
    if result.language:
        complaint.language = result.language
    complaint.classified_at = utcnow()
    db.commit()
    return complaint
