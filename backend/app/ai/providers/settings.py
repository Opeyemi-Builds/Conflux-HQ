"""MaaS settings: env loader plus bridge to shared ``Settings``.

Andrew owns this file. Opeyemi owns ``app/core/config.py`` (which now carries
the same ``MAAS_*``/``gateway_key`` fields). Both read the same env names, so
either path works; the bridge below lets shared ``Settings`` drive the slice.
"""

import os
from dataclasses import dataclass

from app.ai.providers.maas import MaasConfig


@dataclass(frozen=True)
class MaasSettings:
    enabled: bool = False
    base_url: str = "http://huawei-maas.ingress-apisix.svc.cluster.local/openai/v1"
    model: str = "glm-5.2"
    timeout_seconds: float = 20.0
    max_attempts: int = 1
    rate_limit_per_minute: int = 60

    @classmethod
    def from_env(cls, env: dict | None = None) -> "MaasSettings":
        source = env if env is not None else os.environ
        get = source.get
        return cls(
            enabled=str(get("MAAS_ENABLED", "false")).lower() in ("1", "true", "yes"),
            base_url=get("MAAS_BASE_URL", cls.base_url),
            model=get("MAAS_MODEL", cls.model),
            timeout_seconds=float(get("MAAS_TIMEOUT_SECONDS", 20.0)),
            max_attempts=int(get("MAAS_MAX_ATTEMPTS", 1)),
            rate_limit_per_minute=int(get("MAAS_RATE_LIMIT_PER_MINUTE", 60)),
        )


def gateway_key(env: dict | None = None) -> str | None:
    """Team key injected at runtime. Server-only; never log or return it."""
    source = env if env is not None else os.environ
    return source.get("GATEWAY_KEY") or None


def maas_config_from_settings(settings) -> MaasConfig:
    """Build a MaasConfig from shared Settings (Opeyemi-owned fields)."""
    return MaasConfig(
        base_url=getattr(settings, "maas_base_url", MaasConfig.base_url) or MaasConfig.base_url,
        model=getattr(settings, "maas_model", MaasConfig.model) or MaasConfig.model,
        timeout_seconds=float(getattr(settings, "maas_timeout_seconds", 20.0) or 20.0),
        max_attempts=int(getattr(settings, "maas_max_attempts", 1) or 1),
    )


def maas_active(settings) -> bool:
    """True only when the operator selected MaaS and explicitly enabled it."""
    provider = str(getattr(settings, "ai_provider", "") or "").lower().strip()
    return provider == "maas" and bool(getattr(settings, "maas_enabled", False))


def maas_key_from_settings(settings) -> str | None:
    """Team key from shared Settings. Server-only; never log or return it."""
    return getattr(settings, "gateway_key", None) or None
