# Provider Webhook Ingestion & Signature Verification

## Intake Protocol

ConfluxHQ receives real-time customer complaints and provider events via:

```http
POST /api/v1/forge/webhooks
```

## Security Headers

Every webhook payload transmitted by Forge infrastructure contains three security headers:

1. `x-forge-event`: Event identifier (e.g. `complaint.ingested`, `social.mention`, `system.alert`).
2. `x-forge-timestamp`: Unix epoch seconds timestamp when the webhook was generated.
3. `x-forge-signature`: Hexadecimal HMAC-SHA256 digest of `${timestamp}.${raw_body}` using your shared webhook secret.

## Python Verification Implementation

```python
import hmac
import hashlib
import time

def verify_forge_signature(raw_body: bytes, signature_header: str, timestamp_header: str, secret: str) -> bool:
    # Reject replay attacks older than 5 minutes (300 seconds)
    now = int(time.time())
    ts = int(timestamp_header)
    if abs(now - ts) > 300:
        return False
    
    # Compute signature
    signed_payload = f"{ts}.".encode("utf-8") + raw_body
    computed = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    
    return hmac.compare_digest(computed, signature_header)
```
