"""Forge-only, read-oriented client for XtraDot sandbox transfer evidence."""

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import os
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from app.adapters.xtradot_schemas import TransferObservation

DEFAULT_BASE_URL = "http://bank-api.ingress-apisix.svc.cluster.local/v1"
_INTERNAL_HOST = "bank-api.ingress-apisix.svc.cluster.local"
_PUBLIC_HOST = "team10.xtradot.co"


class XtradotConfigurationError(ValueError):
    """Raised when the client is not configured for an approved sandbox endpoint."""


class XtradotAPIError(RuntimeError):
    """Sanitized provider error; response bodies and credentials are never included."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.error_code = error_code
        details = []
        if status_code is not None:
            details.append(f"HTTP {status_code}")
        if error_code:
            details.append(f"code {error_code}")
        suffix = f" ({', '.join(details)})" if details else ""
        super().__init__(message + suffix)


def _validate_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise XtradotConfigurationError("XtraDot base URL must not contain credentials or query data")
    if parsed.path.rstrip("/") != "/v1":
        raise XtradotConfigurationError("XtraDot base URL must end in /v1")
    try:
        port = parsed.port
    except ValueError:
        raise XtradotConfigurationError("XtraDot base URL has an invalid port") from None
    if parsed.hostname == _INTERNAL_HOST and parsed.scheme in {"http", "https"}:
        expected_port = 80 if parsed.scheme == "http" else 443
        if port not in (None, expected_port):
            raise XtradotConfigurationError("XtraDot base URL uses an unexpected port")
        return value.rstrip("/")
    if parsed.hostname == _PUBLIC_HOST and parsed.scheme == "https":
        if port not in (None, 443):
            raise XtradotConfigurationError("XtraDot base URL uses an unexpected port")
        return value.rstrip("/")
    raise XtradotConfigurationError("XtraDot base URL is not an approved Forge sandbox endpoint")


def _safe_request_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("request_id")
    if isinstance(value, str) and value and len(value) <= 160:
        return value
    return None


def _parse_provider_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise XtradotAPIError("XtraDot returned an invalid occurrence timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise XtradotAPIError("XtraDot returned an invalid occurrence timestamp") from None
    if parsed.utcoffset() is None:
        raise XtradotAPIError("XtraDot returned a timezone-naive occurrence timestamp")
    return parsed.astimezone(timezone.utc)


class XtradotClient:
    """No transfer-creation methods are exposed by this evidence-only client."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise XtradotConfigurationError("XtraDot API key is required")
        if timeout_seconds <= 0:
            raise XtradotConfigurationError("XtraDot timeout must be positive")
        self._base_url = _validate_base_url(base_url)
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
        )

    @classmethod
    def from_environment(cls) -> "XtradotClient":
        """Read the Forge-injected key at runtime; never place it in app settings or logs."""
        return cls(
            base_url=os.environ.get("XTRADOT_BASE_URL", DEFAULT_BASE_URL),
            api_key=os.environ.get("GATEWAY_KEY", ""),
        )

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> "XtradotClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_transfer(self, reference: str) -> TransferObservation:
        """Read one transfer by its provider reference; never resubmits a transfer."""
        self._validate_reference(reference)
        path = f"/transfers/{quote(reference, safe='')}"
        return self._request("GET", path, reference=reference)

    def requery_interbank_transfer(
        self,
        reference: str,
        *,
        session_id: str,
    ) -> TransferObservation:
        """Query the sandbox transaction-status endpoint (TSQ).

        Per Mock Spec v2 the requery body is exactly ``{"session_id": ...}``;
        the provider echoes ``reference`` in the response, which is validated
        against the requested reference. Never resubmits a transfer.
        """
        self._validate_reference(reference)
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 160:
            raise ValueError("session_id is required by the XtraDot TSQ specification")
        return self._request(
            "POST",
            "/transfers/interbank/requery",
            reference=reference,
            json_body={"session_id": session_id.strip()},
        )

    @staticmethod
    def _validate_reference(reference: str) -> None:
        if not reference or len(reference) > 160 or not reference.strip():
            raise ValueError("A valid provider transfer reference is required")

    def _request(
        self,
        method: str,
        path: str,
        *,
        reference: str,
        json_body: Mapping[str, Any] | None = None,
    ) -> TransferObservation:
        try:
            response = self._http.request(
                method,
                f"{self._base_url}{path}",
                headers={"x-api-key": self._api_key, "Accept": "application/json"},
                json=dict(json_body) if json_body is not None else None,
                timeout=self._timeout_seconds,
                follow_redirects=False,
            )
        except httpx.TimeoutException:
            return self._unknown(reference)
        except httpx.HTTPError:
            raise XtradotAPIError("XtraDot request failed before a reliable status was received") from None

        payload: Any = None
        try:
            payload = response.json(parse_float=Decimal)
        except ValueError:
            if response.status_code == 504:
                return self._unknown(reference)
            raise XtradotAPIError(
                "XtraDot returned an invalid response",
                status_code=response.status_code,
            ) from None

        if response.status_code == 504:
            return self._unknown(reference, request_id=_safe_request_id(payload))
        if response.status_code == 404:
            return TransferObservation(
                payment_reference=reference,
                source_status="missing",
                received_at=self._now(),
                safe_request_id=_safe_request_id(payload),
                evidence_basis="sandbox_provider_not_found",
                freshness="missing",
                requery_required=True,
            )
        if response.status_code < 200 or response.status_code >= 300:
            code = None
            if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
                candidate = payload["error"].get("code")
                if isinstance(candidate, str) and len(candidate) <= 64:
                    code = candidate
            raise XtradotAPIError(
                "XtraDot request was rejected",
                status_code=response.status_code,
                error_code=code,
            )
        if not isinstance(payload, dict) or payload.get("status") != "success":
            raise XtradotAPIError("XtraDot returned an invalid success envelope")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise XtradotAPIError("XtraDot returned an invalid transfer record")
        self._validate_response_reference(reference, data)
        raw_status = data.get("status")
        provider_status = (
            raw_status.strip()[:64]
            if isinstance(raw_status, str) and raw_status.strip()
            else "unknown"
        )

        amount_value = data.get("amount")
        amount = self._amount_string(amount_value)
        currency = data.get("currency")
        if currency is not None and (not isinstance(currency, str) or len(currency) != 3):
            currency = None
        session_id = data.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 160:
            session_id = None
        nip_code = data.get("nip_response_code")
        if not isinstance(nip_code, str) or not nip_code.strip() or len(nip_code) > 16:
            nip_code = None
        return TransferObservation(
            payment_reference=reference,
            source_status=provider_status,
            amount=amount,
            currency=currency,
            occurred_at=_parse_provider_time(data.get("occurred_at") or data.get("created_at")),
            session_id=session_id,
            nip_response_code=nip_code,
            received_at=self._now(),
            safe_request_id=_safe_request_id(payload),
            evidence_basis="sandbox_provider_response",
            freshness="unknown",
            # Per Mock Spec v2, interbank 202 is pending, TIMEOUT is outcome_unknown
            # until requery, and only an exact reference link is tenant-scoped proof.
            requery_required=True,
        )

    @staticmethod
    def _validate_response_reference(reference: str, data: dict[str, Any]) -> None:
        returned = data.get("reference")
        if returned is not None:
            if not isinstance(returned, str) or returned != reference:
                raise XtradotAPIError("XtraDot response reference mismatch")

    @staticmethod
    def _amount_string(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise XtradotAPIError("XtraDot returned an invalid amount")
        if isinstance(value, (str, int, Decimal)):
            try:
                amount = Decimal(str(value))
            except (InvalidOperation, ValueError):
                raise XtradotAPIError("XtraDot returned an invalid amount") from None
        else:
            raise XtradotAPIError("XtraDot returned an invalid amount")
        if not amount.is_finite() or amount < 0:
            raise XtradotAPIError("XtraDot returned an invalid amount")
        return str(value)

    def _now(self) -> datetime:
        current = self._clock()
        if current.utcoffset() is None:
            raise XtradotConfigurationError("XtraDot clock must return a timezone-aware value")
        return current.astimezone(timezone.utc)

    def _unknown(self, reference: str, request_id: str | None = None) -> TransferObservation:
        return TransferObservation(
            payment_reference=reference,
            source_status="outcome_unknown",
            received_at=self._now(),
            safe_request_id=request_id,
            evidence_basis="transport_timeout",
            freshness="unknown",
            requery_required=True,
        )
