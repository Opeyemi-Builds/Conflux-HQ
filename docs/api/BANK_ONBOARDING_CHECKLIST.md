# Bank Enterprise Integration & Go-Live Checklist

## Phase 1: Authentication & Provisioning
- [ ] Sign in to Console (`/login`) with designated Bank Administrator credentials.
- [ ] Navigate to **API Keys** (`/dashboard/settings/keys`).
- [ ] Generate production Machine Key with `read` (and optionally `operate`) scopes.
- [ ] Securely store the returned `cfx_api_` secret in your enterprise HashiCorp Vault or AWS Secrets Manager.

## Phase 2: Signal Ingestion & Poller Configuration
- [ ] Configure bank's internal poller service using `scripts/poll_machine_updates.py`.
- [ ] Set polling interval to 5 seconds (`GET /api/v1/machine/updates?collections=complaints,incidents&limit=50`).
- [ ] Ensure local cursor persistence across worker restarts to avoid replay gaps.
- [ ] Handle `truncated: true` flag for immediate burst pagination.

## Phase 3: Ingestion & Webhook Intakes
- [ ] Register customer care intake endpoints to forward tickets to `POST /api/v1/complaints`.
- [ ] Configure payment switch webhooks to forward raw delivery notifications to `POST /api/v1/forge/webhooks`.
- [ ] Verify HMAC-SHA256 signature calculation using your assigned gateway key.

## Phase 4: NOC & Operations Alignment
- [ ] Link ConfluxHQ priority incidents directly to your internal PagerDuty or Jira incident response flow.
- [ ] Train support team leads on human-in-the-loop draft reviews and reversal sign-offs.
