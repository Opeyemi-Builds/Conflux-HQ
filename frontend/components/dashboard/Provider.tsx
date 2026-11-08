"use client";
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
  type TraceStep,
  type Txn,
} from "@/lib/types";
import {
  api,
  type BackendAnalyticsSummary,
  type BackendAuditEntry,
  type BackendComplaint,
  type BackendDraft,
  type BackendIncident,
  type BackendSystemEvent,
  type BackendTransactionItem,
  type BackendTransactionsAnalytics,
  type BackendTrendBucket,
  type BackendUser,
} from "@/lib/api";

interface Ctx {
  decisions: Record<string, Decision>;
  decide: (id: string, d: Exclude<Decision, "pending">, draftId?: string) => Promise<void>;
  audit: AuditEntry[];
  complaints: Complaint[];
  incidents: Incident[];
  transactions: Txn[];
  transactionsAnalytics: BackendTransactionsAnalytics | null;
  systemEvents: BackendSystemEvent[];
  summary: BackendAnalyticsSummary | null;
  hourlySeries: HourlyBucket[];
  channelSplit: { name: string; value: number }[];
  regionSplit: { name: string; value: number }[];
  rootCauses: { name: string; value: number }[];
  detectTrend: { d: string; min: number }[];
  addComplaint: (c: Partial<Complaint> & { text: string }) => Promise<void>;
  pullSocialX: () => Promise<{ fetched: number; ingested: number }>;
  investigate: (incidentId: string) => Promise<void>;
  detectNow: () => Promise<void>;
  syncing: boolean;
  user: BackendUser | null;
  isAuthenticated: boolean;
  loginUser: (identifier: string, password: string) => Promise<BackendUser | null>;
  registerBankTenant: (payload: {
    bank_name: string;
    cac_number?: string;
    country?: string;
    admin_full_name: string;
    email: string;
    password: string;
  }) => Promise<BackendUser | null>;
  logoutUser: () => void;
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

function mapBackendComplaint(b: BackendComplaint): Complaint {
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
  const severity: Severity = (b.severity as Severity) || "low";
  const sentiment: Sentiment = (b.sentiment as Sentiment) || "neutral";
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
    isFraud: Boolean(b.is_fraud || issue === "fraud_scam"),
    confidence: b.classification_confidence,
    transactionId: b.transaction_id,
    incidentId: b.incident_id,
  };
}

function mapBackendTransaction(t: BackendTransactionItem): Txn {
  const amt = Number(t.amount || 0);
  const channelLabel =
    t.txn_channel?.toUpperCase() === "USSD"
      ? "USSD"
      : t.txn_channel
      ? t.txn_channel.charAt(0).toUpperCase() + t.txn_channel.slice(1)
      : "—";
  const typeLabel = t.txn_type
    ? t.txn_type.charAt(0).toUpperCase() + t.txn_type.slice(1)
    : "—";
  const statusLabel = t.status === "failed" ? "Debited, not credited" : t.status;
  const revLabel =
    t.reversal_status === "pending"
      ? "Pending"
      : t.reversal_status === "reversed"
      ? "Reversed"
      : t.reversal_status || "—";
  return {
    id: t.id,
    ref: t.reference,
    time: formatTimeHHMM(t.occurred_at),
    type: typeLabel,
    channel: channelLabel,
    amount: `₦${amt.toLocaleString()}`,
    status: statusLabel,
    reversal: revLabel,
    switch: t.processor || "—",
    region: t.region || "—",
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
    detail = `${d.tool || "tool"}(${JSON.stringify(d.input || {})}) → ${d.summary || ""}`;
  } else if (a.action === "spike_detected") {
    detail = `${d.issue_type || "issue"} exceeded baseline (${d.count || 0} complaints vs baseline ${d.baseline || 0}).`;
  } else if (a.action === "incident_investigated") {
    detail = `Root cause ranked at ${Math.round(Number(d.confidence || 0) * 100)}% confidence (${d.source || "AI"}).`;
  } else if (a.action === "draft_created") {
    detail = `Generated ${d.kind || "response"} draft (${d.source || "AI"}).`;
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

function buildIncidentFromBackend(
  b: BackendIncident,
  drafts: BackendDraft[],
  auditRows: BackendAuditEntry[],
  allComplaints: Complaint[],
  events: BackendSystemEvent[]
): Incident {
  const issue = (b.issue_type as IssueType) || "other";
  const issueComplaints = allComplaints.filter((c) => c.incidentId === b.id || c.issue === issue);
  const totalExposure = issueComplaints.reduce((acc, c) => acc + (c.amount || 0), 0);

  // Build time series strictly from backend complaint timestamps
  const bucketMap = new Map<string, number>();
  issueComplaints.forEach((c) => {
    if (c.time && c.time !== "—") {
      bucketMap.set(c.time, (bucketMap.get(c.time) || 0) + 1);
    }
  });
  const sortedTimes = Array.from(bucketMap.keys()).sort().slice(-16);
  const series = sortedTimes.map((k) => bucketMap.get(k) || 0);
  const labels = sortedTimes;

  const confPct = b.cause_confidence != null ? Math.round(b.cause_confidence * 100) : 0;
  const causes: Cause[] = [];
  if (b.likely_cause) {
    causes.push({
      name: b.likely_cause.split(" preceded ")[0] || b.likely_cause,
      confidence: confPct,
      evidence: b.summary || b.likely_cause,
    });
  }
  events.forEach((ev) => {
    const label = `${ev.event_type.toUpperCase()} ${ev.version || ""} · ${ev.component}`.trim();
    if (!causes.some((c) => c.name.includes(ev.component))) {
      causes.push({
        name: label,
        confidence: ev.event_type === "release" ? Math.max(50, confPct - 10) : 10,
        evidence: ev.description,
      });
    }
  });

  const toolLogs = auditRows.filter((r) => r.action === "agent_tool_call");
  const trace: TraceStep[] = toolLogs.map((r) => {
    const d = r.details || {};
    return {
      tool: String(d.tool || r.action),
      args: JSON.stringify(d.input || {}).replace(/[{"}]/g, ""),
      result: String(d.summary || ""),
    };
  });

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

  const releaseEv = events.find((e) => e.event_type === "release");

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
    releaseLabel: releaseEv ? `${releaseEv.component} ${releaseEv.version || ""}`.trim() : undefined,
    causes,
    trace,
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
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [backendComplaints, setBackendComplaints] = useState<Complaint[]>([]);
  const [backendIncidents, setBackendIncidents] = useState<Incident[]>([]);
  const [transactions, setTransactions] = useState<Txn[]>([]);
  const [transactionsAnalytics, setTransactionsAnalytics] = useState<BackendTransactionsAnalytics | null>(null);
  const [systemEvents, setSystemEvents] = useState<BackendSystemEvent[]>([]);
  const [trendBuckets, setTrendBuckets] = useState<BackendTrendBucket[]>([]);
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [summary, setSummary] = useState<BackendAnalyticsSummary | null>(null);
  const [user, setUser] = useState<BackendUser | null>(null);
  const [isBackendLive, setIsBackendLive] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const investigatedRef = useRef<Set<string>>(new Set());

  const fetchBackendData = useCallback(async () => {
    try {
      await api.getAuthToken();

      const [
        meRes,
        rawComplaints,
        rawIncidents,
        sumRes,
        trendsRes,
        txAnalyticsRes,
        txListRes,
        eventsRes,
        bankAuditRes,
      ] = await Promise.all([
        api.getMe().catch(() => null),
        api.getComplaints({ limit: 500 }),
        api.getIncidents(),
        api.getSummary(72),
        api.getTrends(72).catch(() => null),
        api.getTransactionsAnalytics(72).catch(() => null),
        api.getTransactions({ status: "failed", limit: 25 }).catch(() => ({ total: 0, items: [] })),
        api.getSystemEvents(20).catch(() => ({ items: [] })),
        api.getBankAudit(120).catch(() => []),
      ]);

      if (meRes) setUser(meRes);

      const mappedComplaints = (rawComplaints || []).map(mapBackendComplaint);
      setBackendComplaints(mappedComplaints);

      if (sumRes) setSummary(sumRes);
      if (trendsRes?.buckets) setTrendBuckets(trendsRes.buckets);
      if (txAnalyticsRes) setTransactionsAnalytics(txAnalyticsRes);
      if (txListRes?.items) setTransactions(txListRes.items.map(mapBackendTransaction));
      if (eventsRes?.items) setSystemEvents(eventsRes.items);
      if (bankAuditRes) setAuditEntries(bankAuditRes.map(mapBackendAudit));

      let currentRawIncidents = rawIncidents || [];
      if (currentRawIncidents.length === 0 && mappedComplaints.length > 0) {
        const latestOccurred = rawComplaints[0]?.occurred_at;
        currentRawIncidents = await api.detectSpikes(latestOccurred).catch(() => []);
      }

      const enrichedIncidents: Incident[] = await Promise.all(
        currentRawIncidents.map(async (inc) => {
          if (!inc.likely_cause && !investigatedRef.current.has(inc.id)) {
            investigatedRef.current.add(inc.id);
            await api.investigateIncident(inc.id).catch(() => null);
            inc = await api.getIncident(inc.id).catch(() => inc);
          }
          const [drafts, incAudit] = await Promise.all([
            api.getIncidentDrafts(inc.id).catch(() => [] as BackendDraft[]),
            api.getIncidentAudit(inc.id).catch(() => [] as BackendAuditEntry[]),
          ]);
          return buildIncidentFromBackend(inc, drafts, incAudit, mappedComplaints, eventsRes?.items || []);
        })
      );

      const nextDecisions: Record<string, Decision> = {};
      enrichedIncidents.forEach((inc) => {
        if (inc.drafts && inc.drafts.length > 0) {
          const allApproved = inc.drafts.every((d) => d.status === "approved");
          const anyRejected = inc.drafts.some((d) => d.status === "rejected");
          const cust = inc.drafts.find((d) => d.kind === "customer_message");
          nextDecisions[inc.id] = allApproved
            ? "approved"
            : anyRejected
            ? "rejected"
            : cust?.status || "pending";
          inc.drafts.forEach((d) => {
            nextDecisions[d.id] = d.status;
          });
        }
      });
      setDecisions((prev) => ({ ...prev, ...nextDecisions }));
      setBackendIncidents(enrichedIncidents);
      setIsBackendLive(true);
      setIsLoading(false);
    } catch (err) {
      console.warn("Backend real-time sync error:", err);
      setIsBackendLive(false);
      setIsLoading(false);
    }
  }, []);

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

  const loginUser = useCallback(
    async (identifier: string, password: string): Promise<BackendUser | null> => {
      const res = await api.login(identifier, password);
      const me = res.user || (await api.getMe().catch(() => null));
      if (me) setUser(me);
      await fetchBackendData();
      return me;
    },
    [fetchBackendData]
  );

  const registerBankTenant = useCallback(
    async (payload: {
      bank_name: string;
      cac_number?: string;
      country?: string;
      admin_full_name: string;
      email: string;
      password: string;
    }): Promise<BackendUser | null> => {
      const res = await api.registerBank(payload);
      const me = res.user || (await api.getMe().catch(() => null));
      if (me) setUser(me);
      await fetchBackendData();
      return me;
    },
    [fetchBackendData]
  );

  const logoutUser = useCallback(() => {
    api.logout();
    setUser(null);
  }, []);

  // Run live spike detection & refresh backend state
  const detectNow = useCallback(async () => {
    setSyncing(true);
    try {
      const latestOccurred = backendComplaints[0]?.occurredAt;
      await api.detectSpikes(latestOccurred);
      await api.drainJobs().catch(() => null);
      await fetchBackendData();
    } catch (err) {
      console.warn("Spike detection error:", err);
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
    async (id: string, d: Exclude<Decision, "pending">, specificDraftId?: string) => {
      setDecisions((s) => ({ ...s, [id]: d, ...(specificDraftId ? { [specificDraftId]: d } : {}) }));

      try {
        if (specificDraftId) {
          await api.decideDraft(specificDraftId, d);
        } else {
          const targetInc = backendIncidents.find((i) => i.id === id);
          const pendingDrafts = (targetInc?.drafts || []).filter(
            (dr) => dr.status === "pending" && dr.kind !== "reversal_request"
          );
          await Promise.all(pendingDrafts.map((dr) => api.decideDraft(dr.id, d).catch(() => null)));
        }
        await api.drainJobs().catch(() => null);
        await fetchBackendData();
      } catch (err) {
        console.warn("Draft decision error:", err);
      }
    },
    [backendIncidents, fetchBackendData]
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
        language: c.language?.toLowerCase(),
        issue_type: c.issue,
      });
      await api.drainJobs().catch(() => null);
      await fetchBackendData();
    },
    [fetchBackendData]
  );

  const pullSocialX = useCallback(async () => {
    const res = await api.pullXPosts(15);
    await fetchBackendData();
    return { fetched: res.fetched, ingested: res.ingested };
  }, [fetchBackendData]);

  const hourlySeries = useMemo<HourlyBucket[]>(() => {
    if (backendComplaints.length === 0) return [];
    const buckets = new Map<string, HourlyBucket>();
    backendComplaints.forEach((c) => {
      if (!c.time || c.time === "—") return;
      const hourKey = `${c.time.slice(0, 2)}:00`;
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
        d: formatTimeHHMM(b.bucket_start),
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
        decisions,
        decide,
        audit: auditEntries,
        complaints: backendComplaints,
        incidents: backendIncidents,
        transactions,
        transactionsAnalytics,
        systemEvents,
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
        loginUser,
        registerBankTenant,
        logoutUser,
        isBackendLive,
        isLoading,
        refresh: fetchBackendData,
      }}
    >
      {children}
    </C.Provider>
  );
}
