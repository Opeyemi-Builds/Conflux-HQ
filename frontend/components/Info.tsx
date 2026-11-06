import { Radar, ShieldCheck } from "lucide-react";
import Reveal from "./Reveal";
import PillButton from "./PillButton";
export default function Info() {
  return (
    <section id="product" className="bg-cream px-6 py-24">
      <div className="max-w-[88rem] mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 mb-16 items-start">
          <Reveal>
            <h2 className="text-navy text-4xl md:text-6xl font-semibold leading-tight mb-8" style={{ letterSpacing: "-0.03em" }}>Meet Conflux HQ.</h2>
            <PillButton href="#how" size="md">How it works</PillButton>
          </Reveal>
          <Reveal delay={0.1}>
            <p className="text-navy/70 text-2xl md:text-3xl leading-relaxed">Conflux HQ is the early-warning layer between customer, bank, switch and merchant, turning scattered complaints into one clear, explained incident.</p>
          </Reveal>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Reveal className="sm:col-span-2">
            <div className="rounded-2xl p-7 min-h-80 h-full flex flex-col justify-between bg-gradient-to-br from-flux-soft via-flux to-[#c24f0c]">
              <h3 className="text-white text-2xl font-medium leading-snug" style={{ letterSpacing: "-0.02em" }}>The gap is measurable</h3>
              <div>
                <div className="flex gap-10 mb-4 text-white">
                  <div><p className="text-5xl font-semibold" style={{ letterSpacing: "-0.04em" }}>23,129</p><p className="text-white/80 text-sm mt-1">CBN complaints, 2025 (+10.53%)</p></div>
                  <div><p className="text-5xl font-semibold" style={{ letterSpacing: "-0.04em" }}>₦19.12bn</p><p className="text-white/80 text-sm mt-1">refunds ordered, plus $329.3m</p></div>
                </div>
                <p className="text-white/80 text-base max-w-sm">Failed transactions, unauthorised deductions and delayed refunds, each one first seen as a single ticket.</p>
              </div>
            </div>
          </Reveal>
          {[[Radar, "Caught early,\nexplained fast.", "Spikes are flagged by volume and growth, then linked to a release, outage or switch fault."], [ShieldCheck, "Humans approve\nevery money action.", "The agent proposes. A person approves. It can never execute a reversal on its own."]].map(([Icon, t, b], i) => {
            const I = Icon as typeof Radar;
            return (
              <Reveal key={i} delay={0.1 * (i + 1)}>
                <div className="rounded-2xl bg-navy p-7 min-h-80 h-full flex flex-col justify-between">
                  <div><I className="w-7 h-7 text-flux mb-5" /><h3 className="text-white text-2xl font-medium leading-snug whitespace-pre-line" style={{ letterSpacing: "-0.02em" }}>{t as string}</h3></div>
                  <p className="text-white/60 text-base">{b as string}</p>
                </div>
              </Reveal>);
          })}
        </div>
        <p className="mt-6 text-xs text-navy/45">Sources: CBN 2025 data as reported by Leadership and Prime Business Africa; to be confirmed against CBN publications.</p>
      </div>
    </section>
  );
}
