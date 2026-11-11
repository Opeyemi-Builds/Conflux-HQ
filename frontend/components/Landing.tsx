"use client";

import Link from "next/link";
import { motion, MotionConfig } from "framer-motion";
import {
  ArrowDown, ArrowUpRight, Check, ChevronRight, CircleDot,
  FileCheck2, Fingerprint, GitBranch, Layers3, MessageSquare, Network,
  Search, ShieldCheck, Workflow,
} from "lucide-react";
import type { ReactNode } from "react";
import Navbar from "./Navbar";

const features = [
  { icon: MessageSquare, number: "01", title: "Every complaint has context.", text: "Bring support tickets and social signals into one view. Keep the source, language, and original reference attached as each report moves through investigation.", wide: true },
  { icon: Fingerprint, number: "02", title: "Follow the evidence.", text: "Compare customer reports with payment status and system events. See what is recorded, what is a possible match, and what still needs checking." },
  { icon: GitBranch, number: "03", title: "Find the shared issue.", text: "Recognize patterns across failed transfers, duplicate debits, and delayed reversals. Investigate the incident behind the individual tickets." },
  { icon: FileCheck2, number: "04", title: "Give the fix an owner.", text: "Record the action, assign responsibility, and track the change through validation. Keep the evidence behind each decision in the same workspace.", wide: true },
];

const steps = [
  { title: "Connect the reports", text: "Collect complaints from your support channels. Preserve their origin and surface patterns worth a closer look." },
  { title: "Investigate together", text: "Review payment evidence, test likely explanations, and identify the records your team still needs." },
  { title: "Track the follow-through", text: "Assign a corrective action, record what changed, and review the evidence before marking the fix verified." },
];

const teams = [
  { icon: MessageSquare, title: "Customer operations", description: "Start with the customer.", items: ["Review complaints across channels", "Keep related reports together", "Review customer response drafts"] },
  { icon: Search, title: "Payment & engineering teams", description: "Get closer to the cause.", items: ["Compare payment and system records", "See hypotheses and missing evidence", "Own the corrective action"], featured: true },
  { icon: ShieldCheck, title: "Managers & reviewers", description: "Make the decision traceable.", items: ["Follow incident progress", "Review changes and validation", "Keep a record of approvals"] },
];

const faqs = [
  ["Who is Conflux built for?", "Conflux brings customer operations, payment teams, engineering, and bank reviewers into a shared incident workflow. Each team can follow a report from the initial complaint to the evidence behind a verified corrective action."],
  ["Where do the complaints come from?", "The platform supports bank complaint intake and social monitoring. The current prototype demonstrates bank delivery with synthetic support tickets and supports recorded social replay. Live sources depend on the configured connector and authorized access."],
  ["Does a payment match prove the cause?", "A possible payment match is a lead for investigation. Payment status, a customer report, and the timing of a system event each tell part of the story. Conflux keeps those distinctions visible so your team can decide what the evidence supports."],
  ["Can Conflux execute refunds or reversals?", "Financial proposals are for independent review only. Execution is disabled. The investigation workflow helps your team review evidence and record decisions."],
  ["What can I explore in the demo?", "Use the demo workspace to explore synthetic complaints, incidents, reconciliation cases, and review workflows. The prototype uses synthetic data. Live provider access and available workflows depend on the deployed environment."],
];

function Reveal({ children, className = "", delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  return <motion.div className={className} initial={{ opacity: 0, y: 24 }}
    whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.12 }}
    transition={{ duration: 0.7, delay, ease: [0.22, 1, 0.36, 1] }}>{children}</motion.div>;
}

function IncidentVisual() {
  return <div className="incident-visual" aria-label="Illustrative incident review with a customer report, pending payment evidence, and a proposed corrective action">
    <div className="visual-orbit orbit-one" /><div className="visual-orbit orbit-two" />
    <div className="incident-preview landing-float">
      <div className="preview-topline"><span><CircleDot size={13} /> INCIDENT REVIEW</span><span>ILLUSTRATION</span></div>
      <div className="preview-divider" />
      <div className="preview-icon"><Workflow size={25} strokeWidth={1.3} /></div>
      <h2>One issue.<br />The whole picture.</h2>
      <div className="preview-reference">Failed transfer <span>Under review</span></div>
      <div className="preview-nodes" aria-hidden="true"><span /><i /><span /><i /><span /><i /><span /></div>
      <div className="preview-bottom"><span>REPORT</span><span>EVIDENCE</span><span>ACTION</span></div>
    </div>
    <div className="floating-report landing-float">
      <span className="small-icon"><MessageSquare size={17} /></span>
      <div><p>“Debited, but not received.”</p><span>Customer report · In-app</span></div>
    </div>
    <div className="floating-evidence landing-float"><div><span className="preview-dot" /> Evidence to review</div>
      <p>Payment status <span>Pending</span></p><p>Corrective action <span>Proposed</span></p>
    </div>
  </div>;
}

export default function Landing() {
  return <MotionConfig reducedMotion="user"><div className="conflux-landing" id="top">
    <Navbar />
    <main>
      <section className="landing-hero landing-wrap">
        <div className="hero-glow" aria-hidden="true" />
        <Reveal className="hero-copy">
          <p className="landing-eyebrow"><span /> THE PAYMENT INCIDENT WORKSPACE</p>
          <h1><span className="landing-chrome">See the pattern.</span><br /><span className="landing-slate">Follow it through.</span></h1>
          <p className="hero-description">A failed payment is one ticket. A hundred could be one incident. Bring the complaints, evidence, and people together to find out — and track what happens next.</p>
          <div className="landing-buttons"><Link className="landing-button primary" href="/dashboard">Explore the workspace <ArrowUpRight size={18} /></Link>
            <a className="landing-button secondary" href="#workflow">See the workflow <ArrowDown size={16} /></a></div>
          <p className="hero-footnote">Built for bank operations. Explore with synthetic demo data.</p>
        </Reveal>
        <Reveal className="hero-art" delay={0.15}><IncidentVisual /></Reveal>
      </section>

      <section className="landing-wrap workflow-ribbon" aria-label="Core workflow">
        {[
          { icon: MessageSquare, title: "Gather the signals", subtitle: "Complaints & social reports" },
          { icon: Layers3, title: "Build the context", subtitle: "Incidents & payment evidence" },
          { icon: Search, title: "Test the explanation", subtitle: "Findings & missing evidence" },
          { icon: FileCheck2, title: "Follow the action", subtitle: "Ownership & validation" },
        ].map(({ icon: Icon, title, subtitle }, index) => (
          <div key={title}><span className="ribbon-index">0{index + 1}</span><Icon size={20} strokeWidth={1.3} /><h2>{title}</h2><p>{subtitle}</p></div>
        ))}
      </section>

      <section className="landing-wrap landing-section" id="platform">
        <Reveal className="section-heading"><div><p className="landing-eyebrow">ONE CONNECTED WORKSPACE</p><h2 className="landing-chrome">Less chasing context.<br />More moving forward.</h2></div>
          <p>Customer reports are the starting point. Give your team a clear path from the first signal to the action that follows.</p></Reveal>
        <div className="landing-features">{features.map(({ icon: Icon, ...feature }, index) => <Reveal key={feature.number} delay={index * 0.05} className={feature.wide ? "feature-wide" : ""}>
          <article className="landing-glass feature-card"><div className="feature-card-top"><Icon size={27} strokeWidth={1.2} /><span>{feature.number}</span></div>
            <h3>{feature.title}</h3><p>{feature.text}</p><div className="feature-rule" /></article>
        </Reveal>)}</div>
      </section>

      <section className="landing-process" id="workflow"><div className="landing-wrap landing-section">
        <Reveal><p className="landing-eyebrow">FROM SIGNAL TO FOLLOW-THROUGH</p><h2 className="landing-slate">A clearer path.<br />At every handoff.</h2></Reveal>
        <ol className="landing-steps">{steps.map((step, index) => <li key={step.title}><Reveal delay={index * 0.1}>
          <span className="step-number landing-chrome">0{index + 1}</span><h3>{step.title}</h3><p>{step.text}</p>
        </Reveal></li>)}</ol>
        <Reveal className="workflow-note"><ShieldCheck size={19} /><p>Every recommendation needs review. Every verified fix needs evidence.</p></Reveal>
      </div></section>

      <section className="landing-wrap landing-section" id="teams">
        <Reveal className="section-heading"><div><p className="landing-eyebrow">BUILT AROUND YOUR TEAM</p><h2 className="landing-chrome">Different roles.<br />A shared understanding.</h2></div>
          <p>Keep the people handling the complaint connected to the people investigating the payment and reviewing the change.</p></Reveal>
        <div className="landing-teams">{teams.map(({ icon: Icon, ...team }, index) => <Reveal key={team.title} delay={index * 0.07}>
          <article className={`landing-glass team-card ${team.featured ? "team-featured" : ""}`}>
            <Icon size={24} strokeWidth={1.4} /><p className="team-description">{team.description}</p><h3>{team.title}</h3>
            <ul>{team.items.map((item) => <li key={item}><Check size={15} />{item}</li>)}</ul>
            <Link href="/dashboard">Explore workspace <ArrowUpRight size={16} /></Link>
          </article>
        </Reveal>)}</div>
      </section>

      <section className="landing-wrap landing-section landing-faq" id="faq">
        <Reveal><p className="landing-eyebrow">A FEW DETAILS</p><h2 className="landing-slate">Good questions.<br />Clear answers.</h2></Reveal>
        <div>{faqs.map(([question, answer]) => <details key={question}><summary>{question}<span aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div>
      </section>

      <section className="landing-wrap landing-final-cta"><Reveal><div className="landing-glass">
        <p className="landing-eyebrow">THE NEXT STEP IS CLEARER TOGETHER</p><h2 className="landing-chrome">From “what happened?”<br />to “here’s what’s next.”</h2>
        <Link className="landing-button light" href="/dashboard">Step inside Conflux <ArrowUpRight size={18} /></Link>
      </div></Reveal></section>
    </main>

    <footer className="landing-footer">
      <div className="footer-orbit" aria-hidden="true"><div /><div /><div /></div>
      <div className="landing-wrap footer-content">
        <Reveal><h2><span className="landing-chrome">Bring the picture</span><br /><span className="landing-slate">together.</span></h2></Reveal>
        <div className="footer-body">
          <div><Link className="landing-brand" href="#top"><span className="brand-mark"><Network size={20} /></span>conflux<span className="brand-hq">HQ</span></Link>
            <p className="footer-description">The workspace for complaints,<br />payment evidence, and the next step.</p></div>
          <nav aria-label="Footer product navigation"><h3>Explore</h3><a href="#platform">The platform</a><a href="#workflow">The workflow</a><a href="#teams">Your team</a></nav>
          <nav aria-label="Footer workspace navigation"><h3>Workspace</h3><Link href="/login">Sign in <ArrowUpRight size={12} /></Link><Link href="/dashboard">Explore the demo <ArrowUpRight size={12} /></Link><a href="#faq">Questions & answers</a></nav>
          <div className="footer-tiles"><div className="landing-glass"><MessageSquare size={18} /> Connected reports</div><div className="landing-glass"><Search size={18} /> Evidence-led investigation</div><div className="landing-glass"><FileCheck2 size={18} /> Accountable follow-through</div></div>
        </div>
        <div className="footer-bottom"><span>© Conflux HQ</span><span>Built for the Access Youth Tech Forge hackathon</span><a href="#top">Back to top <ChevronRight size={13} /></a></div>
      </div>
    </footer>
  </div></MotionConfig>;
}
