"""Signature and payload checks for XtraDot Forge webhook deliveries."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any


class WebhookVerificationError(ValueError):
    """Raised when a webhook cannot be safely authenticated or decoded."""


def _parse_timestamp(value: str, timestamp_format: str) -> datetime:
    try:
        if timestamp_format == "unix-seconds":
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        if timestamp_format != "iso8601":
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise WebhookVerificationError("Invalid webhook timestamp") from None


def verify_webhook_signature(
    raw_body: bytes,
    timestamp: str,
    signature: str,
    secret: str,
    *,
    now: datetime | None = None,
    tolerance: timedelta = timedelta(minutes=5),
    check_timestamp_freshness: bool = True,
    timestamp_format: str | None = None,
) -> None:
    """Verify HMAC-SHA256(timestamp + '.' + raw_body).

    Set `check_timestamp_freshness=False` when a caller must apply a provider format
    configured outside this module. Freshness checks require an explicit format.
    """
    if not secret:
        raise WebhookVerificationError("Webhook signing secret is not configured")
    if not timestamp or not signature:
        raise WebhookVerificationError("Webhook signature headers are required")
    if check_timestamp_freshness and tolerance <= timedelta(0):
        raise ValueError("tolerance must be positive")

    signed_message = timestamp.encode("utf-8") + b"." + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed_message, hashlib.sha256).hexdigest()
    supplied = signature.removeprefix("sha256=")
    if not hmac.compare_digest(expected, supplied):
        raise WebhookVerificationError("Invalid webhook signature")
    if check_timestamp_freshness:
        if timestamp_format is None:
            raise WebhookVerificationError("Webhook timestamp format is not configured")
        signed_at = _parse_timestamp(timestamp, timestamp_format)
        current_time = now or datetime.now(timezone.utc)
        if current_time.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        current_time = current_time.astimezone(timezone.utc)
        if abs(current_time - signed_at) > tolerance:
            raise WebhookVerificationError("Webhook timestamp is outside the allowed window")


def decode_webhook_body(raw_body: bytes) -> dict[str, Any]:
    """Decode JSON without converting decimal numbers through binary floating point."""
    try:
        payload = json.loads(raw_body, parse_float=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise WebhookVerificationError("Webhook body must be valid JSON") from None
    if not isinstance(payload, dict):
        raise WebhookVerificationError("Webhook body must be a JSON object")
    return payload
