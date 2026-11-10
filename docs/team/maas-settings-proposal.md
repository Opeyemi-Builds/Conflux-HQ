# MaaS settings proposal — Andrew → Opeyemi (do not apply without coordination)

Additive-only proposal for `backend/app/core/config.py`. No existing field changes.

```python
# Proposed additive fields on Settings (defaults are Forge-safe: disabled without a key)
maas_enabled: bool = False
maas_base_url: str = "http://huawei-maas.ingress-apisix.svc.cluster.local/openai/v1"
maas_model: str = "glm-5.2"  # confirmed listed in Forge guide; never assume glm-3.5
maas_timeout_seconds: float = 20.0
maas_max_attempts: int = 1
maas_rate_limit_per_minute: int = 60  # shared Bank+MaaS budget; client-side guard
```

Env names: `MAAS_ENABLED`, `MAAS_BASE_URL`, `MAAS_MODEL`, `MAAS_TIMEOUT_SECONDS`,
`MAAS_MAX_ATTEMPTS`, `MAAS_RATE_LIMIT_PER_MINUTE`. Team key stays `GATEWAY_KEY`
(runtime-injected, server-only, never logged or returned).

Behavior contract for Opeyemi's wiring:
- `ai_provider == "maas"` routes classification/investigation through Andrew's
  provider with deterministic fallback on any failure.
- Dashboard GETs never call MaaS; only the classify job and explicit
  investigation POST do.
- Telemetry stores model/prompt-version/latency/status/confidence only.
