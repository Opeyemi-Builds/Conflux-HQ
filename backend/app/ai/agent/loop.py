import json
import time
from pathlib import Path

import anthropic
from pydantic import ValidationError

from app.ai.evidence import rank_events
from app.ai.runtime import active_model, gemini_function_calls, gemini_request, prompt_version, usage
from app.ai.schemas import CandidateCause, Evidence, Findings
from app.core.config import get_settings
from .tools import ALLOWED_TOOL_NAMES, TOOL_SCHEMAS, run_tool

MAX_STEPS = 8
PROMPT = Path(__file__).parents[1] / "prompts" / "agent_system.md"


def with_registry(evidence: dict) -> dict:
    """Ensure the evidence bundle carries a citable registry for MaaS briefs.

    Bundles built by ``build_evidence`` already include one; synthetic or
    inline bundles from tests/tools get a best-effort registry derived from
    their contents so validation stays strict everywhere.
    """
    if isinstance(evidence.get("evidence_registry"), dict):
        return evidence
    registry: dict = {"complaints": [], "transactions": [], "system_events": [],
                      "payment_exceptions": [], "social": []}
    for key in registry:
        source_key = "events" if key == "system_events" else key
        for item in evidence.get(source_key, []) if isinstance(evidence.get(source_key), list) else []:
            if isinstance(item, dict) and (item.get("id") or item.get("starts_at")):
                registry[key].append({"id": str(item.get("id") or item.get("starts_at"))})
    return {**evidence, "evidence_registry": registry}


def _brief_to_findings(brief, evidence: dict) -> Findings:
    """Project Andrew's grounded brief onto the legacy Findings contract."""
    tx = evidence.get("transactions", {}) if isinstance(evidence, dict) else {}
    complaints = evidence.get("complaints", {}) if isinstance(evidence, dict) else {}
    dominant = tx.get("dominant_processor")
    if not dominant and tx.get("failed_by_processor"):
        by_proc = tx["failed_by_processor"]
        dominant = max(by_proc.items(), key=lambda item: item[1])[0] if max(by_proc.values(), default=0) > 0 else None
    top = brief.hypotheses[0] if brief.hypotheses else None
    cause = top.statement if top else "Cause not established from available evidence."
    confidence = top.confidence if top else brief.confidence
    detail = Evidence(source="baseline", detail="; ".join(brief.observed_facts[:4]) or cause)
    candidates = [CandidateCause(cause=cause, confidence=confidence, evidence=[detail])]
    return Findings(
        headline=cause,
        candidate_causes=candidates,
        affected_channels=list(complaints.get("channels", {})) if isinstance(complaints, dict) else [],
        affected_switch=dominant,
        matched_transactions=int(tx.get("failed", 0) or 0),
        propose_reversal_request=False,
        recommended_action="; ".join(brief.recommended_checks[:3]) or
        "Verify payment-path logs and assign an incident owner. No money movement is authorized.",
    )


def fallback_findings(evidence: dict) -> Findings:
    incident = evidence["incident"]
    tx = evidence.get("transactions", {})
    ranked = rank_events(evidence)
    releases = [item for item in ranked if item["event"].get("type") == "release"]
    dominant_switch = tx.get("dominant_processor")
    if not dominant_switch and tx.get("failed_by_processor"):
        by_proc = tx["failed_by_processor"]
        dominant_switch = max(by_proc.items(), key=lambda item: item[1])[0] if max(by_proc.values(), default=0) > 0 else None

    if releases and tx.get("failed", 0) > 0:
        top = releases[0]
        release = top["event"]
        switch_note = f" via {dominant_switch}" if dominant_switch else ""
        detail = (
            f"Release {release.get('version') or 'unknown'} on {release.get('component', 'service')} "
            f"at {release['starts_at']} preceded the spike{switch_note}"
        )
        confidence = top["score"]
        source = Evidence(source="system_events", detail=detail)
    else:
        detail = f"{incident['complaint_count']} complaints against a {incident['baseline']} baseline; no confirmed single cause"
        confidence = 0.3
        source = Evidence(source="baseline", detail=detail)

    candidates = [CandidateCause(cause=detail, confidence=confidence, evidence=[source])]
    propose_reversal = bool(tx.get("matched_complaints", 0) > 0 and tx.get("unreversed_failed", 0) > 0)
    return Findings(
        headline=detail,
        candidate_causes=candidates,
        affected_channels=list(evidence["complaints"]["channels"]),
        affected_switch=dominant_switch,
        matched_transactions=tx.get("failed", 0),
        propose_reversal_request=propose_reversal,
        recommended_action="Verify payment-path logs and assign an incident owner. No money movement is authorized.",
    )


def run_investigation_loop(evidence: dict, audit=None) -> tuple[Findings, str, list[dict]]:
    settings = get_settings()
    trace = []
    started = time.monotonic()
    prompt_id = prompt_version(PROMPT)
    model_name = active_model(settings)

    def finish(findings: Findings, source: str) -> tuple[Findings, str, list[dict]]:
        telemetry = {
            "telemetry": True,
            "source": source,
            "model": model_name,
            "prompt_version": prompt_id,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        trace.append(telemetry)
        if audit:
            audit(telemetry)
        return findings, source, trace

    input_tokens = output_tokens = 0
    provider = settings.ai_provider.lower().strip()
    if provider == "maas":
        from app.ai.investigation import investigate_with_fallback as _maas_investigate
        from app.ai.providers.rate_limit import RateLimitExceeded, get_limiter
        from app.ai.providers.settings import maas_active, maas_config_from_settings, maas_key_from_settings
        try:
            if not maas_active(settings):
                raise RateLimitExceeded("maas_disabled")
            get_limiter(int(settings.maas_rate_limit_per_minute or 60)).acquire()
            brief, source, telemetry = _maas_investigate(
                with_registry(evidence),
                config=maas_config_from_settings(settings),
                gateway_key=maas_key_from_settings(settings),
            )
            input_tokens = telemetry.get("input_tokens", 0)
            output_tokens = telemetry.get("output_tokens", 0)
            entry = {"step": 1, "tool": "maas_investigate", "input": "evidence_bundle",
                     "output": {"source": source, "confidence": brief.confidence}}
            trace.append(entry)
            if audit:
                audit(entry)
            result = finish(_brief_to_findings(brief, evidence), source)
            # Stash the grounded brief on the telemetry entry so core/worker can
            # persist facts/hypotheses/checks without a second model call.
            trace[-1]["brief"] = brief.model_dump()
            return result
        except RateLimitExceeded:
            return finish(fallback_findings(evidence), "rules")
    configured_key = settings.gemini_api_key if provider == "gemini" else settings.anthropic_api_key
    if not configured_key:
        return finish(fallback_findings(evidence), "rules")

    system = PROMPT.read_text(encoding="utf-8") if PROMPT.exists() else "Investigate using tools and submit findings."

    if provider == "gemini":
        declarations = []
        for tool in TOOL_SCHEMAS:
            schema = dict(tool["input_schema"])
            schema.pop("title", None)
            schema.pop("additionalProperties", None)
            declarations.append({"name": tool["name"], "description": tool["description"], "parameters": schema})
        contents = [{"role": "user", "parts": [{"text": "Investigate the incident using the evidence tools, then call submit_findings.\n" + json.dumps(evidence, default=str)}]}]
        payload_base = {
            "systemInstruction": {"parts": [{"text": system}]},
            "tools": [{"functionDeclarations": declarations}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 1600},
        }
        for step in range(MAX_STEPS):
            try:
                payload = {**payload_base, "contents": contents}
                data, step_input, step_output = gemini_request(
                    settings.gemini_api_key, settings.gemini_model, payload,
                    settings.gemini_timeout_seconds, settings.gemini_max_attempts,
                )
                input_tokens += step_input
                output_tokens += step_output
            except Exception:
                break
            calls = gemini_function_calls(data)
            if not calls:
                break
            parts = []
            for call in calls:
                name = call.get("name", "")
                arguments = call.get("args", {})
                if name == "submit_findings":
                    try:
                        findings = Findings.model_validate(arguments)
                        entry = {"step": step + 1, "tool": "submit_findings", "input": arguments}
                        trace.append(entry)
                        if audit:
                            audit(entry)
                        return finish(findings, "llm")
                    except ValidationError as exc:
                        response = {"error": f"Invalid findings: {exc}"}
                elif name in ALLOWED_TOOL_NAMES:
                    try:
                        response = run_tool(name, arguments, evidence)
                    except Exception as exc:
                        response = {"error": str(exc)}
                else:
                    response = {"error": f"Tool is not allowlisted: {name}"}
                entry = {"step": step + 1, "tool": name, "input": arguments, "output": response}
                trace.append(entry)
                if audit:
                    audit(entry)
                parts.append({"functionResponse": {"name": name, "response": response}})
            contents.append({"role": "user", "parts": parts})
        return finish(fallback_findings(evidence), "rules")

    messages = [{"role": "user", "content": "Investigate the incident using the evidence tools, then call submit_findings.\n" + json.dumps(evidence, default=str)}]
    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.anthropic_timeout_seconds,
        max_retries=settings.anthropic_max_retries,
    )
    for step in range(MAX_STEPS):
        try:
            response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1600,
                temperature=0,
                system=system,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
            response_input, response_output = usage(response)
            input_tokens += response_input
            output_tokens += response_output
        except Exception:
            break
        messages.append({"role": "assistant", "content": response.content})
        calls = [block for block in response.content if block.type == "tool_use"]
        if not calls:
            break
        tool_results = []
        for call in calls:
            if call.name == "submit_findings":
                try:
                    findings = Findings.model_validate(call.input)
                    entry = {"step": step + 1, "tool": "submit_findings", "input": call.input}
                    trace.append(entry)
                    if audit:
                        audit(entry)
                    return finish(findings, "llm")
                except ValidationError as exc:
                    content = f"Invalid findings: {exc}"
            elif call.name in ALLOWED_TOOL_NAMES:
                try:
                    result = run_tool(call.name, call.input, evidence)
                    content = json.dumps(result, default=str)
                except Exception as exc:
                    result = {"error": str(exc)}
                    content = json.dumps(result)
            else:
                content = json.dumps({"error": f"Tool is not allowlisted: {call.name}"})
            entry = {
                "step": step + 1,
                "tool": call.name,
                "input": call.input,
                "output": json.loads(content) if content.startswith("{") else content,
            }
            trace.append(entry)
            if audit:
                audit(entry)
            tool_results.append({"type": "tool_result", "tool_use_id": call.id, "content": content})
        messages.append({"role": "user", "content": tool_results})
    return finish(fallback_findings(evidence), "rules")
