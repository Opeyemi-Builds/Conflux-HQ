"use client";

import { useDash } from "@/components/dashboard/Provider";
import { PageHeader, Stat } from "@/components/dashboard/ui";
import NigeriaRiskMap from "@/components/dashboard/NigeriaRiskMap";

export default function RiskMapPage() {
  const { complaints, summary, incidents, isBackendLive } = useDash();

  const totalExposure = summary?.money_at_risk
    ? `₦${(Number(summary.money_at_risk) / 1_000_000).toFixed(2)}M`
    : `₦${(complaints.reduce((a, c) => a + (c.amount || 0), 0) / 1_000_000).toFixed(2)}M`;

  const criticalCases = complaints.filter((c) => c.severity === "critical" || c.severity === "high").length;
  const primaryInc = incidents[0];

  const regionCounts = new Map<string, number>();
  complaints.forEach((c) => {
    const r = c.region || "Lagos";
    regionCounts.set(r, (regionCounts.get(r) || 0) + 1);
  });
  let topRegion = "Lagos";
  let topCount = 0;
  regionCounts.forEach((cnt, reg) => {
    if (cnt > topCount) {
      topCount = cnt;
      topRegion = reg;
    }
  });

  return (
    <>
      <PageHeader
        title="Geospatial Threat &amp; Complaint Map"
        sub="Continuous real-time threat density mapping across Nigeria's banking channels."
        right={
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200">
              <span className="w-2 h-2 rounded-full bg-red-600 animate-ping" />
              {isBackendLive ? `Active Hotspot: ${topRegion} (${topCount} cases)` : "Connecting…"}
            </span>
          </div>
        }
      />

      <div className="grid sm:grid-cols-4 gap-4 mb-6">
        <Stat label="Total Capital At Risk" value={totalExposure} hint="live disputed exposure" accent />
        <Stat
          label="Primary Incident"
          value={primaryInc ? primaryInc.id.slice(0, 8) : "None"}
          hint={primaryInc ? primaryInc.title : "no active spike"}
        />
        <Stat label="Critical &amp; High Cases" value={`${criticalCases}`} hint={`of ${complaints.length} complaints`} />
        <Stat label="Highest Volume Zone" value={topRegion} hint={`${topCount} live complaints`} />
      </div>

      {/* Interactive Nigeria Threat Map */}
      <NigeriaRiskMap />
    </>
  );
}
