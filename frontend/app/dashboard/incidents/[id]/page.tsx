"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  CheckCircle2,
  ClipboardCopy,
  MessageSquare,
  RefreshCw,
  Server,
  ShieldAlert,
} from "lucide-react";
import { buildIncidentFromBackend, useDash } from "@/components/dashboard/Provider";
import { Card, IssueBadge, PageHeader, Stat, Tag } from "@/components/dashboard/ui";
import { api, ApiError, type BackendIncident, type BackendDraft, type BackendAuditEntry, type IncidentTimelineItem } from "@/lib/api";
import { SpikeChart } from "@/components/dashboard/Charts";

export default function IncidentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <IncidentDetail key={id} id={id} />;
}

function IncidentDetail({ id }: { id: string }) {
  const { decide, complaints, investigate, isBackendLive, user } = useDash();
  const [detail, setDetail] = useState<{ incident: BackendIncident; drafts: BackendDraft[]; audit: BackendAuditEntry[]; timeline: IncidentTimelineItem[] } | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [pending, setPending] = useState(false);
  const canWrite = user?.role !== "manager";

  useEffect(() => {
    let active = true;
    async function load() {
      if (!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(id)) {
        setError("Incident not found.");
        return;
      }
      try {
        const incident = await api.getIncident(id);
        if (!active) return;
        const [drafts, audit, timeline] = await Promise.all([
          canWrite ? api.getIncidentDrafts(id).catch(() => []) : [],
          canWrite ? api.getIncidentAudit(id).catch(() => []) : [],
          api.getIncidentTimeline(id).then((result) => result.timeline).catch(() => null),
        ]);
        if (!active) return;
        setDetail({ incident, drafts, audit, timeline: timeline ?? [] });
        if (!timeline) setError("The reconciliation timeline could not be loaded.");
      } catch (err) {
        if (active) {
          setDetail(null);
          setError(err instanceof ApiError && err.status === 404 ? "Incident not found." : "Could not load the incident.");
        }
      }
    }
    void load();
    return () => { active = false; };
  }, [canWrite, id, revision]);

  const inc = detail && buildIncidentFromBackend(detail.incident, detail.drafts, detail.audit, complaints);
  if (!inc) {
    return (
      <Card className="p-8 text-center">
        <p className="text-navy/60 mb-3">
          {error || "Loading incident…"}
        </p>
        {error && <button type="button" className="mr-4 underline" onClick={() => { setError(""); setRevision((value) => value + 1); }}>Retry</button>}
        <Link href="/dashboard" className="text-flux font-semibold underline">
          Back to overview
        </Link>
      </Card>
    );
  }

  const runAction = async (action: () => Promise<void>) => {
    setPending(true);
    setError("");
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The action failed.");
    } finally {
      setRevision((value) => value + 1);
      setPending(false);
    }
  };

  const custDraftObj = inc.drafts?.find((dr) => dr.kind === "customer_message");
  const itDraftObj = inc.drafts?.find((dr) => dr.kind === "it_ticket");
  const revDraftObj = inc.drafts?.find((dr) => dr.kind === "reversal_request");

  return (
    <>
      <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-navy/60 hover:text-navy mb-4">
        <ArrowLeft className="w-4 h-4" />
        Overview
      </Link>
      <PageHeader
        title={inc.title}
        sub={`${inc.id.slice(0, 8)} · started ${inc.startedAt} · detected ${inc.detectedAt} · ${inc.region}`}
        right={
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => runAction(() => investigate(id))}
              disabled={pending || !canWrite}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-navy/5 hover:bg-navy/10 text-navy text-xs font-semibold transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${pending ? "animate-spin text-flux" : ""}`} />
              {pending ? "Running AI Investigator…" : "Re-run AI Investigation"}
            </button>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              {isBackendLive ? "Live Sync" : "Connecting"}
            </span>
            <IssueBadge i={inc.issue} />
            <Tag
              tone={
                inc.status === "active"
                  ? "flux"
                  : inc.status === "security"
                  ? "red"
                  : inc.status === "resolved"
                  ? "green"
                  : "navy"
              }
            >
              {inc.rawStatus || inc.status}
            </Tag>
          </div>
        }
      />

      {error && <p role="alert" className="mb-4 text-red-700">{error}</p>}
      <Card className="p-6 mb-4 border-l-4 !border-l-flux">
        <p className="text-xs font-semibold tracking-wider text-flux mb-2">
          AI ROOT-CAUSE SUMMARY
        </p>
        <p className="text-lg md:text-xl text-navy leading-relaxed" style={{ letterSpacing: "-0.01em" }}>
          {inc.summary}
        </p>
      </Card>

      <div className="grid sm:grid-cols-4 gap-4 mb-4">
        <Stat label="Complaints" value={String(inc.volume)} hint={inc.growth} />
        <Stat label="Channels" value={inc.channels.slice(0, 3).join(" + ") || "—"} hint="most affected" />
        <Stat label="Money at risk" value={inc.moneyAtRisk} hint="reported exposure" />
        <Stat label="Priority" value={`${inc.priority}/100`} hint="volume × growth" accent />
      </div>

      <Card className="p-6 mb-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-navy">Complaint Timeline</h3>
          <span className="text-sm text-navy/50">Attached complaints from the latest 500 records · UTC</span>
        </div>
        <SpikeChart
          series={inc.series}
          labels={inc.labels}
          releaseLabel={inc.releaseLabel}
        />
      </Card>

      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <Card className="p-6">
          <h3 className="font-semibold text-navy mb-4">Backend cause assessment</h3>
          {inc.causes.length === 0 ? (
            <p className="text-navy/50 text-sm">No backend cause assessment is available.</p>
          ) : (
            <div className="space-y-5">
              {inc.causes.map((c, i) => (
                <div key={`${c.name}-${i}`}>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="font-semibold text-navy">{c.name}</span>
                    <span className={(c.confidence ?? 100) < 50 ? "text-navy/50" : "text-flux font-semibold"}>
                      {c.confidence == null ? "Confidence unavailable" : `${c.confidence}%`}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-navy/5 overflow-hidden">
                    <motion.div
                      className={`h-full rounded-full ${i === 0 ? "bg-flux" : "bg-navy/30"}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${c.confidence ?? 0}%` }}
                      transition={{ duration: 0.9, delay: i * 0.12 }}
                    />
                  </div>
                  <p className="text-sm text-navy/55 mt-1.5">{c.evidence}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card className="p-6">
          <h3 className="font-semibold text-navy mb-4">Agent investigation trace</h3>
          {inc.trace.length === 0 ? (
            <p className="text-navy/50 text-sm">No agent tool calls recorded for this incident yet.</p>
          ) : (
            <ol className="space-y-3">
              {inc.trace.map((s, i) => (
                <motion.li
                  key={`${s.tool}-${i}`}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="flex gap-3"
                >
                  <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
                  <div className="min-w-0">
                    <p className="font-mono text-sm text-navy">
                      {s.tool}
                      <span className="text-navy/40">({s.args})</span>
                    </p>
                    <p className="text-sm text-navy/60">{s.result}</p>
                  </div>
                </motion.li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      <Card className="p-6 mb-4">
        <h3 className="font-semibold text-navy">Reconciliation timeline</h3>
        <p className="text-sm text-navy/60">System events are time correlations. Transaction entries are investigative candidates.</p>
        {detail?.timeline.length ? (
          <ol className="mt-3 space-y-2 text-sm">
            {detail.timeline.map((entry) => (
              <li key={`${entry.kind}-${entry.id}-${entry.at}`} className="break-all">
                <time dateTime={entry.at}>{entry.at}</time> · {entry.kind.replaceAll("_", " ")} · {entry.id}
                {[entry.status, entry.settlement_status, entry.association, entry.channel, entry.component, entry.event_type, entry.processor].filter(Boolean).map((value, index) => (
                  <span key={index}> · {value?.replaceAll("_", " ")}</span>
                ))}
              </li>
            ))}
          </ol>
        ) : <p className="mt-3 text-sm">No timeline entries available.</p>}
      </Card>

      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <Card className="p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-flux" />
              <h3 className="font-semibold text-navy">Draft customer message</h3>
            </div>
            {custDraftObj && (
              <Tag
                tone={
                  custDraftObj.status === "approved"
                    ? "green"
                    : custDraftObj.status === "rejected"
                    ? "red"
                    : "navy"
                }
              >
                {custDraftObj.status}
              </Tag>
            )}
          </div>
          {inc.customerDraft ? (
            <p className="text-navy/80 leading-relaxed bg-navy/[0.03] rounded-xl p-4">
              {inc.customerDraft}
            </p>
          ) : (
            <p className="text-navy/45">No customer message draft generated yet.</p>
          )}
        </Card>
        <Card className="p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-flux" />
              <h3 className="font-semibold text-navy">Draft IT ticket</h3>
            </div>
            {itDraftObj && (
              <Tag
                tone={
                  itDraftObj.status === "approved"
                    ? "green"
                    : itDraftObj.status === "rejected"
                    ? "red"
                    : "navy"
                }
              >
                {itDraftObj.status}
              </Tag>
            )}
          </div>
          {inc.itTicket ? (
            <pre className="whitespace-pre-wrap text-sm font-mono text-navy/80 bg-navy/[0.03] rounded-xl p-4">
              {inc.itTicket}
            </pre>
          ) : (
            <p className="text-navy/45">No IT ticket draft generated yet.</p>
          )}
        </Card>
      </div>

      {revDraftObj && (
        <Card className="p-5 mb-4 border border-amber-200 bg-amber-50/40">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <ShieldAlert className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
              <div>
                <h4 className="font-semibold text-navy text-sm">
                  Financial Guardrail · Reversal Request Batch
                </h4>
                <p className="text-sm text-navy/70 mt-1">{revDraftObj.content}</p>
              </div>
            </div>
            <Tag tone="flux">Requires Core-Banking Sign-Off</Tag>
          </div>
        </Card>
      )}

      <Card className="p-5">
        <h3 className="font-semibold">Communication decisions</h3>
        <p className="text-sm">Approval records the decision. Dispatch is processed separately.</p>
        {[custDraftObj, itDraftObj].map((draft, index) => (
          <div key={draft?.id ?? index} className="mt-3 flex flex-wrap items-center gap-3">
            <span>{index === 0 ? "Customer message" : "IT ticket"}</span>
            <Tag tone="navy">{draft?.status ?? "No draft"}</Tag>
            {draft?.status === "pending" && canWrite && (["approved", "rejected"] as const).map((decision) => (
              <button key={decision} type="button" disabled={pending} className="rounded-full border px-3 py-1 disabled:opacity-50"
                onClick={() => runAction(async () => {
                  const saved = await decide(draft.id, decision);
                  setDetail((current) => current && ({
                    ...current,
                    drafts: current.drafts.map((item) => item.id === saved.id ? saved : item),
                  }));
                })}>
                {decision === "approved" ? "Approve" : "Reject"}
              </button>
            ))}
          </div>
        ))}
      </Card>

      {inc.examples.length > 0 && (
        <Card className="p-6 mt-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-navy">Complaints attached to this incident</h3>
            <ClipboardCopy className="w-4 h-4 text-navy/35" />
          </div>
          <div className="grid md:grid-cols-3 gap-3">
            {inc.examples.map((e, idx) => (
              <p key={`${idx}-${e.slice(0, 12)}`} className="rounded-xl bg-navy/[0.03] p-4 text-sm text-navy/80">
                &ldquo;{e}&rdquo;
              </p>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}
