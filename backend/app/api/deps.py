import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import AuthError, decode_token
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Bank, Profile
from app.models.enums import BankStatus, MemberStatus, UserRole
from app.services.supabase_client import SupabaseAuth, get_supabase

DbSession = Annotated[Session, Depends(get_db)]
Supa = Annotated[SupabaseAuth, Depends(get_supabase)]
_bearer = HTTPBearer(auto_error=False, description="Supabase access token from /auth/login")


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    bank_id: uuid.UUID


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)], db: DbSession
) -> CurrentUser:
    unauthorised = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"}
    )
    if creds is None:
        raise unauthorised
    try:
        claims = decode_token(creds.credentials)
        user_id = uuid.UUID(claims["sub"])
    except (AuthError, ValueError, KeyError):
        raise unauthorised from None

    profile = db.get(Profile, user_id)
    if profile is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No bank account is linked to this user")
    if profile.status == MemberStatus.DISABLED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled")
    bank = db.get(Bank, profile.bank_id)
    if bank is None or bank.status != BankStatus.ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This bank account is not active")
    if profile.status == MemberStatus.INVITED:  # first authenticated request completes the invite
        profile.status = MemberStatus.ACTIVE
        profile.last_login_at = utcnow()
        db.commit()
    return CurrentUser(profile.id, profile.email, profile.full_name, profile.role, profile.bank_id)


def require_roles(*roles: UserRole):
    def checker(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to do this")
        return user

    return checker


AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
Operator = Annotated[CurrentUser, Depends(require_roles(UserRole.BANK_ADMIN, UserRole.AGENT, UserRole.IT))]
AdminUser = Annotated[CurrentUser, Depends(require_roles(UserRole.BANK_ADMIN))]
StaffViewer = Annotated[CurrentUser, Depends(require_roles(UserRole.BANK_ADMIN, UserRole.MANAGER))]
