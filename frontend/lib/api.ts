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
  role: string;
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

class ConfluxApiClient {
  /**
   * Check if a valid token is stored in localStorage / memory
   */
  hasStoredToken(): boolean {
    const now = Date.now();
    if (cachedToken && tokenExpiresAt > now + 10000) return true;
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("conflux_demo_token");
      const storedExp = localStorage.getItem("conflux_demo_token_exp");
      if (stored && storedExp && Number(storedExp) > now + 10000) {
        cachedToken = stored;
        tokenExpiresAt = Number(storedExp);
        return true;
      }
    }
    return false;
  }

  /**
   * Explicit login with username/email and password
   */
  async login(identifier: string, password: string): Promise<BackendLoginResponse> {
    const trimmed = identifier.trim();
    // Try demo login payload first (username + password), then standard email + password if needed
    let res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: trimmed, password }),
    });

    if (res.status === 422 && trimmed.includes("@")) {
      res = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: trimmed, password }),
      });
    }

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

    const data: BackendLoginResponse = await res.json();
    const now = Date.now();
    cachedToken = data.access_token;
    tokenExpiresAt = now + (data.expires_in || 7200) * 1000;

    if (typeof window !== "undefined") {
      localStorage.setItem("conflux_demo_token", cachedToken);
      localStorage.setItem("conflux_demo_token_exp", String(tokenExpiresAt));
      if (data.user) {
        localStorage.setItem("conflux_user", JSON.stringify(data.user));
      }
    }

    return data;
  }

  /**
   * Register a new bank tenant (or provision in demo mode)
   */
  async registerBank(payload: {
    bank_name: string;
    cac_number?: string;
    country?: string;
    admin_full_name: string;
    email: string;
    password: string;
  }): Promise<BackendLoginResponse> {
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
      // Demo mode active: authenticate against demo bank tenant and customize local session profile
      const demoRes = await this.login("Zymic Bank", "123");
      if (demoRes.user && typeof window !== "undefined") {
        const customUser: BackendUser = {
          ...demoRes.user,
          full_name: payload.admin_full_name,
          email: payload.email,
          bank: {
            ...demoRes.user.bank,
            name: payload.bank_name,
            cac_number: payload.cac_number || null,
          },
        };
        localStorage.setItem("conflux_user", JSON.stringify(customUser));
        demoRes.user = customUser;
      }
      return demoRes;
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

    const regData = await res.json();
    if (regData.session?.access_token) {
      const now = Date.now();
      cachedToken = regData.session.access_token;
      tokenExpiresAt = now + (regData.session.expires_in || 7200) * 1000;
      if (typeof window !== "undefined") {
        localStorage.setItem("conflux_demo_token", cachedToken!);
        localStorage.setItem("conflux_demo_token_exp", String(tokenExpiresAt));
        if (regData.user) {
          localStorage.setItem("conflux_user", JSON.stringify(regData.user));
        }
      }
      return {
        access_token: regData.session.access_token,
        token_type: "bearer",
        expires_in: regData.session.expires_in || 7200,
        user: regData.user,
      };
    }

    return this.login(payload.email, payload.password);
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
    }
  }

  /**
   * Retrieves or renews bearer token from FastAPI
   */
  async getAuthToken(): Promise<string> {
    const now = Date.now();
    if (cachedToken && tokenExpiresAt > now + 60000) {
      return cachedToken;
    }

    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("conflux_demo_token");
      const storedExp = localStorage.getItem("conflux_demo_token_exp");
      if (stored && storedExp && Number(storedExp) > now + 60000) {
        cachedToken = stored;
        tokenExpiresAt = Number(storedExp);
        return stored;
      }
    }

    const data = await this.login("Zymic Bank", "123");
    return data.access_token;
  }

  /**
   * Authorized fetch wrapper
   */
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = await this.getAuthToken();
    const headers: Record<string, string> = {
      Accept: "application/json",
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers as Record<string, string>),
    };

    let res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    // If token expired or server restarted, re-login once
    if (res.status === 401) {
      this.logout();
      const freshToken = await this.getAuthToken();
      headers.Authorization = `Bearer ${freshToken}`;
      res = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
      });
    }

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`API error ${res.status} on ${endpoint}: ${errText}`);
    }

    return res.json();
  }

  // Current authenticated user profile
  async getMe(): Promise<BackendUser> {
    const me = await this.request<BackendUser>("/api/v1/auth/me");
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("conflux_user");
      if (saved) {
        try {
          const parsed = JSON.parse(saved) as BackendUser;
          // Preserve custom registered bank/name if set in demo session
          if (parsed.email && parsed.email !== "demo@zymic.example") {
            return parsed;
          }
        } catch {}
      }
      localStorage.setItem("conflux_user", JSON.stringify(me));
    }
    return me;
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

  // Complaints
  async getComplaints(params?: {
    channel?: string;
    issue_type?: string;
    region?: string;
    is_fraud?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<BackendComplaint[]> {
    const query = new URLSearchParams();
    if (params?.channel && params.channel !== "all") query.set("channel", params.channel);
    if (params?.issue_type && params.issue_type !== "all") query.set("issue_type", params.issue_type);
    if (params?.region && params.region !== "all") query.set("region", params.region);
    if (params?.is_fraud !== undefined) query.set("is_fraud", String(params.is_fraud));
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
  async pullXPosts(maxResults = 15): Promise<{
    fetched: number;
    ingested: number;
    duplicates: number;
    unmatched: number;
    source: string;
  }> {
    return this.request("/api/v1/social/x/pull", {
      method: "POST",
      body: JSON.stringify({
        mode: "recent_search",
        max_results: maxResults,
        fallback_to_replay: true,
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
