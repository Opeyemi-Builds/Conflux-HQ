from typing import Literal
from pydantic import BaseModel, Field

PaymentCategory = Literal[
    "debited_not_credited",
    "failed_transfer",
    "pending_transfer",
    "delayed_settlement",
    "reversed_not_refunded",
    "double_debit",
    "duplicate_payment",
    "card_atm_failure",
    "pos_failure",
    "processor_timeout",
    "switch_outage",
    "fees",
    "fraud_scam",
    "account_takeover",
    "unknown_payment_issue",
]


class Evidence(BaseModel):
    source: Literal["complaints", "transactions", "system_events", "baseline"]
    detail: str
    kind: Literal["fact", "inference", "recommendation"] = "fact"


class CandidateCause(BaseModel):
    cause: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list)
    kind: Literal["fact", "inference", "recommendation"] = "inference"


class Findings(BaseModel):
    headline: str
    candidate_causes: list[CandidateCause]
    affected_channels: list[str]
    affected_switch: str | None = None
    matched_transactions: int = 0
    propose_reversal_request: bool = False
    recommended_action: str
    likely_cause: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    supporting_evidence: list[Evidence] = Field(default_factory=list)
    contradicting_evidence: list[Evidence] = Field(default_factory=list)
    affected_systems: list[str] = Field(default_factory=list)
    recommended_owner: str | None = None
    recommended_next_step: str | None = None
    method: Literal["llm", "rules_fallback"] = "llm"


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
    payment_category: PaymentCategory | None = None
    explanation: str = Field(default="Classification based on complaint wording.", max_length=500)
    evidence_phrases: list[str] = Field(default_factory=list, max_length=10)
