"""Simple bounded incident investigation using deterministic evidence plus Claude."""
import json

from sqlalchemy.orm import Session

from app.ai.evidence import build_evidence, rank_events
from app.core.config import get_settings
from app.db.base import utcnow
from app.models import Incident
from app.models.enums import IncidentStatus
from app.services.audit import log_event


def _template_summary(evidence: dict, candidates: list[dict]) -> tuple[str, float]:
    tx = evidence["transactions"]
    event = candidates[0]["event"] if candidates else None
    if event and event["type"] == "release":
        likely = f"Release {event['version'] or 'unknown'} on {event['component']} may be associated with the spike."
        confidence = 0.8 if tx["failed"] else 0.5
    elif tx["failed"]:
        likely = f"The spike coincides with {tx['failed']} failed transactions across {', '.join(tx['channels']) or 'reported channels'}; a system event has not established a cause."
        confidence = 0.55
    else:
        likely = "No transaction failures or nearby system events strongly explain the complaint spike yet."
        confidence = 0.3
    return likely, confidence


def investigate_incident(db: Session, bank_id, incident: Incident, actor: str = "agent") -> Incident:
    evidence = build_evidence(db, bank_id, incident)
    candidates = rank_events(evidence)
    likely_cause, confidence = _template_summary(evidence, candidates)
    summary = (
        f"{evidence['incident']['complaint_count']} complaints increased against a baseline of "
        f"{evidence['incident']['baseline']:.1f}. {likely_cause}"
    )

    from app.ai.agent.loop import run_investigation_loop

    def audit_trace(entry: dict) -> None:
        log_event(db, bank_id=bank_id, actor=actor, action="agent_tool_call", entity_type="incident",
                  entity_id=str(incident.id), details=entry)

    findings, source, trace = run_investigation_loop(evidence, audit=audit_trace)
    telemetry = next((entry for entry in reversed(trace) if entry.get("telemetry")), {})
    incident._ai_source = source
    settings = get_settings()
    default_model = settings.gemini_model if settings.ai_provider.lower().strip() == "gemini" else settings.anthropic_model
    incident._ai_model = telemetry.get("model", default_model)
    incident._ai_prompt_version = telemetry.get("prompt_version")
    incident._ai_latency_ms = telemetry.get("latency_ms")
    incident._ai_input_tokens = telemetry.get("input_tokens", 0)
    incident._ai_output_tokens = telemetry.get("output_tokens", 0)
    top_cause = findings.candidate_causes[0] if findings.candidate_causes else None
    if top_cause:
        likely_cause = top_cause.cause
        confidence = top_cause.confidence
        summary = findings.headline

    incident.likely_cause = likely_cause
    incident.cause_confidence = confidence
    incident.summary = summary
    incident.status = IncidentStatus.AWAITING_APPROVAL
    db.commit()

    log_event(db, bank_id=bank_id, actor=actor, action="incident_investigated", entity_type="incident",
              entity_id=str(incident.id), details={"confidence": confidence, "source": source,
                       "trace_steps": len([entry for entry in trace if not entry.get("telemetry")]),
                       "candidate_count": len(candidates), "evidence": evidence,
                       "model": incident._ai_model, "prompt_version": incident._ai_prompt_version,
                       "latency_ms": incident._ai_latency_ms, "input_tokens": incident._ai_input_tokens,
                       "output_tokens": incident._ai_output_tokens})
    db.commit()
    return incident
