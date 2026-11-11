# ConfluxHQ v1.0 Production Platform Release Notes

## Release Summary

ConfluxHQ v1.0 establishes an API-first complaint intelligence and real-time operational spike platform for commercial banks and payment infrastructure providers.

## Key Deliverables

1. **Stripe-Grade Developer Portal (`/developers`)**:
   - Public interactive documentation with Quickstart, Auth, 5s Polling Feed, Ingestion, and Webhook guides.
   - Live "Try It" API sandbox supporting scoped `cfx_api_` tokens.
   - Code snippet tabs in cURL, Python, and JavaScript with copy utilities.
   - Keyboard-accessible `⌘K` search modal.
   - Proxied `/docs` (FastAPI Swagger UI) and `/openapi.json` schemas.

2. **Machine API Key Manager (`/dashboard/settings/keys`)**:
   - Admin-restricted generation of `cfx_api_` bearer tokens with `read` and `operate` scopes.
   - Zero-plaintext security: only SHA-256 hashes stored in database.
   - One-time raw secret token reveal banner with warning and copy-to-clipboard.
   - Idempotent key revocation with immediate invalidation.

3. **Real-Time Machine Handoff Feed (`/dashboard` & API)**:
   - 5-second polling ticker on Overview consuming `GET /api/v1/machine/updates`.
   - Cursor-based state synchronization with `truncated: true` catch-up pagination.
   - Live pause/resume controls and key provisioning shortcuts.

4. **Incident Queue & Spike Detection (`/dashboard/incidents`)**:
   - Dedicated incident queue ranked by deterministic priority (`volume × growth`).
   - One-click synthetic demo seeding and spike detection.
   - Incident Audit Trail (`GET /api/v1/ai/incidents/{id}/audit`) on detail view.

5. **Design System & Brand Alignment**:
   - Unified cream (`#f0f1eb`), navy (`#14233f`), and flux orange (`#e8651a`) across all views.
   - Integrated `/conflux-logo-full.jpg` brand asset in header, navbar, and sidebar.
   - Live `/api/v1/health` status badge in dashboard header.
