"""Display-safe trace entries for the bounded investigation."""
def trace_step(incident_id: str, step: int, action: str, result: dict) -> dict:
    return {"incident_id": incident_id, "step": step, "action": action,
            "result_summary": result if isinstance(result, str) else str(result)[:1000]}
