"use client";
import { use, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Check,
  CheckCircle2,
  ClipboardCopy,
  Loader2,
  MessageSquare,
  RefreshCw,
  Server,
  ShieldAlert,
  X,
} from "lucide-react";
import { useDash } from "@/components/dashboard/Provider";
import { Card, IssueBadge, PageHeader, Stat, Tag, Td, TableWrap, Th } from "@/components/dashboard/ui";
import { SpikeChart } from "@/components/dashboard/Charts";

export default function IncidentPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const routeParams = useParams();
  const id = resolvedParams?.id ?? (routeParams?.id as string);
  const { role, phase, decisions, decide, incidents, transactions, investigate, isBackendLive, isLoading } = useDash();
  const [investigating, setInvestigating] = useState(false);
  const [deciding, setDeciding] = useState(false);

  const inc = incidents.find((i) => i.id === id) || incidents[0];

  if (!inc) {
    return (
      <Card className="p-8 text-center">
        <p className="text-navy/60 mb-3">
          {isLoading ? "Loading incident from FastAPI backend…" : "No active incident found in the database."}
        </p>
        <Link href="/dashboard" className="text-flux font-semibold underline">
          Back to overview
        </Link>
      </Card>
    );
  }

  const d = decisions[inc.id] ?? (inc.status === "resolved" ? "approved" : "pending");
  const ready = phase >= 4;
  const needsMoney = inc.issue === "failed_transfer" || inc.issue === "double_debit" || inc.issue === "pos" || inc.issue === "card_atm";

  const handleInvestigate = async () => {
    setInvestigating(true);
    try {
      await investigate(inc.id);
    } finally {
      setInvestigating(false);
    }
  };

  const handleDecision = async (decision: "approved" | "rejected", draftId?: string) => {
    setDeciding(true);
    try {
      await decide(inc.id, decision, draftId);
    } finally {
      setDeciding(false);
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
              onClick={handleInvestigate}
              disabled={investigating}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-navy/5 hover:bg-navy/10 text-navy text-xs font-semibold transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${investigating ? "animate-spin text-flux" : ""}`} />
              {investigating ? "Running AI Investigator…" : "Re-run AI Investigation"}
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

      <Card className="p-6 mb-4 border-l-4 !border-l-flux">
        <p className="text-xs font-semibold tracking-wider text-flux mb-2">
          {role === "agent"
            ? "FOR CUSTOMER SERVICE"
            : role === "it"
            ? "FOR IT / ENGINEERING"
            : "FOR MANAGEMENT"}
        </p>
        <p className="text-lg md:text-xl text-navy leading-relaxed" style={{ letterSpacing: "-0.01em" }}>
          {phase >= 3
            ? inc.summary[role]
            : "AI Agent is investigating system events and switch logs…"}
        </p>
      </Card>

      <div className="grid sm:grid-cols-4 gap-4 mb-4">
        <Stat label="Complaints" value={String(inc.volume)} hint={inc.growth} />
        <Stat label="Channels" value={inc.channels.slice(0, 3).join(" + ")} hint="most affected" />
        <Stat label="Money at risk" value={inc.moneyAtRisk} hint="reported exposure" />
        <Stat label="Priority" value={`${inc.priority}/100`} hint="volume × growth" accent />
      </div>

      <Card className="p-6 mb-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-navy">Complaint Timeline</h3>
          <span className="text-sm text-navy/50">Live database bucket distribution</span>
        </div>
        <SpikeChart
          series={inc.series}
          labels={inc.labels}
          phase={phase}
          release={inc.releaseMarker}
        />
      </Card>

      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <Card className="p-6">
          <h3 className="font-semibold text-navy mb-4">Candidate causes (AI Ranked)</h3>
          {phase < 3 ? (
            <p className="text-navy/50 flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Checking release and outage logs…
            </p>
          ) : (
            <div className="space-y-5">
              {inc.causes.map((c, i) => (
                <div key={`${c.name}-${i}`}>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="font-semibold text-navy">{c.name}</span>
                    <span className={c.confidence < 50 ? "text-navy/50" : "text-flux font-semibold"}>
                      {c.confidence}%{c.confidence < 50 ? " · low confidence" : ""}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-navy/5 overflow-hidden">
                    <motion.div
                      className={`h-full rounded-full ${i === 0 ? "bg-flux" : "bg-navy/30"}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${c.confidence}%` }}
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
          <ol className="space-y-3">
            {inc.trace
              .filter((s) => s.phase <= phase)
              .map((s, i) => (
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
            {phase < 4 && (
              <li className="flex gap-3 text-navy/45 text-sm">
                <Loader2 className="w-5 h-5 animate-spin shrink-0" />
                Working…
              </li>
            )}
          </ol>
        </Card>
      </div>

      {needsMoney && phase >= 3 && transactions.length > 0 && (
        <Card className="mb-4 overflow-hidden">
          <div className="px-6 pt-5 pb-2 flex items-center justify-between">
            <h3 className="font-semibold text-navy">Matched failed transactions from switch ledger</h3>
            <Tag tone="flux">{transactions.length} failed records shown</Tag>
          </div>
          <TableWrap>
            <thead className="bg-navy/[0.03]">
              <tr>
                <Th>Ref</Th>
                <Th>Time</Th>
                <Th>Channel</Th>
                <Th>Amount</Th>
                <Th>Status</Th>
                <Th>Reversal</Th>
                <Th>Switch</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-navy/5">
              {transactions.slice(0, 10).map((t) => (
                <tr key={t.id || t.ref} className="hover:bg-navy/[0.02]">
                  <Td className="font-mono">{t.ref}</Td>
                  <Td>{t.time}</Td>
                  <Td>{t.channel}</Td>
                  <Td className="font-semibold">{t.amount}</Td>
                  <Td>
                    <Tag tone="red">{t.status}</Tag>
                  </Td>
                  <Td>{t.reversal}</Td>
                  <Td>{t.switch}</Td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        </Card>
      )}

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
          {ready ? (
            <p className="text-navy/80 leading-relaxed bg-navy/[0.03] rounded-xl p-4">
              {inc.customerDraft}
            </p>
          ) : (
            <p className="text-navy/45">Not drafted yet.</p>
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
          {ready ? (
            <pre className="whitespace-pre-wrap text-sm font-mono text-navy/80 bg-navy/[0.03] rounded-xl p-4">
              {inc.itTicket}
            </pre>
          ) : (
            <p className="text-navy/45">Not drafted yet.</p>
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

      <Card className="p-5 sticky bottom-4 shadow-[0_20px_50px_-20px_rgba(20,35,63,.35)]">
        <div className="flex flex-wrap items-center gap-4 justify-between">
          <div>
            <p className="font-semibold text-navy">
              {d === "pending"
                ? "Waiting for human approval"
                : d === "approved"
                ? "Approved and dispatched to outbox"
                : "Rejected and logged"}
            </p>
            <p className="text-sm text-navy/55">
              {needsMoney
                ? "Approving dispatches the customer holding notice and IT ticket. Automated money movement is blocked by guardrail."
                : "Nothing is sent until an authorized operator approves."}
            </p>
          </div>
          {d === "pending" ? (
            <div className="flex gap-2">
              <button
                onClick={() => handleDecision("rejected")}
                disabled={!ready || deciding}
                className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-full border border-navy/15 text-navy font-semibold hover:bg-navy/5 disabled:opacity-40 transition-colors"
              >
                <X className="w-4 h-4" />
                Reject
              </button>
              <button
                onClick={() => handleDecision("approved")}
                disabled={!ready || deciding}
                className="inline-flex items-center gap-1.5 px-6 py-2.5 rounded-full bg-flux text-white font-semibold hover:bg-[#d25a14] disabled:opacity-40 transition-colors"
              >
                {deciding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                Approve &amp; log
              </button>
            </div>
          ) : (
            <Tag tone={d === "approved" ? "green" : "red"}>Decision recorded: {d}</Tag>
          )}
        </div>
      </Card>

      {inc.examples.length > 0 && (
        <Card className="p-6 mt-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-navy">Sample complaints attached to this incident</h3>
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
