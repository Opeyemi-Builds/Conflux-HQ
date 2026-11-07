"""Read-only tools exposed to the investigation agent."""
from app.ai.schemas import Findings

ALLOWED_TOOL_NAMES = frozenset({
    "get_incident_stats", "search_transactions", "get_system_events", "compare_baseline",
    "draft_message", "submit_findings",
})

TOOL_SCHEMAS = [
    {"name": "get_incident_stats", "description": "Volume, growth, start time, channels and regions for an incident.", "input_schema": {"type": "object", "properties": {"incident_id": {"type": "string"}}, "required": ["incident_id"]}},
    {"name": "search_transactions", "description": "Count transactions and failures near the incident.", "input_schema": {"type": "object", "properties": {"channel": {"type": "string"}, "switch": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}}, "required": []}},
    {"name": "get_system_events", "description": "Read releases and outages near the incident.", "input_schema": {"type": "object", "properties": {"start": {"type": "string"}, "end": {"type": "string"}}, "required": ["start", "end"]}},
    {"name": "compare_baseline", "description": "Compare complaint volume with its baseline.", "input_schema": {"type": "object", "properties": {"issue_type": {"type": "string"}, "window_minutes": {"type": "integer"}}, "required": ["issue_type", "window_minutes"]}},
    {"name": "draft_message", "description": "Return verified facts for a customer or IT draft.", "input_schema": {"type": "object", "properties": {"audience": {"type": "string", "enum": ["customer", "it"]}, "facts": {"type": "object"}}, "required": ["audience", "facts"]}},
    {"name": "submit_findings", "description": "Submit validated investigation findings and end the run.", "input_schema": Findings.model_json_schema()},
]


def run_tool(name: str, arguments: dict, evidence: dict) -> dict:
    if name not in ALLOWED_TOOL_NAMES:
        raise ValueError(f"Tool is not allowlisted: {name}")
    if name == "get_incident_stats":
        return {"complaints": evidence["complaints"], "incident": evidence["incident"]}
    if name == "search_transactions":
        tx = dict(evidence["transactions"])
        switch = (arguments or {}).get("switch")
        channel = (arguments or {}).get("channel")
        if switch and switch in tx.get("failed_by_processor", {}):
            tx["filtered_switch"] = switch
            tx["filtered_failed"] = tx["failed_by_processor"][switch]
        if channel:
            tx["filtered_channel"] = channel
            tx["channel_present"] = channel.lower() in [c.lower() for c in tx.get("channels", [])]
        return tx
    if name == "get_system_events":
        events = list(evidence.get("events", []))
        start = (arguments or {}).get("start")
        end = (arguments or {}).get("end")
        if start or end:
            filtered = [
                e for e in events
                if (not start or e.get("starts_at", "") >= start)
                and (not end or e.get("starts_at", "") <= end)
            ]
            if filtered:
                events = filtered
        return {"events": events}
    if name == "compare_baseline":
        return {
            "issue_type": arguments.get("issue_type") or evidence["incident"].get("issue_type"),
            "window_minutes": arguments.get("window_minutes", 15),
            "complaint_count": evidence["incident"]["complaint_count"],
            "baseline": evidence["incident"]["baseline"],
            "growth_rate": evidence["incident"].get("growth_rate"),
        }
    if name == "draft_message":
        return {"audience": arguments["audience"], "facts": arguments["facts"], "status": "facts_accepted_for_draft"}
    raise ValueError(f"Unknown read-only tool: {name}")
