"""Tenant-safe bank identity management, X v2 stream adapter endpoints, and social intake."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import secrets
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.x_adapter import (
    XAdapter,
    get_x_adapter_status,
    replay_recorded_mentions,
    sync_stream_rules,
)
from app.api.deps import AdminUser, AuthUser, DbSession, Operator
from app.core.config import get_settings
from app.core.privacy import mask_pii, pseudonymise
from app.db.base import utcnow
from app.models import Bank, BankAlias, Complaint, SocialReceipt
from app.models.enums import BankStatus, Channel, IssueType, JobKind, Sentiment, Severity
from app.services.audit import log_event
from app.services.complaint_service import _enqueue_for_complaint
from app.services.demo_auth import DEMO_BANK_ID
from app.services.social_intake import AliasBatch, SocialEvent, analyze, matches, reputation_signals
from app.services.worker import drain_jobs, enqueue_job

router = APIRouter(prefix="/social", tags=["social monitoring"])
_PLATFORM_CHANNEL = {"x": Channel.X, "instagram": Channel.INSTAGRAM, "facebook": Channel.FACEBOOK}
_DEFAULTS = {
    "access bank": [("name", None), ("contextual", None), ("handle", "x"), ("hashtag", "x")],
    "united bank for africa": [("name", None), ("handle", "x"), ("hashtag", "x")],
    "zymic bank": [("name", None), ("handle", "x"), ("hashtag", "x")],
}


class XReplayRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=200)
    at: AwareDatetime | None = None
    auto_drain: bool = True


class XPullRequest(BaseModel):
    mode: str = Field(default="recent_search", pattern=r"^(recent_search|filtered_stream)$")
    handle: str | None = Field(
        default=None,
        description="Optional X handle to fetch mentions for (e.g. '@myaccessbank' or '@accessbank_help')",
    )
    handles: list[str] | None = Field(
        default=None,
        description="Optional list of X handles to fetch mentions for",
    )
    max_results: int = Field(default=15, ge=1, le=100)
    since_id: str | None = None
    fallback_to_replay: bool = False
    auto_drain: bool = True


class XSyncRulesRequest(BaseModel):
    existing_remote_rules: list[dict] | None = None


def _seed_defaults(db, bank_id: uuid.UUID, bank_name: str):
    name = " ".join(bank_name.casefold().split())
    entries = [(name, "name", None)]
    for kind, platform in _DEFAULTS.get(name, []):
        if name == "united bank for africa":
            short, handle, hashtag = "uba", "@ubagroup", "#uba"
        elif name == "zymic bank":
            short, handle, hashtag = "zymic", "@zymicbank", "#zymicbank"
        else:
            short, handle, hashtag = "access", "@accessbankplc", "#accessbank"
        value = {"name": name, "contextual": short, "handle": handle, "hashtag": hashtag}[kind]
        entries.append((value.casefold(), kind, platform))
    if name in ("zymic bank", "access bank"):
        entries.extend([
            ("@myaccessbank", "handle", "x"),
            ("@accessbank_help", "handle", "x"),
        ])
    if name == "zymic bank":
        entries.append(("@confluxbankhq", "handle", "x"))
    existing = {a.value for a in db.scalars(select(BankAlias).where(BankAlias.bank_id == bank_id)).all()}
    for value, kind, platform in entries:
        if value not in existing:
            existing.add(value)
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
    banks = db.scalars(
        select(Bank).where(Bank.status == BankStatus.ACTIVE).order_by(Bank.id).offset(offset).limit(limit)
    ).all()
    items = []
    for bank in banks:
        aliases = db.scalars(select(BankAlias).where(BankAlias.bank_id == bank.id)).all()
        rules = [{"value": bank.name.casefold(), "kind": "name", "platform": None}]
        rules.extend({"value": a.value, "kind": a.kind, "platform": a.platform} for a in aliases)
        items.append({"bank_id": str(bank.id), "bank_name": bank.name, "aliases": rules})
    return {
        "items": items,
        "offset": offset,
        "limit": limit,
        "next_offset": offset + limit if len(banks) == limit else None,
    }


@router.get("/aliases")
def list_aliases(user: AuthUser, db: DbSession):
    bank = db.get(Bank, user.bank_id)
    if db.scalar(select(BankAlias.id).where(BankAlias.bank_id == bank.id).limit(1)) is None:
        _seed_defaults(db, bank.id, bank.name)
        db.commit()
    aliases = db.scalars(
        select(BankAlias).where(BankAlias.bank_id == user.bank_id).order_by(BankAlias.kind, BankAlias.value)
    ).all()
    return {
        "bank_id": str(user.bank_id),
        "items": [{"id": str(a.id), "value": a.value, "kind": a.kind, "platform": a.platform} for a in aliases],
    }


@router.put("/aliases")
def replace_aliases(payload: AliasBatch, admin: AdminUser, db: DbSession):
    normalized = [item.model_dump() for item in payload.aliases]
    values = [item["value"] for item in normalized]
    if len(set(values)) != len(values):
        raise HTTPException(422, "Alias values must be unique within a bank")
    db.query(BankAlias).filter(BankAlias.bank_id == admin.bank_id).delete(synchronize_session=False)
    db.add_all([BankAlias(bank_id=admin.bank_id, **item) for item in normalized])
    enqueue_job(
        db,
        bank_id=admin.bank_id,
        kind=JobKind.SYNC_SOCIAL_RULES,
        payload={"bank_id": str(admin.bank_id)},
        idempotency_key="x_sync_rules",
        reopen_completed=True,
    )
    log_event(
        db,
        bank_id=admin.bank_id,
        actor=str(admin.id),
        action="social_aliases_replaced",
        entity_type="bank",
        entity_id=str(admin.bank_id),
        details={"count": len(normalized)},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Alias update conflicts with another change") from None
    return list_aliases(admin, db)


def ingest_social_event(db: Session, event: SocialEvent) -> dict:
    """Route a social mention to one or more tenants (via rule tags or aliases) and persist complaints."""
    banks = db.scalars(select(Bank).where(Bank.status == BankStatus.ACTIVE)).all()
    aliases = db.scalars(select(BankAlias)).all()
    active_bank_ids = {bank.id for bank in banks}
    grouped: dict[uuid.UUID, list[str]] = defaultdict(list)
    explicit_bank_ids: set[uuid.UUID] = set()

    # 1. Route on X Filtered Stream rule tags (`tenant:<bank_id>`)
    for raw_tag in event.matching_rule_tags:
        tag = raw_tag.strip()
        if tag.startswith("tenant:"):
            try:
                tid = uuid.UUID(tag.removeprefix("tenant:"))
            except ValueError:
                continue
            if tid in active_bank_ids:
                grouped[tid].append(tag)
                explicit_bank_ids.add(tid)

    # 2. Match bank names and configured aliases (`@handle`, `#hashtag`, `contextual`)
    for bank in banks:
        if matches(event.text, " ".join(bank.name.casefold().split()), "name"):
            grouped[bank.id].append(bank.name.casefold())
    for alias in aliases:
        if alias.bank_id not in active_bank_ids:
            continue
        if alias.platform is None or alias.platform == event.platform:
            if matches(event.text, alias.value, alias.kind):
                grouped[alias.bank_id].append(alias.value)
                if alias.kind == "handle":
                    explicit_bank_ids.add(alias.bank_id)

    if not grouped:
        return {"accepted": False, "reason": "no_bank_match", "analysis_method": "demo_rules_v1"}

    if len(grouped) > 1:
        # One post tagging multiple banks by explicit @handle or stream rule tag creates one complaint per tenant.
        # Untagged posts matching multiple banks only by name/contextual keyword remain ambiguous.
        if len(explicit_bank_ids) >= 2:
            target_banks = {bid: grouped[bid] for bid in sorted(explicit_bank_ids, key=str)}
        elif len(explicit_bank_ids) == 1:
            only_id = next(iter(explicit_bank_ids))
            target_banks = {only_id: grouped[only_id]}
        else:
            return {
                "accepted": False,
                "reason": "ambiguous_bank_match",
                "candidate_count": len(grouped),
                "analysis_method": "demo_rules_v1",
            }
    else:
        target_banks = dict(grouped)

    result = analyze(event.text)
    occurred = event.occurred_at.astimezone(timezone.utc)
    created_complaint_ids: list[str] = []
    all_complaint_ids: list[str] = []
    matched_bank_ids: list[str] = []
    all_aliases: list[str] = []
    all_duplicates = True

    for bank_id, matched_aliases in target_banks.items():
        matched_bank_ids.append(str(bank_id))
        clean_aliases = sorted(set(matched_aliases))
        all_aliases.extend(clean_aliases)
        existing = db.scalar(
            select(SocialReceipt).where(
                SocialReceipt.bank_id == bank_id,
                SocialReceipt.platform == event.platform,
                SocialReceipt.post_id == event.post_id,
            )
        )
        if existing:
            all_complaint_ids.append(str(existing.complaint_id))
            continue

        all_duplicates = False
        complaint = Complaint(
            bank_id=bank_id,
            channel=_PLATFORM_CHANNEL[event.platform],
            text=mask_pii(event.text),
            customer_ref=pseudonymise(event.author_ref),
            region=event.region,
            language=None,
            occurred_at=occurred,
            issue_type=IssueType(result["issue_type"]) if result.get("issue_type") else None,
            severity=Severity(result["severity"]) if result.get("severity") else None,
            sentiment=Sentiment.NEGATIVE if result.get("issue_type") else None,
            summary=mask_pii(event.text)[:500] if result.get("issue_type") else None,
            is_fraud=result.get("is_fraud", False),
            classified_at=utcnow() if result.get("issue_type") else None,
        )
        db.add(complaint)
        db.flush()
        _enqueue_for_complaint(db, bank_id, complaint)
        reputation = reputation_signals(event.text, event.public_metrics)
        receipt = SocialReceipt(
            bank_id=bank_id,
            platform=event.platform,
            post_id=event.post_id,
            complaint_id=complaint.id,
            source_url=event.source_url,
            matched_aliases=clean_aliases,
            author_ref_hash=hashlib.sha256((event.author_ref or "anonymous").encode()).hexdigest(),
            public_metrics=event.public_metrics,
            reputation_flags=reputation["flags"],
            reputation_score=reputation["score"],
            analysis_method="demo_rules_v2",
        )
        db.add(receipt)
        log_event(
            db,
            bank_id=bank_id,
            actor="social_adapter",
            action="social_mention_ingested",
            entity_type="complaint",
            entity_id=str(complaint.id),
            details={
                "platform": event.platform,
                "post_hash": hashlib.sha256(event.post_id.encode()).hexdigest()[:16],
                "matched_aliases": clean_aliases,
                "analysis_method": receipt.analysis_method,
                "reputation_flags": reputation["flags"],
                "reputation_score": reputation["score"],
            },
        )
        created_complaint_ids.append(str(complaint.id))
        all_complaint_ids.append(str(complaint.id))

    if all_duplicates:
        return {
            "accepted": True,
            "duplicate": True,
            "complaint_id": all_complaint_ids[0],
            "complaint_ids": all_complaint_ids,
            "bank_ids": matched_bank_ids,
            "analysis_method": "demo_rules_v1",
        }

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        first_bank_id = next(iter(target_banks))
        existing = db.scalar(
            select(SocialReceipt).where(
                SocialReceipt.bank_id == first_bank_id,
                SocialReceipt.platform == event.platform,
                SocialReceipt.post_id == event.post_id,
            )
        )
        if existing:
            return {
                "accepted": True,
                "duplicate": True,
                "complaint_id": str(existing.complaint_id),
                "analysis_method": existing.analysis_method,
            }
        raise HTTPException(409, "Unable to persist social event") from None

    return {
        "accepted": True,
        "duplicate": False,
        "bank_id": matched_bank_ids[0],
        "bank_ids": matched_bank_ids,
        "complaint_id": all_complaint_ids[0],
        "complaint_ids": all_complaint_ids,
        "tenant_fanout_count": len(matched_bank_ids),
        "channel": event.platform,
        "matched_aliases": sorted(set(all_aliases)),
        "issue_type": result.get("issue_type"),
        "is_fraud": result.get("is_fraud", False),
        "analysis_method": "demo_rules_v2",
        "reputation_flags": sorted(set(sum([reputation_signals(event.text, event.public_metrics)["flags"] for _ in [0]], []))),
        "reputation_score": reputation_signals(event.text, event.public_metrics)["score"],
        "synthetic": event.synthetic,
        "source_url": event.source_url,
    }


@router.post("/events", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_adapter)])
def receive_social_event(event: SocialEvent, db: DbSession):
    """Receive collected posts from a trusted scanner; no browser/manual submission required."""
    return ingest_social_event(db, event)


@router.get("/x/status")
def x_adapter_status(user: AuthUser, db: DbSession):
    """Inspect shared X stream connection mode, compiled tenant rules, and daily pay-per-use spend cap."""
    bank = db.get(Bank, user.bank_id)
    if bank and db.scalar(select(BankAlias.id).where(BankAlias.bank_id == bank.id).limit(1)) is None:
        _seed_defaults(db, bank.id, bank.name)
        db.commit()
    return get_x_adapter_status(db)


@router.post("/x/sync-rules")
def x_sync_rules(
    user: Operator,
    db: DbSession,
    payload: XSyncRulesRequest | None = None,
):
    """Idempotently diff and sync active tenant X handle rules against the shared X Filtered Stream."""
    bank = db.get(Bank, user.bank_id)
    if bank and db.scalar(select(BankAlias.id).where(BankAlias.bank_id == bank.id).limit(1)) is None:
        _seed_defaults(db, bank.id, bank.name)
        db.commit()
    existing = payload.existing_remote_rules if payload else None
    return sync_stream_rules(db, existing_remote_rules=existing, actor=str(user.id))


@router.post("/x/ingest-raw", status_code=status.HTTP_202_ACCEPTED)
def x_ingest_raw(raw_payload: dict, user: Operator, db: DbSession):
    """Ingest a native X API v2 Filtered Stream / Recent Search JSON payload through XAdapter."""
    if "data" not in raw_payload and "id" not in raw_payload:
        raise HTTPException(422, "Payload must contain an X v2 'data' object with 'id' and 'text'")
    adapter = XAdapter(db)
    return adapter.ingest_raw_v2_payload(raw_payload)


def _ensure_handles_for_bank(db: Session, bank_id: uuid.UUID, requested_handles: list[str]) -> list[str]:
    existing = {
        a.value
        for a in db.scalars(select(BankAlias).where(BankAlias.bank_id == bank_id)).all()
    }
    normalized: list[str] = []
    added = False
    for raw in requested_handles:
        if not raw or not raw.strip():
            continue
        clean = "@" + raw.strip().lstrip("@").casefold()
        if clean not in normalized:
            normalized.append(clean)
        if clean not in existing:
            existing.add(clean)
            db.add(BankAlias(bank_id=bank_id, value=clean, kind="handle", platform="x"))
            added = True
    if added:
        db.commit()
    return normalized


@router.get("/x/pull")
def x_pull_live_get(
    user: Operator,
    db: DbSession,
    handle: str = Query(
        default="@myaccessbank",
        description="X handle to fetch latest mentions for (e.g. @myaccessbank or @accessbank_help)",
    ),
    max_results: int = Query(default=15, ge=1, le=100),
    since_id: str | None = Query(default=None),
    auto_drain: bool = Query(default=True),
):
    """Fetch the latest live mentions for an X handle (defaults to `@myaccessbank`) via X API v2 Recent Search."""
    payload = XPullRequest(
        mode="recent_search",
        handle=handle,
        max_results=max_results,
        since_id=since_id,
        fallback_to_replay=False,
        auto_drain=auto_drain,
    )
    return x_pull_live_or_fallback(user=user, db=db, payload=payload)


@router.post("/x/pull")
def x_pull_live_or_fallback(
    user: Operator,
    db: DbSession,
    payload: XPullRequest | None = None,
):
    """Pull live mentions from X API v2 (`recent_search` or `filtered_stream`)."""
    bank = db.get(Bank, user.bank_id)
    if bank and db.scalar(select(BankAlias.id).where(BankAlias.bank_id == bank.id).limit(1)) is None:
        _seed_defaults(db, bank.id, bank.name)
        db.commit()
    req = payload or XPullRequest()
    requested_handles: list[str] = []
    if req.handle:
        requested_handles.append(req.handle)
    if req.handles:
        requested_handles.extend(req.handles)
    scoped_handles = (
        _ensure_handles_for_bank(db, user.bank_id, requested_handles)
        if requested_handles
        else None
    )
    adapter = XAdapter(db)
    if req.mode == "filtered_stream":
        pull_result = adapter.stream_filtered_batch(
            max_posts=req.max_results,
            fallback_to_replay=req.fallback_to_replay,
        )
    else:
        pull_result = adapter.pull_recent_mentions(
            max_results=req.max_results,
            since_id=req.since_id,
            handles=scoped_handles,
            target_bank_id=user.bank_id,
            fallback_to_replay=req.fallback_to_replay,
        )
    worker_result = drain_jobs(db, bank_id=user.bank_id, limit=200) if req.auto_drain else None
    return {
        **pull_result,
        "worker_drain": worker_result,
    }


@router.post("/x/replay")
def x_replay_mentions(
    user: Operator,
    db: DbSession,
    payload: XReplayRequest | None = None,
):
    """Replay recorded X v2 mention payloads through XAdapter as the reliable stage fallback."""
    bank = db.get(Bank, user.bank_id)
    if bank and db.scalar(select(BankAlias.id).where(BankAlias.bank_id == bank.id).limit(1)) is None:
        _seed_defaults(db, bank.id, bank.name)
        db.commit()
    req = payload or XReplayRequest()
    replay_result = replay_recorded_mentions(db, limit=req.limit, anchor_at=req.at)
    worker_result = drain_jobs(db, bank_id=user.bank_id, limit=200) if req.auto_drain else None
    return {
        **replay_result,
        "worker_drain": worker_result,
    }
