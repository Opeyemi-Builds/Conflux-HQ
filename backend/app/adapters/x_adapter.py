"""X (Twitter) API v2 Filtered Stream / Recent Search adapter with rule diff-sync, budget cap, and recorded replay."""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.models import AuditLog, Bank, BankAlias, SocialReceipt
from app.models.enums import BankStatus
from app.services.audit import log_event
from app.services.social_intake import SocialEvent

COST_PER_POST_READ_USD = 0.005
RECORDED_MENTIONS_PATH = Path(__file__).resolve().parents[3] / "data" / "social" / "x_recorded_mentions.json"
X_TWEET_FIELDS = "created_at,author_id,lang,public_metrics,conversation_id"
X_EXPANSIONS = "author_id"
X_USER_FIELDS = "username,name"


def _clean_handle(raw: str) -> str:
    return "@" + raw.strip().lstrip("@").casefold()


def compile_desired_rules(db: Session) -> list[dict]:
    """Compile one X v2 Filtered Stream rule per active tenant (`tag = tenant:<bank_id>`)."""
    banks = db.scalars(
        select(Bank).where(Bank.status == BankStatus.ACTIVE).order_by(Bank.id)
    ).all()
    if not banks:
        return []

    aliases = db.scalars(
        select(BankAlias).where(BankAlias.kind.in_(["handle", "hashtag", "name"]))
    ).all()
    identities_by_bank: dict[uuid.UUID, list[str]] = {}
    for alias in aliases:
        if alias.platform in (None, "x"):
            value = alias.value.casefold().strip()
            if alias.kind == "handle":
                value = _clean_handle(value)
            elif alias.kind == "hashtag":
                value = "#" + value.lstrip("#")
            identities_by_bank.setdefault(alias.bank_id, []).append(value)

    rules = []
    for bank in banks:
        identities = sorted(set(identities_by_bank.get(bank.id, [])))
        if not identities:
            slug_clean = "".join(c for c in (bank.slug or bank.name).casefold() if c.isalnum())
            identities = [f"@{slug_clean}"]
        clauses = []
        for identity in identities:
            if identity.startswith("@"):
                bare = identity.lstrip("@")
                clauses.extend([identity, f"to:{bare}"])
            else:
                clauses.append(identity)
        query = f"({' OR '.join(clauses)}) -is:retweet"
        rules.append({
            "value": query,
            "tag": f"tenant:{bank.id}",
            "bank_id": str(bank.id),
            "bank_name": bank.name,
            "handles": [i for i in identities if i.startswith("@")] ,
            "identities": identities,
        })
    return rules


def compile_combined_search_query(
    db: Session,
    *,
    handles: list[str] | None = None,
    target_bank_id: uuid.UUID | None = None,
) -> str:
    """Build a single X v2 Recent Search query across requested handles, a specific tenant, or all active tenants."""
    if handles:
        cleaned = []
        for h in handles:
            if h and h.strip():
                ch = _clean_handle(h)
                if ch not in cleaned:
                    cleaned.append(ch)
        if cleaned:
            clauses = []
            for h in cleaned:
                bare = h.lstrip("@")
                clauses.append(h)
                clauses.append(f"to:{bare}")
            return f"({' OR '.join(clauses)}) -is:retweet"

    rules = compile_desired_rules(db)
    if target_bank_id is not None:
        target_str = str(target_bank_id)
        rules = [r for r in rules if r.get("bank_id") == target_str]

    all_identities: list[str] = []
    for r in rules:
        for identity in r.get("identities", r.get("handles", [])):
            if identity not in all_identities:
                all_identities.append(identity)
    if not all_identities:
        return "(@zymicbank OR to:zymicbank OR @zymic_support OR to:zymic_support) -is:retweet"
    clauses = []
    for identity in all_identities:
        if identity.startswith("@"):
            bare = identity.lstrip("@")
            clauses.extend([identity, f"to:{bare}"])
        else:
            clauses.append(identity)
    return f"({' OR '.join(clauses)}) -is:retweet"


def diff_stream_rules(desired: list[dict], existing: list[dict]) -> dict:
    """Compute idempotent additions and deletions between desired tenant rules and current X stream rules."""
    desired_by_key = {(r["value"], r["tag"]): r for r in desired}
    existing_by_key = {(r["value"], r.get("tag", "")): r for r in existing}

    to_add = [
        {"value": r["value"], "tag": r["tag"]}
        for key, r in desired_by_key.items()
        if key not in existing_by_key
    ]
    to_delete_ids = [
        str(r["id"])
        for key, r in existing_by_key.items()
        if key not in desired_by_key and r.get("id") is not None
    ]
    unchanged = len(desired_by_key.keys() & existing_by_key.keys())
    return {
        "to_add": to_add,
        "to_delete_ids": to_delete_ids,
        "unchanged_count": unchanged,
    }


def _last_synced_rules(db: Session) -> list[dict]:
    """Read the last synced rule state from audit_log when running without a live X token."""
    entry = db.scalars(
        select(AuditLog)
        .where(AuditLog.action == "x_stream_rules_synced")
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    ).first()
    if entry and isinstance(entry.details, dict):
        return entry.details.get("active_rules", [])
    return []


def _last_since_id(db: Session) -> str | None:
    """Return the newest X post_id previously fetched so Recent Search only reads new posts."""
    entry = db.scalars(
        select(AuditLog)
        .where(AuditLog.action == "x_live_pull_completed")
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    ).first()
    if entry and isinstance(entry.details, dict):
        return entry.details.get("newest_id")
    return None


def sync_stream_rules(
    db: Session,
    *,
    existing_remote_rules: list[dict] | None = None,
    actor: str = "system",
) -> dict:
    """Idempotently sync tenant handle rules with X Filtered Stream (`GET/POST /2/tweets/search/stream/rules`)."""
    settings = get_settings()
    desired = compile_desired_rules(db)
    mode = "live" if settings.x_bearer_token else "local_state"
    remote_created_rules: list[dict] = []

    if existing_remote_rules is not None:
        existing = existing_remote_rules
    elif settings.x_bearer_token:
        try:
            headers = {"Authorization": f"Bearer {settings.x_bearer_token}"}
            resp = httpx.get(
                f"{settings.x_api_base_url.rstrip('/')}/tweets/search/stream/rules",
                headers=headers,
                timeout=settings.x_timeout_seconds,
            )
            resp.raise_for_status()
            existing = resp.json().get("data", []) or []
        except httpx.HTTPError:
            mode = "fallback_local_state"
            existing = _last_synced_rules(db)
    else:
        existing = _last_synced_rules(db)

    diff = diff_stream_rules(desired, existing)
    if mode == "live" and settings.x_bearer_token and (diff["to_add"] or diff["to_delete_ids"]):
        headers = {"Authorization": f"Bearer {settings.x_bearer_token}"}
        base_url = f"{settings.x_api_base_url.rstrip('/')}/tweets/search/stream/rules"
        try:
            # X API v2 requires separate POST requests for "delete" and "add" (OneOf schema rule)
            if diff["to_delete_ids"]:
                del_resp = httpx.post(
                    base_url,
                    headers=headers,
                    json={"delete": {"ids": diff["to_delete_ids"]}},
                    timeout=settings.x_timeout_seconds,
                )
                del_resp.raise_for_status()
            if diff["to_add"]:
                add_resp = httpx.post(
                    base_url,
                    headers=headers,
                    json={"add": diff["to_add"]},
                    timeout=settings.x_timeout_seconds,
                )
                add_resp.raise_for_status()
                remote_created_rules = add_resp.json().get("data", []) or []
        except httpx.HTTPError:
            mode = "fallback_local_state"

    created_id_by_key = {(r.get("value"), r.get("tag")): str(r.get("id")) for r in remote_created_rules if r.get("id")}
    existing_id_by_key = {(r.get("value"), r.get("tag")): str(r.get("id")) for r in existing if r.get("id")}
    active_state = [
        {
            "id": (
                created_id_by_key.get((r["value"], r["tag"]))
                or existing_id_by_key.get((r["value"], r["tag"]))
                or hashlib.sha256(f"{r['tag']}:{r['value']}".encode()).hexdigest()[:12]
            ),
            "value": r["value"],
            "tag": r["tag"],
        }
        for r in desired
    ]
    if diff["to_add"] or diff["to_delete_ids"] or not existing:
        log_event(
            db,
            bank_id=None,
            actor=actor,
            action="x_stream_rules_synced",
            entity_type="x_stream",
            entity_id="shared_stream",
            details={
                "mode": mode,
                "added": len(diff["to_add"]),
                "deleted": len(diff["to_delete_ids"]),
                "unchanged": diff["unchanged_count"],
                "active_rules": active_state,
            },
        )
        db.commit()

    return {
        "mode": mode,
        "desired_rules": desired,
        "active_rules": active_state,
        "to_add": diff["to_add"],
        "to_delete_ids": diff["to_delete_ids"],
        "unchanged_count": diff["unchanged_count"],
        "is_noop": not diff["to_add"] and not diff["to_delete_ids"],
    }


def get_daily_x_reads(db: Session, now: datetime | None = None) -> int:
    anchor = (now or utcnow()).astimezone(timezone.utc)
    day_start = anchor.replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.scalar(
        select(func.count(func.distinct(SocialReceipt.post_id))).where(
            SocialReceipt.platform == "x",
            SocialReceipt.received_at >= day_start,
        )
    )
    return int(count or 0)


def get_x_adapter_status(db: Session) -> dict:
    settings = get_settings()
    reads_today = get_daily_x_reads(db)
    limit = settings.x_daily_post_limit
    rules = compile_desired_rules(db)
    return {
        "mode": "live" if settings.x_bearer_token else "replay_fallback",
        "credentials_configured": bool(settings.x_bearer_token),
        "api_base_url": settings.x_api_base_url,
        "shared_stream_connection": True,
        "monitored_tenants": len(rules),
        "compiled_rules": rules,
        "combined_search_query": compile_combined_search_query(db),
        "last_since_id": _last_since_id(db),
        "reads_today": reads_today,
        "daily_post_limit": limit,
        "budget_remaining_reads": max(0, limit - reads_today),
        "estimated_cost_today_usd": round(reads_today * COST_PER_POST_READ_USD, 4),
        "daily_cap_usd": round(limit * COST_PER_POST_READ_USD, 2),
        "rate_per_post_usd": COST_PER_POST_READ_USD,
    }


def parse_x_v2_payload(raw_payload: dict, *, synthetic: bool = False) -> SocialEvent:
    """Convert a single native X API v2 tweet object (`data`, `includes`, `matching_rules`) into a SocialEvent."""
    data = raw_payload.get("data") if isinstance(raw_payload.get("data"), dict) else raw_payload
    post_id = str(data["id"])
    text = str(data["text"])
    created_raw = data.get("created_at")
    if created_raw:
        occurred_at = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
    else:
        occurred_at = utcnow()

    author_id = data.get("author_id")
    username = None
    users = (raw_payload.get("includes") or {}).get("users") or []
    for u in users:
        if author_id and str(u.get("id")) == str(author_id):
            username = u.get("username")
            break
    if not username and users:
        username = users[0].get("username")

    author_ref = f"x_user:{username or author_id}" if (username or author_id) else None
    public_metrics = data.get("public_metrics") or {}
    matching_rules = raw_payload.get("matching_rules") or []
    rule_tags = [str(r["tag"]) for r in matching_rules if isinstance(r, dict) and r.get("tag")]

    source_url = f"https://x.com/i/web/status/{post_id}"
    return SocialEvent(
        synthetic=bool(raw_payload.get("synthetic", synthetic)),
        platform="x",
        post_id=post_id,
        text=text[:5000],
        occurred_at=occurred_at,
        source_url=source_url,
        author_ref=author_ref,
        region=data.get("region") or raw_payload.get("region"),
        matching_rule_tags=rule_tags,
        public_metrics=public_metrics,
    )


class XAdapter:
    """Shared multi-tenant X adapter supporting live v2 Filtered Stream, Recent Search, and recorded stage replay."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def check_budget_available(self, requested_posts: int = 1) -> tuple[bool, int]:
        reads = get_daily_x_reads(self.db)
        remaining = self.settings.x_daily_post_limit - reads
        return remaining >= requested_posts, max(0, remaining)

    def ingest_raw_v2_payload(self, raw_payload: dict, *, synthetic: bool = False) -> dict:
        """Ingest either a Filtered Stream event (`data` is a dict) or a Recent Search response (`data` is a list)."""
        from app.api.routes.social import ingest_social_event

        data_field = raw_payload.get("data")
        # Handle X v2 Recent Search batch format: {"data": [{...}, {...}], "includes": {"users": [...]}, "meta": {...}}
        if isinstance(data_field, list):
            includes = raw_payload.get("includes") or {}
            matching_rules = raw_payload.get("matching_rules") or []
            accepted = 0
            duplicates = 0
            complaints_created = 0
            items = []
            for tweet_obj in data_field:
                allowed, remaining = self.check_budget_available(1)
                if not allowed and not synthetic:
                    items.append({"accepted": False, "reason": "daily_post_cap_reached", "budget_remaining_reads": remaining})
                    break
                single_envelope = {
                    "data": tweet_obj,
                    "includes": includes,
                    "matching_rules": matching_rules,
                    "synthetic": synthetic,
                }
                event = parse_x_v2_payload(single_envelope, synthetic=synthetic)
                res = ingest_social_event(self.db, event)
                items.append({
                    "post_id": event.post_id,
                    "author_ref": event.author_ref,
                    "occurred_at": event.occurred_at.isoformat(),
                    "text": event.text,
                    "source_url": event.source_url,
                    **res,
                })
                if res.get("accepted"):
                    accepted += 1
                    if res.get("duplicate"):
                        duplicates += 1
                    else:
                        complaints_created += len(res.get("complaint_ids", [res.get("complaint_id")]))
            return {
                "accepted": accepted > 0,
                "batch": True,
                "processed": len(items),
                "accepted_count": accepted,
                "duplicates": duplicates,
                "complaints_created": complaints_created,
                "items": items,
            }

        allowed, remaining = self.check_budget_available(1)
        if not allowed and not synthetic:
            return {
                "accepted": False,
                "reason": "daily_post_cap_reached",
                "daily_post_limit": self.settings.x_daily_post_limit,
                "budget_remaining_reads": remaining,
            }
        event = parse_x_v2_payload(raw_payload, synthetic=synthetic)
        return ingest_social_event(self.db, event)

    def pull_recent_mentions(
        self,
        *,
        max_results: int = 10,
        since_id: str | None = None,
        handles: list[str] | None = None,
        target_bank_id: uuid.UUID | None = None,
        fallback_to_replay: bool = False,
    ) -> dict:
        """Call live X API v2 `GET /2/tweets/search/recent` across requested or tenant handles."""
        allowed, remaining = self.check_budget_available(1)
        if not allowed:
            return {
                "source": "blocked_by_cap",
                "accepted": False,
                "reason": "daily_post_cap_reached",
                "daily_post_limit": self.settings.x_daily_post_limit,
                "budget_remaining_reads": remaining,
            }

        if not self.settings.x_bearer_token:
            if fallback_to_replay:
                replay = replay_recorded_mentions(self.db, limit=max_results)
                return {**replay, "source": "replay_fallback", "reason": "x_bearer_token_not_configured"}
            return {
                "source": "none",
                "accepted": False,
                "reason": "x_bearer_token_not_configured",
                "hint": "Set X_BEARER_TOKEN in .env to fetch live mentions from https://api.x.com/2/tweets/search/recent",
            }

        # X API v2 strictly requires max_results in [10, 100] on /2/tweets/search/recent
        clamped_max = max(10, min(100, max_results, max(10, remaining)))
        query = compile_combined_search_query(self.db, handles=handles, target_bank_id=target_bank_id)
        params: dict[str, str | int] = {
            "query": query,
            "max_results": clamped_max,
            "tweet.fields": X_TWEET_FIELDS,
            "expansions": X_EXPANSIONS,
            "user.fields": X_USER_FIELDS,
        }
        if since_id:
            params["since_id"] = since_id

        url = f"{self.settings.x_api_base_url.rstrip('/')}/tweets/search/recent"
        headers = {"Authorization": f"Bearer {self.settings.x_bearer_token}"}
        try:
            resp = httpx.get(url, params=params, headers=headers, timeout=self.settings.x_timeout_seconds)
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPStatusError as exc:
            err_detail = exc.response.text
            try:
                err_detail = exc.response.json()
            except Exception:
                pass
            if fallback_to_replay:
                replay = replay_recorded_mentions(self.db, limit=max_results)
                return {
                    **replay,
                    "source": "replay_fallback",
                    "reason": f"x_api_http_{exc.response.status_code}",
                    "x_api_error": err_detail,
                }
            return {
                "source": "live_error",
                "accepted": False,
                "http_status": exc.response.status_code,
                "reason": f"x_api_http_{exc.response.status_code}",
                "x_api_error": err_detail,
                "query": query,
            }
        except httpx.HTTPError as exc:
            if fallback_to_replay:
                replay = replay_recorded_mentions(self.db, limit=max_results)
                return {**replay, "source": "replay_fallback", "reason": f"x_api_error: {exc}"}
            return {"source": "live_error", "accepted": False, "reason": str(exc), "query": query}

        meta = payload.get("meta") or {}
        if meta.get("result_count", 0) == 0 or not payload.get("data"):
            return {
                "source": "live_recent_search",
                "query": query,
                "fetched": 0,
                "accepted_count": 0,
                "duplicates": 0,
                "complaints_created": 0,
                "newest_id": meta.get("newest_id") or since_id,
                "items": [],
            }

        if target_bank_id and not payload.get("matching_rules"):
            payload["matching_rules"] = [{"id": "live_recent_search", "tag": f"tenant:{target_bank_id}"}]

        batch_result = self.ingest_raw_v2_payload(payload, synthetic=False)
        newest_id = meta.get("newest_id")
        if newest_id:
            log_event(
                self.db,
                bank_id=None,
                actor="x_adapter",
                action="x_live_pull_completed",
                entity_type="x_stream",
                entity_id="recent_search",
                details={
                    "newest_id": str(newest_id),
                    "fetched": len(payload.get("data", [])),
                    "complaints_created": batch_result.get("complaints_created", 0),
                },
            )
            self.db.commit()

        return {
            "source": "live_recent_search",
            "query": query,
            "fetched": len(payload.get("data", [])),
            "newest_id": newest_id,
            **batch_result,
        }

    def stream_filtered_batch(
        self,
        *,
        max_posts: int = 10,
        max_seconds: float = 5.0,
        fallback_to_replay: bool = True,
    ) -> dict:
        """Read a bounded batch from the shared X v2 Filtered Stream (`GET /2/tweets/search/stream`)."""
        allowed, remaining = self.check_budget_available(1)
        if not allowed:
            return {
                "source": "blocked_by_cap",
                "accepted": False,
                "reason": "daily_post_cap_reached",
                "daily_post_limit": self.settings.x_daily_post_limit,
                "budget_remaining_reads": remaining,
            }

        if not self.settings.x_bearer_token:
            if fallback_to_replay:
                replay = replay_recorded_mentions(self.db, limit=max_posts)
                return {"source": "replay_fallback", "reason": "x_bearer_token_not_configured", **replay}
            return {"source": "none", "accepted": False, "reason": "x_bearer_token_not_configured"}

        url = f"{self.settings.x_api_base_url.rstrip('/')}/tweets/search/stream"
        params = {
            "tweet.fields": X_TWEET_FIELDS,
            "expansions": X_EXPANSIONS,
            "user.fields": X_USER_FIELDS,
        }
        headers = {"Authorization": f"Bearer {self.settings.x_bearer_token}"}
        accepted = 0
        duplicates = 0
        complaints_created = 0
        fetched = 0

        try:
            with httpx.stream("GET", url, params=params, headers=headers, timeout=max_seconds) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.strip():
                        continue  # X Filtered Stream sends empty CR/LF heartbeat lines every 20s
                    ok, _ = self.check_budget_available(1)
                    if not ok:
                        break
                    item = json.loads(line)
                    fetched += 1
                    res = self.ingest_raw_v2_payload(item, synthetic=False)
                    if res.get("accepted"):
                        accepted += 1
                        if res.get("duplicate"):
                            duplicates += 1
                        else:
                            complaints_created += len(res.get("complaint_ids", [res.get("complaint_id")]))
                    if fetched >= max_posts:
                        break
        except httpx.TimeoutException:
            # Expected when bounded stream window closes after max_seconds
            pass
        except httpx.HTTPError as exc:
            if fallback_to_replay:
                replay = replay_recorded_mentions(self.db, limit=max_posts)
                return {"source": "replay_fallback", "reason": f"x_stream_error: {exc}", **replay}
            return {"source": "live_error", "accepted": False, "reason": str(exc)}

        return {
            "source": "live_filtered_stream",
            "fetched": fetched,
            "accepted_count": accepted,
            "duplicates": duplicates,
            "complaints_created": complaints_created,
        }


def replay_recorded_mentions(
    db: Session,
    *,
    limit: int | None = None,
    anchor_at: datetime | None = None,
    path: Path | None = None,
) -> dict:
    """Replay recorded X API v2 mention payloads through XAdapter as the reliable stage fallback."""
    target_path = path or RECORDED_MENTIONS_PATH
    if not target_path.exists():
        raise FileNotFoundError(f"Recorded X mentions file not found at {target_path}")

    raw_items: list[dict] = json.loads(target_path.read_text(encoding="utf-8"))
    if limit is not None:
        raw_items = raw_items[:limit]

    banks = db.scalars(
        select(Bank).where(Bank.status == BankStatus.ACTIVE).order_by(Bank.created_at.asc(), Bank.id.asc())
    ).all()
    primary_bank_id = str(banks[0].id) if banks else None
    secondary_bank_id = str(banks[1].id) if len(banks) > 1 else None

    anchor = (anchor_at or utcnow()).astimezone(timezone.utc)
    bucket_start = anchor.replace(minute=anchor.minute - anchor.minute % 15, second=0, microsecond=0)

    adapter = XAdapter(db)
    accepted = 0
    duplicates = 0
    complaints_created = 0
    results = []

    for idx, item in enumerate(raw_items):
        payload = json.loads(json.dumps(item))
        resolved_rules = []
        for rule in payload.get("matching_rules", []):
            tag = rule.get("tag", "")
            if tag == "tenant:PRIMARY_BANK" and primary_bank_id:
                resolved_rules.append({"id": rule.get("id", "r1"), "tag": f"tenant:{primary_bank_id}"})
            elif tag == "tenant:SECONDARY_BANK" and secondary_bank_id:
                resolved_rules.append({"id": rule.get("id", "r2"), "tag": f"tenant:{secondary_bank_id}"})
            elif tag.startswith("tenant:") and tag not in ("tenant:PRIMARY_BANK", "tenant:SECONDARY_BANK"):
                resolved_rules.append(rule)
        payload["matching_rules"] = resolved_rules

        if anchor_at is not None or payload.get("anchor_to_current_bucket", True):
            ts = bucket_start + timedelta(seconds=30 + idx * 15)
            payload.setdefault("data", {})["created_at"] = ts.isoformat()

        outcome = adapter.ingest_raw_v2_payload(payload, synthetic=True)
        results.append(outcome)
        if outcome.get("accepted"):
            accepted += 1
            if outcome.get("duplicate"):
                duplicates += 1
            else:
                complaints_created += len(outcome.get("complaint_ids", [outcome.get("complaint_id")]))

    return {
        "source": "social_replay",
        "replayed": len(raw_items),
        "accepted": accepted,
        "duplicates": duplicates,
        "complaints_created": complaints_created,
        "bucket_start": bucket_start.isoformat(),
        "detection_at": (bucket_start + timedelta(minutes=14, seconds=59)).isoformat(),
    }
