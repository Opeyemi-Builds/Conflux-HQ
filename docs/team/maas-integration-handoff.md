# MaaS integration handoff — Andrew → Opeyemi (2026-11-10)

Status: complete. Branch: `feat/maas-investigation`. No frontend files touched.
No edits to shared router/config/model exports — fold in per contract below.

## Files changed (this slice)

- `backend/app/ai/providers/__init__.py` — package exports
- `backend/app/ai/providers/maas.py` — server-only OpenAI-compatible chat client
  (`apikey` header, `thinking:false`, typed `MaasError` kinds)
- `backend/app/ai/providers/settings.py` — env `MAAS_*` loader + `GATEWAY_KEY` accessor
- `backend/app/ai/providers/rate_limit.py` — sliding-window 60 req/min guard
- `backend/app/ai/providers/classify.py` — structured validation, `null` preserved,
  `classify_with_fallback` (MaaS → rules, complaint/job intact)
- `backend/app/ai/providers/sanitize.py` — `<complaint>` wrapping + injection screen
- `backend/app/ai/prompts/maas_classify_system.md` — grounded classifier prompt
- `backend/app/ai/prompts/maas_investigate_system.md` — grounded investigation prompt
- `backend/app/ai/investigation.py` — `InvestigationBrief`, registry validation,
  `maas_investigate` / `investigate_with_fallback`
- `backend/app/ai/clustering.py` — bounded triage clustering (IDs preserved,
  shared wording ≠ proof of cause)
- `backend/tests/test_maas_provider.py` (18 tests), `test_maas_investigation.py` (9 tests)

## Contracts added

```python
# Classification (Opeyemi: call from classify job when ai_provider == "maas")
from app.ai.providers.classify import classify_with_fallback
result, source = classify_with_fallback(text, channel,
    config=MaasConfig(...), gateway_key=gateway_key())
# source is "maas" | "rules"; result is ClassificationResult with _runtime telemetry

# Investigation (Opeyemi: supply bundle with evidence_registry, store brief)
from app.ai.investigation import investigate_with_fallback
brief, source, telemetry = investigate_with_fallback(evidence_bundle,
    config=..., gateway_key=...)
# evidence_bundle MUST include evidence_registry: {complaints/transactions/
# system_events/social/payment_evidence: [{id, ...}]}. Unknown cited IDs -> fallback.
```

## Migration

None. No model changes in this slice.

## Tests run and exact result

- New: `tests/test_maas_provider.py` + `tests/test_maas_investigation.py` — **27 passed**
- Full suite at commit time: run `python -m pytest tests/ -q` before merge (was 110 passed at baseline)

## External smoke tests

Blocked (expected): no Forge network from this machine, so no live `glm-5.2`
call was made. All provider HTTP paths are covered with fakes (success, 429,
404, timeout, malformed). Live smoke: set `GATEWAY_KEY` in the Forge pod and
call `maas_classify("my money don enter nowhere", "in_app")`; expect
`failed_transfer`/`pidgin` or a clean `rules` fallback — never an exception.

## Security/PII checks

- `GATEWAY_KEY` only in `apikey` header; absent from errors, logs, telemetry, diff
- Complaint text wrapped as untrusted data; injection patterns flagged
- Telemetry = model/latency/tokens/status/confidence only — no raw text, no secrets
- `git diff --check` clean; tenant isolation asserted (cross-bank IDs rejected)

## Known limitations

- `MAAS_ENABLED` loader is separate from `Settings`; Opeyemi folds into
  `config.py` per `docs/team/maas-settings-proposal.md` if desired
- Clustering is a bounded heuristic for triage, not semantic grouping
- Live Forge smoke test still required before demo reliance

## Next handoff (Opeyemi)

1. Wire `ai_provider == "maas"` in the classify job + explicit investigation POST
   (never dashboard GETs); persist `InvestigationBrief` into `InvestigationRun`
   fields (facts/hypotheses/evidence_ids/missing/recommended_checks/owner).
2. Build the masked evidence bundle with `evidence_registry` from stored rows.
3. Frontend (tomorrow): example brief showing facts vs hypotheses vs
   recommended checks, confidence, and missing evidence — money movement stays
   review-only and disabled.
