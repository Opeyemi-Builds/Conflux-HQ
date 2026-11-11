# Machine API Key Security & Lifecycle Management

## Key Format

All machine API keys follow the format:
```
cfx_api_<32_random_urlsafe_bytes>
```
Example: `cfx_api_live_k8s_poller_9a12e84bc9123847aef92`

## Key Properties

- **Never Stored in Plaintext**: ConfluxHQ computes a SHA-256 hash of the token immediately upon issuance. Only the hash and key prefix (`cfx_api_••••••••`) are persisted in the PostgreSQL database.
- **One-Time Secret Reveal**: The raw token is returned exactly once during the `POST /api/v1/api-keys` response. If lost, the key must be revoked and regenerated.
- **Immediate Invalidation**: Revoking a key via `POST /api/v1/api-keys/{id}/revoke` marks the key status as `revoked` and rejects subsequent bearer calls with HTTP 401 Unauthorized within 0ms.

## Scope Definitions

| Scope | Allowed Operations |
|---|---|
| `read` (Default, Required) | Pulls `/machine/updates`, `/machine/summary`, `/machine/incidents`, `/machine/complaints`, and `/machine/health/connectors`. |
| `operate` (Optional) | Triggers automated incident investigations (`POST /machine/investigations`) and drains asynchronous background workers (`POST /machine/jobs/drain`). |

## Tenant Isolation

Machine keys are strictly bound to the issuing Bank Tenant. A bearer key generated for Zymic Bank can never read, modify, or receive complaints belonging to another financial institution.
