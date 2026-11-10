"""Pydantic schemas for bank complaint ingestion."""
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class ComplaintIngestIn(BaseModel):
    """Payload sent by bank support systems (CRM/Call Center/In-App).
    
    extra='forbid' prevents clients from injecting bank_id, received_at,
    or internal classification overrides.
    """
    model_config = ConfigDict(extra="forbid")

    source_system: str = Field(min_length=2, max_length=32, description="Identifier of the origin system, e.g. zendesk_sim")
    external_id: str = Field(min_length=1, max_length=128, description="Unique ticket/case ID in the source system")
    channel: str = Field(description="Support channel: call_center, call, in_app, email, or branch")
    occurred_at: AwareDatetime = Field(description="Timezone-aware timestamp when the customer reported the issue")
    text: str = Field(min_length=1, max_length=5000, description="Customer complaint text")
    customer_ref: str | None = Field(default=None, max_length=128, description="CRM customer ID or phone (pseudonymized upon receipt)")
    payment_reference: str | None = Field(default=None, min_length=4, max_length=64, description="Transaction or transfer reference (e.g. TRF-...)")
    amount: str | None = Field(default=None, description="Decimal string representing monetary amount (e.g. '25000.02')")
    currency: str | None = Field(default=None, min_length=3, max_length=3, description="ISO 4217 currency code, e.g. NGN")
    region: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, max_length=32)
    synthetic: bool = Field(default=True, description="Flag indicating synthetic/sandbox fixture data")

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, v: datetime) -> datetime:
        now = datetime.now(timezone.utc)
        if v.astimezone(timezone.utc) > now + timedelta(minutes=5):
            raise ValueError("occurred_at cannot be more than 5 minutes in the future")
        return v

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if v_clean in ("call_center", "call"):
            return "call"
        if v_clean in ("in_app", "email", "branch"):
            return v_clean
        if v_clean in ("x", "twitter", "instagram", "facebook"):
            raise ValueError("Social media events must be delivered to /api/v1/social/events")
        raise ValueError(f"Unsupported channel '{v}'. Allowed: call_center, call, in_app, email, branch")

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Complaint text must not be empty or whitespace only")
        # Disallow control characters other than newline, tab, carriage return
        if re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", cleaned):
            raise ValueError("Complaint text contains invalid control characters")
        return cleaned

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v_str = str(v).strip()
        if not re.match(r"^\d{1,12}(\.\d{1,2})?$", v_str):
            raise ValueError("Amount must be a decimal string with up to 2 decimal places (e.g. '25000.02')")
        return v_str

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v_clean = v.strip().upper()
        if v_clean not in {"NGN", "USD", "GBP", "EUR"}:
            raise ValueError(f"Currency '{v}' is not supported. Allowed: NGN, USD, GBP, EUR")
        return v_clean

    @field_validator("payment_reference")
    @classmethod
    def validate_payment_reference(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v_clean = v.strip()
        if not re.match(r"^[A-Za-z0-9._:-]{4,64}$", v_clean):
            raise ValueError("Payment reference must contain 4-64 alphanumeric characters or ._:-")
        return v_clean

    @model_validator(mode="after")
    def validate_amount_and_currency(self):
        if self.amount is not None and self.currency is None:
            raise ValueError("Currency is required when amount is provided")
        if self.currency is not None and self.amount is None:
            raise ValueError("Amount is required when currency is provided")
        return self


class ComplaintIngestResponse(BaseModel):
    """Response returned upon durable acceptance (202) or idempotent replay (200)."""
    complaint_id: uuid.UUID
    receipt_id: uuid.UUID
    processing_status: str  # 'queued', 'processing', 'classified', 'failed'
    duplicate: bool
    received_at: datetime


class ConnectorCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    source_system: str = Field(min_length=2, max_length=32)
    synthetic: bool = True


class ConnectorCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    source_system: str
    key_prefix: str
    token: str  # Returned ONCE at creation
    created_at: datetime


class ConnectorRead(BaseModel):
    id: uuid.UUID
    name: str
    source_system: str
    key_prefix: str
    status: str
    synthetic: bool
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ComplaintReceiptRead(BaseModel):
    id: uuid.UUID
    bank_id: uuid.UUID
    connector_id: uuid.UUID
    complaint_id: uuid.UUID
    source_system: str
    external_id: str
    payment_reference: str | None
    amount: Decimal | None
    currency: str | None
    occurred_at: datetime
    received_at: datetime
    synthetic: bool

