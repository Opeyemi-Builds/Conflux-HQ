# Backend demo setup

FastAPI API backed by **Supabase Postgres** through SQLAlchemy. The hackathon login is deliberately separate from Supabase Auth for instant demo access (`DEMO_MODE=true`), while full Supabase Auth + JWKS verification remains available (`DEMO_MODE=false`). AI classification, bounded tool-use investigation, and grounded draft generation run via **Anthropic Claude** or **Google Gemini** when API keys are configured, with deterministic multilingual fallback when offline. No live core-banking connections or real money movements are performed.

## 1. Environment

From the repository root, copy `.env.example` to `.env`. Never commit `.env`.

Set:
- `DATABASE_URL`: Supabase **Connect → Session pooler**, port 5432. Replace project reference, database password and pooler host. URL-encode special characters in the password and keep `sslmode=require`.
- `DEMO_MODE=true`
- `DEMO_TOKEN_SECRET`: a newly generated random value, at least 32 characters. Generate locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

Supabase project API keys are placeholders for future Auth integration. They are **not needed for demo login** and cannot replace the database connection password. Keep service-role keys server-side. With placeholders unchanged, the database cannot connect; there is no silent SQLite fallback.

## 2. Install and migrate

Run from `backend/`:

```sh
python -m venv .venv
# Git Bash / Windows:
source .venv/Scripts/activate
# macOS / Linux instead: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://localhost:8000/docs. The existing migrations create tables and enable PostgreSQL RLS. Direct anon/authenticated Supabase REST access is blocked by the absence of RLS policies; the backend uses a trusted database connection, with tenant scope enforced in application queries. Do not expose that database credential to the browser.

For **explicit offline development only**, set `DATABASE_URL=sqlite:///./conflux.db` and run the same migrations. Demo login still works without Supabase keys. Tests always use isolated in-memory SQLite.

## 3. Login

`POST /api/v1/auth/login`

```json
{"username":"Zymic Bank","password":"123"}
```

Returns `access_token`, `token_type`, `expires_in`, demo/synthetic flags and the user/bank profile. The first valid login provisions the fixed demo bank and operator. Send this header on protected requests:

```text
Authorization: Bearer <access_token>
```

Tokens expire after 120 minutes by default. Log in again to renew; demo mode has no refresh, registration or staff-management endpoints. `GET /api/v1/auth/me` returns the profile. Logout is client-side token removal; issued tokens remain valid until expiry. These public demo credentials and shared identity are not production authentication. Keep the demo local or access-restricted; there is no brute-force rate limiter. Production/prod environment settings reject demo mode.

## 4. Seed and replay the scenario

`POST /api/v1/synthetic/seed`

```json
{"seed":42,"at":"2026-11-06T10:14:59Z"}
```

The request creates:
- 1,000 pre-labelled synthetic complaints: stable baseline, 30 failed-transfer spike reports, eight scam reports and two isolated fee reports.
- 5,000 synthetic transactions, including failures on app/USSD through `demo-switch-a`.
- Two synthetic system events: release v4.2.1 and an unrelated maintenance decoy.

The response supplies `detection_at` and `release_at`. Dates are aligned to the request's 15-minute bucket; this example returns detection time 10:14:59 UTC and release time 09:48 UTC. Omit `at` to anchor around the present. Fixtures are pre-labelled, **not classified by AI**. Seed runs only for the demo bank and returns 409 if complaint/transaction/event data already exists. It never deletes or overwrites records; there is no reset endpoint. A fixed seed reproduces business values, not random UUID identifiers.

Pass returned `detection_at` as `now`:

`POST /api/v1/incidents/detect`

```json
{"now":"2026-11-06T10:14:59Z"}
```

One failed-transfer incident should be created with 30 complaints. Repeat calls do not double-count that bucket. `GET /api/v1/incidents` lists incidents and `GET /api/v1/incidents/{id}` retrieves one. Call `POST /api/v1/ai/incidents/{id}/investigate` (or drain queued jobs via `POST /api/v1/jobs/drain`) to run transaction matching, dynamic cause scoring, bounded agent investigation, and grounded draft generation (`customer_message`, `it_ticket`, `reversal_request`).

## 5. Frontend API reference

All paths below have `/api/v1` prefix and require bearer authentication except health/login.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Database connectivity |
| POST | `/auth/login` | Demo login |
| GET | `/auth/me` | Current user and bank |
| GET | `/analytics/summary` | Complaint totals, issue/channel/region/severity counts, fraud count, reported exposure, open incidents, `avg_time_to_detect_seconds`, and `repeat_complaint_rate` |
| GET | `/analytics/trends` | Zero-filled hourly UTC complaint counts |
| GET | `/analytics/breakdown` | Issue/channel/region counts |
| GET | `/analytics/transactions` | Transaction totals, status counts, failed fraction and amounts |
| POST | `/synthetic/seed` | Seed the 48-hour multilingual Nigerian banking dataset (`reset=true` optional) |
| GET | `/synthetic/transactions` | Paginated synthetic transaction records; optional `status` |
| GET | `/synthetic/system-events` | Synthetic release/maintenance evidence |
| GET | `/complaints` | Filtered complaint feed |
| GET | `/complaints/{id}` | Complaint detail |
| POST | `/complaints` | Ingest a complaint with PII pattern masking and transactional job enqueue |
| POST | `/complaints/bulk` | Ingest up to 5,000 complaints |
| PATCH | `/complaints/{id}/classification` | Store caller-supplied labels |
| POST | `/complaints/{id}/classify` | Classify a stored complaint via Claude/Gemini (with rules fallback) |
| POST | `/incidents/detect` | Explicitly run statistical spike detection |
| GET | `/incidents` | Ranked incidents; optional `status` |
| GET | `/incidents/{id}` | Incident detail |
| POST | `/ai/classify` | Classify pasted complaint text |
| POST | `/ai/incidents/{id}/investigate` | Run bounded investigation agent, cause scoring, and grounded draft generation |
| GET | `/ai/incidents/{id}/drafts` | List generated drafts for an incident |
| POST | `/ai/drafts/{id}/decision` | Approve or reject a draft (enqueues transactional outbox job; blocks direct reversal execution) |
| GET | `/ai/incidents/{id}/audit` | Full audit trail for an incident |
| GET | `/ai/evaluate` | Evaluate classifier accuracy & confusion matrix on the 100-item multilingual golden set |
| GET | `/jobs` | Inspect queued, completed, or `dead_letter` worker jobs |
| POST | `/jobs/drain` | Drain pending classification, detection, investigation, and approval outbox jobs |

Analytics accept `hours` (1–720, default 24) and optional timezone-aware `at`, with an inclusive start and exclusive end. For the complete seeded dataset use **`hours=49&at=<detection_at>`**; the historical baseline plus spike spans slightly over 48 hours. URL-encode timestamps in query strings. Edge hourly buckets can be partial, so trends may contain `hours + 1` entries. Money values are decimal strings; `money_at_risk` is unverified complaint-reported exposure that may duplicate reports, not actual loss. `failed_rate` is a 0–1 fraction, not a percentage. Open-incident counts use current statuses, not reconstructed historical states.

Complaint filters: `channel`, `issue_type`, `region`, `is_fraud`, `unclassified`, timezone-aware `since`/`until`, `limit` and `offset`. Use `is_fraud=true` for the security queue. `since` is inclusive and `until` exclusive. Pagination order is newest first with an ID tie-breaker.

No background scheduler exists: call detection explicitly. Review the OpenAPI schemas at `/docs` for complete payloads.

## 6. Tests

```sh
python -m pytest -q
```

Tests cover demo credentials/token checks, synthetic seeding, analytics windows and bank isolation, complaint transaction links, repeat detection, plus the retained future Supabase Auth workflow with a fake provider. They do not prove live Supabase connectivity, PostgreSQL RLS enforcement or production readiness.

`DEMO_MODE=false` restores the existing Supabase Auth registration/login/refresh and staff endpoints. Restart after changing mode because route selection happens at import time. That future mode needs actual Supabase Auth configuration and uses email/password rather than the demo username.
