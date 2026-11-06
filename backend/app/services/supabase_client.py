"""Thin client for Supabase Auth (GoTrue). Supabase owns passwords and tokens; we never store them."""
from dataclasses import dataclass
from functools import lru_cache

import httpx

from app.core.config import Settings, get_settings


class SupabaseError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code, self.code, self.message = status_code, code, message


@dataclass
class SignUpResult:
    user_id: str
    session: dict | None  # None when the project requires email confirmation


class SupabaseAuth:
    def __init__(self, settings: Settings):
        self.s = settings

    def _call(self, method: str, path: str, *, key: str, json: dict | None = None, params: dict | None = None) -> dict:
        if not self.s.supabase_url or not key:
            raise SupabaseError(503, "not_configured", "Authentication service is not configured")
        headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            r = httpx.request(
                method, f"{self.s.supabase_url.rstrip('/')}/auth/v1{path}",
                headers=headers, json=json, params=params, timeout=10.0,
            )
        except httpx.HTTPError as exc:
            raise SupabaseError(503, "unavailable", "Authentication service unreachable") from exc
        data = r.json() if r.content else {}
        if r.status_code >= 400:
            code = data.get("error_code") or data.get("error") or "error"
            msg = data.get("msg") or data.get("error_description") or data.get("message") or "Authentication error"
            raise SupabaseError(r.status_code, str(code), str(msg))
        return data

    def sign_up(self, email: str, password: str, metadata: dict) -> SignUpResult:
        data = self._call("POST", "/signup", key=self.s.supabase_anon_key,
                          json={"email": email, "password": password, "data": metadata})
        user_id = (data.get("user") or {}).get("id") or data.get("id")
        if not user_id:
            raise SupabaseError(502, "bad_response", "Unexpected response from authentication service")
        return SignUpResult(user_id=user_id, session=data if "access_token" in data else None)

    def password_login(self, email: str, password: str) -> dict:
        return self._call("POST", "/token", key=self.s.supabase_anon_key,
                          params={"grant_type": "password"}, json={"email": email, "password": password})

    def refresh(self, refresh_token: str) -> dict:
        return self._call("POST", "/token", key=self.s.supabase_anon_key,
                          params={"grant_type": "refresh_token"}, json={"refresh_token": refresh_token})

    def invite(self, email: str, metadata: dict) -> str:
        data = self._call("POST", "/invite", key=self.s.supabase_service_role_key,
                          params={"redirect_to": self.s.site_url}, json={"email": email, "data": metadata})
        return data["id"]

    def delete_user(self, user_id: str) -> None:
        self._call("DELETE", f"/admin/users/{user_id}", key=self.s.supabase_service_role_key)


@lru_cache
def _client() -> SupabaseAuth:
    return SupabaseAuth(get_settings())


def get_supabase() -> SupabaseAuth:
    return _client()
