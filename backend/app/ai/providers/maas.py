"""Server-only Huawei MaaS client (OpenAI-compatible chat completions).

Security rules enforced here, not by convention elsewhere:
- The team key (``GATEWAY_KEY``) travels only in the ``apikey`` header of this
  module's requests. It is never logged, never returned, and never embedded in
  error messages or telemetry.
- Complaint/social text is untrusted model *input*; this module never treats it
  as instructions and never exposes raw PII in logs.
- Read-only: this client only calls ``/chat/completions``. It cannot call
  transfers, refunds, reversals, proposals, or outbound messages.
"""

import json
import time
from dataclasses import dataclass, field

import httpx

# Forge Huawei MaaS endpoint (cluster-internal; unreachable from Render/Vercel).
DEFAULT_BASE_URL = "http://huawei-maas.ingress-apisix.svc.cluster.local/openai/v1"
# Model confirmed listed in the Forge guide. Never assume ``glm-3.5`` exists.
DEFAULT_MODEL = "glm-5.2"


class MaasError(Exception):
    """Typed MaaS failure so callers can fall back without leaking details."""

    def __init__(self, kind: str, status_code: int | None = None):
        super().__init__(f"maas_{kind}")
        self.kind = kind  # unavailable | quota | timeout | malformed | unexpected
        self.status_code = status_code


@dataclass
class MaasConfig:
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 20.0
    max_attempts: int = 1
    # Reasoning disabled per Forge guidance (137 tokens vs 18 for a one-liner).
    disable_reasoning: bool = True


@dataclass
class MaasResult:
    """Parsed model output plus audit-safe telemetry (no raw text, no secrets)."""

    payload: dict
    model: str
    latency_ms: int
    status: str = "ok"
    input_tokens: int = 0
    output_tokens: int = 0
    attempts: int = 1
    extra: dict = field(default_factory=dict)


def _body(messages: list[dict], model: str, disable_reasoning: bool,
           json_mode: bool) -> dict:
    body: dict = {"model": model, "messages": messages, "temperature": 0}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if disable_reasoning:
        body["chat_template_kwargs"] = {"thinking": False}
    return body


def _extract_text(data: dict) -> str:
    try:
        return data["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, AttributeError, TypeError) as exc:
        raise MaasError("malformed") from exc


def parse_json_text(text: str) -> dict:
    """Parse model JSON, tolerating markdown fences. Raises MaasError('malformed')."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = lines[1:] if len(lines) > 1 else []
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise MaasError("malformed") from exc
    if not isinstance(parsed, dict):
        raise MaasError("malformed")
    return parsed


def chat_completion(messages: list[dict], *, config: MaasConfig,
                    gateway_key: str | None,
                    json_mode: bool = True) -> MaasResult:
    """Call MaaS chat completions once (plus bounded retries on 5xx only).

    ``gateway_key`` is used for the ``apikey`` header and nothing else; it never
    appears in exceptions, logs, or the returned telemetry.
    """
    if not gateway_key:
        raise MaasError("unavailable")
    url = config.base_url.rstrip("/") + "/chat/completions"
    started = time.monotonic()
    attempts = max(1, config.max_attempts)
    last_error: MaasError | None = None
    usage_meta: dict = {}
    for attempt in range(1, attempts + 1):
        try:
            response = httpx.post(
                url,
                headers={"apikey": gateway_key, "Content-Type": "application/json"},
                json=_body(messages, config.model, config.disable_reasoning, json_mode),
                timeout=config.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise MaasError("timeout") from exc
        except httpx.HTTPError as exc:
            last_error = MaasError("unavailable")
            _ = exc
            break
        if response.status_code == 429:
            raise MaasError("quota", status_code=429)
        if response.status_code == 404:
            # Model not enabled on Huawei side — caller falls back; try another
            # listed model only via explicit operator action, never silently here.
            raise MaasError("unavailable", status_code=404)
        if 500 <= response.status_code < 600:
            last_error = MaasError("unavailable", status_code=response.status_code)
            continue
        if response.status_code != 200:
            raise MaasError("unexpected", status_code=response.status_code)
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise MaasError("malformed") from exc
        text = _extract_text(data)
        payload = parse_json_text(text) if json_mode else {"text": text}
        usage_meta = data.get("usage", {}) if isinstance(data, dict) else {}
        return MaasResult(
            payload=payload,
            model=config.model,
            latency_ms=round((time.monotonic() - started) * 1000),
            input_tokens=int(usage_meta.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage_meta.get("completion_tokens", 0) or 0),
            attempts=attempt,
        )
    raise last_error or MaasError("unavailable")
