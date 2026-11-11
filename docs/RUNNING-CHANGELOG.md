# Conflux HQ — Running Cross-Team Changelog

This is an active, running reference documenting **cross-cutting changes** that affect shared models, APIs, database schemas, worker jobs, and evidence contracts across **dev_id**, **Opeyemi**, **Andrew**, **Adfola**, and the **Frontend team**.

---

## 1. Quick Cross-Cutting Matrix

| Area | Change | Who It Affects | Action Required |
|---|---|---|---|
| **Alembic Head** | Head is now `0011_xtradot_webhooks` (revises `0010_remediation`) | **Opeyemi**, all developers | Base any new migrations on `0011_xtradot_webhooks` |
| **XtraDot Evidence** | New `xtradot_webhook_receipts` table + `POST /forge/webhooks` (signed, 202/duplicate/ignored) + `PROCESS_XTRADOT_WEBHOOK` job wired in worker | **Adfola**, **Opeyemi**, **Frontend** | Sandbox-only; no transfer submission; statuses are observations, not ledger proof. Deploy config: `GATEWAY_KEY`, `XTRADOT_WEBHOOK_SECRET`, `XTRADOT_BANK_ID`, `XTRADOT_SUPPORTED_EVENTS`, `XTRADOT_WEBHOOK_TIMESTAMP_FORMAT` (Forge only) |
| **Corrective Actions** | New `corrective_actions` table + `POST/PATCH /incidents/{id}/actions`, `PATCH /actions/{id}` | **Frontend**, **Opeyemi** | Render action lifecycle `proposed→accepted→in_progress→monitoring→verified`; `verified` needs bank_admin + validation evidence |
| **Investigation Runs** | New `investigation_runs` table + `POST /investigations`, `GET /incidents/{id}/investigations`, `GET /investigations/{id}` | **Andrew**, **Frontend**, **Opeyemi** | GETs never queue jobs; runs persist facts/hypotheses/evidence IDs after drain |
| **Incident Overview** | New `GET /incidents/{id}/overview` single payload (complaints, social corroboration, payment evidence, latest run, actions) | **Frontend** | Use for incident detail view; social counts are triage-only, not proof |
| **Connector Health** | New `GET /health/connectors` (queue, intake, social, investigation, evidence states) | **Frontend**, **Opeyemi** | Show per-provider states; optional provider being down never masks DB health |
| **Synthetic Reset** | Reset now deletes receipts/proposals/cases/actions/runs before parents (FK-safe) | **Opeyemi**, **dev_id** | Safe to reset demo with ingested tickets present |
| **`complaints` Table** | Added column `payment_reference VARCHAR(64)`, indexed | **Adfola**, **Opeyemi**, **Frontend** | Use `complaint.payment_reference` for transaction matching & UI display |
| **`ComplaintRead` Schema** | Added `payment_reference: str | None = None` | **Frontend**, **Opeyemi** | Update TypeScript types to consume `payment_reference` |
| **Worker Queue** | Ingested complaints enqueue `JobKind.CLASSIFY_COMPLAINT` with no pre-labels | **Andrew**, **Opeyemi** | MaaS classifier evaluates severity dynamically |
| **API Router** | Mounted `/api/v1/ingestion` in `app/api/router.py` | **Opeyemi** | Router registration already active; do not overwrite |
| **Frontend Rebuild** | API-First Next.js Rebuild (`/developers`, `/dashboard/settings/keys`, `/dashboard/incidents`, 5s Ticker) | **Frontend**, **All** | Stripe-grade integration docs, machine key generator, real-time handoff ticker, live health status |
| **Trigger Amounts** | Fixed `.02` = timeout/reversal; `.05` = withheld webhook | **Adfola**, **Andrew**, **dev_id** | Reconcile payment status against these exact Forge triggers |
| **Social Guard** | Added `settings.social_live_enabled` | **Forge Deployment** | Set to `false` in Forge namespace to prevent live X calls |

---

## 2. Shared Database Changes

### Migration Chain
```text
0007_payment_exceptions -> 0008_payment_proposals -> 0009_bank_ingestion (HEAD)
```

### Table Changes
1. **`complaints`** (Modified):
   - Added column: `payment_reference` (`String(64)`, nullable, indexed).
   - Links customer-reported tickets directly to payment switches (XtraDot sandbox).
2. **`ingestion_connectors`** (New):
   - Stores bank-scoped API connector credentials (`key_prefix`, HMAC-SHA256 `key_hash`, `status`).
3. **`complaint_receipts`** (New):
   - Database-level deduplication: `UniqueConstraint("bank_id", "connector_id", "external_id")`.
   - Immutable audit trail: stores `content_hash`, `payment_reference`, `amount` (`Numeric(14,2)`), `currency`, `occurred_at`, `received_at`.
4. **`payment_exceptions` & `payment_proposals`** (Added prior in `0007`/`0008`):
   - Tracks transaction reconciliation exceptions and human-approved reversal proposals.

---

## 3. Shared Schema & API Contract Updates

### `backend/app/schemas/complaint.py`
- **`ComplaintRead`**:
  ```python
  class ComplaintRead(BaseModel):
      id: uuid.UUID
      channel: Channel
      text: str
      customer_ref: str | None
      region: str | None
      language: str | None
      occurred_at: datetime
      issue_type: IssueType | None
      severity: Severity | None
      sentiment: Sentiment | None
      summary: str | None
      is_fraud: bool
      mentioned_amount: Decimal | None
      mentioned_time: str | None
      classification_confidence: float | None
      payment_reference: str | None = None  # <--- NEW
      transaction_id: uuid.UUID | None
      incident_id: uuid.UUID | None
  ```
- **`ComplaintCreate`**:
  - Added optional `payment_reference: str | None = None`.

### `backend/app/schemas/ingestion.py` (New Contract)
- **`POST /api/v1/ingestion/complaints`**:
  - Header: `Authorization: Bearer cfx_conn_<prefix>_<secret>`
  - Request: `ComplaintIngestIn`
  - Responses:
    - **`202 Accepted`**: Initial receipt; complaint stored, PII scrubbed, `CLASSIFY_COMPLAINT` job enqueued.
    - **`200 OK`**: Duplicate delivery (`duplicate: true`); returns existing IDs without duplicate jobs.
    - **`409 Conflict`**: Conflicting delivery (same `external_id` with different text/amount).

---

## 4. Cross-Developer Integration Details

### For Opeyemi (Shared Integration & Incident Command)
- **Router Integration:** `api_router.include_router(ingestion.router)` is present in `app/api/router.py`.
- **Receipt API:** Exposed at `GET /api/v1/ingestion/receipts?payment_reference=...` (requires bank login token).
- **Audit Logs:** Ingestion emits `bank_complaint_ingested` with connector prefix (never raw secrets).

### For Andrew (Huawei MaaS Classification & Investigation)
- **Job Enqueue:** Ingested tickets arrive in the SQL queue as `JobKind.CLASSIFY_COMPLAINT` (`payload: {"complaint_id": "..."}`).
- **Pre-labels Removed:** Ingestion fixtures do not hardcode `CRITICAL` or `IssueType`. The classifier must evaluate severity objectively from the masked text.
- **Pidgin & English:** Complaints arrive in standard Nigerian English and Nigerian Pidgin (`language: "pcm"`).

### For Adfola (XtraDot Payment Evidence & Webhooks)
- **Correlation Field:** Query complaints or receipts by `payment_reference` to associate XtraDot payment events.
- **Forge Trigger Values Active:**
  - `amount: "25000.02"` -> Interbank transfer timeout and reversal.
  - `amount: "18000.05"` -> First webhook delivery withheld.
- **Fixture Dispatcher:** You can stream simulated bank complaints linked to your XtraDot references via:
  ```bash
  python backend/scripts/synthetic_bank_sender.py --compress 100
  ```

### For the Frontend Team
- **Complaints Feed:** Complaints now include `payment_reference`. When non-null, display the reference tag in the complaints feed and detail views (`/dashboard/complaints/[id]`).
- **Connector Tokens:** Connector credentials (`cfx_conn_...`) are for bank backend systems, not browser logins. Bank staff continue using standard JWT login tokens.

---

## 5. Security & Secret Hygiene
- Unit test strings such as `"social-demo-test-secret-at-least-thirty-two-characters"` in `backend/tests/test_social.py` are strictly **test fixtures** for in-memory pytest runs.
- Production and live sandbox secrets (`DEMO_TOKEN_SECRET`, `SOCIAL_ADAPTER_TOKEN`, `GATEWAY_KEY`, `INGESTION_HASH_SECRET`) are loaded from environment variables.
- Connector secrets are stored exclusively as HMAC-SHA256 hashes (`key_hash`). Plaintext secrets are never stored or logged.
