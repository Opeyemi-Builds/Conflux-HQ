import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.db.init_db import init_db

settings = get_settings()
logger = logging.getLogger("conflux.social_poller")


async def _social_poll_loop() -> None:
    """Background auto-poll: live X mentions for every tagged bank, underneath.

    No UI action required. A bank is polled once it is tagged (aliases seeded
    automatically at onboarding). Without X_BEARER_TOKEN the poller stands by.
    """
    from app.services.social_poller import poll_tagged_banks_once

    interval = max(30.0, float(settings.social_poll_seconds or 90.0))
    await asyncio.sleep(10.0)  # let startup finish before the first poll
    while True:
        try:
            if settings.social_auto_pull and settings.x_bearer_token:
                await asyncio.to_thread(poll_tagged_banks_once)
        except asyncio.CancelledError:
            break
        except Exception as exc:  # never kill the app on a poll failure
            logger.warning("social auto-poll failed: %s", exc)
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_tables:
        init_db()
    task = None
    if settings.social_auto_pull:
        task = asyncio.create_task(_social_poll_loop())
    try:
        yield
    finally:
        if task is not None:
            task.cancel()


app = FastAPI(
    title=f"{settings.app_name} API",
    version="0.1.0",
    description="AI complaint intelligence for banks. All prototype data is synthetic.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)
