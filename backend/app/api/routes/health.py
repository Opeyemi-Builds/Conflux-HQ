from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.api.deps import AuthUser
from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DbSession) -> dict:
    db.execute(text("SELECT 1"))
    s = get_settings()
    return {"status": "ok", "app": s.app_name, "environment": s.environment, "database": "connected"}


@router.get("/health/connectors")
def connectors_health(db: DbSession, user: AuthUser) -> dict:
    """Bank-scoped connector/queue health. Optional providers report states;
    none of them can make the database look unhealthy, and vice versa."""
    db.execute(text("SELECT 1"))
    s = get_settings()
    from app.services import remediation as remediation_service

    detail = remediation_service.connector_health(db, user.bank_id)
    providers = {
        "database": "connected",
        "worker_queue": (
            "degraded" if detail["queue"]["dead_lettered"] > 0
            else "idle" if detail["queue"]["pending"] == 0
            else "draining"
        ),
        "bank_intake": "active" if detail["active_connectors"] > 0 else "no_connectors",
        "social": (
            "replay_only"
            if not s.social_live_enabled
            else "live_enabled" if s.x_bearer_token else "no_token"
        ),
        "investigation": (
            "configured"
            if (s.anthropic_api_key or s.gemini_api_key)
            else "fallback_only"
        ),
        "payment_evidence": "sandbox_only",
    }
    overall = "ok" if providers["database"] == "connected" else "degraded"
    return {"status": overall, "providers": providers, "detail": detail}
