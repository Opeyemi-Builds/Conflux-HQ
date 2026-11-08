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
  type Role,
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
  role: Role;
  setRole: (r: Role) => void;
  phase: number;
  replaying: boolean;
  replay: () => Promise<void>;
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

const nowHHMM = () => {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

function formatTimeHHMM(iso?: string | null): string {
  if (!iso) return nowHHMM();
  try {
    const d = new Date(iso);
    if (!isNaN(d.getTime())) {
      return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    }
  } catch {}
  return nowHHMM();
}

function formatNaira(amount: number): string {
  if (amount >= 1_000_000) {
    return `₦${(amount / 1_000_000).toFixed(1)}m`;
  }
  if (amount >= 1_000) {
    return `₦${Math.round(amount).toLocaleString()}`;
  }
  return `₦${amount}`;
}

function formatLanguage(lang?: string | null): string {
  if (!lang) return "English";
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
  const issue: IssueType = (b.issue_type as IssueType) || (b.is_fraud ? "fraud_scam" : "failed_transfer");
  const severity: Severity = (b.severity as Severity) || (b.is_fraud ? "critical" : "medium");
  const sentiment: Sentiment = (b.sentiment as Sentiment) || "negative";
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
    region: b.region || "Lagos",
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
  const channelLabel = t.txn_channel?.toUpperCase() === "USSD" ? "USSD" : t.txn_channel ? t.txn_channel.charAt(0).toUpperCase() + t.txn_channel.slice(1) : "App";
  const typeLabel = t.txn_type ? t.txn_type.charAt(0).toUpperCase() + t.txn_type.slice(1) : "Transfer";
  const statusLabel = t.status === "failed" ? "Debited, not credited" : t.status;
  const revLabel = t.reversal_status === "pending" ? "Pending" : t.reversal_status === "reversed" ? "Reversed" : "Not started";
  return {
    id: t.id,
    ref: t.reference,
    time: formatTimeHHMM(t.occurred_at),
    type: typeLabel,
    channel: channelLabel,
    amount: `₦${amt.toLocaleString()}`,
    status: statusLabel,
    reversal: revLabel,
    switch: t.processor || "demo-switch-a",
    region: t.region || "Lagos",
  };
}

function mapBackendAudit(a: BackendAuditEntry): AuditEntry {
  const actorLower = (a.actor || "").toLowerCase();
  const actorLabel =
    actorLower === "system" || actorLower === "detector"
      ? "Detector"
      : actorLower.includes("agent") || a.action.startsWith("agent_") || a.action === "incident_investigated" || a.action === "draft_created"
      ? "Agent"
      : a.action === "draft_decided" || a.action === "demo_login" || a.action === "user_login"
      ? "Human"
      : "System";

  let detail = "";
  const d = a.details || {};
  if (a.action === "agent_tool_call") {
    detail = `${d.tool || "tool"}(${JSON.stringify(d.input || {})}) → ${d.summary || "verified"}`;
  } else if (a.action === "spike_detected") {
    detail = `${d.issue_type || "issue"} exceeded baseline (${d.count || 0} complaints vs baseline ${d.baseline || 1}).`;
  } else if (a.action === "incident_investigated") {
    detail = `Root cause ranked at ${Math.round(Number(d.confidence || 0.9) * 100)}% confidence (${d.source || "rules"} engine).`;
  } else if (a.action === "draft_created") {
    detail = `Generated ${d.kind || "response"} draft via ${d.source || "AI"} engine.`;
  } else if (a.action === "draft_decided") {
    detail = `Draft (${d.kind || "message"}) ${d.decision || "reviewed"} by operator.`;
  } else if (a.action === "synthetic_data_seeded") {
    detail = `Seeded ${d.complaints || 1000} complaints and ${d.transactions || 5000} transactions (seed ${d.seed || 42}).`;
  } else if (a.action === "text_classified" || a.action === "complaint_classified") {
    detail = `AI classified incoming complaint (${a.entity_id?.slice(0, 8) || "live"}).`;
  } else if (Object.keys(d).length > 0) {
    detail = Object.entries(d)
      .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
      .join(" · ")
      .slice(0, 160);
  } else {
    detail = `${a.entity_type || "record"} ${a.entity_id?.slice(0, 8) || ""}`.trim();
  }

  const phase =
    a.action === "synthetic_data_seeded" || a.action === "demo_login"
      ? 1
      : a.action === "spike_detected"
      ? 2
      : a.action === "agent_tool_call" || a.action === "incident_investigated"
      ? 3
      : 4;

  return {
    id: a.id,
    phase,
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
  const issue = (b.issue_type as IssueType) || "failed_transfer";
  const issueComplaints = allComplaints.filter((c) => c.incidentId === b.id || c.issue === issue);
  const allIssueComplaints = allComplaints.filter((c) => c.issue === issue);
  const totalExposure = allIssueComplaints.reduce((acc, c) => acc + (c.amount || 0), 0);

  // Build time series from complaints in 5-minute buckets around detection
  const bucketMap = new Map<string, number>();
  allIssueComplaints.slice(0, 120).forEach((c) => {
    const key = c.time;
    bucketMap.set(key, (bucketMap.get(key) || 0) + 1);
  });
  const sortedTimes = Array.from(bucketMap.keys()).sort();
  const series = sortedTimes.length >= 4 ? sortedTimes.slice(-16).map((k) => bucketMap.get(k) || 0) : [2, 3, 4, Math.max(8, Math.round(b.complaint_count * 0.4)), Math.max(15, Math.round(b.complaint_count * 0.75)), b.complaint_count];
  const labels = sortedTimes.length >= 4 ? sortedTimes.slice(-16) : undefined;

  // Map candidate causes from backend likely_cause + system events
  const confPct = Math.round((b.cause_confidence ?? 0.92) * 100);
  const causes: Cause[] = [];
  if (b.likely_cause) {
    causes.push({
      name: b.likely_cause.split(" preceded ")[0] || b.likely_cause,
      confidence: confPct,
      evidence: b.summary || b.likely_cause,
    });
  }
  events.forEach((ev, idx) => {
    const label = `${ev.event_type === "release" ? "Release" : "Maintenance"} ${ev.version || ""} on ${ev.component}`.trim();
    if (!causes.some((c) => c.name.includes(ev.component))) {
      causes.push({
        name: label,
        confidence: ev.event_type === "release" ? Math.max(65, confPct - 10) : Math.max(8, 18 - idx * 5),
        evidence: ev.description,
      });
    }
  });
  if (causes.length === 0) {
    causes.push({
      name: `${ISSUE_LABEL[issue]} anomaly cluster`,
      confidence: confPct,
      evidence: `${b.complaint_count} complaints exceeded baseline of ${b.baseline.toFixed(1)} (${b.growth_rate}× baseline).`,
    });
  }

  // Map trace steps from real audit log tool calls
  const toolLogs = auditRows.filter((r) => r.action === "agent_tool_call");
  const trace: TraceStep[] =
    toolLogs.length > 0
      ? toolLogs.map((r, idx) => {
          const d = r.details || {};
          return {
            phase: idx < 2 ? 2 : idx < 4 ? 3 : 4,
            tool: String(d.tool || "investigate_step"),
            args: JSON.stringify(d.input || {}).replace(/[{"}]/g, ""),
            result: String(d.summary || "Completed deterministic verification against bank ledger."),
          };
        })
      : [
          {
            phase: 2,
            tool: "get_incident_stats",
            args: b.id.slice(0, 8),
            result: `${b.complaint_count} complaints (${b.growth_rate}× baseline of ${b.baseline}).`,
          },
          {
            phase: 3,
            tool: "search_transactions",
            args: `issue=${b.issue_type}`,
            result: `Correlated complaint timestamps against failed switch transactions.`,
          },
          {
            phase: 4,
            tool: "create_drafts",
            args: `incident=${b.id.slice(0, 8)}`,
            result: `${drafts.length} operator drafts generated and awaiting human sign-off.`,
          },
        ];

  const custDraft = drafts.find((d) => d.kind === "customer_message");
  const itDraft = drafts.find((d) => d.kind === "it_ticket");
  const revDraft = drafts.find((d) => d.kind === "reversal_request");

  const channelsList =
    b.affected_channels && Object.keys(b.affected_channels).length > 0
      ? Object.keys(b.affected_channels).map((ch) => ch.toUpperCase().replace("_", "-"))
      : ["IN-APP", "X", "USSD"];

  const regionSet = Array.from(new Set(issueComplaints.map((c) => c.region).filter(Boolean))).slice(0, 3);
  const regionStr = regionSet.length > 0 ? regionSet.join(", ") : "Lagos, Abuja, Kano";

  const headline =
    b.summary ||
    `${ISSUE_LABEL[issue]} spike (${b.complaint_count} complaints, ${b.growth_rate}× baseline)`;

  return {
    id: b.id,
    title: `${ISSUE_LABEL[issue]} spiking across ${channelsList.slice(0, 2).join(" & ")}`,
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
    priority: b.priority_score || 80,
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
    releaseMarker: events.some((e) => e.event_type === "release"),
    causes,
    trace,
    summary: {
      agent:
        custDraft?.content ||
        `Customers reporting ${ISSUE_LABEL[issue].toLowerCase()} across ${channelsList.join(", ")}. Reassure customers that funds are safe and reversals are being processed.`,
      it:
        b.likely_cause ||
        `Investigate ${ISSUE_LABEL[issue].toLowerCase()} path across ${channelsList.join(", ")}. Check recent deployment and switch logs.`,
      management: `${headline} Estimated exposure across reported complaints: ${formatNaira(totalExposure)}.`,
    },
    customerDraft:
      custDraft?.content ||
      "We are aware of reports affecting transfers and are actively resolving pending reversals. Your funds remain safe.",
    itTicket:
      itDraft?.content ||
      `Incident: ${b.issue_type}\nComplaints: ${b.complaint_count} (${b.growth_rate}x baseline)\nLikely cause: ${b.likely_cause || "Under investigation"}`,
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
    examples: issueComplaints.slice(0, 4).map((c) => c.text),
  };
}

export default function DashboardProvider({ children }: { children: React.ReactNode }) {
  const [role, setRole] = useState<Role>("agent");
  const [phase, setPhase] = useState(4);
  const [replaying, setReplaying] = useState(false);
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
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const investigatedRef = useRef<Set<string>>(new Set());

  const fetchBackendData = useCallback(async () => {
    try {
      await api.getAuthToken();

      const [meRes, rawComplaints, rawIncidents, sumRes, trendsRes, txAnalyticsRes, txListRes, eventsRes, bankAuditRes] =
        await Promise.all([
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

      // Enrich each incident with its drafts & audit trace from backend
      let currentRawIncidents = rawIncidents || [];
      if (currentRawIncidents.length === 0 && mappedComplaints.length > 0) {
        // Trigger spike detection if database has complaints but detection hasn't run yet
        const latestOccurred = rawComplaints[0]?.occurred_at;
        currentRawIncidents = await api.detectSpikes(latestOccurred).catch(() => []);
      }

      const enrichedIncidents: Incident[] = await Promise.all(
        currentRawIncidents.map(async (inc) => {
          // Auto-investigate open uninvestigated incidents once so root-cause & drafts are ready
          if (!inc.likely_cause && !investigatedRef.current.has(inc.id)) {
            investigatedRef.current.add(inc.id);
            await api.investigateIncident(inc.id).catch(() => null);
            const refreshed = await api.getIncident(inc.id).catch(() => inc);
            inc = refreshed;
          }
          const [drafts, incAudit] = await Promise.all([
            api.getIncidentDrafts(inc.id).catch(() => [] as BackendDraft[]),
            api.getIncidentAudit(inc.id).catch(() => [] as BackendAuditEntry[]),
          ]);
          return buildIncidentFromBackend(inc, drafts, incAudit, mappedComplaints, eventsRes?.items || []);
        })
      );

      // Update decisions map from real draft statuses
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

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  // Auth actions
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

  // Replay scenario: seeds backend database, runs spike detection & AI investigation
  const replay = useCallback(async () => {
    if (timer.current) clearInterval(timer.current);
    setDecisions({});
    investigatedRef.current.clear();
    setPhase(0);
    setReplaying(true);

    try {
      const seeded = await api.seedScenario(true);
      const detected = await api.detectSpikes(seeded.detection_at);
      for (const inc of detected) {
        investigatedRef.current.add(inc.id);
        await api.investigateIncident(inc.id).catch(() => null);
      }
      await fetchBackendData();
    } catch (err) {
      console.warn("Scenario replay error:", err);
    }

    let p = 0;
    timer.current = setInterval(() => {
      p += 1;
      setPhase(p);
      if (p >= 4 && timer.current) {
        clearInterval(timer.current);
        setReplaying(false);
      }
    }, 1800);
  }, [fetchBackendData]);

  // Trigger AI investigation on a specific incident
  const investigate = useCallback(
    async (incidentId: string) => {
      await api.investigateIncident(incidentId);
      await fetchBackendData();
    },
    [fetchBackendData]
  );

  // Human-in-the-loop decision on drafts for an incident
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

  // Real-time complaint ingestion
  const addComplaint = useCallback(
    async (c: Partial<Complaint> & { text: string }) => {
      const channelBackend =
        c.channel?.toLowerCase() === "in-app"
          ? "in_app"
          : c.channel?.toLowerCase() || "in_app";
      await api.ingestComplaint({
        text: c.text,
        channel: channelBackend,
        region: c.region || "Lagos",
        language: c.language?.toLowerCase() || "en",
        issue_type: c.issue,
      });
      await api.drainJobs().catch(() => null);
      await fetchBackendData();
    },
    [fetchBackendData]
  );

  // Pull live/recorded X mentions from backend social adapter
  const pullSocialX = useCallback(async () => {
    const res = await api.pullXPosts(15);
    await fetchBackendData();
    return { fetched: res.fetched, ingested: res.ingested };
  }, [fetchBackendData]);

  // Compute hourly stacked series from real backend complaints
  const hourlySeries = useMemo<HourlyBucket[]>(() => {
    if (backendComplaints.length === 0) return [];
    const buckets = new Map<string, HourlyBucket>();
    // Group complaints by hour HH:00
    backendComplaints.forEach((c) => {
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

  // Compute channel split from summary or live complaints
  const channelSplit = useMemo(() => {
    if (summary?.by_channel && Object.keys(summary.by_channel).length > 0) {
      return Object.entries(summary.by_channel)
        .map(([name, value]) => ({
          name: name === "in_app" ? "In-app" : name === "x" ? "X" : name.charAt(0).toUpperCase() + name.slice(1),
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

  // Compute region split from summary or live complaints
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

  // Compute issue / root cause breakdown from summary or live complaints
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

  // Compute trend line from backend trend buckets
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
        role,
        setRole,
        phase,
        replaying,
        replay,
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
