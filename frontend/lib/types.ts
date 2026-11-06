export type IssueType = "failed_transfer" | "double_debit" | "card_atm" | "pos" | "fees" | "loan" | "app_login" | "fraud_scam" | "other";
export type Severity = "low" | "medium" | "high" | "critical";
export type Channel = "X" | "Instagram" | "Facebook" | "Email" | "Call" | "Branch" | "In-app";
export type Role = "agent" | "it" | "management";
export type Sentiment = "angry" | "negative" | "neutral";
export type Decision = "pending" | "approved" | "rejected";

export interface Complaint {
  id: string; time: string; channel: Channel; text: string; issue: IssueType; severity: Severity;
  sentiment: Sentiment; language: string; region: string; ref: string; fresh?: boolean;
}
export interface Cause { name: string; confidence: number; evidence: string }
export interface TraceStep { phase: number; tool: string; args: string; result: string }
export interface Incident {
  id: string; title: string; issue: IssueType; status: "active" | "monitoring" | "security"; priority: number;
  startedAt: string; detectedAt: string; volume: number; growth: string; channels: string[]; region: string;
  moneyAtRisk: string; series: number[]; releaseMarker?: boolean; causes: Cause[]; trace: TraceStep[];
  summary: Record<Role, string>; customerDraft: string; itTicket: string; examples: string[];
}
export interface Txn { ref: string; time: string; type: string; channel: string; amount: string; status: string; reversal: string; switch: string }
export interface AuditEntry { phase: number; time: string; actor: string; action: string; detail: string }
