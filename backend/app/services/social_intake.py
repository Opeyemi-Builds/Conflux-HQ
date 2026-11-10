"""Social adapter contract and conservative demo analysis; no live scraping or AI calls."""
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AwareDatetime, BaseModel, Field, field_validator

Platform = Literal["x", "instagram", "facebook"]
Kind = Literal["name", "handle", "hashtag", "contextual"]


class AliasInput(BaseModel):
    value: str = Field(min_length=2, max_length=120)
    kind: Kind = "name"
    platform: Platform | None = None

    @field_validator("value")
    @classmethod
    def normalize(cls, value):
        value = " ".join(value.casefold().split())
        if len(value) < 2 or not any(c.isalnum() for c in value):
            raise ValueError("Alias must contain letters or numbers")
        return value


class AliasBatch(BaseModel):
    aliases: list[AliasInput] = Field(min_length=1, max_length=50)


class SocialEvent(BaseModel):
    synthetic: bool = False
    platform: Platform
    post_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_.:-]+$")
    text: str = Field(min_length=1, max_length=5000)
    occurred_at: AwareDatetime
    source_url: str | None = Field(default=None, max_length=500)
    author_ref: str | None = Field(default=None, max_length=160)
    region: str | None = Field(default=None, max_length=64)
    matching_rule_tags: list[str] = Field(default_factory=list, max_length=25)
    public_metrics: dict[str, int] = Field(default_factory=dict, max_length=20)

    @field_validator("source_url")
    @classmethod
    def public_url(cls, value):
        if value is None:
            return value
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or parsed.hostname not in {
            "x.com", "www.x.com", "twitter.com", "www.twitter.com",
            "instagram.com", "www.instagram.com", "facebook.com", "www.facebook.com"
        } or parsed.username or parsed.password or parsed.port not in (None, 443)
                or parsed.query or parsed.fragment):
            raise ValueError("Use an HTTPS social permalink without credentials, query or fragment")
        return value


CONTEXT = re.compile(r"\b(bank|banking|transfer|debit(?:ed)?|credit(?:ed)?|account|atm|pos|ussd|refund|money|payment|charged|transaction|otp|scam)\b", re.I)


def matches(text: str, value: str, kind: str) -> bool:
    value = value.casefold()
    if kind == "contextual" and value == "access" and re.search(r"\baccess\s+to\b", text, re.I):
        return False
    if kind == "handle":
        value = "@" + value.lstrip("@")
    elif kind == "hashtag":
        value = "#" + value.lstrip("#")
    found = re.search(r"(?<![\w@#])" + re.escape(value) + r"(?!\w)", text.casefold()) is not None
    return found and (kind != "contextual" or CONTEXT.search(text) is not None)


def analyze(text: str) -> dict:
    """Transparent keyword heuristic, NOT AI. Unclear posts stay unclassified."""
    t = text.casefold()
    rules = [
        ("fraud_scam", r"\b(scam|fraud|fake agent|fake bank agent|stolen|unauthori[sz]ed)\b"),
        ("double_debit", r"\b(double debit|debited(?: me)? twice|charged(?: me)? twice|duplicate debit)\b"),
        ("card_atm", r"\b(atm|card)\b"),
        ("pos", r"\bpos\b"),
        ("failed_transfer", r"\b(failed transfer|transfer failed|no credit|not received|did not receive|money don enter nowhere)\b"),
        ("app_login", r"\b(cannot log|can't log|login|sign in|app crash)"),
        ("fees", r"\b(fee|fees|service charge)\b"),
        ("loan", r"\bloan\b"),
    ]
    issue = next((issue for issue, pattern in rules if re.search(pattern, t)), None)
    if issue is None:
        return {"issue_type": None, "is_fraud": False}
    return {"issue_type": issue, "is_fraud": issue == "fraud_scam",
            "severity": "high" if issue in {"fraud_scam", "double_debit", "failed_transfer"} else "medium",
            "sentiment": None}


def reputation_signals(text: str, metrics: dict[str, int] | None = None) -> dict:
    """Return transparent, non-defamatory reputation-risk signals for triage."""
    value = text.casefold()
    flags: list[str] = []
    patterns = {
        "public_escalation": r"\b(tag|mention|thread|viral|trend|retweet|share)\b",
        "scam_allegation": r"\b(scam|fraud|stole|stolen|thief|criminal|hack)\b",
        "service_failure": r"\b(failed|unable|down|not working|no credit|debited|charged twice)\b",
        "regulatory_escalation": r"\b(cbn|ombudsman|lawyer|court|report you|sue)\b",
        "abusive_language": r"\b(idiot|useless|terrible|worst|thieves|criminals)\b",
    }
    for flag, pattern in patterns.items():
        if re.search(pattern, value):
            flags.append(flag)
    metrics = metrics or {}
    engagement = sum(max(0, int(metrics.get(key, 0) or 0)) for key in ("like_count", "retweet_count", "reply_count", "quote_count"))
    if engagement >= 100:
        flags.append("high_reach")
    score = min(1.0, round(0.15 * len(flags) + (0.25 if engagement >= 100 else 0), 2))
    return {"flags": sorted(set(flags)), "score": score, "engagement": engagement}
