from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services import demo_auth

from app.api.deps import AuthUser, DbSession, Supa
from app.models import Bank
from app.schemas.auth import (
    LoginRequest, MeRead, RefreshRequest, RegisterBankRequest, RegisterResponse, TokenResponse,
)
from app.services import auth_service
from app.services.supabase_client import SupabaseError

router = APIRouter(prefix="/auth", tags=["auth"])


legacy_router = APIRouter()


class DemoLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120, examples=["Zymic Bank"])
    password: str = Field(min_length=1, max_length=256, examples=["123"])


class DemoTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    demo: bool = True
    synthetic: bool = True
    user: MeRead


demo_router = APIRouter()


@demo_router.post("/login", response_model=DemoTokenResponse)
def demo_login(payload: DemoLoginRequest, db: DbSession):
    """Demo-only credentials. Supabase Postgres stores data; this is not Supabase Auth."""
    return demo_auth.login(db, payload.username, payload.password)


if get_settings().demo_mode:
    router.include_router(demo_router)


@legacy_router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register_bank(payload: RegisterBankRequest, db: DbSession, sb: Supa):
    """Register a bank and its first admin. Creates the Supabase user, the bank and the admin profile."""
    bank, profile, session = auth_service.register_bank(db, sb, payload)
    me = auth_service.to_me(profile, bank)
    return RegisterResponse(
        bank=me.bank, user=me, email_confirmation_required=session is None,
        session=auth_service.to_token_response(session, me) if session else None,
    )


@legacy_router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession, sb: Supa):
    return auth_service.login(db, sb, payload.email, payload.password)


@legacy_router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, sb: Supa):
    try:
        return auth_service.to_token_response(sb.refresh(payload.refresh_token))
    except SupabaseError as exc:
        raise auth_service.to_http(exc) from exc


if not get_settings().demo_mode:
    router.include_router(legacy_router)


@router.get("/me", response_model=MeRead)
def me(user: AuthUser, db: DbSession):
    from app.models import Profile

    return auth_service.to_me(db.get(Profile, user.id), db.get(Bank, user.bank_id))
