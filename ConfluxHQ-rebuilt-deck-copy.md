# ConfluxHQ — Rebuilt Pitch Deck (Track 1: Payments & Financial Infrastructure)

> This is the full rebuild copy. Paste-ready for PowerPoint/Google Slides, and ready for pptx generation when workspace is back.
> Theme: backend-green vs user-red. Positioning: NOT a dashboard. An early-warning infrastructure layer with an API handoff.

## How to use this
- 12 slides, ~1.5 min each = ~18 min + questions. For 5-min hackathon: do Slides 1,2,4,5,7,12 only.
- Visual system: light slides (#FFFFFF) + one midnight navy (#1E2761) opener + one midnight closer. Accent coral #F96167 for money-at-risk, teal #028090 for live/API. No accent bars under titles.
- Every slide has: Title, Body copy, Visual direction, Speaker note.

---

### SLIDE 1 — Title
**Title:** Payment failures show up as complaints first. Conflux HQ catches them before they trend.
**Sub:** An AI complaint intelligence layer for banks — Team Zymic | Access Youth Tech Forge · Theme 1
**Visual:** Midnight navy full-bleed. Left: headline in white 40pt. Right: single phone mock with Amaka's tweet. Small pill: "LIVE: failed_transfer spike · Switch A · 88% fail rate".
**Say:** "Money movement in Africa has come a long way. But when it fails, the bank finds out last — from Twitter. We're building the layer that hears it first."

### SLIDE 2 — The gap: Dashboard green, customers red
**Title:** The dashboard is green. The customers are not.
**Body:**
- 2:07 PM Friday. Amaka sends ₦50,000. App says "Successful." Debited. Receiver silent.
- Bank side: servers up, health checks 200 OK, nothing red.
- Amaka on X: "Una don debit me twice, my money never enter. Na so una dey do?"
**Visual:** Split: left bank ops (green checks, 200 OK), right user phone (debit alert + failed receipt + X post). Big Vs in middle.
**Say:** "This is the gap Track 1 is about. Not UI. Settlement didn't complete and access failed — but ops can't see it. To answer your question directly: yes — transfer failure IS settlement infrastructure. Login failure IS access infrastructure when it gates money movement."

### SLIDE 3 — Why banks miss it
**Title:** Three teams. Three tools. One missed outage.
**Body:**
- Social team sees tweets. Call centre sees angry calls. Email team sees tickets.
- By the time dots connect: trending, CBN refund clock ticking, WhatsApp group told "I'm moving banks."
- MTN example: backend says airtime sale OK, user side keeps failing. Backend-green ≠ user-success.
**Visual:** Three siloed icons → disconnected lines → one merged spike line rising. Caption: "Operational resilience gap".
**Say:** "Complaints are resolved in minutes when systems work. When systems fail, there's no signal to the owner. That's infrastructure."

### SLIDE 4 — Cost of finding out late
**Title:** The cost of finding out late
**Stats (keep your sources, flag as reported):**
- 23,129 complaints to CBN, 2025 — up 10.53% from 20,925
- ₦19.12bn + $329.3M refunds ordered — naira roughly doubled from ₦9.66bn
- ₦430M in 21 penalties for slow handling
- Thesis: Fraud losses falling (₦52.26bn 2024, down 51% per NIBSS) — complaints rising. Pain moved from theft to failed / disputed / delayed.
**Visual:** Two small bar pairs (fraud down, complaints+refunds up). Footnote: "CBN 2025 annual report as reported by Nairametrics/Legit/Prime Business Africa — verify before final."
**Say:** "Fraud is falling. Complaints are not. The system leaks money after the theft is stopped."

### SLIDE 5 — Solution: complaints into telemetry
**Title:** Conflux HQ turns complaints into telemetry
**4 steps (no dashboard pitch):**
1. **Detect** — One feed from X/IG/FB + calls + branch. Reads English, Pidgin, Yoruba, Hausa, Igbo.
2. **Investigate** — Statistics flag the spike (median + MAD over 15-min windows), not an LLM. Agent checks switch logs + releases.
3. **Decide** — Plain-language root cause, ranked by volume, growth, money at risk. Rules engine keeps running if cloud model down.
4. **Act** — Drafts customer message + IT ticket. Human approves anything touching money.
**Visual:** Horizontal 1-2-3-4 flow with icons. Under: "Detection = math. Action = human."
**Say:** "Social listening is just the sensor. Value is detection + cause + handoff."

### SLIDE 6 — Same Friday, bank spoke first
**Title:** Same Friday. This time, the bank spoke first.
**Body:**
- Caught early: spike flagged before trend
- Told first: holding message out at once
- Safe by design: person approves money moves
- Demo proof: Release v4.2.1 → 88% failure on Switch A, ₦1.8M at risk — flagged in minutes
**Visual:** Before/after timeline: 10:00 release → 10:12 spike → 10:14 incident + draft → 10:16 human approve → customer SMS.
**Say:** "We don't replace the dashboard. We give the department the signal before escalation."

### SLIDE 7 — NOT another dashboard (your core differentiator — don't bury this)
**Title:** We don't give banks another dashboard. We give them a feed.
**Body:**
- `GET /machine/updates?since=<cursor>` — 5-sec poll, `cfx_api_` keys, collections: complaints / incidents / drafts / actions / investigations / audit
- Webhooks: `x-forge-signature` HMAC-SHA256, ±5min, 1MB cap
- Plugs into existing bank dashboard + Try-It explorer
- Grouped + categorized complaints → patterns compounding over time
**Visual:** Code snippet card left, bank dashboard mock receiving it right. Arrow labeled "handoff, not login".
**Say:** "Banks already have dashboards. Conflux is the friendly API that lands inside theirs. That's why we're infrastructure, not tooling."

### SLIDE 8 — Product proof (live)
**Title:** One feed. Any language. Humans approve.
**Body:**
- Live overview: failed-transfer spike vs baseline
- Explorer: Pidgin + Yoruba classified by issue / severity / region
- Incident view: money at risk + priority score + approval gate — automated movement blocked (403)
- Audit log: every classification, spike, approval stored
**Visual:** 3 screenshots you already have — feed, incident, audit. Keep captions short.
**Say:** "Working prototype end-to-end on synthetic data — 1,000 complaints, 5,000 txns, planted release. All simulated."

### SLIDE 9 — Why existing tools miss it
**Title:** Why existing tools miss it
**Table:**
- APM (Datadog/Grafana): sees uptime — misses whether money arrived
- Social listening (Brandwatch/Sprinklr): sees sentiment — misses release/switch cause
- Ticketing/CRM: sees one case — misses pattern across cases
- Fraud systems: sees theft — misses failed-transaction waves
- Manual: sees what staff read — misses Pidgin/Yoruba/Hausa/Igbo at scale
- **Conflux: complaints as live telemetry + cause + human-approved fix**
**Say:** "Each tool sees one slice. None answers: did settlement complete for users on this switch right now?"

### SLIDE 10 — Market
**Title:** Every transfer is a chance to fail
**Body:**
- ~11bn instant NIP transfers, 2024 — each one can fail
- ₦1.07 quadrillion moved over NIP, 2024 (NIBSS)
- Now: Nigerian banks. Next: fintechs (OPay/Moniepoint/PalmPay), telcos, mobile money. Then: more African markets + languages.
- Adjacent: social listening $9.15bn 2024, 14.3% CAGR — we monetize the operational half of that signal.
**Visual:** Big number left (11bn), path Now → Next → Later right.
**Say:** "Start one rail, one bank. Then multi-bank, multi-rail, regulator view."

### SLIDE 11 — Business + progress
**Title:** Who pays, how, and why they buy
**Body:**
- Who pays: banks, fintechs, mobile money operators. Buyer: Head Digital Banking / Ops Risk (owns CBN timelines + outage cost).
- How: B2B SaaS, tiered by monthly complaint volume + channels. Each bank/channel/module = recurring.
- Why: meet CBN timelines (avoid ₦430M-type penalties), keep customers hearing from bank first, ease call-centre load.
- Built: complaint→spike→cause→drafts→approval in one flow + feed/incident/security/audit + adapters.
- Next: 1 pilot on live channels → more channels/telcos → settlement/reconciliation link.
**Say:** "Beneficiary is the customer. Payer is the bank. Sustainability is subscription tied to volume they already pay for in refunds and penalties."

### SLIDE 12 — Ask + close
**Title:** We catch the failure before it trends.
**3 pills:** Speaks Nigerian · Detects with math · Humans approve every naira
**Ask:** One pilot partner — one bank or fintech to run Conflux HQ on live complaint channels. Team Zymic + contact.
**Closer (pick one):**
> ConfluxHQ is the early-warning layer for money movement — it hears the user when the system can't feel itself failing.
**Alt:** ConfluxHQ is the user-side settlement observability banks are missing.
**Visual:** Midnight navy, white text, single CTA.
**Say:** End on the MTN line: "Teamside green, userside red — we close that gap."

---

## What changed vs your current deck
1. Gap is slide 2, not slide 6. Backend-green vs user-red is the hook, not context.
2. Social (X/IG/FB) reframed as sensor → telemetry → API handoff, not "social listening tool".
3. API feed moved from invisible to Slide 7 hero — this is what makes you infrastructure per Track 1 rubric.
4. Transfer/login explicitly claimed as settlement + access infrastructure (judges will ask).
5. Business slide names buyer + why now (CBN clock + penalties + churn) + expansion one-rail → multi-bank → telco → regulator.
6. Trust slide merged into product: PII masked, tenant-isolated, MAD not LLM, 403 on money, audit log — covers security/fraud/privacy rubric without a separate boring slide.

## Demo script (60 sec, matches your backend)
1. Seed (42): 5k txns + 1k complaints + v4.2.1 release
2. Detect: run_detection → incident 88% Switch A ₦1.8M
3. Investigate: agent → release cause + switch evidence (time-correlated, not proven)
4. Match: amount+time+channel score ≥0.55 → exception debited_not_credited
5. Drafts: customer message + IT ticket → human approve → audit
6. Poll: `GET /machine/updates?since=` in bank dashboard. Second: scam cluster goes to fraud queue, isolated 2-fee case does NOT spike.

## Fix before submitting
- Verify CBN 23,129 / ₦19.12bn / $329.3M / ₦430M from primary CBN PDF, not only press. Footnote exact table/page.
- Rename "Zymic Bank / 123" demo creds if shown publicly.
- Confirm .venv / node_modules gitignored.
