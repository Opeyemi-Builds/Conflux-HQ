"use client";
import type { XResult } from "@/lib/social";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  ISSUE_LABEL,
  type AuditEntry,
  type Cause,
  type Channel,
  type Complaint,
  type Decision,
  type HourlyBucket,
  type Incident,
  type IssueType,
  type Sentiment,
  type Severity,
} from "@/lib/types";
import {
  api,
  type BackendAnalyticsSummary,
  type BackendAuditEntry,
  type BackendComplaint,
  type BackendDraft,
  type BackendIncident,
  type BackendTransactionsAnalytics,
  type BackendTrendBucket,
  type BackendUser,
} from "@/lib/api";

interface Ctx {
  decide: (draftId: string, d: Exclude<Decision, "pending">) => Promise<BackendDraft>;
  audit: AuditEntry[];
  complaints: Complaint[];
  incidents: Incident[];
  transactionsAnalytics: BackendTransactionsAnalytics | null;
  summary: BackendAnalyticsSummary | null;
  hourlySeries: HourlyBucket[];
  channelSplit: { name: string; value: number }[];
  regionSplit: { name: string; value: number }[];
  rootCauses: { name: string; value: number }[];
  detectTrend: { d: string; min: number }[];
  addComplaint: (c: Partial<Complaint> & { text: string }) => Promise<void>;
  pullSocialX: () => Promise<XResult>;
  investigate: (incidentId: string) => Promise<void>;
  detectNow: () => Promise<void>;
  syncing: boolean;
  user: BackendUser | null;
  isAuthenticated: boolean;
  logoutUser: () => void;
  lastRefresh: string | null;
  isBackendLive: boolean;
  isLoading: boolean;
  refresh: () => Promise<void>;
}

const C = createContext<Ctx | null>(null);

export const useDash = () => {
  const v = useContext(C);
  if (!v) throw new Error("useDash outside provider");
  return v;
};

function formatTimeHHMM(iso?: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (!isNaN(d.getTime())) {
      return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    }
  } catch {}
  return "—";
}

function formatNaira(amount: number): string {
  if (amount >= 1_000_000) {
    return `₦${(amount / 1_000_000).toFixed(2)}m`;
  }
  if (amount >= 1_000) {
    return `₦${Math.round(amount).toLocaleString()}`;
  }
  return `₦${amount}`;
}

function formatLanguage(lang?: string | null): string {
  if (!lang) return "—";
  const clean = lang.replace(/_mix$/i, "").toLowerCase();
  if (clean === "en") return "English";
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}

export function mapBackendComplaint(b: BackendComplaint): Complaint {
  const channelMap: Record<string, Channel> = {
    x: "X",
    instagram: "Instagram",
    facebook: "Facebook",
    email: "Email",
    call: "Call",
    branch: "Branch",
    in_app: "In-app",
    ussd: "In-app",
  };
  const channel: Channel = channelMap[b.channel?.toLowerCase()] || "In-app";
  const issue: IssueType = (b.issue_type as IssueType) || "other";
  const severity = (b.severity as Severity | null) ?? null;
  const sentiment = (b.sentiment as Sentiment | null) ?? null;
  const amt = b.mentioned_amount != null ? Number(b.mentioned_amount) : null;

  return {
    id: b.id,
    rawId: b.id,
    time: formatTimeHHMM(b.occurred_at || b.created_at),
    occurredAt: b.occurred_at || b.created_at,
    channel,
    text: b.masked_text || b.text,
    summary: b.summary,
    issue,
    severity,
    sentiment,
    language: formatLanguage(b.language),
    region: b.region || "—",
    ref: b.customer_ref ? `****${b.customer_ref.slice(-4)}` : `****${b.id.slice(0, 4)}`,
    amount: amt,
    isFraud: b.is_fraud ?? undefined,
    confidence: b.classification_confidence,
    transactionId: b.transaction_id,
    incidentId: b.incident_id,
  };
}

function mapBackendAudit(a: BackendAuditEntry): AuditEntry {
  const actorLower = (a.actor || "").toLowerCase();
  const actorLabel =
    actorLower === "system" || actorLower === "detector"
      ? "Detector"
      : actorLower.includes("agent") ||
        a.action.startsWith("agent_") ||
        a.action === "incident_investigated" ||
        a.action === "draft_created"
      ? "Agent"
      : a.action === "draft_decided" || a.action === "demo_login" || a.action === "user_login"
      ? "Human"
      : "System";

  let detail = "";
  const d = a.details || {};
  if (a.action === "agent_tool_call") {
    detail = "Investigation step recorded.";
  } else if (a.action === "spike_detected") {
    detail = `${d.issue_type || "issue"} exceeded baseline (${d.count || 0} complaints vs baseline ${d.baseline || 0}).`;
  } else if (a.action === "incident_investigated") {
    detail = d.confidence == null ? "Investigation completed." : `Likely cause assessed at ${Math.round(Number(d.confidence) * 100)}% confidence.`;
  } else if (a.action === "draft_created") {
    detail = `Generated ${d.kind || "response"} draft.`;
  } else if (a.action === "draft_decided") {
    detail = `Draft (${d.kind || "message"}) ${d.decision || "reviewed"} by operator.`;
  } else if (Object.keys(d).length > 0) {
    detail = Object.entries(d)
      .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
      .join(" · ")
      .slice(0, 160);
  } else {
    detail = `${a.entity_type || ""} ${a.entity_id?.slice(0, 8) || ""}`.trim();
  }

  return {
    id: a.id,
    time: formatTimeHHMM(a.created_at),
    actor: actorLabel,
    action: a.action,
    detail,
    entityType: a.entity_type,
    entityId: a.entity_id,
  };
}

export function buildIncidentFromBackend(
  b: BackendIncident,
  drafts: BackendDraft[],
  allComplaints: Complaint[]
): Incident {
  const issue = (b.issue_type as IssueType) || "other";
  const issueComplaints = allComplaints.filter((c) => c.incidentId === b.id);
  const totalExposure = issueComplaints.reduce((acc, c) => acc + (c.amount || 0), 0);

  // Build time series strictly from backend complaint timestamps
  const bucketMap = new Map<string, number>();
  issueComplaints.forEach((c) => {
    if (c.occurredAt) {
      const minute = new Date(c.occurredAt).toISOString().slice(0, 16);
      bucketMap.set(minute, (bucketMap.get(minute) || 0) + 1);
    }
  });
  const sortedTimes = Array.from(bucketMap.keys()).sort().slice(-16);
  const series = sortedTimes.map((k) => bucketMap.get(k) || 0);
  const labels = sortedTimes.map((time) => time.replace("T", " ") + " UTC");

  const confPct = b.cause_confidence != null ? Math.round(b.cause_confidence * 100) : null;
  const causes: Cause[] = [];
  if (b.likely_cause) {
    causes.push({
      name: b.likely_cause,
      confidence: confPct,
      evidence: b.summary || b.likely_cause,
    });
  }
  const custDraft = drafts.find((d) => d.kind === "customer_message");
  const itDraft = drafts.find((d) => d.kind === "it_ticket");
  const revDraft = drafts.find((d) => d.kind === "reversal_request");

  const channelsList =
    b.affected_channels && Object.keys(b.affected_channels).length > 0
      ? Object.keys(b.affected_channels).map((ch) => ch.toUpperCase().replace("_", "-"))
      : [];

  const regionSet = Array.from(
    new Set(issueComplaints.map((c) => c.region).filter((r) => r && r !== "—"))
  ).slice(0, 4);
  const regionStr = regionSet.length > 0 ? regionSet.join(", ") : "—";

  return {
    id: b.id,
    title:
      channelsList.length > 0
        ? `${ISSUE_LABEL[issue]} spike across ${channelsList.slice(0, 2).join(" & ")}`
        : `${ISSUE_LABEL[issue]} incident`,
    issue,
    status:
      b.status === "resolved"
        ? "resolved"
        : issue === "fraud_scam"
        ? "security"
        : b.status === "monitoring"
        ? "monitoring"
        : "active",
    rawStatus: b.status,
    priority: b.priority_score || 0,
    startedAt: formatTimeHHMM(b.started_at),
    detectedAt: formatTimeHHMM(b.detected_at),
    startedAtIso: b.started_at,
    detectedAtIso: b.detected_at,
    volume: b.complaint_count,
    baseline: b.baseline,
    growth: `${b.growth_rate}× baseline`,
    growthRate: b.growth_rate,
    channels: channelsList,
    region: regionStr,
    moneyAtRisk: formatNaira(totalExposure),
    series,
    labels,
    causes,
    summary: b.summary || b.likely_cause || `${b.complaint_count} complaints linked to this incident.`,
    likelyCause: b.likely_cause,
    customerDraft: custDraft?.content || "",
    itTicket: itDraft?.content || "",
    reversalDraft: revDraft?.content,
    drafts: drafts.map((d) => ({
      id: d.id,
      incident_id: d.incident_id,
      kind: d.kind,
      content: d.content,
      status: d.status,
      decided_by: d.decided_by,
      decided_at: d.decided_at,
    })),
    examples: issueComplaints.slice(0, 6).map((c) => c.text),
  };
}

export default function DashboardProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<BackendUser | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    const endSession = () => {
      active = false;
      setUser(null);
      router.replace("/login");
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === "conflux_demo_token" || event.key === null) endSession();
    };
    window.addEventListener("conflux:logout", endSession);
    window.addEventListener("storage", onStorage);
    if (api.hasStoredToken()) {
      api.getMe().then((me) => {
        if (active) setUser(me);
      }).catch(() => {
        if (!active) return;
        if (api.hasStoredToken()) setError(true);
        else api.logout();
      });
    } else {
      api.logout();
    }
    return () => {
      active = false;
      window.removeEventListener("conflux:logout", endSession);
      window.removeEventListener("storage", onStorage);
    };
  }, [attempt, router]);

  if (user) return <AuthenticatedDashboard user={user}>{children}</AuthenticatedDashboard>;

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center gap-4 p-8 text-navy">
      {error ? (
        <>
          <p role="alert">Could not verify your session.</p>
          <button type="button" onClick={() => { setError(false); setAttempt(attempt + 1); }}>
            Retry
          </button>
        </>
      ) : <p role="status">Checking session…</p>}
    </div>
  );
}

function AuthenticatedDashboard({ children, user }: { children: React.ReactNode; user: BackendUser }) {
  const [backendComplaints, setBackendComplaints] = useState<Complaint[]>([]);
  const [backendIncidents, setBackendIncidents] = useState<Incident[]>([]);
  const [transactionsAnalytics, setTransactionsAnalytics] = useState<BackendTransactionsAnalytics | null>(null);
  const [trendBuckets, setTrendBuckets] = useState<BackendTrendBucket[]>([]);
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [summary, setSummary] = useState<BackendAnalyticsSummary | null>(null);
  const [lastRefresh, setLastRefresh] = useState<string | null>(null);
  const [isBackendLive, setIsBackendLive] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const inFlight = useRef<Promise<void> | null>(null);

  const canOperate = user.role !== "manager";
  const loadBackendData = useCallback(async () => {
    try {
      const [complaintsResult, incidentsResult, summaryResult, trendsRes, txAnalyticsRes, bankAuditRes] = await Promise.allSettled([
        api.getComplaints({ limit: 500 }),
        api.getIncidents(),
        api.getSummary(72),
        api.getTrends(72),
        api.getTransactionsAnalytics(72),
        api.getBankAudit(120),
      ]);
      if (complaintsResult.status === "rejected") throw complaintsResult.reason;
      if (incidentsResult.status === "rejected") throw incidentsResult.reason;
      if (summaryResult.status === "rejected") throw summaryResult.reason;
      const rawComplaints = complaintsResult.value;
      const rawIncidents = incidentsResult.value;
      const sumRes = summaryResult.value;

      const mappedComplaints = (rawComplaints || []).map(mapBackendComplaint);
      setBackendComplaints(mappedComplaints);

      if (sumRes) setSummary(sumRes);
      setTrendBuckets(trendsRes.status === "fulfilled" ? trendsRes.value.buckets : []);
      setTransactionsAnalytics(txAnalyticsRes.status === "fulfilled" ? txAnalyticsRes.value : null);
      if (bankAuditRes.status === "fulfilled") setAuditEntries(bankAuditRes.value.map(mapBackendAudit));

      const enrichedIncidents: Incident[] = await Promise.all(
        rawIncidents.map(async (inc) => {
          const drafts = canOperate ? await api.getIncidentDrafts(inc.id).catch(() => []) : [];
          return buildIncidentFromBackend(inc, drafts, mappedComplaints);
        })
      );

      setBackendIncidents(enrichedIncidents);
      setLastRefresh(new Date().toISOString());
      setIsBackendLive(true);
      setIsLoading(false);
    } catch (err) {
      console.warn("Backend real-time sync error:", err);
      setIsBackendLive(false);
      setIsLoading(false);
    }
  }, [canOperate]);

  const fetchBackendData = useCallback(() => {
    if (!inFlight.current) {
      inFlight.current = loadBackendData().finally(() => {
        inFlight.current = null;
      });
    }
    return inFlight.current;
  }, [loadBackendData]);

  useEffect(() => {
    let active = true;
    const run = () => {
      if (active) fetchBackendData();
    };
    const initialTimer = setTimeout(run, 0);
    const interval = setInterval(run, 4000);
    return () => {
      active = false;
      clearTimeout(initialTimer);
      clearInterval(interval);
    };
  }, [fetchBackendData]);

  const logoutUser = useCallback(() => api.logout(), []);

  // Run live spike detection & refresh backend state
  const detectNow = useCallback(async () => {
    setSyncing(true);
    try {
      const latestOccurred = backendComplaints[0]?.occurredAt;
      await api.detectSpikes(latestOccurred);
      await fetchBackendData();
    } finally {
      setSyncing(false);
    }
  }, [backendComplaints, fetchBackendData]);

  const investigate = useCallback(
    async (incidentId: string) => {
      await api.investigateIncident(incidentId);
      await fetchBackendData();
    },
    [fetchBackendData]
  );

  const decide = useCallback(
    async (draftId: string, decision: Exclude<Decision, "pending">) => {
      const draft = await api.decideDraft(draftId, decision);
      await fetchBackendData();
      return draft;
    },
    [fetchBackendData]
  );

  const addComplaint = useCallback(
    async (c: Partial<Complaint> & { text: string }) => {
      const channelBackend =
        c.channel?.toLowerCase() === "in-app"
          ? "in_app"
          : c.channel?.toLowerCase() || "in_app";
      await api.ingestComplaint({
        text: c.text,
        channel: channelBackend,
        region: c.region,
      });
      await fetchBackendData();
    },
    [fetchBackendData]
  );

  const pullSocialX = useCallback(async () => {
    const res = await api.pullXPosts(15);
    await fetchBackendData();
    return res;
  }, [fetchBackendData]);

  const hourlySeries = useMemo<HourlyBucket[]>(() => {
    if (backendComplaints.length === 0) return [];
    const buckets = new Map<string, HourlyBucket>();
    backendComplaints.forEach((c) => {
      if (!c.time || c.time === "—") return;
      if (!c.occurredAt) return;
      const hourKey = new Date(c.occurredAt).toISOString().slice(0, 13).replace("T", " ") + ":00 UTC";
      const existing = buckets.get(hourKey) || {
        h: hourKey,
        failed_transfer: 0,
        fraud_scam: 0,
        card_atm: 0,
        double_debit: 0,
        other: 0,
      };
      if (c.issue === "failed_transfer") existing.failed_transfer += 1;
      else if (c.issue === "fraud_scam" || c.isFraud) existing.fraud_scam += 1;
      else if (c.issue === "card_atm") existing.card_atm += 1;
      else if (c.issue === "double_debit" || c.issue === "pos") existing.double_debit += 1;
      else existing.other += 1;
      buckets.set(hourKey, existing);
    });
    return Array.from(buckets.values())
      .sort((a, b) => (a.h < b.h ? -1 : 1))
      .slice(-12);
  }, [backendComplaints]);

  const channelSplit = useMemo(() => {
    if (summary?.by_channel && Object.keys(summary.by_channel).length > 0) {
      return Object.entries(summary.by_channel)
        .map(([name, value]) => ({
          name:
            name === "in_app"
              ? "In-app"
              : name === "x"
              ? "X"
              : name.charAt(0).toUpperCase() + name.slice(1),
          value,
        }))
        .sort((a, b) => b.value - a.value);
    }
    const counts = new Map<string, number>();
    backendComplaints.forEach((c) => counts.set(c.channel, (counts.get(c.channel) || 0) + 1));
    return Array.from(counts.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [summary, backendComplaints]);

  const regionSplit = useMemo(() => {
    if (summary?.by_region && Object.keys(summary.by_region).length > 0) {
      return Object.entries(summary.by_region)
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value);
    }
    const counts = new Map<string, number>();
    backendComplaints.forEach((c) => counts.set(c.region, (counts.get(c.region) || 0) + 1));
    return Array.from(counts.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [summary, backendComplaints]);

  const rootCauses = useMemo(() => {
    const byIssue = summary?.by_issue_type || summary?.by_issue;
    if (byIssue && Object.keys(byIssue).length > 0) {
      return Object.entries(byIssue)
        .filter(([, v]) => v > 0)
        .map(([k, value]) => ({
          name: ISSUE_LABEL[k as IssueType] || k,
          value,
        }))
        .sort((a, b) => b.value - a.value);
    }
    const counts = new Map<string, number>();
    backendComplaints.forEach((c) => {
      const label = ISSUE_LABEL[c.issue] || c.issue;
      counts.set(label, (counts.get(label) || 0) + 1);
    });
    return Array.from(counts.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [summary, backendComplaints]);

  const detectTrend = useMemo(() => {
    if (trendBuckets.length > 0) {
      return trendBuckets.slice(-12).map((b) => ({
        d: new Date(b.bucket_start).toISOString().slice(0, 16).replace("T", " ") + " UTC",
        min: b.total_complaints,
      }));
    }
    return hourlySeries.map((h) => ({
      d: h.h,
      min: h.failed_transfer + h.fraud_scam + h.card_atm + h.double_debit + h.other,
    }));
  }, [trendBuckets, hourlySeries]);

  return (
    <C.Provider
      value={{
        decide,
        audit: auditEntries,
        complaints: backendComplaints,
        incidents: backendIncidents,
        transactionsAnalytics,
        summary,
        hourlySeries,
        channelSplit,
        regionSplit,
        rootCauses,
        detectTrend,
        addComplaint,
        pullSocialX,
        investigate,
        detectNow,
        syncing,
        user,
        isAuthenticated: Boolean(user),
        logoutUser,
        lastRefresh,
        isBackendLive,
        isLoading,
        refresh: fetchBackendData,
      }}
    >
      {children}
    </C.Provider>
  );
}
