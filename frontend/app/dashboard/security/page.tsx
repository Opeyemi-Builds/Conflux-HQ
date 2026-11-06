"use client";
import { useState } from "react";
import { Lock, ShieldAlert } from "lucide-react";
import { useDash } from "@/components/dashboard/Provider";
import { Card, PageHeader, SeverityBadge, Stat, Tag, Td, TableWrap, Th } from "@/components/dashboard/ui";
import { SpikeChart } from "@/components/dashboard/Charts";
import { incidents } from "@/lib/mock";

export default function Security() {
  const { complaints, phase } = useDash();
  const [done, setDone] = useState(false);
  const inc = incidents[1];
  const rows = complaints.filter((c) => c.issue === "fraud_scam");
  return (
    <>
      <PageHeader title="Security queue" sub="Fraud and scam complaints are kept apart from the normal queue." right={<Tag tone="red"><Lock className="w-3 h-3 inline -mt-0.5 mr-1" />Restricted</Tag>} />
      <div className="grid sm:grid-cols-3 gap-4 mb-4"><Stat label="Open cases" value={String(rows.length)} hint="routed automatically" accent /><Stat label="Cluster size" value={String(inc.volume)} hint="Kano, since 10:05" /><Stat label="Exposure" value={inc.moneyAtRisk} hint="estimated" /></div>
      <Card className="p-6 mb-4">
        <div className="flex flex-wrap items-start justify-between gap-4 mb-2">
          <div className="flex gap-3"><div className="w-10 h-10 rounded-xl bg-red-100 flex items-center justify-center"><ShieldAlert className="w-5 h-5 text-red-600" /></div><div><h3 className="font-semibold text-navy">{inc.title}</h3><p className="text-sm text-navy/55 max-w-xl mt-0.5">{inc.summary.agent}</p></div></div>
          <button onClick={() => setDone(true)} disabled={done || phase < 3} className="px-5 py-2.5 rounded-full bg-navy text-white font-semibold hover:bg-navy-600 disabled:opacity-50 transition-colors">{done ? "Escalated to security" : "Escalate to security"}</button>
        </div>
        <SpikeChart series={inc.series} phase={4} height={200} />
      </Card>
      <Card className="overflow-hidden">
        <TableWrap><thead className="bg-navy/[0.03]"><tr><Th>Time</Th><Th>Report</Th><Th>Severity</Th><Th>Channel</Th><Th>Region</Th><Th>Customer ref</Th></tr></thead>
          <tbody className="divide-y divide-navy/5">{rows.map((c) => (<tr key={c.id} className="hover:bg-navy/[0.02]"><Td className="font-mono text-navy/50">{c.time}</Td><Td className="max-w-md">{c.text}</Td><Td><SeverityBadge s={c.severity} /></Td><Td>{c.channel}</Td><Td>{c.region}</Td><Td className="font-mono">{c.ref}</Td></tr>))}</tbody></TableWrap>
      </Card>
    </>
  );
}
