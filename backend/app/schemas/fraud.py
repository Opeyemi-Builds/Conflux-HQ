import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FraudPriority = Literal["critical", "high", "medium", "low"]
FraudStatus = Literal["open", "under_review", "escalated", "closed_resolved", "closed_false_positive"]
FraudType = Literal[
    "otp_request",
    "fake_bank_agent",
    "phishing_link",
    "sim_swap_indicator",
    "unauthorized_transfer",
    "account_takeover_claim",
    "other_fraud",
]


class FraudCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    complaint_id: uuid.UUID
    fraud_type: FraudType
    priority: FraudPriority
    status: FraudStatus
    indicators: list[str]
    repeat_count: int
    assigned_to: str | None
    text_masked: str
    created_at: datetime
    updated_at: datetime


class FraudCaseList(BaseModel):
    items: list[FraudCaseRead]
    total: int


class FraudCasePatch(BaseModel):
    status: FraudStatus | None = None
    assigned_to: str | None = Field(default=None, max_length=64)

    def has_changes(self) -> bool:
        return bool(self.model_fields_set)
