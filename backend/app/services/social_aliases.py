"""Default social identity tagging for onboarded banks.

A bank is "tagged" the moment it has aliases (bank name, @handles, #hashtags,
contextual keywords). The server-side X poller only watches tagged active
banks, so onboarding must always seed defaults — no manual step required.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BankAlias

_DEFAULTS = {
    "zymic bank": [("name", None), ("contextual", None), ("handle", "x"), ("hashtag", "x")],
    "apex demo bank": [("name", None), ("handle", "x"), ("hashtag", "x")],
}


def seed_default_aliases(db: Session, bank_id: uuid.UUID, bank_name: str) -> int:
    """Seed default monitoring identities for a bank. Returns aliases added."""
    name = " ".join(bank_name.casefold().split())
    entries = [(name, "name", None)]
    short, handle, hashtag = "zymic", "@zymicbank", "#zymicbank"
    if name != "zymic bank":
        clean_slug = "".join(c for c in name if c.isalnum())[:15] or "demobank"
        short, handle, hashtag = clean_slug, f"@{clean_slug}", f"#{clean_slug}"
    for kind, platform in _DEFAULTS.get(name, [("name", None), ("handle", "x"), ("hashtag", "x")]):
        value = {"name": name, "contextual": short, "handle": handle, "hashtag": hashtag}.get(kind, name)
        entries.append((value.casefold(), kind, platform))
    if name == "zymic bank":
        entries.extend([
            ("@zymic_help", "handle", "x"),
            ("@zymic_support", "handle", "x"),
            ("@confluxbankhq", "handle", "x"),
        ])
    existing = {a.value for a in db.scalars(select(BankAlias).where(BankAlias.bank_id == bank_id)).all()}
    added = 0
    for value, kind, platform in entries:
        if value not in existing:
            existing.add(value)
            db.add(BankAlias(bank_id=bank_id, value=value, kind=kind, platform=platform))
            added += 1
    return added
