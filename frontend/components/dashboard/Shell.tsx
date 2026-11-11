"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  BarChart3,
  BookOpen,
  Building2,
  KeyRound,
  LayoutDashboard,
  List,
  Loader2,
  LogOut,
  MapPin,
  Radio,
  Receipt,
  RefreshCw,
  ScrollText,
  ShieldAlert,
  Siren,
} from "lucide-react";
import { api } from "@/lib/api";
import { useDash } from "./Provider";

export default function Shell({ children }: { children: React.ReactNode }) {
  const [scanError, setScanError] = useState(false);
  const [healthStatus, setHealthStatus] = useState<"checking" | "ok" | "offline">("checking");
  const path = usePathname();
  const { detectNow, syncing, complaints, incidents, user, logoutUser, isBackendLive, isLoading, lastRefresh } = useDash();

  useEffect(() => {
    let mounted = true;
    const pollHealth = async () => {
      try {
        const res = await api.checkHealth();
        if (mounted) setHealthStatus(res.status === "ok" ? "ok" : "offline");
      } catch {
        if (mounted) setHealthStatus("offline");
      }
    };
    void pollHealth();
    const timer = setInterval(pollHealth, 15000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const nav = [
    { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
    { href: "/dashboard/incidents", label: "Incidents", icon: Siren },
    { href: "/dashboard/complaints", label: "Complaints", icon: List },
    { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
    { href: "/dashboard/reconciliation", label: "Reconciliation", icon: Receipt },
    { href: "/dashboard/social", label: "Social monitoring", icon: Radio },
    { href: "/dashboard/security", label: "Security queue", icon: ShieldAlert },
    { href: "/dashboard/settings/keys", label: "API keys", icon: KeyRound },
    { href: "/dashboard/risk-map", label: "Geo Risk Map", icon: MapPin },
    { href: "/dashboard/audit", label: "Audit log", icon: ScrollText },
  ];

  const active = (h: string) => {
    if (h === "/dashboard") return path === "/dashboard";
    if (h === "/dashboard/settings/keys") return path.startsWith("/dashboard/settings");
    return path.startsWith(h);
  };

  const fraudCount = complaints.filter((c) => c.isFraud || c.issue === "fraud_scam").length;
  const openIncidentsCount = incidents.filter((i) => i.status !== "resolved" && i.rawStatus !== "dismissed").length;

  return (
    <div className="min-h-screen bg-cream lg:flex">
      <aside className="hidden lg:flex w-64 shrink-0 flex-col bg-navy text-white p-5 sticky top-0 h-screen">
        <Link href="/" className="flex items-center gap-2.5 mb-6 px-2">
          <img
            src="/conflux-logo-full.jpg"
            alt="Conflux HQ"
            className="h-8 w-auto rounded-lg object-contain bg-white px-1.5 py-0.5"
          />
          <span className="text-lg font-semibold tracking-tight">
            Conflux <span className="text-flux">HQ</span>
          </span>
        </Link>

        {/* Active Bank Tenant Card */}
        <div className="mb-5 rounded-2xl bg-white/[0.06] border border-white/[0.08] p-3.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-8 h-8 rounded-xl bg-flux/20 text-flux flex items-center justify-center shrink-0">
                <Building2 className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-white truncate">
                  {user?.bank?.name || "Zymic Bank"}
                </p>
                <p className="text-[11px] text-white/55 truncate">
                  {user?.full_name || user?.email || "Operations Console"}
                </p>
              </div>
            </div>
            <button
              onClick={logoutUser}
              title="Sign out"
              className="p-1.5 rounded-lg text-white/50 hover:text-white hover:bg-white/10 transition-colors shrink-0"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>

        <nav className="space-y-1 flex-1 overflow-y-auto pr-1">
          {nav.map(({ href, label, icon: I }) => (
            <Link
              key={label}
              href={href}
              className={`relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-[14px] font-medium transition-colors ${
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
              <I className="w-[17px] h-[17px] relative shrink-0" />
              <span className="relative truncate">{label}</span>
              {label === "Incidents" && openIncidentsCount > 0 && (
                <span className="relative ml-auto text-[11px] bg-white/15 text-white rounded-full px-2 py-0.5">
                  {openIncidentsCount}
                </span>
              )}
              {label === "Security queue" && fraudCount > 0 && (
                <span className="relative ml-auto text-[11px] bg-flux rounded-full px-2 py-0.5">
                  {fraudCount}
                </span>
              )}
            </Link>
          ))}
        </nav>

        <div className="mt-4 pt-3 border-t border-white/10 space-y-2">
          <Link
            href="/developers"
            className="flex items-center justify-between rounded-xl bg-white/[0.06] hover:bg-white/10 px-3 py-2.5 text-xs font-medium text-white/85 transition-colors"
          >
            <span className="inline-flex items-center gap-2">
              <BookOpen className="w-3.5 h-3.5 text-flux-soft" />
              Developer API Docs
            </span>
            <span className="font-mono text-[10px] text-flux-soft">v1</span>
          </Link>
          <div className="rounded-xl bg-white/5 px-3 py-2 text-xs text-white/60 flex items-center justify-between gap-2">
            <Link href="/login" className="text-flux-soft hover:underline font-medium">
              Switch account
            </Link>
            <button
              type="button"
              onClick={logoutUser}
              className="text-white/55 hover:text-white transition-colors"
            >
              Log out
            </button>
          </div>
        </div>
      </aside>

      <div className="flex-1 min-w-0">
        <header className="sticky top-0 z-30 bg-cream/85 backdrop-blur-xl border-b border-navy/[0.06] px-4 md:px-8 py-3 flex flex-wrap items-center gap-3 justify-between">
          <div className="flex items-center gap-2 lg:hidden">
            <img
              src="/conflux-logo-full.jpg"
              alt="Conflux HQ"
              className="h-7 w-auto rounded object-contain bg-white px-1 py-0.5"
            />
            <span className="font-semibold text-navy">Conflux HQ</span>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 text-xs text-navy/60">
            <span className="font-medium text-navy">
              {user?.bank?.name ? `${user.bank.name} Operations Console` : "Operations Console"}
            </span>
            {user?.role && (
              <span className="hidden sm:inline-block rounded-full bg-navy/5 px-2.5 py-0.5 text-[11px] font-mono text-navy/65">
                {user.role}
              </span>
            )}
            <span
              title="Backend /api/v1/health status"
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium border ${
                healthStatus === "ok"
                  ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                  : healthStatus === "offline"
                  ? "bg-amber-50 text-amber-800 border-amber-200"
                  : "bg-navy/5 text-navy/60 border-navy/10"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  healthStatus === "ok"
                    ? "bg-emerald-500"
                    : healthStatus === "offline"
                    ? "bg-amber-500"
                    : "bg-navy/40 animate-pulse"
                }`}
              />
              {healthStatus === "ok" ? "API Live" : healthStatus === "offline" ? "API Offline" : "Checking API…"}
            </span>
          </div>

          <div className="flex items-center gap-2.5">
            <button type="button" onClick={logoutUser} className="text-xs underline lg:hidden">
              Sign out
            </button>
            <Link
              href="/developers"
              className="hidden md:inline-flex items-center gap-1.5 text-xs font-medium text-navy/75 bg-white hover:bg-navy/[0.03] rounded-full px-3.5 py-1.5 border border-navy/[0.08] transition-colors"
            >
              <BookOpen className="w-3.5 h-3.5 text-flux" />
              API Docs
            </Link>
            <Link
              href="/dashboard/settings/keys"
              className="hidden sm:inline-flex items-center gap-1.5 text-xs font-medium text-navy/75 bg-white hover:bg-navy/[0.03] rounded-full px-3.5 py-1.5 border border-navy/[0.08] transition-colors"
            >
              <KeyRound className="w-3.5 h-3.5 text-flux" />
              API Keys
            </Link>
            <button
              onClick={async () => {
                setScanError(false);
                try {
                  await detectNow();
                } catch {
                  setScanError(true);
                }
              }}
              disabled={syncing || user?.role === "manager"}
              className="inline-flex items-center gap-2 bg-navy text-white text-xs sm:text-sm font-semibold px-4 py-2 rounded-full hover:bg-navy-600 disabled:opacity-80 transition-colors shadow-sm"
            >
              {syncing ? (
                <Loader2 className="w-4 h-4 animate-spin text-flux" />
              ) : (
                <RefreshCw className="w-4 h-4 text-flux" />
              )}
              {syncing ? "Scanning Spikes…" : "Run spike detection"}
            </button>
          </div>
        </header>
        {scanError && (
          <p role="alert" className="px-4 py-2 text-sm text-red-700">
            Spike detection failed. Try again.
          </p>
        )}
        <div className="lg:hidden flex gap-1 overflow-x-auto px-4 py-2 bg-navy">
          {nav.map(({ href, label }) => (
            <Link
              key={label}
              href={href}
              className={`whitespace-nowrap text-xs px-3 py-1.5 rounded-full ${
                active(href) ? "bg-white/15 text-white font-semibold" : "text-white/60"
              }`}
            >
              {label}
            </Link>
          ))}
          <Link
            href="/developers"
            className="whitespace-nowrap text-xs px-3 py-1.5 rounded-full text-flux-soft"
          >
            Docs
          </Link>
        </div>
        <main className="px-4 md:px-8 py-8 max-w-[88rem] mx-auto">
          {!isLoading && !isBackendLive && (
            <p role="status" className="mb-4 text-sm text-amber-800">
              {lastRefresh ? "Dashboard figures may be out of date." : "Dashboard figures could not be loaded."}
            </p>
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
