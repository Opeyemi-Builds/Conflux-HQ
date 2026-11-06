from fastapi import APIRouter

<<<<<<< HEAD
from app.api.routes import ai, analytics, auth, bank, complaints, health, incidents
=======
from app.api.routes import analytics, auth, bank, complaints, health, incidents, synthetic, social

from app.core.config import get_settings
>>>>>>> origin/main

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
if not get_settings().demo_mode:
    api_router.include_router(bank.router)
api_router.include_router(complaints.router)
api_router.include_router(incidents.router)
api_router.include_router(analytics.router)
<<<<<<< HEAD
api_router.include_router(ai.router)
=======
api_router.include_router(social.router)
if get_settings().demo_mode:
    api_router.include_router(synthetic.router)
>>>>>>> origin/main
