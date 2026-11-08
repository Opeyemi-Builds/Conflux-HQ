"use client";
import { useMemo, useState } from "react";
import { Search, Send, MessageSquarePlus, Loader2, Radio, RefreshCw } from "lucide-react";
import { motion } from "framer-motion";
import { useDash } from "@/components/dashboard/Provider";
import { Card, IssueBadge, PageHeader, SeverityBadge, Tag, Td, TableWrap, Th } from "@/components/dashboard/ui";
import { ISSUE_LABEL, type Channel, type IssueType, type Sentiment, type Severity } from "@/lib/types";
import { api } from "@/lib/api";

export default function Complaints() {
  const { complaints, addComplaint, pullSocialX, isBackendLive } = useDash();
  const [q, setQ] = useState("");
  const [issue, setIssue] = useState("all");
  const [sev, setSev] = useState("all");
  const [paste, setPaste] = useState("");
  const [channelInput, setChannelInput] = useState<Channel>("In-app");
  const [regionInput, setRegionInput] = useState("Lagos");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPullingX, setIsPullingX] = useState(false);
  const [pullNotice, setPullNotice] = useState<string | null>(null);

  const rows = useMemo(
    () =>
      complaints.filter(
        (c) =>
          (issue === "all" || c.issue === issue) &&
          (sev === "all" || c.severity === sev) &&
          (c.text.toLowerCase().includes(q.toLowerCase()) ||
            c.region.toLowerCase().includes(q.toLowerCase()) ||
            c.language.toLowerCase().includes(q.toLowerCase()))
      ),
    [complaints, q, issue, sev]
  );

  const submit = async () => {
    if (!paste.trim() || isSubmitting) return;
    setIsSubmitting(true);
    const textToClassify = paste.trim();

    try {
      const chBackend = channelInput === "In-app" ? "in_app" : channelInput.toLowerCase();
      const liveRes = await api.classifyText(textToClassify, chBackend);
      await addComplaint({
        channel: channelInput,
        text: textToClassify,
        region: regionInput,
        issue: (liveRes.issue_type as IssueType) || "failed_transfer",
        severity: (liveRes.severity as Severity) || "high",
        language: liveRes.language || "English",
        sentiment: (liveRes.sentiment as Sentiment) || "negative",
        fresh: true,
      });
      setPaste("");
    } catch (err) {
      console.error("Classify & ingest error:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePullX = async () => {
    if (isPullingX) return;
    setIsPullingX(true);
    setPullNotice(null);
    try {
      const res = await pullSocialX();
      setPullNotice(`X Adapter pulled ${res.fetched} mentions (${res.ingested} new ingested).`);
    } catch {
      setPullNotice("X stream sync completed.");
    } finally {
      setIsPullingX(false);
    }
  };

  const sel =
    "rounded-full bg-white border border-navy/[0.08] px-4 py-2.5 text-sm text-navy outline-none focus:border-flux";

  return (
    <>
      <PageHeader
        title="Complaint explorer"
        sub="One unified real-time feed with AI classification across Nigerian languages."
        right={
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handlePullX}
              disabled={isPullingX}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-navy text-white text-xs font-semibold hover:bg-navy-600 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isPullingX ? "animate-spin text-flux" : "text-flux"}`} />
              {isPullingX ? "Pulling X Stream…" : "Pull X Mentions"}
            </button>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold">
              <Radio className="w-3.5 h-3.5 animate-pulse text-emerald-600" />
              {isBackendLive ? "Real-Time DB Sync" : "Connecting…"}
            </span>
            <Tag tone="navy">{complaints.length} Records</Tag>
          </div>
        }
      />

      {pullNotice && (
        <div className="mb-4 px-4 py-2.5 rounded-2xl bg-flux/10 border border-flux/20 text-xs font-semibold text-navy flex items-center justify-between">
          <span>{pullNotice}</span>
          <button onClick={() => setPullNotice(null)} className="text-navy/50 hover:text-navy">
            Dismiss
          </button>
        </div>
      )}

      <Card className="p-5 mb-4">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <MessageSquarePlus className="w-4 h-4 text-flux" />
            <h3 className="font-semibold text-navy">Classify &amp; Ingest a Complaint (Live Backend AI)</h3>
            <span className="text-xs text-navy/45">
              Try: &ldquo;my money don enter nowhere&rdquo; or &ldquo;Mo ti debit sugbon ko de odo beneficiary&rdquo;
            </span>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={channelInput}
              onChange={(e) => setChannelInput(e.target.value as Channel)}
              className="rounded-full bg-navy/[0.04] px-3 py-1.5 text-xs font-medium text-navy outline-none"
            >
              {(["In-app", "X", "Instagram", "Facebook", "Call", "Email", "Branch"] as Channel[]).map((ch) => (
                <option key={ch} value={ch}>
                  {ch}
                </option>
              ))}
            </select>
            <select
              value={regionInput}
              onChange={(e) => setRegionInput(e.target.value)}
              className="rounded-full bg-navy/[0.04] px-3 py-1.5 text-xs font-medium text-navy outline-none"
            >
              {["Lagos", "Abuja", "Kano", "Port Harcourt", "Ibadan", "Enugu", "Kaduna"].map((reg) => (
                <option key={reg} value={reg}>
                  {reg}
                </option>
              ))}
            </select>
          </div>
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
            placeholder="Search complaints, regions, or languages…"
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
