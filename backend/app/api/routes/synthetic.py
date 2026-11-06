"""Bounded, reproducible synthetic fixtures. Never calls a live bank or moves money."""
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from app.api.deps import DbSession, Operator
from app.core.config import get_settings
from app.db.base import utcnow
from app.models import Bank, Complaint, SystemEvent, Transaction
from app.models.enums import (Channel, EventType, IssueType, ReversalStatus, Sentiment,
                              Severity, TxnChannel, TxnStatus, TxnType)
from app.services.audit import log_event
from app.services.demo_auth import DEMO_BANK_ID

router = APIRouter(prefix="/synthetic", tags=["synthetic demo data"])


class SeedRequest(BaseModel):
    seed: int = Field(default=42, ge=0, le=2147483647)
    at: datetime | None = None

    @field_validator("at")
    @classmethod
    def aware(cls, value):
        if value is not None and value.utcoffset() is None:
            raise ValueError("at must include a timezone")
        return value


def require_demo(user):
    if not get_settings().demo_mode or user.bank_id != DEMO_BANK_ID:
        raise HTTPException(404, "Synthetic routes are only available for the demo bank")


@router.post("/seed", status_code=201)
def seed_data(payload: SeedRequest, user: Operator, db: DbSession):
    """Seed once into an empty demo bank; no deletion/reset endpoint is exposed."""
    require_demo(user)
    # Serialize concurrent seeds on PostgreSQL; the bank row already exists after login.
    db.execute(select(Bank).where(Bank.id == user.bank_id).with_for_update()).scalar_one()
    for model in (Complaint, Transaction, SystemEvent):
        if db.scalar(select(func.count()).select_from(model).where(model.bank_id == user.bank_id)):
            raise HTTPException(409, "Demo bank already contains data; seed never overwrites existing records")
    rng = random.Random(payload.seed)
    anchor = (payload.at or utcnow()).astimezone(timezone.utc)
    bucket = anchor.replace(minute=anchor.minute - anchor.minute % 15, second=0, microsecond=0)
    # Current bucket holds the spike. Use the returned anchor for analytics and detection.
    detection_at = bucket + timedelta(minutes=14, seconds=59)
    release_at = bucket - timedelta(minutes=12)
    start = bucket - timedelta(hours=48)
    channels = list(Channel)
    regions = ["Lagos", "Abuja", "Kano", "Port Harcourt", "Ibadan"]
    texts = {
        IssueType.FAILED_TRANSFER: ["My transfer failed but I was debited.", "My money don enter nowhere."],
        IssueType.FRAUD_SCAM: ["A fake bank agent asked me for my OTP. Please investigate."],
        IssueType.CARD_ATM: ["The ATM debited me without dispensing cash."],
        IssueType.POS: ["My POS payment failed and the merchant received nothing."],
        IssueType.APP_LOGIN: ["I cannot sign into the banking app."],
        IssueType.FEES: ["Please explain the service fee on my account."],
    }
    transactions = []
    for i in range(5000):
        affected = i >= 4900
        occurred = bucket + timedelta(seconds=rng.randrange(840)) if affected else start + timedelta(seconds=rng.randrange(48 * 3600))
        failed = affected or rng.random() < 0.04
        txn = Transaction(
            bank_id=user.bank_id, reference=f"SYN-{payload.seed}-{i:05d}",
            txn_type=TxnType.TRANSFER, txn_channel=rng.choice([TxnChannel.APP, TxnChannel.USSD]) if affected else rng.choice(list(TxnChannel)),
            status=TxnStatus.FAILED if failed else TxnStatus.SUCCESSFUL,
            reversal_status=ReversalStatus.PENDING if failed else ReversalStatus.NONE,
            processor="demo-switch-a" if affected else "demo-switch-b",
            amount=Decimal(rng.randrange(10, 2000) * 100), region=rng.choice(regions), occurred_at=occurred,
        )
        transactions.append(txn)
    db.add_all(transactions)
    db.flush()
    complaints = []
    # Stable baseline: five complaints per historical quarter-hour (960 total).
    normal_issues = [IssueType.FAILED_TRANSFER, IssueType.CARD_ATM, IssueType.POS, IssueType.APP_LOGIN]
    for i in range(1000):
        spike = 960 <= i < 990
        fraud = 990 <= i < 998
        if i < 960:
            occurred = start + timedelta(minutes=(i // 5) * 15, seconds=(i % 5 + 1) * 120)
            issue = normal_issues[i % len(normal_issues)]
        else:
            occurred = bucket + timedelta(seconds=60 + (i - 960) * 18)
            issue = IssueType.FAILED_TRANSFER if spike else IssueType.FRAUD_SCAM if fraud else IssueType.FEES
        txn = transactions[4900 + i - 960] if spike else None
        text = rng.choice(texts[issue])
        complaints.append(Complaint(
            bank_id=user.bank_id, channel=rng.choice(channels), text=text,
            customer_ref=f"synthetic_{i:05d}", region=txn.region if txn else rng.choice(regions),
            language="pcm" if text.startswith("My money don") else "en", occurred_at=occurred,
            issue_type=issue, severity=Severity.HIGH if spike or fraud else Severity.MEDIUM,
            sentiment=Sentiment.NEGATIVE, summary=text, is_fraud=fraud,
            mentioned_amount=txn.amount if txn else None, classified_at=detection_at,
            transaction_id=txn.id if txn else None,
        ))
    db.add_all(complaints)
    db.add_all([
        SystemEvent(bank_id=user.bank_id, event_type=EventType.RELEASE, component="transfer-service",
                    version="v4.2.1", description="SYNTHETIC: app transfer release on demo-switch-a", starts_at=release_at),
        SystemEvent(bank_id=user.bank_id, event_type=EventType.MAINTENANCE, component="email-service",
                    description="SYNTHETIC DECOY: unrelated email maintenance", starts_at=release_at - timedelta(hours=6)),
    ])
    log_event(db, bank_id=user.bank_id, actor=str(user.id), action="synthetic_data_seeded",
              entity_type="bank", entity_id=str(user.bank_id), details={"seed": payload.seed, "complaints": 1000, "transactions": 5000})
    db.commit()
    return {"synthetic": True, "seed": payload.seed, "complaints_created": 1000,
            "transactions_created": 5000, "system_events_created": 2,
            "detection_at": detection_at, "release_at": release_at,
            "note": "Pre-labelled fixtures, not AI classifications. No money moved. Use detection_at as analytics at and incident detection now."}


class TransactionRead(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    reference: str
    txn_type: TxnType
    txn_channel: TxnChannel
    status: TxnStatus
    reversal_status: ReversalStatus
    processor: str | None
    amount: Decimal
    region: str | None
    occurred_at: datetime


class EventRead(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    event_type: EventType
    component: str
    version: str | None
    description: str
    starts_at: datetime
    ends_at: datetime | None


@router.get("/transactions")
def transactions(user: Operator, db: DbSession, status: TxnStatus | None = None,
                 limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    require_demo(user)
    filters = [Transaction.bank_id == user.bank_id]
    if status is not None:
        filters.append(Transaction.status == status)
    total = db.scalar(select(func.count()).select_from(Transaction).where(*filters))
    rows = db.scalars(select(Transaction).where(*filters).order_by(Transaction.occurred_at.desc(), Transaction.id).offset(offset).limit(limit)).all()
    return {"synthetic": True, "total": total, "limit": limit, "offset": offset,
            "items": [TransactionRead.model_validate(row) for row in rows]}


@router.get("/system-events")
def system_events(user: Operator, db: DbSession, limit: int = Query(50, ge=1, le=200)):
    require_demo(user)
    rows = db.scalars(select(SystemEvent).where(SystemEvent.bank_id == user.bank_id).order_by(SystemEvent.starts_at.desc()).limit(limit)).all()
    return {"synthetic": True, "items": [EventRead.model_validate(row) for row in rows]}
