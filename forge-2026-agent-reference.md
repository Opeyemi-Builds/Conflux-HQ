# Forge 2026 Sandbox — Agent Reference

> Source: **Access · Youth Tech Forge — Sandbox Participant Platform Guide**, version 1.0, dated 9 Nov 2026.
>
> This is a structured extraction for AI agents and developers. The guide explicitly says the authoritative bank API contract is the separate **Sandbox API Mock Specification v2**. That specification was not included in the supplied PDF. Consequently, DTOs below are exact where the guide provides fields and deliberately marked partial/unknown where it does not. Do not infer missing schemas as if they were confirmed API contracts.

## 1. Agent quick summary

The Forge 2026 sandbox gives each team an isolated Kubernetes namespace, a public app URL, and internal access to two platform APIs:

- **Xtradot Bank sandbox**: simulated Nigerian banking API. It supports reference data, transfers, accounts, wallets, collections, settlements, virtual accounts, identity, open banking, lending, carbon registry, webhooks, and team-admin operations.
- **Huawei MaaS**: OpenAI-compatible model inference endpoint.

All platform API calls must originate from a workload in the team's namespace. The bank API uses `x-api-key`; Huawei MaaS uses `apikey`. The same team key is provisioned as the `GATEWAY_KEY` field in the `huawei-gateway` Kubernetes secret.

The bank data is synthetic and isolated per team. Never use real personal or payment data. Bank sandbox state is volatile and may reset after a platform restart.

## 2. Runtime and service endpoints

| Service | Base URL | Reachability | Purpose |
|---|---|---|---|
| Team app | `https://teamXX.xtradot.co` | Public internet | Published app; gateway routes to Service `app` on port 80 |
| Xtradot Bank | `http://bank-api.ingress-apisix.svc.cluster.local/v1` | Team namespaces only | Bank sandbox API |
| Huawei MaaS | `http://huawei-maas.ingress-apisix.svc.cluster.local/openai/v1` | Team namespaces only | OpenAI-compatible inference |
| Hosted checkout | `https://pay.xtradot.co/pay/<token>` | Public internet | Hosted payment page returned by bank API |
| Internal app address | `http://app.teamXX.svc.cluster.local` | Cluster | Webhook destination / internal app address |

Platform facts:

- Nodes use `linux/amd64`.
- TLS terminates at Cloudflare and the gateway; the app serves plain HTTP inside the cluster.
- `LoadBalancer` and `NodePort` Services are blocked by quota.
- Team namespaces are isolated from one another at the network layer.
- Exactly one Service per team is published publicly: Service name `app`, port `80` (any `targetPort`).

## 3. Authentication and request conventions

### 3.1 Xtradot Bank

```http
x-api-key: <team-key>
Content-Type: application/json
```

Base URL:

```text
http://bank-api.ingress-apisix.svc.cluster.local/v1
```

### 3.2 Huawei MaaS

```http
apikey: <team-key>
```

Base URL:

```text
http://huawei-maas.ingress-apisix.svc.cluster.local/openai/v1
```

For OpenAI SDK configuration, the SDK `apiKey` field can be any placeholder (for example `unused`); supply the real team key through the `apikey` default header.

### 3.3 Shared bank API conventions

| Concern | Contract |
|---|---|
| Amounts | NGN, two decimal places |
| Timestamps | ISO 8601 UTC (`Z`) |
| Pagination | `?page=1&per_page=20`; maximum `per_page` is 100; list responses include `meta` |
| Rate limit | 60 requests/minute/team, shared between Bank API and Huawei MaaS |
| Rate-limit response | HTTP `429` |
| Idempotency | `Idempotency-Key: <uuid>` required on every POST that moves money or creates a record |
| Repeated idempotent request | Same key + same body replays original response and returns `Idempotent-Replayed: true` |
| Idempotency conflict | Same key + different body returns HTTP `409` |
| Forced test outcome | Optional `x-test-outcome: successful | failed | pending | timeout | reversed` |

### 3.4 Idempotency guidance for agents

- Generate and persist a unique idempotency key for each money-moving or record-creating POST.
- For a retry of the *same logical operation*, reuse the same key and identical body.
- Never reuse a key with a changed body.
- A `504 TIMEOUT` means the outcome is unknown. **Never resend the transfer.** Query its status with `GET /transfers/{reference}` or `POST /transfers/interbank/requery` until final.

## 4. Response DTOs

### 4.1 Success envelope

The guide documents this common success shape:

```json
{
  "status": "success",
  "message": "...",
  "data": {},
  "meta": null,
  "request_id": "req_7f3a9c21"
}
```

TypeScript DTO:

```ts
export interface ApiSuccess<TData> {
  status: "success";
  message: string;
  data: TData;
  meta: Record<string, unknown> | null;
  request_id: string;
}
```

`meta` is shown as `null` in the example; list endpoints are documented as returning pagination metadata, but its exact schema is not supplied.

### 4.2 Error envelope

The guide documents this error shape:

```json
{
  "status": "error",
  "error": {
    "code": "INVALID_REQUEST",
    "message": "...",
    "field": "amount"
  },
  "request_id": "req_7f3a9c22"
}
```

TypeScript DTO:

```ts
export interface ApiError {
  status: "error";
  error: {
    code: string;
    message: string;
    field?: string;
  };
  request_id: string;
}

export type ApiResponse<TData> = ApiSuccess<TData> | ApiError;
```

The guide warns that the gateway may return its own short `401` body, so do not assume every authentication failure uses the standard envelope.

### 4.3 Transfer response fields explicitly guaranteed

Every transfer response returns these charge fields:

```ts
export interface TransferCharges {
  fee: number;
  vat: number;
  stamp_duty: number;
  total_debit: number;
}
```

The complete transfer response DTO is **not** specified in this guide. Treat the above as a guaranteed field fragment, not a complete response model.

## 5. Request DTOs explicitly supported by the guide

### 5.1 Interbank name enquiry

Endpoint: `POST /transfers/interbank/name-enquiry`

Request example:

```json
{
  "destination_bank_code": "000013",
  "account_number": "0123987001"
}
```

DTO:

```ts
export interface InterbankNameEnquiryRequest {
  destination_bank_code: string;
  account_number: string;
}
```

The guide does not provide the full name-enquiry response schema. It does establish that the transfer flow uses a returned `name_enquiry_ref` and that the resolved account name must be displayed to the user before submitting the transfer.

### 5.2 Interbank transfer

Endpoint: `POST /transfers/interbank`

Request example:

```json
{
  "source_account": "0123456790",
  "destination_bank_code": "000013",
  "destination_account": "0123987001",
  "name_enquiry_ref": "<ref>",
  "amount": 75000.00,
  "narration": "Generator repairs",
  "reference": "TRF-0002"
}
```

DTO:

```ts
export interface InterbankTransferRequest {
  source_account: string;
  destination_bank_code: string;
  destination_account: string;
  name_enquiry_ref: string;
  amount: number;
  narration: string;
  reference: string;
}
```

The guide requires `Idempotency-Key` on this money-moving POST. Interbank transfers return HTTP `202` with a pending state and typically settle in about five seconds.

### 5.3 Webhook registration

Endpoint: `POST /webhooks`

Request example:

```json
{
  "url": "http://app.teamXX.svc.cluster.local/hooks/forge",
  "events": ["*"]
}
```

DTO:

```ts
export interface WebhookRegistrationRequest {
  url: string;
  events: string[];
}
```

The registration response returns `webhook_secret` once. The guide does not provide the full registration response schema. Store the secret securely when received.

## 6. Transfers: agent workflow and business rules

### 6.1 Required transfer sequence

1. Call the matching name-enquiry endpoint.
2. Read the resolved beneficiary name and `name_enquiry_ref` from the response.
3. Display the resolved name to the user and obtain confirmation before sending.
4. Submit the transfer with the returned reference and a new idempotency key.
5. For interbank transfers, expect an asynchronous pending result; poll/requery until final.
6. Use the returned `fee`, `vat`, `stamp_duty`, and `total_debit`; never hard-code charges.

### 6.2 Intra-bank vs interbank

| Type | Enquiry endpoint | Transfer endpoint | Behaviour |
|---|---|---|---|
| Intrabank (Xtradot to Xtradot) | `POST /transfers/intra/name-enquiry` | `POST /transfers/intra` | Completes in the call with HTTP `201`; no transfer fee |
| Interbank (NIP) | `POST /transfers/interbank/name-enquiry` | `POST /transfers/interbank` | Returns HTTP `202` pending; settles in about 5 seconds |

### 6.3 Enquiry constraints

- `name_enquiry_ref` is single-use.
- It expires after 10 minutes.
- The destination must match the enquiry.
- Intrabank and NIP/interbank enquiry references are not interchangeable.
- Dormant and frozen beneficiaries fail at enquiry.
- PND source accounts cannot send.
- Source account is debited by amount plus charges.

### 6.4 KYC transfer limits

| Account tier | Single-transfer limit | Daily limit |
|---|---:|---:|
| Tier 1 | ₦50,000 | ₦300,000 |
| Tier 2 | ₦100,000 | ₦500,000 |
| Tier 3 | ₦5,000,000 | ₦25,000,000 |
| Corporate | ₦10,000,000 | ₦100,000,000 |

### 6.5 Transfer charges

The active tariff is available from `GET /tariff`. The guide says the initial sandbox schedule uses NIP fees of ₦10 / ₦25 / ₦50 by band, plus 7.5% VAT. The platform may switch to the CBN 2026 schedule for demo day:

- ₦0 up to ₦5,000
- ₦10 up to ₦50,000
- ₦50 above ₦50,000
- VAT applies
- ₦50 stamp duty on any transfer of ₦10,000 or more

These are operational notes, not a substitute for the live tariff response. Always use the returned charge fields.

## 7. Bank API endpoint catalogue and brief summaries

> The guide supplies paths and HTTP methods for this catalogue, but does **not** supply complete request/response field schemas for most endpoints. The summaries below describe the documented purpose implied by each endpoint name and section. DTOs for these operations must be sourced from Sandbox API Mock Specification v2 before strict typed integration.

### 7.1 Reference data

| Method | Path | Brief summary | DTO status |
|---|---|---|---|
| GET | `/banks` | List supported banks and their reference data. | Response schema not supplied |
| GET | `/banks/{nip_code}/availability` | Check availability of a bank identified by NIP code. | Path param known; response schema not supplied |
| GET | `/tariff` | Retrieve the active fee/tariff schedule. | Response schema not supplied; use this rather than hard-coding fees |

### 7.2 Transfers

| Method | Path | Brief summary | DTO status |
|---|---|---|---|
| POST | `/transfers/intra/name-enquiry` | Resolve an Xtradot Bank beneficiary before an intrabank transfer. | Request/response schema not supplied; analogous interbank request must not be assumed identical without spec |
| POST | `/transfers/intra` | Submit an intrabank transfer using its enquiry reference. | Request/response schema not supplied |
| POST | `/transfers/interbank/name-enquiry` | Resolve a NIP beneficiary. | Request DTO documented in §5.1; response schema partial/unknown |
| POST | `/transfers/interbank` | Submit an interbank transfer. | Request DTO documented in §5.2; response schema partial/unknown |
| GET | `/transfers/{reference}` | Retrieve transfer status by client/reference identifier; use to resolve uncertain outcomes. | Path param known; response schema not supplied |
| POST | `/transfers/interbank/requery` | Requery an interbank transfer after an uncertain result. | Request/response schema not supplied |
| POST | `/transfers/bulk` | Submit a bulk transfer batch. | Request/response schema not supplied |
| GET | `/transfers/bulk/{batch_reference}` | Retrieve bulk batch status/result. | Path param known; response schema not supplied |

### 7.3 Accounts and transactions

| Method | Path | Brief summary | DTO status |
|---|---|---|---|
| GET | `/accounts/{account_number}/balance` | Retrieve an account balance. | Path param known; response schema not supplied |
| GET | `/accounts/resolve` | Resolve account details. | Query/request schema not supplied |
| GET | `/transactions` | List transactions; pagination conventions apply. | Query filters and item schema not supplied |
| GET | `/transactions/{reference}` | Retrieve a transaction by reference. | Path param known; response schema not supplied |

### 7.4 Wallets

| Method | Path | Brief summary | DTO status |
|---|---|---|---|
| POST | `/wallets` | Create a wallet. | Request/response schema not supplied |
| GET | `/wallets/{wallet_id}` | Retrieve wallet details. | Path param known; response schema not supplied |
| POST | `/wallets/{wallet_id}/fund` | Fund a wallet. | Request/response schema not supplied |
| POST | `/wallets/transfer` | Transfer value between wallets. | Request/response schema not supplied |

### 7.5 Collections and POS

| Method | Path | Brief summary | DTO status |
|---|---|---|---|
| POST | `/payments/checkout` | Create a hosted checkout/payment session. | Request/response schema not supplied; response includes `payment_url` according to guide |
| POST | `/payments/{reference}/card` | Submit card details/payment step for a checkout. | Request/response schema not supplied |
| POST | `/payments/{reference}/otp` | Submit OTP for a checkout. | Request/response schema not supplied |
| POST | `/payments/{reference}/simulate-transfer` | Simulate a bank-transfer payment. | Request/response schema not supplied |
| POST | `/payments/{reference}/simulate-ussd` | Simulate a USSD payment. | Request/response schema not supplied |
| POST | `/payments/{reference}/simulate-qr` | Simulate a QR payment. | Request/response schema not supplied |
| GET | `/payments/{reference}/verify` | Verify final payment status. Must be called before giving value. | Path param known; response schema not supplied |
| POST | `/pos/transactions` | Create/simulate a POS transaction. | Request/response schema not supplied |

Collections rules:

- `payment_url` opens a public hosted checkout at `pay.xtradot.co`.
- Checkout redirects to the supplied `callback_url` with `reference` and `status`.
- Do not trust the redirect alone; always call `GET /payments/{reference}/verify` before fulfilling an order.
- Merchant fees: card and POS 1.5%, capped at ₦2,000; transfer, USSD, and QR ₦50 flat.

### 7.6 Settlements and reconciliation

| Method | Path | Brief summary | DTO status |
|---|---|---|---|
| GET | `/settlements` | List/retrieve settlement records. | Query and response schema not supplied |
| POST | `/reconciliation` | Run or submit a reconciliation operation. | Request/response schema not supplied |

### 7.7 Virtual accounts

| Method | Path | Brief summary | DTO status |
|---|---|---|---|
| POST | `/virtual-accounts` | Create a virtual account. | Request/response schema not supplied |
| GET | `/virtual-accounts/{account_number}` | Retrieve a virtual account. | Path param known; response schema not supplied |
| POST | `/virtual-accounts/{account_number}/simulate-inflow` | Simulate an inflow/credit to a virtual account. | Request/response schema not supplied |

### 7.8 Identity

| Method | Path | Brief summary | DTO status |
|---|---|---|---|
| POST | `/identity/bvn/verify` | Verify a BVN against sandbox fixtures. | Request/response schema not supplied |
| POST | `/identity/nin/verify` | Verify a NIN against sandbox fixtures. | Request/response schema not supplied |

### 7.9 Open banking

| Method | Path | Brief summary | DTO status |
|---|---|---|---|
| POST | `/open-banking/consents` | Create an open-banking consent. | Request/response schema not supplied |
| POST | `/open-banking/consents/{id}/authorise` | Authorise a consent. | Path param known; body/response schema not supplied |
| GET | `/open-banking/consents/{id}` | Retrieve a consent. | Path param known; response schema not supplied |
| DELETE | `/open-banking/consents/{id}` | Revoke/delete a consent. | Path param known; response schema not supplied |
| GET | `/open-banking/accounts/{account_number}` | Retrieve account information through open banking. | Path param known; reads require `consent_id` |
| GET | `/open-banking/accounts/{account_number}/balance` | Retrieve balance through open banking. | Path param known; reads require `consent_id` |
| GET | `/open-banking/accounts/{account_number}/statement` | Retrieve statement through open banking. | Path param known; reads require `consent_id` |

All open-banking account reads take `?consent_id=...`. Missing active scope consent produces `CONSENT_REQUIRED` / HTTP `403`.

### 7.10 Lending

| Method | Path | Brief summary | DTO status |
|---|---|---|---|
| POST | `/loans/applications` | Submit a loan application. | Request/response schema not supplied |
| GET | `/loans/{loan_id}` | Retrieve loan details/status. | Path param known; response schema not supplied |
| POST | `/loans/{loan_id}/accept` | Accept a loan offer. | Path param known; body/response schema not supplied |
| POST | `/loans/{loan_id}/disburse` | Disburse an accepted loan. | Path param known; body/response schema not supplied |
| POST | `/loans/{loan_id}/repayments` | Submit/record a loan repayment. | Path param known; body/response schema not supplied |

### 7.11 Carbon registry

| Method | Path | Brief summary | DTO status |
|---|---|---|---|
| POST | `/carbon/projects` | Register/create a carbon project. | Request/response schema not supplied |
| GET | `/carbon/projects/{id}` | Retrieve a carbon project. | Path param known; response schema not supplied |
| POST | `/carbon/projects/{id}/mrv` | Submit monitoring, reporting, and verification (MRV) data. | Request/response schema not supplied |
| GET | `/carbon/mrv/{id}` | Retrieve an MRV submission. | Path param known; response schema not supplied |
| POST | `/carbon/mrv/{id}/review` | Review an MRV submission. | Request/response schema not supplied |
| POST | `/carbon/credits/retire` | Retire carbon credits. | Request/response schema not supplied |
| GET | `/carbon/certificates/{id}` | Retrieve a carbon certificate. | Path param known; response schema not supplied |

### 7.12 Webhooks

| Method | Path | Brief summary | DTO status |
|---|---|---|---|
| POST | `/webhooks` | Register a webhook URL and event subscriptions. | Request DTO documented in §5.3; response schema partial/unknown; `webhook_secret` returned once |
| GET | `/webhooks` | List registered webhooks. | Response schema not supplied |
| DELETE | `/webhooks/{id}` | Delete a webhook registration. | Path param known; response schema not supplied |
| POST | `/webhooks/test` | Trigger a test webhook delivery. | Request/response schema not supplied |
| GET | `/webhooks/deliveries` | List webhook delivery attempts. | Query/response schema not supplied |
| POST | `/webhooks/deliveries/{event_id}/replay` | Replay a webhook delivery. | Path param known; request/response schema not supplied |

### 7.13 Team administration

| Method | Path | Brief summary | DTO status |
|---|---|---|---|
| POST | `/admin/reset` | Restore this team's opening sandbox state. Does not affect other teams. | Request/response schema not supplied |
| POST | `/admin/accounts/{n}/fund` | Fund a team account fixture. | Path param known; body/response schema not supplied |
| POST | `/admin/accounts/{n}/status` | Change an account fixture's status. | Path param known; body/response schema not supplied |
| POST | `/admin/banks/{nip_code}/status` | Change a bank fixture's status. | Path param known; body/response schema not supplied |
| POST | `/admin/settlements/run` | Trigger settlement processing. | Request/response schema not supplied |
| POST | `/admin/loans/{id}/advance-to-due` | Advance a loan fixture to its due state. | Path param known; body/response schema not supplied |

### 7.14 Explicitly unimplemented services

The guide states these return `404 NOT_FOUND` in the sandbox build:

- Merchant onboarding
- KYC tiering
- Mandates
- Split and escrow
- Refunds and disputes
- Cards (as optional service; note that the documented checkout flow has a card payment step)
- Cross-border
- Bills
- Risk

Do not build an agent workflow that assumes these optional services are available.

## 8. Webhook contract

### 8.1 Registration

Register either an HTTPS public URL or an internal service URL such as:

```text
http://app.teamXX.svc.cluster.local/hooks/forge
```

The `webhook_secret` is returned once during registration.

### 8.2 Delivery headers and signature

Each delivery includes:

- `x-forge-event`
- `x-forge-timestamp`
- `x-forge-signature: sha256=<hex>`

The signature is HMAC-SHA256 over the exact byte sequence:

```text
{timestamp}.{raw_body}
```

Verification requirements:

- Reject timestamps more than 5 minutes old (300 seconds drift).
- Verify the HMAC against the raw request body, not a re-serialized JSON object.
- Compare signatures using a constant-time comparison.
- De-duplicate deliveries using `event_id`.
- Respond with a 2xx status within 10 seconds.

Retry schedule after failure: 1 minute, 5 minutes, 15 minutes, 1 hour, and 6 hours.

### 8.3 Event names

```text
transfer.pending
transfer.successful
transfer.failed
transfer.reversed
transfer.bulk.completed
payment.pending
payment.successful
payment.failed
payment.partial
payment.overpaid
virtual_account.credited
settlement.completed
consent.authorised
consent.revoked
loan.disbursed
loan.repayment_received
loan.overdue
loan.closed
carbon.mrv.verified
carbon.mrv.rejected
carbon.credits.retired
webhook.test
```

### 8.4 Webhook event DTO boundary

The guide establishes that `event_id` exists (for de-duplication), and the event name and timestamp are supplied through headers. It does not publish a complete webhook JSON body schema. Use a tolerant envelope until the full specification is available:

```ts
export interface ForgeWebhookHeaders {
  "x-forge-event": string;
  "x-forge-timestamp": string;
  "x-forge-signature": string;
}

// Partial only: event_id is explicitly referenced by the guide.
// Additional fields are intentionally unknown until the full API spec is obtained.
export interface ForgeWebhookPayload {
  event_id: string;
  [key: string]: unknown;
}
```

## 9. Error catalogue

| Error code | HTTP | Meaning / agent action |
|---|---:|---|
| `INVALID_REQUEST` | 400 | Malformed or missing field; `field` identifies the field. Correct request; do not blindly retry. |
| `UNAUTHORIZED` | 401 | Missing/invalid key. Check header name and secret injection. Gateway may return a short non-standard body. |
| `INSUFFICIENT_FUNDS` | 402 | Balance below amount plus charges. Inform user / choose valid funding path; do not retry unchanged. |
| `ACCOUNT_RESTRICTED` | 403 | Source is PND, dormant, or frozen. |
| `CONSENT_REQUIRED` | 403 | No active open-banking consent for requested scope. Obtain/authorise consent. |
| `ACCOUNT_NOT_FOUND` / `NOT_FOUND` | 404 | Unknown account, record, or endpoint. Check identifier and sandbox implementation status. |
| `DUPLICATE_REQUEST` | 409 | Reused key, reference, or enquiry reference. Check prior operation state. |
| `NAME_ENQUIRY_EXPIRED` | 409 | Enquiry older than 10 minutes. Perform a fresh enquiry. |
| `NAME_ENQUIRY_MISMATCH` | 409 | Destination differs from the destination used for enquiry. Re-enquire and verify beneficiary. |
| `ACCOUNT_DORMANT` | 422 | Beneficiary cannot receive. |
| `BENEFICIARY_FROZEN` | 422 | Beneficiary cannot receive. |
| `LIMIT_EXCEEDED` | 422 | KYC transfer/application limit exceeded. |
| `BVN_MISMATCH` | 422 | Identity mismatch. |
| `INVALID_OTP` | 422 | OTP incorrect. |
| `RATE_LIMITED` | 429 | More than 60 combined requests/minute/team. Back off, batch, or cache. |
| `BANK_UNAVAILABLE` | 503 | Beneficiary bank unavailable. |
| `TIMEOUT` | 504 | Outcome unknown. Requery; never resend a transfer. |

## 10. Sandbox fixtures and deterministic test triggers

### 10.1 Team-owned Xtradot accounts

Bank: Xtradot Bank, NIP `000014`, CBN `044`.

| Account | Holder | Type | Tier | Opening balance (NGN) | BVN |
|---|---|---|---:|---:|---|
| `0123456789` | Adaeze Chiamaka Okonkwo | Savings | 3 | 1,500,000.00 | `22200000001` |
| `0123456790` | Babatunde Olumide Adeyemi | Current | 3 | 5,000,000.00 | `22200000002` |
| `0123456791` | Musa Ibrahim Abdullahi | Savings | 2 | 250,000.00 | `22200000003` |
| `0123456792` | Efosa Godwin Osagie | Savings | 1 | 40,000.00 | `22200000004` |
| `0123456793` | Mama Nkechi Provisions Ltd | Corporate | n/a | 12,000,000.00 | n/a |

### 10.2 Beneficiary fixtures

| Account | Holder | Bank (NIP) | State |
|---|---|---|---|
| `0987654321` | Ngozi Adaobi Eze | Xtradot Bank (`000014`) | active |
| `0987654322` | Aisha Hauwa Bello | Xtradot Bank (`000014`) | active |
| `0987654399` | Obinna Kelechi Okafor | Xtradot Bank (`000014`) | dormant |
| `0123987001` | Chukwuemeka Ifeanyi Nwosu | GTBank (`000013`) | active |
| `0123987099` | Garba Sani Danjuma | GTBank (`000013`) | PND |
| `0123987002` | Funmilayo Abiola Ogunleye | Zenith (`000015`) | active |
| `0123987003` | Zainab Halima Yusuf | First Bank (`000016`) | active |
| `0123987004` | Tamunotonye Briggs | UBA (`000004`) | active |
| `0123987098` | Blessing Oghenekaro Edeh | Wema (`000017`) | frozen |
| `8031234506` | Ifeoluwa Grace Adebayo | OPay (`100004`) | active |
| `8051234507` | Iya Bisi Foods Enterprises | Moniepoint (`090405`) | active |
| `0123987005` | Arewa Solar Co-operative Society | Zenith (`000015`) | carbon payouts |
| `0123987006` | Ogoja Community Forest Trust | First Bank (`000016`) | carbon payouts |

### 10.3 Other fixtures

- BVNs `22200000001`–`22200000004` and NINs `70000000001`–`70000000004` match the four individual team account holders.
- Corresponding dates of birth: `1998-04-12`, `1985-09-30`, `1992-01-17`, `2001-06-05`.
- Merchants: `mer_204` Mama Nkechi Provisions; `mer_205` Kano Agro Hub; `mer_206` Ọ̀ṣun Threads; `mer_900` Forge Carbon Registry.
- Wallets: `wal_adaeze_01` (₦20,000), `wal_musa_01` (₦5,000).
- Team accounts have seeded October 2026 history for statements and credit scoring.
- OTP for cards and consents: `123456`.
- Test cards (any future expiry, CVV `123`, PIN `1234`): `5399830000000008` succeeds; `5399830000000016` declines for insufficient funds; `5399830000000024` fails OTP.

### 10.4 Trigger values

| Trigger | Applies to | Expected result |
|---|---|---|
| Account `0000000001` | Name enquiry, bulk | `ACCOUNT_NOT_FOUND` |
| Account `0000000002` | Name enquiry | `TIMEOUT` after 10 seconds |
| Bank code `999999` | Interbank enquiry | `BANK_UNAVAILABLE` |
| Amount ending `.01` | Transfers, card, POS | `INSUFFICIENT_FUNDS` |
| Amount ending `.02` | Transfers | `TIMEOUT`, then failed and reversed after 30 seconds |
| Amount ending `.03` | Transfers | Pending 2 minutes, then successful |
| Amount ending `.04` | Interbank | Successful, then reversed after about 60 seconds |
| Amount ending `.05` | Transfers | First webhook delivery withheld |
| Reference prefix `DUP-` | Transfers, payments | `DUPLICATE_REQUEST` |
| BVN `22299999999` | Identity, loans | No match / declined |
| NIN `70099999999` | Identity | No match |

Amounts ending `.00` do not trigger these deterministic outcomes.

## 11. Huawei MaaS quick reference

Huawei MaaS is OpenAI-compatible.

| Setting | Value |
|---|---|
| Base URL | `http://huawei-maas.ingress-apisix.svc.cluster.local/openai/v1` |
| SDK API key | Any placeholder, e.g. `unused` |
| Auth header | `apikey: <team-key>` |
| Models | `glm-5.3`, `glm-5.2`, `glm-5.1`, `deepseek-v4.1-flash-1017`, `deepseek-v4.1-flash`, `deepseek-v4-flash` |
| Gateway timeout | 120 seconds |

Model availability depends on what Huawei has enabled. If a model returns not found, try another listed model.

Example JavaScript setup:

```ts
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://huawei-maas.ingress-apisix.svc.cluster.local/openai/v1",
  apiKey: "unused",
  defaultHeaders: { apikey: process.env.GATEWAY_KEY! },
});
```

Example call:

```ts
const response = await client.chat.completions.create({
  model: "glm-5.2",
  messages: [
    {
      role: "user",
      content: "Classify this transaction narration: 'POS SALE - KANO AGRO HUB'",
    },
  ],
  extra_body: { chat_template_kwargs: { thinking: false } },
});
```

Usage guidance:

- Disable reasoning with `chat_template_kwargs: { thinking: false }` unless needed. The guide reports a one-line reply used 137 tokens with reasoning and 18 without in platform testing.
- Do not call models on page load, in loops, or from unauthenticated public endpoints without application-level throttling.
- Cache responses that are reused.
- Requests may take several seconds; set client timeouts appropriately and stream where useful.

## 12. Rate limits, quotas, and operational policies

### 12.1 Namespace quota

| Resource | Limit |
|---|---:|
| Pods | 10 |
| CPU requests / limits (namespace total) | 400m / 2 cores |
| Memory requests / limits (namespace total) | 768Mi / 2Gi |
| Services | 5 (`LoadBalancer` and `NodePort`: 0) |
| Persistent volumes | 1, up to 10Gi |
| Container defaults if unset | requests 50m / 64Mi; limits 500m / 512Mi |

### 12.2 Platform API limits

- 60 requests/minute/team combined across bank sandbox and Huawei MaaS.
- Bank sandbox gateway timeout: 30 seconds.
- Huawei MaaS gateway timeout: 120 seconds.

### 12.3 Policies

- Synthetic data only. Never place real names, account numbers, BVNs, NINs, card numbers, or other personal data in the sandbox, logs, or seed files.
- Public by default: anyone with the team app URL can reach it. Protect private resources.
- Do not probe other namespaces or platform components.
- Gateway requests are logged and metered per team.
- Bank sandbox state is in memory. A platform restart restores every team to opening state. Keep application-owned records separately.
- Kubeconfigs and team keys are revoked when the event closes. Export required data before then.

## 13. Agent operational playbook

### 13.1 Before making an API call

1. Confirm the operation is listed as implemented in this guide.
2. Confirm the caller runs inside the team's Kubernetes namespace.
3. Select the correct base URL and auth header.
4. Validate required inputs and use synthetic fixture data only.
5. Add `Idempotency-Key` to POST operations that move money or create records.
6. Respect the combined 60 RPM limit.

### 13.2 For money movement

1. Resolve the beneficiary with the matching intra/interbank name-enquiry endpoint.
2. Show the resolved beneficiary name to the user before sending.
3. Submit once with the enquiry reference and an idempotency key.
4. Treat interbank `202` as pending, not final success.
5. If a timeout occurs, query/requery; do not submit again.
6. Use response charge fields for displayed totals.
7. For payment collections, verify the payment with the verification endpoint before fulfilling.

### 13.3 For webhook handling

1. Preserve the raw request bytes.
2. Validate timestamp freshness (within 300 seconds).
3. Verify HMAC-SHA256 over `timestamp + "." + raw_body`.
4. Reject invalid signatures.
5. De-duplicate by `event_id`.
6. Return 2xx within 10 seconds; process heavier work asynchronously.

### 13.4 For unknown DTOs

- Do not fabricate required fields, enums, or nested response structures.
- Retrieve the separate Sandbox API Mock Specification v2 before implementing strict schemas for endpoints marked “not supplied”.
- Until then, use `unknown`/opaque payloads at the integration boundary and validate only fields explicitly documented here.

## 14. Troubleshooting summary

| Symptom | Likely cause | Action |
|---|---|---|
| `Forbidden` from kubectl | Wrong namespace/resource | Remove incorrect `-n`; check `kubectl auth can-i <verb> <resource>` |
| `ImagePullBackOff` | Wrong image or missing private-registry pull secret | `kubectl describe pod <pod>`; configure `regcred` |
| `CrashLoopBackOff` | App exits during startup | `kubectl logs deploy/app --previous` |
| `exec format error` | ARM image | Rebuild with `--platform linux/amd64` |
| Pod pending / quota exceeded | Resource requests exceed namespace quota | Lower requests or reduce pods |
| `502` / `503` on team URL | Missing app Service, wrong target port, or pod not ready | Check `kubectl get svc,endpoints app` and readiness probe |
| `404 Route Not Found` | Hostname typo | Use `teamXX.xtradot.co` exactly |
| `401` from platform API | Missing key or wrong header | Bank: `x-api-key`; MaaS: `apikey` |
| `429` | Combined rate limit exceeded | Back off, batch, cache |
| Platform API timeout | Request sent outside cluster/team namespace | Call from a pod in the team's namespace |
| `404 NOT_FOUND` / not available in sandbox | Optional service not implemented | Check §7.14 |
| Bank data reset to opening balances | `/admin/reset` or platform restart | Re-seed application flow; keep own records |

For support, collect team ID, exact command/request, full error, `request_id` (if returned), `kubectl get pods`, and `kubectl describe pod <pod>`. Never send kubeconfig or team key in a support message.

## 15. Source gaps / follow-up documents needed

To produce a complete machine-valid API contract (for example OpenAPI, Zod, or TypeScript DTOs for every endpoint), obtain:

1. **Sandbox API Mock Specification v2** — explicitly named by the guide as the authoritative bank API contract.
2. Any separate webhook event schema/reference, if it is not included in v2.

This guide alone does not define full DTOs for banks, tariff, name-enquiry responses, transfer responses beyond charge fields, accounts, transactions, wallets, payments, settlements, virtual accounts, identity, open banking, lending, carbon, admin, or webhook event bodies.

---

## Appendix A — Compact agent facts

```yaml
source:
  title: "Forge 2026 Sandbox Participant Platform Guide"
  version: "1.0"
  date: "2026-11-09"
  authoritative_bank_api_spec: "Sandbox API Mock Specification v2 (not included)"

bank_api:
  base_url: "http://bank-api.ingress-apisix.svc.cluster.local/v1"
  auth_header: "x-api-key"
  rate_limit_per_minute_team: 60
  shared_rate_limit_with: "Huawei MaaS"
  gateway_timeout_seconds: 30
  amount_currency: "NGN"
  amount_precision: 2
  timestamp_format: "ISO 8601 UTC"
  pagination:
    default_page: 1
    default_per_page: 20
    max_per_page: 100
  idempotency:
    header: "Idempotency-Key"
    required_for: "POST requests that move money or create records"
    same_key_same_body: "replay original response"
    same_key_different_body: 409

huawei_maas:
  base_url: "http://huawei-maas.ingress-apisix.svc.cluster.local/openai/v1"
  auth_header: "apikey"
  gateway_timeout_seconds: 120
  models:
    - glm-5.3
    - glm-5.2
    - glm-5.1
    - deepseek-v4.1-flash-1017
    - deepseek-v4.1-flash
    - deepseek-v4-flash

critical_rules:
  - "All platform API calls must originate inside the team's namespace."
  - "Resolve beneficiary and show resolved name before transfer."
  - "Enquiry reference is single-use and expires after 10 minutes."
  - "On transfer timeout, requery; never resend."
  - "Verify checkout payment before giving value."
  - "Verify webhook HMAC against timestamp + '.' + raw body."
  - "Deduplicate webhook deliveries by event_id."
  - "Use synthetic data only."
  - "Do not assume optional/unimplemented endpoints exist."
```
