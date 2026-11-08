import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExceptionType, ReconciliationStatus, SettlementStatus


class PaymentExceptionCreate(BaseModel):
    complaint_id: uuid.UUID | None = None
    transaction_id: uuid.UUID | None = None
    exception_type: ExceptionType
    settlement_status: SettlementStatus = SettlementStatus.UNKNOWN
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="NGN", min_length=3, max_length=3)
    transaction_reference: str | None = Field(default=None, max_length=64)
    processor: str | None = Field(default=None, max_length=64)
    payment_channel: str | None = Field(default=None, max_length=32)
    customer_ref_hash: str | None = Field(default=None, max_length=128)
    match_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    evidence_summary: str | None = Field(default=None, max_length=2000)
    priority: int = Field(default=0, ge=0, le=100)
    approval_required: bool = False


class PaymentExceptionUpdate(BaseModel):
    status: ReconciliationStatus | None = None
    settlement_status: SettlementStatus | None = None
    owner: str | None = Field(default=None, max_length=128)
    evidence_summary: str | None = Field(default=None, max_length=2000)
    priority: int | None = Field(default=None, ge=0, le=100)
    approval_required: bool | None = None


class PaymentExceptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bank_id: uuid.UUID
    complaint_id: uuid.UUID | None
    transaction_id: uuid.UUID | None
    exception_type: ExceptionType
    status: ReconciliationStatus
    settlement_status: SettlementStatus
    amount: Decimal | None
    currency: str
    transaction_reference: str | None
    processor: str | None
    payment_channel: str | None
    customer_ref_hash: str | None
    match_confidence: Decimal | None
    evidence_summary: str | None
    owner: str | None
    priority: int
    approval_required: bool
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class MatchCandidate(BaseModel):
    transaction_id: uuid.UUID
    reference: str
    confidence: Decimal = Field(ge=0, le=1)
    reasons: list[str]


class TransactionMatchResponse(BaseModel):
    complaint_id: uuid.UUID
    candidates: list[MatchCandidate]
    selected_transaction_id: uuid.UUID | None
    match_confidence: Decimal | None
    reason: str
