# Incident Detection & Human-in-the-Loop Guardrail Lifecycle

## 1. Detection Phase

Complaints are continuously indexed into rolling 1-hour buckets segmented by `issue_type` and `channel`.
When an issue category volume exceeds the trailing median plus 3 Median Absolute Deviations (MAD):
```
threshold = median(hourly_counts) + 3 * MAD(hourly_counts)
```
A priority incident is flagged with an impact score calculated as:
```
priority = min(100, volume_score * growth_multiplier)
```

## 2. Investigation Phase

Bank operators or machine workers trigger automated root cause correlation:
```http
POST /api/v1/ai/incidents/{incident_id}/investigate
```
The investigation engine analyzes:
- Internal switch transaction failure rates (Interswitch, NIBSS, Unified Payments).
- System event timestamps (deployments, network drops, latency spikes).
- Social sentiment velocity on X / Twitter.

## 3. Human Guardrail Decision Phase

Remediation proposals are generated as structured drafts:
- `customer_message`: Holding communications tailored to Nigerian banking customers.
- `it_ticket`: Formatted infrastructure tickets with correlation IDs.
- `reversal_request`: Batch financial reversal candidates.

### Financial Guardrail Protection
Reversal requests cannot be executed autonomously by machines. They enforce human review (`POST /api/v1/ai/drafts/{id}/decision`) and immutable audit trails via `GET /api/v1/ai/incidents/{id}/audit`.
