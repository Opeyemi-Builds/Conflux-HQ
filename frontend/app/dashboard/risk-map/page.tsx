"use client";

import { PageHeader, Stat } from "@/components/dashboard/ui";
import NigeriaRiskMap from "@/components/dashboard/NigeriaRiskMap";

export default function RiskMapPage() {
  return (
    <>
      <PageHeader
        title="Geospatial Threat &amp; Complaint Map"
        sub="Continuous real-time threat density mapping across Nigeria's banking channels."
        right={
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200">
              <span className="w-2 h-2 rounded-full bg-red-600 animate-ping" />
              Active High-Risk Hotspot: Lagos / VI
            </span>
          </div>
        }
      />

      <div className="grid sm:grid-cols-4 gap-4 mb-6">
        <Stat label="Total Capital At Risk" value="₦48.25M" hint="concentrated in South-West" accent />
        <Stat label="Primary Incident" value="INC-0421" hint="Switch B USSD timeout" />
        <Stat label="Critical Complaints" value="284 cases" hint="unreversed > ₦100k" />
        <Stat label="Fastest Rising Zone" value="Lagos Metro" hint="+640% rise vs baseline" />
      </div>

      {/* Interactive Nigeria Threat Map */}
      <NigeriaRiskMap />
    </>
  );
}
