"use client";
import Link from "next/link";
import { MapPin } from "lucide-react";
import { Card, PageHeader, Stat } from "@/components/dashboard/ui";
import { Bars, HourlyStack, TrendLine } from "@/components/dashboard/Charts";
import NigeriaRiskMap from "@/components/dashboard/NigeriaRiskMap";
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
  const {
    summary,
    transactionsAnalytics,
    hourlySeries,
    channelSplit,
    regionSplit,
    rootCauses,
    detectTrend,
  } = useDash();

  const ttd =
    summary?.avg_time_to_detect_seconds != null
      ? `${Math.max(1, Math.round(summary.avg_time_to_detect_seconds / 60))} min`
      : "—";

  const repeatRate =
    summary?.repeat_complaint_rate != null
      ? `${(summary.repeat_complaint_rate * 100).toFixed(1)}%`
      : "—";

  const failedRate =
    transactionsAnalytics?.failed_rate != null
      ? `${(transactionsAnalytics.failed_rate * 100).toFixed(1)}%`
      : "—";

  const totalTxns =
    transactionsAnalytics?.total_transactions != null
      ? transactionsAnalytics.total_transactions.toLocaleString()
      : "—";

  return (
    <>
      <PageHeader
        title="Analytics &amp; Intelligence"
        sub="Bank aggregates cover 72 hours. Sample charts and map use up to the latest 500 complaints."
        right={
          <div className="flex items-center gap-2">
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
        <Stat
          label="Total complaints (72h)"
          value={summary?.total_complaints != null ? summary.total_complaints.toLocaleString() : "—"}
          hint="all intake channels"
        />
        <Stat label="Repeat complaint rate" value={repeatRate} hint="unique customer handles" />
        <Stat label="Switch failure rate" value={failedRate} hint={`${totalTxns} transactions`} />
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <Block t="Volume over time" s="Latest complaint sample by issue and UTC hour">
          <HourlyStack data={hourlySeries} />
        </Block>
        <Block t="Complaints by issue category" s="Complaint categories">
          <Bars data={rootCauses} horizontal color="#14233F" height={300} />
        </Block>
        <Block t="Issues by channel" s="Channel breakdown from bank totals or the latest complaint sample">
          <Bars data={channelSplit} />
        </Block>
        <Block t="Issues by region" s="State &amp; geopolitical distribution">
          <Bars data={regionSplit} color="#3D5A80" />
        </Block>
        <Block
          t="Hourly complaint velocity"
          s="Complaint totals by hour"
          className="lg:col-span-2"
        >
          <TrendLine data={detectTrend} />
        </Block>
      </div>

      <div className="mt-6">
        <NigeriaRiskMap />
      </div>
    </>
  );
}
