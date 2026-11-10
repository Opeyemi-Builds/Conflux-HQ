"""Pydantic schemas for bank-scoped machine API keys."""
import uuid
from datetime import datetime, timezone

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.models.api_key import ALLOWED_API_SCOPES


class ApiKeyCreateIn(BaseModel):
    """Provision a developer credential. The raw token is returned once, at creation."""

    name: str = Field(min_length=2, max_length=64)
    scopes: list[str] = Field(default_factory=lambda: ["read"], min_length=1, max_length=8)
    expires_at: AwareDatetime | None = Field(default=None)
    demo: bool = False

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        for scope in v:
            s = scope.strip().lower()
            if s not in ALLOWED_API_SCOPES:
                raise ValueError(f"Unsupported scope '{scope}'. Allowed: {sorted(ALLOWED_API_SCOPES)}")
            if s not in cleaned:
                cleaned.append(s)
        if "read" not in cleaned:
            raise ValueError("The 'read' scope is required; 'operate' is optional")
        return cleaned

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, v: AwareDatetime | None) -> AwareDatetime | None:
        if v is not None and v.astimezone(timezone.utc) <= datetime.now(timezone.utc):
            raise ValueError("expires_at must be in the future")
        return v


class ApiKeyCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str]
    token: str  # Returned ONCE at creation
    expires_at: datetime | None
    created_at: datetime


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str]
    status: str
    expires_at: datetime | None
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    demo: bool
