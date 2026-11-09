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
