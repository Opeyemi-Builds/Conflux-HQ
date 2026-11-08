"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError, type BackendComplaint } from "@/lib/api";
import { ISSUE_LABEL, type IssueType } from "@/lib/types";
import { useDash } from "@/components/dashboard/Provider";
import { Card, PageHeader } from "@/components/dashboard/ui";

export default function ComplaintPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <ComplaintDetail key={id} id={id} />;
}

function ComplaintDetail({ id }: { id: string }) {
  const { user } = useDash();
  const [item, setItem] = useState<BackendComplaint | null>(null);
  const [error, setError] = useState("");
  const [classifying, setClassifying] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    api.getComplaint(id).then((result) => {
      if (active) setItem(result);
    }).catch((err) => {
      if (active) setError(err instanceof ApiError && err.status === 404 ? "Complaint not found." : "Could not load complaint.");
    });
    return () => { active = false; };
  }, [id, revision]);

  return <>
    <Link className="underline" href="/dashboard/complaints">Back to complaints</Link>
    <PageHeader title="Complaint detail" sub={id} />
    <button disabled={classifying} className="mb-3 underline" onClick={() => { setError(""); setRevision((value) => value + 1); }}>Refresh classification</button>
    {item && !item.issue_type && user?.role !== "manager" &&
      <button className="mb-3 ml-4 underline disabled:opacity-50" disabled={classifying} onClick={async () => {
        setClassifying(true);
        setError("");
        try {
          setItem(await api.classifyComplaint(id));
        } catch {
          setError("Classification failed. The submitted complaint is still available.");
        } finally {
          setClassifying(false);
        }
      }}>{classifying ? "Classifying…" : "Classify now"}</button>}
    {error && <p role="alert">{error}</p>}
    {!item && !error && <p role="status">Loading complaint…</p>}
    {item && <Card className="space-y-4 p-5">
      <p>{item.masked_text ?? item.text}</p>
      <dl className="grid gap-3 sm:grid-cols-2">
        {Object.entries({
          Classification: item.issue_type ? ISSUE_LABEL[item.issue_type as IssueType] ?? item.issue_type : "Pending",
          Severity: item.severity,
          Sentiment: item.sentiment,
          Summary: item.summary,
          "Reported amount": item.mentioned_amount,
          "Fraud flag": item.issue_type == null || item.is_fraud == null ? "Pending" : item.is_fraud ? "Flagged" : "Unflagged",
          Confidence: item.classification_confidence,
          Region: item.region,
          Occurred: item.occurred_at,
        }).map(([key, value]) => <div key={key}><dt className="font-semibold">{key}</dt><dd>{value ?? "Unavailable"}</dd></div>)}
      </dl>
      <div className="flex flex-wrap gap-4">
        {item.incident_id && <Link className="underline" href={`/dashboard/incidents/${item.incident_id}`}>View attached incident</Link>}
        {user?.role !== "manager" && <Link className="underline" href={`/dashboard/reconciliation?complaint=${id}`}>Investigate in reconciliation</Link>}
      </div>
    </Card>}
  </>;
}
