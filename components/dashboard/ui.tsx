import type { ReactNode } from "react";
import type { IssueType, Severity } from "@/lib/types";
import { ISSUE_LABEL } from "@/lib/mock";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl bg-white border border-navy/[0.06] shadow-[0_1px_2px_rgba(20,35,63,.04)] ${className}`}>{children}</div>;
}
export function PageHeader({ title, sub, right }: { title: string; sub?: string; right?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
      <div><h1 className="text-3xl md:text-4xl font-semibold text-navy" style={{ letterSpacing: "-0.03em" }}>{title}</h1>{sub && <p className="text-navy/60 mt-1">{sub}</p>}</div>
      {right}
    </div>
  );
}
const sev: Record<Severity, string> = { low: "bg-navy/5 text-navy/70", medium: "bg-amber-100 text-amber-800", high: "bg-flux/15 text-[#b84d0e]", critical: "bg-red-100 text-red-700" };
export const SeverityBadge = ({ s }: { s: Severity }) => <span className={`px-2.5 py-1 rounded-full text-xs font-semibold capitalize ${sev[s]}`}>{s}</span>;
export const IssueBadge = ({ i }: { i: IssueType }) => <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${i === "fraud_scam" ? "bg-red-50 text-red-700" : "bg-navy/5 text-navy/80"}`}>{ISSUE_LABEL[i]}</span>;
export const Tag = ({ children, tone = "navy" }: { children: ReactNode; tone?: "navy" | "flux" | "green" | "red" }) => {
  const t = { navy: "bg-navy/5 text-navy/70", flux: "bg-flux/15 text-[#b84d0e]", green: "bg-emerald-100 text-emerald-700", red: "bg-red-100 text-red-700" }[tone];
  return <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${t}`}>{children}</span>;
};
export function Stat({ label, value, hint, accent }: { label: string; value: string; hint?: string; accent?: boolean }) {
  return (
    <Card className={`p-5 ${accent ? "!bg-navy !border-navy" : ""}`}>
      <p className={`text-sm ${accent ? "text-white/60" : "text-navy/55"}`}>{label}</p>
      <p className={`text-3xl font-semibold mt-1 ${accent ? "text-white" : "text-navy"}`} style={{ letterSpacing: "-0.03em" }}>{value}</p>
      {hint && <p className={`text-xs mt-1 ${accent ? "text-flux-soft" : "text-navy/45"}`}>{hint}</p>}
    </Card>
  );
}
export const Th = ({ children }: { children: ReactNode }) => <th className="text-left text-xs font-semibold uppercase tracking-wide text-navy/45 px-4 py-3 whitespace-nowrap">{children}</th>;
export const Td = ({ children, className = "" }: { children: ReactNode; className?: string }) => <td className={`px-4 py-3.5 text-sm text-navy/85 ${className}`}>{children}</td>;
export const TableWrap = ({ children }: { children: ReactNode }) => <div className="overflow-x-auto"><table className="w-full min-w-[640px]">{children}</table></div>;
