"""Deterministic, privacy-conscious public-signal triage helpers."""
from datetime import datetime, timedelta
from difflib import SequenceMatcher


_NEGATIVE_FLAGS = {
    "service_failure",
    "scam_allegation",
    "regulatory_escalation",
    "abusive_language",
}
_SAFE_THEME_LABELS = {
    "failed_transfer",
    "double_debit",
    "card_atm_failure",
    "pos_failure",
    "fees",
    "loan",
    "app_login",
    "other",
    "security_concern",
    "payment_concern",
}

ALLOWED_REPUTATION_LABELS = frozenset(
    {
        "service_failure",
        "scam_allegation",
        "regulatory_escalation",
        "public_escalation",
        "abusive_language",
        "high_reach",
        "coordinated_pattern",
        "repeated_theme",
        "high_reach_negative",
        *_SAFE_THEME_LABELS,
    }
)


def _as_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def coordinated_post_ids(posts: list[dict]) -> set[str]:
    """Find near-identical posts in a 60-minute window from at least 3 authors."""
    ordered = sorted(posts, key=lambda post: _as_datetime(post["received_at"]))
    coordinated: set[str] = set()
    for anchor in ordered:
        anchor_time = _as_datetime(anchor["received_at"])
        anchor_text = _normalized_text(anchor.get("text", ""))
        if not anchor_text:
            continue
        matching = [
            post
            for post in ordered
            if anchor_time <= _as_datetime(post["received_at"]) <= anchor_time + timedelta(minutes=60)
            and SequenceMatcher(
                None, anchor_text, _normalized_text(post.get("text", ""))
            ).ratio()
            >= 0.8
        ]
        authors = {post.get("author_ref_hash") for post in matching if post.get("author_ref_hash")}
        if len(matching) >= 5 and len(authors) >= 3:
            coordinated.update(str(post["id"]) for post in matching)
    return coordinated


def public_escalation_urgency(
    flags: list[str] | set[str], *, score: float, engagement: int
) -> tuple[str, str, bool]:
    labels = set(flags)
    if (
        ("scam_allegation" in labels and "high_reach" in labels)
        or ("regulatory_escalation" in labels and engagement >= 100)
        or score >= 0.85
    ):
        urgency = "urgent"
    elif (
        ("high_reach" in labels and labels & _NEGATIVE_FLAGS)
        or score >= 0.6
        or "coordinated_pattern" in labels
        or "repeated_theme" in labels
    ):
        urgency = "high"
    elif labels & (_NEGATIVE_FLAGS | {"public_escalation", "high_reach"}):
        urgency = "normal"
    else:
        urgency = "low"
    return urgency, urgency, urgency in {"high", "urgent"}


def reputation_signal_index(posts: list[dict]) -> float:
    """Return a demo heuristic, not a verdict; high-reach negative signals weigh more."""
    if not posts:
        return 50.0
    risk = 0.0
    for post in posts:
        flags = set(post.get("flags", []))
        if flags & _NEGATIVE_FLAGS:
            risk += 1.5 if "high_reach" in flags else 1.0
    return round(max(0.0, min(100.0, 100.0 * (1 - risk / len(posts)))), 1)


def safe_theme_label(payment_category: str | None, issue_type: str) -> str:
    if payment_category in _SAFE_THEME_LABELS:
        return payment_category
    if payment_category in {"fraud_scam", "account_takeover"} or issue_type == "fraud_scam":
        return "security_concern"
    if payment_category:
        return "payment_concern"
    return issue_type if issue_type in _SAFE_THEME_LABELS else "other"
