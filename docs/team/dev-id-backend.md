# dev_id — Bank complaint ingestion and source integrity

Read [shared sprint plan](../backend-team-workplan.md) and the [agent prompting guide](agent-prompting-guide.md) first. Use the copyable dev_id prompt there when delegating work. Backend today; no frontend edits. Branch suggestion: `feat/bank-complaint-ingestion`.

## Goal

Make a bank support system able to send synthetic complaint tickets into Conflux securely and reliably. Social intake already exists: reuse it, do not rebuild every connector today.

## Read first

- `backend/app/api/routes/complaints.py`
- `backend/app/schemas/complaint.py`
- `backend/app/services/complaint_service.py`
- `backend/app/core/privacy.py`
- `backend/app/services/social_intake.py`
- `backend/app/api/routes/social.py`
- `backend/app/models/complaint.py` and `backend/app/models/job.py`

## Owned work

Suggested new modules: `api/routes/ingestion.py`, `schemas/ingestion.py`, `services/bank_intake.py`, `models/complaint_receipt.py`; focused tests and a synthetic support-ticket sender/fixtures. Coordinate existing complaint model changes with Opeyemi.

1. Implement the proposed intake contract from the shared plan.
2. Authenticate a connector credential bound to a single bank. Never trust a client-supplied bank ID. Store credential hashes, redact logs and support revocation; never use GATEWAY_KEY as a bank customer credential.
3. Validate bounded text, timezone-aware times, supported channel values, decimal amount/currency and permitted metadata. Inspect existing enums; map `call_center` to the existing call channel rather than silently adding incompatible values.
4. Persist receipt/provenance and masked complaint with atomic classification-job enqueue. Acknowledge only after commit. Do not run model calls inside the request.
5. Enforce database-backed uniqueness `(bank_id, connector_id, external_id)` under concurrent delivery. Identical replay returns existing record; conflicting create-only payload returns 409. No silent overwrites.
6. Preserve source reports. Same person reporting via email and X may be linked but is not automatically two affected customers or a confirmed duplicate.
7. Pass payment reference to a structured correlation field/service; do not discard it or bury the only reference in model-generated text.
8. Add a reproducible synthetic bank-ticket sender: call/in-app examples in English and Pidgin linked to configured sandbox references. This is a simulated bank customer-service system, not an XtraDot complaint endpoint.
9. Preserve current social live/replay labels and processing path. Do not ingest real social PII into Forge, whose policy permits synthetic data only.

## Handoffs

- To Opeyemi: durable complaint ID, receipt ID, bank/connector scope, source, external ID, timestamps, payment reference, processing status and migration.
- To Andrew: masked text and validated optional context through existing classification jobs.
- To Adfola: structured bank/provider-scoped payment reference for evidence lookups.
- To frontend team tomorrow: request/response/error examples and complaint processing/provenance fields.

## Required tests

Invalid/revoked credential; forged bank ID; cross-bank reads; malformed/oversized text; naive timestamps; identical and concurrent duplicate delivery; conflicting replay; transaction rollback without orphan jobs; masking; multilingual fixtures; unsupported channels; payment reference survives reload. Verify no accepted complaint disappears when the worker/provider fails.

## Done today

A synthetic bank sender submits tickets from two channels, replay is safe, a worker classifies them, and stored records expose provenance without secrets. CSV/SFTP/email connectors are future adapters, not required implementations today.

Do not edit shared router/config/worker/migration chain without coordinating with Opeyemi. Supply a small registration/settings patch and run focused tests; report any blocked checks honestly.
