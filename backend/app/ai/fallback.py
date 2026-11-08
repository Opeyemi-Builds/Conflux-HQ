import re

from app.models.enums import IssueType, Severity
from .schemas import ClassificationResult

KEYWORDS = {
    "failed_transfer": ("don enter nowhere", "not credited", "no credit", "never reach", "transfer failed", "pending", "reversal", "unreversed", "debit without credit", "did not receive", "didn't receive", "not received", "never receive", "receive my money", "money never reach", "money no enter", "my money since", "owo mi", "ti debited", "ko de"),
    "double_debit": ("debited twice", "double debit", "charged twice", "two times", "duplicate debit", "abụọ ugboro", "lọ ugboro abụọ", "nso ugboro abụọ"),
    "card_atm": ("atm", "card swallowed", "cash no come out", "ego ọpụpụ", "cash no dispensed"),
    "pos": ("pos", "terminal", "merchant", "muna samun al'amari"),
    "fees": ("charge", "fee", "stamp duty", "deducted", "why una dey charge", "asuwo"),
    "loan": ("loan", "repayment", "overdraft", " aro ", "jinginar bashin", "inye mgbapụta"),
    "app_login": ("login", "log in", "otp", "app no dey open", "app crash", "token", "ba zan iya shiga"),
    "fraud_scam": ("fraud", "scam", "hack", "someone called", "asked for my otp", "unauthorised", "unauthorized", "fake agent", "gbajie mi", "ntọghọ aka", "yaudarar"),
}

LOCAL_MARKERS = {
    "yoruba_mix": ("seun", "awon", "mo ti", "owo mi", "e jowo", "e gba", "ko si", "danwo"),
    "hausa_mix": ("don allah", "ba zai", "ina son", "kudi na", "ba zan iya", "an debita", "yaudarar"),
    "igbo_mix": ("biko", "ego m", "ọ bụ", "adịghị", "anyị", "m ga-achọ", "nwere", "abụọ ugboro"),
}
PIDGIN_MARKERS = (" don ", " dey ", " una ", " abeg ", " wetin ", " na ", " e no ", " no be ", " dem ", " chop my money ", " enter nowhere ")


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
            english = bool(re.search(r"\b(?:my|money|bank|payment|transfer|debit|app|card)\b", value))
            return language if english or language == "yoruba_mix" else language
    if any(marker in padded for marker in PIDGIN_MARKERS) or value.startswith(("wetin", "abeg", "my money")):
        return "pidgin"
    if re.search(r"[a-z]", value):
        return "english"
    return "other"


def rules_classify(text: str) -> ClassificationResult:
    value = text.lower()
    scored = [(issue, sum(keyword in value for keyword in words)) for issue, words in KEYWORDS.items()]
    issue, hits = max(scored, key=lambda item: item[1])
    fraud_terms = ("someone called", "fake agent", "asked for my otp", "phishing", "scam", "unauthorised", "unauthorized")
    if any(term in value for term in fraud_terms):
        issue, hits = "fraud_scam", max(1, hits)
    issue = issue if hits else "other"
    language = _language(value)
    positive = bool(re.search(r"\b(thank|thanks|great job|excellent|resolved)\b", value))
    mentioned_time = None
    time_match = re.search(r"(?:since|from|at)\s+(today|morning|yesterday|afternoon|evening|\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", value, re.I)
    if time_match:
        mentioned_time = value[time_match.start():time_match.end()].strip()
    severity = "high" if issue not in ("other", "fees", "app_login") else "medium" if issue == "app_login" else "low"
    if any(word in value for word in ("otp", "hacked", "unauthorised", "unauthorized", "account compromised")):
        severity = "critical" if "compromised" in value else "high"
    fraud = issue == "fraud_scam"
    summary = "The customer reports " + issue.replace("_", " ") + " wording." if issue != "other" else "The customer message does not match a known issue type."
    confidence = min(0.85, 0.35 + hits * 0.15)
    return ClassificationResult(issue_type=issue, severity=severity,
                                sentiment="positive" if positive else "negative",
                                language=language, mentioned_amount=_amount(value),
                                mentioned_time=mentioned_time, is_fraud=fraud,
                                short_summary=summary, confidence=confidence)
