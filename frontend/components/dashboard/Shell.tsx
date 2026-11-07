"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { BarChart3, LayoutDashboard, List, Play, ScrollText, ShieldAlert, Siren, Loader2, MapPin } from "lucide-react";
import LogoIcon from "@/components/LogoIcon";
import { useDash } from "./Provider";
import type { Role } from "@/lib/types";

const nav = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/risk-map", label: "Geo Risk Map", icon: MapPin },
  { href: "/dashboard/incidents/INC-0421", label: "Incidents", icon: Siren },
  { href: "/dashboard/complaints", label: "Complaints", icon: List },
  { href: "/dashboard/security", label: "Security queue", icon: ShieldAlert },
  { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/dashboard/audit", label: "Audit log", icon: ScrollText },
];
const roles: { id: Role; label: string }[] = [
  { id: "agent", label: "Agent" },
  { id: "it", label: "IT" },
  { id: "management", label: "Management" },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { role, setRole, replay, replaying, phase, complaints, isBackendLive } = useDash();
  const active = (h: string) => (h === "/dashboard" ? path === h : path.startsWith(h.split("/").slice(0, 3).join("/")));
  const fraudCount = complaints.filter((c) => c.issue === "fraud_scam").length;

  return (
    <div className="min-h-screen bg-cream lg:flex">
      <aside className="hidden lg:flex w-64 shrink-0 flex-col bg-navy text-white p-5 sticky top-0 h-screen">
        <Link href="/" className="flex items-center gap-2.5 mb-10 px-2">
          <LogoIcon className="w-8 h-8" />
          <span className="text-xl font-semibold tracking-tight">
            Conflux <span className="text-flux">HQ</span>
          </span>
        </Link>
        <nav className="space-y-1 flex-1">
          {nav.map(({ href, label, icon: I }) => (
            <Link
              key={href}
              href={href}
              className={`relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-[15px] font-medium transition-colors ${
                active(href) ? "text-white" : "text-white/60 hover:text-white hover:bg-white/5"
              }`}
            >
              {active(href) && (
                <motion.span
                  layoutId="nav"
                  className="absolute inset-0 rounded-xl bg-white/10"
                  transition={{ type: "spring", stiffness: 400, damping: 34 }}
                />
              )}
              <I className="w-[18px] h-[18px] relative" />
              <span className="relative">{label}</span>
              {label === "Security queue" && (
                <span className="relative ml-auto text-[11px] bg-flux rounded-full px-2 py-0.5">
                  {fraudCount > 0 ? fraudCount : 34}
                </span>
              )}
            </Link>
          ))}
        </nav>
        <div className="rounded-xl bg-white/5 p-3 text-xs text-white/60 flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${isBackendLive ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
          {isBackendLive ? "Real-time backend connected" : "Local engine mode"}
        </div>
      </aside>

      <div className="flex-1 min-w-0">
        <header className="sticky top-0 z-30 bg-cream/85 backdrop-blur-xl border-b border-navy/[0.06] px-4 md:px-8 py-3 flex flex-wrap items-center gap-3 justify-between">
          <div className="flex items-center gap-2 lg:hidden">
            <LogoIcon className="w-7 h-7" />
            <span className="font-semibold text-navy">Conflux HQ</span>
          </div>
          <div className="flex items-center gap-1 rounded-full bg-white border border-navy/[0.06] p-1" role="tablist" aria-label="Role view">
            {roles.map((r) => (
              <button
                key={r.id}
                onClick={() => setRole(r.id)}
                role="tab"
                aria-selected={role === r.id}
                className={`relative px-4 py-1.5 text-sm font-medium rounded-full transition-colors ${
                  role === r.id ? "text-white" : "text-navy/60 hover:text-navy"
                }`}
              >
                {role === r.id && (
                  <motion.span
                    layoutId="role"
                    className="absolute inset-0 rounded-full bg-navy"
                    transition={{ type: "spring", stiffness: 420, damping: 34 }}
                  />
                )}
                <span className="relative">{r.label}</span>
              </button>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden sm:inline-flex items-center gap-1.5 text-xs font-medium text-navy/70 bg-white rounded-full px-3 py-1.5 border border-navy/[0.06]">
              <span className={`w-2 h-2 rounded-full ${isBackendLive ? "bg-emerald-500 animate-pulse" : "bg-flux"}`} />
              {isBackendLive ? "FastAPI Live · 4s Polling" : "Demo Mode"}
            </span>
            <button
              onClick={replay}
              disabled={replaying}
              className="inline-flex items-center gap-2 bg-flux text-white text-sm font-semibold px-4 py-2 rounded-full hover:bg-[#d25a14] disabled:opacity-80 transition-colors shadow-sm"
            >
              {replaying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              {replaying ? `Replaying ${phase}/4` : "Replay scenario"}
            </button>
          </div>
        </header>
        <div className="lg:hidden flex gap-1 overflow-x-auto px-4 py-2 bg-navy">
          {nav.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`whitespace-nowrap text-sm px-3 py-1.5 rounded-full ${
                active(href) ? "bg-white/15 text-white" : "text-white/60"
              }`}
            >
              {label}
            </Link>
          ))}
        </div>
        <main className="px-4 md:px-8 py-8 max-w-[88rem] mx-auto">{children}</main>
      </div>
    </div>
  );
}
