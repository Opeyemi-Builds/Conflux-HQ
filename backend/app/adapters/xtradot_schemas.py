"""Normalized, non-authoritative evidence contracts for the XtraDot sandbox."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from urllib.parse import urlsplit
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
    session_id: str | None = Field(default=None, max_length=160)
    nip_response_code: str | None = Field(default=None, max_length=16)
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


# Hosts allowed to appear in a report `download_url`. Anything else is
# dropped to None at normalization — evidence is never fetched automatically.
REPORT_DOWNLOAD_HOSTS = frozenset({"team10.xtradot.co"})


class ReportEvidenceEvent(BaseModel):
    """Canonical provider report event, before persistence in the shared evidence store.

    Reports are observations only — never ledger proof, never a transfer trigger.
    Updates for the same `report_id` arrive under a new `provider_event_id`
    (snapshot semantics); readers supersede by `report_id` at read time.
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    bank_id: uuid.UUID
    provider: Literal["xtradot"] = "xtradot"
    environment: Literal["sandbox"] = "sandbox"
    provider_event_id: str = Field(min_length=1, max_length=160)
    event_type: str = Field(min_length=1, max_length=64)
    report_id: str = Field(min_length=1, max_length=160)
    report_type: str = Field(min_length=1, max_length=64)
    source_status: ProviderStatus = Field(min_length=1, max_length=64)
    amount: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    period_from: datetime | None = None
    period_to: datetime | None = None
    payment_references: list[str] | None = Field(default=None, max_length=500)
    download_url: str | None = Field(default=None, max_length=2048)
    checksum: str | None = Field(default=None, max_length=256)
    occurred_at: datetime | None = None
    received_at: datetime
    evidence_basis: Literal["sandbox_signed_webhook"] = "sandbox_signed_webhook"
    freshness: Literal["fresh", "stale", "unknown", "missing"] = "unknown"

    @field_validator("event_type")
    @classmethod
    def event_type_is_report(cls, value: str) -> str:
        if not value.startswith("report."):
            raise ValueError("event_type must start with 'report.'")
        return value

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

    @field_validator("payment_references")
    @classmethod
    def references_are_bounded(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [entry.strip() for entry in value if isinstance(entry, str) and entry.strip()]
        for entry in cleaned:
            if len(entry) > 160:
                raise ValueError("payment references must be at most 160 characters")
        if not cleaned:
            return None
        return cleaned

    @field_validator("download_url")
    @classmethod
    def download_url_is_allowlisted(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value.strip())
        if parsed.scheme != "https" or parsed.hostname not in REPORT_DOWNLOAD_HOSTS:
            raise ValueError("download_url host is not allow-listed")
        return value
