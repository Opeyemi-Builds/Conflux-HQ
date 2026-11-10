"""Fast, signed intake for XtraDot Forge webhook evidence."""

from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.xtradot_webhooks import (
    WebhookVerificationError,
    verify_webhook_signature,
)
from app.db.base import utcnow
from app.db.session import get_db
from app.models.xtradot_webhook import XtradotWebhookReceipt

router = APIRouter(prefix="/forge/webhooks", tags=["forge webhooks"])

MAX_WEBHOOK_BODY_BYTES = 1024 * 1024
WEBHOOK_TIMESTAMP_TOLERANCE = timedelta(minutes=5)


def _configured_bank_id() -> uuid.UUID | None:
    value = os.environ.get("XTRADOT_BANK_ID", "").strip()
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _configured_event_types() -> set[str]:
    return {
        event_type.strip()
        for event_type in os.environ.get("XTRADOT_SUPPORTED_EVENTS", "").split(",")
        if event_type.strip()
    }


def _parse_timestamp(raw_timestamp: str, configured_format: str) -> datetime | None:
    """Parse only a format explicitly selected by the Forge deployment."""
    try:
        if configured_format == "unix-seconds":
            parsed = datetime.fromtimestamp(float(raw_timestamp), tz=timezone.utc)
        elif configured_format == "iso8601":
            parsed = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
            if parsed.utcoffset() is None:
                return None
            parsed = parsed.astimezone(timezone.utc)
        else:
            return None
    except (OverflowError, OSError, TypeError, ValueError):
        return None
    return parsed


async def _read_limited_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_WEBHOOK_BODY_BYTES:
                raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Webhook body is too large")
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid content length") from None

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_WEBHOOK_BODY_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Webhook body is too large")
    return bytes(body)


def _event_id_from_body(raw_body: bytes) -> str | None:
    try:
        payload: Any = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    event_id = payload.get("event_id")
    if isinstance(event_id, str) and event_id.strip() and len(event_id) <= 160:
        return event_id
    return None


def _save_receipt(
    db: Session,
    *,
    bank_id: uuid.UUID | None,
    event_id: str | None,
    event_type: str | None,
    raw_body: bytes,
    raw_timestamp: str | None,
    signature_valid: bool | None,
    receipt_status: str,
) -> tuple[XtradotWebhookReceipt, bool]:
    receipt = XtradotWebhookReceipt(
        bank_id=bank_id,
        event_id=event_id,
        event_type=event_type,
        raw_body=raw_body,
        raw_timestamp=raw_timestamp,
        signature_valid=signature_valid,
        status=receipt_status,
        received_at=utcnow(),
    )
    db.add(receipt)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if event_id:
            existing = db.scalar(
                select(XtradotWebhookReceipt).where(
                    XtradotWebhookReceipt.provider == "xtradot",
                    XtradotWebhookReceipt.environment == "sandbox",
                    XtradotWebhookReceipt.event_id == event_id,
                )
            )
            if existing is not None:
                return existing, True
        raise
    db.refresh(receipt)
    return receipt, False


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def receive_xtradot_webhook(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    raw_timestamp: str | None = Header(default=None, alias="x-forge-timestamp"),
    signature: str | None = Header(default=None, alias="x-forge-signature"),
    event_type: str | None = Header(default=None, alias="x-forge-event"),
) -> dict[str, Any]:
    """Verify and durably retain the raw receipt; business processing is asynchronous."""
    raw_body = await _read_limited_body(request)
    secret = os.environ.get("XTRADOT_WEBHOOK_SECRET", "")
    bank_id = _configured_bank_id()
    if event_type is not None and len(event_type) > 160:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Webhook event header is too long")
    if raw_timestamp is not None and len(raw_timestamp) > 160:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Webhook timestamp header is too long")
    if signature is not None and len(signature) > 128:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Webhook signature header is too long")
    clean_event_type = event_type

    if not secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Webhook verification is not configured",
        )

    if not raw_timestamp or not signature:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Webhook signature headers are required")
    try:
        verify_webhook_signature(
            raw_body,
            raw_timestamp,
            signature,
            secret,
            check_timestamp_freshness=False,
        )
    except WebhookVerificationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from None

    timestamp_format = os.environ.get("XTRADOT_WEBHOOK_TIMESTAMP_FORMAT", "")
    parsed_timestamp = _parse_timestamp(raw_timestamp, timestamp_format)
    event_id = _event_id_from_body(raw_body)
    now = datetime.now(timezone.utc)
    is_fresh = (
        parsed_timestamp is not None
        and abs(now - parsed_timestamp) <= WEBHOOK_TIMESTAMP_TOLERANCE
    )
    if parsed_timestamp is not None and not is_fresh:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Webhook timestamp is outside the allowed window")

    supported_types = _configured_event_types()
    receipt_status = "received"
    if bank_id is None or parsed_timestamp is None or event_id is None:
        receipt_status = "ignored"
    elif clean_event_type not in supported_types:
        receipt_status = "ignored"

    receipt, duplicate = _save_receipt(
        db,
        bank_id=bank_id,
        event_id=event_id,
        event_type=clean_event_type,
        raw_body=raw_body,
        raw_timestamp=raw_timestamp,
        signature_valid=True,
        receipt_status=receipt_status,
    )
    response.status_code = status.HTTP_202_ACCEPTED
    return {
        "receipt_id": str(receipt.id),
        "status": "duplicate" if duplicate else receipt.status,
        "duplicate": duplicate,
    }
