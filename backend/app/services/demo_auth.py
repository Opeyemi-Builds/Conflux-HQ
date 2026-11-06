"""Explicit demo login. This is NOT Supabase Auth or a production password scheme."""
import secrets
import uuid
from datetime import timedelta

import jwt
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.models import Bank, Profile
from app.models.enums import BankStatus, MemberStatus, UserRole
from app.services.audit import log_event
from app.services.auth_service import to_me

DEMO_BANK_ID = uuid.UUID("ba81dd8c-7512-4ed8-94f9-008d06b372e1")
DEMO_USER_ID = uuid.UUID("5071cb21-234c-4745-b66b-d1e3136d28d7")
DEMO_ISSUER = "conflux-demo"
DEMO_AUDIENCE = "conflux-demo-api"


def demo_secret() -> str:
    settings = get_settings()
    if not settings.demo_mode:
        raise HTTPException(404, "Demo mode is disabled")
    if len(settings.demo_token_secret) < 32:
        raise HTTPException(503, "Set DEMO_TOKEN_SECRET to a random secret of at least 32 characters")
    return settings.demo_token_secret


def login(db: Session, username: str, password: str) -> dict:
    settings = get_settings()
    secret = demo_secret()
    valid_name = secrets.compare_digest(username.encode(), settings.demo_username.encode())
    valid_password = secrets.compare_digest(password.encode(), settings.demo_password.encode())
    if not (valid_name and valid_password):
        raise HTTPException(401, "Invalid username or password", headers={"WWW-Authenticate": "Bearer"})

    bank = db.get(Bank, DEMO_BANK_ID)
    profile = db.get(Profile, DEMO_USER_ID)
    if bank is None or profile is None:
        try:
            if bank is None:
                bank = Bank(id=DEMO_BANK_ID, name=settings.demo_username, slug="zymic-bank-demo",
                            country="NG", contact_email="demo@zymic.example")
                db.add(bank)
                db.flush()
            if profile is None:
                profile = Profile(id=DEMO_USER_ID, bank_id=DEMO_BANK_ID, email="demo@zymic.example",
                                  full_name="Demo Operator", role=UserRole.BANK_ADMIN,
                                  status=MemberStatus.ACTIVE)
                db.add(profile)
            db.commit()
        except IntegrityError:
            # A parallel first login may have provisioned the same fixed records.
            db.rollback()
            bank = db.get(Bank, DEMO_BANK_ID)
            profile = db.get(Profile, DEMO_USER_ID)
            if bank is None or profile is None:
                raise HTTPException(409, "Demo identity conflicts with existing records") from None
    if (bank.status != BankStatus.ACTIVE or profile.status != MemberStatus.ACTIVE
            or profile.bank_id != DEMO_BANK_ID):
        raise HTTPException(403, "Demo account is inactive")
    now = utcnow()
    expires_in = settings.demo_token_minutes * 60
    token = jwt.encode({"sub": str(profile.id), "iss": DEMO_ISSUER, "aud": DEMO_AUDIENCE,
                        "iat": now, "exp": now + timedelta(seconds=expires_in),
                        "jti": str(uuid.uuid4())}, secret, algorithm="HS256")
    profile.last_login_at = now
    log_event(db, bank_id=bank.id, actor=str(profile.id), action="demo_login",
              entity_type="profile", entity_id=str(profile.id))
    db.commit()
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in,
            "demo": True, "synthetic": True, "user": to_me(profile, bank)}
