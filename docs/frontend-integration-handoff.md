# Frontend integration handoff — Opeyemi slice (2026-11-10)

For tomorrow's rebuild. Backend only changed; no frontend files touched.
Full spec: [openapi.json](openapi.json). Cross-cutting notes: [RUNNING-CHANGELOG](RUNNING-CHANGELOG.md).

## New endpoints

| Method | Path | Auth | Body / note |
|---|---|---|---|
| GET | `/api/v1/incidents/{id}/overview` | bank login | **Incident detail view.** Read-only; never queues jobs. |
| GET | `/api/v1/incidents/{id}/actions` | bank login | List corrective actions. |
| POST | `/api/v1/incidents/{id}/actions` | operator | `{title, recommendation, owner?, due_date?, bank_confirmed_cause?, change_reference?, validation_plan?}` → 201 |
| PATCH | `/api/v1/actions/{id}` | operator | `{status?, owner?, due_date?, bank_confirmed_cause?, change_reference?, validation_plan?, validation_observation?}`. Illegal jumps → 409. `verified` needs bank_admin + validation evidence, else 403/422. |
| POST | `/api/v1/investigations` | operator | `{incident_id}` → 202, queues exactly one job. Button-triggered only. |
| GET | `/api/v1/incidents/{id}/investigations` | bank login | List runs (facts/hypotheses/evidence IDs). |
| GET | `/api/v1/investigations/{id}` | bank login | Single run. |
| GET | `/api/v1/health/connectors` | bank login | `{status, providers:{database, worker_queue, bank_intake, social, investigation, payment_evidence}, detail}` |

## Overview payload shape

```json
{
  "incident_id": "uuid",
  "issue_type": "failed_transfer",
  "status": "open",
  "complaint_count": 12,
  "affected_channels": {"in_app": 9},
  "likely_cause": "...",
  "cause_confidence": 0.55,
  "summary": "...",
  "complaints": [{"id": "...", "channel": "in_app", "payment_reference": "TRF-...", "transaction_id": null}],
  "social_corroboration": {"linked_complaints": 0, "post_count": 0, "platforms": [], "note": "...triage only..."},
  "payment_evidence": {"total_exceptions": 3, "by_status": {}, "timeline": [], "amount_note": "..."},
  "investigation_latest": null,
  "corrective_actions": [],
  "audit_count": 4
}
```

## UI rules

- Overview GET is safe to poll; investigation POST is a button ("Request investigation"), then poll the runs list.
- Corrective lifecycle: `proposed → accepted → in_progress → monitoring → verified` (`rejected` from any non-terminal). Render as stepper; disable illegal jumps (API 409s them).
- `verified` requires validation observation + cause/change ref; only bank_admin.
- Social counts = triage priority, never "confirmed customers affected".
- No money movement: proposals stay review-only; nothing executes.
