"""PII masking applied to every complaint before it is stored or analysed (NDPR alignment)."""
import hashlib
import re

# Nigerian mobile numbers: 080..., 070..., 090..., 081..., or +234 / 234 prefix.
_PHONE = re.compile(r"(?<!\d)(?:\+?234|0)[789][01]\d{8}(?!\d)")
_ACCOUNT = re.compile(r"(?<!\d)\d{10}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def mask_pii(text: str) -> str:
    text = _EMAIL.sub("[EMAIL]", text)
    text = _CARD.sub("[CARD]", text)
    text = _PHONE.sub("[PHONE]", text)
    text = _ACCOUNT.sub("[ACCOUNT]", text)
    return text


def pseudonymise(ref: str | None) -> str | None:
    """Stable one-way reference so repeat complainants can be counted without identifying them."""
    if not ref:
        return None
    return "cust_" + hashlib.sha256(ref.strip().lower().encode()).hexdigest()[:12]
