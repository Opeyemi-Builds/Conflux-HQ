"""PII masking applied to every complaint before it is stored or analysed (NDPR alignment)."""
import hashlib
import re

# Nigerian mobile numbers: 080..., 070..., 090..., 081..., or +234 / 234 prefix.
_PHONE = re.compile(r"(?<!\d)(?:\+?234|0)[789][01]\d{8}(?!\d)")
_ACCOUNT = re.compile(r"(?<!\d)\d{10}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_ELEVEN_DIGITS = re.compile(r"(?<!\d)\d{11}(?!\d)")


def _mask_contextual_bvn(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        context = text[max(0, match.start() - 20):match.start()]
        return "[BVN]" if re.search(r"\bBVN\b", context, re.IGNORECASE) else match.group(0)

    return _ELEVEN_DIGITS.sub(replace, text)


def mask_pii(text: str) -> str:
    text = _mask_contextual_bvn(text)
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
