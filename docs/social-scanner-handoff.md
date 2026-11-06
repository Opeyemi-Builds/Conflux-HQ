# Social scanner integration contract

Written for the teammate implementing X collection. The scanner collects permitted posts using official platform APIs; the backend does not scrape or run a polling worker.

## Setup

Run backend migrations (`python -m alembic upgrade head` from backend). Configure `DATABASE_URL` and a random `SOCIAL_ADAPTER_TOKEN` of at least 32 characters in the backend environment. Give the scanner the same token and API base URL. This token grants service-wide monitoring-rule access and ingestion: keep it server-side, out of browser bundles, logs and source control. It is not a bank login token or Supabase service-role key. Empty/unconfigured credentials return 503; incorrect credentials return 401. Use HTTPS outside local development.

The social routes are mounted in both demo and non-demo modes. Non-demo bank login uses the existing Supabase Auth flow. Platform credentials, search permissions, cursors, polling intervals, rate limits and retries belong to the scanner.

## Discover monitored banks

`GET /api/v1/social/monitoring-rules?limit=100&offset=0`

Header: `Authorization: Bearer <SOCIAL_ADAPTER_TOKEN>`

Response contains `items` with `bank_id`, `bank_name` and `aliases` (`value`, `kind`, `platform`). Follow `next_offset` until null. Refresh periodically so newly registered banks and alias edits are picked up. Only active banks are returned. Every registered bank's full name is included immediately; admins configure handles/hashtags/abbreviations through `PUT /api/v1/social/aliases` using their bank login token. GET on that same path lists the bank's aliases.

Example admin configuration:

```json
{"aliases":[
  {"value":"Access Bank","kind":"name"},
  {"value":"@accessbankplc","kind":"handle","platform":"x"},
  {"value":"#AccessBank","kind":"hashtag","platform":"x"},
  {"value":"Access","kind":"contextual"}
]}
```

Alias replacement is complete replacement, not append. For UBA configure the full name, `UBA`, relevant handles and hashtags. Handles must be confirmed by the bank; the backend does not verify ownership. A generic contextual alias uses banking-keyword checks, not semantic AI. Prefer precise handles/full names to minimize false positives.

## Deliver collected posts

`POST /api/v1/social/events`

Header: `Authorization: Bearer <SOCIAL_ADAPTER_TOKEN>`

```json
{
  "platform":"x",
  "post_id":"1234567890123456789",
  "text":"@accessbankplc my transfer failed but I was debited",
  "occurred_at":"2026-11-06T10:12:00Z",
  "source_url":"https://x.com/customer/status/1234567890123456789",
  "author_ref":"platform-scoped-author-id",
  "region":null,
  "synthetic":false
}
```

Use the platform's stable post ID and original timezone-aware timestamp. `source_url`, `author_ref` and `region` are optional. URLs must be HTTPS X/Twitter/Instagram/Facebook permalinks without query strings, fragments or embedded credentials. Text limit is 5,000 characters. Accepted platforms currently are `x`, `instagram`, `facebook`; do not send unsupported platforms. Synthetic fixtures must explicitly set `synthetic=true`.

The backend determines the bank itself: don't pass arbitrary bank IDs. Matching one active bank persists a PII-masked complaint, hashed author reference, source receipt and audit entry. The keyword classifier runs synchronously and is explicitly labelled `demo_rules_v1`; unclear content stays unclassified. This is not AI classification, sentiment inference or proof of financial loss.

## Responses and retries

- 202 + `accepted=true, duplicate=false`: complaint stored; use returned `complaint_id`.
- 202 + `accepted=true, duplicate=true`: already received for that bank/platform/post ID. Stop retrying. Existing content is not overwritten, so edited posts do not update previous complaints.
- 202 + `accepted=false, reason=no_bank_match`: no match. Not persisted; do not endlessly retry. You may reconsider after monitoring rules change.
- 202 + `accepted=false, reason=ambiguous_bank_match`: multiple banks matched. Not persisted; scanner should keep its own review/dead-letter record. The backend does not currently persist an ambiguity queue.
- 422: invalid payload. Fix or dead-letter; do not blindly retry.
- 401/503: check service credentials/configuration.
- 409: persistence conflict not resolved as a duplicate; investigate before retrying.
- Network errors/5xx: retry with exponential backoff and the same post ID. Do not advance the collection cursor until delivery is acknowledged or durably queued in the scanner.

Deduplication is bank/platform/post ID scoped and database-enforced. No batch endpoint is provided; deliver one event per request with bounded concurrency.

## Downstream consumers

Bank staff use their own bank bearer token, not the adapter token, to read `/complaints`, `/analytics/summary`, `/analytics/trends`, `/analytics/breakdown` and `/incidents`. Fraud flags appear through `/complaints?is_fraud=true`. The scanner token cannot authenticate as bank staff.

Spike detection is not scheduled automatically. An authenticated bank operator calls `POST /api/v1/incidents/detect`; a future worker must manage its own operator authorization or use a dedicated service integration. Investigation, AI classification and approval execution are separate unfinished work. Dashboard data is still mocked until frontend API integration lands.
