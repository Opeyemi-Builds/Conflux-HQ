import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import BankStatus, MemberStatus, UserRole


def _check_password(v: str) -> str:
    if len(v) < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("Password must be at least 8 characters and include a letter and a number")
    return v


class BankRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    country: str
    cac_number: str | None
    status: BankStatus
    created_at: datetime


class RegisterBankRequest(BaseModel):
    bank_name: str = Field(min_length=2, max_length=120)
    cac_number: str | None = Field(default=None, max_length=32)
    country: str = Field(default="NG", min_length=2, max_length=2)
    admin_full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str

    _pw = field_validator("password")(_check_password)

    @field_validator("bank_name", "admin_full_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return " ".join(v.split())

    @field_validator("country")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class MeRead(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    status: MemberStatus
    bank: BankRead


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: MeRead | None = None


class RegisterResponse(BaseModel):
    bank: BankRead
    user: MeRead
    email_confirmation_required: bool
    session: TokenResponse | None = None


class BankUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    cac_number: str | None = Field(default=None, max_length=32)
    contact_email: EmailStr | None = None


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    status: MemberStatus
    last_login_at: datetime | None
    created_at: datetime


class InviteMemberRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    role: UserRole = UserRole.AGENT


class MemberUpdate(BaseModel):
    role: UserRole | None = None
    status: MemberStatus | None = None

    @field_validator("status")
    @classmethod
    def _only_active_or_disabled(cls, v):
        if v == MemberStatus.INVITED:
            raise ValueError("Status can only be set to active or disabled")
        return v
