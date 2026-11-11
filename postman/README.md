# Conflux HQ — Postman Collection & Testing Guide

This directory contains the complete Postman Collection and Environments for testing Conflux HQ across local development and the deployed Forge Kubernetes environment.

---

## 1. Quick Import Guide

1. Open Postman.
2. Click **Import** (top left).
3. Select the three files in this folder:
   - [`Conflux_HQ.postman_collection.json`](./Conflux_HQ.postman_collection.json) (Collection)
   - [`Conflux_HQ_Local.postman_environment.json`](./Conflux_HQ_Local.postman_environment.json) (Local Environment)
   - [`Conflux_HQ_Forge.postman_environment.json`](./Conflux_HQ_Forge.postman_environment.json) (Forge Pod Environment)
4. In the top-right environment selector in Postman, choose:
   - **`Conflux HQ (Local - 127.0.0.1:8000)`** if testing locally or via `./connect-forge.sh`.
   - **`Conflux HQ (Forge Pod - team10.xtradot.co)`** if testing the live deployed cluster pod directly.

---

## 2. Automated Token Cascading & Scripting Features

You do **not** need to manually copy and paste tokens, hashes, or IDs. The collection automates this:

- **JWT Auto-Save:** Running `01.1 Demo Login` saves `access_token` into `{{jwt_token}}` and `bank_id` into `{{bank_id}}`.
- **Connector Key Auto-Save:** Running `02.1 Provision Ingestion Connector` captures the raw `cfx_conn_...` token into `{{connector_token}}`.
- **Machine API Key Auto-Save:** Running `01.2 Provision Machine API Key` captures the `cfx_api_...` key into `{{machine_api_key}}`.
- **Dynamic HMAC Signature Calculation:** In `05.1 Send Signed Transfer Webhook`, a Pre-request Script automatically computes the required HMAC-SHA256 signature over `timestamp + "." + raw_body` using `{{xtradot_webhook_secret}}`.
- **Incident & Remediation ID Cascading:** Running `06.2 List Incidents` automatically saves `{{incident_id}}`, and `07.1 Propose Corrective Action` saves `{{ca_id}}`.

---

## 3. Recommended Sequential Test Walkthrough

Execute the requests in this order to test the complete end-to-end flow:

### Step 1: Health Probes
- Run `00.1 Liveness Probe (healthz)`: Confirms server is running (`200 OK`).
- Run `00.2 Deep Health & Database`: Confirms SQLite database is connected.

### Step 2: Authentication
- Run `01.1 Demo Login - Zymic Bank`: Authenticates as bank admin (`200 OK`), saves `{{jwt_token}}`.
- Run `00.3 Connector Health Matrix`: Inspects provider states across MaaS, Worker, and Database.

### Step 3: Bank Support Intake & Deduplication
- Run `02.1 Provision Ingestion Connector`: Creates connector token, saves `{{connector_token}}`.
- Run `02.3 Ingest Complaint with PII & .02 Trigger`: Submits complaint with phone/account and `.02` amount (`202 Accepted`).
- Run `02.4 Test Idempotent Duplicate Ingestion`: Re-sends same ticket; verifies database deduplication (`200 OK duplicate: true`).
- Run `02.5 Test Payload Drift Conflict (409)`: Submits same ID with different text; verifies payload drift rejection (`409 Conflict`).

### Step 4: Verification of PII Redaction
- Run `03.1 List Filtered Complaints`: Lists stored complaints.
- Run `03.2 Get Complaint Details`: Verifies raw phone and account numbers are replaced with `[PHONE]` and `[ACCOUNT]`.

### Step 5: XtraDot Signed Payment Webhooks
- Run `05.1 Send Signed Transfer Webhook`: Automatically signs payload and delivers `.02` switch timeout event (`202 Accepted`).
- Run `05.2 Test Invalid Webhook Signature Rejection`: Verifies tampered signatures are rejected (`401 Unauthorized`).

### Step 6: Incident Detection & Grounded MaaS Investigation
- Run `06.1 Detect Spikes (15-min MAD)`: Detects complaint spike and creates an Incident.
- Run `06.2 List Incidents`: Fetches active incidents and sets `{{incident_id}}`.
- Run `06.4 Trigger Grounded MaaS Investigation`: Dispatches an asynchronous MaaS investigation brief.
- Run `06.3 Unified Incident Overview`: Reads back the single overview payload containing facts, hypotheses, missing evidence, and recommended checks.

### Step 7: Corrective Action Governance
- Run `07.1 Propose Corrective Action`: Proposes remediation plan in `proposed` state, saves `{{ca_id}}`.
- Run `07.2 Advance to In Progress`: Transitions state to `in_progress`.
- Run `07.3 Attempt Verify Without Evidence`: Confirms tamper-proof rule rejecting verification without evidence (`400 Bad Request`).
- Run `07.4 Verify With Evidence as Bank Admin`: Successfully validates and closes action (`200 OK verified`).

### Step 8: Machine API Automation
- Run `01.2 Provision Machine API Key`: Generates `cfx_api_...` key.
- Run `01.4 Test Machine Key Dual-Auth`: Proves machine key authenticates against protected endpoints.
- Run `01.5 Revoke Machine API Key`: Confirms immediate key revocation.

