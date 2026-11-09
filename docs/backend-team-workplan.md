# Conflux backend sprint — four-person ownership

Audience: dev_id, Andrew, Adfola and Opeyemi.

Sprint: backend on 9 November 2026; frontend rebuild on 10 November 2026. These are targets, not a claim that every production integration can be completed in one day.

This replaces the earlier three-person workplan. Existing implementation is a starting point: inspect and reuse it instead of rebuilding completed reconciliation, social, queue or authentication features.

## Product decision

Conflux unifies bank complaints and social signals, detects shared payment problems, correlates available payment evidence, supports investigation and tracks corrective actions to reduce recurrence. It is not a payment gateway or an autonomous root-cause oracle.

Core flow:

Complaint ingestion → privacy processing → classification → pattern/incident detection → payment evidence correlation → investigation brief → assigned corrective action → post-change validation.

## Assignments

| Person | Backend ownership today | Task file |
|---|---|---|
| dev_id | Bank complaint ingestion, source provenance and existing social intake integration | [dev_id](team/dev-id-backend.md) |
| Andrew | Huawei MaaS classification and grounded investigation services | [Andrew](team/andrew-backend.md) |
| Adfola | XtraDot payment evidence connector and signed webhook receiver | [Adfola](team/adfola-backend.md) |
| Opeyemi | Incident/evidence API, corrective-action lifecycle, shared integration and Forge packaging | [Opeyemi](team/opeyemi-backend.md) |

## Scope boundaries

- No frontend implementation today. Tomorrow rebuild around complaint → incident → evidence → corrective action, not unrelated lending or geographic-risk features.
- No live NIBSS integration. XtraDot is synthetic and does not connect to NIBSS.
- The supplied catalogue has no complaint API. Demonstrate bank-side delivery using a labelled synthetic support-ticket sender into Conflux's ingestion endpoint.
- Payment evidence shows status, not necessarily technical root cause or beneficiary-ledger proof.
- A timeout is an unknown outcome: query/requery, never resubmit a transfer.
- The `.05` test trigger is an AMOUNT ending in `.05`, not a reference suffix.
- Social corroboration may increase priority but does not prove an allegation or justify an automatic critical severity. Deduplicate reposts and distinguish unique customers where identity is reliable.
- Corrective actions require bank confirmation. Lower complaint counts alone do not prove a permanent fix; account for payment volume and source-feed health.
- Existing refund/reversal proposals remain review-only. No money movement is added to operational investigation.

## Shared file ownership

Opeyemi owns edits to shared registration/configuration: API router, main app, settings, dependency manifests, worker dispatch, model exports, enum changes and migration integration. Others supply exact integration patches or coordinate a short handoff before editing these files. Do not replace those files wholesale.

Each developer owns tests for their module. Opeyemi owns end-to-end orchestration, not writing everyone else's tests.

Opeyemi assigns unique Alembic revision IDs after checking the current head. Never reuse `0008` or create concurrent uncoordinated heads. Each model owner supplies their migration and downgrade; Opeyemi integrates the chain.

Suggested separate branches: `feat/bank-complaint-ingestion`, `feat/maas-investigation`, `feat/xtradot-evidence`, `feat/incident-remediation`. Do not commit kubeconfigs or secrets. Do not commit or push another person's changes.

## Proposed contracts — freeze together before implementation

These are TARGET contracts, not claims that endpoints already exist. Export actual OpenAPI after integration.

### Bank complaint intake

`POST /api/v1/ingestion/complaints` with a bank-bound service credential, not the Forge gateway key.

Required: `source_system`, `external_id`, `channel`, `occurred_at` (timezone-aware), `text`.
Optional: pseudonymous `customer_ref`, `payment_reference`, decimal-string `amount`, `currency`, `region`, `language`.

Server derives bank from credential and records `received_at`. First version handles create-only delivery; updates to an existing external ticket are explicitly deferred. Unique identity is `(bank_id, connector_id, external_id)`.

Return 202 only after durable acceptance and atomic job enqueue: `complaint_id`, `receipt_id`, `processing_status`, `duplicate`. Same identity and normalized content returns existing IDs without a new job; different content returns 409. Reject invalid/unauthorised payloads before processing.

### Evidence boundary

Adfola exposes a bank-scoped service to read retained payment evidence by reference and a queued refresh operation. Opeyemi consumes this; Andrew never receives credentials.

Normalized evidence: local `id`, `bank_id`, `provider`, `environment`, provider event ID where supplied, `payment_reference`, `event_type`, source status, `occurred_at`, `received_at`, safe source/request reference, optional decimal-string amount/currency, evidence basis and freshness.

Do not infer missing fields. An exact reference link must also be tenant/provider scoped; an amount/time match is only a candidate.

### Investigation boundary

Opeyemi supplies Andrew a bounded, masked evidence bundle with stable local IDs, source/freshness labels and counts. Andrew returns validated structured content: observed facts, hypotheses, supporting/contradicting evidence IDs, missing evidence, suggested checks, suggested owner and corrective recommendations. Confidence describes a hypothesis, not a verified probability unless calibrated.

### Corrective actions

Opeyemi provides persisted incident actions with owner, due date, recommendation, status, bank-confirmed cause if provided, change reference, validation plan and validation observations. Suggested states: `proposed`, `accepted`, `in_progress`, `monitoring`, `verified`, `rejected`. Verify requires authorised review and recorded validation evidence.

## Integration order

1. Agree contracts, existing-file boundaries and migration sequence immediately.
2. Build parallel vertical slices using synthetic fixtures; no one waits for live Forge access to write unit tests.
3. Merge ingestion first; preserve existing complaint/worker behavior.
4. Merge payment evidence and signature/idempotency tests.
5. Merge structured investigation and corrective-action APIs.
6. Deploy and smoke-test on Forge only after valid credential setup. Treat the kubeconfig pasted in conversation as disclosed: request replacement privately; do not reuse/copy its token into source.
7. Run the complete synthetic complaint-to-prevention scenario and export actual OpenAPI.

## Forge constraints

- Bank and MaaS endpoints are reachable only from authorised Forge namespace workloads. Render/Vercel cannot directly call internal cluster hostnames.
- Team namespace is `team10`; expected public route is `https://team10.xtradot.co` once deployed and verified.
- One public Service named `app`, port 80; image architecture `linux/amd64`.
- Plan backend + worker requests within namespace total 400m CPU / 768Mi memory. Do not copy resource settings for many pods without checking totals.
- 60 calls/minute shared across bank and MaaS: coordinate a single budget; no per-complaint polling loops or model calls on dashboard reads.
- XtraDot state is volatile. Retain evidence locally and label provider reset/stale records; never assume historical sandbox references remain queryable.
- Database egress/persistence must be verified. Do not assume Supabase is reachable from Forge; use an approved persistent database path if not.
- Only synthetic data in Forge, including social fixtures, logs and model inputs. Do not forward real X customer content into Forge without explicit organiser permission.

## End-of-day acceptance

- Synthetic support tickets from at least two channels enter through authenticated intake; replay does not duplicate complaints/jobs.
- Related complaints are linked to an incident; exact membership and evidence are retrievable.
- A sandbox timeout is retained as unknown and refreshed safely without resending.
- Signed webhook verification, event deduplication and out-of-order handling are demonstrated.
- Investigation cites real stored evidence IDs and distinguishes facts from hypotheses.
- An operator assigns a corrective action, records a change and records validation; financial execution remains disabled.
- Cross-bank requests are rejected; no secrets or raw PII appear in logs/API output.
- Each person supplies tests, payload examples, errors and limitations. Full backend tests and migrations run in a configured environment; blocked checks are explicitly recorded, not called passed.

## Tomorrow's frontend handoff

Deliver actual OpenAPI, sample responses and error cases for: explicit session bootstrap, complaint intake/list/detail, incident list/detail/exact complaints, evidence timeline, investigation request/status/result, corrective-action create/update/list and connector health/provenance. Existing reconciliation/proposal endpoints remain supporting capabilities.

GET/dashboard refresh must be read-only: no model calls, transfer submission or investigation triggered by page load. UI distinguishes sandbox events, simulated support tickets, social replay, stale data and missing evidence.
