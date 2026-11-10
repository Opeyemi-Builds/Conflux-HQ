"""Normalized, non-authoritative evidence contracts for the XtraDot sandbox."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


ProviderStatus = str


class TransferObservation(BaseModel):
    """A provider observation; it is not proof of another bank's ledger credit."""

    model_config = ConfigDict(frozen=True)

    provider: Literal["xtradot"] = "xtradot"
    environment: Literal["sandbox"] = "sandbox"
    payment_reference: str
    source_status: ProviderStatus = Field(min_length=1, max_length=64)
    amount: str | None = None
    currency: str | None = None
    occurred_at: datetime | None = None
    received_at: datetime
    safe_request_id: str | None = None
    evidence_basis: Literal[
        "sandbox_provider_response",
        "sandbox_provider_not_found",
        "transport_timeout",
    ]
    freshness: Literal["fresh", "stale", "unknown", "missing"] = "unknown"
    requery_required: bool = False

    @field_validator("amount")
    @classmethod
    def amount_is_decimal_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            amount = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("amount must be a decimal string") from exc
        if not amount.is_finite() or amount < 0:
            raise ValueError("amount must be a finite non-negative decimal")
        return value


class PaymentEvidenceEvent(BaseModel):
    """Canonical provider event, before persistence in the shared evidence store."""

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    bank_id: uuid.UUID
    provider: Literal["xtradot"] = "xtradot"
    environment: Literal["sandbox"] = "sandbox"
    provider_event_id: str = Field(min_length=1, max_length=160)
    payment_reference: str = Field(min_length=1, max_length=160)
    event_type: str = Field(min_length=1, max_length=64)
    source_status: ProviderStatus = Field(min_length=1, max_length=64)
    amount: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    occurred_at: datetime | None = None
    received_at: datetime
    safe_request_id: str | None = Field(default=None, max_length=160)
    evidence_basis: Literal["sandbox_signed_webhook"] = "sandbox_signed_webhook"
    freshness: Literal["fresh", "stale", "unknown", "missing"] = "unknown"

    @field_validator("amount")
    @classmethod
    def amount_is_decimal_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            amount = Decimal(value)
        except Exception as exc:
            raise ValueError("amount must be a decimal string") from exc
        if not amount.is_finite() or amount < 0:
            raise ValueError("amount must be a finite non-negative decimal")
        return value
