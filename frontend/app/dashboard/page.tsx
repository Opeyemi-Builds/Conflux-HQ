"use client";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, ArrowRight, ShieldAlert, Timer } from "lucide-react";
import { useDash } from "@/components/dashboard/Provider";
import { Card, IssueBadge, PageHeader, Stat, Tag } from "@/components/dashboard/ui";
import { Bars, HourlyStack } from "@/components/dashboard/Charts";
import NigeriaRiskMap from "@/components/dashboard/NigeriaRiskMap";

export default function Overview() {
  const {
    incidents,
    summary,
    transactionsAnalytics,
    hourlySeries,
    channelSplit,
  } = useDash();

  const live = incidents.filter((incident) => incident.status !== "resolved" && incident.rawStatus !== "dismissed").sort((a, b) => b.priority - a.priority);
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
              <p className="opacity-90 mt-1">
                {topIncident.summary}
              </p>
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
        sub="Monitor complaint trends and prioritize incidents across your bank."
      />

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
          <h3 className="font-semibold text-navy">Active incidents, ranked by priority</h3>
          <Tag>{live.length} listed</Tag>
        </div>
        {live.length === 0 && <p className="px-4 py-10 text-center text-navy/50">No active incidents detected.</p>}
        {live.map((i, idx) => (
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
        ))}
      </Card>
    </>
  );
}
