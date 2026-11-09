import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import case, func, select

from app.api.deps import AuthUser, DbSession, Operator
from app.db.base import utcnow
from app.models import Complaint, FraudCase, Profile
from app.schemas.fraud import FraudCaseList, FraudCasePatch, FraudCaseRead
from app.services.audit import log_event

router = APIRouter(prefix="/fraud/cases", tags=["fraud queue"])
PriorityFilter = Annotated[str | None, Query(pattern="^(critical|high|medium|low)$")]
StatusFilter = Annotated[
    str | None,
    Query(pattern="^(open|under_review|escalated|closed_resolved|closed_false_positive)$"),
]
FraudTypeFilter = Annotated[
    str | None,
    Query(pattern="^(otp_request|fake_bank_agent|phishing_link|sim_swap_indicator|unauthorized_transfer|account_takeover_claim|other_fraud)$"),
]


def _read(case: FraudCase, complaint: Complaint) -> FraudCaseRead:
    return FraudCaseRead(
        id=case.id,
        complaint_id=case.complaint_id,
        fraud_type=case.fraud_type,
        priority=case.priority,
        status=case.status,
        indicators=case.indicators or [],
        repeat_count=case.repeat_count,
        assigned_to=case.assigned_to,
        text_masked=complaint.text,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def _owned_case(db: DbSession, case_id: uuid.UUID, bank_id: uuid.UUID) -> tuple[FraudCase, Complaint]:
    result = db.execute(
        select(FraudCase, Complaint)
        .join(Complaint, Complaint.id == FraudCase.complaint_id)
        .where(
            FraudCase.id == case_id,
            FraudCase.bank_id == bank_id,
            Complaint.bank_id == bank_id,
        )
    ).first()
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fraud case not found")
    return result


@router.get("", response_model=FraudCaseList)
def list_fraud_cases(
    user: AuthUser,
    db: DbSession,
    status_filter: str | None = Query(
        None, alias="status", pattern="^(open|under_review|escalated|closed_resolved|closed_false_positive)$"
    ),
    priority: PriorityFilter = None,
    fraud_type: FraudTypeFilter = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conditions = [FraudCase.bank_id == user.bank_id]
    if status_filter:
        conditions.append(FraudCase.status == status_filter)
    if priority:
        conditions.append(FraudCase.priority == priority)
    if fraud_type:
        conditions.append(FraudCase.fraud_type == fraud_type)

    total = db.scalar(select(func.count()).select_from(FraudCase).where(*conditions)) or 0
    order_priority = case(
        (FraudCase.priority == "critical", 0),
        (FraudCase.priority == "high", 1),
        (FraudCase.priority == "medium", 2),
        else_=3,
    )
    rows = db.execute(
        select(FraudCase, Complaint)
        .join(Complaint, Complaint.id == FraudCase.complaint_id)
        .where(*conditions, Complaint.bank_id == user.bank_id)
        .order_by(order_priority, FraudCase.created_at.desc(), FraudCase.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return FraudCaseList(items=[_read(fraud_case, complaint) for fraud_case, complaint in rows], total=total)


@router.get("/{case_id}", response_model=FraudCaseRead)
def get_fraud_case(case_id: uuid.UUID, user: AuthUser, db: DbSession):
    fraud_case, complaint = _owned_case(db, case_id, user.bank_id)
    return _read(fraud_case, complaint)


@router.patch("/{case_id}", response_model=FraudCaseRead)
def patch_fraud_case(case_id: uuid.UUID, payload: FraudCasePatch, user: Operator, db: DbSession):
    if not payload.has_changes():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "At least one field must be provided")
    fraud_case, complaint = _owned_case(db, case_id, user.bank_id)
    changed = {}
    if "status" in payload.model_fields_set and payload.status is not None:
        if fraud_case.status != payload.status:
            changed["status"] = {"from": fraud_case.status, "to": payload.status}
            fraud_case.status = payload.status
    if "assigned_to" in payload.model_fields_set:
        if payload.assigned_to is not None:
            try:
                assigned_id = uuid.UUID(payload.assigned_to)
            except ValueError:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "assigned_to must be a staff UUID") from None
            profile = db.scalar(
                select(Profile).where(Profile.id == assigned_id, Profile.bank_id == user.bank_id)
            )
            if profile is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff member not found")
        else:
            assigned_id = None
        new_assignment = str(assigned_id) if assigned_id else None
        if fraud_case.assigned_to != new_assignment:
            changed["assigned_to"] = {"from": fraud_case.assigned_to, "to": new_assignment}
            fraud_case.assigned_to = new_assignment

    if changed:
        fraud_case.updated_at = utcnow()
        log_event(
            db,
            bank_id=user.bank_id,
            actor=str(user.id),
            action="fraud_case_status_changed" if "status" in changed else "fraud_case_assigned",
            entity_type="fraud_case",
            entity_id=str(fraud_case.id),
            details=changed,
        )
        db.commit()
        db.refresh(fraud_case)
    return _read(fraud_case, complaint)
