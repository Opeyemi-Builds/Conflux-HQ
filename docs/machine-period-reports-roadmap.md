# Flow B — Period analysis reports (parked roadmap)

Status: **NOT BUILT.** Parked after Flow A merged. Revisit when the ticker is live with banks.

## What Flow A already does (done, on `main`)

`GET /machine/updates` — bank polls every 5s with their `cfx_api_` key and gets
operational rows: `{issue_type, severity, time, location, text}` for complaints
and `{issue_type, status, complaint_count, time}` for incidents. Thin, real-time,
cheap. No sentiment, no severity triage, no trend commentary.

## What Flow B is

A bank asks: *"analyse failed_transfers from Jan 1 → Mar 31"* (2 days / 30 days /
1 month, optional `issue_type` filter) and gets back a document-like bundle they
can read directly:

- totals + trend over the window
- top incidents in the window (with links back to per-item IDs from Flow A)
- likely causes (from stored investigation runs, not fresh inference where possible)
- recommended actions
- evidence appendix (complaint excerpts, transaction references)

## Why a separate route

| Flow A (ticker) | Flow B (report) |
|---|---|
| per-item, real-time | per-period, on-demand |
| cheap (plain SQL) | expensive (GLM summarization over hundreds of items) |
| polled every 5s | generated once, cacheable |

Mixing them would put summarization cost on the hot poll loop.

## Proposed shape (to confirm when we build it)

- `POST /machine/reports {from, to, issue_type?}` → `{report_id, status: queued}`
  Async job — sync generation will time out on big windows.
- `GET /machine/reports/{id}` → status + finished document when done.
- Inputs already exist in the DB: complaints, incidents, investigation runs,
  transactions. Flow B is composition + summarization, no new ingestion.

## Constraints to respect when building

- **MaaS budget:** report traffic must not eat the 60/min budget that Flow A
  classification needs. Separate quota or off-peak generation.
- **Scope:** machine key auth like the rest of `/machine`; decide `read` vs
  `operate` when speccing.
- **Retention/caching:** completed reports should be cached by
  `(bank_id, from, to, issue_type)` — same request twice must not re-run GLM.
- **Comments/threads:** skip per-post thread fetching by default ($0.005/read
  against the daily cap). Reserve thread summarization for the investigation
  step on high-severity incidents only.
- **Region is nullable:** X posts usually carry no region; reports must handle
  `"unknown"` without skewing location breakdowns.
- **Multi-bank rule stays:** a report is bank-scoped to the presenting key,
  same as the ticker. No cross-bank aggregation.

## Open decisions

1. Exact report document schema (sections, field names).
2. `read` vs `operate` scope for requesting reports.
3. Retention window + cache invalidation for completed reports.
4. Whether banks can schedule recurring reports (e.g. monthly auto-run) or
   only request ad hoc.
