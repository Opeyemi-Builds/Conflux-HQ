# XtraDot Report Webhook Contract (Draft — docs-first)

Status: **implemented**. `report.ready` / `report.updated` normalize to `ReportEvidenceEvent` via `normalize_receipt_report_event()` in `app/services/xtradot_webhook_worker.py`; schema in `app/adapters/xtradot_schemas.py`; tests in `tests/test_xtradot_connector.py`.
Existing path this reuses: `POST /api/v1/forge/webhooks` → receipt in `xtradot_webhook_receipts` → async worker → evidence. See `app/api/routes/forge_webhooks.py`, `app/adapters/xtradot_webhooks.py`, `app/services/xtradot_webhook_worker.py`.

## 1. Purpose

Deliver XtraDot **reports** (batch / aggregate provider output, e.g. settlement or reconciliation reports) via the same signed webhook intake as `transfer.*` / `payment.*` events.

Design principle (carried over from payments): **receipt first, normalize later, never guess**. Anything outside this contract stays `ignored` with raw bytes retained.

## 2. Transport (reuse, no change)

- Endpoint: `POST /forge/webhooks` (mounted at `/api/v1/forge/webhooks`).
- Headers:
  - `x-forge-event`: event name, e.g. `report.ready`. Max 160 chars. Must be listed in `XTRADOT_SUPPORTED_EVENTS`.
  - `x-forge-timestamp`: provider timestamp. Format selected by `XTRADOT_WEBHOOK_TIMESTAMP_FORMAT` (`unix-seconds` | `iso8601`). Max 160 chars.
  - `x-forge-signature`: `HMAC-SHA256(timestamp + "." + raw_body)`, hex, optional `sha256=` prefix. Max 128 chars.
- Body: raw JSON object, max 1 MB (streamed, `413` over limit).
- Responses:
  - `202 { receipt_id, status, duplicate }` where `status` is `received` | `ignored` | `duplicate`.
  - `401` bad/missing signature or stale timestamp (>5 min skew). Nothing persisted.
  - `503` when `XTRADOT_WEBHOOK_SECRET` is unset. Nothing persisted.
- Dedupe: unique on `(provider="xtradot", environment="sandbox", event_id)`. Byte-identical redelivery returns `duplicate: true`. Conflicting reuse of an `event_id` is rejected at the DB constraint (existing behavior).

## 3. Security (reuse, no change)

- `verify_webhook_signature()` with `hmac.compare_digest`; timestamp freshness enforced by caller against configured format.
- Secrets via env only (`XTRADOT_WEBHOOK_SECRET`, `GATEWAY_KEY` never logged).
- Raw body stored verbatim (`LargeBinary`); worker never mutates it.
- Worker processing is bank-scoped (`receipt.bank_id` must match caller).

## 4. Proposed `report.*` body contract

Mirrors Mock Spec v2 transfer shape: top-level `{event, event_id, created_at, attempt, data}`.

```json
{
  "event": "report.ready",
  "event_id": "rpt-evt-01JC8Z4K2M",
  "created_at": "2026-11-09T11:42:05Z",
  "attempt": 1,
  "data": {
    "report_id": "RPT-20261109-0001",
    "report_type": "settlement",
    "status": "ready",
    "period_from": "2026-11-08T00:00:00Z",
    "period_to": "2026-11-09T00:00:00Z",
    "payment_references": ["TRF-20261109-0001"],
    "download_url": null,
    "checksum": null
  }
}
```

### Proposed event names

| Event | Meaning |
| --- | --- |
| `report.ready` | Report generated and available; terminal for that `report_id` unless superseded. |
| `report.updated` | Same `report_id` re-issued with corrections; non-terminal, supersedes prior snapshot. |

Both must be added to `XTRADOT_SUPPORTED_EVENTS` and to the worker's documented prefix list (currently `("transfer.", "payment.")` → add `"report."`).

### Field rules (proposed)

Top level — same as v2 transfers:

- `event` (str, required): must equal `x-forge-event` header exactly, else receipt stays `ignored` (header/body mismatch = untrustworthy).
- `event_id` (str, 1–160 chars, required): dedupe key. Missing → `ignored` at intake.
- `created_at` (str, required): ISO-8601 with timezone. Timezone-naive → treated as missing (`occurred_at = None`, not rejection).
- `attempt` (int, optional): delivery attempt; informational only, never affects dedupe.

`data` (object, required):

- `report_id` (str, 1–160, required): provider report identifier. Analogue of `reference`.
- `report_type` (str, 1–64, required): e.g. `settlement`, `reconciliation`. Free-form provider vocabulary, preserved verbatim, never interpreted.
- `status` (str, 1–64, required): e.g. `ready`, `updated`, `failed`. Observation only.
- `period_from` / `period_to` (ISO-8601 TZ-aware strings, optional): report window. Naive/unparseable → `None`, never guessed.
- `payment_references` (array of str ≤160, optional): links to transfer references. Entries violating length/type are dropped individually; if none valid remain → `None`.
- `download_url` (str ≤2048, optional): only `https://` on allow-listed hosts (TBD). Anything else → `None`, never fetched automatically.
- `checksum` (str ≤256, optional): opaque, stored verbatim.
- `amount` / `currency` (optional, if provider sends totals): same decimal-string rules as payments — `Decimal` via `parse_float`, finite, non-negative, preserved as provider string; `currency` exactly 3 letters or rejected to `ignored`.

Anything else in `data` is ignored (preserved in raw bytes, not normalized).

## 5. Receipt lifecycle (reuse, no change)

- Intake sets `received` when `bank_id` + parsed timestamp + `event_id` present and event in supported set; else `ignored`.
- Worker re-checks: `signature_valid is True`, `event_id` + `event_type` present, event in `XTRADOT_SUPPORTED_EVENTS`. Fail → `ignored` + `processed_at`.
- Normalization failure (corrupt JSON, bad currency/amount, header/body mismatch, non-`report.` prefix) → `ignored` + `processing_error` (≤256 chars).
- Success → `processed` + `processed_at`. Raw bytes untouched either way.

## 6. Evidence mapping (proposed, not implemented)

Current `PaymentEvidenceEvent` is payment-shaped (`payment_reference`, `source_status`) and does not fit reports. Proposal: new `ReportEvidenceEvent` in `app/adapters/xtradot_schemas.py`:

- `bank_id`, `provider="xtradot"`, `environment="sandbox"`
- `provider_event_id` (= `event_id`), `event_type` (1–64, must start `report.`)
- `report_id`, `report_type`, `source_status` (= `data.status`)
- `period_from`, `period_to`, `payment_references`, `download_url`, `checksum`
- `amount`, `currency` (same decimal-string validator)
- `occurred_at` (from `data.created_at` fallback `created_at`), `received_at`
- `evidence_basis = "sandbox_signed_webhook"`, `freshness = "unknown"`

Reports are **observations only** — never ledger proof, never a transfer trigger — same as payment evidence. Dedupe via existing `append_unique_events()` pattern extended to report scope `(bank_id, provider, environment, provider_event_id)`; conflicting content under one `event_id` raises `ProviderEventConflictError` → `ignored`.

Open design choice: `report.updated` for the same `report_id` arrives under a **new** `event_id` (new evidence row, supersedes by `report_id` at read time) — never an in-place update. Confirmed below.

## 7. Config (additive)

- `XTRADOT_SUPPORTED_EVENTS`: add `report.ready,report.updated`.
- `XTRADOT_BANK_ID`, `XTRADOT_WEBHOOK_SECRET`, `XTRADOT_WEBHOOK_TIMESTAMP_FORMAT`: unchanged.
- Worker `DOCUMENTED_EVENT_PREFIXES`: add `"report."`.

No migration needed: existing `xtradot_webhook_receipts` table already stores arbitrary `event_type` (≤160) + raw body.

## 8. Examples

Ready (minimal):

```json
{
  "event": "report.ready",
  "event_id": "rpt-evt-0001",
  "created_at": "2026-11-09T12:00:00Z",
  "attempt": 1,
  "data": {
    "report_id": "RPT-0001",
    "report_type": "settlement",
    "status": "ready"
  }
}
```

Updated (superseding snapshot, new `event_id`, same `report_id`):

```json
{
  "event": "report.updated",
  "event_id": "rpt-evt-0002",
  "created_at": "2026-11-09T13:00:00Z",
  "attempt": 1,
  "data": {
    "report_id": "RPT-0001",
    "report_type": "settlement",
    "status": "updated",
    "period_from": "2026-11-08T00:00:00Z",
    "period_to": "2026-11-09T00:00:00Z",
    "payment_references": ["TRF-1", "TRF-2"]
  }
}
```

## 9. Open questions for the provider

1. Exact `report.*` event names — is it `report.ready` / `report.updated`, or different (`report.completed`, `report.failed`)?
2. What `report_type` values exist (`settlement`, `reconciliation`, others)?
3. How does a report link to payments — `payment_references`, `session_id`s, or no link?
4. Are reports snapshots (new `event_id` per update, assumed above) or mutated in place?
5. Is there a `download_url` — if so, allowed hosts, auth scheme, and checksum algorithm?
6. Do reports carry totals (`amount`, `currency`) and under what field names?
7. Redelivery semantics — same `attempt` increment behavior as transfers?

## 10. Test plan (when implemented)

Mirror `tests/test_xtradot_connector.py`:

- Signed `report.ready` persists verbatim, dedupes on redelivery, worker yields one `ReportEvidenceEvent`, raw bytes intact.
- `report.updated` with new `event_id` / same `report_id` yields a second row (no overwrite).
- Header/body `event` mismatch → `ignored`.
- Undocumented shape / bad currency / bad amount → `ignored` + `processing_error`, never guessed.
- Missing secret → `503` nothing persisted; bad signature / stale timestamp → `401` nothing persisted.
- Bank scoping: wrong `bank_id` raises `LookupError`.
