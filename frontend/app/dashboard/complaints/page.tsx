"use client";
import { useEffect, useMemo, useState } from "react";
import { Search, Send, MessageSquarePlus, Loader2, Radio, RefreshCw } from "lucide-react";
import { describeXResult } from "@/lib/social";
import { motion } from "framer-motion";
import Link from "next/link";
import { api } from "@/lib/api";
import { mapBackendComplaint, useDash } from "@/components/dashboard/Provider";
import { Card, IssueBadge, PageHeader, SeverityBadge, Tag, Td, TableWrap, Th } from "@/components/dashboard/ui";
import { ISSUE_LABEL, type Channel, type Complaint, type IssueType } from "@/lib/types";

export default function Complaints() {
  const { addComplaint, pullSocialX, isBackendLive, user } = useDash();
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [offset, setOffset] = useState(0);
  const [channel, setChannel] = useState("");
  const [region, setRegion] = useState("");
  const [fraud, setFraud] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [revision, setRevision] = useState(0);
  const [resultKey, setResultKey] = useState("");
  const [listError, setListError] = useState("");
  const [q, setQ] = useState("");
  const [issue, setIssue] = useState("all");
  const [sev, setSev] = useState("all");
  const [paste, setPaste] = useState("");
  const [channelInput, setChannelInput] = useState<Channel>("In-app");
  const [regionInput, setRegionInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPullingX, setIsPullingX] = useState(false);
  const [submitNotice, setSubmitNotice] = useState<string | null>(null);
  const [pullNotice, setPullNotice] = useState<string | null>(null);

  const queryKey = JSON.stringify([channel, issue, region, fraud, since, until, offset, revision]);
  const loading = queryKey !== resultKey;
  useEffect(() => {
    let active = true;
    api.getComplaints({
      channel, issue_type: issue, region,
      is_fraud: fraud ? fraud === "yes" : undefined,
      since: since ? `${since}T00:00:00Z` : undefined,
      until: until ? `${until}T00:00:00Z` : undefined,
      offset, limit: 50,
    }).then((items) => {
      if (!active) return;
      setComplaints(items.map(mapBackendComplaint));
      setListError("");
    }).catch((err) => {
      if (active) setListError(err instanceof Error ? err.message : "Could not load complaints.");
    }).finally(() => {
      if (active) setResultKey(queryKey);
    });
    return () => { active = false; };
  }, [channel, issue, region, fraud, since, until, offset, queryKey]);

  const rows = useMemo(
    () =>
      complaints.filter(
        (c) =>
          (sev === "all" || c.severity === sev) &&
          (c.text.toLowerCase().includes(q.toLowerCase()) ||
            c.region.toLowerCase().includes(q.toLowerCase()) ||
            c.language.toLowerCase().includes(q.toLowerCase()))
      ),
    [complaints, q, sev]
  );

  const submit = async () => {
    if (!paste.trim() || isSubmitting || user?.role === "manager") return;
    setIsSubmitting(true);
    setSubmitNotice(null);
    const textToClassify = paste.trim();

    try {
      await addComplaint({ channel: channelInput, text: textToClassify, region: regionInput || undefined });
      setSubmitNotice("Complaint submitted. Classification will appear after processing.");
      setPaste("");
      setOffset(0);
      setRevision((value) => value + 1);
    } catch {
      setSubmitNotice("Could not submit the complaint. Try again.");
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
      setPullNotice(describeXResult(res));
      setRevision((value) => value + 1);
    } catch {
      setPullNotice("Could not pull X mentions. Try again.");
    } finally {
      setIsPullingX(false);
    }
  };

  const sel =
    "rounded-full bg-white border border-navy/[0.08] px-4 py-2.5 text-sm text-navy outline-none focus:border-flux";

  return (
    <>
      {submitNotice && <p role="status">{submitNotice}</p>}
      <PageHeader
        title="Complaint explorer"
        sub="Bank complaint records with server filters. Text and severity filters apply to the current page."
        right={
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handlePullX}
              disabled={isPullingX || user?.role === "manager"}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-navy text-white text-xs font-semibold hover:bg-navy-600 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isPullingX ? "animate-spin text-flux" : "text-flux"}`} />
              {isPullingX ? "Pulling X Stream…" : "Pull X Mentions"}
            </button>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold">
              <Radio className="w-3.5 h-3.5 animate-pulse text-emerald-600" />
              {isBackendLive ? "Dashboard polling" : "Connecting…"}
            </span>
            <Tag tone="navy">{loading || listError ? "—" : complaints.length} records on page</Tag>
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
            <h3 className="font-semibold text-navy">Submit a complaint for classification</h3>
            <span className="text-xs text-navy/45">
              Try: &ldquo;my money don enter nowhere&rdquo; or &ldquo;Mo ti debit sugbon ko de odo beneficiary&rdquo;
            </span>
          </div>
          <div className="flex items-center gap-2">
            <select
              aria-label="Complaint channel"
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
              aria-label="Complaint region"
              value={regionInput}
              onChange={(e) => setRegionInput(e.target.value)}
              className="rounded-full bg-navy/[0.04] px-3 py-1.5 text-xs font-medium text-navy outline-none"
            >
              <option value="">Unknown region</option>
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
            aria-label="Complaint text"
            value={paste}
            onChange={(e) => setPaste(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            disabled={isSubmitting || user?.role === "manager"}
            placeholder="Paste a complaint in English, Pidgin, Yoruba, Hausa or Igbo…"
            className="flex-1 rounded-full bg-navy/[0.04] px-5 py-3 text-navy outline-none focus:ring-2 focus:ring-flux/40 disabled:opacity-60"
          />
          <button
            onClick={submit}
            disabled={isSubmitting || !paste.trim() || user?.role === "manager"}
            className="inline-flex items-center gap-2 bg-navy text-white font-semibold px-6 rounded-full hover:bg-navy-600 transition-colors disabled:opacity-50"
          >
            {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Submit
          </button>
        </div>
      </Card>

      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-navy/40" />
          <input
            aria-label="Search current page"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search complaints, regions, or languages…"
            className={`${sel} w-full pl-10`}
          />
        </div>
        <select aria-label="Issue" value={issue} onChange={(e) => { setIssue(e.target.value); setOffset(0); }} className={sel}>
          <option value="all">All issues</option>
          {(Object.keys(ISSUE_LABEL) as IssueType[]).map((k) => (
            <option key={k} value={k}>
              {ISSUE_LABEL[k]}
            </option>
          ))}
        </select>
        <select aria-label="Severity on current page" value={sev} onChange={(e) => setSev(e.target.value)} className={sel}>
          <option value="all">All severities</option>
          {["critical", "high", "medium", "low"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-2">
        <label className="grid gap-1">Channel<select className={sel} value={channel} onChange={(e) => { setChannel(e.target.value); setOffset(0); }}>
          <option value="">All channels</option>
          {["in_app", "x", "instagram", "facebook", "call", "email", "branch"].map((value) => <option key={value}>{value}</option>)}
        </select></label>
        <label className="grid gap-1">Exact region<input className={sel} value={region} onChange={(e) => { setRegion(e.target.value); setOffset(0); }} /></label>
        <label className="grid gap-1">Fraud flag<select className={sel} value={fraud} onChange={(e) => { setFraud(e.target.value); setOffset(0); }}>
          <option value="">Any</option><option value="yes">Flagged</option><option value="no">Unflagged</option>
        </select></label>
        <label className="grid gap-1">From date (UTC)<input className={sel} type="date" value={since} onChange={(e) => { setSince(e.target.value); setOffset(0); }} /></label>
        <label className="grid gap-1">Before date (UTC)<input className={sel} type="date" value={until} onChange={(e) => { setUntil(e.target.value); setOffset(0); }} /></label>
        <button className={sel} onClick={() => setRevision((value) => value + 1)}>Refresh complaints</button>
      </div>
      {loading && <p role="status">Loading complaints…</p>}
      {!loading && listError && <p role="alert">{listError}</p>}
      {!loading && !listError &&
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
                <Td className="font-mono text-navy/50">{c.occurredAt ?? "—"}</Td>
                <Td className="max-w-md">
                  <Link className="underline" href={`/dashboard/complaints/${c.id}`}>{c.text}</Link>
                  {c.fresh && (
                    <span className="ml-2">
                      <Tag tone="flux">Just ingested</Tag>
                    </span>
                  )}
                </Td>
                <Td>
                  {c.confidence == null && c.severity == null ? "Unclassified" : <IssueBadge i={c.issue} />}
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
      </Card>}
      <div className="mt-4 flex items-center gap-2">
        <button className={sel} disabled={loading || offset === 0} onClick={() => setOffset(offset - 50)}>Previous</button>
        <span>Page {offset / 50 + 1}</span>
        <button className={sel} disabled={loading || !!listError || complaints.length < 50} onClick={() => setOffset(offset + 50)}>Next</button>
      </div>
    </>
  );
}
