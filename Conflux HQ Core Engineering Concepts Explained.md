# **Conflux HQ: Core Engineering Concepts Explained**

Prepared for the Conflux HQ team · Access Youth Tech Forge, Theme 1 · Scaled-down build, same structure

This document explains each core engineering idea behind Conflux HQ in brief, and how it looks in the lean version of the build.

## **1\. Deterministic core, LLM at the edges**

Detection, bucketing, cause scoring and state changes are plain code. Claude only classifies, summarises and drafts. This makes the demo reliable and gives you a clear answer for judges: the AI can never be the reason money moves.

## **2\. Privacy boundary**

* **Masking at the adapter edge:** phones, account numbers, BVNs, cards (Luhn check), emails and names are redacted before anything reaches the analysis DB or an LLM.  
* **HMAC pseudonymization:** the same customer always gets the same token (so repeat-complaint rate still works), but the token cannot be reversed without the key.  
* **Data minimization:** the LLM sees only masked text, channel and aggregates, never raw transaction rows.  
* **Lean version:** one raw table the analysis code never queries, plus a log entry on every read. Describe the separate DB role as the production design.

## **3\. Idempotency (safe to retry anything)**

| Stage | Idea |
| :---- | :---- |
| Ingest | Unique key on hash(source, source\_msg\_id), so replays and duplicates are ignored |
| Classify | Cache by (complaint, prompt version, model), so rerunning costs nothing |
| Buckets | Derived data, recomputed by upsert, so late events fix themselves |
| Incident | The detector merges into an open incident instead of creating a duplicate, and closes after N quiet buckets so it does not flap |
| Agent run | A new run only if the evidence changed |
| Approval | Idempotency key plus compare-and-set, so a double-click cannot create two reversals |
| Side effects | **Outbox pattern:** the approval and the "to-do" are written in one transaction, then a worker dispatches it |
| Audit | Append-only and hash-chained, so tampering is detectable |

## **4\. Jobs table as the queue**

Instead of Redis or Kafka, use a table with status, attempts, lease time and a dead-letter state. It is transactional with your data and removes a dependency. In SQLite you claim a job with a single UPDATE ... RETURNING.

## **5\. Graceful degradation**

* **LLM down:** timeout, retry with backoff, then a rules-based classifier (keywords including Pidgin patterns), tagged classified\_by=fallback. Detection keeps running.  
* **Agent fails:** a deterministic **evidence pack** (stats, matched transactions, nearby events, baseline delta) is built first, so the UI still shows facts plus a template summary.  
* **Late or out-of-order events:** bucket by event time and recompute affected buckets.  
* **Demo safety:** a record/replay cache of LLM responses lets the whole demo run offline.

## **6\. AI orchestration**

* **Model tiering:** a small fast model for classification, a stronger one for the investigation agent and drafts.  
* **Cost levers:** batch complaints per call, cache the system prompt and few-shot examples, classify near-duplicates once, and run the agent only per incident. Show **cost per 1,000 complaints** on the dashboard.  
* **Structured output:** a strict JSON schema, Pydantic validation, one repair retry, then dead-letter.  
* **Computed confidence:** cause ranking comes from time proximity, path overlap and failure-rate delta. The LLM explains the ranking but does not assign it.  
* **Grounding verifier:** every amount, count and time in a draft is checked against the DB, and a mismatch blocks the draft.  
* **Bounded agent:** about 6 steps, read-only tools, validated arguments, and a full trace in the audit log.  
* **Prompt-injection hygiene:** complaints are untrusted input, so they are delimited and never passed into tool arguments, and the agent has no write tools.  
* **Eval harness:** a versioned prompt registry and the 100-item golden set, reporting accuracy per language and a confusion matrix.

## **7\. Detection fixes**

* Simulate 72 hours so there is enough baseline for "same time of day".  
* Put a floor under MAD (it can be zero on sparse data) and add a Poisson check as a second gate.  
* Localize the spike by comparing each channel, switch or region's share against its normal share. That is how you get "USSD \+ app via SwitchX" deterministically.  
* Show the isolated incident as a deliberate non-alert, with the reason it did not fire.

## **8\. Engineering hygiene**

* A modular monolith: one repo, shared Pydantic contracts.  
* Alembic migrations (optional if you are on SQLite and short on time).  
* SSE for live dashboard updates.  
* Correlation IDs in logs.  
* Separation of duties, so the person who requests a reversal cannot approve it.  
* A pre-commit secret scan.

## **9\. The chaos demo**

Kill the LLM mid-run and show that detection, alerts and the evidence pack still work. It proves the robustness claims better than any slide.

## **Next step**

Build the masking module with its no-PII-leaks test, or the SQLite schema and jobs table.