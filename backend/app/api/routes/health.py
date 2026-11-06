from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DbSession) -> dict:
    db.execute(text("SELECT 1"))
    s = get_settings()
    return {"status": "ok", "app": s.app_name, "environment": s.environment, "database": "connected"}
