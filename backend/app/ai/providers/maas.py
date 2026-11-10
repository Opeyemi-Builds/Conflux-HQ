"""Read-only Forge MaaS transport. The gateway quota is shared with payment reads."""
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
