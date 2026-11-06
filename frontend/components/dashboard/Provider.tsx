"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { AuditEntry, Complaint, Decision, Role } from "@/lib/types";
import { auditSeed, seedComplaints } from "@/lib/mock";

interface Ctx {
  role: Role; setRole: (r: Role) => void; phase: number; replaying: boolean; replay: () => void;
  decisions: Record<string, Decision>; decide: (id: string, d: Exclude<Decision, "pending">) => void;
  audit: AuditEntry[]; complaints: Complaint[]; addComplaint: (c: Complaint) => void;
}
const C = createContext<Ctx | null>(null);
export const useDash = () => { const v = useContext(C); if (!v) throw new Error("useDash outside provider"); return v; };
const now = () => new Date().toTimeString().slice(0, 5);

export default function DashboardProvider({ children }: { children: React.ReactNode }) {
  const [role, setRole] = useState<Role>("agent");
  const [phase, setPhase] = useState(4);
  const [replaying, setReplaying] = useState(false);
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [human, setHuman] = useState<AuditEntry[]>([]);
  const [fresh, setFresh] = useState<Complaint[]>([]);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const replay = useCallback(() => {
    if (timer.current) clearInterval(timer.current);
    setDecisions({}); setHuman([]); setPhase(0); setReplaying(true);
    let p = 0;
    timer.current = setInterval(() => {
      p += 1; setPhase(p);
      if (p >= 4 && timer.current) { clearInterval(timer.current); setReplaying(false); }
    }, 2600);
  }, []);
  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  const decide = useCallback((id: string, d: Exclude<Decision, "pending">) => {
    setDecisions((s) => ({ ...s, [id]: d }));
    setHuman((h) => [...h, { phase: 4, time: now(), actor: "Human", action: d === "approved" ? "Approved" : "Rejected", detail: `${id}: customer message and reversal request ${d}.` }]);
  }, []);
  const addComplaint = useCallback((c: Complaint) => setFresh((f) => [c, ...f]), []);

  const audit = useMemo(() => [...auditSeed.filter((a) => a.phase <= phase), ...human].reverse(), [phase, human]);
  const complaints = useMemo(() => [...fresh, ...seedComplaints], [fresh]);
  return <C.Provider value={{ role, setRole, phase, replaying, replay, decisions, decide, audit, complaints, addComplaint }}>{children}</C.Provider>;
}
