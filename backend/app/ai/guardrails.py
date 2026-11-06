"""Small grounding checks for AI-generated drafts."""
import json
import re

NUM = re.compile(r"\d[\d,.]*")


def ungrounded_numbers(draft: str, facts: dict) -> list[str]:
    def clean(value: str) -> str:
        return value.rstrip(".,").replace(",", "")
    allowed = {clean(value) for value in NUM.findall(json.dumps(facts, default=str))}
    used = {clean(value) for value in NUM.findall(draft)}
    return sorted(used - allowed)


def verify_draft(draft: str, facts: dict) -> tuple[bool, list[str]]:
    ungrounded = ungrounded_numbers(draft, facts)
    return not ungrounded, ungrounded
