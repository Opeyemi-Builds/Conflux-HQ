"use client";
import { AnimatePresence, motion } from "framer-motion";
import { Bot, Cpu, Radio, User } from "lucide-react";
import { useDash } from "@/components/dashboard/Provider";
import { Card, PageHeader, Tag } from "@/components/dashboard/ui";

const icon = { Human: User, Agent: Bot, Detector: Cpu, System: Cpu } as const;

export default function Audit() {
  const { audit, isBackendLive } = useDash();
  return (
    <>
      <PageHeader
        title="Audit log"
        sub="Every AI agent tool step, classification, spike alert, and human approval stored in the database."
        right={
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold">
              <Radio className="w-3.5 h-3.5 animate-pulse text-emerald-600" />
              {isBackendLive ? "Live Audit Ledger" : "Connecting…"}
            </span>
            <Tag>{audit.length} entries</Tag>
          </div>
        }
      />
      <Card className="p-2">
        <AnimatePresence initial={false}>
          {audit.map((a, i) => {
            const I = icon[a.actor as keyof typeof icon] ?? Cpu;
            return (
              <motion.div
                key={a.id || `${i}-${a.time}-${a.action}`}
                layout
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex gap-4 px-4 py-4 ${i ? "border-t border-navy/5" : ""}`}
              >
                <span className="font-mono text-sm text-navy/45 w-14 shrink-0 pt-0.5">{a.time}</span>
                <div
                  className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                    a.actor === "Human" ? "bg-flux/15 text-flux" : "bg-navy/5 text-navy/70"
                  }`}
                >
                  <I className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm">
                    <span className="font-semibold text-navy">{a.actor}</span>{" "}
                    <span className="text-navy/50">·</span>{" "}
                    <span className="font-mono text-navy/80">{a.action}</span>
                  </p>
                  <p className="text-sm text-navy/60 mt-0.5 break-words">{a.detail}</p>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
        {audit.length === 0 && <p className="text-center text-navy/50 py-12">No audit entries recorded yet.</p>}
      </Card>
    </>
  );
}
