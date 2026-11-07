/**
 * Conflux HQ - Live FastAPI Backend Client
 * Connects Next.js Frontend to FastAPI Backend in Real Time
 */

const API_BASE = typeof window !== "undefined" ? "" : process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000";

let cachedToken: string | null = null;
let tokenExpiresAt = 0;

export interface BackendLoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  synthetic?: boolean;
}

export interface BackendComplaint {
  id: string;
  bank_id: string;
  channel: string;
  text: string;
  masked_text?: string;
  issue_type: string;
  severity: "low" | "medium" | "high" | "critical";
  sentiment: "angry" | "negative" | "neutral" | "positive";
  language: string;
  region: string;
  is_fraud: boolean;
  occurred_at: string;
  created_at: string;
}

export interface BackendIncident {
  id: string;
  issue_type: string;
  status: "open" | "active" | "investigating" | "monitoring" | "resolved";
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

export interface BackendAnalyticsSummary {
  total_complaints?: number;
  complaints_total?: number;
  unresolved_complaints?: number;
  fraud_count?: number;
  fraud_complaints?: number;
  money_at_risk?: string | number;
  reported_exposure_ngn?: string;
  open_incidents: number;
  avg_time_to_detect_seconds?: number | null;
  repeat_complaint_rate?: number;
  by_issue?: Record<string, number>;
  by_issue_type?: Record<string, number>;
  by_channel: Record<string, number>;
  by_region: Record<string, number>;
  by_severity?: Record<string, number>;
}

export interface BackendAuditEntry {
  id?: string;
  phase?: number;
  time?: string;
  created_at?: string;
  actor: string;
  action: string;
  detail: string;
}

class ConfluxApiClient {
  /**
   * Retrieves or renews demo bearer token from FastAPI
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

    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: "Zymic Bank", password: "123" }),
      });

      if (!res.ok) {
        throw new Error(`Auth failed with status ${res.status}`);
      }

      const data: BackendLoginResponse = await res.json();
      cachedToken = data.access_token;
      tokenExpiresAt = now + (data.expires_in || 7200) * 1000;

      if (typeof window !== "undefined") {
        localStorage.setItem("conflux_demo_token", cachedToken);
        localStorage.setItem("conflux_demo_token_exp", String(tokenExpiresAt));
      }

      return cachedToken;
    } catch {
      return cachedToken || "demo-offline-token";
    }
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

    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`API error ${res.status} on ${endpoint}: ${errText}`);
    }

    return res.json();
  }

  // Analytics & Summary
  async getSummary(hours = 48): Promise<BackendAnalyticsSummary> {
    const raw = await this.request<Record<string, unknown>>(`/api/v1/analytics/summary?hours=${hours}`);
    return {
      ...(raw as unknown as BackendAnalyticsSummary),
      total_complaints: typeof raw.total_complaints === "number" ? raw.total_complaints : (raw.complaints_total as number | undefined),
      complaints_total: typeof raw.complaints_total === "number" ? raw.complaints_total : (raw.total_complaints as number | undefined),
      money_at_risk: raw.money_at_risk as string | number | undefined,
      reported_exposure_ngn: raw.reported_exposure_ngn ? String(raw.reported_exposure_ngn) : raw.money_at_risk ? String(raw.money_at_risk) : "48200000",
      by_issue: (raw.by_issue_type || raw.by_issue || {}) as Record<string, number>,
      by_issue_type: (raw.by_issue_type || raw.by_issue || {}) as Record<string, number>,
    };
  }

  async getTrends(hours = 24): Promise<Array<{ timestamp: string; count: number }>> {
    return this.request<Array<{ timestamp: string; count: number }>>(`/api/v1/analytics/trends?hours=${hours}`);
  }

  // Incidents
  async getIncidents(): Promise<BackendIncident[]> {
    return this.request<BackendIncident[]>("/api/v1/incidents");
  }

  async getIncident(id: string): Promise<BackendIncident> {
    return this.request<BackendIncident>(`/api/v1/incidents/${id}`);
  }

  async detectSpikes(): Promise<BackendIncident[]> {
    return this.request<BackendIncident[]>("/api/v1/incidents/detect", {
      method: "POST",
      body: JSON.stringify({}),
    });
  }

  async investigateIncident(id: string): Promise<{ status: string; cause?: string; confidence?: number; trace?: unknown[] }> {
    return this.request(`/api/v1/ai/incidents/${id}/investigate`, {
      method: "POST",
    });
  }

  async getIncidentDrafts(id: string): Promise<Array<{ id: string; draft_type: string; content: string; status: string }>> {
    return this.request(`/api/v1/ai/incidents/${id}/drafts`);
  }

  async decideDraft(draftId: string, decision: "approved" | "rejected", note?: string): Promise<{ success: boolean; decision: string }> {
    return this.request(`/api/v1/ai/drafts/${draftId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, note }),
    });
  }

  async getIncidentAudit(id: string): Promise<BackendAuditEntry[]> {
    return this.request<BackendAuditEntry[]>(`/api/v1/ai/incidents/${id}/audit`);
  }

  // Complaints
  async getComplaints(params?: {
    channel?: string;
    issue_type?: string;
    is_fraud?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<BackendComplaint[]> {
    const query = new URLSearchParams();
    if (params?.channel && params.channel !== "all") query.set("channel", params.channel);
    if (params?.issue_type && params.issue_type !== "all") query.set("issue_type", params.issue_type);
    if (params?.is_fraud !== undefined) query.set("is_fraud", String(params.is_fraud));
    query.set("limit", String(params?.limit || 100));
    if (params?.offset) query.set("offset", String(params.offset));

    const qs = query.toString();
    return this.request<BackendComplaint[]>(`/api/v1/complaints${qs ? `?${qs}` : ""}`);
  }

  async ingestComplaint(data: {
    channel: string;
    text: string;
    region?: string;
    customer_handle?: string;
  }): Promise<BackendComplaint> {
    return this.request<BackendComplaint>("/api/v1/complaints", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async classifyText(text: string): Promise<{
    issue_type: string;
    severity: string;
    language: string;
    sentiment: string;
    confidence: number;
  }> {
    return this.request("/api/v1/ai/classify", {
      method: "POST",
      body: JSON.stringify({ text }),
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

  async drainJobs(): Promise<{ drained: number; jobs: unknown[] }> {
    return this.request("/api/v1/jobs/drain", {
      method: "POST",
    });
  }
}

export const api = new ConfluxApiClient();
