"""Machine API key lifecycle: issuance, verification, listing, revocation.

Mirrors the ingestion-connector credential pattern: the raw secret is shown once
at creation, only an HMAC-SHA256 hash is stored, and the public key_prefix is
used for lookup/logging. The HMAC master secret is shared with connector
credentials, but the token prefixes differ (cfx_api_ vs cfx_conn_), so a token
from one domain can never verify in the other.

Management (create/list/revoke) is JWT bank_admin-only. Machine callers present
the raw token as a Bearer credential and receive a bank-scoped principal with
explicit scopes: 'read' pulls signal, 'operate' additionally triggers jobs.
"""
import hashlib
import hmac
import secrets
import uuid
from datetime import timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.models import ApiKey, Bank
from app.models.api_key import ALLOWED_API_SCOPES, API_KEY_PREFIX
from app.models.enums import BankStatus
from app.services.audit import log_event


def hash_api_key_secret(secret: str) -> str:
    """Derive the HMAC-SHA256 representation of the raw secret."""
    key = get_settings().ingestion_hash_secret.encode("utf-8")
    return hmac.new(key, secret.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_api_key_token() -> tuple[str, str, str]:
    """Generate (prefix, token, hash).

    Token format: cfx_api_<12-char prefix>_<32-char random secret>
    """
    prefix = secrets.token_hex(6)  # 12 hex chars
    secret = secrets.token_urlsafe(24)  # ~32 chars
    full_token = f"{API_KEY_PREFIX}{prefix}_{secret}"
    key_hash = hash_api_key_secret(secret)
    return prefix, full_token, key_hash


def _not_expired(key: ApiKey) -> bool:
    if key.expires_at is None:
        return True
    expires = key.expires_at
    if expires.tzinfo is None:  # SQLite returns naive datetimes
        expires = expires.replace(tzinfo=timezone.utc)
    return expires > utcnow()


def verify_api_key(db: Session, token: str) -> ApiKey:
    """Authenticate an API key token and return the bound active ApiKey.

    Raises HTTPException(401) on invalid/unknown credentials, 403 on revoked,
    expired, or suspended-bank credentials. Refreshes last_used_at on success.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token or not token.startswith(API_KEY_PREFIX):
        raise unauthorized

    parts = token[len(API_KEY_PREFIX):].split("_", 1)
    if len(parts) != 2:
        raise unauthorized
    prefix, secret = parts

    key = db.scalar(select(ApiKey).where(ApiKey.key_prefix == prefix))
    if key is None:
        raise unauthorized

    if not secrets.compare_digest(key.key_hash, hash_api_key_secret(secret)):
        raise unauthorized

    if key.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key has been revoked",
        )
    if not _not_expired(key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key has expired",
        )

    bank = db.get(Bank, key.bank_id)
    if bank is None or bank.status != BankStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Associated bank account is suspended or inactive",
        )

    key.last_used_at = utcnow()
    db.commit()
    return key


def create_api_key(
    db: Session,
    *,
    bank_id: uuid.UUID,
    name: str,
    scopes: list[str],
    expires_at,
    demo: bool,
    created_by: str,
) -> tuple[ApiKey, str]:
    """Provision a key for the bank. Returns (key, raw_token); the raw token is never stored."""
    unknown = set(scopes) - ALLOWED_API_SCOPES
    if unknown or "read" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Scopes must include 'read' and be a subset of {sorted(ALLOWED_API_SCOPES)}",
        )
    prefix, token, key_hash = generate_api_key_token()
    key = ApiKey(
        bank_id=bank_id,
        name=name,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=list(scopes),
        status="active",
        expires_at=expires_at,
        created_by=created_by,
        created_at=utcnow(),
        demo=demo,
    )
    db.add(key)
    log_event(
        db,
        bank_id=bank_id,
        actor=created_by,
        action="api_key_created",
        entity_type="api_key",
        entity_id=prefix,
        details={"name": name, "scopes": list(scopes)},
    )
    db.commit()
    return key, token


def list_api_keys(db: Session, bank_id: uuid.UUID) -> list[ApiKey]:
    return db.scalars(
        select(ApiKey).where(ApiKey.bank_id == bank_id).order_by(ApiKey.created_at.desc())
    ).all()


def revoke_api_key(db: Session, *, bank_id: uuid.UUID, key_id: uuid.UUID, actor: str) -> ApiKey:
    """Revoke a key immediately. Idempotent: revoking twice still returns the key."""
    key = db.get(ApiKey, key_id)
    if key is None or key.bank_id != bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    key.status = "revoked"
    key.revoked_at = utcnow()
    log_event(
        db,
        bank_id=bank_id,
        actor=actor,
        action="api_key_revoked",
        entity_type="api_key",
        entity_id=key.key_prefix,
    )
    db.commit()
    return key
