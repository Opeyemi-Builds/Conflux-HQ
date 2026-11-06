from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_kwargs: dict = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    _kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Needed for the Supabase transaction pooler (port 6543); harmless elsewhere.
    _kwargs["connect_args"] = {"prepare_threshold": None}

engine = create_engine(settings.database_url, **_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
