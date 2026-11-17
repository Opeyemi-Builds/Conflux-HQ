"""Server-side auto-poll: live X mentions for every tagged active bank.

Runs underneath — no UI button, no manual pull/replay. The lifespan background
task calls :func:`poll_tagged_banks_once` every ``SOCIAL_POLL_SECONDS``. A bank
is polled only once it is tagged (has aliases, seeded automatically at
onboarding). Without ``X_BEARER_TOKEN`` the poller stands by and the API keeps
serving already-ingested receipts.
"""
import logging

from sqlalchemy import select

from app.adapters.x_adapter import XAdapter, compile_desired_rules
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Bank
from app.models.enums import BankStatus
from app.services.worker import drain_jobs

logger = logging.getLogger("conflux.social_poller")


def poll_tagged_banks_once(max_results: int = 50) -> dict:
    """One shared live X pull across all tagged tenants, then drain the queue."""
    settings = get_settings()
    if not settings.social_live_enabled:
        return {"ran": False, "reason": "social_live_disabled"}
    if not settings.social_auto_pull:
        return {"ran": False, "reason": "social_auto_pull_disabled"}
    if not settings.x_bearer_token:
        return {"ran": False, "reason": "x_bearer_token_not_configured"}
    with SessionLocal() as db:
        tagged = [b for b in db.scalars(
            select(Bank).where(Bank.status == BankStatus.ACTIVE)
        ).all()]
        rules = compile_desired_rules(db)
        if not rules:
            return {"ran": False, "reason": "no_tagged_banks"}
        adapter = XAdapter(db)
        result = adapter.pull_recent_mentions(
            max_results=max_results,
            fallback_to_replay=False,
        )
        drained: dict = {}
        if result.get("accepted") or result.get("accepted_count"):
            try:
                drained = drain_jobs(db, limit=200)
            except Exception as exc:  # never break the poll loop on drain errors
                logger.warning("social auto-drain failed: %s", exc)
        logger.info(
            "social auto-poll across %d tagged banks: %s",
            len(rules),
            {k: result.get(k) for k in ("source", "fetched", "accepted_count", "complaints_created", "duplicates", "reason")},
        )
        return {"ran": True, "tagged_banks": len(tagged), "rules": len(rules), **result, "drained": drained}
