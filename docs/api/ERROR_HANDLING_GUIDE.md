# ConfluxHQ API Error Handling & Status Codes

## Error Response Envelope

All API errors return RFC 7807 problem details in standard JSON:

```json
{
  "detail": "Descriptive message identifying the cause of failure",
  "status_code": 401,
  "error_code": "INVALID_MACHINE_KEY"
}
```

## Standard HTTP Status Codes

| Code | Meaning | Cause | Action |
|---|---|---|---|
| `401 Unauthorized` | Invalid or revoked key | Missing `Authorization` header or revoked `cfx_api_` key | Refresh or regenerate token in `/dashboard/settings/keys` |
| `403 Forbidden` | Insufficient scope | Attempted write operation using `read`-only key | Generate key with `operate` scope |
| `409 Conflict` | Duplicate resource | Complaint with identical external ID or idempotency key exists | Safely ignore (idempotent duplicate) |
| `422 Unprocessable` | Schema validation error | Missing required fields or invalid types | Check request body against API specification |
| `503 Service Unavailable` | Backpressure / maintenance | Rate limiter engaged or background worker busy | Implement exponential backoff (e.g. retry after 5s, 10s, 20s) |
