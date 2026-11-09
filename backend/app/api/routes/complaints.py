import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from pydantic import AwareDatetime

from app.api.deps import AuthUser, DbSession, Operator
from app.models import Complaint
from app.models.enums import Channel, IssueType
from app.schemas.complaint import (
    BulkResult, ComplaintBulkCreate, ComplaintClassification, ComplaintCreate, ComplaintRead,
)
from app.services import complaint_service
from app.services.audit import log_event
from app.ai.classifier import classify as ai_classify_complaint_text

router = APIRouter(prefix="/complaints", tags=["complaints"])


def _own(db, complaint_id: uuid.UUID, bank_id: uuid.UUID) -> Complaint:
    complaint = db.get(Complaint, complaint_id)
    if not complaint or complaint.bank_id != bank_id:  # other banks' data is simply "not found"
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Complaint not found")
    return complaint


@router.post("", response_model=ComplaintRead, status_code=status.HTTP_201_CREATED)
def create_complaint(payload: ComplaintCreate, user: Operator, db: DbSession):
    return complaint_service.create_complaint(db, user.bank_id, payload)


@router.post("/bulk", response_model=BulkResult, status_code=status.HTTP_201_CREATED)
def create_complaints_bulk(payload: ComplaintBulkCreate, user: Operator, db: DbSession):
    return BulkResult(created=complaint_service.create_complaints_bulk(db, user.bank_id, payload.complaints))


@router.get("", response_model=list[ComplaintRead])
def list_complaints(
    user: AuthUser,
    db: DbSession,
    channel: Channel | None = None,
    issue_type: IssueType | None = None,
    unclassified: bool = False,
    since: AwareDatetime | None = None,
    until: AwareDatetime | None = None,
    region: str | None = Query(None, max_length=64),
    is_fraud: bool | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    if since and until and since >= until:
        raise HTTPException(422, "since must be earlier than until")
    q = select(Complaint).where(Complaint.bank_id == user.bank_id).order_by(Complaint.occurred_at.desc(), Complaint.id)
    if region is not None:
        q = q.where(Complaint.region == region)
    if is_fraud is not None:
        q = q.where(Complaint.is_fraud == is_fraud)
    if channel:
        q = q.where(Complaint.channel == channel)
    if issue_type:
        q = q.where(Complaint.issue_type == issue_type)
    if unclassified:
        q = q.where(Complaint.issue_type.is_(None))
    if since:
        q = q.where(Complaint.occurred_at >= since)
    if until:
        q = q.where(Complaint.occurred_at < until)
    return db.execute(q.limit(limit).offset(offset)).scalars().all()


@router.get("/{complaint_id}", response_model=ComplaintRead)
def get_complaint(complaint_id: uuid.UUID, user: AuthUser, db: DbSession):
    return _own(db, complaint_id, user.bank_id)


@router.patch("/{complaint_id}/classification", response_model=ComplaintRead)
def classify_complaint(complaint_id: uuid.UUID, payload: ComplaintClassification, user: Operator, db: DbSession):
    return complaint_service.apply_classification(db, _own(db, complaint_id, user.bank_id), payload)


@router.post("/{complaint_id}/classify", response_model=ComplaintRead)
def ai_classify_complaint(complaint_id: uuid.UUID, user: Operator, db: DbSession):
    complaint = _own(db, complaint_id, user.bank_id)
    result, source = ai_classify_complaint_text(complaint.text, complaint.channel.value)
    runtime = getattr(result, "_runtime", {})
    classified = complaint_service.apply_classification(db, complaint, ComplaintClassification(
        issue_type=result.issue_type.value if hasattr(result.issue_type, "value") else result.issue_type,
        severity=result.severity, sentiment=result.sentiment, language=result.language,
        summary=result.short_summary, mentioned_amount=result.mentioned_amount,
        mentioned_time=result.mentioned_time, confidence=result.confidence,
        is_fraud=result.is_fraud, payment_category=result.payment_category,
        explanation=result.explanation, evidence_phrases=result.evidence_phrases))
    log_event(db, bank_id=user.bank_id, actor=str(user.id), action="complaint_classified",
              entity_type="complaint", entity_id=str(complaint.id),
              details={"issue_type": classified.issue_type.value, "source": source,
                       **{key: value for key, value in runtime.items() if key != "source"}})
    db.commit()
    return classified
