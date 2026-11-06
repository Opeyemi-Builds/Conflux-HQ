"""Complaint classification with forced Claude tool use and rules fallback."""
import json
import time
from pathlib import Path

import anthropic
import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from .fallback import rules_classify
from .runtime import active_key, active_model, gemini_request, gemini_schema, gemini_text, prompt_version, usage
from .schemas import ClassificationResult

_PROMPTS = Path(__file__).parent / "prompts"


def fallback_classify(text: str) -> ClassificationResult:
    return rules_classify(text)


def classify(text: str, channel: str = "unknown") -> tuple[ClassificationResult, str]:
    """Classify using Claude, falling back safely after bounded attempts."""
    settings = get_settings()
    prompt_path = _PROMPTS / "classify_system.md"
    prompt_id = prompt_version(prompt_path)
    started = time.monotonic()
    provider = settings.ai_provider.lower().strip()
    if not active_key(settings):
        return rules_classify(text), "rules"

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

    system = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "Classify the masked bank complaint and call record_classification."
    tool = {"name": "record_classification", "description": "Record one structured complaint classification.",
            "input_schema": ClassificationResult.model_json_schema()}
    input_tokens = output_tokens = 0
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=settings.anthropic_timeout_seconds,
                                     max_retries=settings.anthropic_max_retries)
        for attempt in range(max(1, settings.anthropic_max_attempts)):
            try:
                response = client.messages.create(model=settings.anthropic_model, max_tokens=600, temperature=0,
                    system=system, tools=[tool], tool_choice={"type": "tool", "name": "record_classification"},
                    messages=[{"role": "user", "content": f"Channel: {channel}\n<complaint>{text}</complaint>"}])
                attempt_input, attempt_output = usage(response)
                input_tokens += attempt_input
                output_tokens += attempt_output
                block = next(block for block in response.content if block.type == "tool_use")
                result = ClassificationResult.model_validate(block.input)
                result._runtime = {"source": "llm", "model": settings.anthropic_model,
                                   "prompt_version": prompt_id,
                                   "latency_ms": round((time.monotonic() - started) * 1000),
                                   "input_tokens": input_tokens, "output_tokens": output_tokens}
                return result, "llm"
            except (ValidationError, StopIteration, anthropic.APIError, anthropic.APIConnectionError,
                    anthropic.APITimeoutError):
                continue
            except Exception:
                break
    except Exception:
        pass
    result = rules_classify(text)
    result._runtime = {"source": "rules", "model": settings.anthropic_model, "prompt_version": prompt_id,
                       "latency_ms": round((time.monotonic() - started) * 1000),
                       "input_tokens": input_tokens, "output_tokens": output_tokens}
    return result, "rules"


def classify_complaint(text: str, channel: str | None = None) -> ClassificationResult:
    result, _ = classify(text, channel or "unknown")
    return result
