from fastapi import APIRouter

from app.api.routes import analytics, auth, bank, complaints, health, incidents

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(bank.router)
api_router.include_router(complaints.router)
api_router.include_router(incidents.router)
api_router.include_router(analytics.router)
