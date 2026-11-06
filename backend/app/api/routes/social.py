"""Tenant-safe bank identity management and official-adapter/simulator intake."""
import hashlib
import uuid
from collections import defaultdict
from datetime import timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
import secrets

from app.models import Bank
from app.models.enums import BankStatus
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminUser, AuthUser, DbSession
from app.core.config import get_settings
from app.core.privacy import mask_pii, pseudonymise
from app.db.base import utcnow
from app.models import BankAlias, Complaint, SocialReceipt
from app.models.enums import Channel, IssueType, Sentiment, Severity
from app.services.audit import log_event
from app.services.demo_auth import DEMO_BANK_ID
from app.services.social_intake import AliasBatch, AliasInput, SocialEvent, analyze, matches

router = APIRouter(prefix="/social", tags=["social monitoring"])
_PLATFORM_CHANNEL = {"x": Channel.X, "instagram": Channel.INSTAGRAM, "facebook": Channel.FACEBOOK}
_DEFAULTS = {
    "access bank": [("name", None), ("contextual", None), ("handle", "x"), ("hashtag", "x")],
    "united bank for africa": [("name", None), ("handle", "x"), ("hashtag", "x")],
}


def _seed_defaults(db, bank_id: uuid.UUID, bank_name: str):
    name = " ".join(bank_name.casefold().split())
    entries = [(name, "name", None)]
    for kind, platform in _DEFAULTS.get(name, []):
        short = "uba" if name == "united bank for africa" else "access"
        value = {"name": name, "contextual": short, "handle": "@ubagroup" if short == "uba" else "@accessbankplc",
                 "hashtag": "#uba" if short == "uba" else "#accessbank"}[kind]
        entries.append((value.casefold(), kind, platform))
    existing = {a.value for a in db.scalars(select(BankAlias).where(BankAlias.bank_id == bank_id)).all()}
    for value, kind, platform in entries:
        if value not in existing:
            db.add(BankAlias(bank_id=bank_id, value=value, kind=kind, platform=platform))


def require_adapter(authorization: str | None = Header(default=None)):
    expected = get_settings().social_adapter_token
    if len(expected) < 32:
        raise HTTPException(503, "Social adapter credential is not configured")
    supplied = authorization.removeprefix("Bearer ") if authorization and authorization.startswith("Bearer ") else ""
    if not secrets.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(401, "Invalid social adapter credential", headers={"WWW-Authenticate": "Bearer"})


@router.get("/monitoring-rules", dependencies=[Depends(require_adapter)])
def monitoring_rules(db: DbSession, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
    """Service-only rule discovery. Refresh periodically; never expose the credential to browsers."""
    banks = db.scalars(select(Bank).where(Bank.status == BankStatus.ACTIVE)
                       .order_by(Bank.id).offset(offset).limit(limit)).all()
    items = []
    for bank in banks:
        aliases = db.scalars(select(BankAlias).where(BankAlias.bank_id == bank.id)).all()
        # Bank name works immediately after registration, even before aliases are configured.
        rules = [{"value": bank.name.casefold(), "kind": "name", "platform": None}]
        rules.extend({"value": a.value, "kind": a.kind, "platform": a.platform} for a in aliases)
        items.append({"bank_id": str(bank.id), "bank_name": bank.name, "aliases": rules})
    return {"items": items, "offset": offset, "limit": limit, "next_offset": offset + limit if len(banks) == limit else None}


@router.get("/aliases")
def list_aliases(user: AuthUser, db: DbSession):
    bank = db.get(Bank, user.bank_id)
    if db.scalar(select(BankAlias.id).where(BankAlias.bank_id == bank.id).limit(1)) is None:
        _seed_defaults(db, bank.id, bank.name)
        db.commit()
    aliases = db.scalars(select(BankAlias).where(BankAlias.bank_id == user.bank_id).order_by(BankAlias.kind, BankAlias.value)).all()
    return {"bank_id": str(user.bank_id), "items": [{"id": str(a.id), "value": a.value, "kind": a.kind, "platform": a.platform} for a in aliases]}


@router.put("/aliases")
def replace_aliases(payload: AliasBatch, admin: AdminUser, db: DbSession):
    normalized = [item.model_dump() for item in payload.aliases]
    values = [item["value"] for item in normalized]
    if len(set(values)) != len(values):
        raise HTTPException(422, "Alias values must be unique within a bank")
    db.query(BankAlias).filter(BankAlias.bank_id == admin.bank_id).delete(synchronize_session=False)
    db.add_all([BankAlias(bank_id=admin.bank_id, **item) for item in normalized])
    log_event(db, bank_id=admin.bank_id, actor=str(admin.id), action="social_aliases_replaced",
              entity_type="bank", entity_id=str(admin.bank_id), details={"count": len(normalized)})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Alias update conflicts with another change") from None
    return list_aliases(admin, db)


@router.post("/events", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_adapter)])
def receive_social_event(event: SocialEvent, db: DbSession):
    """Receive collected posts from a trusted scanner; no browser/manual submission required."""
    banks = db.scalars(select(Bank).where(Bank.status == BankStatus.ACTIVE)).all()
    aliases = db.scalars(select(BankAlias)).all()
    active_bank_ids = {bank.id for bank in banks}
    grouped = defaultdict(list)
    for bank in banks:
        if matches(event.text, " ".join(bank.name.casefold().split()), "name"):
            grouped[bank.id].append(bank.name.casefold())
    for alias in aliases:
        if alias.bank_id not in active_bank_ids:
            continue
        if alias.platform is None or alias.platform == event.platform:
            if matches(event.text, alias.value, alias.kind):
                grouped[alias.bank_id].append(alias.value)
    if not grouped:
        return {"accepted": False, "reason": "no_bank_match", "analysis_method": "demo_rules_v1"}
    if len(grouped) > 1:
        return {"accepted": False, "reason": "ambiguous_bank_match", "candidate_count": len(grouped), "analysis_method": "demo_rules_v1"}
    bank_id, matched_aliases = next(iter(grouped.items()))
    existing = db.scalar(select(SocialReceipt).where(
        SocialReceipt.bank_id == bank_id, SocialReceipt.platform == event.platform,
        SocialReceipt.post_id == event.post_id))
    if existing:
        return {"accepted": True, "duplicate": True, "complaint_id": str(existing.complaint_id),
                "analysis_method": existing.analysis_method}

    result = analyze(event.text)
    occurred = event.occurred_at.astimezone(timezone.utc)
    complaint = Complaint(bank_id=bank_id, channel=_PLATFORM_CHANNEL[event.platform],
        text=mask_pii(event.text), customer_ref=pseudonymise(event.author_ref), region=event.region,
        language=None, occurred_at=occurred, issue_type=IssueType(result["issue_type"]) if result.get("issue_type") else None,
        severity=Severity(result["severity"]) if result.get("severity") else None,
        sentiment=Sentiment.NEGATIVE if result.get("issue_type") else None,
        summary=mask_pii(event.text)[:500] if result.get("issue_type") else None,
        is_fraud=result.get("is_fraud", False), classified_at=utcnow() if result.get("issue_type") else None)
    db.add(complaint)
    db.flush()
    receipt = SocialReceipt(bank_id=bank_id, platform=event.platform, post_id=event.post_id,
        complaint_id=complaint.id, source_url=event.source_url, matched_aliases=sorted(set(matched_aliases)),
        analysis_method="demo_rules_v1")
    db.add(receipt)
    log_event(db, bank_id=bank_id, actor="social_adapter", action="social_mention_ingested",
              entity_type="complaint", entity_id=str(complaint.id),
              details={"platform": event.platform, "post_hash": hashlib.sha256(event.post_id.encode()).hexdigest()[:16],
                       "matched_aliases": receipt.matched_aliases, "analysis_method": receipt.analysis_method})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(SocialReceipt).where(
            SocialReceipt.bank_id == bank_id, SocialReceipt.platform == event.platform,
            SocialReceipt.post_id == event.post_id))
        if existing:
            return {"accepted": True, "duplicate": True, "complaint_id": str(existing.complaint_id),
                    "analysis_method": existing.analysis_method}
        raise HTTPException(409, "Unable to persist social event") from None
    return {"accepted": True, "duplicate": False, "bank_id": str(bank_id),
            "complaint_id": str(complaint.id), "channel": event.platform,
            "matched_aliases": receipt.matched_aliases, "issue_type": result.get("issue_type"),
            "is_fraud": result.get("is_fraud", False), "analysis_method": "demo_rules_v1",
            "synthetic": event.synthetic, "source_url": event.source_url}
