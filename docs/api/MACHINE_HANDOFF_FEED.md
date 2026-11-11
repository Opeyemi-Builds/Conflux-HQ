# ConfluxHQ Machine Handoff Feed Specification

## Overview

The ConfluxHQ Machine Handoff Feed allows partner banks to stream real-time operational intelligence (customer complaints, incident spikes, investigation drafts, and audit events) directly into their internal dashboards, SIEMs, or NOC monitors without relying on webhooks or UI access.

## Endpoint

```http
GET /api/v1/machine/updates
```

### Authentication

- Header: `Authorization: Bearer cfx_api_<secret>`
- Required Scope: `read`

### Query Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `since` | ISO 8601 UTC string | `null` | Lower timestamp bound for incremental polling. Omit on initial poll. |
| `collections` | comma-separated string | `complaints,incidents` | Filter by collection: `complaints`, `incidents`, `drafts`, `actions`, `investigations`, `audit`. |
| `limit` | integer (1–100) | `20` | Maximum items to return in a single batch. |

### Response Schema

```json
{
  "bank_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "since": "2026-11-11T01:30:00.000000Z",
  "cursor": "2026-11-11T01:35:12.451829Z",
  "count": 4,
  "truncated": false,
  "collections": ["complaints", "incidents"],
  "poll_interval_seconds": 5,
  "items": [
    {
      "collection": "incidents",
      "id": "e8a946b2-6c3e-4b21-9a74-d4b93198f26a",
      "updated_at": "2026-11-11T01:35:12.451829Z",
      "data": {
        "id": "e8a946b2-6c3e-4b21-9a74-d4b93198f26a",
        "title": "NIBSS Instant Payment Timeout Surge",
        "issue_type": "failed_transfer",
        "status": "investigating",
        "priority": 88,
        "complaint_count": 142
      }
    }
  ]
}
```

## Recommended Polling Loop

1. Initialize `cursor = null`.
2. Every 5 seconds, execute:
   `GET /api/v1/machine/updates?since=${cursor}&collections=complaints,incidents&limit=50`
3. Process returned `items`.
4. Update `cursor = response.cursor`.
5. If `response.truncated === true`, poll immediately without waiting 5 seconds to catch up.
