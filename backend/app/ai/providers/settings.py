"""Env-based MaaS settings (Andrew-owned; avoids touching shared config).

Opeyemi owns ``app/core/config.py`` — this loader reads ``MAAS_*`` env vars
directly so the MaaS slice needs no coordination edit. Opeyemi can fold these
into ``Settings`` later using docs/team/maas-settings-proposal.md.
"""

import os
from dataclasses import dataclass


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
