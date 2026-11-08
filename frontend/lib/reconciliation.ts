export const caseStatuses = ["reported", "transaction_matched", "settlement_checked", "reconciliation_pending", "approval_required", "resolved", "rejected"] as const;
export const settlementStatuses = ["initiated", "processing", "successful", "failed", "pending", "reversed", "partially_settled", "unknown", "disputed", "reconciled"] as const;
export const exceptionTypes = ["debited_not_credited", "failed_transfer", "delayed_settlement", "reversed_not_refunded", "duplicate_debit", "duplicate_settlement", "processor_timeout", "switch_outage", "unknown_settlement", "fraud_dispute"] as const;

export interface PaymentException {
  id: string;
  complaint_id: string | null;
  transaction_id: string | null;
  exception_type: typeof exceptionTypes[number];
  status: typeof caseStatuses[number];
  settlement_status: typeof settlementStatuses[number];
  amount: string | null;
  currency: string;
  processor: string | null;
  payment_channel: string | null;
  match_confidence: string | null;
  owner: string | null;
  evidence_summary: string | null;
  priority: number;
  approval_required: boolean;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export type CaseUpdate = Partial<Pick<PaymentException, "status" | "settlement_status" | "owner" | "evidence_summary" | "priority" | "approval_required">>;
export type ManualCase = Pick<PaymentException, "exception_type" | "currency"> & Partial<Pick<PaymentException, "amount" | "complaint_id" | "transaction_id" | "processor" | "payment_channel">>;

export interface ReconciliationSummary {
  total_exceptions: number;
  reported_open_amount_by_currency: Record<string, string>;
  amount_note: string;
}

export interface MatchResult {
  complaint_id: string;
  selected_transaction_id: string | null;
  candidates: { transaction_id: string; reference: string; confidence: string; reasons: string[] }[];
}

export interface ProposalInput {
  kind: "refund" | "reversal";
  amount: string;
  reason: string;
}

export interface Proposal extends ProposalInput {
  id: string;
  currency: string;
  status: "pending" | "approved" | "rejected";
  proposed_by: string;
  decided_by: string | null;
  decided_at: string | null;
}

export interface IncidentTimelineItem {
  at: string;
  kind: string;
  id: string;
  status?: string;
  settlement_status?: string;
  association?: string;
  channel?: string;
  component?: string;
  event_type?: string;
  processor?: string;
}
