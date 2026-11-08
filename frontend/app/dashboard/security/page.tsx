"use client";
import { useMemo } from "react";
import { Lock, ShieldAlert, Radio } from "lucide-react";
import { useDash } from "@/components/dashboard/Provider";
import { Card, PageHeader, SeverityBadge, Stat, Tag, Td, TableWrap, Th } from "@/components/dashboard/ui";
import { SpikeChart } from "@/components/dashboard/Charts";

export default function Security() {
  const { complaints, summary, isBackendLive } = useDash();

  const rows = useMemo(
    () => complaints.filter((c) => c.isFraud || c.issue === "fraud_scam"),
    [complaints]
  );

  const totalFraudExposure = useMemo(() => {
    const sum = rows.reduce((acc, c) => acc + (c.amount || 0), 0);
    if (sum >= 1_000_000) return `₦${(sum / 1_000_000).toFixed(2)}m`;
    if (sum > 0) return `₦${sum.toLocaleString()}`;
    return "₦0";
  }, [rows]);

  const topRegions = useMemo(() => {
    const counts = new Map<string, number>();
    rows.forEach((r) => {
      if (r.region && r.region !== "—") {
        counts.set(r.region, (counts.get(r.region) || 0) + 1);
      }
    });
    const sorted = Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 2)
      .map(([reg]) => reg);
    return sorted.length > 0 ? sorted.join(" & ") : "—";
  }, [rows]);

  const fraudSeries = useMemo(() => {
    const buckets = new Map<string, number>();
    rows.forEach((r) => {
      if (r.occurredAt) {
        const bucket = new Date(r.occurredAt).toISOString().slice(0, 13).replace("T", " ") + ":00 UTC";
        buckets.set(bucket, (buckets.get(bucket) || 0) + 1);
      }
    });
    const keys = Array.from(buckets.keys()).sort();
    return {
      labels: keys,
      series: keys.map((k) => buckets.get(k) || 0),
    };
  }, [rows]);

  return (
    <>
      <PageHeader
        title="Security queue"
        sub="Fraud flags and scam classifications from the latest 500 complaints. Dashboard data updates by polling."
        right={
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold">
              <Radio className="w-3.5 h-3.5 animate-pulse text-emerald-600" />
              {isBackendLive ? "Polling security data" : "Connecting…"}
            </span>
            <Tag tone="red">
              <Lock className="w-3 h-3 inline -mt-0.5 mr-1" />
              Restricted
            </Tag>
          </div>
        }
      />

      <div className="grid sm:grid-cols-3 gap-4 mb-4">
        <Stat
          label="Open fraud cases"
          value={String(summary?.fraud_count ?? rows.length)}
          hint="routed automatically by AI"
          accent
        />
        <Stat
          label="Primary cluster"
          value={topRegions}
          hint="highest fraud report density"
        />
        <Stat
          label="Reported fraud exposure"
          value={totalFraudExposure}
          hint="sum of mentioned amounts"
        />
      </div>

      {rows.length > 0 && (
        <Card className="p-6 mb-4">
          <div className="flex flex-wrap items-start justify-between gap-4 mb-2">
            <div className="flex gap-3">
              <div className="w-10 h-10 rounded-xl bg-red-100 flex items-center justify-center">
                <ShieldAlert className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <h3 className="font-semibold text-navy">
                  Active Fraud &amp; Social-Engineering Cluster ({topRegions})
                </h3>
                <p className="text-sm text-navy/55 max-w-xl mt-0.5">
                  {rows[0]?.summary || rows[0]?.text}
                </p>
              </div>
            </div>
            <button
              disabled
              className="px-5 py-2.5 rounded-full bg-navy text-white font-semibold hover:bg-navy-600 disabled:opacity-50 transition-colors"
            >
              Security escalation unavailable
            </button>
          </div>
          {fraudSeries.labels.length > 0 && (
            <SpikeChart
              series={fraudSeries.series}
              labels={fraudSeries.labels}
              height={200}
            />
          )}
        </Card>
      )}

      <Card className="overflow-hidden">
        <TableWrap>
          <thead className="bg-navy/[0.03]">
            <tr>
              <Th>Time</Th>
              <Th>Report</Th>
              <Th>Amount</Th>
              <Th>Severity</Th>
              <Th>Channel</Th>
              <Th>Region</Th>
              <Th>Customer ref</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-navy/5">
            {rows.map((c) => (
              <tr key={c.id} className="hover:bg-navy/[0.02]">
                <Td className="font-mono text-navy/50">{c.time}</Td>
                <Td className="max-w-md font-medium text-navy/90">{c.text}</Td>
                <Td className="font-semibold text-red-700">
                  {c.amount ? `₦${c.amount.toLocaleString()}` : "—"}
                </Td>
                <Td>
                  <SeverityBadge s={c.severity} />
                </Td>
                <Td>{c.channel}</Td>
                <Td>{c.region}</Td>
                <Td className="font-mono">{c.ref}</Td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center py-12 text-navy/50">
                  No active fraud complaints detected.
                </td>
              </tr>
            )}
          </tbody>
        </TableWrap>
      </Card>
    </>
  );
}
