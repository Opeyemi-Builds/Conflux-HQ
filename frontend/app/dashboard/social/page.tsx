"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { type SocialAlias, type SocialAnalytics } from "@/lib/social";
import { useDash } from "@/components/dashboard/Provider";
import { Card, PageHeader, Stat } from "@/components/dashboard/ui";

const field = "rounded border border-navy/20 p-2";
const action = "rounded bg-navy px-3 py-2 text-white disabled:opacity-50";
const kinds = ["name", "handle", "hashtag", "contextual"] as const;
const platforms = ["x", "instagram", "facebook"] as const;

export default function SocialPage() {
  const { user } = useDash();
  const admin = user?.role === "bank_admin";
  const [data, setData] = useState<SocialAnalytics | null>(null);
  const [connector, setConnector] = useState<Awaited<ReturnType<typeof api.getXStatus>> | null>(null);
  const [aliases, setAliases] = useState<SocialAlias[] | null>(null);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.allSettled([api.getSocialAnalytics(), api.getXStatus(), api.getAliases()]).then(([analytics, status, aliasList]) => {
      if (!active) return;
      if (analytics.status === "fulfilled") setData(analytics.value);
      if (status.status === "fulfilled") setConnector(status.value);
      if (aliasList.status === "fulfilled") setAliases(aliasList.value.items);
      if ([analytics, status, aliasList].some((result) => result.status === "rejected")) {
        setError("Some social data could not be loaded. Refresh to retry.");
      }
    });
    return () => { active = false; };
  }, [revision]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Social action failed.");
    } finally {
      setBusy(false);
    }
  };

  const update = (index: number, patch: Partial<SocialAlias>) => {
    setAliases((current) => current?.map((alias, i) => i === index ? { ...alias, ...patch } : alias) ?? null);
  };

  return <div className="space-y-4">
    <PageHeader title="Social monitoring" sub="Live reputation signals from stored social receipts. The server polls X automatically — no manual pull needed." />
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <Card className="space-y-3 p-4">
      <h2 className="font-semibold">X connector</h2>
      <p>{connector ? (connector.credentials_configured ? "Live X credentials configured. The background poller collects mentions automatically." : "Live X credentials unavailable. New mentions arrive when the server is configured.") : "Connector status unavailable."}</p>
      {connector && <p className="text-sm">Reads today {connector.reads_today} of {connector.daily_post_limit}</p>}
      <div className="flex flex-wrap gap-2">
        <button className={action} disabled={busy || confirm} onClick={() => { setError(""); setRevision((value) => value + 1); }}>Refresh social data</button>
      </div>
    </Card>
    <Card className="space-y-3 p-4">
      <h2 className="font-semibold">Reputation over the last 24 hours</h2>
      <p className="text-sm">Reputation flags are triage signals. Allegations require independent verification.</p>
      {data ? <>
        <p className="text-xs">{data.window_start} to {data.window_end} · UTC</p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Stat label="Posts" value={String(data.total_posts)} />
          <Stat label="Authors" value={String(data.unique_authors)} />
          <Stat label="Engagement" value={String(data.total_engagement)} />
          <Stat label="High reach" value={String(data.high_reach_posts)} />
          <Stat label="Reputation risk" value={String(data.reputation_risk_posts)} />
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="Impressions" value={String(data.total_impressions)} />
          <Stat label="Avg reputation score" value={data.average_reputation_score != null ? String(data.average_reputation_score) : "—"} />
        </div>
        <h3 className="font-semibold">Top flags</h3>
        <ul>{Object.entries(data.top_reputation_flags).map(([flag, count]) => <li key={flag}>{flag.replaceAll("_", " ")} · {count}</li>)}</ul>
        {Object.keys(data.top_reputation_flags).length === 0 && <p>No flags in this window.</p>}
        {Object.keys(data.by_issue_type || {}).length > 0 && <>
          <h3 className="font-semibold">Posts by issue</h3>
          <ul>{Object.entries(data.by_issue_type).map(([issue, count]) => <li key={issue}>{issue.replaceAll("_", " ")} · {count}</li>)}</ul>
        </>}
        {Object.keys(data.by_platform || {}).length > 0 && <>
          <h3 className="font-semibold">Posts by platform</h3>
          <ul>{Object.entries(data.by_platform).map(([platform, count]) => <li key={platform}>{platform} · {count}</li>)}</ul>
        </>}
        {(data.top_posts || []).length > 0 && <>
          <h3 className="font-semibold">Top posts by reach</h3>
          <ol className="grid gap-2">
            {data.top_posts.map((post) => <li key={`${post.platform}:${post.post_id}`} className="rounded border border-navy/10 p-2 text-sm">
              <div className="flex flex-wrap gap-2 text-xs text-navy/60">
                <span>{post.platform}</span>
                <span>{post.engagement} engagement</span>
                <span>{post.impressions} impressions</span>
                {post.issue_type && <span>{post.issue_type.replaceAll("_", " ")}</span>}
              </div>
              {post.snippet && <p className="mt-1">{post.snippet}</p>}
              {post.source_url && <a className="underline text-xs" href={post.source_url} target="_blank" rel="noreferrer">Open source</a>}
            </li>)}
          </ol>
        </>}
        <details><summary className="cursor-pointer font-semibold">Hourly post velocity in UTC</summary>
          <ol className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
            {data.hourly_velocity.map(({ bucket_start, posts }) => <li key={bucket_start}><time dateTime={bucket_start}>{bucket_start}</time> · {posts} posts</li>)}
          </ol>
        </details>
      </> : <p>Social analytics unavailable until loaded.</p>}
    </Card>
    <Card className="space-y-3 p-4">
      <h2 className="font-semibold">Bank aliases</h2>
      {!aliases ? <p>Aliases unavailable until loaded.</p> : !admin ? (
        <ul>{aliases.map((alias, index) => <li key={index}>{alias.value} · {alias.kind} · {alias.platform ?? "All platforms"}</li>)}</ul>
      ) : <form className="space-y-2" onSubmit={(event) => { event.preventDefault(); setConfirm(true); }}>
        <fieldset disabled={busy || confirm} className="space-y-2">
          {aliases.map((alias, index) => <div key={index} className="flex flex-wrap items-end gap-2">
            <label className="grid gap-1">Alias {index + 1}<input className={field} value={alias.value} required minLength={2} maxLength={120} onChange={(event) => update(index, { value: event.target.value })} /></label>
            <label className="grid gap-1">Kind<select className={field} value={alias.kind} onChange={(event) => update(index, { kind: event.target.value as SocialAlias["kind"] })}>
              {kinds.map((kind) => <option key={kind}>{kind}</option>)}
            </select></label>
            <label className="grid gap-1">Platform<select className={field} value={alias.platform ?? ""} onChange={(event) => update(index, { platform: (event.target.value || null) as SocialAlias["platform"] })}>
              <option value="">All platforms</option>{platforms.map((platform) => <option key={platform}>{platform}</option>)}
            </select></label>
            <button type="button" className={action} onClick={() => setAliases(aliases.filter((_, i) => i !== index))}>Remove alias {index + 1}</button>
          </div>)}
          <button type="button" className={action} disabled={aliases.length >= 50} onClick={() => setAliases([...aliases, { value: "", kind: "name", platform: null }])}>Add alias</button>
          <button className={`${action} ml-2`} disabled={aliases.length === 0}>Review replacement</button>
        </fieldset>
        {confirm && <div className="rounded border p-3" role="group" aria-label="Confirm alias replacement">
          <p>Replace the entire saved alias set with the {aliases.length} aliases shown above?</p>
          <button type="button" className={action} disabled={busy} onClick={() => run(async () => {
            setAliases((await api.replaceAliases(aliases.map(({ value, kind, platform }) => ({ value, kind, platform })))).items);
            setConfirm(false);
          })}>Confirm replacement</button>
          <button type="button" className="ml-3 underline" disabled={busy} onClick={() => setConfirm(false)}>Cancel</button>
        </div>}
      </form>}
    </Card>
  </div>;
}
