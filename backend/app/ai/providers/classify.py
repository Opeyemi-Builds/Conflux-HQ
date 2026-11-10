"""MaaS-backed complaint classification with strict structured validation.

Contract (for Opeyemi's wiring):
- Input: masked complaint text + channel. Text is untrusted data, wrapped in
  <complaint> tags and never treated as instructions.
- Output: (ClassificationResult, "maas") on success; raises MaasError otherwise
  so the caller falls back to deterministic rules with the complaint and job
  left intact — never a false successful investigation.
- ``None`` is preserved for unknown amount/time (never 0 or "").
"""

from pathlib import Path

from app.ai.fallback import rules_classify
from app.ai.providers.maas import MaasConfig, MaasError, MaasResult, chat_completion
from app.ai.providers.sanitize import wrap_complaint
from app.ai.schemas import ClassificationResult

_PROMPTS = Path(__file__).parents[1] / "prompts"
CLASSIFY_PROMPT = "maas_classify_system.md"

_ALLOWED_ISSUES = {
    "failed_transfer", "double_debit", "card_atm", "pos", "fees",
    "loan", "app_login", "fraud_scam", "other",
}


def build_messages(text: str, channel: str, system: str) -> list[dict]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Channel: {channel}\n{wrap_complaint(text)}"},
    ]


def validate_classification(payload: dict) -> ClassificationResult:
    """Strict validation: unknown issue -> 'other', low-confidence kept as-is."""
    issue = payload.get("issue_type")
    if issue not in _ALLOWED_ISSUES:
        payload = dict(payload, issue_type="other")
    result = ClassificationResult.model_validate(payload)
    return result


def maas_classify(text: str, channel: str = "unknown", *,
                  config: MaasConfig | None = None,
                  gateway_key: str | None = None,
                  system_prompt: str | None = None) -> tuple[ClassificationResult, MaasResult]:
    """Classify via MaaS. Raises MaasError on any provider failure."""
    cfg = config or MaasConfig()
    if system_prompt is None:
        prompt_path = _PROMPTS / CLASSIFY_PROMPT
        system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() \
            else "Classify the masked bank complaint and return JSON."
    messages = build_messages(text, channel, system_prompt)
    result = chat_completion(messages, config=cfg, gateway_key=gateway_key, json_mode=True)
    try:
        classification = validate_classification(result.payload)
    except Exception as exc:
        raise MaasError("malformed") from exc
    classification._runtime = {
        "source": "maas", "model": result.model,
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
    }
    return classification, result


def classify_with_fallback(text: str, channel: str = "unknown", *,
                           config: MaasConfig | None = None,
                           gateway_key: str | None = None) -> tuple[ClassificationResult, str]:
    """MaaS with deterministic fallback: provider failure never loses the complaint."""
    try:
        result, _ = maas_classify(text, channel, config=config, gateway_key=gateway_key)
        return result, "maas"
    except MaasError:
        fallback = rules_classify(text)
        fallback._runtime = {"source": "rules", "model": (config.model if config else MaasConfig().model)}
        return fallback, "rules"
