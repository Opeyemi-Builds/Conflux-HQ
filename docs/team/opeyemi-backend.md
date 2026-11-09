# Opeyemi — Incident command, corrective action and integration lead

Read [shared sprint plan](../backend-team-workplan.md) and the [agent prompting guide](agent-prompting-guide.md) first. Use the copyable Opeyemi prompt there when delegating work. Backend today; no frontend edits. Branch suggestion: `feat/incident-remediation`.

## Goal

Own the shared backend integration and make Conflux prove its promise: bank complaints and social signals become an evidence-backed payment incident, an investigation brief and a tracked corrective action. Coordinate contracts and migration order; do not rewrite other people's feature slices.

## Read first

- `backend/app/api/router.py`, `backend/app/main.py`, `backend/app/core/config.py`
- `backend/app/api/routes/incidents.py`
- `backend/app/ai/evidence.py`
- `backend/app/models/incident.py`, `backend/app/models/system_event.py`, `backend/app/models/audit_log.py`
- `backend/app/services/worker.py`
- `backend/app/api/routes/reconciliation.py`
- `backend/app/services/reconciliation_reporting.py`
- `backend/app/api/routes/health.py`
- `docs/backend-implementation.md` and the shared sprint plan

## Owned work

1. Freeze and publish the shared API contracts. Ensure all new routes are bank-scoped and every response has explicit provenance/freshness where relevant.
2. Extend incident read models/endpoints with affected complaint IDs/counts, linked payment evidence IDs, social corroboration count/source, payment status counts, likely-cause facts/hypotheses, missing evidence, recommended next action and owner. Keep existing incident/reconciliation endpoints compatible.
3. Add a corrective-action model/service/API if not already available. Fields: incident ID, bank ID, title/recommendation, owner, due date, status (`proposed`, `accepted`, `in_progress`, `monitoring`, `verified`, `rejected`), bank-confirmed cause, change reference, validation plan, validation observation, actor/timestamps. `verified` requires evidence and authorised actor. No automatic closure merely because complaint volume falls.
4. Add investigation request/result persistence and status if needed. Request must be explicit operator action or queued job; GET/dashboard polling remains read-only. Store model/provider status and evidence IDs, not secrets or raw PII.
5. Orchestrate jobs idempotently: intake → classification → clustering/incident enrichment → payment evidence refresh → investigation → corrective action reminders. Avoid duplicate jobs and avoid model calls in polling. Preserve failure states and dead-letter behavior.
6. Add bank/provider connector health to health responses without making an unavailable optional connector make the whole service look healthy. Distinguish database, worker, X/social, MaaS and XtraDot states.
7. Integrate Opeyemi-owned route/migration exports carefully. Assign one Alembic revision chain after checking current head. No multiple heads, no reusing existing revision IDs.
8. Build a deterministic end-to-end test fixture: complaints from bank intake/social replay, related XtraDot-like evidence, incident, grounded investigation, corrective action and audit entries. Label all data synthetic/sandbox.
9. Produce actual OpenAPI/sample payloads for tomorrow's frontend rebuild. Do not touch frontend files today.

## Evidence rules

- Customer complaint = reported evidence.
- Provider event = provider/sandbox evidence.
- Transaction/reference match = candidate unless exact provider-scoped reference.
- System timing = correlation, not confirmed cause.
- GLM output = hypothesis/recommendation, not fact.
- Bank-confirmed root cause and remediation validation require explicit human/authoritative evidence.
- Social volume increases triage priority only; it does not prove truth, causation or affected customer count.

## Handoffs

Receive from dev_id: complaint receipt and stable IDs. From Adfola: normalized payment evidence/status/event rules. From Andrew: validated investigation schema and evidence IDs. Return a single integration contract, migration order, route registration, health status and demo command to all.

## Required tests

Tenant isolation; exact incident membership; no false cause; read-only investigation; corrective-action state transition permissions; verify requires evidence; duplicate jobs; provider unavailable; stale evidence; audit correlation IDs; no secret/raw PII logs; no automatic money movement; existing reconciliation/proposal tests remain green.

## Done today

One command or documented sequence runs the synthetic end-to-end scenario and produces: complaint cluster, incident with evidence timeline, investigation brief separating facts/hypotheses/missing evidence, corrective action with owner/status and audit history. Payment proposals remain review-only. Deliver OpenAPI and a frontend handoff note for tomorrow.

## Coordinator rules

Ask teammates for interface changes before touching their files. Keep reviews short and concrete. If Forge credentials or deployment access is blocked, use synthetic contract fixtures and record the exact blocked smoke test; do not weaken security or claim it passed.
