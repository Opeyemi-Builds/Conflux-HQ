"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { AuditEntry, Complaint, Decision, Role, Incident, Channel, IssueType, Severity, Sentiment } from "@/lib/types";
import { auditSeed, seedComplaints, incidents as initialIncidents } from "@/lib/mock";
import { api, BackendComplaint, BackendIncident, BackendAnalyticsSummary } from "@/lib/api";

interface Ctx {
  role: Role;
  setRole: (r: Role) => void;
  phase: number;
  replaying: boolean;
  replay: () => void;
  decisions: Record<string, Decision>;
  decide: (id: string, d: Exclude<Decision, "pending">) => void;
  audit: AuditEntry[];
  complaints: Complaint[];
  incidents: Incident[];
  summary: BackendAnalyticsSummary | null;
  addComplaint: (c: Partial<Complaint> & { text: string }) => Promise<void>;
  isBackendLive: boolean;
  refresh: () => Promise<void>;
}

const C = createContext<Ctx | null>(null);

export const useDash = () => {
  const v = useContext(C);
  if (!v) throw new Error("useDash outside provider");
  return v;
};

const now = () => {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

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

  let timeStr = now();
  try {
    const d = new Date(b.occurred_at || b.created_at);
    if (!isNaN(d.getTime())) {
      timeStr = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    }
  } catch {}

  const issue: IssueType = (b.issue_type as IssueType) || (b.is_fraud ? "fraud_scam" : "failed_transfer");
  const severity: Severity = (b.severity as Severity) || (b.is_fraud ? "critical" : "high");
  const sentiment: Sentiment = (b.sentiment as Sentiment) || "negative";

  return {
    id: b.id.length > 8 ? `C-${b.id.slice(0, 4)}` : b.id,
    time: timeStr,
    channel,
    text: b.masked_text || b.text,
    issue,
    severity,
    sentiment,
    language: b.language ? (b.language.charAt(0).toUpperCase() + b.language.slice(1)) : "English",
    region: b.region || "Lagos",
    ref: (b as unknown as { customer_ref?: string }).customer_ref ? `****${(b as unknown as { customer_ref?: string }).customer_ref!.slice(-4)}` : "****4471",
  };
}

function mapBackendIncident(b: BackendIncident): Incident {
  return {
    id: b.id,
    title: b.summary || `${b.issue_type.replace(/_/g, " ").toUpperCase()} spike detected`,
    issue: (b.issue_type as IssueType) || "failed_transfer",
    status: b.status === "open" || b.status === "active" ? "active" : b.status === "investigating" ? "monitoring" : "active",
    priority: b.priority_score || 85,
    startedAt: b.started_at ? new Date(b.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "10:12",
    detectedAt: b.detected_at ? new Date(b.detected_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "10:15",
    volume: b.complaint_count || 30,
    growth: b.growth_rate ? `${b.growth_rate.toFixed(1)}x baseline` : "15x baseline",
    channels: b.affected_channels ? Object.keys(b.affected_channels).map((c) => c.toUpperCase()) : ["USSD", "APP"],
    region: "Lagos, Abuja, Kano",
    moneyAtRisk: "₦48.2m",
    series: [3, 4, 3, 5, 4, 3, 4, 4, 6, 22, 38, 52, 60, 57, 49, 43, 38, 33, 30],
    releaseMarker: true,
    causes: b.likely_cause
      ? [{ name: b.likely_cause, confidence: Math.round((b.cause_confidence || 0.87) * 100), evidence: "Detected by AI Root-Cause analyzer." }]
      : [{ name: "App release v4.2.1 (10:00)", confidence: 87, evidence: "Failure rate on app/USSD rose from 1.1% to 38% after deploy." }],
    trace: [
      { phase: 2, tool: "get_incident_stats", args: b.id.slice(0, 8), result: `${b.complaint_count} complaints detected by auto-correlator.` },
      { phase: 3, tool: "compare_baseline", args: b.issue_type, result: `Baseline exceeded by ${(b.growth_rate || 12).toFixed(1)}x.` },
      { phase: 4, tool: "draft_message", args: "customer, IT", result: "Draft holding messages created and waiting for sign-off." },
    ],
    summary: {
      agent: "Customers on USSD and the app are experiencing delays and debit discrepancies. Tell them money is secure and auto-reversals are running.",
      it: b.likely_cause || "Release v4.2.1 at 10:00 is suspect. Check switch callbacks and consider rollback.",
      management: `${b.complaint_count} complaints detected in window. Automated holding notices queued for operator sign-off.`,
    },
    customerDraft: "We are aware that some transfers did not complete and your account may have been debited. Your money is safe. Any failed transfer will be automatically reversed.",
    itTicket: `[P1] ${b.issue_type} spike - detected at ${b.detected_at || "10:15"}. Review upstream switch routing and rollback options.`,
    examples: ["my money don enter nowhere since morning", "Transfer failed on app but I was charged. Ref ending 4471"],
  };
}

export default function DashboardProvider({ children }: { children: React.ReactNode }) {
  const [role, setRole] = useState<Role>("agent");
  const [phase, setPhase] = useState(4);
  const [replaying, setReplaying] = useState(false);
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [human, setHuman] = useState<AuditEntry[]>([]);
  const [fresh, setFresh] = useState<Complaint[]>([]);
  const [backendComplaints, setBackendComplaints] = useState<Complaint[]>([]);
  const [backendIncidents, setBackendIncidents] = useState<Incident[]>([]);
  const [summary, setSummary] = useState<BackendAnalyticsSummary | null>(null);
  const [isBackendLive, setIsBackendLive] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch real-time data from FastAPI
  const fetchBackendData = useCallback(async () => {
    try {
      // 1. Auth check
      await api.getAuthToken();

      // 2. Fetch live complaints (up to 300 latest)
      const rawComplaints = await api.getComplaints({ limit: 300 });
      if (rawComplaints && Array.isArray(rawComplaints) && rawComplaints.length > 0) {
        const mapped = rawComplaints.map(mapBackendComplaint);
        setBackendComplaints(mapped);
      }

      // 3. Fetch live incidents
      const rawIncidents = await api.getIncidents();
      if (rawIncidents && Array.isArray(rawIncidents) && rawIncidents.length > 0) {
        const mappedInc = rawIncidents.map(mapBackendIncident);
        // Merge with initial template if helpful
        setBackendIncidents(mappedInc);
      }

      // 4. Fetch live analytics summary
      const sum = await api.getSummary(48);
      if (sum) {
        setSummary(sum);
      }

      setIsBackendLive(true);
    } catch (err) {
      // Silently fall back to seed data if server is restarting
      console.warn("Backend real-time sync:", err);
      setIsBackendLive(false);
    }
  }, []);

  // Poll backend every 4 seconds for real-time live data
  useEffect(() => {
    let active = true;
    const run = () => {
      if (active) {
        fetchBackendData();
      }
    };
    const initialTimer = setTimeout(run, 0);
    const interval = setInterval(run, 4000);
    return () => {
      active = false;
      clearTimeout(initialTimer);
      clearInterval(interval);
    };
  }, [fetchBackendData]);

  // Clean up replay timer
  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  // Replay scenario (triggers backend seed and detection)
  const replay = useCallback(async () => {
    if (timer.current) clearInterval(timer.current);
    setDecisions({});
    setHuman([]);
    setPhase(0);
    setReplaying(true);

    try {
      await api.seedScenario(true);
      await api.detectSpikes();
      await fetchBackendData();
    } catch (err) {
      console.warn("Scenario seeding:", err);
    }

    let p = 0;
    timer.current = setInterval(() => {
      p += 1;
      setPhase(p);
      if (p >= 4 && timer.current) {
        clearInterval(timer.current);
        setReplaying(false);
      }
    }, 2600);
  }, [fetchBackendData]);

  // Human in the loop decision
  const decide = useCallback((id: string, d: Exclude<Decision, "pending">) => {
    setDecisions((s) => ({ ...s, [id]: d }));
    setHuman((h) => [
      ...h,
      {
        phase: 4,
        time: now(),
        actor: "Human",
        action: d === "approved" ? "Approved" : "Rejected",
        detail: `${id}: Customer holding message & auto-reversals ${d}.`,
      },
    ]);

    // Async decision dispatch to backend if a draft UUID matches
    api.decideDraft(id, d).catch(() => {});
  }, []);

  // Real-time complaint ingestion
  const addComplaint = useCallback(async (c: Partial<Complaint> & { text: string }) => {
    const opt: Complaint = {
      id: c.id || `C-${Date.now().toString().slice(-4)}`,
      time: c.time || now(),
      channel: c.channel || "In-app",
      text: c.text,
      issue: c.issue || "failed_transfer",
      severity: c.severity || "high",
      sentiment: c.sentiment || "negative",
      language: c.language || "English",
      region: c.region || "Lagos",
      ref: c.ref || "****0000",
      fresh: true,
    };
    setFresh((f) => [opt, ...f]);

    try {
      const channelBackend = (c.channel?.toLowerCase() === "in-app" ? "in_app" : c.channel?.toLowerCase()) || "in_app";
      await api.ingestComplaint({
        text: c.text,
        channel: channelBackend,
        region: c.region || "Lagos",
      });
      setTimeout(() => {
        fetchBackendData();
      }, 500);
    } catch (err) {
      console.warn("Backend ingestion:", err);
    }
  }, [fetchBackendData]);

  // Merge complaints: optimistic fresh + live backend complaints (or fallback to seedComplaints)
  const complaints = useMemo(() => {
    const baseList = backendComplaints.length > 0 ? backendComplaints : seedComplaints;
    return [...fresh, ...baseList];
  }, [fresh, backendComplaints]);

  // Merge incidents: live backend incidents with rich initial mock templates
  const incidents = useMemo(() => {
    if (backendIncidents.length > 0) {
      // Keep any synthetic demo incidents INC-0421, INC-0422 for the scenario replay if not present
      const combined = [...backendIncidents];
      for (const inc of initialIncidents) {
        if (!combined.some((x) => x.id === inc.id)) {
          combined.push(inc);
        }
      }
      return combined;
    }
    return initialIncidents;
  }, [backendIncidents]);

  // Audit trail
  const audit = useMemo(() => {
    return [...auditSeed.filter((a) => a.phase <= phase), ...human].reverse();
  }, [phase, human]);

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
        audit,
        complaints,
        incidents,
        summary,
        addComplaint,
        isBackendLive,
        refresh: fetchBackendData,
      }}
    >
      {children}
    </C.Provider>
  );
}
