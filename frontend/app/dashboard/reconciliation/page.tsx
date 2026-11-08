"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { caseStatuses, exceptionTypes, settlementStatuses, type CaseUpdate, type MatchResult, type PaymentException, type Proposal, type ReconciliationSummary } from "@/lib/reconciliation";
import { useDash } from "@/components/dashboard/Provider";
import { Card, PageHeader, TableWrap, Td, Th } from "@/components/dashboard/ui";

const field = "rounded border border-navy/20 p-2";
const action = "rounded bg-navy px-3 py-2 text-white disabled:opacity-50";
const label = (value: string) => value.replaceAll("_", " ");
const message = (error: unknown) => error instanceof Error ? error.message : "The request failed.";

export default function ReconciliationPage() {
  const { user } = useDash();
  const complaint = useSearchParams().get("complaint") ?? "";
  if (!user || user.role === "manager") return <PageHeader title="Reconciliation" sub="Operator access is required." />;
  return <Queue key={complaint} complaint={complaint} userId={user.id} admin={user.role === "bank_admin"} />;
}

function Queue({ complaint, userId, admin }: { complaint: string; userId: string; admin: boolean }) {
  const [cases, setCases] = useState<PaymentException[]>([]);
  const [summary, setSummary] = useState<ReconciliationSummary | null>(null);
  const [selected, setSelected] = useState<PaymentException | null>(null);
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [loadedKey, setLoadedKey] = useState("");
  const [queueError, setQueueError] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [complaintId, setComplaintId] = useState(complaint);
  const [match, setMatch] = useState<MatchResult | null>(null);
  const queryKey = JSON.stringify([status, offset, revision]);
  const loaded = loadedKey === queryKey;
  const currentCase = selected && (loaded ? cases.find((item) => item.id === selected.id) : null) || selected;

  useEffect(() => {
    let active = true;
    Promise.all([api.getExceptions(status, offset), api.getReconciliationSummary()]).then(([items, totals]) => {
      if (!active) return;
      setCases(items);
      setSummary(totals);
      setQueueError("");
    }).catch((err) => {
      if (active) setQueueError(message(err));
    }).finally(() => {
      if (active) setLoadedKey(queryKey);
    });
    return () => { active = false; };
  }, [status, offset, queryKey]);

  const refresh = () => setRevision((value) => value + 1);
  const showCreated = (item: PaymentException) => {
    setSelected(item);
    setOffset(0);
    setStatus("");
    refresh();
  };
  const run = async (fn: () => Promise<void>) => {
    setError("");
    setBusy(true);
    try {
      await fn();
    } catch (err) {
      setError(message(err));
      if (err instanceof ApiError && err.status === 409) {
        setStatus("");
        setOffset(0);
        refresh();
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Payment reconciliation" sub="Investigate reported payment exceptions and track settlement evidence." />
      {summary && <Card className="p-4">
        <h2 className="font-semibold">{summary.total_exceptions} recorded exceptions</h2>
        <p>Reported open amounts</p>
        {Object.entries(summary.reported_open_amount_by_currency).map(([currency, amount]) => (
          <p key={currency} className="font-mono">{currency} {amount}</p>
        ))}
        <p className="text-sm text-navy/65">{summary.amount_note}</p>
      </Card>}
      {error && <p role="alert" className="text-red-700">{error}</p>}
      <Card className="space-y-3 p-4">
        <h2 className="font-semibold">Complaint matching</h2>
        <div className="flex flex-wrap items-end gap-2">
          <label className="grid gap-1">Complaint ID
            <input className={field} value={complaintId} disabled={busy} onChange={(e) => {
              setComplaintId(e.target.value);
              setMatch(null);
            }} />
          </label>
          <button className={action} disabled={busy || !complaintId.trim()} onClick={() => run(async () => {
            setMatch(null);
            setMatch(await api.matchComplaint(complaintId.trim()));
          })}>Find candidates</button>
          <button className={action} disabled={busy || !complaintId.trim()} onClick={() => run(async () => {
            showCreated(await api.createComplaintException(complaintId.trim()));
          })}>Create from complaint</button>
        </div>
        {match && <>
          <p>{match.selected_transaction_id ? `Suggested transaction · ${match.selected_transaction_id}` : "Unresolved · No unique confident match."}</p>
          <p className="text-sm text-navy/65">Candidates are investigative leads. Customer ownership and refund eligibility require verification.</p>
          <ol className="list-decimal space-y-2 pl-5">
            {match.candidates.map((candidate) => <li key={candidate.transaction_id} className="break-all">
              {candidate.reference} · {candidate.transaction_id} · Confidence {candidate.confidence}
              <p className="text-sm">{candidate.reasons.join(" · ")}</p>
            </li>)}
          </ol>
        </>}
      </Card>
      <Card className="p-4">
        <details>
          <summary className="cursor-pointer font-semibold">Create manual case</summary>
          <form className="mt-3 flex flex-wrap items-end gap-2" onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            const amount = String(data.get("amount")).trim();
            void run(async () => showCreated(await api.createException({
              exception_type: data.get("type") as PaymentException["exception_type"],
              currency: String(data.get("currency")).toUpperCase(),
              ...(amount && { amount }),
            })));
          }}>
            <label className="grid gap-1">Exception type<select className={field} name="type">
              {exceptionTypes.map((type) => <option key={type} value={type}>{label(type)}</option>)}
            </select></label>
            <label className="grid gap-1">Amount<input className={field} name="amount" inputMode="decimal" pattern="[0-9]+(\.[0-9]{1,2})?" /></label>
            <label className="grid gap-1">Currency<input className={field} name="currency" defaultValue="NGN" pattern="[A-Za-z]{3}" required maxLength={3} /></label>
            <button className={action} disabled={busy}>Create case</button>
          </form>
        </details>
      </Card>
      <Card className="p-4">
        <div className="mb-3 flex flex-wrap items-end gap-2">
          <label className="grid gap-1">Case status<select className={field} value={status} onChange={(event) => {
            setStatus(event.target.value);
            setOffset(0);
          }}>
            <option value="">All statuses</option>
            {caseStatuses.map((value) => <option key={value} value={value}>{label(value)}</option>)}
          </select></label>
          <button className={action} onClick={refresh}>Refresh queue</button>
        </div>
        {!loaded ? <p role="status">Loading cases…</p> : queueError ? <p role="alert">{queueError}</p> : cases.length === 0 ? <p>No cases found.</p> :
          <TableWrap>
            <thead><tr><Th>Case</Th><Th>Status</Th><Th>Settlement</Th><Th>Reported amount</Th><Th>Owner</Th><Th>Priority</Th></tr></thead>
            <tbody>{cases.map((item) => <tr key={item.id}>
              <Td><button className="underline" onClick={() => setSelected(item)}>{label(item.exception_type)} · {item.id.slice(0, 8)}</button></Td>
              <Td>{label(item.status)}</Td><Td>{label(item.settlement_status)}</Td>
              <Td>{item.amount == null ? "—" : `${item.currency} ${item.amount}`}</Td>
              <Td>{item.owner ?? "Unassigned"}</Td><Td>{item.priority}</Td>
            </tr>)}</tbody>
          </TableWrap>}
        <div className="mt-3 flex gap-2">
          <button className={action} disabled={!loaded || offset === 0} onClick={() => setOffset(offset - 50)}>Previous</button>
          <button className={action} disabled={!loaded || !!queueError || cases.length < 50} onClick={() => setOffset(offset + 50)}>Next</button>
        </div>
      </Card>
      {currentCase && <CasePanel key={`${currentCase.id}-${currentCase.updated_at}`} item={currentCase} admin={admin} userId={userId} onProposalCreated={refresh} onSaved={(item) => {
        setSelected(item);
        refresh();
      }} />}
    </div>
  );
}

function CasePanel({ item, userId, admin, onSaved, onProposalCreated }: { item: PaymentException; userId: string; admin: boolean; onSaved: (item: PaymentException) => void; onProposalCreated: () => void }) {
  const [proposals, setProposals] = useState<Proposal[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const closed = item.status === "resolved" || item.status === "rejected";

  useEffect(() => {
    let active = true;
    api.getProposals(item.id).then((result) => { if (active) setProposals(result); }).catch((err) => {
      if (active) setError(message(err));
    });
    return () => { active = false; };
  }, [item.id, revision]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (err) {
      setError(message(err));
      if (err instanceof ApiError && err.status === 409) setRevision((value) => value + 1);
    } finally {
      setBusy(false);
    }
  };

  const update = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const status = form.get("status") as PaymentException["status"];
    const settlement = form.get("settlement") as PaymentException["settlement_status"];
    const owner = String(form.get("owner")).trim();
    const evidence = String(form.get("evidence")).trim();
    const priority = Number(form.get("priority"));
    const approval = form.has("approval");
    const patch: CaseUpdate = {
      ...(status !== item.status && { status }),
      ...(settlement !== item.settlement_status && { settlement_status: settlement }),
      ...(owner !== (item.owner ?? "") && { owner: owner || null }),
      ...(evidence !== (item.evidence_summary ?? "") && { evidence_summary: evidence || null }),
      ...(priority !== item.priority && { priority }),
      ...(approval !== item.approval_required && { approval_required: approval }),
    };
    if (Object.keys(patch).length) void run(async () => onSaved(await api.updateException(item.id, patch)));
  };

  return <Card className="space-y-4 p-4">
    <h2 className="font-semibold">Case {label(item.exception_type)} · {item.id}</h2>
    <dl className="grid gap-2 break-all text-sm md:grid-cols-2">
      {Object.entries({
        Complaint: item.complaint_id, Transaction: item.transaction_id, Processor: item.processor,
        Channel: item.payment_channel, Confidence: item.match_confidence,
        "Reported amount": item.amount == null ? null : `${item.currency} ${item.amount}`,
        Created: item.created_at, Updated: item.updated_at, Resolved: item.resolved_at,
      }).map(([key, value]) => <div key={key}><dt className="font-semibold">{key}</dt><dd>{value ?? "—"}</dd></div>)}
    </dl>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <form className="grid gap-3 sm:grid-cols-2" onSubmit={update}>
      <label className="grid gap-1">Status<select className={field} name="status" defaultValue={item.status}>
        {caseStatuses.map((value) => <option key={value} value={value}>{label(value)}</option>)}
      </select></label>
      <label className="grid gap-1">Settlement<select className={field} name="settlement" defaultValue={item.settlement_status}>
        {settlementStatuses.map((value) => <option key={value} value={value}>{label(value)}</option>)}
      </select></label>
      <label className="grid gap-1">Owner<input className={field} name="owner" maxLength={128} defaultValue={item.owner ?? ""} /></label>
      <label className="grid gap-1">Priority<input className={field} name="priority" type="number" min={0} max={100} defaultValue={item.priority} required /></label>
      <label className="grid gap-1 sm:col-span-2">Evidence summary<textarea className={field} name="evidence" maxLength={2000} defaultValue={item.evidence_summary ?? ""} /></label>
      <label><input type="checkbox" name="approval" defaultChecked={item.approval_required} /> Approval required</label>
      <button className={action} disabled={busy}>Save case</button>
    </form>
    <h3 className="font-semibold">Financial proposals</h3>
    <p>Review approval only — execution disabled; no funds moved.</p>
    <p className="text-sm">Only a bank administrator other than the proposer can record a decision. Approval leaves case status unchanged.</p>
    <button className={action} disabled={busy} onClick={() => setRevision((value) => value + 1)}>Reload proposals</button>
    {proposals == null ? <p>Proposals unavailable until loaded.</p> : proposals.length === 0 ? <p>No proposals.</p> : proposals.map((proposal) => (
      <div className="space-y-1 rounded border p-3 text-sm" key={proposal.id}>
        <p className="font-semibold">{proposal.kind} · {proposal.currency} {proposal.amount} · {proposal.status}</p>
        <p>{proposal.reason}</p>
        <p className="break-all">Proposer {proposal.proposed_by} · Reviewer {proposal.decided_by ?? "—"} · Decision time {proposal.decided_at ?? "—"}</p>
        {proposal.status === "pending" && admin && proposal.proposed_by !== userId && (["approved", "rejected"] as const).map((decision) => (
          <button className={`${action} mr-2`} key={decision} disabled={busy} onClick={() => run(async () => {
            const saved = await api.decideProposal(proposal.id, decision);
            setProposals((current) => current?.map((value) => value.id === saved.id ? saved : value) ?? null);
          })}>{decision === "approved" ? "Approve review" : "Reject"}</button>
        ))}
      </div>
    ))}
    {proposals && !closed && item.amount != null && !proposals.some((proposal) => proposal.status !== "rejected") &&
      <form className="grid gap-2 sm:grid-cols-2" onSubmit={(event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const data = new FormData(form);
        const amount = String(data.get("amount"));
        const cents = (value: string) => {
          const [whole, fraction = ""] = value.split(".");
          return BigInt(whole) * BigInt(100) + BigInt(fraction.padEnd(2, "0").slice(0, 2));
        };
        void run(async () => {
          if (cents(amount) <= BigInt(0) || cents(amount) > cents(item.amount!)) throw new Error("Enter a positive amount within the reported case amount.");
          const proposal = await api.createProposal(item.id, {
            kind: data.get("kind") as Proposal["kind"], amount, reason: String(data.get("reason")).trim(),
          });
          setProposals((current) => [...(current ?? []), proposal]);
          form.reset();
          onProposalCreated();
        });
      }}>
        <label className="grid gap-1">Proposal type<select className={field} name="kind"><option value="refund">Refund</option><option value="reversal">Reversal</option></select></label>
        <label className="grid gap-1">Amount in {item.currency}<input className={field} name="amount" inputMode="decimal" pattern="[0-9]+(\.[0-9]{1,2})?" required /></label>
        <label className="grid gap-1 sm:col-span-2">Reason<textarea className={field} name="reason" required minLength={10} maxLength={2000} /></label>
        <button className={action} disabled={busy}>Submit for review</button>
      </form>}
  </Card>;
}
