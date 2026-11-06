# Conflux HQ: Product Requirements Document

Version 0.1 · Access Youth Tech Forge, Theme 1 (Payments and Financial Infrastructure) · Status: backend started

Team: Alegbeleye Opeyemi (Backend), Adakole Andrew (Frontend and Product Design), David Uwagbale (System Architecture), Adekola Folarin John (AI Engineer)

## 1. Overview

Conflux HQ is an AI complaint intelligence and analytics platform for banks. It pulls customer complaints from every channel into one feed, classifies and groups them, detects unusual spikes, investigates the likely cause, and drafts the response. Humans approve anything that touches money.

Payment and settlement failures (debit with no credit, unreversed ATM or POS debits, duplicate debits) show up as customer complaints before they show up anywhere else. Banks see these one ticket at a time and learn about systemic faults too late. Conflux HQ is the early-warning layer.

## 2. Problem

**How it works today.** Complaints arrive through X, Instagram, Facebook, email, call centres, branches and in-app chat. Each channel has its own team and each complaint is its own ticket.

**Where it falls short.** No single view across channels. Teams cannot tell an isolated incident from a systemic fault, so root causes surface after the issue is public.

**Evidence.** The CBN received 23,129 complaints in 2025, up 10.53% from 20,925 in 2024, and ordered ₦19.12bn and $329.3m refunded (CBN 2025 data as reported by Leadership and Prime Business Africa; confirm against CBN publications).

## 3. Goals and non-goals

**Goals (72 hours)**
- One end-to-end flow: complaint in, spike detected, cause suggested, action drafted, human approval.
- Analytics on complaint trends by issue, channel and location.
- Clearly labelled synthetic data, with adapters so a bank can plug in real sources.

**Non-goals (roadmap, not claimed)**
- Live bank, switch or social platform integrations.
- Real customer data and production-grade security.
- Automatic reversals without human approval.

## 4. Users

| User | Needs | Primary view |
| --- | --- | --- |
| Customer service agent | What is happening, what to tell customers, approve replies | Agent view |
| IT / engineering | Root cause, affected component, version, evidence | IT view |
| Operations / management | Trends, priority, cost and SLA exposure | Management view |
| Customers (indirect) | Be told first, fast resolution | Holding messages |

## 5. Core scenario (the demo)

1. A synthetic feed streams in complaints from X, Instagram, Facebook, email and call transcripts, including Pidgin ("my money don enter nowhere").
2. At 10:00 a simulated app release (v4.2.1) goes live. From about 10:12, failed-transfer complaints rise sharply on USSD and the app through one switch.
3. Conflux HQ flags the spike with volume, growth rate and channels.
4. The agent matches complaints to simulated transactions, checks release and outage logs, and states the likely cause with confidence.
5. It drafts a customer holding message and an IT ticket.
6. A human approves any message or reversal. Every agent step is logged.

A second scenario shows breadth: a fake-agent scam cluster routed to the security queue.

## 6. Scope

**Must have:** unified feed and storage; AI classification; spike detection; transaction matching and cause investigation; draft message and IT ticket; human approval and audit log; dashboard.

**Should have:** role-based views; fraud routing queue; priority scoring; manual "paste a complaint" box.

**Could have:** embedding-based grouping; exportable incident report; local-language evaluation set.

## 7. Functional requirements

| ID | Requirement |
| --- | --- |
| F1 | Ingest complaints from a JSON/CSV feed and a live simulator, tagged with channel, timestamp and masked customer reference. |
| F2 | Classify into: failed transfer, double debit, card or ATM, POS, fees, loan, app or login, fraud or scam, other. |
| F3 | Extract severity, sentiment, language and mentioned transaction details. |
| F4 | Aggregate into 15-minute buckets per issue type, channel and region. |
| F5 | Detect a spike when a bucket exceeds its baseline by a threshold with a minimum volume. |
| F6 | Create an incident per spike with start time, volume, growth, affected channels and examples. |
| F7 | Match complaints to transaction records by reference, amount or time window. |
| F8 | Check system events around incident start and rank candidate causes with confidence. |
| F9 | Produce a plain-language summary per role. |
| F10 | Draft a customer holding message and an IT ticket. |
| F11 | Require human approval before any money-related action. |
| F12 | Audit-log every agent step and human decision. |
| F13 | Route fraud and scam complaints to a security queue. |
| F14 | Analytics: volume over time, top issues, issues by channel and region, incident history, time to detect. |

## 8. AI design

**Model.** Claude via the API for classification, extraction, summaries and drafting, with strict JSON output validated before saving.

**Investigation agent.** One agent with tools: get_incident_stats, search_transactions, get_system_events, compare_baseline, draft_message. It decides what to check, calls tools, forms a conclusion with confidence, drafts actions, then waits for approval. Each step is written to the audit log.

**Guardrails.** The agent proposes and never executes reversals. Drafts state only facts present in the data. Low confidence is shown as such.

**Spike detection (deterministic).** Per issue type, baseline is the median of trailing 15-minute buckets. Flag when the current count exceeds baseline plus 3 scaled median absolute deviations and has at least 10 complaints.

**Priority score.** Volume, growth rate, money at risk and customer-type weight, normalised to 0-100.

## 9. Synthetic data

All data is simulated and labelled on screen.
- About 1,000 complaints over 48 simulated hours across channels, with Pidgin, Yoruba, Hausa, Igbo and formal English, plus noise.
- About 5,000 transactions with a rising failure rate on the affected path after the release.
- System events: release v4.2.1 at 10:00 and one unrelated decoy.
- Planted stories: release-linked transfer failures, a scam cluster, and one isolated incident that must not trigger a spike.
- 100 hand-labelled complaints for measuring classification accuracy.

## 10. Dashboard

1. **Live overview:** alert banner, complaints per hour by issue type, channel breakdown, ranked incidents.
2. **Incident detail:** summary, timeline with release marker, matched transactions, candidate causes, agent trace, drafts, Approve and Reject.
3. **Analytics:** trends, top root causes, issues by channel and region, time to detect and resolve, repeat complaint rate.
4. **Complaint explorer:** unified feed with filters and AI tags.
5. **Security queue:** fraud and scam complaints.
6. **Audit log.**

## 11. Architecture and stack

React + Tailwind + Recharts; FastAPI + SQLAlchemy; PostgreSQL (SQLite for quick dev); Claude API with tool use; adapter interface per data source (simulator now, official APIs and bank systems later).

Flow: adapters → ingestion → classification → bucketing and spike detection → incident → agent investigation → drafts and approval → dashboard.

## 12. Security, fraud and data privacy

- Mask names, phone numbers and account numbers before analysis (NDPR alignment).
- Role-based access to views and actions.
- Synthetic data only in the prototype.
- Human approval on every money action; full audit trail.
- Fraud and scam complaints routed to security.
- No API keys in the repo; environment variables only.

## 13. Success criteria

- The planted spike is detected within minutes of simulated time.
- The agent names the release and affected channel as the likely cause.
- The isolated incident does not trigger a false spike.
- Drafts use only facts from the data; the audit log shows every step.
- Report honestly: classification accuracy on the 100 labelled complaints, time to alert, number of false spikes.

## 14. 72-hour plan

| Window | Opeyemi (Backend) | David (Architecture) | Andrew (Frontend) | Folarin (AI) |
| --- | --- | --- | --- | --- |
| 0-12h | API skeleton, ingestion, tables | Schema, adapters, environments | Design system, wireframes | Classification prompt, eval set |
| 12-30h | Bucketing, spike detection | Transaction matching, simulator | Overview, explorer | Extraction, summaries |
| 30-48h | Incidents, approval API, audit log | Integration, deployment | Incident detail, analytics | Investigation agent, drafting |
| 48-60h | Fixes, performance | End-to-end tests | Role views, polish | Guardrails, accuracy report |
| 60-72h | Demo mode, rehearsal | Backup demo build | Screenshots, recording | Final prompts, demo script |

One scenario must work end to end by hour 36 before adding anything else.

## 15. Business model and roadmap

**Benefits:** banks (lower support cost, fewer repeat complaints, less churn, stronger reputation), customers (faster resolution), IT teams (root causes). **Pays:** the bank, via subscription by channels connected and complaint volume. **Growth:** more banks, fintechs, telcos and mobile money operators, then more markets and languages. **Roadmap:** live social APIs, bank integrations, settlement and reconciliation data, approved low-risk auto-resolution, production security review.

## 16. Risks

| Risk | Mitigation |
| --- | --- |
| Social APIs restricted or paid | Simulator for demo, adapters for production |
| Inconsistent LLM output | Strict JSON schema, validation, deterministic spike detection |
| Demo fails live | Replay mode, recorded backup, local build |
| Overbuilding | Must-have list only until the core flow works |
| Overclaiming | Label synthetic data, claim nothing unmeasured |

## 17. Open questions

- Which region and channels does the simulated scenario use?
- Do we get Access Bank sandbox API access, and for what?
- Who labels the evaluation set?
- Can we confirm the CBN figures against CBN's own publication?

## 18. Bank accounts, authentication and multi-tenancy

- **Registration:** a bank registers with its name, optional CAC number, country and an admin's details. The admin becomes the bank's first `bank_admin`.
- **Login:** email and password through Supabase Auth; the backend verifies Supabase tokens and loads the user's bank and role.
- **Roles:** `bank_admin` (manages the bank and staff), `agent`, `it` (read and write complaints and incidents), `manager` (read-only analytics).
- **Staff:** admins invite colleagues by email with a role, and can change roles or disable accounts. A bank always keeps at least one active admin.
- **Tenant isolation:** every data table carries `bank_id`; every query is filtered by the signed-in user's bank; other banks' records return "not found". Row level security is enabled in the database as a second layer.
- **Audit:** registration, login, invites, role changes and spike detections are written to the audit log.
- **Out of scope for the hackathon:** SSO, multi-factor authentication, CAC verification of registrations, and bank approval workflows.
