import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import Bank, Profile
from app.models.enums import BankStatus, MemberStatus, UserRole
from app.schemas.auth import BankRead, MeRead, RegisterBankRequest, TokenResponse
from app.services.audit import log_event
from app.services.supabase_client import SupabaseAuth, SupabaseError


def to_http(exc: SupabaseError) -> HTTPException:
    """Translate Supabase errors into clean API errors without leaking internals."""
    code, st = exc.code, exc.status_code
    if code in {"invalid_credentials", "invalid_grant", "refresh_token_not_found", "refresh_token_already_used"}:
        return HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password" if code == "invalid_credentials" else "Session expired, please sign in again")
    if code == "email_not_confirmed":
        return HTTPException(status.HTTP_403_FORBIDDEN, "Please confirm your email address before signing in")
    if code in {"user_already_exists", "email_exists"}:
        return HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    if code == "weak_password":
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.message)
    if st == 429 or code.startswith("over_"):
        return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts, please try again shortly")
    if st == 503:
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service unavailable")
    return HTTPException(status.HTTP_502_BAD_GATEWAY, "Authentication service error")


def make_slug(db: Session, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "bank"
    slug, n = base, 1
    while db.scalar(select(Bank.id).where(Bank.slug == slug)):
        n += 1
        slug = f"{base}-{n}"
    return slug


def to_me(profile: Profile, bank: Bank) -> MeRead:
    return MeRead(
        id=profile.id, email=profile.email, full_name=profile.full_name, role=profile.role,
        status=profile.status, bank=BankRead.model_validate(bank),
    )


def to_token_response(data: dict, me: MeRead | None = None) -> TokenResponse:
    return TokenResponse(
        access_token=data["access_token"], refresh_token=data["refresh_token"],
        token_type=data.get("token_type", "bearer"), expires_in=int(data.get("expires_in", 3600)), user=me,
    )


def register_bank(db: Session, sb: SupabaseAuth, data: RegisterBankRequest) -> tuple[Bank, Profile, dict | None]:
    email = data.email.lower()
    if db.scalar(select(Profile.id).where(Profile.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    try:
        result = sb.sign_up(email, data.password, {"full_name": data.admin_full_name})
    except SupabaseError as exc:
        raise to_http(exc) from exc

    try:
        bank = Bank(
            name=data.bank_name, slug=make_slug(db, data.bank_name), country=data.country,
            cac_number=data.cac_number, contact_email=email,
        )
        db.add(bank)
        db.flush()
        profile = Profile(
            id=uuid.UUID(result.user_id), bank_id=bank.id, email=email,
            full_name=data.admin_full_name, role=UserRole.BANK_ADMIN, status=MemberStatus.ACTIVE,
        )
        db.add(profile)
        log_event(db, bank_id=bank.id, actor=str(profile.id), action="bank_registered",
                  entity_type="bank", entity_id=str(bank.id), details={"name": bank.name})
        db.commit()
    except Exception:
        db.rollback()
        try:  # do not leave an orphaned auth user behind
            sb.delete_user(result.user_id)
        except SupabaseError:
            pass
        raise
    return bank, profile, result.session


def login(db: Session, sb: SupabaseAuth, email: str, password: str) -> TokenResponse:
    try:
        tokens = sb.password_login(email.lower(), password)
    except SupabaseError as exc:
        raise to_http(exc) from exc

    profile = db.get(Profile, uuid.UUID(tokens["user"]["id"]))
    if profile is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No bank account is linked to this user")
    bank = db.get(Bank, profile.bank_id)
    if profile.status == MemberStatus.DISABLED or bank is None or bank.status != BankStatus.ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is not active")
    if profile.status == MemberStatus.INVITED:
        profile.status = MemberStatus.ACTIVE
    profile.last_login_at = utcnow()
    log_event(db, bank_id=bank.id, actor=str(profile.id), action="login", entity_type="profile", entity_id=str(profile.id))
    db.commit()
    return to_token_response(tokens, to_me(profile, bank))


def active_admin_count(db: Session, bank_id: uuid.UUID, exclude: uuid.UUID | None = None) -> int:
    q = select(func.count()).select_from(Profile).where(
        Profile.bank_id == bank_id, Profile.role == UserRole.BANK_ADMIN, Profile.status == MemberStatus.ACTIVE
    )
    if exclude:
        q = q.where(Profile.id != exclude)
    return db.scalar(q) or 0
