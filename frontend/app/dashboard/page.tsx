"use client";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, ArrowRight, ShieldAlert, Timer, Radio } from "lucide-react";
import { useDash } from "@/components/dashboard/Provider";
import { Card, IssueBadge, PageHeader, Stat, Tag } from "@/components/dashboard/ui";
import { Bars, HourlyStack } from "@/components/dashboard/Charts";
import NigeriaRiskMap from "@/components/dashboard/NigeriaRiskMap";
import { channelSplit } from "@/lib/mock";

export default function Overview() {
  const { role, phase, incidents: allIncidents, summary, isBackendLive } = useDash();
  const live = (allIncidents || []).filter((i) => phase >= (i.id === "INC-0421" ? 2 : i.id === "INC-0422" ? 3 : 4)).sort((a, b) => b.priority - a.priority);

  const complaintsCount = summary?.total_complaints
    ? summary.total_complaints.toLocaleString()
    : phase >= 2
    ? "1,248"
    : "512";

  const exposureFormatted = summary?.money_at_risk
    ? `₦${(Number(summary.money_at_risk) / 1000000).toFixed(1)}m`
    : phase >= 2
    ? "₦48.2m"
    : "₦0";

  const openIncidentsCount = summary?.open_incidents !== undefined
    ? String(summary.open_incidents)
    : String(live.filter((i) => i.status !== "monitoring").length);

  const kpis = {
    agent: [
      ["Open incidents", openIncidentsCount, "need attention"],
      ["Awaiting approval", phase >= 4 ? "1" : "0", "customer message"],
      ["Complaints monitored", complaintsCount, "across all channels"],
    ],
    it: [
      ["Likely cause", phase >= 3 ? "v4.2.1" : "Pending", phase >= 3 ? "87% confidence" : "investigating"],
      ["Failure rate", phase >= 2 ? "38%" : "1.1%", "USSD + app path"],
      ["Affected switch", phase >= 3 ? "Switch B" : "—", "94% of failures"],
    ],
    management: [
      ["Money at risk", exposureFormatted, "unreversed debits"],
      ["Time to detect", phase >= 2 ? "3 min" : "—", "from first rise"],
      ["SLA exposure", phase >= 2 ? "184 cases" : "0", "reversal pending"],
    ],
  }[role];

  return (
    <>
      <AnimatePresence mode="wait">
        {phase >= 2 ? (
          <motion.div
            key="alert"
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
                LIVE THREAT DETECTED · 10:15
              </p>
              <h2 className="text-2xl md:text-3xl font-semibold mt-1" style={{ letterSpacing: "-0.03em" }}>
                Failed transfers spiking on USSD and the app
              </h2>
              <p className="opacity-90 mt-1">
                {phase >= 3
                  ? "Likely cause: release v4.2.1 (87% confidence). Drafts ready for your approval."
                  : "AI Agent is correlating complaints with system events…"}
              </p>
            </div>
            <Link
              href="/dashboard/incidents/INC-0421"
              className="inline-flex items-center gap-2 bg-navy text-white font-semibold px-5 py-3 rounded-full hover:bg-navy-600 transition-colors"
            >
              Open incident <ArrowRight className="w-4 h-4" />
            </Link>
          </motion.div>
        ) : (
          <motion.div
            key="ok"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="rounded-3xl bg-white border border-navy/[0.06] p-6 mb-6 flex items-center gap-4"
          >
            <span className="w-3 h-3 rounded-full bg-emerald-500" />
            <p className="font-semibold text-navy">All systems normal.</p>
            <p className="text-navy/55">
              {phase === 1
                ? "Release v4.2.1 deployed at 10:00. Monitoring incoming streams…"
                : "No active spikes. Watching 9 Nigerian banking issue categories."}
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      <PageHeader
        title="Live overview"
        sub="Complaints from every channel, classified and watched for systemic spikes in real time."
        right={
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold">
            <Radio className="w-3.5 h-3.5 animate-pulse text-emerald-600" />
            {isBackendLive ? "FastAPI Backend Live · 4s Polling" : "Demo Simulation Engine Active"}
          </div>
        }
      />

      <div className="grid sm:grid-cols-3 gap-4 mb-6">
        {kpis.map(([l, v, h], i) => (
          <Stat key={l} label={l} value={v} hint={h} accent={i === 0} />
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mb-6">
        <Card className="lg:col-span-2 p-6">
          <h3 className="font-semibold text-navy mb-1">Complaints per hour by issue type</h3>
          <p className="text-sm text-navy/50 mb-4">Stacked, today</p>
          <HourlyStack phase={phase} />
        </Card>
        <Card className="p-6">
          <h3 className="font-semibold text-navy mb-1">Channel breakdown</h3>
          <p className="text-sm text-navy/50 mb-4">Complaints in the last 2 hours</p>
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
        {live.length === 0 && <p className="px-4 py-10 text-center text-navy/50">Nothing to show yet.</p>}
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
