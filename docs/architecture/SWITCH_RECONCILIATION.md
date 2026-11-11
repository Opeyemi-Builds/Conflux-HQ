# Switch Settlement & Transaction Exception Reconciliation

## Payment Rails Integrated

1. **NIBSS Instant Payments (NIP)**: Interbank credit transfers, account lookups, and session ID tracing.
2. **Interswitch (Verve / Quickteller)**: ATM terminal network declines and POS merchant transactions.
3. **Unified Payments (PayAttitude)**: Digital channel debit exceptions.

## Exception Matching Rules

When a customer reports an unsettled transaction:

1. **Exact Reference Match**:
   `complaint.payment_reference == transaction.reference`
   Confidence: `100%`.

2. **Fuzzy Amount & Timestamp Correlation**:
   - `|complaint.amount - transaction.amount| == 0`
   - `|complaint.occurred_at - transaction.occurred_at| <= 30 minutes`
   - Matching channel (`USSD`, `POS`, `ATM`, `In-app`)
   - Same receiving institution / BIN
   Confidence: `85% - 95%`.

3. **Status Taxonomy**:
   - `SETTLED`: Successful core-banking ledger posting.
   - `PENDING_REVERSAL`: Reversal initiated on payment rail, awaiting destination bank acknowledgment.
   - `FAILED_UNREVERSED`: Explicit exception requiring operator remediation.
