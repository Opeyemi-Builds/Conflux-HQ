# Frontend implementation handoff

Reviewed baseline: `main` at `c0bccbd` (frontend PR #6).

Audience: frontend developer and backend integration team.

## Assessment

The frontend is now API-connected, not just a mock dashboard. Keep the existing visual design and extend it rather than rebuilding it.

Already present:
- Login and registration screens, authenticated API wrapper and Next.js API proxy.
- Dashboard summary, complaint feed, classification form and X pull action.
- Incident investigation, communication drafts and audit retrieval.
- Transaction analytics, fraud view, geographic risk map and bank audit page.
- Four-second polling for dashboard updates.

The main missing product capability is **payment exception reconciliation**. Several existing interactions also need correctness fixes before the demo can be trusted.

Validation: existing ESLint and direct TypeScript checks passed during this assessment. No production build, browser walkthrough or live backend end-to-end test was performed. Passing static checks does not establish that API actions work.

## Delivery order

1. P0: fix identity/session behavior and false-success states.
2. P0: fix complaint persistence and exact incident association.
3. P1: add reconciliation queue, matching, case updates and incident timeline.
4. P1: add non-executing financial proposals and reviewer restrictions.
5. P1: expose social analytics, connector provenance and alias configuration.
6. P2: finish pagination, map accuracy, accessibility and demo acceptance tests.

## P0 — Correct the existing integration

### 1. Make identity authoritative and demo access explicit

Evidence: `frontend/lib/api.ts:256–273`, `:326–398`; `frontend/app/dashboard/layout.tsx`.

Current issues:
- Missing/expiring tokens automatically log in as Zymic Bank.
- A 401 retries with the shared demo identity instead of returning the user to login.
- Registration returning any 404 is treated as successful demo provisioning: only the locally displayed bank/profile changes; no new tenant is created.
- Cached local profile data can override the server's `/auth/me` identity.

Implement:
- Remove silent demo login from ordinary authenticated requests. Offer an explicit “Enter demo” action instead.
- Bootstrap the session with `GET /api/v1/auth/me`; server bank ID, user ID and role are authoritative.
- On expiry/401, clear session state and return to login; use supported non-demo refresh flow if implemented.
- Never claim a tenant was created after a registration 404. Demo mode has a fixed bank; registration is unavailable there.
- Handle non-demo `email_confirmation_required` without immediately attempting login.
- Gate dashboard fetching until authentication is established; logout must stop polling and clear bank-scoped cached data.
- Use backend roles: `bank_admin`, `agent`, `it`, `manager`. Disable unavailable write controls, but keep server authorization authoritative.

Acceptance: direct dashboard access requires login; an expired session never changes banks; registration errors cannot produce a fake bank identity.

### 2. Persist complete complaint classification

Evidence: `frontend/app/dashboard/complaints/page.tsx:40–52`; `frontend/components/dashboard/Provider.tsx:537–551`.

The form classifies text, then creates a complaint with `issue_type` but drops most classification output. Backend creation treats that issue type as a prelabel and skips the normal classification queue. Severity, fraud flag, amount, summary and confidence can therefore remain absent.

Recommended flow:
1. `POST /api/v1/complaints` with text, channel and optional context, **without `issue_type`**.
2. Let the worker classify and refresh after processing; for explicit immediate classification use `POST /api/v1/complaints/{id}/classify`.
3. Present pending/unclassified state until classification exists. Do not map unknown severity to “low” or unknown sentiment to “neutral”.

Do not send unsupported severity/sentiment fields to the creation endpoint and assume they were saved. An alternative full-classification PATCH must match the backend schema exactly.

Acceptance: submit a fraud/failed-transfer complaint and verify persisted severity, fraud flag, amount and confidence after reload, not just the temporary form preview.

### 3. Resolve incident IDs exactly and stop inventing evidence

Evidence: `frontend/app/dashboard/incidents/[id]/page.tsx:25–30`; `frontend/components/dashboard/Provider.tsx:229–260`, `:378–410`.

Implement:
- Use `GET /api/v1/incidents/{id}` for the exact route UUID. Never fall back to the first incident when the ID is missing or unknown.
- Only call complaints “attached” when `complaint.incident_id === incident.id`. Same-issue complaints may be a separately labelled related feed, not incident evidence.
- Remove frontend-generated cause confidence. Show backend `likely_cause` and `cause_confidence`; label nearby system events as correlations, not confirmed causes.
- Do not label the first 25 bank-wide failed synthetic transactions as “matched transactions”. Use reconciliation match results and the incident timeline.
- A failed transaction status alone does not prove “debited, not credited”; preserve the actual status label.
- Use date-aware timestamps/buckets; `HH:mm` alone combines different dates in a 72-hour window.

Acceptance: an unknown incident shows not found and no mutation controls; two incidents with the same issue never share attached evidence accidentally.

### 4. Show mutation outcomes honestly

Evidence: `frontend/components/dashboard/Provider.tsx:514–532`; `frontend/app/dashboard/complaints/page.tsx:61–70`; `frontend/app/dashboard/security/page.tsx:106–112`.

Implement:
- Await each draft decision before marking it approved/rejected. Surface partial batch failures and preserve server statuses.
- Prefer individual customer-message and IT-ticket decisions. Disable actions when no pending item exists.
- Do not say “dispatched” merely because approval returned successfully; worker dispatch is a separate stage.
- X pull failures must show an error, not “sync completed”.
- Fraud escalation currently changes local component state only. Mark it unavailable/demo-only until a persistent backend workflow exists; do not claim it was sent.
- Distinguish loading, failed, stale, empty and healthy states. A backend outage is not “All systems normal”.
- Exclude resolved/dismissed incidents from “Active” counts.

### 5. Keep polling read-only

Evidence: `frontend/components/dashboard/Provider.tsx:395–410`, `:443–455`.

Dashboard loading currently initiates detection and investigation. Move mutations to explicit operator actions or the backend worker. Page refresh and manager viewing must not trigger investigation/model calls. Add in-flight request protection so slow polling cannot overlap indefinitely; show last successful refresh time and stale-data state.

## P1 — Add payment reconciliation

### 6. Build a reconciliation queue and case panel

Suggested route: `/dashboard/reconciliation`; add navigation, API methods and TypeScript response types.

| Action | Existing endpoint |
|---|---|
| Bank-wide summary | `GET /api/v1/reconciliation/summary` |
| Cases | `GET /api/v1/reconciliation/exceptions?status=reported&limit=50&offset=0` |
| Manual case | `POST /api/v1/reconciliation/exceptions` |
| Candidate matching | `POST /api/v1/reconciliation/complaints/{complaint_id}/match` |
| Case from complaint | `POST /api/v1/reconciliation/complaints/{complaint_id}/create` |
| Case updates | `PATCH /api/v1/reconciliation/exceptions/{exception_id}` |
| Incident cases/timeline | `GET /api/v1/incidents/{incident_id}/reconciliation` |

Queue fields: exception type, complaint/transaction ID, amount and currency, processor, payment channel, settlement status, case status, owner, priority, confidence, approval requirement, created/updated/resolved timestamps.

Case update body supports `status`, `settlement_status`, `owner`, `evidence_summary`, `priority`, `approval_required`. Omit unchanged properties; do not send null for nonnullable fields.

Case statuses: `reported`, `transaction_matched`, `settlement_checked`, `reconciliation_pending`, `approval_required`, `resolved`, `rejected`.

Settlement statuses: `initiated`, `processing`, `successful`, `failed`, `pending`, `reversed`, `partially_settled`, `unknown`, `disputed`, `reconciled`.

Requirements:
- Display ranked match candidates with confidence and reasons. A candidate is an investigative lead, not verified customer ownership or proof of refund eligibility.
- When `selected_transaction_id` is null, retain an unresolved state, including ambiguous equal-scoring matches. Never silently choose the first row.
- Handle duplicate-case 409 responses and refresh the queue.
- Preserve money as decimal strings in request/state handling; format for display without implying confirmed losses.
- Summary uses `reported_open_amount_by_currency`; do not combine currencies or label reported amounts as actual loss.
- Render the incident timeline's `at`, `kind`, `id` and optional status/association fields chronologically.

Acceptance: complaint → candidate match → case → owner/status update → reload → incident timeline is demonstrable with persisted backend data.

### 7. Add financial proposals separately from communication drafts

| Action | Existing endpoint |
|---|---|
| Create | `POST /api/v1/reconciliation/exceptions/{exception_id}/proposals` |
| List | `GET /api/v1/reconciliation/exceptions/{exception_id}/proposals` |
| Decide | `POST /api/v1/reconciliation/proposals/{proposal_id}/decision` |

Creation example:
```json
{"kind":"refund","amount":"25000.00","reason":"Settlement evidence requires an independent refund review."}
```
Decision body: `{"decision":"approved"}` or `{"decision":"rejected"}`.

Requirements:
- Kind is `refund` or `reversal`; positive amount has at most two decimal places and cannot exceed the documented case amount.
- Closed cases and an existing pending/approved proposal prevent a new active proposal.
- Decisions require `bank_admin`; the proposer cannot decide their own proposal. Display this restriction and handle server 403/409 responses.
- Show pending/approved/rejected, proposer, reviewer and decision time.
- Always state **“Review approval only — execution disabled; no funds moved.”** Approval does not resolve the case.
- Do not route financial proposals through `/ai/drafts/{id}/decision`; that endpoint blocks reversal-request approval.

Demo dependency: the fixed Zymic demo login provides one identity. A genuine independent approval requires a separately authorized bank administrator/test setup from the backend team. Do not fake a second reviewer in local storage or weaken the rule to finish the demo.

## P1 — Finish social monitoring and reputation visibility

Keep the existing X pull button, but add source/provenance reporting and social configuration.

| Capability | Existing endpoint |
|---|---|
| Read aliases | `GET /api/v1/social/aliases` |
| Replace full alias set (admin) | `PUT /api/v1/social/aliases` |
| Connector status | `GET /api/v1/social/x/status` |
| Live/fallback pull | `POST /api/v1/social/x/pull` |
| Explicit recorded replay | `POST /api/v1/social/x/replay` |
| Reputation and velocity | `GET /api/v1/analytics/social?hours=24` |

Requirements:
- Preserve the pull result source and visibly distinguish live X, recorded replay and failure. A connected backend is not proof of a live X connection.
- Show actual ingestion counts rather than claiming every fetched post became a complaint.
- Admin alias editor supports `name`, `handle`, `hashtag`, `contextual`; PUT replaces the complete set, so confirm changes before submitting.
- Add social totals, engagement, high-reach posts, reputation-risk counts, top flags and hourly velocity from backend responses. Reputation flags are triage signals, not proof that allegations are true.
- Do not invent per-post reach or reputation fields if the complaint response does not contain them; request a social receipt listing/detail contract from the backend team first.
- Never expose X tokens, Supabase service-role keys or `SOCIAL_ADAPTER_TOKEN` in browser code. Trusted scanner ingestion/rule discovery is service-to-service, not a browser integration.

## P2 — Data quality, usability and acceptance

- Add server complaint pagination and supported channel/issue/region/fraud/date filters; current local filtering only covers the latest 500 fetched records.
- Align analytics and complaint date windows or explicitly label when a view uses a partial sample. Use full ISO timestamps for buckets and a consistent timezone label.
- Add complaint detail with classification, incident link and reconciliation action.
- Unknown map regions must stay unknown, not become Lagos. Label geocoded/approximate region locations and remove workflow labels such as “quarantined” when inferred only from severity.
- Keep synthetic transaction/event endpoints demo-only; gracefully show unavailable data outside demo mode.
- Provide keyboard-accessible dialogs, labelled form errors, pending-action disabling, retry controls and responsive tables.
- Explain that updates use polling; do not claim push-stream freshness.

## Backend dependencies — do not solve by fabricating frontend state

- No individual reconciliation GET-by-ID route exists yet. A list-backed case panel works now; robust direct case URLs need backend detail retrieval.
- Complaint listing currently has no `incident_id` filter. Exact filtering of loaded data is possible but may be incomplete; complete incident complaint drilldown needs backend pagination/filter support.
- Durable fraud escalation, detailed per-post social metrics and richer ranked-cause evidence require agreed backend contracts.
- Demo seed reset does not currently clean payment proposals/exceptions before deleting complaints/transactions. Backend must address dependent-record cleanup before promising reliable reset after reconciliation activity.
- Existing reconciliation test coverage is limited; earlier full execution was blocked by missing Anthropic dependency and placeholder database configuration. Do not equate documented endpoints with verified production readiness.

## Final demo acceptance checklist

- [ ] Explicit demo login; no silent identity substitution or fake tenant registration.
- [ ] Complaint classification survives reload and shows null/pending fields honestly.
- [ ] Incident UUID, complaints, evidence and actions refer to the same incident.
- [ ] Failed API actions never display success; approvals reflect backend responses.
- [ ] Reconciliation queue, matching, status updates and evidence timeline work.
- [ ] Financial proposal restrictions are enforced and execution is visibly disabled.
- [ ] X live versus recorded provenance is visible; reputation aggregates are real.
- [ ] No browser secrets, invented cause confidence or false loss claims.
- [ ] Lint, TypeScript, production build and browser/backend walkthrough pass, with any blocked steps recorded.
