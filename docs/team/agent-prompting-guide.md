# Backend agent prompting guide

Audience: dev_id, Andrew, Adfola and Opeyemi.

This guide makes delegated-agent work consistent with the current Conflux backend plan. Read it before prompting an implementation agent. The agent's final response is a summary only; inspect the working tree, tests and diff before accepting the work.

## Current product boundary

Conflux unifies authorised bank complaints, social signals and payment evidence. It detects shared payment problems, investigates evidence-backed hypotheses and tracks corrective actions. It does not claim to prove root cause from complaints alone, does not automatically move money and does not have live NIBSS access.

Current backend already includes:

- FastAPI, SQLAlchemy and Alembic.
- Bank-scoped JWT/demo authentication and role checks.
- Complaint intake, masking/pseudonymisation, classification jobs and deterministic fallback.
- X/social intake, aliases, replay/live provenance and social analytics foundations.
- Incidents, evidence summaries, audit logs and worker jobs.
- Transactions and synthetic demo data.
- Payment exceptions, candidate transaction matching, settlement/reversal fields and non-executing refund/reversal proposals.
- Reconciliation timelines and synthetic reset cleanup.
- Render/Supabase production deployment; Forge/XtraDot integration is a separate sandbox deployment concern.

Do not rebuild these features or replace working files wholesale. Extend existing contracts compatibly.

## Read order for every agent

1. `docs/backend-team-workplan.md`
2. The assigned role file in this directory.
3. The exact target files listed by the role.
4. Relevant tests, migrations and model exports.
5. `git status --short` and `git diff` before editing.

## Prompt template — copy and fill

```text
You are implementing the [ROLE] slice for Conflux HQ in the repository at [PATH].

Read first:
- docs/backend-team-workplan.md
- docs/team/[ROLE-FILE].md
- [EXACT TARGET FILES]

Goal:
[ONE TESTABLE OUTCOME]

Use the existing FastAPI/SQLAlchemy/Alembic architecture and preserve current public contracts unless a compatibility change is explicitly required. Do not touch frontend files. Do not rewrite unrelated files. Keep all records bank-scoped.

Implementation requirements:
- [REQUIREMENT 1]
- [REQUIREMENT 2]
- [SECURITY/PRIVACY REQUIREMENT]
- [ERROR/IDEMPOTENCY REQUIREMENT]

Evidence rules:
- Customer text is reported evidence.
- Provider/sandbox events are provider evidence.
- Matches are candidates unless exact and provider-scoped.
- Timing is correlation, not causation.
- AI output is a hypothesis/recommendation, not a fact.

Security constraints:
- Never expose or commit credentials, kubeconfig files, GATEWAY_KEY, webhook secrets, API tokens or raw PII.
- Do not call payment execution, refund or reversal actions automatically.
- Keep secrets server-side and redact them from logs/errors.

Tests:
- Add focused tests for [CASES].
- Include tenant isolation and failure behavior.
- Run the focused tests and compile/lint checks available locally.
- If an external Forge API is unavailable, use recorded synthetic fixtures and state exactly which smoke test is blocked.

Handoff:
- Report files changed, contracts added, tests run/results, migration revision, known limitations and exact integration instructions.
- Do not claim a test, deployment or live integration passed unless it actually ran.
```

## Prompt template — review/fix pass

```text
Review the current implementation of [FILES] against docs/team/[ROLE-FILE].md and docs/backend-team-workplan.md.

Find only verified correctness, security, tenant-isolation, data-integrity, idempotency and contract issues. Check the diff and tests. Do not redesign unrelated code or touch frontend files.

For every issue, give:
1. file and line;
2. concrete failure scenario;
3. smallest safe fix;
4. regression test.

Then apply only confirmed fixes, run focused tests, and report any blocked external checks honestly. Never print secrets or raw PII.
```

## Role-specific starting prompts

### dev_id

```text
Implement the bank complaint-ingestion slice. Add the authenticated, bank-bound POST /api/v1/ingestion/complaints contract, durable receipt/provenance, masking, database idempotency on (bank_id, connector_id, external_id), atomic job enqueue and a synthetic support-ticket sender. Reuse existing complaint/worker/social services. Add tests for concurrent duplicates, conflicting replay, invalid credentials, cross-bank isolation, rollback and PII masking. Do not treat XtraDot as a complaint source.
```

### Andrew

```text
Implement the Huawei MaaS/fallback investigation slice. Use the Forge OpenAI-compatible endpoint only server-side with runtime GATEWAY_KEY; use a model confirmed available by smoke test, not an assumed glm-3.5. Add strict structured validation, grounded facts/hypotheses/missing-evidence/corrective-action output, evidence-ID validation, prompt-injection resistance and deterministic fallback. The agent is read-only: it cannot call transfer, refund, reversal, proposal or outbound-message actions. Add multilingual, malformed-output, timeout, 429 and fabricated-evidence tests.
```

### Adfola

```text
Implement the Forge-only XtraDot evidence slice. Add safe status lookup/requery, immutable normalized payment events, signed webhook verification, five-minute timestamp protection, event deduplication and out-of-order handling. A timeout is outcome_unknown and requires requery; never resend. Use synthetic recorded fixtures if Forge is unavailable. Add tests for invalid signatures, duplicates, pending-versus-failed, successful-then-reversed, 504/429 and no-secret logging. Never commit team10.yml or any key.
```

### Opeyemi

```text
Integrate the three slices without rewriting them. Extend incident/evidence reads, investigation lifecycle, corrective-action persistence and audit correlation; register routes; coordinate one Alembic chain; add connector health and a deterministic end-to-end synthetic scenario. GET/dashboard reads must be read-only. Verification requires explicit evidence and authorised action. Preserve existing reconciliation/proposal behavior and ensure no money movement occurs. Produce OpenAPI examples for tomorrow's frontend rebuild.
```

## Required agent handoff format

Every agent must finish with:

```text
Status: complete | partial | blocked
Files changed:
Contracts added/changed:
Migration:
Tests run and exact result:
External smoke tests:
Security/PII checks:
Known limitations:
Next handoff:
```

## Shared integration checklist

Before merging any slice:

- [ ] No frontend files changed.
- [ ] `git diff --check` passes.
- [ ] Bank ownership is enforced on reads and writes.
- [ ] Duplicate delivery is safe.
- [ ] Failure does not lose the original complaint/event.
- [ ] Money remains a decimal string at API boundaries.
- [ ] Evidence source, environment and freshness are visible.
- [ ] Facts, hypotheses and recommendations are separate.
- [ ] No automatic transfer/refund/reversal execution exists.
- [ ] No secret, kubeconfig, webhook secret or raw PII is in the diff/logs.
- [ ] Migration is linear and has a downgrade.
- [ ] Focused tests pass; blocked checks are recorded.
- [ ] OpenAPI/sample payloads are handed to tomorrow's frontend team.

## Forge-specific safety

The bank and Huawei endpoints are reachable only from a workload inside the Forge namespace. Render and Vercel cannot call the internal hostnames. The team key is injected into the Forge pod and uses `x-api-key` for XtraDot and `apikey` for Huawei. Keep it out of browser code, Docker layers, Git and chat. The sandbox is synthetic and volatile; label it as sandbox in the UI and stored evidence.

The kubeconfig/token previously opened in the IDE is a credential. If it has been copied outside the private team channel, request rotation before deployment. Never ask an agent to print it, inspect its token value or commit it.

## What agents must not do

- Do not add a guessed NIBSS integration.
- Do not call a provider from a dashboard GET or unauthenticated public route.
- Do not claim an XtraDot record proves beneficiary credit at another institution.
- Do not call complaint volume a confirmed loss or root cause.
- Do not use AI output to approve financial proposals.
- Do not make a live API claim from a recorded fixture.
- Do not create meaningless commits or modify unrelated frontend code.
