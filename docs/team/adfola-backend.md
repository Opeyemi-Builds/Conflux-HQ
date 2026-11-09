# Adfola — XtraDot payment evidence and signed webhooks

Read [shared sprint plan](../backend-team-workplan.md) and the [agent prompting guide](agent-prompting-guide.md) first. Use the copyable Adfola prompt there when delegating work. Backend today; no frontend edits. Branch suggestion: `feat/xtradot-evidence`.

## Goal

Build a Forge-only adapter that observes the XtraDot sandbox payment lifecycle and converts it into safe, tenant-scoped evidence for Conflux investigations. It must never retry a timed-out transfer or move money as a result of model output.

## Read first

- Forge Sandbox Participant Guide sections 4–5.7 (keep outside Git if it contains credentials)
- `backend/app/models/transaction.py`
- `backend/app/models/enums.py`
- `backend/app/services/transaction_matching.py`
- `backend/app/api/routes/reconciliation.py`
- `backend/app/api/routes/health.py`
- `backend/app/core/config.py`
- Existing migration head before adding a revision

## Owned work

Suggested modules: `backend/app/adapters/xtradot_client.py`, `backend/app/adapters/xtradot_schemas.py`, `backend/app/api/routes/forge_webhooks.py`, `backend/app/services/payment_evidence.py`, model/migration only if needed; focused tests and safe synthetic fixtures.

1. Use the internal base URL only from a Forge workload. Read `GATEWAY_KEY` from runtime secret. Use `x-api-key`; never send it browser-side or log it. Do not make Render/Vercel call the internal hostname.
2. Implement safe read operations first: status lookup, requery, transactions and settlements. If implementing transfer creation for the demo, require explicit operator action, name-enquiry reference, idempotency key and a visible synthetic-only boundary; no page-load or automatic transfer calls.
3. On TIMEOUT/504, persist `outcome_unknown` and surface “requery required”; never resend. Requery until a bounded final state or escalation. Do not assume a 202 pending response is failure.
4. Register an internal webhook URL and verify `x-forge-timestamp` and `x-forge-signature = HMAC-SHA256(timestamp + '.' + raw_body)`. Reject timestamps older than 5 minutes. Deduplicate by provider event ID. Acknowledge valid events within 10 seconds and process asynchronously.
5. Handle duplicate, delayed and out-of-order events. A late `successful` after a `pending` is valid; a `reversed` after `successful` changes the timeline. Do not overwrite source evidence: append immutable events and derive current status.
6. Normalize into the shared evidence contract: provider, sandbox environment, provider event ID, payment/reference, event type, source status, amount/currency, occurrence/receipt timestamps, safe request ID, evidence basis and freshness. Preserve decimal amounts as strings.
7. Scope every lookup and stored evidence by bank/provider/environment. Do not treat an internal XtraDot record as independent beneficiary-credit proof; label it provider/sandbox evidence.
8. Respect 60 calls/minute shared with MaaS. No per-page polling loop. Use backoff and bounded requery. Cache safe reference data.
9. Include connector health/provenance and clear `sandbox`, `stale`, `unknown`, `missing` labels. XtraDot state is volatile and may reset.

## Demo fixtures

Use deterministic amount triggers from the guide only after the adapter is tested: `.02` timeout then failed/reversed; `.03` pending then successful; `.04` successful then later reversed; `.05` first webhook withheld. Treat these as sandbox fixtures, not universal production behavior. Do not claim XtraDot is NIBSS.

## Handoffs

- To Opeyemi: normalized evidence model, event ordering rules, status mapping and health/error contract.
- To Andrew: immutable evidence IDs and freshness/source labels.
- To dev_id: payment-reference lookup/correlation input.
- To frontend tomorrow: event timeline, unknown-outcome warning, source/provenance and error states.

## Required tests

Signature valid/invalid; stale timestamp; malformed body; duplicate delivery; same event replay; out-of-order events; timeout never resends; pending is not failure; successful then reversed; unknown reference; 401/429/503/504; decimal amounts; cross-bank/provider isolation; key absent; no secret in logs.

## Done today

A Forge smoke path can observe a synthetic transfer lifecycle, receive a verified webhook, retain immutable evidence, safely requery a timeout, derive the current state and expose an investigation-ready timeline. If Forge access is unavailable, complete contract tests with recorded synthetic payloads and document the blocked smoke step.

Do not edit shared router/config/model exports without coordinating with Opeyemi. Do not commit `team10.yml`, `GATEWAY_KEY`, webhook secrets or API responses containing credentials.
