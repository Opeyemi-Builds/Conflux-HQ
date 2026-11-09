"""Bounded, reproducible synthetic fixtures with realistic Nigerian multilingual complaints."""
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from app.ai.fallback import rules_classify
from app.api.deps import DbSession, Operator
from app.core.config import get_settings
from app.core.privacy import mask_pii, pseudonymise
from app.db.base import utcnow
from app.models import Bank, Complaint, Draft, Incident, PaymentException, PaymentProposal, SystemEvent, Transaction
from app.models.enums import (
    Channel,
    EventType,
    IssueType,
    ReversalStatus,
    Sentiment,
    Severity,
    TxnChannel,
    TxnStatus,
    TxnType,
)
from app.services.audit import log_event
from app.services.demo_auth import DEMO_BANK_ID
from app.services.fraud import route_classification_to_fraud

router = APIRouter(prefix="/synthetic", tags=["synthetic demo data"])

# Authentic Nigerian banking complaint templates across English, Pidgin, Yoruba, Hausa, and Igbo mixes.
_TEMPLATES: dict[IssueType, list[tuple[str, str, str]]] = {
    IssueType.FAILED_TRANSFER: [
        ("en", "My NIP transfer of ₦{amt} to account [ACCOUNT] failed on the mobile app since {time}, but my account was debited and still not reversed.", "Customer debited ₦{amt} for failed NIP transfer with no reversal."),
        ("pidgin", "Abeg wetin dey happen? My money don enter nowhere! I send ₦{amt} via USSD since {time}, una debit me sharp sharp but receiver never see alert.", "Customer in Pidgin reports ₦{amt} USSD transfer debited without credit."),
        ("pidgin", "Una app don chop my ₦{amt} since {time} o. Transfer failed on screen, yet debit alert enter immediately. Abeg reverse am.", "Failed app transfer of ₦{amt} with immediate debit and pending reversal."),
        ("yoruba_mix", "E jowo Zymic Bank, mo ti transfer ₦{amt} lati {time} on USSD, owo mi ti debited sugbon ko de odo beneficiary.", "Yoruba-English complaint: ₦{amt} USSD transfer debited without reaching beneficiary."),
        ("igbo_mix", "Biko, my transfer of ₦{amt} since {time} failed on the app, ego m was debited and recipient adịghị credited till now.", "Igbo-English complaint: ₦{amt} app transfer failed after account debit."),
        ("hausa_mix", "Don Allah check my account [ACCOUNT], an debita kudi na ₦{amt} since {time} on USSD transfer amma transfer failed.", "Hausa-English complaint: ₦{amt} USSD transfer failed after debit."),
        ("en", "Urgent: USSD transfer of ₦{amt} at {time} returned session timeout through the switch, yet my balance dropped by ₦{amt}.", "USSD session timeout caused unreversed ₦{amt} transfer debit."),
        ("pidgin", "Why una USSD code dey deduct money without sending am? ₦{amt} don hang since {time}, my money don enter nowhere.", "Pidgin report of ₦{amt} hanging after failed USSD transfer."),
    ],
    IssueType.FRAUD_SCAM: [
        ("en", "Someone called me from [PHONE] pretending to be a fake bank agent and asked for my OTP, then ₦{amt} left my account unauthorized.", "Customer targeted by fake bank agent OTP social-engineering scam."),
        ("pidgin", "Abeg block my account sharp! Fake agent call me ask for my OTP say dem wan upgrade my tier, next thing ₦{amt} comot unauthorized.", "Pidgin report of fake agent OTP scam and unauthorized debit."),
        ("yoruba_mix", "E gba mi o, fake bank agent called my line asking for OTP and gbajie mi of ₦{amt} unauthorized transfer.", "Yoruba-English report of fake agent OTP scam."),
        ("hausa_mix", "Don Allah help, someone called claiming to be bank staff for yaudarar OTP scam and moved ₦{amt} unauthorized.", "Hausa-English report of phishing OTP call and unauthorized debit."),
    ],
    IssueType.CARD_ATM: [
        ("en", "The ATM at {region} branch debited my account ₦{amt} at {time} without dispensing cash, and the dispense error has not reversed.", "ATM dispense error of ₦{amt} in {region} awaiting reversal."),
        ("pidgin", "ATM for {region} swallow my card and still debit me ₦{amt} when cash no come out since {time}. Abeg refund my money.", "Pidgin report of ATM card capture and ₦{amt} dispense failure."),
        ("igbo_mix", "Biko, ATM dispensed nothing at {region} branch since {time}, ego ọpụpụ failed but I got a ₦{amt} debit alert.", "Igbo-English report of ₦{amt} ATM debit without cash dispensed."),
    ],
    IssueType.POS: [
        ("en", "My POS payment of ₦{amt} at a supermarket in {region} declined on the terminal at {time}, but my account was debited.", "Declined POS terminal transaction in {region} debited ₦{amt}."),
        ("pidgin", "POS machine print declined receipt for {region} since {time}, merchant no see money, but una debit me ₦{amt}.", "Pidgin report of declined POS payment with ₦{amt} debit."),
        ("hausa_mix", "Muna samun al'amari with POS payment in {region}: terminal declined ₦{amt} at {time} but debit alert came in.", "Hausa-English report of failed POS debit of ₦{amt}."),
    ],
    IssueType.APP_LOGIN: [
        ("en", "I cannot sign into the mobile banking app since {time}; login keeps timing out after entering my password.", "Customer unable to log into mobile banking app due to timeout."),
        ("pidgin", "Una mobile app no dey open since {time} o, anytime I try login e go just crash.", "Pidgin report of mobile app crash during login."),
        ("hausa_mix", "Ba zan iya shiga the banking app since {time}, login screen keeps failing with an error.", "Hausa-English report of mobile app sign-in failure."),
    ],
    IssueType.FEES: [
        ("en", "Please explain the unexpected ₦{amt} SMS maintenance and service fee deducted from my account at {time}.", "Customer disputing ₦{amt} account maintenance/service charge."),
        ("pidgin", "Why una dey charge me ₦{amt} service fee and stamp duty on top my account since {time}?", "Pidgin inquiry over ₦{amt} service fee deduction."),
    ],
}


class SeedRequest(BaseModel):
    seed: int = Field(default=42, ge=0, le=2147483647)
    at: datetime | None = None
    reset: bool = False

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
    """Seed the 48-hour Nigerian banking dataset once into an empty demo bank (or reset when requested)."""
    require_demo(user)
    db.execute(select(Bank).where(Bank.id == user.bank_id).with_for_update()).scalar_one()
    if payload.reset:
        # Remove dependent reconciliation records before their complaint/transaction parents.
        exception_ids = select(PaymentException.id).where(PaymentException.bank_id == user.bank_id)
        db.query(PaymentProposal).filter(
            PaymentProposal.bank_id == user.bank_id,
            PaymentProposal.exception_id.in_(exception_ids),
        ).delete(synchronize_session=False)
        db.query(PaymentException).filter(PaymentException.bank_id == user.bank_id).delete(
            synchronize_session=False
        )
        inc_ids = select(Incident.id).where(Incident.bank_id == user.bank_id)
        db.query(Draft).filter(Draft.incident_id.in_(inc_ids)).delete(synchronize_session=False)
        for model in (Complaint, Transaction, SystemEvent, Incident):
            db.query(model).filter(model.bank_id == user.bank_id).delete(synchronize_session=False)
        db.flush()
    else:
        for model in (Complaint, Transaction, SystemEvent):
            if db.scalar(select(func.count()).select_from(model).where(model.bank_id == user.bank_id)):
                raise HTTPException(409, "Demo bank already contains data; seed never overwrites existing records")

    rng = random.Random(payload.seed)
    anchor = (payload.at or utcnow()).astimezone(timezone.utc)
    bucket = anchor.replace(minute=anchor.minute - anchor.minute % 15, second=0, microsecond=0)
    detection_at = bucket + timedelta(minutes=14, seconds=59)
    release_at = bucket - timedelta(minutes=12)
    start = bucket - timedelta(hours=48)
    channels = list(Channel)
    regions = ["Lagos", "Abuja", "Kano", "Port Harcourt", "Ibadan", "Enugu", "Kaduna"]

    transactions = []
    for i in range(5000):
        affected = i >= 4900
        occurred = (
            bucket + timedelta(seconds=rng.randrange(840))
            if affected
            else start + timedelta(seconds=rng.randrange(48 * 3600))
        )
        failed = affected or rng.random() < 0.04
        txn_type = (
            TxnType.TRANSFER
            if affected
            else rng.choices(
                [TxnType.TRANSFER, TxnType.POS, TxnType.ATM, TxnType.BILL, TxnType.AIRTIME],
                weights=[50, 22, 15, 8, 5],
                k=1,
            )[0]
        )
        txn = Transaction(
            bank_id=user.bank_id,
            reference=f"SYN-{payload.seed}-{i:05d}",
            txn_type=txn_type,
            txn_channel=rng.choice([TxnChannel.APP, TxnChannel.USSD]) if affected else rng.choice(list(TxnChannel)),
            status=TxnStatus.FAILED if failed else TxnStatus.SUCCESSFUL,
            reversal_status=ReversalStatus.PENDING if failed else ReversalStatus.NONE,
            processor="demo-switch-a" if affected else rng.choice(["demo-switch-a", "demo-switch-b"]),
            amount=Decimal(rng.randrange(10, 2000) * 100),
            region=rng.choice(regions[:5]),
            occurred_at=occurred,
        )
        transactions.append(txn)
    db.add_all(transactions)
    db.flush()

    complaints = []
    # Stable baseline: 5 complaints per historical quarter-hour (960 total), plus 30 spike, 8 fraud, 2 isolated fee complaints.
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
        region = txn.region if txn else rng.choice(regions[:5])
        amount_val = txn.amount if txn else Decimal(rng.choice([500, 1500, 5000, 12000, 25000, 45000, 75000, 120000]))
        amt_fmt = f"{int(amount_val):,}"
        time_label = occurred.strftime("%H:%M")

        if spike and i - 960 < 12:
            lang, raw_template, summary_template = _TEMPLATES[issue][0]
        else:
            lang, raw_template, summary_template = rng.choice(_TEMPLATES[issue])
        text = mask_pii(raw_template.format(amt=amt_fmt, time=time_label, region=region))
        summary = summary_template.format(amt=amt_fmt, time=time_label, region=region)
        classification = rules_classify(text)
        confidence = round(rng.uniform(0.82, 0.96), 2)
        channel = (
            rng.choice([Channel.IN_APP, Channel.X, Channel.CALL, Channel.INSTAGRAM])
            if spike
            else rng.choice(channels)
        )
        # Create realistic repeat complainants (~18% repeat rate)
        customer_pool_id = i % 380 if not spike else 380 + (i - 960) % 18
        complaints.append(
            Complaint(
                bank_id=user.bank_id,
                channel=channel,
                text=text,
                customer_ref=pseudonymise(f"234803{customer_pool_id:07d}"),
                region=region,
                language=lang,
                occurred_at=occurred,
                issue_type=issue,
                severity=Severity.CRITICAL if fraud else Severity.HIGH if spike else Severity.MEDIUM,
                sentiment=Sentiment.NEGATIVE,
                summary=summary,
                is_fraud=fraud,
                mentioned_amount=amount_val if issue != IssueType.APP_LOGIN else None,
                mentioned_time=f"since {time_label}",
                classification_confidence=confidence,
                payment_category=classification.payment_category,
                classification_explanation=classification.explanation,
                evidence_phrases=classification.evidence_phrases,
                review_status="needs_review" if fraud or confidence < get_settings().classification_review_threshold else "auto",
                routing_queue="fraud_security" if fraud else "standard",
                classified_at=detection_at,
                transaction_id=txn.id if txn else None,
            )
        )
    db.add_all(complaints)
    db.flush()
    for complaint in complaints:
        if complaint.is_fraud:
            route_classification_to_fraud(db, complaint, actor="synthetic_seed")
    db.add_all([
        SystemEvent(
            bank_id=user.bank_id,
            event_type=EventType.RELEASE,
            component="transfer-service",
            version="v4.2.1",
            description="SYNTHETIC: app and USSD transfer release on demo-switch-a",
            starts_at=release_at,
        ),
        SystemEvent(
            bank_id=user.bank_id,
            event_type=EventType.MAINTENANCE,
            component="email-service",
            description="SYNTHETIC DECOY: unrelated email notification maintenance",
            starts_at=release_at - timedelta(hours=4),
        ),
    ])
    log_event(
        db,
        bank_id=user.bank_id,
        actor=str(user.id),
        action="synthetic_data_seeded",
        entity_type="bank",
        entity_id=str(user.bank_id),
        details={"seed": payload.seed, "complaints": 1000, "transactions": 5000},
    )
    db.commit()
    return {
        "synthetic": True,
        "seed": payload.seed,
        "complaints_created": 1000,
        "transactions_created": 5000,
        "system_events_created": 2,
        "detection_at": detection_at,
        "release_at": release_at,
        "note": "Multilingual Nigerian banking dataset seeded. Use detection_at as analytics at and incident detection now.",
    }


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
def transactions(
    user: Operator,
    db: DbSession,
    status: TxnStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    require_demo(user)
    filters = [Transaction.bank_id == user.bank_id]
    if status is not None:
        filters.append(Transaction.status == status)
    total = db.scalar(select(func.count()).select_from(Transaction).where(*filters))
    rows = db.scalars(
        select(Transaction)
        .where(*filters)
        .order_by(Transaction.occurred_at.desc(), Transaction.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "synthetic": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [TransactionRead.model_validate(row) for row in rows],
    }


@router.get("/system-events")
def system_events(user: Operator, db: DbSession, limit: int = Query(50, ge=1, le=200)):
    require_demo(user)
    rows = db.scalars(
        select(SystemEvent)
        .where(SystemEvent.bank_id == user.bank_id)
        .order_by(SystemEvent.starts_at.desc())
        .limit(limit)
    ).all()
    return {"synthetic": True, "items": [EventRead.model_validate(row) for row in rows]}
