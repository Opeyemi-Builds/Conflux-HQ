"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  BarChart3,
  Building2,
  LayoutDashboard,
  List,
  Loader2,
  LogOut,
  MapPin,
  RefreshCw,
  ScrollText,
  ShieldAlert,
  Siren,
} from "lucide-react";
import LogoIcon from "@/components/LogoIcon";
import { useDash } from "./Provider";

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { detectNow, syncing, complaints, incidents, user, logoutUser, isBackendLive } = useDash();

  const primaryIncidentId = incidents[0]?.id || "latest";
  const nav = [
    { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
    { href: "/dashboard/risk-map", label: "Geo Risk Map", icon: MapPin },
    { href: `/dashboard/incidents/${primaryIncidentId}`, label: "Incidents", icon: Siren },
    { href: "/dashboard/complaints", label: "Complaints", icon: List },
    { href: "/dashboard/security", label: "Security queue", icon: ShieldAlert },
    { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
    { href: "/dashboard/audit", label: "Audit log", icon: ScrollText },
  ];

  const active = (h: string) =>
    h === "/dashboard" ? path === h : path.startsWith(h.split("/").slice(0, 3).join("/"));
  const fraudCount = complaints.filter((c) => c.isFraud || c.issue === "fraud_scam").length;

  const handleSignOut = () => {
    logoutUser();
    router.push("/login");
  };

  return (
    <div className="min-h-screen bg-cream lg:flex">
      <aside className="hidden lg:flex w-64 shrink-0 flex-col bg-navy text-white p-5 sticky top-0 h-screen">
        <Link href="/" className="flex items-center gap-2.5 mb-8 px-2">
          <LogoIcon className="w-8 h-8" />
          <span className="text-xl font-semibold tracking-tight">
            Conflux <span className="text-flux">HQ</span>
          </span>
        </Link>

        {/* Active Bank Tenant Card */}
        <div className="mb-6 rounded-2xl bg-white/[0.06] border border-white/[0.08] p-3.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-8 h-8 rounded-xl bg-flux/20 text-flux flex items-center justify-center shrink-0">
                <Building2 className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-white truncate">
                  {user?.bank?.name || (isBackendLive ? "Authenticated Bank" : "Connecting…")}
                </p>
                <p className="text-[11px] text-white/55 truncate">
                  {user?.full_name || user?.email || "—"}
                </p>
              </div>
            </div>
            <button
              onClick={handleSignOut}
              title="Sign out"
              className="p-1.5 rounded-lg text-white/50 hover:text-white hover:bg-white/10 transition-colors shrink-0"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>

        <nav className="space-y-1 flex-1">
          {nav.map(({ href, label, icon: I }) => (
            <Link
              key={label}
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
              {label === "Security queue" && fraudCount > 0 && (
                <span className="relative ml-auto text-[11px] bg-flux rounded-full px-2 py-0.5">
                  {fraudCount}
                </span>
              )}
            </Link>
          ))}
        </nav>

        <div className="rounded-xl bg-white/5 p-3 text-xs text-white/60 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                isBackendLive ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
              }`}
            />
            <span>{isBackendLive ? "Live API Connected" : "Connecting API…"}</span>
          </div>
          <Link href="/login" className="text-flux-soft hover:underline font-medium">
            Account
          </Link>
        </div>
      </aside>

      <div className="flex-1 min-w-0">
        <header className="sticky top-0 z-30 bg-cream/85 backdrop-blur-xl border-b border-navy/[0.06] px-4 md:px-8 py-3 flex flex-wrap items-center gap-3 justify-between">
          <div className="flex items-center gap-2 lg:hidden">
            <LogoIcon className="w-7 h-7" />
            <span className="font-semibold text-navy">Conflux HQ</span>
          </div>

          <div className="flex items-center gap-2 text-xs text-navy/60">
            <span
              className={`w-2 h-2 rounded-full ${
                isBackendLive ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
              }`}
            />
            <span className="font-medium text-navy">
              {user?.bank?.name ? `${user.bank.name} Operations Console` : "Live Operations Console"}
            </span>
            {user?.role && (
              <span className="hidden sm:inline-block rounded-full bg-navy/5 px-2.5 py-0.5 text-[11px] font-mono text-navy/65">
                {user.role}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="hidden sm:inline-flex items-center gap-1.5 text-xs font-medium text-navy/75 bg-white hover:bg-navy/[0.03] rounded-full px-3.5 py-1.5 border border-navy/[0.08] transition-colors"
            >
              {user?.email || "Switch Account"}
            </Link>
            <button
              onClick={detectNow}
              disabled={syncing}
              className="inline-flex items-center gap-2 bg-navy text-white text-sm font-semibold px-4 py-2 rounded-full hover:bg-navy-600 disabled:opacity-80 transition-colors shadow-sm"
            >
              {syncing ? (
                <Loader2 className="w-4 h-4 animate-spin text-flux" />
              ) : (
                <RefreshCw className="w-4 h-4 text-flux" />
              )}
              {syncing ? "Scanning Spikes…" : "Scan & Sync Live"}
            </button>
          </div>
        </header>
        <div className="lg:hidden flex gap-1 overflow-x-auto px-4 py-2 bg-navy">
          {nav.map(({ href, label }) => (
            <Link
              key={label}
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
