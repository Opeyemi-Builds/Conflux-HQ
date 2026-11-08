export type IssueType =
  | "failed_transfer"
  | "double_debit"
  | "card_atm"
  | "pos"
  | "fees"
  | "loan"
  | "app_login"
  | "fraud_scam"
  | "other";

export type Severity = "low" | "medium" | "high" | "critical";
export type Channel = "X" | "Instagram" | "Facebook" | "Email" | "Call" | "Branch" | "In-app";
export type Sentiment = "angry" | "negative" | "neutral" | "positive";
export type Decision = "pending" | "approved" | "rejected";

export const ISSUE_LABEL: Record<IssueType, string> = {
  failed_transfer: "Failed transfer",
  double_debit: "Double debit",
  card_atm: "Card / ATM",
  pos: "POS",
  fees: "Fees",
  loan: "Loan",
  app_login: "App / login",
  fraud_scam: "Fraud / scam",
  other: "Other",
};

export const SEV_ORDER: Severity[] = ["low", "medium", "high", "critical"];

export interface Complaint {
  id: string;
  rawId?: string;
  time: string;
  occurredAt?: string;
  channel: Channel;
  text: string;
  summary?: string | null;
  issue: IssueType;
  severity: Severity | null;
  sentiment: Sentiment | null;
  language: string;
  region: string;
  ref: string;
  amount?: number | null;
  isFraud?: boolean;
  confidence?: number | null;
  transactionId?: string | null;
  incidentId?: string | null;
  fresh?: boolean;
}

export interface Cause {
  name: string;
  confidence: number | null;
  evidence: string;
}

export interface TraceStep {
  tool: string;
  args: string;
  result: string;
}

export interface DraftItem {
  id: string;
  incident_id: string;
  kind: "customer_message" | "it_ticket" | "reversal_request";
  content: string;
  status: Decision;
  decided_by?: string | null;
  decided_at?: string | null;
}

export interface Incident {
  id: string;
  title: string;
  issue: IssueType;
  status: "active" | "monitoring" | "security" | "resolved";
  rawStatus?: string;
  priority: number;
  startedAt: string;
  detectedAt: string;
  startedAtIso?: string;
  detectedAtIso?: string;
  volume: number;
  baseline?: number;
  growth: string;
  growthRate?: number;
  channels: string[];
  region: string;
  moneyAtRisk: string;
  series: number[];
  labels: string[];
  releaseLabel?: string;
  causes: Cause[];
  trace: TraceStep[];
  summary: string;
  likelyCause?: string | null;
  customerDraft: string;
  itTicket: string;
  reversalDraft?: string;
  drafts: DraftItem[];
  examples: string[];
}

export interface Txn {
  id?: string;
  ref: string;
  time: string;
  type: string;
  channel: string;
  amount: string;
  status: string;
  reversal: string;
  switch: string;
  region?: string;
}

export interface AuditEntry {
  id: string;
  time: string;
  actor: string;
  action: string;
  detail: string;
  entityType?: string;
  entityId?: string;
}

export interface HourlyBucket {
  h: string;
  failed_transfer: number;
  fraud_scam: number;
  card_atm: number;
  double_debit: number;
  other: number;
}
