import json
import time
from pathlib import Path

import anthropic
from pydantic import ValidationError

from app.ai.runtime import gemini_function_calls, gemini_request, gemini_schema, prompt_version, usage
from app.ai.schemas import CandidateCause, Evidence, Findings
from app.core.config import get_settings
from .tools import ALLOWED_TOOL_NAMES, TOOL_SCHEMAS, run_tool

MAX_STEPS = 8
PROMPT = Path(__file__).parents[1] / "prompts" / "agent_system.md"


def fallback_findings(evidence: dict) -> Findings:
    incident = evidence["incident"]
    events = evidence["events"]
    releases = [event for event in events if event["type"] == "release"]
    if releases and evidence["transactions"]["failed"] > 0:
        release = releases[-1]
        detail = f"Release {release.get('version') or 'unknown'} at {release['starts_at']} preceded the spike"
        confidence = 0.5
        source = Evidence(source="system_events", detail=detail)
    else:
        detail = f"{incident['complaint_count']} complaints against a {incident['baseline']} baseline; no confirmed single cause"
        confidence = 0.3
        source = Evidence(source="baseline", detail=detail)
    candidates = [CandidateCause(cause=detail, confidence=confidence, evidence=[source])]
    return Findings(headline=detail, candidate_causes=candidates,
                    affected_channels=list(evidence["complaints"]["channels"]),
                    matched_transactions=evidence["transactions"]["failed"],
                    propose_reversal_request=False,
                    recommended_action="Verify payment-path logs and assign an incident owner. No money movement is authorized.")


def run_investigation_loop(evidence: dict, audit=None) -> tuple[Findings, str, list[dict]]:
    settings = get_settings()
    trace = []
    started = time.monotonic()
    prompt_id = prompt_version(PROMPT)

    def finish(findings: Findings, source: str) -> tuple[Findings, str, list[dict]]:
        telemetry = {"telemetry": True, "source": source, "model": settings.anthropic_model,
                     "prompt_version": prompt_id, "latency_ms": round((time.monotonic() - started) * 1000),
                     "input_tokens": input_tokens, "output_tokens": output_tokens}
        trace.append(telemetry)
        if audit:
            audit(telemetry)
        return findings, source, trace

    input_tokens = output_tokens = 0
    provider = settings.ai_provider.lower().strip()
    configured_key = settings.gemini_api_key if provider == "gemini" else settings.anthropic_api_key
    if not configured_key:
        return finish(fallback_findings(evidence), "rules")

    system = PROMPT.read_text(encoding="utf-8") if PROMPT.exists() else "Investigate using tools and submit findings."

    if provider == "gemini":
        declarations = []
        for tool in TOOL_SCHEMAS:
            schema = tool["input_schema"]
            schema = dict(schema)
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
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=settings.anthropic_timeout_seconds,
                                 max_retries=settings.anthropic_max_retries)
    for step in range(MAX_STEPS):
        try:
            response = client.messages.create(model=settings.anthropic_model, max_tokens=1600, temperature=0,
                                              system=system, tools=TOOL_SCHEMAS, messages=messages)
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
            entry = {"step": step + 1, "tool": call.name, "input": call.input,
                     "output": json.loads(content) if content.startswith("{") else content}
            trace.append(entry)
            if audit:
                audit(entry)
            tool_results.append({"type": "tool_result", "tool_use_id": call.id, "content": content})
        messages.append({"role": "user", "content": tool_results})
    return finish(fallback_findings(evidence), "rules")
