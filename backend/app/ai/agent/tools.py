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
        return evidence["transactions"]
    if name == "get_system_events":
        return {"events": evidence["events"]}
    if name == "compare_baseline":
        return {"issue_type": arguments.get("issue_type"), "window_minutes": arguments.get("window_minutes"), "complaint_count": evidence["incident"]["complaint_count"], "baseline": evidence["incident"]["baseline"]}
    if name == "draft_message":
        return {"audience": arguments["audience"], "facts": arguments["facts"], "status": "facts_accepted_for_draft"}
    raise ValueError(f"Unknown read-only tool: {name}")
