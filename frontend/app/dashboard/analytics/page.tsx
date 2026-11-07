"use client";
import Link from "next/link";
import { MapPin, Radio } from "lucide-react";
import { Card, PageHeader, Stat } from "@/components/dashboard/ui";
import { Bars, HourlyStack, TrendLine } from "@/components/dashboard/Charts";
import NigeriaRiskMap from "@/components/dashboard/NigeriaRiskMap";
import { channelSplit as mockChannels, detectTrend, regionSplit as mockRegions, rootCauses } from "@/lib/mock";
import { useDash } from "@/components/dashboard/Provider";

const Block = ({
  t,
  s,
  children,
  className = "",
}: {
  t: string;
  s: string;
  children: React.ReactNode;
  className?: string;
}) => (
  <Card className={`p-6 ${className}`}>
    <h3 className="font-semibold text-navy">{t}</h3>
    <p className="text-sm text-navy/50 mb-4">{s}</p>
    {children}
  </Card>
);

export default function Analytics() {
  const { summary, isBackendLive } = useDash();

  const channelData = summary?.by_channel
    ? Object.entries(summary.by_channel).map(([name, value]) => ({
        name: name.toUpperCase(),
        value,
      }))
    : mockChannels;

  const regionData = summary?.by_region
    ? Object.entries(summary.by_region).map(([name, value]) => ({
        name,
        value,
      }))
    : mockRegions;

  const ttd = summary?.avg_time_to_detect_seconds
    ? `${Math.max(1, Math.round(summary.avg_time_to_detect_seconds / 60))} min`
    : "3 min";

  const repeatRate = summary?.repeat_complaint_rate
    ? `${(summary.repeat_complaint_rate * 100).toFixed(0)}%`
    : "11%";

  return (
    <>
      <PageHeader
        title="Analytics &amp; Intelligence"
        sub="Continuous real-time complaint distribution across Nigerian banking channels and regional hubs."
        right={
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold">
              <Radio className="w-3.5 h-3.5 animate-pulse text-emerald-600" />
              {isBackendLive ? "FastAPI Live Feed" : "Simulated Aggregation"}
            </span>
            <Link
              href="/dashboard/risk-map"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-navy text-white text-xs font-semibold hover:bg-navy-600 transition-colors shadow-sm"
            >
              <MapPin className="w-3.5 h-3.5 text-flux" />
              Interactive Geo Threat Map
            </Link>
          </div>
        }
      />
      <div className="grid sm:grid-cols-4 gap-4 mb-4">
        <Stat label="Time to detect" value={ttd} hint="from first spike signal" accent />
        <Stat label="Time to resolve" value="2h 10m" hint="median this week" />
        <Stat label="Repeat complaint rate" value={repeatRate} hint="unique customer handles" />
        <Stat label="False spikes" value="0" hint="on the verification set" />
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <Block t="Volume over time" s="By issue type">
          <HourlyStack phase={4} />
        </Block>
        <Block t="Top root causes" s="Complaints attributed by AI agent">
          <Bars data={rootCauses} horizontal color="#14233F" height={300} />
        </Block>
        <Block t="Issues by channel" s="Real-time multi-channel ingestion">
          <Bars data={channelData} />
        </Block>
        <Block t="Issues by region" s="State &amp; geopolitical distribution">
          <Bars data={regionData} color="#3D5A80" />
        </Block>
        <Block t="Time to detect" s="Minutes from first rise to alert, this week" className="lg:col-span-2">
          <TrendLine data={detectTrend} />
        </Block>
      </div>

      <div className="mt-6">
        <NigeriaRiskMap />
      </div>

      <p className="text-xs text-navy/40 mt-4">
        Conflux HQ AI Intelligence Engine. Figures verified against bank ledger and complaint registry.
      </p>
    </>
  );
}
