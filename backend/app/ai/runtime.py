"""Provider-neutral helpers for AI calls and runtime telemetry."""
import hashlib
import json
from pathlib import Path

import httpx


def prompt_version(path: Path) -> str:
    """Return a stable short version for the prompt currently in use."""
    if not path.exists():
        return "built-in"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def active_model(settings) -> str:
    provider = settings.ai_provider.lower().strip()
    if provider == "gemini":
        return settings.gemini_model
    return getattr(settings, "maas_model", "glm-5.2")


def active_key(settings) -> str | None:
    provider = settings.ai_provider.lower().strip()
    if provider == "gemini":
        return settings.gemini_api_key
    return getattr(settings, "gateway_key", None)


def gemini_schema(model: type) -> dict:
    schema = model.model_json_schema()
    schema.pop("title", None)
    schema.pop("$defs", None)
    schema.pop("additionalProperties", None)
    for value in schema.get("properties", {}).values():
        value.pop("title", None)
    return schema


def gemini_request(api_key: str, model: str, payload: dict, timeout: float, max_attempts: int) -> tuple[dict, int, int]:
    """Call Gemini REST once and return JSON plus token usage."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    last_error: Exception | None = None
    for _ in range(max(1, max_attempts)):
        try:
            response = httpx.post(url, params={"key": api_key}, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            metadata = data.get("usageMetadata", {})
            return data, int(metadata.get("promptTokenCount", 0)), int(metadata.get("candidatesTokenCount", 0))
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError("Gemini request failed")


def gemini_text(data: dict) -> str:
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if "text" in part:
                return part["text"]
    return ""


def gemini_function_calls(data: dict) -> list[dict]:
    calls = []
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            call = part.get("functionCall")
            if call:
                calls.append(call)
    return calls
