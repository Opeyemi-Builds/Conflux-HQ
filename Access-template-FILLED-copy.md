# ConfluxHQ — Filled for Access Youth Tech Forge Template
> Paste-ready. Keep the template's fonts/colors/layouts — just replace text. Your template is ~12 slides, so this is mapped 1:1.
> Workspace is down right now so I can't write into the .pptx binary directly — paste this in (5 min), and I'll generate the filled .pptx the moment it's back.

## SLIDE 1 — Cover [keep template cover layout]
**Title:** Payment failures show up as complaints first. Conflux HQ catches them before they trend.
**Subtitle:** An AI complaint-intelligence layer for banks · Track 1 Payments & Financial Infrastructure
**Footer:** Team Zymic
**Speaker:** "Money movement in Africa has come a long way. But when it fails, the bank finds out last — from Twitter."

## SLIDE 2 — Problem [template: Problem]
**Header:** The dashboard is green. The customers are not.
**Bullets (keep to 3):**
- 2:07 PM Friday. Amaka sends ₦50,000. App says "Successful." Debited. Receiver hears nothing.
- Bank side: servers up, health checks 200 OK, nothing red.
- Amaka on X: "Una don debit me twice, my money never enter. Na so una dey do?"
**Callout box:** Transfer failure = settlement didn't complete. Login failure = access block when it gates money. That IS infrastructure.
**Speaker:** Backend-green vs user-red. MTN airtime: backend says OK, user side keeps failing.

## SLIDE 3 — Problem cont'd / Why now [template: Problem in numbers OR Market pain]
**Header:** The cost of finding out late
- 23,129 complaints to CBN 2025, up 10.53% from 20,925
- ₦19.12bn + $329.3M refunds ordered — naira roughly doubled from ₦9.66bn
- ₦430M in 21 penalties for slow handling
- Thesis: fraud losses falling (₦52.26bn 2024, down 51% NIBSS) while complaints rise. Pain moved from theft to failed/disputed/delayed.
**Footnote (small):** CBN 2025 annual report as reported by Nairametrics/Legit/Prime Business Africa — verify primary table. NIBSS fraud.
**Speaker:** "Fraud is falling. Complaints are not."

## SLIDE 4 — Solution [template: Solution]
**Header:** Conflux HQ turns complaints into telemetry
1. **Detect** — One feed X/IG/FB + calls + branch. English, Pidgin, Yoruba, Hausa, Igbo.
2. **Investigate** — Math flags spike (median + MAD, 15-min), not LLM. Agent checks switch logs + releases.
3. **Decide** — Plain-language cause, ranked by volume, growth, money at risk. Rules engine if cloud down.
4. **Act** — Drafts customer message + IT ticket. Human approves money moves.
**Speaker:** Social is the sensor. Value is detection + cause + handoff.

## SLIDE 5 — How it works / Product [template: Product / How it works]
**Header:** We don't give banks another dashboard. We give them a feed.
**Left (code card, monospace 12pt):**
```
GET /machine/updates?since=<cursor>
Authorization: Bearer cfx_api_...
collections: complaints, incidents,
drafts, actions, investigations, audit
```
5-sec cursor poll · HMAC webhooks x-forge-signature · Try-It explorer
**Right bullets:**
- Plugs into existing bank dashboard
- Grouped + categorized → patterns compound
- handoff, not login
**Speaker:** "Banks already have dashboards. Conflux lands inside theirs. That's why we're infrastructure."

## SLIDE 6 — Demo / Traction [template: Demo / Traction / Product in action]
**Header:** Same Friday. This time, the bank spoke first.
- 10:00 Release v4.2.1 ships → 10:12 spike flagged → 10:14 incident + draft → 10:16 human approves → holding SMS out
- Proof: 88% failure Switch A, ₦1.8M at risk — flagged in minutes
- Prototype live end-to-end on synthetic data: 1,000 complaints, 5,000 txns, planted release. All simulated.
- Screenshots: feed spike vs baseline / Pidgin+Yoruba explorer / incident + approval gate (403) / audit log
**Speaker:** Caught early, told first, safe by design.

## SLIDE 7 — Competition / Why existing tools miss it [template: Competitive landscape]
**Header:** Why existing tools miss it
- APM (Datadog/Grafana): sees uptime — misses whether money arrived
- Social listening (Brandwatch/Sprinklr): sees sentiment — misses release/switch cause
- Ticketing/CRM: sees one case — misses pattern
- Fraud systems: sees theft — misses failed-transaction waves
- **Conflux: complaints as live telemetry + cause + human-approved fix**
**Speaker:** "None answers: did settlement complete for users on this switch right now?"

## SLIDE 8 — Market [template: Market opportunity]
**Header:** Every transfer is a chance to fail
- ~11bn instant NIP transfers 2024 · ₦1.07 quadrillion moved (NIBSS)
- Now: Nigerian banks → Next: OPay/Moniepoint/PalmPay, telcos, mobile money → Later: more African markets + languages
- Adjacent: social listening $9.15bn 2024, 14.3% CAGR — we monetize the operational half
**Speaker:** Start one rail, one bank. Then multi-bank, multi-rail, regulator view.

## SLIDE 9 — Business model [template: Business model]
**Header:** Who pays, how, and why they buy
- **Who pays:** banks, fintechs, mobile-money operators. Buyer: Head Digital Banking / Ops Risk.
- **How:** B2B SaaS, tiered by monthly complaint volume + channels. Each bank/channel/module = recurring.
- **Why:** meet CBN timelines (avoid ₦430M-type penalties), keep customers hearing from bank first, ease call-centre load.
**Speaker:** Beneficiary = customer. Payer = bank. Sustainability = subscription tied to volume they already pay in refunds.

## SLIDE 10 — Roadmap [template: Roadmap / Milestones]
**Header:** Working prototype → pilot → scale
- **Built:** complaint→spike→cause→drafts→approval + feed/incident/security/audit + adapters
- **Next:** 1 live pilot on real channels → more channels/telcos → settlement + reconciliation link
- Trust built-in: PII masked, tenant-isolated, MAD not LLM, 403 on money, audit log
**Speaker:** Link complaints to settlement data next — that's full Track 1.

## SLIDE 11 — Team [template: Team — keep photos/layout]
**Header:** Team Zymic
- Alegbeleye Opeyemi — Backend engineer, EEE student, DU
- Adakole Andrew — Frontend + product design, Founder Koraspace
- David Uwagbale — System architecture, 4 yrs dev
- Adekola Folarin John (AJ) — AI engineer, evaluation
**Speaker:** Builder team across backend, frontend, systems, AI eval.

## SLIDE 12 — Ask [template: Ask — keep contact layout]
**Header:** We catch the failure before it trends.
**Pills/badges:** Speaks Nigerian · Detects with math · Humans approve every naira
**Ask:** One pilot partner — one bank or fintech to run Conflux HQ on live complaint channels. + contact email/phone + demo line (seed 42 → detect → investigate → match → approve → poll /machine/updates)
**Closer — say this last:**
> ConfluxHQ is the early-warning layer for money movement — it hears the user when the system can't feel itself failing.
**Alt:** the user-side settlement observability banks are missing.

---
### Paste tips for your template
- Don't change template theme/fonts — only replace titles/bullets. Keep one message per slide.
- Slide 5 code card: use a dark rounded rectangle + Consolas 12pt if template has no code style.
- Slide 3 footnote 8pt muted — judges check sources.
- Slide 6: drop in 2-3 real screenshots from your dashboard (feed + incident + audit). Blur Zymic Bank/123 creds.
- If template has extra slides (Go-to-Market, Financials): merge Go-to-Market into Slide 8 Next/Later; put Financials as "pilot → 3 banks → 10 banks" only if asked — don't invent ARR.
