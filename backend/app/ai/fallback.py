import re

from app.models.enums import IssueType, Severity
from .schemas import ClassificationResult, PaymentCategory


PAYMENT_TO_ISSUE_TYPE: dict[PaymentCategory, IssueType] = {
    "debited_not_credited": IssueType.FAILED_TRANSFER,
    "failed_transfer": IssueType.FAILED_TRANSFER,
    "pending_transfer": IssueType.FAILED_TRANSFER,
    "delayed_settlement": IssueType.FAILED_TRANSFER,
    "reversed_not_refunded": IssueType.FAILED_TRANSFER,
    "double_debit": IssueType.DOUBLE_DEBIT,
    "duplicate_payment": IssueType.DOUBLE_DEBIT,
    "card_atm_failure": IssueType.CARD_ATM,
    "pos_failure": IssueType.POS,
    "processor_timeout": IssueType.FAILED_TRANSFER,
    "switch_outage": IssueType.FAILED_TRANSFER,
    "fees": IssueType.FEES,
    "fraud_scam": IssueType.FRAUD_SCAM,
    "account_takeover": IssueType.FRAUD_SCAM,
    "unknown_payment_issue": IssueType.OTHER,
}

# Keep specific categories before broad transfer and fraud language so a complaint
# mentioning an ATM, POS, or takeover is not reduced to a generic transfer issue.
PAYMENT_KEYWORDS: dict[PaymentCategory, tuple[str, ...]] = {
    "account_takeover": (
        "account takeover", "took over my account", "someone accessed my account",
        "my account was hacked", "account compromised", "sim swap", "sim-swap",
        "gbajie mi", "yaudarar account",
    ),
    "fraud_scam": (
        "scam", "phishing", "fake agent", "fake bank staff", "asked for my otp",
        "requested my otp", "someone called", "unauthorised transfer",
        "unauthorized transfer", "fraud", "yaudarar", "gbajie",
    ),
    "double_debit": (
        "debited twice", "double debit", "charged twice", "duplicate debit",
        "two times", "twice for", "abụọ ugboro", "lọ ugboro abụọ", "nso ugboro abụọ",
    ),
    "duplicate_payment": (
        "duplicate payment", "paid twice", "payment made twice",
        "duplicate transaction", "charged two times",
    ),
    "card_atm_failure": (
        "atm", "card swallowed", "cash no come out", "cash did not come out",
        "cash didn't come out", "cash not dispensed", "cash no dispense",
        "card transaction failed", "ego ọpụpụ", "biko atm",
    ),
    "pos_failure": (
        "pos", "point of sale", "merchant terminal", "terminal transaction",
        "pos terminal", "merchant payment",
    ),
    "processor_timeout": (
        "processor timeout", "processor timed out", "payment processor timed out",
        "gateway timeout", "switch timeout",
    ),
    "switch_outage": (
        "switch outage", "payment switch is down", "switch is down",
        "switch unavailable", "network outage", "switch failure",
    ),
    "reversed_not_refunded": (
        "reversed but not refunded", "reversed but i was not refunded", "reversed but not credited",
        "reversal not refunded", "reversal has not returned", "abeg reverse",
        "reversal never come",
    ),
    "debited_not_credited": (
        "debited but not credited", "debit without credit", "debited and not credited",
        "debited but receiver", "receiver was not credited", "not credited",
        "no credit", "never reach", "don enter nowhere", "chop my money",
        "alert never come", "money don disappear", "owo mi", "ti debited",
        "an debita", "ego m",
    ),
    "pending_transfer": (
        "transfer is pending", "transfer still pending", "transfer is still pending", "pending transfer",
        "payment is pending", "payment still pending", "payment is still pending", "transaction pending",
    ),
    "delayed_settlement": (
        "delayed settlement", "settlement is delayed", "settlement delayed",
        "settlement has not arrived", "settlement not received",
    ),
    "fees": (
        "fee", "fees", "stamp duty", "service charge", "maintenance charge",
        "why una dey charge", "asuwo",
    ),
    "failed_transfer": (
        "transfer failed", "failed transfer", "transfer no go", "e no work",
        "the thing no work", "money no enter", "transfer did not go through",
        "transfer didn't go through", "transaction failed",
    ),
    "unknown_payment_issue": (
        "payment", "transfer", "debited", "debit alert", "transaction",
        "settlement", "receiver", "reversal", "money no enter",
    ),
}

LEGACY_KEYWORDS: dict[IssueType, tuple[str, ...]] = {
    IssueType.CARD_ATM: ("atm", "card swallowed", "cash no come out", "cash no dispensed"),
    IssueType.POS: ("pos", "terminal", "merchant"),
    IssueType.FEES: ("charge", "fee", "stamp duty", "deducted", "why una dey charge"),
    IssueType.LOAN: ("loan", "repayment", "overdraft", " aro ", "jinginar bashin"),
    IssueType.APP_LOGIN: ("login", "log in", "otp", "app no dey open", "app crash", "token"),
    IssueType.FRAUD_SCAM: (
        "fraud", "scam", "hack", "someone called", "asked for my otp",
        "unauthorised", "unauthorized", "fake agent", "yaudarar",
    ),
    IssueType.DOUBLE_DEBIT: ("debited twice", "double debit", "charged twice", "two times", "duplicate debit"),
    IssueType.FAILED_TRANSFER: (
        "don enter nowhere", "not credited", "no credit", "never reach",
        "transfer failed", "pending", "reversal", "unreversed", "debit without credit",
        "did not receive", "didn't receive", "not received", "never receive",
        "receive my money", "money never reach", "money no enter", "my money since",
        "owo mi", "ti debited", "ko de",
    ),
}

LOCAL_MARKERS = {
    "yoruba_mix": ("seun", "awon", "mo ti", "owo mi", "e jowo", "e gba", "ko si", "danwo"),
    "hausa_mix": ("don allah", "ba zai", "ina son", "kudi na", "ba zan iya", "an debita", "yaudarar"),
    "igbo_mix": ("biko", "ego m", "ọ bụ", "adịghị", "anyị", "m ga-achọ", "nwere", "abụọ ugboro"),
}
PIDGIN_MARKERS = (
    " don ", " dey ", " una ", " abeg ", " wetin ", " na ", " e no ", " no be ",
    " dem ", " chop my money ", " enter nowhere ", "transfer no go",
)
_INJECTION_CLAUSES = re.compile(
    r"\b(?:ignore|disregard)\s+(?:all\s+)?(?:the\s+)?"
    r"(?:previous|prior|above|earlier)\s+instructions?\b[^.!?\n]*[.!?]?"
    r"|\bthis\s+is\s+not\s+a\s+complaint\b[^.!?\n]*[.!?]?"
    r"|\b(?:reveal|show|print|expose)\s+(?:the\s+)?"
    r"(?:system\s+prompt|api\s+keys?|secrets?)\b[^.!?\n]*[.!?]?",
    re.IGNORECASE,
)


def _amount(value: str) -> float | None:
    match = re.search(r"(?:n|ngn|₦)?\s*(\d+(?:[,.]\d+)?)\s*(k)?", value, re.I)
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    return number * 1000 if match.group(2) else number


def _language(value: str) -> str:
    padded = f" {value} "
    for language, markers in LOCAL_MARKERS.items():
        if any(marker in padded for marker in markers):
            return language
    if any(marker in padded for marker in PIDGIN_MARKERS) or value.startswith(("wetin", "abeg", "my money")):
        return "pidgin"
    if re.search(r"[a-z]", value):
        return "english"
    return "other"


def _evidence_phrases(text: str, keywords: tuple[str, ...]) -> list[str]:
    phrases: list[str] = []
    for keyword in keywords:
        match = re.search(re.escape(keyword.strip()), text, re.IGNORECASE)
        if match and match.group(0).lower() not in {phrase.lower() for phrase in phrases}:
            phrases.append(match.group(0))
        if len(phrases) == 5:
            break
    return phrases


def rules_classify(text: str) -> ClassificationResult:
    value = _INJECTION_CLAUSES.sub(" ", text).lower()
    category_scores = [
        (category, sum(keyword in value for keyword in keywords))
        for category, keywords in PAYMENT_KEYWORDS.items()
        if category != "unknown_payment_issue"
    ]
    payment_category, payment_hits = max(category_scores, key=lambda item: item[1])
    if not payment_hits:
        unknown_hits = sum(keyword in value for keyword in PAYMENT_KEYWORDS["unknown_payment_issue"])
        payment_category = "unknown_payment_issue" if unknown_hits else None
        payment_hits = unknown_hits

    legacy_scores = [
        (issue, sum(keyword in value for keyword in keywords))
        for issue, keywords in LEGACY_KEYWORDS.items()
    ]
    legacy_issue, legacy_hits = max(legacy_scores, key=lambda item: item[1])

    if payment_category is not None:
        issue = PAYMENT_TO_ISSUE_TYPE[payment_category]
    else:
        issue = legacy_issue if legacy_hits else IssueType.OTHER

    language = _language(value)
    positive = bool(re.search(r"\b(thank|thanks|great job|excellent|resolved)\b", value))
    mentioned_time = None
    time_match = re.search(
        r"(?:since|from|at)\s+(today|morning|yesterday|afternoon|evening|\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
        value,
        re.I,
    )
    if time_match:
        mentioned_time = value[time_match.start():time_match.end()].strip()

    fraud = payment_category in ("fraud_scam", "account_takeover")
    severity = "high" if issue not in (IssueType.OTHER, IssueType.FEES, IssueType.APP_LOGIN) else "low"
    if any(word in value for word in ("otp", "hacked", "unauthorised", "unauthorized", "account compromised")):
        severity = "critical" if "compromised" in value or payment_category == "account_takeover" else "high"
    if payment_category == "unknown_payment_issue":
        severity = "medium"

    evidence = _evidence_phrases(
        text,
        PAYMENT_KEYWORDS[payment_category] if payment_category else LEGACY_KEYWORDS.get(issue, ()),
    )
    label = payment_category.replace("_", " ") if payment_category else issue.value.replace("_", " ")
    summary = (
        f"The customer reports a {label} issue."
        if payment_category or issue != IssueType.OTHER
        else "The complaint needs human review to determine the issue."
    )
    explanation = (
        f"Matched the complaint wording to {label}."
        if payment_category or issue != IssueType.OTHER
        else "No supported complaint category was identified from the wording."
    )
    hits = payment_hits if payment_category else legacy_hits
    confidence = min(0.85, 0.35 + hits * 0.15)

    return ClassificationResult(
        issue_type=issue.value,
        severity=severity,
        sentiment="positive" if positive else "negative",
        language=language,
        mentioned_amount=_amount(value),
        mentioned_time=mentioned_time,
        is_fraud=fraud,
        short_summary=summary,
        confidence=confidence,
        payment_category=payment_category,
        explanation=explanation,
        evidence_phrases=evidence,
    )
