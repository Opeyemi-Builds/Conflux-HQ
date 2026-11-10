"""Core business logic for bank complaint ingestion, connector verification, and idempotency."""
import hashlib
import hmac
import json
import secrets
import unicodedata
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.privacy import mask_pii, pseudonymise
from app.db.base import utcnow
from app.models import Bank, Complaint, Job
from app.models.enums import BankStatus, Channel, JobKind, JobStatus
from app.models.ingestion import ComplaintReceipt, IngestionConnector
from app.schemas.ingestion import ComplaintIngestIn
from app.services.audit import log_event
from app.services.complaint_service import _enqueue_for_complaint


TOKEN_PREFIX = "cfx_conn_"


def hash_connector_secret(secret: str) -> str:
    """Derive HMAC-SHA256 representation of the raw secret using the server's master secret."""
    key = get_settings().ingestion_hash_secret.encode("utf-8")
    return hmac.new(key, secret.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_connector_token() -> tuple[str, str, str]:
    """Generate (prefix, token, hash).
    
    Token format: cfx_conn_<12-char prefix>_<32-char random secret>
    """
    prefix = secrets.token_hex(6)  # 12 hex chars
    secret = secrets.token_urlsafe(24)  # ~32 chars
    full_token = f"{TOKEN_PREFIX}{prefix}_{secret}"
    key_hash = hash_connector_secret(secret)
    return prefix, full_token, key_hash


def verify_connector_token(db: Session, token: str) -> IngestionConnector:
    """Authenticate connector token and return the active bound IngestionConnector.
    
    Raises HTTPException(401) on invalid/unknown credentials or 403 on revoked/inactive status.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing connector credential",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token or not token.startswith(TOKEN_PREFIX):
        raise unauthorized

    parts = token[len(TOKEN_PREFIX):].split("_", 1)
    if len(parts) != 2:
        raise unauthorized
    prefix, secret = parts

    connector = db.scalar(
        select(IngestionConnector).where(IngestionConnector.key_prefix == prefix)
    )
    if connector is None:
        raise unauthorized

    computed_hash = hash_connector_secret(secret)
    if not secrets.compare_digest(connector.key_hash, computed_hash):
        raise unauthorized

    if connector.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Connector credential has been revoked",
        )

    bank = db.get(Bank, connector.bank_id)
    if bank is None or bank.status != BankStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Associated bank account is suspended or inactive",
        )

    return connector


def compute_canonical_content_hash(payload: ComplaintIngestIn) -> str:
    """Compute HMAC-SHA256 content hash of the canonicalized input.
    
    Normalizes unicode, whitespace, dates, and amounts so identical logical
    submissions produce identical hashes while preventing hash collision attacks.
    """
    normalized_text = unicodedata.normalize("NFC", payload.text.strip())
    occurred_iso = payload.occurred_at.astimezone(timezone.utc).isoformat()
    amount_str = f"{Decimal(payload.amount):.2f}" if payload.amount else None

    canonical_dict = {
        "source_system": payload.source_system.strip(),
        "external_id": payload.external_id.strip(),
        "channel": payload.channel,
        "occurred_at": occurred_iso,
        "text": normalized_text,
        "customer_ref": payload.customer_ref.strip() if payload.customer_ref else None,
        "payment_reference": payload.payment_reference.strip() if payload.payment_reference else None,
        "amount": amount_str,
        "currency": payload.currency,
        "region": payload.region.strip() if payload.region else None,
        "language": payload.language.strip() if payload.language else None,
    }
    encoded = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    key = get_settings().ingestion_hash_secret.encode("utf-8")
    return hmac.new(key, encoded, hashlib.sha256).hexdigest()


def get_processing_status_for_complaint(db: Session, complaint: Complaint) -> str:
    """Determine current classification lifecycle status."""
    if complaint.issue_type is not None:
        return "classified"

    job = db.scalar(
        select(Job)
        .where(
            Job.bank_id == complaint.bank_id,
            Job.kind == JobKind.CLASSIFY_COMPLAINT,
            Job.idempotency_key == f"classify:{complaint.id}",
        )
        .order_by(Job.created_at.desc())
    )
    if job is None:
        return "queued"
    if job.status == JobStatus.COMPLETED:
        return "classified"
    if job.status == JobStatus.RUNNING:
        return "processing"
    if job.status == JobStatus.DEAD_LETTER:
        return "failed"
    return "queued"


def ingest_bank_complaint(
    db: Session,
    connector: IngestionConnector,
    payload: ComplaintIngestIn,
) -> tuple[int, dict]:
    """Ingest a complaint with database-enforced idempotency, atomicity, and provenance.
    
    Returns (status_code, response_data).
    - 202: Durable initial acceptance
    - 200: Idempotent replay of identical payload
    - 409: Conflicting replay with changed content
    """
    content_hash = compute_canonical_content_hash(payload)

    # 1. Fast Path: Check existing receipt by (bank_id, connector_id, external_id)
    existing_receipt = db.scalar(
        select(ComplaintReceipt).where(
            ComplaintReceipt.bank_id == connector.bank_id,
            ComplaintReceipt.connector_id == connector.id,
            ComplaintReceipt.external_id == payload.external_id,
        )
    )

    if existing_receipt is not None:
        complaint = db.get(Complaint, existing_receipt.complaint_id)
        if secrets.compare_digest(existing_receipt.content_hash, content_hash):
            # Safe duplicate replay
            processing_status = get_processing_status_for_complaint(db, complaint) if complaint else "queued"
            received_at = existing_receipt.received_at
            if received_at.tzinfo is None:
                received_at = received_at.replace(tzinfo=timezone.utc)
            return status.HTTP_200_OK, {
                "complaint_id": existing_receipt.complaint_id,
                "receipt_id": existing_receipt.id,
                "processing_status": processing_status,
                "duplicate": True,
                "received_at": received_at,
            }
        else:
            # Conflict: same external_id re-used with differing content
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "external_id_conflict",
                    "message": f"A ticket with external_id '{payload.external_id}' already exists with different payload content.",
                    "receipt_id": str(existing_receipt.id),
                    "existing_received_at": existing_receipt.received_at.isoformat(),
                },
            )

    # 2. Insertion Path: Inside a savepoint to catch race conditions cleanly
    masked_text = mask_pii(payload.text)
    pseudo_cust_ref = pseudonymise(payload.customer_ref)
    received_now = utcnow()
    amount_dec = Decimal(payload.amount) if payload.amount else None

    try:
        with db.begin_nested():
            complaint = Complaint(
                bank_id=connector.bank_id,
                channel=Channel(payload.channel),
                text=masked_text,
                customer_ref=pseudo_cust_ref,
                payment_reference=payload.payment_reference,
                region=payload.region,
                language=payload.language,
                occurred_at=payload.occurred_at,
                ingested_at=received_now,
                issue_type=None,
            )
            db.add(complaint)
            db.flush()

            receipt = ComplaintReceipt(
                bank_id=connector.bank_id,
                connector_id=connector.id,
                complaint_id=complaint.id,
                source_system=payload.source_system,
                external_id=payload.external_id,
                content_hash=content_hash,
                payment_reference=payload.payment_reference,
                amount=amount_dec,
                currency=payload.currency,
                occurred_at=payload.occurred_at,
                received_at=received_now,
                synthetic=payload.synthetic,
            )
            db.add(receipt)
            db.flush()

            # Atomic classification job enqueue
            _enqueue_for_complaint(db, connector.bank_id, complaint)

            # Update connector activity timestamp
            connector.last_used_at = received_now

            log_event(
                db,
                bank_id=connector.bank_id,
                actor=f"connector:{connector.key_prefix}",
                action="bank_complaint_ingested",
                entity_type="complaint",
                entity_id=str(complaint.id),
                details={
                    "connector_id": str(connector.id),
                    "receipt_id": str(receipt.id),
                    "external_id": payload.external_id,
                    "payment_reference": payload.payment_reference,
                    "amount": payload.amount,
                    "currency": payload.currency,
                },
            )
    except IntegrityError as exc:
        # Concurrent delivery collision caught by database UniqueConstraint.
        # Roll back our failed transaction state so we can read the winning transaction's committed row.
        db.rollback()
        import time

        existing_receipt = None
        for _ in range(10):
            existing_receipt = db.scalar(
                select(ComplaintReceipt).where(
                    ComplaintReceipt.bank_id == connector.bank_id,
                    ComplaintReceipt.connector_id == connector.id,
                    ComplaintReceipt.external_id == payload.external_id,
                )
            )
            if existing_receipt is not None:
                break
            time.sleep(0.05)

        if existing_receipt is not None:
            complaint = db.get(Complaint, existing_receipt.complaint_id)
            if secrets.compare_digest(existing_receipt.content_hash, content_hash):
                processing_status = get_processing_status_for_complaint(db, complaint) if complaint else "queued"
                received_at = existing_receipt.received_at
                if received_at.tzinfo is None:
                    received_at = received_at.replace(tzinfo=timezone.utc)
                return status.HTTP_200_OK, {
                    "complaint_id": existing_receipt.complaint_id,
                    "receipt_id": existing_receipt.id,
                    "processing_status": processing_status,
                    "duplicate": True,
                    "received_at": received_at,
                }
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "external_id_conflict",
                    "message": f"A ticket with external_id '{payload.external_id}' already exists with different payload content.",
                    "receipt_id": str(existing_receipt.id),
                },
            )
        raise exc

    db.commit()

    return status.HTTP_202_ACCEPTED, {
        "complaint_id": complaint.id,
        "receipt_id": receipt.id,
        "processing_status": "queued",
        "duplicate": False,
        "received_at": received_now,
    }
