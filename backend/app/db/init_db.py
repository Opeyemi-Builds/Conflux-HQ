from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.db.base import Base
from app.db.session import engine


def init_db() -> None:
    """Create tables. Fine for the hackathon; switch to Alembic migrations after."""
    Base.metadata.create_all(bind=engine)
