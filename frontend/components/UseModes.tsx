"use client";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, CheckCircle2, Search, Database, Clock, FileText } from "lucide-react";
import Reveal from "./Reveal";
const steps = [
  [Search, "get_incident_stats", "212 failed-transfer complaints, USSD + app"],
  [Database, "search_transactions", "184 matched: debited, not credited"],
  [Clock, "get_system_events", "Release v4.2.1 deployed at 10:00"],
  [FileText, "draft_message", "Holding message + IT ticket ready"],
] as const;
const how = [["1", "Detect", "Complaints are classified by issue, severity, sentiment and language. A category rising faster than normal triggers an alert."], ["2", "Investigate", "An agent matches complaints to transactions, then checks release and outage logs."], ["3", "Decide", "It states the likely cause with a confidence level and ranks by money at risk."], ["4", "Act", "It drafts the message and IT ticket. A person approves, and every step is logged."]];
export default function UseModes() {
  return (
    <>
      <section id="how" className="bg-cream px-6 py-24">
        <div className="max-w-[88rem] mx-auto">
          <Reveal><h2 className="text-navy text-4xl md:text-6xl font-semibold mb-12" style={{ letterSpacing: "-0.04em" }}>Detect, investigate,<br />decide, act.</h2></Reveal>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {how.map(([n, t, b], i) => (
              <Reveal key={n} delay={i * 0.08}>
                <div className="rounded-2xl bg-white p-7 h-full border border-navy/5 hover:-translate-y-1 hover:shadow-xl transition-all duration-300">
                  <span className="w-9 h-9 rounded-full bg-flux text-white font-semibold flex items-center justify-center mb-6">{n}</span>
                  <h3 className="text-2xl font-medium text-navy mb-2" style={{ letterSpacing: "-0.02em" }}>{t}</h3>
                  <p className="text-navy/65 text-base leading-relaxed">{b}</p>
                </div>
              </Reveal>))}
          </div>
        </div>
      </section>

      <section id="views" className="bg-cream px-6 py-24">
        <div className="max-w-[88rem] mx-auto grid grid-cols-1 md:grid-cols-2 gap-8 items-start">
          <Reveal className="md:pr-12 md:pt-2">
            <p className="text-navy/60 text-sm mb-2">Conflux HQ in practice</p>
            <h2 className="text-5xl md:text-6xl font-semibold leading-none mb-6 text-navy" style={{ letterSpacing: "-0.04em" }}>Built for every role</h2>
            <p className="text-navy/60 text-base leading-relaxed max-w-sm">Agents, IT and management each get the view they need, from a customer-ready reply to the root cause and the cost exposure.</p>
          </Reveal>
          <Reveal>
            <div className="relative rounded-3xl overflow-hidden min-h-[720px] bg-navy">
              <motion.div className="absolute -top-24 -right-24 w-96 h-96 rounded-full bg-flux/40 blur-3xl" animate={{ scale: [1, 1.25, 1] }} transition={{ duration: 9, repeat: Infinity }} />
              <div className="relative z-10 p-10 md:p-12">
                <h3 className="text-white text-4xl md:text-5xl font-medium leading-tight mb-5" style={{ letterSpacing: "-0.03em" }}>Incident trace</h3>
                <p className="text-white/70 text-base max-w-md mb-8">Every agent step is shown and logged. Low confidence is shown as low confidence, never hidden.</p>
                <div className="space-y-3 mb-8">
                  {steps.map(([Icon, name, out], i) => (
                    <motion.div key={name} initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: 0.25 * i, duration: 0.5 }}
                      className="flex items-center gap-4 rounded-2xl bg-white/10 backdrop-blur border border-white/10 p-4">
                      <div className="w-10 h-10 rounded-xl bg-flux/20 flex items-center justify-center shrink-0"><Icon className="w-5 h-5 text-flux-soft" /></div>
                      <div className="flex-1 min-w-0"><p className="text-white font-mono text-sm">{name}()</p><p className="text-white/60 text-sm truncate">{out}</p></div>
                      <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                    </motion.div>))}
                </div>
                <div className="rounded-2xl bg-white p-5 mb-8">
                  <p className="text-xs font-semibold text-flux mb-1">DRAFT HOLDING MESSAGE · AWAITING APPROVAL</p>
                  <p className="text-navy/80 text-sm leading-relaxed">We are aware some transfers made on USSD and the app did not complete. Your money is safe and any debit will be reversed. We will update you shortly.</p>
                  <div className="flex gap-2 mt-4"><span className="px-4 py-2 rounded-full bg-navy text-white text-sm font-medium">Approve</span><span className="px-4 py-2 rounded-full bg-navy/10 text-navy text-sm font-medium">Reject</span></div>
                </div>
                <div className="flex flex-wrap items-center gap-6">
                  <a href="#trust" className="group inline-flex items-center gap-3 text-white font-medium"><span className="w-9 h-9 rounded-full bg-white/80 group-hover:bg-white transition-colors flex items-center justify-center"><ArrowRight className="w-4 h-4 text-navy" /></span>Know more</a>
                  <Link href="/dashboard/incidents/latest" className="text-sm font-medium text-flux-soft hover:text-white transition-colors underline underline-offset-4">Open Incident in Dashboard →</Link>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>
    </>
  );
}
