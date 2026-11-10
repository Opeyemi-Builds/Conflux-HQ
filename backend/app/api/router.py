from fastapi import APIRouter

from app.api.routes import ai, analytics, auth, bank, complaints, health, incidents, ingestion, jobs, reconciliation, remediation, social, synthetic
from app.core.config import get_settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
if not get_settings().demo_mode:
    api_router.include_router(bank.router)
api_router.include_router(ingestion.router)
api_router.include_router(complaints.router)
api_router.include_router(incidents.router)
api_router.include_router(remediation.router)
api_router.include_router(analytics.router)
api_router.include_router(ai.router)
api_router.include_router(jobs.router)
api_router.include_router(social.router)
api_router.include_router(reconciliation.router)
if get_settings().demo_mode:
    api_router.include_router(synthetic.router)
