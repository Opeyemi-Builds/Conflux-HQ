from fastapi import APIRouter, status

from app.api.deps import AuthUser, DbSession, Supa
from app.models import Bank
from app.schemas.auth import (
    LoginRequest, MeRead, RefreshRequest, RegisterBankRequest, RegisterResponse, TokenResponse,
)
from app.services import auth_service
from app.services.supabase_client import SupabaseError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register_bank(payload: RegisterBankRequest, db: DbSession, sb: Supa):
    """Register a bank and its first admin. Creates the Supabase user, the bank and the admin profile."""
    bank, profile, session = auth_service.register_bank(db, sb, payload)
    me = auth_service.to_me(profile, bank)
    return RegisterResponse(
        bank=me.bank, user=me, email_confirmation_required=session is None,
        session=auth_service.to_token_response(session, me) if session else None,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession, sb: Supa):
    return auth_service.login(db, sb, payload.email, payload.password)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, sb: Supa):
    try:
        return auth_service.to_token_response(sb.refresh(payload.refresh_token))
    except SupabaseError as exc:
        raise auth_service.to_http(exc) from exc


@router.get("/me", response_model=MeRead)
def me(user: AuthUser, db: DbSession):
    from app.models import Profile

    return auth_service.to_me(db.get(Profile, user.id), db.get(Bank, user.bank_id))
