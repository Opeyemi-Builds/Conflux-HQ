"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  DatabaseZap,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
  Siren,
  Timer,
} from "lucide-react";
import { useDash } from "@/components/dashboard/Provider";
import { Card, IssueBadge, PageHeader, Stat, Tag } from "@/components/dashboard/ui";
import { api } from "@/lib/api";

const STATUS_FILTERS = [
  { id: "all", label: "All incidents" },
  { id: "open", label: "Open / Active" },
  { id: "awaiting_approval", label: "Awaiting sign-off" },
  { id: "monitoring", label: "Monitoring" },
  { id: "resolved", label: "Resolved" },
] as const;

export default function IncidentsListPage() {
  const { incidents, isLoading, detectNow, syncing, refresh, user } = useDash();
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]["id"]>("all");
  const [query, setQuery] = useState("");
  const [seeding, setSeeding] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const canWrite = user?.role !== "manager";

  const filtered = useMemo(() => {
    return [...incidents]
      .sort((a, b) => b.priority - a.priority)
      .filter((inc) => {
        if (statusFilter === "open") {
          if (inc.status === "resolved" || inc.rawStatus === "dismissed") return false;
        } else if (statusFilter === "awaiting_approval") {
          const hasPending = inc.drafts?.some((d) => d.status === "pending");
          if (!hasPending && inc.rawStatus !== "awaiting_approval") return false;
        } else if (statusFilter === "monitoring") {
          if (inc.status !== "monitoring" && inc.rawStatus !== "monitoring") return false;
        } else if (statusFilter === "resolved") {
          if (inc.status !== "resolved" && inc.rawStatus !== "resolved") return false;
        }

        if (query.trim()) {
          const q = query.trim().toLowerCase();
          const hay = `${inc.title} ${inc.summary} ${inc.issue} ${inc.region} ${inc.channels.join(" ")}`.toLowerCase();
          if (!hay.includes(q)) return false;
        }
        return true;
      });
  }, [incidents, statusFilter, query]);

  const activeCount = incidents.filter((i) => i.status !== "resolved" && i.rawStatus !== "dismissed").length;
  const securityCount = incidents.filter((i) => i.status === "security" || i.issue === "fraud_scam").length;
  const awaitingApprovalCount = incidents.filter(
    (i) => i.rawStatus === "awaiting_approval" || i.drafts?.some((d) => d.status === "pending")
  ).length;

  const handleSeedDemo = async () => {
    setSeeding(true);
    setActionMsg(null);
    try {
      const seeded = await api.seedScenario(true);
      const detected = await api.detectSpikes(seeded.detection_at).catch(() => []);
      await refresh();
      setActionMsg(
        `Seeded ${seeded.complaints_created} complaints & detected ${detected.length} incident spikes.`
      );
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : "Could not seed demo scenario.");
    } finally {
      setSeeding(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Incidents"
        sub="Clustered operational spikes, correlation evidence, and human-approved remediation drafts."
        right={
          <div className="flex flex-wrap items-center gap-2.5">
            {canWrite && (
              <button
                type="button"
                disabled={seeding || syncing}
                onClick={() => void handleSeedDemo()}
                className="inline-flex items-center gap-1.5 rounded-full bg-white border border-navy/10 hover:bg-navy/[0.03] text-navy px-4 py-2 text-xs font-semibold transition-colors disabled:opacity-50"
              >
                {seeding ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-flux" />
                ) : (
                  <DatabaseZap className="w-3.5 h-3.5 text-flux" />
                )}
                {seeding ? "Seeding demo…" : "Seed demo scenario"}
              </button>
            )}
            <button
              type="button"
              disabled={syncing || !canWrite}
              onClick={() => void detectNow()}
              className="inline-flex items-center gap-1.5 rounded-full bg-navy text-white hover:bg-navy-600 px-4 py-2 text-xs font-semibold transition-colors disabled:opacity-50"
            >
              {syncing ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-flux" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5 text-flux" />
              )}
              {syncing ? "Scanning spikes…" : "Detect spikes now"}
            </button>
          </div>
        }
      />

      {actionMsg && (
        <Card className="p-4 mb-5 border-l-4 !border-l-flux bg-white flex items-center justify-between gap-3">
          <p className="text-xs font-medium text-navy">{actionMsg}</p>
          <button
            type="button"
            onClick={() => setActionMsg(null)}
            className="text-xs text-navy/50 hover:text-navy underline"
          >
            Dismiss
          </button>
        </Card>
      )}

      <div className="grid sm:grid-cols-4 gap-4 mb-6">
        <Stat label="Total incidents" value={String(incidents.length)} hint="tracked in current window" />
        <Stat label="Active spikes" value={String(activeCount)} hint="open or investigating" accent />
        <Stat label="Awaiting sign-off" value={String(awaitingApprovalCount)} hint="drafts pending approval" />
        <Stat label="Security & fraud" value={String(securityCount)} hint="elevated risk priority" />
      </div>

      {/* Filters & Search Bar */}
      <Card className="p-4 mb-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1.5">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setStatusFilter(f.id)}
                className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                  statusFilter === f.id
                    ? "bg-navy text-white"
                    : "bg-navy/[0.04] text-navy/65 hover:bg-navy/[0.08]"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="relative min-w-[240px] flex-1 max-w-sm">
            <Search className="w-4 h-4 text-navy/40 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter by title, issue, channel, region…"
              className="w-full rounded-full bg-cream/70 border border-navy/10 pl-9 pr-4 py-1.5 text-xs text-navy placeholder:text-navy/40 focus:outline-none focus:border-flux"
            />
          </div>
        </div>
      </Card>

      {/* Incidents List */}
      <Card className="p-2">
        <div className="flex items-center justify-between px-4 pt-4 pb-2">
          <h3 className="font-semibold text-navy">Incident queue, ranked by priority score</h3>
          <Tag>{filtered.length} shown</Tag>
        </div>

        {isLoading ? (
          <div className="p-4 space-y-3">
            {[0, 1, 2, 3].map((idx) => (
              <div
                key={idx}
                className="h-20 rounded-2xl bg-navy/[0.04] animate-pulse px-5 flex items-center justify-between"
              >
                <div className="space-y-2">
                  <div className="h-4 w-64 rounded bg-navy/10" />
                  <div className="h-3 w-44 rounded bg-navy/10" />
                </div>
                <div className="h-6 w-24 rounded-full bg-navy/10" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-6 py-14 text-center">
            <div className="w-12 h-12 rounded-2xl bg-flux/10 text-flux flex items-center justify-center mx-auto mb-3">
              <Siren className="w-6 h-6" />
            </div>
            <h4 className="text-base font-semibold text-navy">
              {incidents.length === 0 ? "No incidents — seed the demo" : "No incidents match your filter"}
            </h4>
            <p className="text-sm text-navy/55 max-w-md mx-auto mt-1 mb-5">
              {incidents.length === 0
                ? "Seed the synthetic Nigerian banking spike scenario or run spike detection on existing complaints to populate the incident queue."
                : "Try clearing your status filter or search query to inspect all incidents."}
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3">
              {incidents.length === 0 && canWrite ? (
                <>
                  <button
                    type="button"
                    disabled={seeding}
                    onClick={() => void handleSeedDemo()}
                    className="inline-flex items-center gap-2 rounded-full bg-flux hover:bg-[#d4560f] text-white px-5 py-2.5 text-xs font-semibold transition-colors disabled:opacity-50"
                  >
                    {seeding ? <Loader2 className="w-4 h-4 animate-spin" /> : <DatabaseZap className="w-4 h-4" />}
                    {seeding ? "Seeding demo scenario…" : "Seed demo & detect spikes"}
                  </button>
                  <button
                    type="button"
                    disabled={syncing}
                    onClick={() => void detectNow()}
                    className="inline-flex items-center gap-2 rounded-full bg-navy text-white px-5 py-2.5 text-xs font-semibold hover:bg-navy-600 transition-colors disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${syncing ? "animate-spin text-flux" : "text-flux"}`} />
                    Run spike detection
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setStatusFilter("all");
                    setQuery("");
                  }}
                  className="inline-flex items-center gap-2 rounded-full bg-navy text-white px-4 py-2 text-xs font-semibold"
                >
                  Reset filters
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="divide-y divide-navy/[0.05]">
            {filtered.map((inc, idx) => {
              const pendingDrafts = inc.drafts?.filter((d) => d.status === "pending").length || 0;
              return (
                <motion.div
                  key={inc.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.04 }}
                >
                  <Link
                    href={`/dashboard/incidents/${inc.id}`}
                    className="flex flex-wrap items-center gap-4 px-4 py-4 rounded-xl hover:bg-navy/[0.03] transition-colors"
                  >
                    <div className="w-14 text-center shrink-0">
                      <p className="text-2xl font-semibold text-navy leading-none">{inc.priority}</p>
                      <p className="text-[10px] uppercase tracking-wider text-navy/40 mt-1">priority</p>
                    </div>

                    <div className="flex-1 min-w-[240px]">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-navy">{inc.title}</p>
                        <span className="text-[11px] font-mono text-navy/40">#{inc.id.slice(0, 8)}</span>
                      </div>
                      <p className="text-xs text-navy/65 mt-0.5 line-clamp-1">{inc.summary}</p>
                      <p className="text-xs text-navy/50 mt-1 flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center gap-1">
                          <Timer className="w-3.5 h-3.5" />
                          Started {inc.startedAt}
                        </span>
                        <span>·</span>
                        <span>{inc.volume} complaints</span>
                        <span>·</span>
                        <span>{inc.moneyAtRisk} at risk</span>
                        <span>·</span>
                        <span>{inc.region}</span>
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      {pendingDrafts > 0 && (
                        <Tag tone="flux">
                          <AlertTriangle className="w-3 h-3 inline -mt-0.5 mr-1" />
                          {pendingDrafts} draft{pendingDrafts > 1 ? "s" : ""} pending
                        </Tag>
                      )}
                      <IssueBadge i={inc.issue} />
                      {inc.status === "security" && (
                        <Tag tone="red">
                          <ShieldAlert className="w-3 h-3 inline -mt-0.5 mr-1" />
                          Security
                        </Tag>
                      )}
                      {inc.status === "monitoring" && <Tag>Monitoring</Tag>}
                      {inc.status === "resolved" && <Tag tone="green">Resolved</Tag>}
                      {inc.status === "active" && <Tag tone="flux">{inc.rawStatus || "Active"}</Tag>}
                    </div>

                    <ArrowRight className="w-4 h-4 text-navy/35 shrink-0" />
                  </Link>
                </motion.div>
              );
            })}
          </div>
        )}
      </Card>
    </>
  );
}
