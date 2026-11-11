"use client";

import { useRef } from "react";
import Image from "next/image";
import Link from "next/link";
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { ArrowRight, ArrowUpRight, Check, FileCheck2, Fingerprint, GitBranch, Layers3, MessageSquare, Search, ShieldCheck } from "lucide-react";

const channels = ["Support tickets", "In-app reports", "Email", "Call centre", "Branch", "Social signals"];
const workflow = [
  { title: "Start with the report.", text: "A complaint arrives with a source, a timestamp, and a customer’s account of what happened. Keep that context attached as the report moves through the workflow.", detail: "Source preserved · Sensitive details masked", icon: MessageSquare },
  { title: "Recognize the shared issue.", text: "Review related complaints together. A pattern across transfers, duplicate debits, or delayed reversals can give your team a reason to investigate beyond a single ticket.", detail: "Related reports · Incident context", icon: GitBranch },
  { title: "Examine the evidence.", text: "Compare reported experiences with payment status and recorded system events. Keep observations, possible explanations, and missing evidence distinct.", detail: "Payment records · Investigation findings", icon: Search },
  { title: "Put the next step in motion.", text: "Record a corrective action, assign an owner, and document the change. Review the validation evidence before marking the fix verified.", detail: "Accountable owner · Recorded validation", icon: FileCheck2 },
];
const teams = [
  { title: "Customer operations", heading: "Know what to tell the customer.", text: "Keep the original report connected to the incident as the investigation develops.", items: ["Review the complaint history", "Find related reports", "Review proposed customer responses"] },
  { title: "Payment & engineering", heading: "Get the context behind the ticket.", text: "Bring payment evidence and system records into the same conversation.", items: ["Compare recorded payment status", "Review likely explanations", "Assign and document corrective work"] },
  { title: "Managers & reviewers", heading: "See what changed, and why.", text: "Follow incident progress and review the evidence behind important decisions.", items: ["Track ownership and progress", "Review validation observations", "Keep an approval history"] },
];
const questions = [
  ["What is Conflux?", "Conflux is a workspace for bank complaint monitoring, payment incident investigation, and corrective actions. It connects the customer report to the people reviewing the evidence and recording the next step."],
  ["How are complaints brought into the platform?", "Bank systems can deliver support tickets through authenticated complaint intake. Social monitoring provides an additional source of signals. The prototype demonstrates these flows with synthetic tickets and recorded social replay; live access depends on the configured connectors."],
  ["Does a shared complaint pattern establish a technical cause?", "A pattern helps a team decide where to investigate. Establishing a technical cause requires additional evidence and review. Conflux keeps customer reports, payment records, possible explanations, and bank-confirmed findings distinguishable."],
  ["What happens when payment evidence is incomplete?", "The investigation can list the missing evidence and recommend checks. A provider timeout remains an unknown outcome until an authorized status query provides more information."],
  ["How are corrective actions verified?", "An action moves through review, implementation, and monitoring. Verification requires an authorized reviewer and recorded validation evidence, with a confirmed cause or change reference as required by the workflow."],
  ["Can the platform move customer funds?", "Refund and reversal proposals are available for review. Financial execution is disabled in this prototype. An approved proposal records a review decision."],
  ["Can I try it without connecting a bank system?", "Yes. The demo uses synthetic records so you can explore complaints, incidents, payment reconciliation, and review workflows. Available integrations depend on the deployed environment."],
];

export default function CastDetails() {
  const ctaSectionRef = useRef<HTMLElement>(null);
  const reduced = useReducedMotion();

  const { scrollYProgress } = useScroll({
    target: ctaSectionRef,
    offset: ["start end", "center center"],
  });

  const x = useTransform(scrollYProgress, [0, 1], ["50%", "0%"]);
  const y = useTransform(scrollYProgress, [0, 1], ["50%", "0%"]);
  const scale = useTransform(scrollYProgress, [0, 1], [1.5, 1]);
  const opacity = useTransform(scrollYProgress, [0, 0.25, 1], [0.65, 0.9, 1]);

  return <div className="cast-details">
    <section className="cast-long-section cast-introduction">
      <div className="cast-long-wrap">
        <p className="cast-kicker">A CLOSER LOOK AT CONFLUX</p>
        <h2>There’s a story<br />behind every ticket.</h2>
        <div className="cast-intro-bottom"><p>“I was debited. They haven’t received it.”</p><p>For the customer, it’s personal. For your team, it may be one report in a growing pattern. Conflux helps you hold both perspectives in view.</p></div>
        <div className="cast-channel-list" aria-label="Complaint channels">{channels.map((channel) => <span key={channel}>{channel}</span>)}</div>
        <p className="cast-small-note">Source availability depends on your bank’s configured connectors.</p>
      </div>
    </section>

    <section className="cast-long-section cast-dark-section" id="platform">
      <div className="cast-long-wrap">
        <p className="cast-kicker">THE CONTEXT YOUR TEAM NEEDS</p>
        <div className="cast-split-heading"><h2>Scattered signals.<br />A shared understanding.</h2><p>Support has the complaint. Payments has the transaction record. Engineering has the system history. Bring the relevant pieces into one incident.</p></div>
        <div className="cast-context-grid">
          {[
            { icon: MessageSquare, title: "What the customer reported", text: "Preserve the customer’s account, complaint channel, and timing. Keep every report individually traceable." },
            { icon: Layers3, title: "What the records show", text: "Review retained payment status and nearby system events, with their sources and associations visible." },
            { icon: Fingerprint, title: "What still needs checking", text: "See gaps in the evidence alongside possible explanations. Give the next reviewer a clear starting point." },
          ].map(({ icon: Icon, title, text }) => <article key={title}><Icon size={29} strokeWidth={1.25} /><h3>{title}</h3><p>{text}</p></article>)}
        </div>
      </div>
    </section>

    <section className="cast-long-section" id="workflow">
      <div className="cast-long-wrap">
        <p className="cast-kicker">THE WORKFLOW</p>
        <h2>From first signal<br />to the next clear step.</h2>
        <div className="cast-detailed-steps">{workflow.map(({ title, text, detail, icon: Icon }, index) => <article key={title}>
          <div className="cast-step-number">0{index + 1}</div><div><h3>{title}</h3><p>{text}</p><span className="cast-step-detail">{detail}</span></div><Icon size={34} strokeWidth={1.1} />
        </article>)}</div>
      </div>
    </section>

    <section className="cast-long-section cast-evidence-section" id="evidence">
      <div className="cast-long-wrap cast-two-columns">
        <div><p className="cast-kicker">AN EVIDENCE-LED VIEW</p><h2>See what’s known.<br />Ask what’s missing.</h2>
          <p className="cast-long-description">An investigation is easier to review when the findings show where they came from. Follow the records behind a possible explanation and keep the unanswered questions in view.</p>
          <Link className="cast-text-link" href="/dashboard">Explore the workspace <ArrowUpRight size={16} /></Link></div>
        <div className="cast-evidence-card">
          <div className="cast-example-label"><span>INCIDENT BRIEF</span><span>ILLUSTRATIVE EXAMPLE</span></div>
          <h3>Transfer delivery under review</h3>
          <div><span className="cast-record-label">CUSTOMER REPORT</span><p>Account debited. Recipient says funds have not arrived.</p></div>
          <div><span className="cast-record-label">PAYMENT RECORD</span><p>The associated provider record shows a pending status.</p></div>
          <div><span className="cast-record-label">OPEN QUESTION</span><p>Has the payment reached a final settlement state?</p></div>
          <div className="cast-example-next"><Search size={17} /><span>Suggested check<br /><strong>Review the latest provider status.</strong></span></div>
        </div>
      </div>
    </section>

    <section className="cast-long-section" id="teams">
      <div className="cast-long-wrap">
        <p className="cast-kicker">MADE FOR THE PEOPLE DOING THE WORK</p>
        <h2>Different responsibilities.<br />The same picture.</h2>
        <div className="cast-role-grid">{teams.map((team, index) => <article key={team.title}>
          <span className="cast-role-index">0{index + 1} / {team.title}</span><h3>{team.heading}</h3><p>{team.text}</p>
          <ul>{team.items.map((item) => <li key={item}><Check size={15} />{item}</li>)}</ul>
          <Link href="/dashboard">Open workspace <ArrowRight size={16} /></Link>
        </article>)}</div>
      </div>
    </section>

    <section className="cast-long-section cast-action-section" id="corrective-actions">
      <div className="cast-long-wrap">
        <p className="cast-kicker">ACCOUNTABILITY AFTER THE INVESTIGATION</p>
        <div className="cast-split-heading"><h2>The handoff<br />is part of the fix.</h2><p>Turn a recommendation into work someone owns. Keep the change reference and validation observations alongside the action, ready for review.</p></div>
        <ol className="cast-action-stages">{["Proposed", "Accepted", "In progress", "Monitoring", "Verified"].map((stage, index) => <li key={stage}><span>0{index + 1}</span><h3>{stage}</h3></li>)}</ol>
        <div className="cast-action-notes"><div><h3>A named owner</h3><p>Make responsibility and the intended next step clear.</p></div><div><h3>A recorded change</h3><p>Keep the change reference connected to the incident.</p></div><div><h3>A reviewed outcome</h3><p>Use recorded validation evidence to support verification.</p></div></div>
      </div>
    </section>

    <section className="cast-long-section cast-dark-section">
      <div className="cast-long-wrap cast-two-columns">
        <div><p className="cast-kicker">DECISIONS WITH A RECORD</p><h2>Keep the reasoning.<br />Keep the responsibility.</h2></div>
        <div className="cast-principles">
          {[
            ["Reports retain their source.", "Keep customer reports, social signals, and payment evidence identifiable throughout the review."],
            ["Recommendations stay reviewable.", "See hypotheses and suggested checks alongside the stored evidence they refer to."],
            ["Verification requires evidence.", "A reviewer records the basis for a verified action. A quieter complaint feed alone does not establish a permanent fix."],
            ["Financial proposals require review.", "The prototype records refund and reversal review decisions with execution disabled."],
          ].map(([title, text]) => <div key={title}><ShieldCheck size={21} strokeWidth={1.4} /><div><h3>{title}</h3><p>{text}</p></div></div>)}
        </div>
      </div>
    </section>

    <section className="cast-long-section cast-faq-section" id="questions">
      <div className="cast-long-wrap cast-two-columns"><div><p className="cast-kicker">A FEW THINGS TO KNOW</p><h2>Before you<br />step inside.</h2><p className="cast-long-description">A closer look at the platform, the prototype, and how the workflow fits your team.</p></div>
        <div className="cast-long-faq">{questions.map(([question, answer]) => <details key={question}><summary>{question}<span aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div>
      </div>
    </section>

    <section className="cast-long-section cast-closing" ref={ctaSectionRef}>
      <div className="cast-long-wrap">
        <p className="cast-kicker">BRING THE PICTURE TOGETHER</p>
        <h2>Start with a complaint.<br />See where it leads.</h2>
        <p>Explore the workspace with synthetic demo data.</p>
        <div className="cast-closing-cta-stage">
          <motion.div
            style={reduced ? undefined : { x, y, scale, opacity }}
            className="cast-closing-cta-motion"
          >
            <Link className="cast-pill cast-primary" href="/dashboard">
              Explore Conflux <ArrowUpRight size={17} />
            </Link>
          </motion.div>
        </div>
      </div>
    </section>

    <footer className="cast-long-footer">
      <div className="cast-long-wrap">
        <div className="cast-footer-main">
          <Link className="cast-brand" href="/" aria-label="Conflux HQ home">
            <Image
              src="/conflux-logo-full.jpg"
              alt="Conflux HQ"
              width={30}
              height={30}
              className="cast-brand-logo"
            />
            <span>conflux<span className="cast-hq">HQ</span></span>
          </Link>
          <nav aria-label="Product footer">
            <a href="#platform">Platform</a>
            <a href="#workflow">Workflow</a>
            <a href="#teams">Your team</a>
            <a href="#questions">Questions</a>
            <Link href="/developers">Developers</Link>
            <Link href="/login">Sign in <ArrowUpRight size={13} /></Link>
          </nav>
        </div>

        {/* Large Text Brand Display */}
        <div className="cast-footer-display" aria-hidden="true">
          <span>CONFLUX</span>
          <span className="cast-footer-display-hq">HQ</span>
        </div>

        <div className="cast-footer-meta">
          <span>© Conflux HQ</span>
          <span>Built for the Access Youth Tech Forge hackathon</span>
          <a href="#">Back to top ↑</a>
        </div>
      </div>
    </footer>
  </div>;
}
