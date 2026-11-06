import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import EventType, enum_type


class SystemEvent(Base):
    """Releases, outages and config changes the agent compares against complaint spikes."""

    __tablename__ = "system_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True)
    event_type: Mapped[EventType] = mapped_column(enum_type(EventType), index=True)
    component: Mapped[str] = mapped_column(String(64))
    version: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
