# Conflux HQ Backend Team Workplan

## Objective

Complete the backend for the hackathon around one core promise:

> Conflux HQ helps African financial institutions detect, investigate and safely resolve payment failures by connecting customer reports, social signals, transaction records and system events.

This plan divides the remaining backend work among three people. Person 1 owns the largest workstream because they have the most implementation credits and will coordinate the core payment-intelligence flow.

## Shared rules

- Work from the latest feature branch before starting.
- Keep all changes tenant-scoped by `bank_id`.
- Never expose Supabase service-role keys, X bearer tokens or social adapter credentials.
- Never execute refunds, reversals or money movement automatically.
- Use human approval for financial or public-response actions.
- Mask personal information before persistence or logging.
- Add tests for every endpoint and important business rule.
- Use migrations for every database schema change.
- Keep synthetic fixtures clearly marked as synthetic.
- Push completed commits to the assigned feature branch and open a pull request for review.
- Do not mix unrelated changes into another person’s workstream.

## Person 1: Payment intelligence, reconciliation and orchestration

### Scope

Person 1 owns the largest and most central workstream. They connect complaints, social posts, transactions, incidents, reconciliation and worker processing into one payment-incident workflow.

### Features

#### Payment exception model

Add a bank-scoped payment exception or reconciliation case model with:

- Complaint ID.
- Transaction ID.
- Bank ID.
- Customer reference hash.
- Exception type.
- Amount.
- Currency.
- Payment channel.
- Processor or switch.
- Transaction reference.
- Settlement status.
- Match confidence.
- Evidence summary.
- Owner.
- Priority.
- Current status.
- Created, updated and resolved timestamps.
- Human approval fields.

Recommended exception types:

- Debited but not credited.
- Failed transfer.
- Pending beyond expected time.
- Reversed but not refunded.
- Duplicate debit.
- Duplicate settlement.
- Processor timeout.
- Switch outage.
- Unknown settlement status.
- Fraud-related payment dispute.

Recommended lifecycle:

```text
reported -> transaction_matched -> settlement_checked -> reconciliation_pending -> approval_required -> resolved
```

#### Settlement and transaction matching

Implement matching between complaints and transactions using:

- Exact transaction reference.
- Customer reference hash.
- Amount.
- Time window.
- Channel.
- Processor.
- Sender or recipient reference where permitted.

Return a match confidence value and explain the matching evidence.

Support these match results:

- Exact match.
- Strong match.
- Possible match.
- No match.
- Conflicting matches.

#### Incident command center API

Extend incident responses with:

- Affected customers.
- Affected channels.
- Failed, pending, reversed and successful transaction counts.
- Linked payment exceptions.
- Linked social complaint count.
- Complaint growth rate.
- First detected time.
- Estimated unverified exposure.
- Linked processor, switch and system events.
- Current owner.
- Recommended next action.

Add an evidence timeline endpoint for each incident.

#### Worker orchestration

Extend the worker queue to process:

- Transaction matching.
- Reconciliation case creation.
- Incident enrichment.
- Social trend evaluation.
- Reconciliation reminders.
- Approval dispatch.
- Incident resolution updates.

Keep jobs idempotent, retryable and tenant-scoped. Add dead-letter tests.

#### Safe financial action workflow

Create proposal records for:

- Reversal request.
- Refund request.
- Customer compensation recommendation.
- Public communication approval.

Proposals must remain pending until a human approves them. The backend must not call a bank or payment processor to move money in this prototype.

### Suggested files

- `backend/app/models/payment_exception.py`
- `backend/app/models/settlement.py`
- `backend/app/schemas/reconciliation.py`
- `backend/app/services/transaction_matching.py`
- `backend/app/services/reconciliation.py`
- `backend/app/api/routes/reconciliation.py`
- `backend/app/api/routes/incidents.py`
- `backend/app/services/worker.py`
- `backend/alembic/versions/0007_payment_exceptions.py`
- `backend/tests/test_reconciliation.py`
- `backend/tests/test_transaction_matching.py`

### Acceptance criteria

- A complaint can be matched to a transaction with a confidence score.
- A debited-but-not-credited case appears in a reconciliation queue.
- Every case is bank-scoped.
- A human can approve or reject a proposed action.
- No endpoint moves money automatically.
- Incident detail includes transaction, social and system evidence.
- Tests cover exact matches, ambiguous matches, no matches, duplicate cases and tenant isolation.

## Person 2: AI analysis, clustering, fraud and reputation intelligence

### Scope

Person 2 owns deeper content intelligence. Their work should make the system explain what customers are reporting, identify related complaints and prioritize fraud or reputation risk.

### Features

#### Payment-specific classification

Expand classification categories to include:

- Debited but not credited.
- Failed transfer.
- Pending transfer.
- Delayed settlement.
- Reversed but not refunded.
- Double debit.
- Duplicate payment.
- Card or ATM failure.
- Point-of-sale failure.
- Processor timeout.
- Switch outage.
- Fees.
- Fraud or scam.
- Account takeover.
- Unknown payment issue.

Return:

- Category.
- Severity.
- Sentiment.
- Language.
- Mentioned amount.
- Mentioned time.
- Fraud status.
- Confidence.
- Short explanation.
- Evidence phrases from the masked content.

#### Complaint clustering

Group similar complaints by issue and meaning. Each cluster should expose:

- Cluster ID.
- Bank ID.
- Label.
- Complaint count.
- Growth rate.
- First and last seen time.
- Affected channels.
- Affected regions.
- Fraud count.
- Sample masked complaints.
- Related incident ID.

A deterministic similarity fallback is required when the AI provider is unavailable.

#### Root-cause analysis improvements

Improve investigation output with:

- Likely cause.
- Confidence.
- Supporting evidence.
- Contradicting evidence.
- Affected systems.
- Affected channels.
- Recommended owner.
- Recommended next step.
- Clear distinction between fact, inference and recommendation.

The investigation agent must remain read-only.

#### Fraud and security queue

Add fraud-specific routing for:

- OTP requests.
- Fake bank agents.
- Phishing links.
- SIM-swap indicators.
- Unauthorized transfers.
- Account takeover claims.
- Repeated fraud reports.
- Suspicious transaction clusters.

Add bank-scoped endpoints for listing and prioritizing fraud cases.

#### Reputation intelligence

Extend existing social signals with:

- High-reach negative posts.
- Scam allegations.
- Regulatory escalation.
- Coordinated complaint patterns.
- Repeated complaint themes.
- Public escalation urgency.
- Recommended response priority.

Use careful labels such as `reputation_signal`, `triage_indicator` and `requires_review`. Do not make legal or defamatory conclusions.

#### AI safety and evaluation

Add or verify:

- Strict structured output validation.
- Confidence thresholds.
- Human review for low-confidence outputs.
- Prompt-injection resistance for post content.
- AI audit metadata.
- Provider failure fallback.
- Golden evaluation coverage.
- Tests for multilingual and adversarial content.

### Suggested files

- `backend/app/ai/schemas.py`
- `backend/app/ai/classifier.py`
- `backend/app/ai/fallback.py`
- `backend/app/ai/guardrails.py`
- `backend/app/ai/clustering.py`
- `backend/app/ai/reputation.py`
- `backend/app/api/routes/ai.py`
- `backend/app/api/routes/fraud.py`
- `backend/app/models/complaint_cluster.py`
- `backend/app/models/fraud_case.py`
- `backend/alembic/versions/0008_ai_intelligence.py`
- `backend/tests/test_ai.py`
- `backend/tests/test_clustering.py`
- `backend/tests/test_fraud.py`

### Acceptance criteria

- A masked post receives a payment-specific category and confidence.
- Similar complaints form a visible cluster.
- Fraud complaints enter a separate security queue.
- Root-cause findings distinguish evidence from inference.
- AI failure falls back safely without dropping the complaint.
- Low-confidence outputs remain reviewable rather than being treated as facts.
- No AI tool can execute money movement.
- Tests cover prompt injection, malformed output, multilingual text and fraud routing.

## Person 3: Social ingestion, analytics, audit and operational readiness

### Scope

Person 3 owns external signal quality, trend reporting, platform integration and operational visibility. They should make the payment incident workflow easy to monitor and demonstrate.

### Features

#### X and social ingestion

Complete and stabilize:

- X Recent Search.
- X Filtered Stream rule synchronization.
- Handles and hashtags.
- Native X payload parsing.
- Social adapter authentication.
- Multi-bank fan-out.
- Deduplication.
- Replay mode.
- Public engagement metrics.
- Post source URLs.
- Privacy-safe author references.

Add validation for:

- Unsupported platform payloads.
- Invalid source URLs.
- Missing post IDs.
- Oversized content.
- Duplicate delivery.
- Malformed metrics.

#### Social trend analytics

Extend `/api/v1/analytics/social` with:

- Complaint volume velocity.
- Unique authors.
- Engagement growth.
- High-reach posts.
- Reply and repost counts.
- First-seen time.
- Top aliases.
- Top issue categories.
- Geographic concentration.
- Channel concentration.
- Emerging, growing and viral labels.

Keep all results bank-scoped for operator-facing routes.

#### Incident timeline and reporting

Add operational reporting for:

- Time from post receipt to classification.
- Time from first complaint to detection.
- Time from detection to investigation.
- Time from investigation to approval.
- Number of affected customers.
- Number of unresolved exceptions.
- Number of high-risk posts.
- Number of fraud cases.

#### Audit and observability

Improve audit entries with:

- Correlation ID.
- Request ID.
- Job ID.
- Source platform.
- Actor type.
- Model and prompt version.
- Input and output token counts where applicable.
- Processing latency.
- Failure reason.

Add health checks for:

- Database.
- Worker queue.
- X credentials.
- AI provider configuration.
- Migration status.

#### Demo operations

Provide a reliable demo mode that can:

- Load the synthetic scenario.
- Replay recorded X posts.
- Drain workers.
- Detect incidents.
- Produce investigation results.
- Generate drafts.
- Show audit records.

Document the exact commands and environment variables for the presentation.

### Suggested files

- `backend/app/adapters/x_adapter.py`
- `backend/app/services/social_intake.py`
- `backend/app/api/routes/social.py`
- `backend/app/api/routes/analytics.py`
- `backend/app/services/audit.py`
- `backend/app/api/routes/health.py`
- `backend/app/api/routes/jobs.py`
- `backend/app/models/audit_log.py`
- `backend/tests/test_x_adapter.py`
- `backend/tests/test_social.py`
- `backend/tests/test_analytics.py`
- `docs/social-scanner-handoff.md`

### Acceptance criteria

- A post containing a configured hashtag reaches the correct bank.
- Full post content is available to downstream analysis after masking.
- Engagement and trend metrics are visible through an API.
- Replay mode reproduces the same demo flow without live credentials.
- Operational endpoints expose failures clearly.
- Audit records connect ingestion, jobs, AI analysis and approvals.
- Tests cover X request shapes, hashtags, replay, deduplication and trend calculations.

## Shared integration contract

Person 1 depends on:

- Complaint IDs and transaction IDs from existing ingestion.
- Social receipts and incident IDs.
- AI classifications from Person 2.
- Worker jobs from Person 3.

Person 2 depends on:

- Full masked complaint text.
- Payment and transaction evidence from Person 1.
- Social engagement and reputation fields from Person 3.

Person 3 depends on:

- Stable complaint and incident schemas.
- Stable bank-scoped authentication.
- Worker job types and idempotency behavior.

Before merging, each person must run:

```sh
cd backend
python -m pytest -q
python -m alembic check
```

If the full environment is unavailable, they must at minimum run Python compilation for changed files and the focused test modules.

## Suggested delivery order

### First delivery

- Person 1: payment exception model and transaction matching.
- Person 2: payment-specific classification and fraud routing.
- Person 3: hashtag ingestion, X metrics and social trend endpoint.

### Second delivery

- Person 1: reconciliation lifecycle and incident evidence timeline.
- Person 2: complaint clustering and grounded root-cause output.
- Person 3: audit correlation, health checks and demo replay commands.

### Final integration

- Run the synthetic payment incident scenario.
- Replay or pull X posts.
- Drain classification and matching jobs.
- Detect and investigate the incident.
- Confirm the reconciliation queue is populated.
- Review fraud and reputation queues.
- Approve a safe draft.
- Verify audit history.
- Run the complete backend test suite.

## Definition of done

The backend is ready for the hackathon when one end-to-end scenario proves that:

1. A customer reports a payment failure.
2. The bank is identified from a name, handle or hashtag.
3. Personal information is masked.
4. The complaint is classified and clustered.
5. The related transaction is matched or marked unresolved.
6. A reconciliation exception is created.
7. Transaction and system evidence are linked.
8. A payment incident is detected.
9. Fraud and reputation risk are prioritized.
10. A human-reviewable response and operational action are drafted.
11. No money moves automatically.
12. Every step is auditable and tenant-scoped.
