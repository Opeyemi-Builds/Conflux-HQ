"""Small grounding checks for AI-generated drafts."""
import json
import re

from app.core.privacy import mask_pii

NUM = re.compile(r"\d[\d,.]*")
_INSULTS = re.compile(
    r"\b(?:idiot|stupid|useless|incompetent|worthless|moron|fool|scammer|thief|criminal)\b",
    re.IGNORECASE,
)
_REFUND_PROMISE = re.compile(
    r"\b(?:we(?:\s+will|'ll)|i(?:\s+will|'ll))\s+"
    r"(?:refund|reverse|credit|repay)\b|\bguarantee(?:d)?\b",
    re.IGNORECASE,
)
_TIMELINE_PROMISE = re.compile(
    r"\bwithin\s+\d+\s+(?:minutes?|hours?|days?)\b"
    r"|\b(?:will|shall|guarantee(?:d)?\s+to)\s+(?:resolve|fix|complete|credit|refund|reverse)"
    r"(?:\s+this)?\s+(?:by|within)\b"
    r"|\b(?:by|before)\s+(?:tomorrow|today|tonight)\b",
    re.IGNORECASE,
)


def ungrounded_numbers(draft: str, facts: dict) -> list[str]:
    def clean(value: str) -> str:
        return value.rstrip(".,").replace(",", "")
    allowed = {clean(value) for value in NUM.findall(json.dumps(facts, default=str))}
    used = {clean(value) for value in NUM.findall(draft)}
    return sorted(used - allowed)


def verify_draft(draft: str, facts: dict) -> tuple[bool, list[str]]:
    ungrounded = ungrounded_numbers(draft, facts)
    return not ungrounded, ungrounded


def check_outbound_text(text: str) -> list[str]:
    """Return policy violations in customer-facing or operational draft text."""
    violations = []
    if _INSULTS.search(text):
        violations.append("insult")
    if _REFUND_PROMISE.search(text):
        violations.append("refund_or_resolution_promise")
    if _TIMELINE_PROMISE.search(text):
        violations.append("timeline_promise")
    if mask_pii(text) != text:
        violations.append("personal_data")
    return violations
