"use client";
import { useMemo, useState } from "react";
import { Search, Send, MessageSquarePlus } from "lucide-react";
import { motion } from "framer-motion";
import { useDash } from "@/components/dashboard/Provider";
import { Card, IssueBadge, PageHeader, SeverityBadge, Tag, Td, TableWrap, Th } from "@/components/dashboard/ui";
import { ISSUE_LABEL } from "@/lib/mock";
import type { Complaint, IssueType, Severity } from "@/lib/types";

/** Demo-only keyword tagger. In production, the Claude classifier returns this. */
function tag(text: string): Pick<Complaint, "issue" | "severity" | "language" | "sentiment"> {
  const t = text.toLowerCase();
  const issue: IssueType = /otp|pin|agent|scam|fraud/.test(t) ? "fraud_scam" : /twice|double/.test(t) ? "double_debit" : /atm/.test(t) ? "card_atm" : /pos/.test(t) ? "pos" : /transfer|money|debit|enter/.test(t) ? "failed_transfer" : /login|log in|app/.test(t) ? "app_login" : /fee|charge/.test(t) ? "fees" : "other";
  const language = /\b(don|abeg|dey|wetin|nowhere|enter|na)\b/.test(t) ? "Pidgin" : "English";
  const severity: Severity = issue === "fraud_scam" ? "critical" : issue === "failed_transfer" ? "high" : "medium";
  return { issue, severity, language, sentiment: /abeg|angry|useless|worst|!/.test(t) ? "angry" : "negative" };
}
export default function Complaints() {
  const { complaints, addComplaint } = useDash();
  const [q, setQ] = useState(""); const [issue, setIssue] = useState("all"); const [sev, setSev] = useState("all"); const [paste, setPaste] = useState("");
  const rows = useMemo(() => complaints.filter((c) => (issue === "all" || c.issue === issue) && (sev === "all" || c.severity === sev) && c.text.toLowerCase().includes(q.toLowerCase())), [complaints, q, issue, sev]);
  const submit = () => {
    if (!paste.trim()) return;
    addComplaint({ id: `C-${Date.now().toString().slice(-4)}`, time: new Date().toTimeString().slice(0, 5), channel: "In-app", text: paste.trim(), region: "Lagos", ref: "****0000", fresh: true, ...tag(paste) });
    setPaste("");
  };
  const sel = "rounded-full bg-white border border-navy/[0.08] px-4 py-2.5 text-sm text-navy outline-none focus:border-flux";
  return (
    <>
      <PageHeader title="Complaint explorer" sub="One unified feed, with AI tags on every complaint." />
      <Card className="p-5 mb-4">
        <div className="flex items-center gap-2 mb-3"><MessageSquarePlus className="w-4 h-4 text-flux" /><h3 className="font-semibold text-navy">Paste a complaint</h3><span className="text-xs text-navy/45">Try: “my money don enter nowhere”</span></div>
        <div className="flex gap-2"><input value={paste} onChange={(e) => setPaste(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} placeholder="Paste a complaint in English, Pidgin, Yoruba, Hausa or Igbo…" className="flex-1 rounded-full bg-navy/[0.04] px-5 py-3 text-navy outline-none focus:ring-2 focus:ring-flux/40" />
          <button onClick={submit} className="inline-flex items-center gap-2 bg-navy text-white font-semibold px-6 rounded-full hover:bg-navy-600 transition-colors"><Send className="w-4 h-4" />Classify</button></div>
      </Card>
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[220px]"><Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-navy/40" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search complaints" className={`${sel} w-full pl-10`} /></div>
        <select value={issue} onChange={(e) => setIssue(e.target.value)} className={sel}><option value="all">All issues</option>{(Object.keys(ISSUE_LABEL) as IssueType[]).map((k) => <option key={k} value={k}>{ISSUE_LABEL[k]}</option>)}</select>
        <select value={sev} onChange={(e) => setSev(e.target.value)} className={sel}><option value="all">All severities</option>{["critical", "high", "medium", "low"].map((s) => <option key={s} value={s}>{s}</option>)}</select>
      </div>
      <Card className="overflow-hidden">
        <TableWrap><thead className="bg-navy/[0.03]"><tr><Th>Time</Th><Th>Complaint</Th><Th>Issue</Th><Th>Severity</Th><Th>Channel</Th><Th>Language</Th><Th>Region</Th></tr></thead>
          <tbody className="divide-y divide-navy/5">
            {rows.map((c) => (
              <motion.tr key={c.id} initial={c.fresh ? { backgroundColor: "rgba(232,101,26,.15)" } : false} animate={{ backgroundColor: "rgba(255,255,255,0)" }} transition={{ duration: 2 }} className="hover:bg-navy/[0.02]">
                <Td className="font-mono text-navy/50">{c.time}</Td><Td className="max-w-md">{c.text}{c.fresh && <span className="ml-2"><Tag tone="flux">Just pasted</Tag></span>}</Td>
                <Td><IssueBadge i={c.issue} /></Td><Td><SeverityBadge s={c.severity} /></Td><Td>{c.channel}</Td><Td>{c.language}</Td><Td>{c.region}</Td>
              </motion.tr>))}
            {rows.length === 0 && <tr><td colSpan={7} className="text-center py-12 text-navy/50">No complaints match these filters.</td></tr>}
          </tbody></TableWrap>
      </Card>
    </>
  );
}
