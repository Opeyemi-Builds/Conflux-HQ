"""Worker-side processing of durably retained XtraDot webhook evidence."""

import os
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.xtradot_webhook import XtradotWebhookReceipt


def process_xtradot_webhook_receipt(
    db: Session,
    *,
    receipt_id: uuid.UUID,
    bank_id: uuid.UUID,
) -> dict[str, str | bool]:
    """Mark a receipt handled without guessing undocumented business payload fields.

    The shared worker dispatcher should call this with the job's bank ID. Raw
    evidence remains immutable; only processing metadata is updated. The receipt
    stays in `received` state until Opeyemi wires and enqueues the shared job.
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
    else:
        # A provider receipt is retained as evidence, but unknown body/status
        # schemas are deliberately not interpreted as transfer outcomes.
        receipt.status = "processed"
    receipt.processed_at = utcnow()
    db.commit()
    return {"receipt_id": str(receipt.id), "status": receipt.status, "duplicate": False}
