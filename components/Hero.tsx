"use client";
import Link from "next/link";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, TrendingUp } from "lucide-react";
import PillButton from "./PillButton";
const brands = [
  ["X", "700 16px Arial"], ["Instagram", "italic 600 15px Georgia"], ["Facebook", "700 15px Verdana"],
  ["Email", "400 16px Palatino, serif"], ["Call centre", "700 13px 'Courier New', monospace"], ["Branch", "600 15px Trebuchet MS"],
  ["In-app chat", "700 14px Arial"], ["USSD", "900 13px Arial Black"],
];
export default function Hero() {
  const track = [...brands, ...brands];
  return (
    <section className="flex-1 px-6 pt-20 pb-6 flex items-end">
      <div className="relative w-full max-w-[88rem] mx-auto rounded-2xl overflow-hidden bg-[#E6E8E0]" style={{ height: "calc(100vh - 96px)" }}>
        {/* animated aurora background */}
        <motion.div className="absolute -right-32 -top-24 w-[640px] h-[640px] rounded-full bg-flux/40 blur-3xl" animate={{ x: [0, -50, 0], y: [0, 40, 0] }} transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }} />
        <motion.div className="absolute right-1/4 -bottom-40 w-[560px] h-[560px] rounded-full bg-navy/25 blur-3xl" animate={{ x: [0, 60, 0], y: [0, -30, 0] }} transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }} />
        <motion.div className="absolute left-1/3 top-10 w-[360px] h-[360px] rounded-full bg-flux-soft/40 blur-3xl" animate={{ scale: [1, 1.2, 1] }} transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }} />

        <div className="relative z-10 flex flex-col items-start justify-start h-full p-8 md:p-12 pt-28 md:pt-36">
          <motion.h1 initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            className="text-navy text-5xl md:text-7xl font-semibold leading-[1.02] max-w-2xl mb-5" style={{ letterSpacing: "-0.04em" }}>
            Payment failures<br />show up as <span className="text-flux">complaints</span> first.
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.15 }}
            className="text-navy/70 text-base md:text-lg max-w-md mb-8 leading-relaxed">
            Conflux HQ unifies every customer complaint, spots the spike, finds the likely cause and drafts the response. A human approves anything that touches money.
          </motion.p>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.3 }}>
            <PillButton href="/dashboard">Watch the demo</PillButton>
          </motion.div>

          <div className="marquee-wrap mt-16 md:mt-24 w-full max-w-md overflow-hidden" style={{ maskImage: "linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent)" }}>
            <div className="marquee-track">
              {track.map(([n, f], i) => (<span key={i} className="mx-7 shrink-0 text-navy/60 whitespace-nowrap" style={{ font: f }}>{n}</span>))}
            </div>
          </div>
        </div>

        {/* floating live alert card */}
        <motion.div initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.9, delay: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="hidden lg:block absolute right-12 bottom-12 w-[380px] rounded-2xl bg-white/80 backdrop-blur-xl border border-white p-5 shadow-[0_20px_60px_-20px_rgba(20,35,63,.35)] group">
          <Link href="/dashboard/incidents/INC-0421" className="block">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-flux text-sm font-semibold">
                <span className="relative flex h-2.5 w-2.5"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-flux opacity-60" /><span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-flux" /></span>
                LIVE ALERT · 10:14
              </div>
              <span className="text-xs text-navy/40 group-hover:text-flux flex items-center gap-1 transition-colors font-medium">Investigate <ArrowRight className="w-3 h-3" /></span>
            </div>
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-flux/15 flex items-center justify-center shrink-0"><AlertTriangle className="w-5 h-5 text-flux" /></div>
              <div><p className="font-semibold text-navy leading-snug group-hover:text-flux transition-colors">Failed transfers spiking on USSD + app</p><p className="text-sm text-navy/60">Likely cause: release v4.2.1 · confidence 87%</p></div>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              {[["212", "complaints"], ["+640%", "vs baseline"], ["12 min", "to detect"]].map(([v, l]) => (
                <div key={l} className="rounded-xl bg-navy/5 py-2.5"><p className="font-semibold text-navy">{v}</p><p className="text-[11px] text-navy/55">{l}</p></div>))}
            </div>
            <div className="mt-3 flex items-center gap-1.5 text-xs text-navy/50"><TrendingUp className="w-3.5 h-3.5" /> Synthetic demo data · Click to inspect trace</div>
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
