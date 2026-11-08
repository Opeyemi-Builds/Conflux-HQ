# Conflux HQ Backend Implementation

## Purpose

Conflux HQ is a bank complaint-intelligence backend built for the Access Youth Tech Forge demo. It receives customer complaints from multiple channels, identifies the registered bank involved, protects sensitive information, classifies complaints, detects systemic incidents, investigates likely causes, and prepares human-reviewable response drafts.

The backend is a FastAPI application backed by SQLAlchemy and designed for Supabase Postgres. Demo mode uses a controlled local login and synthetic data so the product can be demonstrated without production banking credentials or live core-banking access.

## Backend structure

The backend lives in `backend/` and is organized as a modular FastAPI application.

- `app/api/` contains routers and request handling.
- `app/models/` contains SQLAlchemy database models.
- `app/schemas/` contains Pydantic request and response schemas.
- `app/services/` contains complaint, social, audit, spike-detection and worker logic.
- `app/ai/` contains classification, investigation, evidence, guardrail and draft logic.
- `app/adapters/` contains external-platform adapters, including the X API v2 adapter.
- `alembic/versions/` contains database migrations.
- `tests/` contains API, privacy, authentication, analytics, worker, AI and social integration tests.

## Configuration and environments

Configuration is loaded through Pydantic settings and environment variables.

Important settings include:

- `DATABASE_URL` for Supabase Postgres or explicit local SQLite development.
- `DEMO_MODE` to enable the hackathon login.
- `DEMO_USERNAME`, defaulting to `Zymic Bank`.
- `DEMO_PASSWORD`, defaulting to `123`.
- `DEMO_TOKEN_SECRET` for demo JWT signing.
- `SOCIAL_ADAPTER_TOKEN` for trusted scanner ingestion.
- `X_BEARER_TOKEN` for official X API v2 access.
- `X_API_BASE_URL` for the X API endpoint.
- `X_DAILY_POST_LIMIT` for the demo spending guardrail.
- `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` for Claude classification and investigation.
- `GEMINI_API_KEY` and `GEMINI_MODEL` for the optional Gemini provider.

Secrets are server-side only. Supabase service-role keys, X bearer tokens and social adapter tokens must never be exposed to frontend code.

Demo mode is rejected when the environment is set to production.

## Authentication

### Demo authentication

The demo login endpoint is:

```text
POST /api/v1/auth/login
```

Example request:

```json
{
  "username": "Zymic Bank",
  "password": "123"
}
```

A successful login returns a signed, expiring demo JWT with the demo bank and operator profile. The token uses a dedicated issuer and audience and is restricted to the fixed demo operator identity.

The demo flow is intentionally separate from Supabase Auth. It exists only for the hackathon demonstration and does not provide production authentication controls such as single sign-on, multi-factor authentication or brute-force protection.

### Supabase authentication

When `DEMO_MODE=false`, the existing Supabase Auth flow is used. Supabase JWT verification supports the configured JWT secret or JWKS verification path.

## Database and tenant isolation

The application uses SQLAlchemy models and Alembic migrations. Supabase Postgres is the intended hosted database.

Core entities include:

- Banks.
- Users and bank memberships.
- Complaints.
- Transactions.
- System events.
- Incidents.
- Drafts.
- Audit logs.
- Bank aliases.
- Social receipts.
- Worker jobs.

Bank-scoped queries use `bank_id`. The backend also enables PostgreSQL row-level security on protected tables through migrations. Application-level tenant checks ensure that users cannot read another bank's complaints, incidents or drafts.

## Privacy protection

Complaint and social content is masked before persistence. The privacy layer detects and replaces common patterns for:

- Email addresses.
- Phone numbers.
- Card numbers.
- Account numbers.

Customer references are pseudonymized. Social author identifiers are hashed or converted into scoped references. Raw author identities are not used as customer-facing data.

## Complaint ingestion

The complaint API supports direct and bulk ingestion.

```text
POST /api/v1/complaints
POST /api/v1/complaints/bulk
GET  /api/v1/complaints
GET  /api/v1/complaints/{complaint_id}
PATCH /api/v1/complaints/{complaint_id}/classification
POST /api/v1/complaints/{complaint_id}/classify
```

Complaint listings support filters for:

- Channel.
- Issue type.
- Region.
- Fraud status.
- Classified or unclassified state.
- Inclusive `since` time.
- Exclusive `until` time.
- Pagination.

New unclassified complaints are placed into the transactional worker queue for classification.

## Synthetic demo scenario

The synthetic seed route creates a reproducible banking incident scenario.

```text
POST /api/v1/synthetic/seed
GET  /api/v1/synthetic/transactions
GET  /api/v1/synthetic/system-events
```

The scenario includes:

- One thousand synthetic complaints.
- Five thousand synthetic transactions.
- A failed-transfer complaint spike.
- Fraud and scam complaints.
- A release event affecting the transfer service.
- An unrelated maintenance event as a decoy.
- App and USSD transaction failures.

Synthetic records are explicitly marked or described as synthetic. The seed route does not call external AI services and does not move money.

## Analytics

The analytics API provides bank-scoped reporting over UTC windows.

```text
GET /api/v1/analytics/summary
GET /api/v1/analytics/trends
GET /api/v1/analytics/breakdown
GET /api/v1/analytics/transactions
GET /api/v1/analytics/social
```

The standard analytics routes report complaint totals, issue types, channels, regions, severity, fraud counts, reported exposure, incidents, time to detection, repeat complaints and transaction status metrics.

The social analytics route reports:

- Total received social posts.
- Privacy-safe unique author count.
- Aggregate engagement.
- High-reach post count.
- Reputation-risk post count.
- Average reputation score.
- Common reputation flags.
- Hourly social-post velocity.

The analytics window uses an inclusive start and exclusive end. Reported money is unverified customer-reported exposure, not confirmed financial loss.

## Social identity and alias management

Registered banks can configure names, handles, hashtags and contextual aliases.

```text
GET /api/v1/social/aliases
PUT /api/v1/social/aliases
```

Supported alias kinds are:

- `name`.
- `handle`.
- `hashtag`.
- `contextual`.

The backend matches bank names and aliases using boundary-aware matching. It rejects generic contextual phrases that would create obvious false positives, such as treating `access to my account` as a reference to Access Bank.

## Trusted social scanner contract

An external scanner can discover active monitoring rules through:

```text
GET /api/v1/social/monitoring-rules
```

It can deliver normalized social events through:

```text
POST /api/v1/social/events
```

These routes require the server-side `SOCIAL_ADAPTER_TOKEN`. The scanner must use official platform APIs and permitted access. The backend does not scrape social platforms.

The backend determines the target bank itself. Scanner payloads do not accept arbitrary bank IDs. The backend handles:

- Active-bank matching.
- Alias matching.
- No-match responses.
- Ambiguous-match responses.
- Multi-bank fan-out for explicit handles or stream rule tags.
- Duplicate detection.
- PII masking.
- Complaint creation.
- Social receipt creation.
- Audit logging.
- Worker job enqueueing.

## X API v2 integration

The X adapter is implemented in `app/adapters/x_adapter.py`.

Endpoints include:

```text
GET  /api/v1/social/x/status
POST /api/v1/social/x/sync-rules
GET  /api/v1/social/x/pull
POST /api/v1/social/x/pull
POST /api/v1/social/x/ingest-raw
POST /api/v1/social/x/replay
```

### Recent Search

The adapter calls the official X API v2 Recent Search endpoint with a server-side bearer token. It requests post text, creation time, author ID, language and public engagement metrics.

Queries are compiled from registered bank identities. They include handles, replies to handles and configured hashtags. A typical query looks like:

```text
(@zymicbank OR to:zymicbank OR #zymicbank) -is:retweet
```

### Filtered Stream

The adapter compiles one tagged stream rule per active bank. Each rule contains a tenant tag such as:

```text
tenant:<bank_id>
```

The adapter compares desired rules with remote rules, adds missing rules and deletes stale rules. This supports bank alias updates without duplicating stream rules.

### Native X payload ingestion

`POST /social/x/ingest-raw` accepts native X API v2 payload shapes. It extracts:

- Post ID.
- Full post text.
- Creation timestamp.
- Author reference.
- Public metrics.
- Matching rule tags.
- Source permalink.

The payload is converted to the normalized `SocialEvent` model and sent through the same bank matching and complaint pipeline.

### Replay mode

When a live X token is not configured, the demo can replay recorded X-shaped payloads through the real ingestion path.

This provides a reliable presentation mode without pretending that the application is connected to X.

## Social content analysis and reputation protection

Every received social post retains the full masked post content in the complaint record. The social receipt stores platform metadata and analytics signals.

The transparent reputation analysis currently detects triage signals such as:

- `service_failure` for failed or unavailable services.
- `scam_allegation` for fraud or theft allegations.
- `regulatory_escalation` for references to regulators, lawyers or legal action.
- `public_escalation` for viral, trend, thread or repost language.
- `abusive_language` for hostile language.
- `high_reach` when public engagement passes the configured demo threshold.

These are triage indicators, not legal or reputational conclusions. They help bank staff prioritize responses and protect the bank's public image by surfacing high-risk complaints early.

Each social receipt stores:

- Public engagement metrics.
- Reputation flags.
- Reputation score.
- Privacy-safe author hash.
- Matched aliases.
- Source URL.
- Analysis method.

AI classification remains a separate deeper analysis step. The rules-based social triage does not claim to be semantic AI.

## AI classification

The AI layer supports Claude and optional Gemini providers, with deterministic fallback rules when no provider is configured or a provider request fails.

Classification extracts:

- Issue type.
- Severity.
- Sentiment.
- Language.
- Mentioned amount.
- Mentioned time.
- Fraud status.
- Short summary.
- Confidence.

Supported multilingual fallback categories include English, Nigerian Pidgin and mixed Yoruba, Hausa and Igbo content.

The worker queue allows classification to happen after social ingestion without blocking the receipt endpoint.

## Incident detection and investigation

The spike detector uses time buckets, historical baselines, median absolute deviation and minimum-volume thresholds to identify complaint spikes.

```text
POST /api/v1/incidents/detect
GET  /api/v1/incidents
GET  /api/v1/incidents/{incident_id}
```

Investigation routes include:

```text
POST /api/v1/ai/incidents/{incident_id}/investigate
GET  /api/v1/ai/incidents/{incident_id}/drafts
GET  /api/v1/ai/incidents/{incident_id}/audit
```

The investigation pipeline combines:

- Complaint evidence.
- Transaction failures.
- Processor and channel data.
- Nearby system events.
- Baseline comparisons.
- Ranked likely causes.
- Bounded AI tool use.
- Deterministic fallback findings.

Investigation tools are read-only. The system does not directly refund customers, reverse transactions, block accounts or move money.

## Drafts and approval

The system creates human-reviewable drafts for:

- Customer messages.
- IT tickets.
- Reversal requests where applicable.

Draft decisions are recorded through:

```text
POST /api/v1/ai/drafts/{draft_id}/decision
```

Money-related actions require human approval. The prototype blocks direct reversal execution and records approval decisions in the audit log.

## Worker queue

The transactional worker handles:

- Complaint classification.
- Spike detection.
- Incident investigation.
- Approval dispatch.
- X stream rule synchronization.

Worker routes include:

```text
GET  /api/v1/jobs
POST /api/v1/jobs/drain
```

Jobs include idempotency keys, retries, leases, failure tracking and dead-letter handling. The demo can drain jobs synchronously, while a future deployment can run the worker continuously.

## Audit logging

Important actions are recorded, including:

- Demo login.
- Complaint classification.
- Social alias changes.
- Social post ingestion.
- X rule synchronization.
- AI tool calls.
- Incident investigation.
- Draft creation.
- Draft approval or rejection.
- Worker dead-letter events.

Audit records are bank-scoped where the event belongs to a specific tenant.

## Database migrations

The migration chain includes the initial schema, row-level security, AI complaint fields, social intake, worker jobs and social intelligence fields.

Before using a hosted database, run:

```sh
cd backend
python -m alembic upgrade head
```

The active feature branch includes migrations for social engagement metrics, reputation fields and privacy-safe author hashes.

## Testing and validation

The test suite covers:

- Demo authentication.
- JWT validation.
- Tenant isolation.
- Complaint privacy masking.
- Synthetic seeding.
- Analytics windows.
- Repeat spike detection.
- Social alias matching.
- Hashtag and handle matching.
- No-match and ambiguous-match handling.
- Social deduplication.
- X payload parsing.
- X rule synchronization.
- X replay.
- X Recent Search request shape.
- Multi-tenant fan-out.
- AI fallback classification.
- Nigerian language handling.
- Investigation safety.
- Worker queue behavior.
- Draft approval restrictions.

Run the backend tests from `backend/`:

```sh
python -m pytest -q
```

The active environment must have all packages from `backend/requirements.txt`, including the Anthropic SDK.

## Current demo flow

The recommended presentation flow is:

1. Start the backend.
2. Log in with `Zymic Bank` and `123`.
3. Configure or display bank handles and hashtags.
4. Use live X pull when `X_BEARER_TOKEN` is configured.
5. Otherwise replay recorded X posts.
6. Drain the worker queue.
7. Open the complaints feed and show masked post content.
8. Open social analytics and show reach, risk flags and hourly velocity.
9. Detect the complaint spike.
10. Investigate the incident.
11. Show the likely cause and evidence.
12. Show the customer and IT drafts.
13. Approve or reject a draft.
14. Open the audit trail.

## Remaining demo setup

The backend is functionally prepared for the demonstration. The remaining setup work is operational:

- Install all backend dependencies in the active virtual environment.
- Configure a random demo token secret.
- Configure Supabase `DATABASE_URL` if using hosted Postgres.
- Run Alembic migrations.
- Configure `X_BEARER_TOKEN` only if live X access is available.
- Connect the frontend dashboard to the backend routes.
- Decide whether to run worker draining manually during the presentation or host a background worker.

The recorded replay path remains available as the reliable fallback for a presentation without live X access.
