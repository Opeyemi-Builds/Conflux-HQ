"""Deterministic routing signals for the human-reviewed fraud queue."""
import re
from dataclasses import dataclass

from app.ai.schemas import ClassificationResult


@dataclass(frozen=True)
class FraudRouting:
    routed: bool
    fraud_type: str | None = None
    priority: str | None = None
    indicators: tuple[str, ...] = ()


_SIGNALS: tuple[tuple[str, str, str], ...] = (
    ("otp_request", r"\botp\b|\bone[- ]time password\b", "critical"),
    ("fake_bank_agent", r"\bfake (?:bank )?(?:agent|staff)\b|\bclaiming to be (?:from )?(?:the )?bank\b", "critical"),
    ("phishing_link", r"\bphishing link\b|\bsuspicious link\b|\bclicked the link\b", "high"),
    ("sim_swap_indicator", r"\bsim[- ]swap\b|\bsim swap\b", "critical"),
    ("account_takeover_claim", r"\btook over my account\b|\baccount takeover\b|\baccount was hacked\b|\bhacked my account\b|\bunauthori[sz]ed access\b", "critical"),
    ("unauthorized_transfer", r"\bunauthori[sz]ed transfer\b|\bdid not authori[sz]e\b|\bunknown debit\b|\bunexplained debit\b|\bunrecognized debit\b|\bunrecognised debit\b", "critical"),
    ("other_fraud", r"\bscam\b|\bfraud\b|\bstole my\b|\bstolen\b|\bmy brother used my card\b|\bmy sister used my card\b", "medium"),
)

_KNOWN_PERSON_CARD_USE = re.compile(
    r"\bmy (?:brother|sister|mother|father|husband|wife|son|daughter) used my card\b",
    re.IGNORECASE,
)


def route_fraud(classification: ClassificationResult, text: str) -> FraudRouting:
    """Route explicit fraud signals or suspicious unauthorized debit reports for human review."""
    normalized = text.casefold()
    matches = [
        (fraud_type, priority, match.group(0))
        for fraud_type, pattern, priority in _SIGNALS
        if (match := re.search(pattern, normalized))
    ]
    if not matches and classification.payment_category not in {"fraud_scam", "account_takeover"} and not classification.is_fraud:
        return FraudRouting(routed=False)

    if _KNOWN_PERSON_CARD_USE.search(text):
        return FraudRouting(
            routed=True,
            fraud_type="other_fraud",
            priority="low",
            indicators=("known_person_card_use",),
        )

    if not matches:
        fraud_type = "account_takeover_claim" if classification.payment_category == "account_takeover" else "other_fraud"
        priority = "high" if fraud_type == "account_takeover_claim" else "medium"
        return FraudRouting(routed=True, fraud_type=fraud_type, priority=priority, indicators=("classifier_fraud_signal",))

    precedence = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    fraud_type, priority, _ = min(matches, key=lambda match: precedence[match[1]])
    indicators = tuple(dict.fromkeys(match[0] for match in matches))
    return FraudRouting(routed=True, fraud_type=fraud_type, priority=priority, indicators=indicators)
