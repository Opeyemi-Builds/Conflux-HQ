import type { AuditEntry, Complaint, Incident, IssueType, Severity, Txn } from "./types";

export const ISSUE_LABEL: Record<IssueType, string> = {
  failed_transfer: "Failed transfer", double_debit: "Double debit", card_atm: "Card / ATM", pos: "POS", fees: "Fees",
  loan: "Loan", app_login: "App / login", fraud_scam: "Fraud / scam", other: "Other",
};
export const SEV_ORDER: Severity[] = ["low", "medium", "high", "critical"];

/** 5-minute buckets, 09:30 → 11:00. Release v4.2.1 at 10:00, first rise 10:12. */
export const LABELS = ["09:30","09:35","09:40","09:45","09:50","09:55","10:00","10:05","10:10","10:15","10:20","10:25","10:30","10:35","10:40","10:45","10:50","10:55","11:00"];
export const RELEASE_IDX = 6;
const ft = [3,4,3,5,4,3,4,4,6,22,38,52,60,57,49,43,38,33,30];
const scam = [0,1,0,1,0,2,1,3,4,6,9,12,15,17,19,22,24,27,31];
const iso = [1,0,1,0,2,0,1,0,1,3,2,1,0,1,0,1,0,0,1];

export const incidents: Incident[] = [
  {
    id: "INC-0421", title: "Failed transfers spiking on USSD and app", issue: "failed_transfer", status: "active", priority: 94,
    startedAt: "10:12", detectedAt: "10:15", volume: 422, growth: "15× baseline", channels: ["USSD", "App"], region: "Lagos, Abuja, Ibadan",
    moneyAtRisk: "₦48.2m", series: ft, releaseMarker: true,
    causes: [
      { name: "App release v4.2.1 (10:00)", confidence: 87, evidence: "Failure rate on the app and USSD path rose from 1.1% to 38% within 12 minutes of deploy." },
      { name: "Switch B degradation", confidence: 41, evidence: "94% of failed debits routed through Switch B, but no outage event was logged." },
      { name: "Scheduled maintenance (09:30)", confidence: 6, evidence: "Unrelated decoy event. Affected a different service and finished before the spike." },
    ],
    trace: [
      { phase: 2, tool: "get_incident_stats", args: "INC-0421", result: "422 complaints, 15× baseline, concentrated on USSD (61%) and app (33%)." },
      { phase: 2, tool: "compare_baseline", args: "failed_transfer, 24h", result: "Baseline median 4 per 5 min. Current 60. Exceeds baseline + 3 MAD." },
      { phase: 3, tool: "search_transactions", args: "channel in (USSD, app), 10:00–10:45", result: "184 of 190 sampled complaints matched: debited, not credited, reversal pending." },
      { phase: 3, tool: "get_system_events", args: "09:45–10:15", result: "Release v4.2.1 at 10:00. Maintenance at 09:30 (unrelated)." },
      { phase: 4, tool: "draft_message", args: "customer, IT", result: "Holding message and IT ticket drafted from verified facts only. Awaiting approval." },
    ],
    summary: {
      agent: "Customers on USSD and the app are being debited without the recipient being credited. Tell them the money is safe, a reversal is in progress and we will update shortly. Do not promise a time.",
      it: "Release v4.2.1 (10:00) is the most likely cause, at 87% confidence. Failures concentrate on the USSD and app transfer path through Switch B. Check the transfer-confirmation callback changed in this release. Rollback is an option.",
      management: "422 complaints in 50 minutes, roughly ₦48.2m at risk and 15× the normal rate. Detected 3 minutes after the first rise. Customer messaging is ready for approval. Reversals need sign-off.",
    },
    customerDraft: "We are aware that some transfers made through USSD and the app did not complete and your account may have been debited. Your money is safe. Any amount debited without being received will be reversed. We will update you as soon as we can.",
    itTicket: "[P1] Failed transfers after release v4.2.1\nStart: 10:12 · Detected: 10:15\nPath: USSD + app → Switch B\nSymptom: debit succeeds, credit not confirmed, reversal pending (184 matched)\nSuspect: release v4.2.1 deployed 10:00 (confidence 87%)\nAsk: review transfer-confirmation changes, consider rollback, confirm Switch B health.",
    examples: ["my money don enter nowhere since morning", "Debited ₦25,000 via USSD, receiver has not got am. Abeg help", "Transfer failed on app but I was charged. Ref ending 4471"],
  },
  {
    id: "INC-0422", title: "Fake-agent scam cluster in Kano", issue: "fraud_scam", status: "security", priority: 71,
    startedAt: "10:05", detectedAt: "10:30", volume: 34, growth: "12× baseline", channels: ["Facebook", "Call"], region: "Kano",
    moneyAtRisk: "₦6.9m", series: scam,
    causes: [{ name: "Impersonation of bank agents", confidence: 78, evidence: "Complaints describe the same pattern: a caller posing as an agent requests a PIN and an OTP." }, { name: "Compromised agent device", confidence: 22, evidence: "Weak signal. Several victims named different agents." }],
    trace: [
      { phase: 2, tool: "get_incident_stats", args: "INC-0422", result: "34 complaints in 40 minutes, 82% from Kano." },
      { phase: 3, tool: "compare_baseline", args: "fraud_scam, 24h", result: "Baseline 0–1 per 5 min. Current 5. Exceeds threshold." },
      { phase: 4, tool: "draft_message", args: "security", result: "Routed to the security queue. Advisory drafted." },
    ],
    summary: {
      agent: "These callers are scammers pretending to be bank agents. Do not discuss account details. Escalate to security and remind customers the bank never asks for a PIN or OTP.",
      it: "No platform fault detected. Pattern points to social engineering outside our systems. Security should review affected accounts.",
      management: "34 reports, about ₦6.9m exposed, concentrated in Kano. Routed to security. A customer advisory is ready to approve.",
    },
    customerDraft: "Our staff will never ask for your PIN, OTP or password. If someone asked for these, do not share them and contact us on our official line.",
    itTicket: "[Security] Impersonation cluster, Kano\n34 complaints since 10:05. Pattern: fake agent requests PIN/OTP.\nAsk: freeze review on affected accounts, assess advisory.",
    examples: ["Man call me say na bank agent, he collect my OTP", "Agent for Kano ask for my PIN, now money don commot"],
  },
  {
    id: "INC-0423", title: "Isolated ATM debit complaints, Ikeja", issue: "card_atm", status: "monitoring", priority: 18,
    startedAt: "10:15", detectedAt: "—", volume: 6, growth: "Below threshold", channels: ["Branch"], region: "Ikeja",
    moneyAtRisk: "₦0.3m", series: iso,
    causes: [{ name: "Single ATM cash-out fault", confidence: 64, evidence: "All 6 complaints reference the same ATM. No pattern elsewhere." }],
    trace: [{ phase: 2, tool: "compare_baseline", args: "card_atm, 24h", result: "6 complaints, below the minimum volume of 10. No spike raised." }],
    summary: { agent: "Isolated. Handle each complaint as a normal reversal case.", it: "One ATM only. Raise a field-service ticket for that machine.", management: "Below threshold, no systemic risk. Correctly not escalated." },
    customerDraft: "We are sorry about the failed ATM withdrawal. Your debit will be reviewed and reversed where confirmed.",
    itTicket: "[P4] ATM cash-out fault, Ikeja. 6 complaints, one terminal. Field service check.",
    examples: ["ATM no pay cash but debit alert don come"],
  },
];

export const transactions: Txn[] = [
  { ref: "TX-88421", time: "10:14", type: "Transfer", channel: "USSD", amount: "₦25,000", status: "Debited, not credited", reversal: "Pending", switch: "Switch B" },
  { ref: "TX-88437", time: "10:16", type: "Transfer", channel: "App", amount: "₦120,000", status: "Debited, not credited", reversal: "Pending", switch: "Switch B" },
  { ref: "TX-88452", time: "10:19", type: "Transfer", channel: "USSD", amount: "₦8,500", status: "Debited, not credited", reversal: "Pending", switch: "Switch B" },
  { ref: "TX-88470", time: "10:22", type: "Transfer", channel: "App", amount: "₦60,000", status: "Debited, not credited", reversal: "Not started", switch: "Switch B" },
  { ref: "TX-88491", time: "10:27", type: "Transfer", channel: "USSD", amount: "₦15,000", status: "Debited, not credited", reversal: "Pending", switch: "Switch B" },
  { ref: "TX-88503", time: "10:31", type: "Transfer", channel: "App", amount: "₦200,000", status: "Debited, not credited", reversal: "Not started", switch: "Switch A" },
];

const base: [string, IssueType, Severity, string, string, string, import("./types").Channel][] = [
  ["my money don enter nowhere since morning", "failed_transfer", "critical", "Pidgin", "Lagos", "angry", "X"],
  ["Debited ₦25,000 via USSD, receiver never got am. Abeg help", "failed_transfer", "high", "Pidgin", "Ibadan", "angry", "Facebook"],
  ["Transfer failed on the app but I was charged", "failed_transfer", "high", "English", "Abuja", "negative", "In-app"],
  ["Mo ti fi owo ranṣẹ, o kuna sugbon wọn ti debit mi", "failed_transfer", "high", "Yoruba", "Ibadan", "negative", "Call"],
  ["Same charge appear twice for one POS payment", "double_debit", "medium", "English", "Lagos", "negative", "Email"],
  ["ATM no pay cash but debit alert don come", "card_atm", "medium", "Pidgin", "Ikeja", "negative", "Branch"],
  ["Man call me say na bank agent, he collect my OTP", "fraud_scam", "critical", "Pidgin", "Kano", "angry", "Call"],
  ["Wani ya kira ni yana cewa shi ma'aikacin banki ne, ya nemi PIN dina", "fraud_scam", "critical", "Hausa", "Kano", "angry", "Facebook"],
  ["I cannot log in to the app after the update", "app_login", "medium", "English", "Abuja", "negative", "In-app"],
  ["Why was I charged ₦50 on a failed transfer?", "fees", "low", "English", "Lagos", "negative", "Instagram"],
  ["Loan repayment shows twice on my statement", "loan", "medium", "English", "Port Harcourt", "negative", "Email"],
  ["Ego m abanyeghi onye m zitere ya, ma e wepụrụ ya", "failed_transfer", "high", "Igbo", "Enugu", "negative", "X"],
  ["Please update me on my complaint, no feedback in 3 days", "other", "low", "English", "Lagos", "neutral", "Email"],
  ["POS declined but my account was debited at the shop", "pos", "medium", "English", "Abuja", "negative", "Branch"],
];
const times = ["10:12","10:14","10:15","10:17","10:19","10:21","10:23","10:26","10:28","10:30","10:33","10:36","10:40","10:44"];
export const seedComplaints: Complaint[] = Array.from({ length: 42 }, (_, i) => {
  const b = base[i % base.length];
  const h = String(10 + Math.floor((i * 3 + 12) / 60)).padStart(2, "0");
  const m = String((i * 3 + 12) % 60).padStart(2, "0");
  return { id: `C-${1001 + i}`, time: i < 14 ? times[i] : `${h}:${m}`, text: b[0], issue: b[1], severity: b[2], language: b[3], region: b[4], sentiment: b[5] as Complaint["sentiment"], channel: b[6], ref: `****${4400 + i * 7}` };
}).sort((a, z) => (a.time < z.time ? 1 : -1));

export const hourly = [
  { h: "06:00", failed_transfer: 12, double_debit: 4, card_atm: 6, fraud_scam: 1, other: 18 },
  { h: "07:00", failed_transfer: 15, double_debit: 5, card_atm: 7, fraud_scam: 1, other: 22 },
  { h: "08:00", failed_transfer: 18, double_debit: 6, card_atm: 8, fraud_scam: 2, other: 26 },
  { h: "09:00", failed_transfer: 17, double_debit: 5, card_atm: 9, fraud_scam: 2, other: 25 },
  { h: "10:00", failed_transfer: 212, double_debit: 7, card_atm: 12, fraud_scam: 18, other: 27 },
  { h: "11:00", failed_transfer: 168, double_debit: 6, card_atm: 9, fraud_scam: 16, other: 21 },
];
export const channelSplit = [{ name: "USSD", value: 258 }, { name: "App", value: 139 }, { name: "Call", value: 74 }, { name: "Facebook", value: 52 }, { name: "X", value: 44 }, { name: "Email", value: 31 }, { name: "Branch", value: 22 }];
export const regionSplit = [{ name: "Lagos", value: 188 }, { name: "Abuja", value: 96 }, { name: "Ibadan", value: 74 }, { name: "Kano", value: 41 }, { name: "Port Harcourt", value: 29 }, { name: "Enugu", value: 18 }];
export const rootCauses = [{ name: "App release", value: 422 }, { name: "Social engineering", value: 34 }, { name: "ATM terminal", value: 6 }, { name: "Switch latency", value: 21 }];
export const detectTrend = [{ d: "Mon", min: 41 }, { d: "Tue", min: 33 }, { d: "Wed", min: 22 }, { d: "Thu", min: 12 }, { d: "Fri", min: 3 }];

export const auditSeed: AuditEntry[] = [
  { phase: 1, time: "10:00", actor: "System", action: "Release detected", detail: "v4.2.1 deployed to production." },
  { phase: 2, time: "10:15", actor: "Detector", action: "Spike flagged", detail: "failed_transfer exceeded baseline + 3 MAD with 22 complaints. INC-0421 created." },
  { phase: 2, time: "10:15", actor: "Agent", action: "get_incident_stats", detail: "422 complaints, USSD 61%, app 33%." },
  { phase: 2, time: "10:15", actor: "Agent", action: "compare_baseline", detail: "Baseline 4 per 5 min. Current 60." },
  { phase: 3, time: "10:16", actor: "Agent", action: "search_transactions", detail: "184 matched: debited, not credited." },
  { phase: 3, time: "10:16", actor: "Agent", action: "get_system_events", detail: "Release v4.2.1 at 10:00 ranked top cause (87%)." },
  { phase: 3, time: "10:30", actor: "Detector", action: "Spike flagged", detail: "fraud_scam cluster in Kano. INC-0422 routed to security queue." },
  { phase: 4, time: "10:17", actor: "Agent", action: "draft_message", detail: "Customer holding message and IT ticket drafted. Waiting for human approval." },
  { phase: 4, time: "10:17", actor: "Detector", action: "No spike raised", detail: "card_atm below minimum volume (6 of 10). INC-0423 left on monitoring." },
];
