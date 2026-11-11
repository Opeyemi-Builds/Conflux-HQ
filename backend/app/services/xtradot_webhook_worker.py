"""Worker-side processing of durably retained XtraDot webhook evidence."""

import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.xtradot_schemas import (
    PaymentEvidenceEvent,
    REPORT_DOWNLOAD_HOSTS,
    ReportEvidenceEvent,
)
from app.adapters.xtradot_webhooks import WebhookVerificationError, decode_webhook_body
from app.db.base import utcnow
from app.models.xtradot_webhook import XtradotWebhookReceipt
from app.services.payment_evidence import ProviderEventConflictError, append_unique_events

# Mock Spec v2 documents the transfer/payment event body shape
# ({event, event_id, created_at, attempt, data: {reference, session_id,
# amount, currency, status}}). Any other shape stays `ignored`.
DOCUMENTED_EVENT_PREFIXES = ("transfer.", "payment.")
# `docs/xtradot-report-webhook.md` documents the report event body shape
# ({event, event_id, created_at, attempt, data: {report_id, report_type,
# status, period_from, period_to, payment_references, download_url,
# checksum, amount, currency}}). Anything else stays `ignored`.
DOCUMENTED_REPORT_PREFIX = "report."


def _parse_event_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _decimal_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("amount must be a decimal value")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("amount must be a decimal value") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("amount must be a finite non-negative decimal")
    if isinstance(value, str):
        return value  # preserve the provider's exact decimal representation
    return format(amount, "f")


def _sanitize_download_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 2048:
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or parsed.hostname not in REPORT_DOWNLOAD_HOSTS:
        return None  # never fetch non-allowlisted hosts; keep evidence without the link
    return value.strip()


def _sanitize_payment_references(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    cleaned = [entry.strip() for entry in value if isinstance(entry, str) and entry.strip()]
    cleaned = [entry for entry in cleaned if len(entry) <= 160]
    return cleaned or None


def normalize_receipt_report_event(
    *, bank_id: uuid.UUID, event_id: str, event_type: str, raw_body: bytes, received_at: datetime
) -> ReportEvidenceEvent | None:
    """Normalize a documented report body, or return None.

    Returns None for any shape outside `docs/xtradot-report-webhook.md` —
    those receipts stay `ignored`, never guessed. Raises on corrupt JSON
    or invalid amount/currency (caller marks ignored).
    """
    if not event_type.startswith(DOCUMENTED_REPORT_PREFIX):
        return None
    payload = decode_webhook_body(raw_body)
    body_event = payload.get("event")
    if isinstance(body_event, str) and body_event != event_type:
        return None  # header/body mismatch: not trustworthy evidence
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    report_id = data.get("report_id")
    report_type = data.get("report_type")
    source_status = data.get("status")
    if (
        not isinstance(report_id, str)
        or not report_id.strip()
        or len(report_id) > 160
        or not isinstance(report_type, str)
        or not report_type.strip()
        or len(report_type) > 64
        or not isinstance(source_status, str)
        or not source_status.strip()
        or len(source_status) > 64
    ):
        return None
    currency = data.get("currency")
    if currency is not None and (not isinstance(currency, str) or len(currency) != 3):
        raise ValueError("currency must be a 3-letter code when present")
    checksum = data.get("checksum")
    if checksum is not None and (not isinstance(checksum, str) or not checksum.strip()):
        checksum = None
    if isinstance(checksum, str) and len(checksum.strip()) > 256:
        raise ValueError("checksum must be at most 256 characters")
    occurred_at = _parse_event_time(data.get("created_at")) or _parse_event_time(payload.get("created_at"))
    return ReportEvidenceEvent(
        bank_id=bank_id,
        provider_event_id=event_id,
        event_type=event_type,
        report_id=report_id.strip(),
        report_type=report_type.strip(),
        source_status=source_status.strip(),
        amount=_decimal_string(data.get("amount")),
        currency=currency,
        period_from=_parse_event_time(data.get("period_from")),
        period_to=_parse_event_time(data.get("period_to")),
        payment_references=_sanitize_payment_references(data.get("payment_references")),
        download_url=_sanitize_download_url(data.get("download_url")),
        checksum=checksum.strip() if isinstance(checksum, str) else None,
        occurred_at=occurred_at,
        received_at=received_at,
    )


def normalize_receipt_event(
    *, bank_id: uuid.UUID, event_id: str, event_type: str, raw_body: bytes, received_at: datetime
) -> PaymentEvidenceEvent | None:
    """Normalize a documented v2 transfer/payment body, or return None.

    Returns None for any shape outside the documented contract — those receipts
    stay `ignored`, never guessed. Raises on corrupt JSON (caller marks ignored).
    """
    if not event_type.startswith(DOCUMENTED_EVENT_PREFIXES):
        return None
    payload = decode_webhook_body(raw_body)
    body_event = payload.get("event")
    if isinstance(body_event, str) and body_event != event_type:
        return None  # header/body mismatch: not trustworthy evidence
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    reference = data.get("reference")
    source_status = data.get("status")
    if (
        not isinstance(reference, str)
        or not reference.strip()
        or len(reference) > 160
        or not isinstance(source_status, str)
        or not source_status.strip()
        or len(source_status) > 64
    ):
        return None
    currency = data.get("currency")
    if currency is not None and (not isinstance(currency, str) or len(currency) != 3):
        raise ValueError("currency must be a 3-letter code when present")
    occurred_at = _parse_event_time(data.get("created_at")) or _parse_event_time(payload.get("created_at"))
    return PaymentEvidenceEvent(
        bank_id=bank_id,
        provider_event_id=event_id,
        payment_reference=reference.strip(),
        event_type=event_type,
        source_status=source_status.strip(),
        amount=_decimal_string(data.get("amount")),
        currency=currency,
        occurred_at=occurred_at,
        received_at=received_at,
    )


def process_xtradot_webhook_receipt(
    db: Session,
    *,
    receipt_id: uuid.UUID,
    bank_id: uuid.UUID,
) -> dict[str, Any]:
    """Normalize a retained receipt into provider evidence without mutating raw bytes.

    Documented v2 transfer/payment bodies become one `PaymentEvidenceEvent`;
    documented report bodies become one `ReportEvidenceEvent`
    (single-event receipts dedupe trivially via `append_unique_events`; the
    receipt-level unique constraint already dedupes redeliveries by event_id).
    Anything outside the documented shapes stays `ignored`. Provider statuses are
    observations only — never ledger proof, never a transfer trigger.
    """
    receipt = db.scalar(
        select(XtradotWebhookReceipt).where(
            XtradotWebhookReceipt.id == receipt_id,
            XtradotWebhookReceipt.bank_id == bank_id,
            XtradotWebhookReceipt.provider == "xtradot",
            XtradotWebhookReceipt.environment == "sandbox",
        )
    )
    if receipt is None:
        raise LookupError("XtraDot webhook receipt not found for this bank")
    if receipt.status != "received":
        return {"receipt_id": str(receipt.id), "status": receipt.status, "duplicate": True}

    configured_events = {
        event_type.strip()
        for event_type in os.environ.get("XTRADOT_SUPPORTED_EVENTS", "").split(",")
        if event_type.strip()
    }
    if (
        receipt.signature_valid is not True
        or not receipt.event_id
        or not receipt.event_type
        or receipt.event_type not in configured_events
    ):
        receipt.status = "ignored"
        receipt.processed_at = utcnow()
        db.commit()
        return {"receipt_id": str(receipt.id), "status": receipt.status, "duplicate": False}

    try:
        if receipt.event_type.startswith(DOCUMENTED_REPORT_PREFIX):
            event = normalize_receipt_report_event(
                bank_id=bank_id,
                event_id=receipt.event_id,
                event_type=receipt.event_type,
                raw_body=receipt.raw_body,
                received_at=utcnow(),
            )
        else:
            event = normalize_receipt_event(
                bank_id=bank_id,
                event_id=receipt.event_id,
                event_type=receipt.event_type,
                raw_body=receipt.raw_body,
                received_at=utcnow(),
            )
    except (WebhookVerificationError, ValueError) as exc:
        receipt.status = "ignored"
        receipt.processing_error = str(exc)[:256]
        receipt.processed_at = utcnow()
        db.commit()
        return {"receipt_id": str(receipt.id), "status": receipt.status, "duplicate": False}

    if event is None:
        receipt.status = "ignored"
        receipt.processed_at = utcnow()
        db.commit()
        return {"receipt_id": str(receipt.id), "status": receipt.status, "duplicate": False}

    try:
        append_unique_events([], [event])
    except ProviderEventConflictError as exc:  # cannot happen for a single event; stay safe
        receipt.status = "ignored"
        receipt.processing_error = str(exc)[:256]
        receipt.processed_at = utcnow()
        db.commit()
        return {"receipt_id": str(receipt.id), "status": receipt.status, "duplicate": False}

    receipt.status = "processed"
    receipt.processed_at = utcnow()
    db.commit()
    return {
        "receipt_id": str(receipt.id),
        "status": receipt.status,
        "duplicate": False,
        "evidence": event.model_dump(mode="json"),
    }
