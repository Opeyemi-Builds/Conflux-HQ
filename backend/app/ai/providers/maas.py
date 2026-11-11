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

import hashlib
import json
import os
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock
from typing import TypeVar
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ValidationError

Result = TypeVar("Result", bound=BaseModel)

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
    timeout_seconds: float = 45.0
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
    # GLM-5.2 on Forge Huawei APISIX gateway can stall with response_format=json_object.
    # System prompts strictly enforce JSON and parse_json_text safely extracts and decodes it.
    if disable_reasoning:
        body["chat_template_kwargs"] = {"thinking": False}
    return body


def _extract_text(data: dict) -> str:
    try:
        return data["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, AttributeError, TypeError) as exc:
        raise MaasError("malformed") from exc


def parse_json_text(text: str) -> dict:
    """Parse model JSON, tolerating markdown fences and conversational wrapping. Raises MaasError('malformed')."""
    cleaned = text.strip()
    # 1. Direct JSON parse
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 2. Extract from markdown code fences if present
    if "```" in cleaned:
        start_fence = cleaned.find("```")
        content_start = cleaned.find("\n", start_fence)
        if content_start != -1:
            end_fence = cleaned.find("```", content_start)
            fence_block = cleaned[content_start:end_fence if end_fence != -1 else len(cleaned)].strip()
            try:
                parsed = json.loads(fence_block)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

    # 3. Find first '{' and last '}'
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        snippet = cleaned[first_brace:last_brace + 1]
        try:
            parsed = json.loads(snippet)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise MaasError("malformed")


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


class MaaSFailure(Exception):
    """Only stable reason codes leave the transport."""


@dataclass(frozen=True)
class MaaSSettings:
    base_url: str
    model: str
    gateway_key: str = field(repr=False)
    timeout: float = 8

    def __post_init__(self):
        url = urlsplit(self.base_url)
        if (
            url.scheme not in {"http", "https"} or not url.hostname or url.username is not None
            or url.password is not None or url.query or url.fragment
            or not self.model.strip() or not self.gateway_key.strip() or not 0 < self.timeout <= 30
        ):
            raise ValueError("Invalid Forge MaaS configuration")

    @classmethod
    def from_environment(cls):
        return cls(
            base_url=os.environ.get("MAAS_BASE_URL", ""),
            model=os.environ.get("MAAS_MODEL", ""),
            gateway_key=os.environ.get("GATEWAY_KEY", ""),
            timeout=float(os.environ.get("MAAS_TIMEOUT_SECONDS", "8")),
        )


class MaaSClient:
    def __init__(
        self,
        settings: MaaSSettings,
        acquire_shared_slot: Callable[[], bool],
        transport: httpx.BaseTransport | None = None,
    ):
        self.settings = settings
        self._acquire = acquire_shared_slot
        self._transport = transport
        self._lock = Lock()
        self._cache: OrderedDict[str, tuple[float, str]] = OrderedDict()

    def complete(
        self,
        system: str,
        data: dict,
        schema: type[Result],
        validate: Callable[[Result], None],
        *,
        scope: str | None = None,
        max_tokens: int = 1200,
    ) -> tuple[Result, str]:
        content = json.dumps(data, ensure_ascii=False, sort_keys=True)
        instructions = system + "\nReturn a single JSON object matching this schema:\n" + json.dumps(schema.model_json_schema())
        key = hashlib.sha256(json.dumps([scope, self.settings.model, instructions, content]).encode()).hexdigest()
        if scope is not None:
            with self._lock:
                cached = self._cache.get(key)
                if cached and cached[0] > time.monotonic():
                    self._cache.move_to_end(key)
                    return schema.model_validate_json(cached[1]), "cache"

        try:
            allowed = self._acquire()
        except Exception:
            raise MaaSFailure("budget_unavailable") from None
        if not allowed:
            raise MaaSFailure("budget_exhausted")

        url = self.settings.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.model,
            "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": content}],
            "thinking": {"type": "disabled"},
            "temperature": 0,
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            with httpx.Client(
                transport=self._transport, timeout=self.settings.timeout, trust_env=False, follow_redirects=False,
            ) as client:
                response = client.post(url, headers={"apikey": self.settings.gateway_key}, json=payload)
            if response.status_code == 429:
                raise MaaSFailure("rate_limited")
            if not response.is_success:
                raise MaaSFailure("provider_unavailable")
            choice = response.json()["choices"][0]
            message = choice["message"]
            if choice.get("finish_reason") != "stop" or message.get("tool_calls") or message.get("function_call"):
                raise MaaSFailure("invalid_output")
            raw = message["content"]
            if not isinstance(raw, str) or len(raw) > 16000:
                raise MaaSFailure("invalid_output")
            result = schema.model_validate_json(raw)
            validate(result)
        except httpx.TimeoutException:
            raise MaaSFailure("timeout") from None
        except httpx.HTTPError:
            raise MaaSFailure("provider_unavailable") from None
        except (KeyError, IndexError, TypeError, AttributeError, ValueError, ValidationError):
            raise MaaSFailure("invalid_output") from None

        if scope is not None:
            with self._lock:
                self._cache[key] = (time.monotonic() + 300, result.model_dump_json())
                self._cache.move_to_end(key)
                if len(self._cache) > 128:
                    self._cache.popitem(last=False)
        return result, "ok"
