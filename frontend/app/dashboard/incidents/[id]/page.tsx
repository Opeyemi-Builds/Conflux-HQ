"use client";
import { use } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, Check, CheckCircle2, ClipboardCopy, Loader2, MessageSquare, Server, X } from "lucide-react";
import { useDash } from "@/components/dashboard/Provider";
import { Card, IssueBadge, PageHeader, Stat, Tag, Td, TableWrap, Th } from "@/components/dashboard/ui";
import { SpikeChart } from "@/components/dashboard/Charts";
import { incidents, transactions } from "@/lib/mock";

export default function IncidentPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const routeParams = useParams();
  const id = resolvedParams?.id ?? (routeParams?.id as string);
  const { role, phase, decisions, decide } = useDash();
  const inc = incidents.find((i) => i.id === id);
  if (!inc) return <p className="text-navy/60">Incident not found. <Link href="/dashboard" className="text-flux underline">Back to overview</Link></p>;
  const d = decisions[inc.id] ?? "pending";
  const ready = phase >= 4;
  const needsMoney = inc.id === "INC-0421";
  return (
    <>
      <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-navy/60 hover:text-navy mb-4"><ArrowLeft className="w-4 h-4" />Overview</Link>
      <PageHeader title={inc.title} sub={`${inc.id} · started ${inc.startedAt} · detected ${inc.detectedAt} · ${inc.region}`} right={<div className="flex gap-2"><IssueBadge i={inc.issue} /><Tag tone={inc.status === "active" ? "flux" : inc.status === "security" ? "red" : "navy"}>{inc.status}</Tag></div>} />

      <Card className="p-6 mb-4 border-l-4 !border-l-flux">
        <p className="text-xs font-semibold tracking-wider text-flux mb-2">{role === "agent" ? "FOR CUSTOMER SERVICE" : role === "it" ? "FOR IT / ENGINEERING" : "FOR MANAGEMENT"}</p>
        <p className="text-lg md:text-xl text-navy leading-relaxed" style={{ letterSpacing: "-0.01em" }}>{phase >= 3 ? inc.summary[role] : "Agent is still investigating. A summary will appear here."}</p>
      </Card>

      <div className="grid sm:grid-cols-4 gap-4 mb-4">
        <Stat label="Complaints" value={String(inc.volume)} hint={inc.growth} />
        <Stat label="Channels" value={inc.channels.join(" + ")} hint="most affected" />
        <Stat label="Money at risk" value={inc.moneyAtRisk} hint="estimated" />
        <Stat label="Priority" value={`${inc.priority}/100`} hint="volume × growth × money" accent />
      </div>

      <Card className="p-6 mb-4"><div className="flex items-center justify-between mb-2"><h3 className="font-semibold text-navy">Timeline</h3><span className="text-sm text-navy/50">Complaints per 5 minutes</span></div><SpikeChart series={inc.series} phase={phase} release={inc.releaseMarker} /></Card>

      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <Card className="p-6">
          <h3 className="font-semibold text-navy mb-4">Candidate causes</h3>
          {phase < 3 ? <p className="text-navy/50 flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />Checking release and outage logs…</p> : (
            <div className="space-y-5">
              {inc.causes.map((c, i) => (
                <div key={c.name}>
                  <div className="flex justify-between text-sm mb-1.5"><span className="font-semibold text-navy">{c.name}</span><span className={c.confidence < 50 ? "text-navy/50" : "text-flux font-semibold"}>{c.confidence}%{c.confidence < 50 ? " · low confidence" : ""}</span></div>
                  <div className="h-2 rounded-full bg-navy/5 overflow-hidden"><motion.div className={`h-full rounded-full ${i === 0 ? "bg-flux" : "bg-navy/30"}`} initial={{ width: 0 }} animate={{ width: `${c.confidence}%` }} transition={{ duration: 0.9, delay: i * 0.12 }} /></div>
                  <p className="text-sm text-navy/55 mt-1.5">{c.evidence}</p>
                </div>))}
            </div>)}
        </Card>
        <Card className="p-6">
          <h3 className="font-semibold text-navy mb-4">Agent trace</h3>
          <ol className="space-y-3">
            {inc.trace.filter((s) => s.phase <= phase).map((s, i) => (
              <motion.li key={s.tool} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }} className="flex gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
                <div className="min-w-0"><p className="font-mono text-sm text-navy">{s.tool}<span className="text-navy/40">({s.args})</span></p><p className="text-sm text-navy/60">{s.result}</p></div>
              </motion.li>))}
            {phase < 4 && <li className="flex gap-3 text-navy/45 text-sm"><Loader2 className="w-5 h-5 animate-spin shrink-0" />Working…</li>}
          </ol>
        </Card>
      </div>

      {needsMoney && phase >= 3 && (
        <Card className="mb-4 overflow-hidden">
          <div className="px-6 pt-5 pb-2 flex items-center justify-between"><h3 className="font-semibold text-navy">Matched transactions</h3><Tag>Simulated records</Tag></div>
          <TableWrap><thead className="bg-navy/[0.03]"><tr><Th>Ref</Th><Th>Time</Th><Th>Channel</Th><Th>Amount</Th><Th>Status</Th><Th>Reversal</Th><Th>Switch</Th></tr></thead>
            <tbody className="divide-y divide-navy/5">{transactions.map((t) => (<tr key={t.ref} className="hover:bg-navy/[0.02]"><Td className="font-mono">{t.ref}</Td><Td>{t.time}</Td><Td>{t.channel}</Td><Td className="font-semibold">{t.amount}</Td><Td><Tag tone="red">{t.status}</Tag></Td><Td>{t.reversal}</Td><Td>{t.switch}</Td></tr>))}</tbody></TableWrap>
        </Card>)}

      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <Card className="p-6"><div className="flex items-center gap-2 mb-3"><MessageSquare className="w-4 h-4 text-flux" /><h3 className="font-semibold text-navy">Draft customer message</h3></div>{ready ? <p className="text-navy/80 leading-relaxed bg-navy/[0.03] rounded-xl p-4">{inc.customerDraft}</p> : <p className="text-navy/45">Not drafted yet.</p>}</Card>
        <Card className="p-6"><div className="flex items-center gap-2 mb-3"><Server className="w-4 h-4 text-flux" /><h3 className="font-semibold text-navy">Draft IT ticket</h3></div>{ready ? <pre className="whitespace-pre-wrap text-sm font-mono text-navy/80 bg-navy/[0.03] rounded-xl p-4">{inc.itTicket}</pre> : <p className="text-navy/45">Not drafted yet.</p>}</Card>
      </div>

      <Card className="p-5 sticky bottom-4 shadow-[0_20px_50px_-20px_rgba(20,35,63,.35)]">
        <div className="flex flex-wrap items-center gap-4 justify-between">
          <div><p className="font-semibold text-navy">{d === "pending" ? "Waiting for human approval" : d === "approved" ? "Approved and logged" : "Rejected and logged"}</p><p className="text-sm text-navy/55">{needsMoney ? "Includes a reversal request for 184 transactions (₦48.2m). The agent cannot execute reversals." : "Nothing is sent until a person approves."}</p></div>
          {d === "pending" ? (
            <div className="flex gap-2">
              <button disabled={!ready} onClick={() => decide(inc.id, "rejected")} className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-navy/10 text-navy font-semibold hover:bg-navy/15 disabled:opacity-40 transition-colors"><X className="w-4 h-4" />Reject</button>
              <button disabled={!ready} onClick={() => decide(inc.id, "approved")} className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-navy text-white font-semibold hover:bg-navy-600 disabled:opacity-40 transition-colors"><Check className="w-4 h-4" />Approve</button>
            </div>
          ) : <Tag tone={d === "approved" ? "green" : "red"}>{d}</Tag>}
        </div>
      </Card>
      <p className="mt-3 text-xs text-navy/40 flex items-center gap-1.5"><ClipboardCopy className="w-3.5 h-3.5" />Examples: {inc.examples.map((e) => `“${e}”`).join(" · ")}</p>
    </>
  );
}
