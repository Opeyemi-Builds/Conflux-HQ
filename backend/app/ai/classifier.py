"""Complaint classification with MaaS structured output and rules fallback."""
import json
import time
from pathlib import Path

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from .fallback import rules_classify
from .runtime import active_key, active_model, gemini_request, gemini_schema, gemini_text, prompt_version
from .schemas import ClassificationResult

_PROMPTS = Path(__file__).parent / "prompts"


def fallback_classify(text: str) -> ClassificationResult:
    return rules_classify(text)


def classify(text: str, channel: str = "unknown") -> tuple[ClassificationResult, str]:
    """Classify using MaaS/Gemini, falling back safely to deterministic rules."""
    settings = get_settings()
    prompt_path = _PROMPTS / "classify_system.md"
    prompt_id = prompt_version(prompt_path)
    started = time.monotonic()
    provider = settings.ai_provider.lower().strip()
    if provider == "maas":
        from .forge_classification import classify_forge

        return classify_forge(text, channel)
    if not active_key(settings):
        result = rules_classify(text)
        result._runtime = {"source": "rules", "model": active_model(settings), "prompt_version": prompt_id,
                           "latency_ms": round((time.monotonic() - started) * 1000), "input_tokens": 0,
                           "output_tokens": 0}
        return result, "rules"

    if provider == "gemini":
        system = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "Classify the masked bank complaint and return JSON."
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": f"Channel: {channel}\n<complaint>{text}</complaint>"}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 600,
                                  "responseMimeType": "application/json",
                                  "responseSchema": gemini_schema(ClassificationResult)},
        }
        try:
            data, input_tokens, output_tokens = gemini_request(
                settings.gemini_api_key, settings.gemini_model, payload,
                settings.gemini_timeout_seconds, settings.gemini_max_attempts,
            )
            result = ClassificationResult.model_validate_json(gemini_text(data))
            result._runtime = {"source": "llm", "model": settings.gemini_model,
                               "prompt_version": prompt_id,
                               "latency_ms": round((time.monotonic() - started) * 1000),
                               "input_tokens": input_tokens, "output_tokens": output_tokens}
            return result, "llm"
        except (ValidationError, json.JSONDecodeError, httpx.HTTPError) as exc:
            pass
        except Exception:
            pass
        result = rules_classify(text)
        result._runtime = {"source": "rules", "model": settings.gemini_model, "prompt_version": prompt_id,
                           "latency_ms": round((time.monotonic() - started) * 1000), "input_tokens": 0,
                           "output_tokens": 0}
        return result, "rules"

    if provider == "maas":
        from app.ai.providers.classify import classify_with_fallback as _maas_classify
        from app.ai.providers.rate_limit import RateLimitExceeded, get_limiter
        from app.ai.providers.settings import maas_active, maas_config_from_settings, maas_key_from_settings
        cfg = maas_config_from_settings(settings)
        maas_prompt_id = prompt_version(_PROMPTS / "maas_classify_system.md")
        try:
            if not maas_active(settings):
                raise RateLimitExceeded("maas_disabled")
            get_limiter(int(settings.maas_rate_limit_per_minute or 60)).acquire()
            result, source = _maas_classify(
                text, channel, config=cfg, gateway_key=maas_key_from_settings(settings))
        except RateLimitExceeded:
            result, source = rules_classify(text), "rules"
        if source == "maas":
            runtime = dict(getattr(result, "_runtime", {}))
            runtime["prompt_version"] = maas_prompt_id
            result._runtime = runtime
        else:
            result._runtime = {"source": "rules", "model": cfg.model, "prompt_version": maas_prompt_id,
                               "latency_ms": round((time.monotonic() - started) * 1000), "input_tokens": 0,
                               "output_tokens": 0}
        return result, source

    # Non-Gemini, non-MaaS provider selections fall back to deterministic rules.
    result = rules_classify(text)
    result._runtime = {"source": "rules", "model": active_model(settings), "prompt_version": prompt_id,
                       "latency_ms": round((time.monotonic() - started) * 1000),
                       "input_tokens": 0, "output_tokens": 0}
    return result, "rules"


def classify_complaint(text: str, channel: str | None = None) -> ClassificationResult:
    result, _ = classify(text, channel or "unknown")
    return result
