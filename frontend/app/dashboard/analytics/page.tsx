"use client";
import { Card, PageHeader, Stat } from "@/components/dashboard/ui";
import { Bars, HourlyStack, TrendLine } from "@/components/dashboard/Charts";
import { channelSplit, detectTrend, regionSplit, rootCauses } from "@/lib/mock";

const Block = ({ t, s, children, className = "" }: { t: string; s: string; children: React.ReactNode; className?: string }) => (<Card className={`p-6 ${className}`}><h3 className="font-semibold text-navy">{t}</h3><p className="text-sm text-navy/50 mb-4">{s}</p>{children}</Card>);
export default function Analytics() {
  return (
    <>
      <PageHeader title="Analytics" sub="How complaints change over time, by issue, channel and region." />
      <div className="grid sm:grid-cols-4 gap-4 mb-4"><Stat label="Time to detect" value="3 min" hint="was 41 min on Monday" accent /><Stat label="Time to resolve" value="2h 10m" hint="median this week" /><Stat label="Repeat complaint rate" value="11%" hint="down from 19%" /><Stat label="False spikes" value="0" hint="on the test set" /></div>
      <div className="grid lg:grid-cols-2 gap-4">
        <Block t="Volume over time" s="By issue type"><HourlyStack phase={4} /></Block>
        <Block t="Top root causes" s="Complaints attributed"><Bars data={rootCauses} horizontal color="#14233F" height={300} /></Block>
        <Block t="Issues by channel" s="All issue types"><Bars data={channelSplit} /></Block>
        <Block t="Issues by region" s="All issue types"><Bars data={regionSplit} color="#3D5A80" /></Block>
        <Block t="Time to detect" s="Minutes from first rise to alert, this week" className="lg:col-span-2"><TrendLine data={detectTrend} /></Block>
      </div>
      <p className="text-xs text-navy/40 mt-4">Synthetic data. Figures are illustrative until measured on the labelled test set.</p>
    </>
  );
}
