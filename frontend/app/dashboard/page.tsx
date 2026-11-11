"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  DatabaseZap,
  KeyRound,
  Loader2,
  Pause,
  Play,
  Radio,
  ShieldAlert,
  Timer,
} from "lucide-react";
import { useDash } from "@/components/dashboard/Provider";
import { Card, IssueBadge, PageHeader, Stat, Tag } from "@/components/dashboard/ui";
import { Bars, HourlyStack } from "@/components/dashboard/Charts";
import NigeriaRiskMap from "@/components/dashboard/NigeriaRiskMap";
import { api, type HandoffUpdateItem } from "@/lib/api";

const MACHINE_KEY_STORAGE = "conflux_demo_machine_key";

export default function Overview() {
  const {
    incidents,
    complaints,
    summary,
    transactionsAnalytics,
    hourlySeries,
    channelSplit,
    isLoading,
    refresh,
    user,
  } = useDash();

  const [seeding, setSeeding] = useState(false);
  const [seedFeedback, setSeedFeedback] = useState<string | null>(null);

  // 5-second Handoff Ticker state
  const [machineKey, setMachineKey] = useState<string>("");
  const [tickerPaused, setTickerPaused] = useState(false);
  const [tickerCursor, setTickerCursor] = useState<string | null>(null);
  const [tickerItems, setTickerItems] = useState<HandoffUpdateItem[]>([]);
  const [tickerTruncated, setTickerTruncated] = useState(false);
  const [lastPolledAt, setLastPolledAt] = useState<string | null>(null);
  const [tickerError, setTickerError] = useState<string | null>(null);
  const [provisioningKey, setProvisioningKey] = useState(false);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(MACHINE_KEY_STORAGE);
      if (saved) setMachineKey(saved);
    } catch {}
  }, []);

  const pollMachineFeed = useCallback(
    async (keyToUse: string, cursorToUse: string | null) => {
      if (!keyToUse) return;
      try {
        const res = await api.machineUpdates({
          since: cursorToUse,
          collections: "complaints,incidents",
          limit: 20,
          apiKey: keyToUse,
        });
        setTickerError(null);
        setLastPolledAt(new Date().toLocaleTimeString("en-GB"));
        setTickerTruncated(Boolean(res.truncated));
        if (res.cursor) {
          setTickerCursor(res.cursor);
        }
        if (res.items && res.items.length > 0) {
          setTickerItems((prev) => {
            const combined = [...res.items, ...prev];
            const seen = new Set<string>();
            return combined
              .filter((item) => {
                const k = `${item.collection}:${item.id}:${item.updated_at}`;
                if (seen.has(k)) return false;
                seen.add(k);
                return true;
              })
              .slice(0, 20);
          });
        }
      } catch (err) {
        setTickerError(
          err instanceof Error ? err.message : "Machine feed poll failed"
        );
      }
    },
    []
  );

  // 5-second interval polling when machineKey is present
  useEffect(() => {
    if (!machineKey || tickerPaused) return;
    void pollMachineFeed(machineKey, tickerCursor);
    const id = setInterval(() => {
      void pollMachineFeed(machineKey, tickerCursor);
    }, 5000);
    return () => clearInterval(id);
  }, [machineKey, tickerPaused, tickerCursor, pollMachineFeed]);

  // Fallback synthetic ticker items derived from real complaints & incidents if no cfx_api_ key is bound yet
  const fallbackTickerItems: HandoffUpdateItem[] = [
    ...incidents.slice(0, 6).map((inc) => ({
      collection: "incidents" as const,
      id: inc.id,
      updated_at: inc.detectedAt,
      data: {
        title: inc.title,
        issue_type: inc.issue,
        status: inc.rawStatus || inc.status,
        complaint_count: inc.volume,
        priority: inc.priority,
      },
    })),
    ...complaints.slice(0, 14).map((c) => ({
      collection: "complaints" as const,
      id: c.id,
      updated_at: c.occurredAt || c.time,
      data: {
        channel: c.channel,
        issue_type: c.issue,
        summary: c.summary || c.text,
        region: c.region,
        payment_reference: c.ref,
      },
    })),
  ].slice(0, 20);

  const displayedTickerItems = tickerItems.length > 0 ? tickerItems : fallbackTickerItems;

  const handleQuickProvisionKey = async () => {
    setProvisioningKey(true);
    setTickerError(null);
    try {
      const created = await api.createKey({
        name: `Overview Live Ticker (${new Date().toLocaleTimeString("en-GB")})`,
        scopes: ["read", "operate"],
      });
      setMachineKey(created.token);
      setTickerCursor(null);
      try {
        window.localStorage.setItem(MACHINE_KEY_STORAGE, created.token);
      } catch {}
      await pollMachineFeed(created.token, null);
    } catch (err) {
      setTickerError(
        err instanceof Error
          ? err.message
          : "Could not provision machine key. Generate one in API Keys settings."
      );
    } finally {
      setProvisioningKey(false);
    }
  };

  const handleSeedDemo = async () => {
    setSeeding(true);
    setSeedFeedback(null);
    try {
      const seeded = await api.seedScenario(true);
      const detected = await api.detectSpikes(seeded.detection_at).catch(() => []);
      await refresh();
      setSeedFeedback(
        `Seeded ${seeded.complaints_created} complaints and detected ${detected.length} active spikes.`
      );
    } catch (err) {
      setSeedFeedback(
        err instanceof Error ? err.message : "Could not seed demo scenario."
      );
    } finally {
      setSeeding(false);
    }
  };

  const live = incidents
    .filter((incident) => incident.status !== "resolved" && incident.rawStatus !== "dismissed")
    .sort((a, b) => b.priority - a.priority);
  const topIncident = live[0] || null;

  const complaintsCount =
    summary?.total_complaints !== undefined
      ? summary.total_complaints.toLocaleString()
      : "—";

  const exposureFormatted =
    summary?.money_at_risk !== undefined
      ? `₦${(Number(summary.money_at_risk) / 1_000_000).toFixed(2)}m`
      : "—";

  const openIncidentsCount =
    summary?.open_incidents !== undefined
      ? String(summary.open_incidents)
      : String(live.filter((i) => i.status !== "resolved").length);

  const pendingDraftsCount = live.reduce(
    (acc, inc) => acc + (inc.drafts?.filter((d) => d.status === "pending").length || 0),
    0
  );

  const failedRatePct =
    transactionsAnalytics?.failed_rate !== undefined
      ? `${(transactionsAnalytics.failed_rate * 100).toFixed(1)}%`
      : "—";

  const failedCount = transactionsAnalytics?.by_status?.failed ?? 0;

  return (
    <>
      <AnimatePresence mode="wait">
        {topIncident ? (
          <motion.div
            key={topIncident.id}
            initial={{ opacity: 0, y: -16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ type: "spring", stiffness: 260, damping: 24 }}
            className="rounded-3xl bg-gradient-to-r from-[#c24f0c] via-flux to-flux-soft p-6 md:p-7 mb-6 text-white flex flex-wrap items-center gap-5 shadow-[0_20px_50px_-20px_rgba(232,101,26,.6)]"
          >
            <div className="w-12 h-12 rounded-2xl bg-white/20 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div className="flex-1 min-w-[240px]">
              <p className="text-xs font-semibold tracking-wider opacity-90 flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute h-full w-full rounded-full bg-white opacity-70" />
                  <span className="relative h-2 w-2 rounded-full bg-white" />
                </span>
                PRIORITY INCIDENT · {topIncident.detectedAt}
              </p>
              <h2 className="text-2xl md:text-3xl font-semibold mt-1" style={{ letterSpacing: "-0.03em" }}>
                {topIncident.title}
              </h2>
              <p className="opacity-90 mt-1">{topIncident.summary}</p>
            </div>
            <Link
              href={`/dashboard/incidents/${topIncident.id}`}
              className="inline-flex items-center gap-2 bg-navy text-white font-semibold px-5 py-3 rounded-full hover:bg-navy-600 transition-colors"
            >
              Open incident <ArrowRight className="w-4 h-4" />
            </Link>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <PageHeader
        title="Live overview"
        sub="Monitor complaint trends, active incident spikes, and the 5-second machine handoff feed."
      />

      {seedFeedback && (
        <Card className="p-4 mb-5 border-l-4 !border-l-flux flex items-center justify-between gap-3">
          <p className="text-xs font-medium text-navy">{seedFeedback}</p>
          <button
            type="button"
            onClick={() => setSeedFeedback(null)}
            className="text-xs text-navy/50 hover:text-navy underline"
          >
            Dismiss
          </button>
        </Card>
      )}

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Stat
          label="Open incidents"
          value={openIncidentsCount}
          hint={`${pendingDraftsCount} drafts awaiting sign-off`}
          accent
        />
        <Stat
          label="Complaints monitored"
          value={complaintsCount}
          hint="across all intake channels"
        />
        <Stat
          label="Reported exposure"
          value={exposureFormatted}
          hint="from customer complaint amounts"
        />
        <Stat
          label="Failed transaction rate"
          value={failedRatePct}
          hint={`${failedCount} failed switch transactions`}
        />
      </div>

      {/* 5-Second Machine Handoff Live Ticker */}
      <Card className="p-5 mb-6 border border-navy/10 bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2.5">
            <span className="relative flex h-2.5 w-2.5">
              {!tickerPaused && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-flux opacity-75" />
              )}
              <span
                className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                  tickerPaused ? "bg-navy/35" : "bg-flux"
                }`}
              />
            </span>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold text-navy">
                  5s Handoff Live Ticker
                </h3>
                <code className="text-[11px] font-mono bg-navy/[0.05] text-navy/75 px-2 py-0.5 rounded">
                  GET /api/v1/machine/updates?collections=complaints,incidents&amp;limit=20
                </code>
                {tickerTruncated && (
                  <Tag tone="flux">truncated=true</Tag>
                )}
              </div>
              <p className="text-xs text-navy/55 mt-0.5">
                {machineKey ? (
                  <>
                    Polling with bound <code className="font-mono">cfx_api_</code> key ·{" "}
                    {lastPolledAt ? `last poll ${lastPolledAt}` : "connecting…"} · cursor:{" "}
                    <code className="font-mono text-[11px]">
                      {tickerCursor ? `${tickerCursor.slice(0, 19)}Z` : "initial"}
                    </code>
                  </>
                ) : (
                  <>
                    Showing live workspace feed ({displayedTickerItems.length} items). Bind a{" "}
                    <code className="font-mono">cfx_api_</code> machine key to stream via cursor polling.
                  </>
                )}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {!machineKey && user?.role !== "manager" && (
              <button
                type="button"
                disabled={provisioningKey}
                onClick={() => void handleQuickProvisionKey()}
                className="inline-flex items-center gap-1.5 rounded-full bg-flux/10 hover:bg-flux/20 text-flux px-3.5 py-1.5 text-xs font-semibold transition-colors disabled:opacity-50"
              >
                {provisioningKey ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <KeyRound className="w-3.5 h-3.5" />
                )}
                {provisioningKey ? "Binding key…" : "Bind cfx_api_ key"}
              </button>
            )}
            <button
              type="button"
              onClick={() => setTickerPaused((p) => !p)}
              className="inline-flex items-center gap-1.5 rounded-full bg-navy/[0.05] hover:bg-navy/10 text-navy px-3 py-1.5 text-xs font-semibold transition-colors"
            >
              {tickerPaused ? <Play className="w-3.5 h-3.5 text-flux" /> : <Pause className="w-3.5 h-3.5" />}
              {tickerPaused ? "Resume 5s poll" : "Pause"}
            </button>
            <Link
              href="/developers#polling"
              className="inline-flex items-center gap-1 text-xs font-semibold text-flux hover:underline px-2 py-1"
            >
              Polling docs <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>

        {tickerError && (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2 mb-3">
            {tickerError}
          </p>
        )}

        {displayedTickerItems.length === 0 ? (
          <div className="rounded-2xl bg-cream/60 border border-navy/[0.06] px-4 py-6 text-center text-xs text-navy/55">
            No handoff events in window yet. Seed the demo scenario below to watch complaints and incidents stream in.
          </div>
        ) : (
          <div className="max-h-52 overflow-y-auto rounded-2xl bg-navy text-white p-3 space-y-1.5 font-mono text-xs">
            {displayedTickerItems.map((item, i) => {
              const isIncident = item.collection === "incidents";
              const d = item.data || {};
              const label = isIncident
                ? String(d.title || d.issue_type || "Incident spike")
                : String(d.summary || d.text || d.issue_type || "Customer complaint");
              const sub = isIncident
                ? `status=${String(d.status || "open")} · complaints=${String(d.complaint_count ?? "—")}`
                : `channel=${String(d.channel || "—")} · issue=${String(d.issue_type || "—")}${
                    d.payment_reference ? ` · ref=${String(d.payment_reference)}` : ""
                  }`;
              return (
                <div
                  key={`${item.collection}-${item.id}-${i}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.09] px-3 py-2 transition-colors"
                >
                  <div className="flex items-center gap-2.5 min-w-0 flex-1">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] uppercase font-semibold shrink-0 ${
                        isIncident
                          ? "bg-flux text-white"
                          : "bg-white/15 text-flux-soft"
                      }`}
                    >
                      {item.collection}
                    </span>
                    <Link
                      href={
                        isIncident
                          ? `/dashboard/incidents/${item.id}`
                          : `/dashboard/complaints/${item.id}`
                      }
                      className="truncate text-white/90 hover:text-flux-soft hover:underline"
                    >
                      {label}
                    </Link>
                  </div>
                  <div className="flex items-center gap-3 text-[11px] text-white/55 shrink-0">
                    <span className="hidden md:inline">{sub}</span>
                    <span className="text-white/40">{String(item.updated_at).slice(0, 19)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <div className="grid lg:grid-cols-3 gap-4 mb-6">
        <Card className="lg:col-span-2 p-6">
          <h3 className="font-semibold text-navy mb-1">Complaints per hour by issue type</h3>
          <p className="text-sm text-navy/50 mb-4">Live stacked database distribution</p>
          <HourlyStack data={hourlySeries} />
        </Card>
        <Card className="p-6">
          <h3 className="font-semibold text-navy mb-1">Channel breakdown</h3>
          <p className="text-sm text-navy/50 mb-4">Complaints by intake channel</p>
          <Bars data={channelSplit} horizontal height={300} />
        </Card>
      </div>

      {/* Geospatial Threat & Complaint Map (Nigeria) */}
      <NigeriaRiskMap />

      <Card className="p-2">
        <div className="flex items-center justify-between px-4 pt-4 pb-2">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-navy">Active incidents, ranked by priority</h3>
            <Tag>{live.length} listed</Tag>
          </div>
          <Link
            href="/dashboard/incidents"
            className="text-xs font-semibold text-flux hover:underline inline-flex items-center gap-1"
          >
            View all incidents <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {isLoading ? (
          <div className="p-4 space-y-3">
            {[0, 1, 2].map((idx) => (
              <div
                key={idx}
                className="h-16 rounded-2xl bg-navy/[0.04] animate-pulse px-4 flex items-center justify-between"
              >
                <div className="h-4 w-56 rounded bg-navy/10" />
                <div className="h-5 w-20 rounded-full bg-navy/10" />
              </div>
            ))}
          </div>
        ) : live.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <div className="w-11 h-11 rounded-2xl bg-flux/10 text-flux flex items-center justify-center mx-auto mb-3">
              <Radio className="w-5 h-5" />
            </div>
            <p className="font-semibold text-navy">No incidents — seed the demo</p>
            <p className="text-sm text-navy/55 max-w-md mx-auto mt-1 mb-4">
              Populate realistic multi-channel Nigerian banking complaints, transactions, and system events to trigger spike detection.
            </p>
            {user?.role !== "manager" && (
              <button
                type="button"
                disabled={seeding}
                onClick={() => void handleSeedDemo()}
                className="inline-flex items-center gap-2 rounded-full bg-flux hover:bg-[#d4560f] text-white px-5 py-2.5 text-xs font-semibold transition-colors disabled:opacity-50"
              >
                {seeding ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <DatabaseZap className="w-4 h-4" />
                )}
                {seeding ? "Seeding demo scenario…" : "Seed demo & detect spikes"}
              </button>
            )}
          </div>
        ) : (
          live.map((i, idx) => (
            <motion.div
              key={i.id}
              layout
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.06 }}
            >
              <Link
                href={`/dashboard/incidents/${i.id}`}
                className="flex flex-wrap items-center gap-4 px-4 py-4 rounded-xl hover:bg-navy/[0.03] transition-colors"
              >
                <div className="w-14 text-center">
                  <p className="text-2xl font-semibold text-navy leading-none">{i.priority}</p>
                  <p className="text-[10px] uppercase tracking-wider text-navy/40 mt-1">priority</p>
                </div>
                <div className="flex-1 min-w-[220px]">
                  <p className="font-semibold text-navy">{i.title}</p>
                  <p className="text-sm text-navy/55 mt-0.5 flex items-center gap-2">
                    <Timer className="w-3.5 h-3.5" />
                    Started {i.startedAt} · {i.volume} complaints · {i.moneyAtRisk}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <IssueBadge i={i.issue} />
                  {i.status === "security" && (
                    <Tag tone="red">
                      <ShieldAlert className="w-3 h-3 inline -mt-0.5 mr-1" />
                      Security
                    </Tag>
                  )}
                  {i.status === "monitoring" && <Tag>Monitoring</Tag>}
                  {i.status === "resolved" && <Tag tone="green">Resolved</Tag>}
                  {i.status === "active" && <Tag tone="flux">Active</Tag>}
                </div>
                <ArrowRight className="w-4 h-4 text-navy/30" />
              </Link>
            </motion.div>
          ))
        )}
      </Card>
    </>
  );
}
