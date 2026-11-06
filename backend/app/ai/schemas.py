from typing import Literal
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    source: Literal["complaints", "transactions", "system_events", "baseline"]
    detail: str


class CandidateCause(BaseModel):
    cause: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence]


class Findings(BaseModel):
    headline: str
    candidate_causes: list[CandidateCause]
    affected_channels: list[str]
    affected_switch: str | None = None
    matched_transactions: int = 0
    propose_reversal_request: bool = False
    recommended_action: str


class ClassificationResult(BaseModel):
    issue_type: Literal["failed_transfer", "double_debit", "card_atm", "pos", "fees", "loan", "app_login", "fraud_scam", "other"]
    severity: Literal["low", "medium", "high", "critical"]
    sentiment: Literal["negative", "neutral", "positive"]
    language: Literal["english", "pidgin", "yoruba_mix", "hausa_mix", "igbo_mix", "other"]
    mentioned_amount: float | None = Field(default=None, ge=0)
    mentioned_time: str | None = None
    is_fraud: bool = False
    short_summary: str = Field(max_length=500)
    confidence: float = Field(ge=0, le=1)
