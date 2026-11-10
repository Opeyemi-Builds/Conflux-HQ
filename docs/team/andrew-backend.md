# Andrew — Huawei MaaS classification and grounded investigation

Read [shared sprint plan](../backend-team-workplan.md) and the [agent prompting guide](agent-prompting-guide.md) first. Use the copyable Andrew prompt there when delegating work. Backend today; no frontend edits. Branch suggestion: `feat/maas-investigation`.

## Goal

Use the Forge Huawei MaaS model for complaint understanding and incident investigation without allowing model output to become an unsupported fact or perform an action.

## Read first

- `backend/app/ai/classifier.py`
- `backend/app/ai/fallback.py`
- `backend/app/ai/schemas.py`
- `backend/app/ai/guardrails.py`
- `backend/app/api/routes/ai.py`
- `backend/app/core/config.py`
- `backend/app/services/worker.py`
- `backend/app/ai/evidence.py`

## Owned work

Suggested modules: `backend/app/ai/providers/maas.py`, `backend/app/ai/investigation.py`, optional `backend/app/ai/clustering.py`; focused tests. Do not add OpenAI or Anthropic calls to the Forge path. The guide shows an OpenAI-compatible client pointed at Huawei MaaS; use the project's existing abstraction and exact documented SDK only.

1. Add a server-only MaaS provider using internal base URL and `GATEWAY_KEY` injected at runtime. Never expose the key, raw prompt, raw complaint PII or provider errors in API responses/logs.
2. Make model/URL/timeouts configurable. Start with an enabled model confirmed by a smoke test (`glm-5.2` is listed in the guide; do not assume `glm-3.5` exists). Disable reasoning for routine calls as the guide recommends. Respect a shared 60 requests/minute budget and cache/reuse safe results.
3. Keep existing deterministic fallback. Provider timeout, unavailable model, quota 429 or malformed output must leave the complaint and job intact and produce a reviewable fallback, not a false successful investigation.
4. Enforce structured output validation. Classification should return payment issue, severity, language, sentiment, amount/time, fraud flag, confidence and explanation/evidence phrases. Preserve `null` when unknown.
5. Add bounded complaint clustering or similarity fallback if scope fits: cluster by masked text, issue and time/context; preserve individual complaint IDs and do not turn shared wording into proof of a common technical cause.
6. Add investigation output with separate arrays for `observed_facts`, `hypotheses`, `supporting_evidence_ids`, `contradicting_evidence_ids`, `missing_evidence`, `recommended_checks`, `recommended_owner` and `corrective_actions`. Every evidence ID must refer to stored complaint/payment/system/social evidence; no invented IDs or metrics.
7. Treat all complaint/social text as untrusted input. Defend against prompt injection, request instructions in content and attempts to cause tools/actions. This provider is read-only; it cannot call transfers, reconciliation mutations, proposals or outbound messages.
8. Use grounded prompts that require the model to say “unknown” and distinguish customer report, provider event, correlation and bank-confirmed cause. Do not generate a root cause from timing alone.
9. Store model/provider metadata needed for audit without storing secrets: model, version/prompt identifier, latency, status and confidence. Avoid raw text in telemetry.

## Handoffs

- To Opeyemi: exact validated schemas and investigation request/result lifecycle; evidence IDs required.
- To dev_id: classification job input and failure states.
- To Adfola: payment evidence field names and freshness labels consumed by investigation.
- To frontend tomorrow: example investigation brief with facts vs hypotheses vs recommended checks, confidence and missing evidence.

## Required tests

GLM structured success; provider unavailable; 429; timeout; malformed JSON; low confidence; Nigerian English/Pidgin/Yoruba/Hausa/Igbo mixed examples; prompt injection; unsupported category; missing evidence; fabricated evidence ID; deterministic fallback; tenant isolation; no tool/action invocation.

## Done today

A synthetic incident can be investigated through MaaS or fallback and returns a grounded brief that cites stored evidence IDs, labels hypotheses, lists missing evidence and cannot move money. A model output alone must never close a case or confirm fraud.

Do not edit shared router/config/model exports without coordinating with Opeyemi. Supply focused provider/tests and a settings proposal.

## Implementation handoff

### Runtime and ownership

Use the existing `AI_PROVIDER=maas` setting. Inject `MAAS_BASE_URL`,
`MAAS_MODEL`, `MAAS_TIMEOUT_SECONDS` and `GATEWAY_KEY` at runtime in the
authorized Forge workload. Supply the internal URL with its version prefix
and without `/chat/completions`. Select a model verified in that namespace.
The existing HTTP client calls the OpenAI-compatible Huawei endpoint with
`apikey`, reasoning disabled, no tools and one attempt.

Opeyemi should construct one `MaaSClient(MaaSSettings.from_environment(),
acquire_shared_slot)` per process. The callback must atomically grant a slot
from the same rolling 60-second, 60-call budget used by XtraDot across replicas.
The client fails closed on budget rejection or failure. Wire this client via
`configure_forge_classifier(client)` in API and worker startup. The classifier
keeps its existing `(ClassificationResult, "llm" | "rules")` contract.
`ForgeClassification.model_json_schema()` defines the validated provider
payload. The existing public classifier returns a server-written summary
and omits model-provided explanations and raw evidence phrases.

For the explicit investigation job, call
`investigate_grounded(db, bank_id, incident_id, client)`. Persist
`result.brief.model_dump(mode="json")` as the result and `result.metadata`
as audit metadata. Map `LookupError` to a tenant-neutral 404. Use this
service in place of the legacy draft-producing Forge path. The service does
not change incident status, confirm fraud, create actions, or send messages.
Publish `InvestigationResult.model_json_schema()` when wiring the route.
No migration or dependency manifest changes are required for this slice.

### Evidence contract and example

Reads are tenant-scoped and bounded to 12 records per source. Payment links
remain candidates, and nearby events are correlations. Provider freshness
and verified settlement are unknown until the payment evidence integration
supplies them. Wording groups use masked normalized text, issue and UTC hour.
They return individual stored complaint IDs and do not establish cause.

```json
{
  "incident_id": "00000000-0000-4000-8000-000000000002",
  "observed_facts": [{"evidence_id": "00000000-0000-4000-8000-000000000001", "source": "customer_report", "status": "in_app", "occurred_at": "2026-11-09T10:00:00+00:00"}],
  "hypotheses": [],
  "supporting_evidence_ids": [],
  "contradicting_evidence_ids": [],
  "missing_evidence": ["bank_confirmed_cause", "payment_candidate", "correlated_event", "social_report", "verified_settlement_and_processor_trace"],
  "recommended_checks": ["review_complaint_links", "verify_payment_status"],
  "recommended_owner": ["operations", "payments"],
  "corrective_actions": ["review_associations"],
  "similar_wording_groups": []
}
```

Stable failure reasons include `not_configured`, `budget_unavailable`,
`budget_exhausted`, `rate_limited`, `timeout`, `provider_unavailable`,
`invalid_output`, `ungrounded_output`, `low_confidence` and
`missing_evidence`. Fallback results carry `source: rules`. Audit metadata
contains model, prompt version, status, latency and confidence, with no
prompt, complaint text, credentials or raw provider error. Validated
investigations can be reused for five minutes by bank and evidence snapshot.

Live GLM availability and protocol verification remain pending an authorized
Forge workload. The local GLM tests use synthetic responses.
