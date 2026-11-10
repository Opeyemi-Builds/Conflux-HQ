# XtraDot sandbox webhook contract notes

Source: Access Youth Tech Forge Participant Platform Guide v1.0 and the team-owned
Adfola implementation instructions. This is a sanitized implementation note, not
the unavailable Sandbox API Mock Specification v2.

## Confirmed

- The sandbox is synthetic and isolated per team; it does not connect to NIBSS,
  NIMC, or a real core banking system.
- XtraDot webhook signature headers are `x-forge-timestamp` and
  `x-forge-signature`.
- The signature is HMAC-SHA256 over the exact bytes
  `timestamp + "." + raw_body`.
- Reject a signed timestamp older than five minutes.
- The `event_id` field is named by the team instructions, but the rest of the
  webhook payload is not documented here.
- The event type is provided in the `x-forge-event` header.
- A webhook receipt must be retained verbatim and deduplicated by `event_id`.
- Provider data and statuses are sandbox evidence only. They are not independent
  proof of another bank's beneficiary ledger.

## Deliberately unspecified

Do not infer any of the following from the participant guide:

- The webhook body fields other than `event_id`.
- The requery request body.
- The representation or encoding of `x-forge-timestamp`.
- The transfer status vocabulary, transitions, or finality rules.
- The set of supported `x-forge-event` values.

Until the authoritative contract is supplied, preserve raw bytes and headers,
verify the signature over the raw body, and mark unrecognized or unprocessable
receipts `ignored`. Do not parse business status, infer settlement, or construct
a requery request from guessed fields.

No API keys, webhook secrets, participant credentials, real account details, or
personal data belong in this file.