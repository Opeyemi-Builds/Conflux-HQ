import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession, Operator
from app.schemas.reconciliation import (
    MatchCandidate, PaymentExceptionCreate, PaymentExceptionRead, PaymentExceptionUpdate,
    ProposalCreate, ProposalDecision, ProposalRead, TransactionMatchResponse,
)
from app.db.base import utcnow
from app.models import Complaint, PaymentException, PaymentProposal, Transaction
from app.models.enums import ReconciliationStatus
from app.services.audit import log_event
from app.services.transaction_matching import create_exception_from_complaint, find_transaction_matches

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


@router.post("/exceptions/{exception_id}/proposals", response_model=ProposalRead, status_code=201)
def propose_action(exception_id: uuid.UUID, payload: ProposalCreate, user: Operator, db: DbSession):
    case = db.get(PaymentException, exception_id)
    if case is None or case.bank_id != user.bank_id:
        raise HTTPException(404, "Reconciliation case not found")
    if case.status in {ReconciliationStatus.RESOLVED, ReconciliationStatus.REJECTED}:
        raise HTTPException(409, "Case is closed")
    if case.amount is None or payload.amount > case.amount:
        raise HTTPException(422, "Proposal must not exceed the documented case amount")
    existing = db.scalar(select(PaymentProposal).where(
        PaymentProposal.bank_id == user.bank_id, PaymentProposal.exception_id == case.id,
        PaymentProposal.status.in_(["pending", "approved"]),
    ))
    if existing:
        raise HTTPException(409, "An active financial proposal already exists")
    proposal = PaymentProposal(bank_id=user.bank_id, exception_id=case.id,
        kind=payload.kind, amount=payload.amount, currency=case.currency,
        reason=payload.reason, proposed_by=str(user.id))
    db.add(proposal)
    db.flush()
    case.approval_required = True
    case.status = ReconciliationStatus.APPROVAL_REQUIRED
    log_event(db, bank_id=user.bank_id, actor=str(user.id), action="financial_proposal_created",
        entity_type="payment_proposal", entity_id=str(proposal.id),
        details={"kind": proposal.kind, "execution_enabled": False})
    db.commit()
    db.refresh(proposal)
    return proposal


@router.get("/exceptions/{exception_id}/proposals", response_model=list[ProposalRead])
def list_proposals(exception_id: uuid.UUID, user: Operator, db: DbSession):
    case = db.get(PaymentException, exception_id)
    if case is None or case.bank_id != user.bank_id:
        raise HTTPException(404, "Reconciliation case not found")
    return db.scalars(select(PaymentProposal).where(
        PaymentProposal.bank_id == user.bank_id, PaymentProposal.exception_id == case.id
    ).order_by(PaymentProposal.created_at.desc())).all()


@router.post("/proposals/{proposal_id}/decision", response_model=ProposalRead)
def decide_proposal(proposal_id: uuid.UUID, payload: ProposalDecision, user: AdminUser, db: DbSession):
    proposal = db.scalar(select(PaymentProposal).where(
        PaymentProposal.id == proposal_id, PaymentProposal.bank_id == user.bank_id
    ).with_for_update())
    if proposal is None:
        raise HTTPException(404, "Proposal not found")
    if proposal.status != "pending":
        raise HTTPException(409, "Proposal has already been decided")
    if proposal.proposed_by == str(user.id):
        raise HTTPException(403, "A different bank administrator must review this proposal")
    proposal.status = payload.decision
    proposal.decided_by = str(user.id)
    proposal.decided_at = utcnow()
    log_event(db, bank_id=user.bank_id, actor=str(user.id), action="financial_proposal_decided",
        entity_type="payment_proposal", entity_id=str(proposal.id),
        details={"decision": payload.decision, "execution_enabled": False})
    # Approval records intent only. Never enqueue a financial execution job or resolve the case.
    db.commit()
    db.refresh(proposal)
    return proposal


@router.get("/summary")
def reconciliation_summary(user: Operator, db: DbSession):
    from app.services.reconciliation_reporting import summary

    return summary(db, user.bank_id)


@router.get("/exceptions", response_model=list[PaymentExceptionRead])
def list_exceptions(
    user: Operator,
    db: DbSession,
    status_filter: ReconciliationStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = select(PaymentException).where(PaymentException.bank_id == user.bank_id)
    if status_filter:
        query = query.where(PaymentException.status == status_filter)
    query = query.order_by(PaymentException.priority.desc(), PaymentException.created_at.desc())
    return db.scalars(query.limit(limit).offset(offset)).all()


@router.post("/exceptions", response_model=PaymentExceptionRead, status_code=status.HTTP_201_CREATED)
def create_exception(payload: PaymentExceptionCreate, user: Operator, db: DbSession):
    if payload.complaint_id:
        complaint = db.get(Complaint, payload.complaint_id)
        if complaint is None or complaint.bank_id != user.bank_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Complaint not found")
    if payload.transaction_id:
        transaction = db.get(Transaction, payload.transaction_id)
        if transaction is None or transaction.bank_id != user.bank_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    exception = PaymentException(bank_id=user.bank_id, **payload.model_dump())
    db.add(exception)
    db.commit()
    db.refresh(exception)
    return exception


@router.post("/complaints/{complaint_id}/match", response_model=TransactionMatchResponse)
def match_complaint(complaint_id: uuid.UUID, user: Operator, db: DbSession):
    complaint = db.get(Complaint, complaint_id)
    if complaint is None or complaint.bank_id != user.bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Complaint not found")
    candidates = find_transaction_matches(db, complaint)
    selected = candidates[0] if candidates and candidates[0][1] >= Decimal("0.55") else None
    if selected and len(candidates) > 1 and candidates[1][1] == selected[1]:
        selected = None
    return TransactionMatchResponse(
        complaint_id=complaint.id,
        candidates=[MatchCandidate(transaction_id=t.id, reference=t.reference, confidence=score, reasons=reasons) for t, score, reasons in candidates],
        selected_transaction_id=selected[0].id if selected else None,
        match_confidence=selected[1] if selected else None,
        reason="confident_match" if selected else "no_confident_match",
    )


@router.post("/complaints/{complaint_id}/create", response_model=PaymentExceptionRead, status_code=status.HTTP_201_CREATED)
def create_exception_from_complaint_route(complaint_id: uuid.UUID, user: Operator, db: DbSession):
    complaint = db.get(Complaint, complaint_id)
    if complaint is None or complaint.bank_id != user.bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Complaint not found")
    existing = db.scalar(select(PaymentException).where(PaymentException.bank_id == user.bank_id, PaymentException.complaint_id == complaint.id))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "A reconciliation case already exists for this complaint")
    exception = create_exception_from_complaint(db, complaint)
    db.commit()
    db.refresh(exception)
    return exception


@router.patch("/exceptions/{exception_id}", response_model=PaymentExceptionRead)
def update_exception(exception_id: uuid.UUID, payload: PaymentExceptionUpdate, user: Operator, db: DbSession):
    exception = db.get(PaymentException, exception_id)
    if exception is None or exception.bank_id != user.bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reconciliation case not found")
    changes = payload.model_dump(exclude_unset=True)
    for field in ("status", "settlement_status", "priority", "approval_required"):
        if field in changes and changes[field] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{field} cannot be null")
    for field, value in changes.items():
        setattr(exception, field, value)
    if exception.status == ReconciliationStatus.RESOLVED:
        exception.resolved_at = exception.resolved_at or utcnow()
    else:
        exception.resolved_at = None
    log_event(db, bank_id=user.bank_id, actor=str(user.id), action="reconciliation_updated",
              entity_type="payment_exception", entity_id=str(exception.id),
              details={"fields": sorted(changes), "status": exception.status.value})
    db.commit()
    db.refresh(exception)
    return exception
