import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import AdminUser, AuthUser, DbSession, StaffViewer, Supa
from app.models import Bank, Profile
from app.models.enums import MemberStatus, UserRole
from app.schemas.auth import BankRead, BankUpdate, InviteMemberRequest, MemberRead, MemberUpdate
from app.services import auth_service
from app.services.audit import log_event
from app.services.supabase_client import SupabaseError

router = APIRouter(prefix="/bank", tags=["bank"])


@router.get("", response_model=BankRead)
def get_bank(user: AuthUser, db: DbSession):
    return db.get(Bank, user.bank_id)


@router.patch("", response_model=BankRead)
def update_bank(payload: BankUpdate, admin: AdminUser, db: DbSession):
    bank = db.get(Bank, admin.bank_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(bank, field, value)
    log_event(db, bank_id=bank.id, actor=str(admin.id), action="bank_updated",
              entity_type="bank", entity_id=str(bank.id), details={"fields": list(changes)})
    db.commit()
    return bank


@router.get("/members", response_model=list[MemberRead])
def list_members(user: StaffViewer, db: DbSession):
    q = select(Profile).where(Profile.bank_id == user.bank_id).order_by(Profile.created_at)
    return db.execute(q).scalars().all()


@router.post("/members", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
def invite_member(payload: InviteMemberRequest, admin: AdminUser, db: DbSession, sb: Supa):
    """Invite a colleague by email. Supabase sends the invite; they set a password and sign in."""
    email = payload.email.lower()
    if db.scalar(select(Profile.id).where(Profile.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    try:
        user_id = sb.invite(email, {"full_name": payload.full_name})
    except SupabaseError as exc:
        raise auth_service.to_http(exc) from exc
    member = Profile(
        id=uuid.UUID(user_id), bank_id=admin.bank_id, email=email, full_name=payload.full_name,
        role=payload.role, status=MemberStatus.INVITED,
    )
    db.add(member)
    log_event(db, bank_id=admin.bank_id, actor=str(admin.id), action="member_invited",
              entity_type="profile", entity_id=user_id, details={"role": payload.role.value})
    db.commit()
    return member


@router.patch("/members/{user_id}", response_model=MemberRead)
def update_member(user_id: uuid.UUID, payload: MemberUpdate, admin: AdminUser, db: DbSession):
    member = db.get(Profile, user_id)
    if member is None or member.bank_id != admin.bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    new_role = payload.role or member.role
    new_status = payload.status or member.status
    loses_admin = member.role == UserRole.BANK_ADMIN and member.status == MemberStatus.ACTIVE and (
        new_role != UserRole.BANK_ADMIN or new_status != MemberStatus.ACTIVE
    )
    if loses_admin and auth_service.active_admin_count(db, admin.bank_id, exclude=member.id) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A bank must keep at least one active admin")
    member.role, member.status = new_role, new_status
    log_event(db, bank_id=admin.bank_id, actor=str(admin.id), action="member_updated",
              entity_type="profile", entity_id=str(member.id),
              details={"role": new_role.value, "status": new_status.value})
    db.commit()
    return member
