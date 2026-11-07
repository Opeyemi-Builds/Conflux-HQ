"use client";
import { useMemo, useState } from "react";
import { Search, Send, MessageSquarePlus, Loader2, Radio } from "lucide-react";
import { motion } from "framer-motion";
import { useDash } from "@/components/dashboard/Provider";
import { Card, IssueBadge, PageHeader, SeverityBadge, Tag, Td, TableWrap, Th } from "@/components/dashboard/ui";
import { ISSUE_LABEL } from "@/lib/mock";
import type { Complaint, IssueType, Severity, Sentiment } from "@/lib/types";
import { api } from "@/lib/api";

/** Fallback rule tagger for instant response if offline */
function tag(text: string): Pick<Complaint, "issue" | "severity" | "language" | "sentiment"> {
  const t = text.toLowerCase();
  const issue: IssueType = /otp|pin|agent|scam|fraud/.test(t)
    ? "fraud_scam"
    : /twice|double/.test(t)
    ? "double_debit"
    : /atm/.test(t)
    ? "card_atm"
    : /pos/.test(t)
    ? "pos"
    : /transfer|money|debit|enter/.test(t)
    ? "failed_transfer"
    : /login|log in|app/.test(t)
    ? "app_login"
    : /fee|charge/.test(t)
    ? "fees"
    : "other";
  const language = /\b(don|abeg|dey|wetin|nowhere|enter|na)\b/.test(t)
    ? "Pidgin"
    : /\b(owo|mo ti|sugbon|jowo)\b/.test(t)
    ? "Yoruba"
    : /\b(kudi|yaudarar|don allah)\b/.test(t)
    ? "Hausa"
    : /\b(ego|biko|adịghị)\b/.test(t)
    ? "Igbo"
    : "English";
  const severity: Severity = issue === "fraud_scam" ? "critical" : issue === "failed_transfer" ? "high" : "medium";
  return { issue, severity, language, sentiment: /abeg|angry|useless|worst|!/.test(t) ? "angry" : "negative" };
}

export default function Complaints() {
  const { complaints, addComplaint, isBackendLive } = useDash();
  const [q, setQ] = useState("");
  const [issue, setIssue] = useState("all");
  const [sev, setSev] = useState("all");
  const [paste, setPaste] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const rows = useMemo(
    () =>
      complaints.filter(
        (c) =>
          (issue === "all" || c.issue === issue) &&
          (sev === "all" || c.severity === sev) &&
          c.text.toLowerCase().includes(q.toLowerCase())
      ),
    [complaints, q, issue, sev]
  );

  const submit = async () => {
    if (!paste.trim() || isSubmitting) return;
    setIsSubmitting(true);
    const textToClassify = paste.trim();

    let meta: Pick<Complaint, "issue" | "severity" | "language" | "sentiment">;
    try {
      const liveRes = await api.classifyText(textToClassify);
      meta = {
        issue: (liveRes.issue_type as IssueType) || tag(textToClassify).issue,
        severity: (liveRes.severity as Severity) || tag(textToClassify).severity,
        language: liveRes.language || tag(textToClassify).language,
        sentiment: (liveRes.sentiment as Sentiment) || tag(textToClassify).sentiment,
      };
    } catch {
      meta = tag(textToClassify);
    }

    await addComplaint({
      id: `C-${Date.now().toString().slice(-4)}`,
      time: new Date().toTimeString().slice(0, 5),
      channel: "In-app",
      text: textToClassify,
      region: "Lagos",
      ref: "****0000",
      fresh: true,
      ...meta,
    });

    setPaste("");
    setIsSubmitting(false);
  };

  const sel =
    "rounded-full bg-white border border-navy/[0.08] px-4 py-2.5 text-sm text-navy outline-none focus:border-flux";

  return (
    <>
      <PageHeader
        title="Complaint explorer"
        sub="One unified real-time feed with AI classification across Nigerian languages."
        right={
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold">
              <Radio className="w-3.5 h-3.5 animate-pulse text-emerald-600" />
              {isBackendLive ? "Real-Time DB Sync" : "Local Sync Active"}
            </span>
            <Tag tone="navy">{complaints.length} Total Complaints</Tag>
          </div>
        }
      />

      <Card className="p-5 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <MessageSquarePlus className="w-4 h-4 text-flux" />
          <h3 className="font-semibold text-navy">Classify &amp; Ingest a Complaint</h3>
          <span className="text-xs text-navy/45">Try: “my money don enter nowhere” or “Mo ti debit sugbon ko de odo beneficiary”</span>
        </div>
        <div className="flex gap-2">
          <input
            value={paste}
            onChange={(e) => setPaste(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            disabled={isSubmitting}
            placeholder="Paste a complaint in English, Pidgin, Yoruba, Hausa or Igbo…"
            className="flex-1 rounded-full bg-navy/[0.04] px-5 py-3 text-navy outline-none focus:ring-2 focus:ring-flux/40 disabled:opacity-60"
          />
          <button
            onClick={submit}
            disabled={isSubmitting || !paste.trim()}
            className="inline-flex items-center gap-2 bg-navy text-white font-semibold px-6 rounded-full hover:bg-navy-600 transition-colors disabled:opacity-50"
          >
            {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Classify
          </button>
        </div>
      </Card>

      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-navy/40" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search complaints"
            className={`${sel} w-full pl-10`}
          />
        </div>
        <select value={issue} onChange={(e) => setIssue(e.target.value)} className={sel}>
          <option value="all">All issues</option>
          {(Object.keys(ISSUE_LABEL) as IssueType[]).map((k) => (
            <option key={k} value={k}>
              {ISSUE_LABEL[k]}
            </option>
          ))}
        </select>
        <select value={sev} onChange={(e) => setSev(e.target.value)} className={sel}>
          <option value="all">All severities</option>
          {["critical", "high", "medium", "low"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <Card className="overflow-hidden">
        <TableWrap>
          <thead className="bg-navy/[0.03]">
            <tr>
              <Th>Time</Th>
              <Th>Complaint</Th>
              <Th>Issue</Th>
              <Th>Severity</Th>
              <Th>Channel</Th>
              <Th>Language</Th>
              <Th>Region</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-navy/5">
            {rows.map((c) => (
              <motion.tr
                key={c.id}
                initial={c.fresh ? { backgroundColor: "rgba(232,101,26,.15)" } : false}
                animate={{ backgroundColor: "rgba(255,255,255,0)" }}
                transition={{ duration: 2 }}
                className="hover:bg-navy/[0.02]"
              >
                <Td className="font-mono text-navy/50">{c.time}</Td>
                <Td className="max-w-md">
                  {c.text}
                  {c.fresh && (
                    <span className="ml-2">
                      <Tag tone="flux">Just ingested</Tag>
                    </span>
                  )}
                </Td>
                <Td>
                  <IssueBadge i={c.issue} />
                </Td>
                <Td>
                  <SeverityBadge s={c.severity} />
                </Td>
                <Td>{c.channel}</Td>
                <Td>{c.language}</Td>
                <Td>{c.region}</Td>
              </motion.tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center py-12 text-navy/50">
                  No complaints match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </TableWrap>
      </Card>
    </>
  );
}
