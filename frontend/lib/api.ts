import type { SocialAlias, SocialAnalytics, XResult } from "./social";
import type { CaseUpdate, IncidentTimelineItem, ManualCase, MatchResult, PaymentException, Proposal, ProposalInput, ReconciliationSummary } from "./reconciliation";
export type { IncidentTimelineItem } from "./reconciliation";

/**
 * Conflux HQ — Full Real-Time FastAPI Backend Client
 */

const API_BASE =
  typeof window !== "undefined"
    ? ""
    : process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000";

let cachedToken: string | null = null;
let tokenExpiresAt = 0;

export interface BackendBank {
  id: string;
  name: string;
  slug: string;
  country: string;
  cac_number?: string | null;
  status: string;
  created_at: string;
}

export interface BackendUser {
  id: string;
  email: string;
  full_name: string;
  role: "bank_admin" | "agent" | "it" | "manager";
  status: string;
  bank: BackendBank;
}

export interface BackendLoginResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
  demo?: boolean;
  synthetic?: boolean;
  user?: BackendUser;
}

export interface BackendComplaint {
  id: string;
  bank_id?: string;
  channel: string;
  text: string;
  masked_text?: string;
  customer_ref?: string | null;
  issue_type?: string | null;
  severity?: "low" | "medium" | "high" | "critical" | null;
  sentiment?: "angry" | "negative" | "neutral" | "positive" | null;
  summary?: string | null;
  language?: string | null;
  region?: string | null;
  is_fraud: boolean;
  mentioned_amount?: number | string | null;
  mentioned_time?: string | null;
  classification_confidence?: number | null;
  payment_category?: string | null;
  classification_explanation?: string | null;
  evidence_phrases?: string[];
  review_status?: "auto" | "needs_review" | "reviewed";
  routing_queue?: "standard" | "fraud_security" | "human_review";
  transaction_id?: string | null;
  incident_id?: string | null;
  occurred_at: string;
  created_at?: string;
}

export interface BackendIncident {
  id: string;
  issue_type: string;
  status: "open" | "active" | "investigating" | "awaiting_approval" | "monitoring" | "resolved" | "dismissed";
  started_at: string;
  detected_at: string;
  complaint_count: number;
  baseline: number;
  growth_rate: number;
  priority_score: number;
  affected_channels: Record<string, number>;
  likely_cause?: string | null;
  cause_confidence?: number | null;
  summary?: string | null;
}

export interface BackendDraft {
  id: string;
  incident_id: string;
  kind: "customer_message" | "it_ticket" | "reversal_request";
  content: string;
  status: "pending" | "approved" | "rejected";
  decided_by?: string | null;
  decided_at?: string | null;
}

export interface BackendAnalyticsSummary {
  window_hours?: number;
  window_start?: string;
  window_end?: string;
  total_complaints: number;
  complaints_total: number;
  unresolved_complaints?: number;
  fraud_count: number;
  fraud_complaints: number;
  money_at_risk: string | number;
  reported_exposure_ngn: string;
  open_incidents: number;
  avg_time_to_detect_seconds?: number | null;
  repeat_complaint_rate: number;
  by_issue: Record<string, number>;
  by_issue_type: Record<string, number>;
  by_channel: Record<string, number>;
  by_region: Record<string, number>;
  by_severity: Record<string, number>;
}

export interface BackendTrendBucket {
  bucket_start: string;
  total_complaints: number;
}

export interface BackendTrendsResponse {
  window_hours: number;
  window_start: string;
  window_end: string;
  buckets: BackendTrendBucket[];
}

export interface BackendTransactionsAnalytics {
  window_hours: number;
  total_transactions: number;
  by_status: Record<string, number>;
  failed_rate: number;
  total_amount: string | number;
  amount_by_status: Record<string, string | number>;
}

export interface BackendTransactionItem {
  id: string;
  reference: string;
  txn_type: string;
  txn_channel: string;
  status: string;
  reversal_status: string;
  processor?: string | null;
  amount: string | number;
  region?: string | null;
  occurred_at: string;
}

export interface BackendSystemEvent {
  id: string;
  event_type: string;
  component: string;
  version?: string | null;
  description: string;
  starts_at: string;
  ends_at?: string | null;
}

export interface BackendAuditEntry {
  id: string;
  actor: string;
  action: string;
  entity_type?: string;
  entity_id?: string;
  details?: Record<string, unknown> | null;
  created_at: string;
}

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

class ConfluxApiClient {
  hasStoredToken(): boolean {
    if (typeof window === "undefined") return false;
    cachedToken = localStorage.getItem("conflux_demo_token");
    tokenExpiresAt = Number(localStorage.getItem("conflux_demo_token_exp"));
    return Boolean(cachedToken && tokenExpiresAt > Date.now());
  }

  private storeToken(data: BackendLoginResponse): void {
    cachedToken = data.access_token;
    tokenExpiresAt = Date.now() + data.expires_in * 1000;
    localStorage.setItem("conflux_demo_token", cachedToken);
    localStorage.setItem("conflux_demo_token_exp", String(tokenExpiresAt));
    localStorage.removeItem("conflux_user");
  }

  async login(email: string, password: string): Promise<void> {
    await this.signIn({ email, password });
  }

  async enterDemo(): Promise<void> {
    await this.signIn({ username: "Zymic Bank", password: "123" });
  }

  private async signIn(payload: { email?: string; username?: string; password: string }): Promise<void> {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let detail = `Authentication failed (${res.status})`;
      try {
        const errJson = await res.json();
        if (errJson?.detail) {
          detail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
        }
      } catch {}
      throw new Error(detail);
    }

    this.storeToken(await res.json());
  }

  async registerBank(payload: {
    bank_name: string;
    cac_number?: string;
    country?: string;
    admin_full_name: string;
    email: string;
    password: string;
  }): Promise<{ email_confirmation_required: boolean }> {
    const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        bank_name: payload.bank_name,
        cac_number: payload.cac_number || null,
        country: payload.country || "NG",
        admin_full_name: payload.admin_full_name,
        email: payload.email,
        password: payload.password,
      }),
    });

    if (res.status === 404) {
      throw new Error("Bank registration is unavailable on this server. Demo access uses the fixed Zymic Bank tenant.");
    }

    if (!res.ok) {
      let detail = `Registration failed (${res.status})`;
      try {
        const errJson = await res.json();
        if (errJson?.detail) {
          detail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
        }
      } catch {}
      throw new Error(detail);
    }

    const data: { session: BackendLoginResponse | null; email_confirmation_required: boolean } = await res.json();
    if (data.session) this.storeToken(data.session);
    if (!data.session && !data.email_confirmation_required) {
      throw new Error("Registration did not return a session. Sign in to continue.");
    }
    return { email_confirmation_required: data.email_confirmation_required };
  }

  /**
   * Sign out and clear stored credentials
   */
  logout(): void {
    cachedToken = null;
    tokenExpiresAt = 0;
    if (typeof window !== "undefined") {
      localStorage.removeItem("conflux_demo_token");
      localStorage.removeItem("conflux_demo_token_exp");
      localStorage.removeItem("conflux_user");
      window.dispatchEvent(new Event("conflux:logout"));
    }
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    if (!this.hasStoredToken()) {
      this.logout();
      throw new Error("Your session has expired. Please sign in.");
    }
    const token = cachedToken;
    const headers: Record<string, string> = {
      Accept: "application/json",
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers as Record<string, string>),
    };

    const res = await fetch(`${API_BASE}${endpoint}`, {
      signal: !options.method || options.method === "GET" ? AbortSignal.timeout(15000) : undefined,
      ...options,
      headers,
    });

    if (res.status === 401 && typeof window !== "undefined" && localStorage.getItem("conflux_demo_token") === token) {
      this.logout();
    }

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new ApiError(res.status, `API error ${res.status}: ${errText}`);
    }

    return res.json();
  }

  // Current authenticated user profile
  async getMe(): Promise<BackendUser> {
    return this.request<BackendUser>("/api/v1/auth/me");
  }

  private reconciliation<T>(path: string, method = "GET", payload?: unknown): Promise<T> {
    return this.request<T>(`/api/v1/reconciliation${path}`, { method, body: JSON.stringify(payload) });
  }

  getReconciliationSummary() {
    return this.reconciliation<ReconciliationSummary>("/summary");
  }

  getExceptions(status: string, offset: number) {
    const query = new URLSearchParams({ limit: "50", offset: String(offset) });
    if (status) query.set("status", status);
    return this.reconciliation<PaymentException[]>(`/exceptions?${query}`);
  }

  createException(payload: ManualCase) {
    return this.reconciliation<PaymentException>("/exceptions", "POST", payload);
  }

  matchComplaint(id: string) {
    return this.reconciliation<MatchResult>(`/complaints/${encodeURIComponent(id)}/match`, "POST");
  }

  createComplaintException(id: string) {
    return this.reconciliation<PaymentException>(`/complaints/${encodeURIComponent(id)}/create`, "POST");
  }

  updateException(id: string, payload: CaseUpdate) {
    return this.reconciliation<PaymentException>(`/exceptions/${id}`, "PATCH", payload);
  }

  getProposals(id: string) {
    return this.reconciliation<Proposal[]>(`/exceptions/${id}/proposals`);
  }

  createProposal(id: string, payload: ProposalInput) {
    return this.reconciliation<Proposal>(`/exceptions/${id}/proposals`, "POST", payload);
  }

  decideProposal(id: string, decision: "approved" | "rejected") {
    return this.reconciliation<Proposal>(`/proposals/${id}/decision`, "POST", { decision });
  }

  getIncidentTimeline(id: string) {
    return this.request<{ timeline: IncidentTimelineItem[] }>(`/api/v1/incidents/${id}/reconciliation`);
  }

  // Analytics & Summary
  async getSummary(hours = 72): Promise<BackendAnalyticsSummary> {
    const raw = await this.request<Record<string, unknown>>(`/api/v1/analytics/summary?hours=${hours}`);
    const total =
      typeof raw.total_complaints === "number"
        ? raw.total_complaints
        : (raw.complaints_total as number | undefined) || 0;
    const fraud =
      typeof raw.fraud_count === "number"
        ? raw.fraud_count
        : (raw.fraud_complaints as number | undefined) || 0;
    const money = raw.money_at_risk ?? raw.reported_exposure_ngn ?? 0;
    const byIssue = (raw.by_issue_type || raw.by_issue || {}) as Record<string, number>;

    return {
      ...(raw as unknown as BackendAnalyticsSummary),
      total_complaints: total,
      complaints_total: total,
      fraud_count: fraud,
      fraud_complaints: fraud,
      money_at_risk: money as string | number,
      reported_exposure_ngn: String(money),
      by_issue: byIssue,
      by_issue_type: byIssue,
      by_channel: (raw.by_channel || {}) as Record<string, number>,
      by_region: (raw.by_region || {}) as Record<string, number>,
      by_severity: (raw.by_severity || {}) as Record<string, number>,
    };
  }

  async getTrends(hours = 72): Promise<BackendTrendsResponse> {
    return this.request<BackendTrendsResponse>(`/api/v1/analytics/trends?hours=${hours}`);
  }

  async getTransactionsAnalytics(hours = 72): Promise<BackendTransactionsAnalytics> {
    return this.request<BackendTransactionsAnalytics>(`/api/v1/analytics/transactions?hours=${hours}`);
  }

  async getTransactions(params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ total: number; items: BackendTransactionItem[] }> {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    q.set("limit", String(params?.limit || 25));
    if (params?.offset) q.set("offset", String(params.offset));
    return this.request<{ total: number; items: BackendTransactionItem[] }>(
      `/api/v1/synthetic/transactions?${q.toString()}`
    );
  }

  async getSystemEvents(limit = 20): Promise<{ items: BackendSystemEvent[] }> {
    return this.request<{ items: BackendSystemEvent[] }>(`/api/v1/synthetic/system-events?limit=${limit}`);
  }

  // Incidents
  async getIncidents(): Promise<BackendIncident[]> {
    return this.request<BackendIncident[]>("/api/v1/incidents");
  }

  async getIncident(id: string): Promise<BackendIncident> {
    return this.request<BackendIncident>(`/api/v1/incidents/${id}`);
  }

  async detectSpikes(now?: string): Promise<BackendIncident[]> {
    return this.request<BackendIncident[]>("/api/v1/incidents/detect", {
      method: "POST",
      body: JSON.stringify(now ? { now } : {}),
    });
  }

  async investigateIncident(id: string): Promise<{
    incident_id: string;
    likely_cause?: string | null;
    cause_confidence?: number | null;
    summary?: string | null;
    draft_count: number;
    source: string;
  }> {
    return this.request(`/api/v1/ai/incidents/${id}/investigate`, {
      method: "POST",
    });
  }

  async getIncidentDrafts(id: string): Promise<BackendDraft[]> {
    return this.request<BackendDraft[]>(`/api/v1/ai/incidents/${id}/drafts`);
  }

  async decideDraft(draftId: string, decision: "approved" | "rejected"): Promise<BackendDraft> {
    return this.request<BackendDraft>(`/api/v1/ai/drafts/${draftId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    });
  }

  async getIncidentAudit(id: string): Promise<BackendAuditEntry[]> {
    return this.request<BackendAuditEntry[]>(`/api/v1/ai/incidents/${id}/audit`);
  }

  async getBankAudit(limit = 100): Promise<BackendAuditEntry[]> {
    return this.request<BackendAuditEntry[]>(`/api/v1/ai/audit?limit=${limit}`);
  }

  async getComplaint(id: string): Promise<BackendComplaint> {
    return this.request(`/api/v1/complaints/${encodeURIComponent(id)}`);
  }

  classifyComplaint(id: string) {
    return this.request<BackendComplaint>(`/api/v1/complaints/${encodeURIComponent(id)}/classify`, { method: "POST" });
  }

  // Complaints
  async getComplaints(params?: {
    channel?: string;
    issue_type?: string;
    region?: string;
    is_fraud?: boolean;
    since?: string;
    until?: string;
    limit?: number;
    offset?: number;
  }): Promise<BackendComplaint[]> {
    const query = new URLSearchParams();
    if (params?.channel && params.channel !== "all") query.set("channel", params.channel);
    if (params?.issue_type && params.issue_type !== "all") query.set("issue_type", params.issue_type);
    if (params?.region && params.region !== "all") query.set("region", params.region);
    if (params?.is_fraud !== undefined) query.set("is_fraud", String(params.is_fraud));
    if (params?.since) query.set("since", params.since);
    if (params?.until) query.set("until", params.until);
    query.set("limit", String(params?.limit || 300));
    if (params?.offset) query.set("offset", String(params.offset));

    const qs = query.toString();
    return this.request<BackendComplaint[]>(`/api/v1/complaints${qs ? `?${qs}` : ""}`);
  }

  async ingestComplaint(data: {
    channel: string;
    text: string;
    region?: string;
    customer_ref?: string;
    language?: string;
    issue_type?: string;
  }): Promise<BackendComplaint> {
    return this.request<BackendComplaint>("/api/v1/complaints", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async classifyText(
    text: string,
    channel = "in_app"
  ): Promise<{
    issue_type: string;
    severity: string;
    language: string;
    sentiment: string;
    mentioned_amount?: number | null;
    is_fraud: boolean;
    short_summary: string;
    confidence: number;
  }> {
    return this.request("/api/v1/ai/classify", {
      method: "POST",
      body: JSON.stringify({ text, channel }),
    });
  }

  // Social X Adapter
  getSocialAnalytics() {
    return this.request<SocialAnalytics>("/api/v1/analytics/social?hours=24");
  }

  getXStatus() {
    return this.request<{ credentials_configured: boolean; reads_today: number; daily_post_limit: number }>("/api/v1/social/x/status");
  }

  getAliases() {
    return this.request<{ items: SocialAlias[] }>("/api/v1/social/aliases");
  }

  replaceAliases(aliases: SocialAlias[]) {
    return this.request<{ items: SocialAlias[] }>("/api/v1/social/aliases", {
      method: "PUT", body: JSON.stringify({ aliases }),
    });
  }

  async replayXPosts(): Promise<XResult> {
    const result = await this.request<XResult>("/api/v1/social/x/replay", {
      method: "POST", body: JSON.stringify({ limit: 15 }),
    });
    return { ...result, source: "recorded_replay" };
  }

  async pullXPosts(maxResults = 15, fallbackToReplay = false): Promise<XResult> {
    return this.request("/api/v1/social/x/pull", {
      method: "POST",
      body: JSON.stringify({
        mode: "recent_search",
        max_results: maxResults,
        fallback_to_replay: fallbackToReplay,
        auto_drain: true,
      }),
    });
  }

  // Synthetic Replay Scenario
  async seedScenario(reset = true): Promise<{
    synthetic: boolean;
    complaints_created: number;
    transactions_created: number;
    detection_at: string;
    release_at: string;
  }> {
    return this.request("/api/v1/synthetic/seed", {
      method: "POST",
      body: JSON.stringify({ seed: 42, reset }),
    });
  }

  async drainJobs(): Promise<{ processed: number; completed: number }> {
    return this.request("/api/v1/jobs/drain", {
      method: "POST",
      body: JSON.stringify({ limit: 100 }),
    });
  }
}

export const api = new ConfluxApiClient();
