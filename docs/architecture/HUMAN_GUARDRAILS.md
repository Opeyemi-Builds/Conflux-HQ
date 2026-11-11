# Human-in-the-Loop Financial Guardrails & Audit Framework

## Core Principle

ConfluxHQ operates on a strict **Autonomous Investigation, Human Authorization** principle. AI models generate diagnostic insights and candidate drafts, but cannot execute financial reversals or public statements without operator sign-off.

## Financial Risk Boundaries

```
[Customer Complaint Stream]
             │
             ▼
[Spike Detector & Root Cause Correlator]
             │
             ▼
[Remediation Draft Engine]
       │                 │
       ▼                 ▼
[Customer Message]   [Batch Reversal Candidate]
  (Auto-Propose)        (Financial Guardrail)
       │                         │
       ▼                         ▼
 [Bank Operator]        [Core-Banking Authorized Sign-off]
 (Approve / Reject)     (Dual Key Operator Approval)
       │                         │
       ▼                         ▼
[Immutable Audit Log]   [Immutable Audit Log]
(GET /ai/incidents/.../audit)
```

## Immutable Audit Trail

Every decision records:
- `actor`: User email or authenticated system service.
- `action`: `investigation_completed`, `draft_approved`, `draft_rejected`, `reversal_flagged`.
- `decision`: `approved` | `rejected` | `deferred`.
- `timestamp`: Nanosecond-precision UTC timestamp.
