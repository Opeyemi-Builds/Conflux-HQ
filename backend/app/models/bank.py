import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.enums import BankStatus, MemberStatus, UserRole, enum_type


class Bank(Base):
    """A tenant. Every other table carries bank_id, so banks never see each other's data."""

    __tablename__ = "banks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    country: Mapped[str] = mapped_column(String(2), default="NG")
    cac_number: Mapped[str | None] = mapped_column(String(32))  # corporate registration number
    contact_email: Mapped[str] = mapped_column(String(255))
    status: Mapped[BankStatus] = mapped_column(enum_type(BankStatus), default=BankStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    members: Mapped[list["Profile"]] = relationship(back_populates="bank")


class Profile(Base):
    """A bank staff member. `id` is the Supabase auth.users id; Supabase owns the credentials."""

    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[UserRole] = mapped_column(enum_type(UserRole))
    status: Mapped[MemberStatus] = mapped_column(enum_type(MemberStatus), default=MemberStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    bank: Mapped[Bank] = relationship(back_populates="members")
