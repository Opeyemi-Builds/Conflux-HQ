"""Grounding validation and conservative constraints for investigation findings."""
import json
import re

from app.ai.evidence import rank_events
from app.ai.schemas import CandidateCause, Evidence, Findings

_NUMBER_OR_TIME = re.compile(r"(?<!\d)\d+(?:[.,:/-]\d+)*")


def _source_payload(evidence: dict, source: str) -> object:
    if source == "baseline":
        return evidence.get("incident", {})
    if source == "system_events":
        return evidence.get("events")
    return evidence.get(source)


def _grounded(item: Evidence, evidence: dict) -> bool:
    source_data = _source_payload(evidence, item.source)
    if source_data is None:
        return False
    rendered = json.dumps(source_data, default=str)
    return all(token in rendered for token in _NUMBER_OR_TIME.findall(item.detail))


def validate_findings(findings: Findings, evidence: dict) -> Findings:
    """Downgrade numeric/time facts that cannot be found in their stated tool source."""
    invalid_fact = False
    statements = list(findings.supporting_evidence) + list(findings.contradicting_evidence)
    statements.extend(item for cause in findings.candidate_causes for item in cause.evidence)
    for statement in statements:
        if statement.kind == "fact" and not _grounded(statement, evidence):
            statement.kind = "inference"
            invalid_fact = True
    if findings.likely_cause is None and findings.candidate_causes:
        findings.likely_cause = findings.candidate_causes[0].cause
    if findings.confidence is None and findings.candidate_causes:
        findings.confidence = findings.candidate_causes[0].confidence
    if not findings.supporting_evidence and findings.candidate_causes:
        findings.supporting_evidence = list(findings.candidate_causes[0].evidence)
    if findings.recommended_next_step is None:
        findings.recommended_next_step = findings.recommended_action
    if invalid_fact:
        if findings.confidence is not None:
            findings.confidence = max(0.0, findings.confidence - 0.2)
        for cause in findings.candidate_causes:
            cause.confidence = max(0.0, cause.confidence - 0.2)
    return enforce_supported_cause(findings, evidence)


def enforce_supported_cause(findings: Findings, evidence: dict) -> Findings:
    """Do not blame a decoy or claim a cause without a relevant nearby system event."""
    incident = evidence.get("incident", {})
    incident_at = incident.get("started_at", "")
    ranked = rank_events(evidence)
    supported = [
        item for item in ranked
        if item["score"] >= 0.5
        and item["event"].get("type") in {"release", "outage", "config_change"}
        and not any(word in (item["event"].get("description") or "").casefold() for word in ("decoy", "unrelated"))
        and item["event"].get("starts_at", "") <= incident_at
    ]
    if supported:
        event = supported[0]["event"]
        event_terms = [term for term in (event.get("version"), event.get("component")) if term]
        cause_text = (findings.likely_cause or "").casefold()
        if not findings.likely_cause or "decoy" in cause_text or not any(term.casefold() in cause_text for term in event_terms):
            version = event.get("version") or "unknown"
            component = event.get("component") or "system"
            findings.likely_cause = f"Release {version} on {component} is a plausible contributor to the spike."
            findings.confidence = min(findings.confidence if findings.confidence is not None else 0.5, 0.5)
        channel_counts = evidence.get("complaints", {}).get("channels", {})
        findings.affected_channels = sorted(set(findings.affected_channels or channel_counts.keys()))
        return findings

    findings.headline = "Investigation did not identify a supported cause."
    findings.likely_cause = "unknown"
    findings.confidence = min(findings.confidence if findings.confidence is not None else 0.4, 0.4)
    findings.recommended_next_step = "Manually check the payment path and relevant system logs."
    findings.recommended_action = (
        f"{findings.recommended_next_step} No money movement is authorized."
    )
    findings.supporting_evidence = [
        item for item in findings.supporting_evidence
        if item.kind != "fact" or _grounded(item, evidence)
    ]
    findings.candidate_causes = [
        CandidateCause(
            cause="unknown",
            confidence=findings.confidence,
            evidence=[
                Evidence(
                    source="baseline",
                    detail="Available evidence does not establish a system-event cause.",
                    kind="inference",
                )
            ],
        )
    ]
    decoys = [
        event for event in evidence.get("events", [])
        if any(word in (event.get("description") or "").casefold() for word in ("decoy", "unrelated"))
    ]
    if decoys:
        findings.contradicting_evidence.extend(
            Evidence(
                source="system_events",
                detail=f"The nearby event is marked unrelated: {event.get('description', '')}",
                kind="fact",
            )
            for event in decoys
        )
    return findings
