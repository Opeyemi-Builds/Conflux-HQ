import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.db.init_db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_tables:
        init_db()
    if os.environ.get("RUN_EMBEDDED_WORKER", "false").lower() in ("1", "true", "yes"):
        from app.services.worker import run_worker_loop

        worker_thread = threading.Thread(
            target=run_worker_loop, kwargs={"poll_interval": 2.0}, daemon=True
        )
        worker_thread.start()
    yield


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
