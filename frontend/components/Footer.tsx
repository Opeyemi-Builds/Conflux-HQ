"use client";

import Link from "next/link";
import {
  Lock,
  UserCheck,
  ScrollText,
  ShieldAlert,
  ArrowUp,
  ShieldCheck,
} from "lucide-react";
import LogoIcon from "./LogoIcon";
import Reveal from "./Reveal";

const trust = [
  {
    icon: Lock,
    title: "Privacy",
    desc: "Names, phones and accounts are masked before analysis (NDPR compliance).",
  },
  {
    icon: UserCheck,
    title: "Access control",
    desc: "Role-based views for agents, IT and management.",
  },
  {
    icon: ScrollText,
    title: "Accountability",
    desc: "Human approval and a full audit log of every agent step.",
  },
  {
    icon: ShieldAlert,
    title: "Fraud routing",
    desc: "Scam complaints go to the security queue, not the normal one.",
  },
] as const;

const navColumns = [
  {
    title: "Dashboard",
    links: [
      { label: "Live Overview", href: "/dashboard" },
      { label: "Active Incidents (INC-0421)", href: "/dashboard/incidents/INC-0421" },
      { label: "All Complaints Feed", href: "/dashboard/complaints" },
      { label: "Fraud & Security Queue", href: "/dashboard/security" },
      { label: "Analytics & Trends", href: "/dashboard/analytics" },
      { label: "Audit Trail", href: "/dashboard/audit" },
    ],
  },
  {
    title: "Channels",
    links: [
      { label: "USSD & Mobile Apps", href: "#channels" },
      { label: "Pidgin NLP Intelligence", href: "#channels" },
      { label: "Social Feeds (X, IG, FB)", href: "#channels" },
      { label: "Branch & Call Transcripts", href: "#channels" },
    ],
  },
  {
    title: "Architecture",
    links: [
      { label: "NDPR Data Privacy", href: "#trust" },
      { label: "Human-in-the-Loop", href: "#trust" },
      { label: "Audit Logging", href: "#trust" },
      { label: "CBN 2025 Benchmarks", href: "#product" },
    ],
  },
];

export default function Footer() {
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <footer id="trust" className="bg-cream px-6 pt-16 pb-8 border-t border-navy/5">
      <div className="max-w-[88rem] mx-auto">
        {/* Safe by design cards */}
        <Reveal>
          <div className="flex flex-col md:flex-row md:items-end justify-between mb-10 gap-4">
            <div>
              <p className="text-xs uppercase tracking-wider font-semibold text-flux mb-2 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5" />
                Security & Governance
              </p>
              <h2
                className="text-navy text-4xl md:text-5xl font-semibold"
                style={{ letterSpacing: "-0.04em" }}
              >
                Safe by design.
              </h2>
            </div>
            <p className="text-navy/60 text-base max-w-md">
              Every automated recommendation requires verified human oversight
              before funds or customer communications are dispatched.
            </p>
          </div>
        </Reveal>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-20">
          {trust.map(({ icon: Icon, title, desc }, i) => (
            <Reveal key={title} delay={i * 0.07}>
              <div className="rounded-2xl bg-navy p-7 h-full flex flex-col justify-between group hover:bg-navy-600 transition-colors duration-300">
                <div>
                  <div className="w-11 h-11 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center mb-6">
                    <Icon className="w-5 h-5 text-flux" />
                  </div>
                  <h3 className="text-white text-xl font-medium mb-2.5">
                    {title}
                  </h3>
                </div>
                <p className="text-white/60 text-sm leading-relaxed">{desc}</p>
              </div>
            </Reveal>
          ))}
        </div>

        {/* Footer Navigation & Brand Details */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-10 pt-10 border-t border-navy/10 items-start">
          <div className="md:col-span-5 flex flex-col gap-4">
            <Link href="/" className="flex items-center gap-2.5 w-fit">
              <LogoIcon className="w-9 h-9" />
              <span className="text-2xl font-bold tracking-tight text-navy">
                Conflux <span className="text-flux">HQ</span>
              </span>
            </Link>
            <p className="text-navy/70 text-sm max-w-sm leading-relaxed">
              AI complaint intelligence platform for banks. Detecting payment
              settlement failures before they trend.
            </p>
            <div className="pt-2">
              <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-800 border border-emerald-500/20">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                Live synthetic simulation stream active
              </span>
            </div>
          </div>

          <div className="md:col-span-7 grid grid-cols-2 sm:grid-cols-3 gap-8">
            {navColumns.map((col) => (
              <div key={col.title}>
                <p className="text-xs font-bold uppercase tracking-wider text-navy/40 mb-3.5">
                  {col.title}
                </p>
                <ul className="space-y-2.5">
                  {col.links.map((link) => (
                    <li key={link.label}>
                      <Link
                        href={link.href}
                        className="text-sm text-navy/70 hover:text-flux transition-colors duration-150"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* Large Text Brand Display Banner */}
        <div className="mt-14 pt-8 border-t border-navy/10 overflow-hidden select-none">
          <div
            className="flex items-center justify-center font-black tracking-tighter leading-none text-center uppercase text-navy/[0.08] hover:text-navy/[0.12] transition-colors duration-300 pointer-events-none"
            style={{
              fontSize: "clamp(3.5rem, 14vw, 12rem)",
              letterSpacing: "-0.05em",
            }}
          >
            <span>CONFLUX</span>
            <span className="text-flux/20 ml-2 sm:ml-4">HQ</span>
          </div>
        </div>

        {/* Bottom Credits & Copyright */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-navy/10 pt-6 text-xs text-navy/55">
          <p>
            © 2026 Conflux HQ · Access Youth Tech Forge, Theme 1 (Payments &amp; Financial Infrastructure).
          </p>
          <div className="flex items-center gap-4">
            <span className="text-navy/45">
              All complaints, logs and transactions shown are synthetic.
            </span>
            <button
              onClick={scrollToTop}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-navy/5 hover:bg-navy/10 text-navy font-medium transition-colors"
              aria-label="Back to top"
            >
              <span>Top</span>
              <ArrowUp className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
}
