"""Verify Supabase access tokens locally (no network call per request)."""
from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.core.config import get_settings

_ALLOWED_ALGS = {"HS256", "RS256", "ES256"}


class AuthError(Exception):
    pass


@lru_cache
def _jwks_client() -> PyJWKClient:
    s = get_settings()
    return PyJWKClient(f"{s.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json", cache_keys=True)


def decode_token(token: str) -> dict:
    """Return the verified claims, or raise AuthError.

    Legacy Supabase projects sign with a shared HS256 secret. Newer projects sign with
    asymmetric keys published at the JWKS endpoint. Both are supported.
    """
    s = get_settings()
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg not in _ALLOWED_ALGS:
            raise AuthError("Unsupported token algorithm")
        if alg == "HS256":
            if not s.supabase_jwt_secret:
                raise AuthError("Token verification is not configured")
            key = s.supabase_jwt_secret
        else:
            if not s.supabase_url:
                raise AuthError("Token verification is not configured")
            key = _jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(
            token, key, algorithms=[alg], audience=s.supabase_jwt_audience,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid or expired token") from exc
