"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  Copy,
  KeyRound,
  Loader2,
  Plus,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  Trash2,
  X,
} from "lucide-react";
import { api, ApiError, type BackendApiKey, type BackendApiKeyCreated } from "@/lib/api";
import { useDash } from "@/components/dashboard/Provider";
import { Card, PageHeader, Tag } from "@/components/dashboard/ui";

const MACHINE_KEY_STORAGE = "conflux_demo_machine_key";

function formatDateTime(iso?: string | null): string {
  if (!iso) return "Never";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function ApiKeysSettingsPage() {
  const { user } = useDash();
  const isAdmin = !user?.role || user.role === "bank_admin";

  const [keys, setKeys] = useState<BackendApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create modal state
  const [createOpen, setCreateOpen] = useState(false);
  const [keyName, setKeyName] = useState("");
  const [scopeRead] = useState(true);
  const [scopeOperate, setScopeOperate] = useState(true);
  const [expiryPreset, setExpiryPreset] = useState<"never" | "30d" | "90d" | "365d">("90d");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Newly created key (shown ONCE)
  const [newlyCreated, setNewlyCreated] = useState<BackendApiKeyCreated | null>(null);
  const [copiedToken, setCopiedToken] = useState(false);
  const [copiedCurl, setCopiedCurl] = useState(false);

  // Revoke confirmation modal state
  const [revokeTarget, setRevokeTarget] = useState<BackendApiKey | null>(null);
  const [revoking, setRevoking] = useState(false);

  // Toast feedback
  const [toast, setToast] = useState<string | null>(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => {
      setToast((prev) => (prev === msg ? null : prev));
    }, 3200);
  }, []);

  const loadKeys = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.listKeys();
      setKeys(list);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError("Admin role is required to view or manage machine API keys.");
      } else {
        setError(err instanceof Error ? err.message : "Could not load API keys from the backend.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadKeys();
  }, [loadKeys]);

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyName.trim()) {
      setCreateError("Please enter a descriptive key name.");
      return;
    }
    setCreating(true);
    setCreateError(null);

    const scopes = ["read"];
    if (scopeOperate) scopes.push("operate");

    let expires_at: string | null = null;
    if (expiryPreset !== "never") {
      const days = expiryPreset === "30d" ? 30 : expiryPreset === "90d" ? 90 : 365;
      const d = new Date(Date.now() + days * 24 * 60 * 60 * 1000);
      expires_at = d.toISOString();
    }

    try {
      const created = await api.createKey({
        name: keyName.trim(),
        scopes,
        expires_at,
      });
      setNewlyCreated(created);
      try {
        window.localStorage.setItem(MACHINE_KEY_STORAGE, created.token);
      } catch {}
      setCreateOpen(false);
      setKeyName("");
      showToast(`Created machine key "${created.name}"`);
      await loadKeys();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to generate API key.");
    } finally {
      setCreating(false);
    }
  };

  const handleRevokeConfirm = async () => {
    if (!revokeTarget) return;
    setRevoking(true);
    try {
      const updated = await api.revokeKey(revokeTarget.id);
      setKeys((prev) => prev.map((k) => (k.id === updated.id ? updated : k)));
      if (newlyCreated?.id === updated.id) {
        setNewlyCreated(null);
      }
      showToast(`Revoked key "${revokeTarget.name}" (${revokeTarget.key_prefix}…)`);
      setRevokeTarget(null);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to revoke API key.");
    } finally {
      setRevoking(false);
    }
  };

  const copyRawToken = async (token: string) => {
    try {
      await navigator.clipboard.writeText(token);
      setCopiedToken(true);
      showToast("Raw API key copied to clipboard");
      setTimeout(() => setCopiedToken(false), 2000);
    } catch {}
  };

  const copyCurlExample = async (token: string) => {
    const cmd = `curl -sS "http://127.0.0.1:8000/api/v1/machine/updates?collections=complaints,incidents&limit=20" \\\n  -H "Authorization: Bearer ${token}"`;
    try {
      await navigator.clipboard.writeText(cmd);
      setCopiedCurl(true);
      showToast("cURL command copied to clipboard");
      setTimeout(() => setCopiedCurl(false), 2000);
    } catch {}
  };

  const activeCount = keys.filter((k) => k.status === "active" && !k.revoked_at).length;
  const revokedCount = keys.length - activeCount;

  return (
    <>
      {/* Toast Notification */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.96 }}
            className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 rounded-full bg-navy text-white px-5 py-3 text-sm font-medium shadow-xl border border-white/10"
          >
            <Check className="w-4 h-4 text-flux shrink-0" />
            <span>{toast}</span>
          </motion.div>
        )}
      </AnimatePresence>

      <PageHeader
        title="Machine API Keys"
        sub="Issue scoped cfx_api_ bearer tokens for your bank's internal dashboard, SOC SIEM, or NOC polling worker."
        right={
          <div className="flex flex-wrap items-center gap-2.5">
            <Link
              href="/developers"
              className="inline-flex items-center gap-1.5 rounded-full bg-white border border-navy/10 px-4 py-2 text-xs font-semibold text-navy hover:bg-navy/[0.03] transition-colors"
            >
              Integration docs <ArrowUpRight className="w-3.5 h-3.5 text-flux" />
            </Link>
            <button
              type="button"
              onClick={() => void loadKeys()}
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-full bg-white border border-navy/10 px-3.5 py-2 text-xs font-semibold text-navy hover:bg-navy/[0.03] transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-flux" : ""}`} />
              Refresh
            </button>
            <button
              type="button"
              disabled={!isAdmin}
              onClick={() => {
                setCreateError(null);
                setKeyName("");
                setScopeOperate(true);
                setExpiryPreset("90d");
                setCreateOpen(true);
              }}
              className="inline-flex items-center gap-2 rounded-full bg-flux hover:bg-[#d4560f] text-white px-4 py-2 text-xs font-semibold transition-colors shadow-sm disabled:opacity-50"
            >
              <Plus className="w-4 h-4" />
              Generate new key
            </button>
          </div>
        }
      />

      {!isAdmin && (
        <Card className="p-5 mb-6 border-l-4 !border-l-amber-500 bg-amber-50/50">
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-navy">Admin privileges required</p>
              <p className="text-xs text-navy/65 mt-0.5">
                Only bank administrators (`role: admin`) can generate or revoke machine API keys. Sign in with the demo bank admin account (`Zymic Bank` / `123`) to manage credentials.
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Copy-once newly generated token alert */}
      <AnimatePresence>
        {newlyCreated && (
          <motion.div
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            className="mb-6 rounded-3xl bg-navy text-white p-6 md:p-7 border border-flux/40 shadow-[0_24px_60px_-24px_rgba(20,35,63,0.45)]"
          >
            <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-2xl bg-flux/20 text-flux flex items-center justify-center shrink-0 mt-0.5">
                  <KeyRound className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-mono uppercase tracking-wider text-flux-soft font-semibold">
                      Copy Secret Token Now
                    </span>
                    <span className="rounded-full bg-flux/20 text-flux-soft px-2.5 py-0.5 text-[11px] font-medium">
                      Shown Once Only
                    </span>
                  </div>
                  <h3 className="text-lg font-semibold mt-1">
                    {newlyCreated.name} ({newlyCreated.key_prefix}…)
                  </h3>
                  <p className="text-xs text-white/65 mt-0.5">
                    Save this key in your secret manager now — <strong className="text-white">you will never see this raw token again</strong>. ConfluxHQ only stores its SHA-256 hash.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setNewlyCreated(null)}
                className="text-xs text-white/60 hover:text-white inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-white/10"
              >
                <X className="w-3.5 h-3.5" />
                I&apos;ve saved this key
              </button>
            </div>

            <div className="rounded-2xl bg-black/35 border border-white/15 p-4 flex flex-wrap items-center justify-between gap-3">
              <code className="font-mono text-sm md:text-base text-flux-soft break-all select-all">
                {newlyCreated.token}
              </code>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => void copyRawToken(newlyCreated.token)}
                  className="inline-flex items-center gap-1.5 rounded-full bg-flux hover:bg-[#d4560f] text-white px-4 py-2 text-xs font-semibold transition-colors"
                >
                  {copiedToken ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  {copiedToken ? "Copied token" : "Copy token"}
                </button>
                <button
                  type="button"
                  onClick={() => void copyCurlExample(newlyCreated.token)}
                  className="inline-flex items-center gap-1.5 rounded-full bg-white/10 hover:bg-white/15 text-white px-3.5 py-2 text-xs font-semibold transition-colors"
                >
                  {copiedCurl ? <Check className="w-3.5 h-3.5 text-flux" /> : <Terminal className="w-3.5 h-3.5 text-flux-soft" />}
                  {copiedCurl ? "Copied cURL" : "Copy 5s poll cURL"}
                </button>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-white/55">
              <span>
                Scopes: <strong className="text-white font-mono">{newlyCreated.scopes.join(", ")}</strong> · Bound to local Live Ticker &amp;{" "}
                <Link href="/developers#try-it" className="text-flux-soft underline">
                  /developers interactive tester
                </Link>
              </span>
              <span>Expires: {formatDateTime(newlyCreated.expires_at)}</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Summary Strip */}
      <div className="grid sm:grid-cols-3 gap-4 mb-6">
        <Card className="p-5">
          <p className="text-xs uppercase tracking-wider text-navy/45 font-semibold">Active machine keys</p>
          <p className="text-3xl font-semibold text-navy mt-1">{loading ? "—" : activeCount}</p>
          <p className="text-xs text-navy/55 mt-1">Authorized for `/api/v1/machine/*` polling</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs uppercase tracking-wider text-navy/45 font-semibold">Revoked / expired</p>
          <p className="text-3xl font-semibold text-navy mt-1">{loading ? "—" : revokedCount}</p>
          <p className="text-xs text-navy/55 mt-1">Immediately rejected with HTTP 401</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs uppercase tracking-wider text-navy/45 font-semibold">Recommended cadence</p>
          <p className="text-3xl font-semibold text-flux mt-1">5s cursor</p>
          <p className="text-xs text-navy/55 mt-1">
            Poll <code className="font-mono text-[11px] bg-navy/5 px-1.5 py-0.5 rounded">GET /machine/updates</code>
          </p>
        </Card>
      </div>

      {error && (
        <Card className="p-5 mb-6 border border-red-200 bg-red-50/60 text-red-900">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2.5 text-sm">
              <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
              <span>{error}</span>
            </div>
            <button
              type="button"
              onClick={() => void loadKeys()}
              className="text-xs font-semibold underline shrink-0"
            >
              Retry
            </button>
          </div>
        </Card>
      )}

      {/* Keys Table */}
      <Card className="overflow-hidden">
        <div className="px-6 py-4 border-b border-navy/[0.06] flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold text-navy">Issued API keys</h3>
            <p className="text-xs text-navy/55">
              Raw tokens and SHA-256 hashes are never returned in list responses. Only the key prefix is shown for identification.
            </p>
          </div>
          <Tag>{keys.length} total</Tag>
        </div>

        {loading ? (
          <div className="p-6 space-y-3">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="h-14 rounded-2xl bg-navy/[0.04] animate-pulse flex items-center justify-between px-4"
              >
                <div className="h-4 w-48 rounded bg-navy/10" />
                <div className="h-4 w-28 rounded bg-navy/10" />
              </div>
            ))}
          </div>
        ) : keys.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-12 h-12 rounded-2xl bg-navy/[0.05] text-navy/60 flex items-center justify-center mx-auto mb-3">
              <KeyRound className="w-6 h-6" />
            </div>
            <h4 className="text-base font-semibold text-navy">No machine API keys issued yet</h4>
            <p className="text-sm text-navy/55 max-w-md mx-auto mt-1 mb-5">
              Generate a scoped <code className="font-mono text-xs bg-navy/5 px-1.5 py-0.5 rounded">cfx_api_</code> key so your bank&apos;s internal NOC or customer support portal can poll live complaints and incident spikes.
            </p>
            {isAdmin && (
              <button
                type="button"
                onClick={() => setCreateOpen(true)}
                className="inline-flex items-center gap-2 rounded-full bg-navy text-white px-5 py-2.5 text-xs font-semibold hover:bg-navy-600 transition-colors"
              >
                <Plus className="w-4 h-4 text-flux" />
                Generate your first key
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-navy/[0.06] text-[11px] font-semibold uppercase tracking-wider text-navy/45 bg-navy/[0.015]">
                  <th className="py-3.5 px-6">Name</th>
                  <th className="py-3.5 px-4">Prefix</th>
                  <th className="py-3.5 px-4">Scopes</th>
                  <th className="py-3.5 px-4">Created</th>
                  <th className="py-3.5 px-4">Expires</th>
                  <th className="py-3.5 px-4">Last Used</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-6 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy/[0.06] text-sm">
                {keys.map((k) => {
                  const isRevoked = k.status === "revoked" || Boolean(k.revoked_at);
                  return (
                    <tr
                      key={k.id}
                      className={`transition-colors ${
                        isRevoked ? "bg-navy/[0.015] opacity-65" : "hover:bg-navy/[0.02]"
                      }`}
                    >
                      <td className="py-4 px-6">
                        <div className="font-semibold text-navy flex items-center gap-2">
                          <span>{k.name}</span>
                          {k.demo && (
                            <span className="text-[10px] font-mono uppercase bg-navy/5 text-navy/60 px-2 py-0.5 rounded-full">
                              demo
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] font-mono text-navy/40 mt-0.5">
                          id: {k.id.slice(0, 8)}…
                        </div>
                      </td>
                      <td className="py-4 px-4">
                        <code className="font-mono text-xs bg-navy/[0.05] text-navy px-2.5 py-1 rounded-lg">
                          {k.key_prefix}••••••••
                        </code>
                      </td>
                      <td className="py-4 px-4">
                        <div className="flex flex-wrap gap-1.5">
                          {k.scopes.map((scope) => (
                            <Tag key={scope} tone={scope === "operate" ? "flux" : "navy"}>
                              {scope}
                            </Tag>
                          ))}
                        </div>
                      </td>
                      <td className="py-4 px-4 text-xs text-navy/65 whitespace-nowrap">
                        {formatDateTime(k.created_at)}
                      </td>
                      <td className="py-4 px-4 text-xs text-navy/65 whitespace-nowrap">
                        {formatDateTime(k.expires_at)}
                      </td>
                      <td className="py-4 px-4 text-xs text-navy/65 whitespace-nowrap">
                        {k.last_used_at ? formatDateTime(k.last_used_at) : "Never polled"}
                      </td>
                      <td className="py-4 px-4">
                        {isRevoked ? (
                          <div>
                            <Tag tone="red">revoked</Tag>
                            {k.revoked_at && (
                              <p className="text-[10px] text-navy/45 mt-1">
                                {formatDateTime(k.revoked_at)}
                              </p>
                            )}
                          </div>
                        ) : (
                          <Tag tone="green">active</Tag>
                        )}
                      </td>
                      <td className="py-4 px-6 text-right">
                        {isRevoked ? (
                          <span className="text-xs text-navy/35 font-medium">Revoked</span>
                        ) : (
                          <button
                            type="button"
                            disabled={!isAdmin}
                            onClick={() => setRevokeTarget(k)}
                            className="inline-flex items-center gap-1.5 rounded-full border border-red-200 bg-red-50/70 hover:bg-red-100 text-red-700 px-3 py-1.5 text-xs font-semibold transition-colors disabled:opacity-40"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Generate Key Modal */}
      <AnimatePresence>
        {createOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-navy/60 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={() => !creating && setCreateOpen(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 12 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-lg rounded-3xl bg-cream border border-navy/10 p-6 md:p-7 shadow-2xl"
            >
              <div className="flex items-start justify-between gap-3 mb-5">
                <div>
                  <span className="text-[11px] font-mono uppercase tracking-wider text-flux font-semibold">
                    New Machine Credential
                  </span>
                  <h3 className="text-xl font-semibold text-navy mt-0.5">
                    Generate <code className="font-mono text-base">cfx_api_</code> key
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setCreateOpen(false)}
                  className="p-1.5 rounded-full text-navy/50 hover:text-navy hover:bg-navy/5"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleCreateKey} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-navy/60 mb-1.5">
                    Key Name
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Zymic Core NOC Poller (Prod)"
                    value={keyName}
                    onChange={(e) => setKeyName(e.target.value)}
                    className="w-full rounded-2xl bg-white border border-navy/15 px-4 py-3 text-sm text-navy placeholder:text-navy/35 focus:outline-none focus:border-flux"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-navy/60 mb-2">
                    Permission Scopes
                  </label>
                  <div className="space-y-2.5">
                    <label className="flex items-start gap-3 rounded-2xl bg-white border border-navy/10 p-3.5 cursor-not-allowed">
                      <input
                        type="checkbox"
                        checked={scopeRead}
                        disabled
                        className="mt-1 accent-flux"
                      />
                      <div className="text-xs">
                        <div className="font-semibold text-navy flex items-center gap-2">
                          <code className="font-mono text-flux">read</code>
                          <span className="text-[10px] uppercase tracking-wider bg-navy/5 px-2 py-0.5 rounded-full text-navy/60">
                            Required
                          </span>
                        </div>
                        <p className="text-navy/60 mt-0.5">
                          Pull <code className="font-mono">/machine/updates</code>, <code className="font-mono">/machine/summary</code>, <code className="font-mono">/machine/incidents</code>, <code className="font-mono">/machine/complaints</code>, and connector health.
                        </p>
                      </div>
                    </label>

                    <label className="flex items-start gap-3 rounded-2xl bg-white border border-navy/10 p-3.5 cursor-pointer hover:border-navy/25 transition-colors">
                      <input
                        type="checkbox"
                        checked={scopeOperate}
                        onChange={(e) => setScopeOperate(e.target.checked)}
                        className="mt-1 accent-flux"
                      />
                      <div className="text-xs">
                        <div className="font-semibold text-navy flex items-center gap-2">
                          <code className="font-mono text-flux">operate</code>
                          <span className="text-[10px] uppercase tracking-wider bg-flux/10 px-2 py-0.5 rounded-full text-flux">
                            Optional
                          </span>
                        </div>
                        <p className="text-navy/60 mt-0.5">
                          Trigger AI incident investigations (<code className="font-mono">POST /machine/investigations</code>) and drain queued background jobs (<code className="font-mono">POST /machine/jobs/drain</code>).
                        </p>
                      </div>
                    </label>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-navy/60 mb-1.5">
                    Expiration
                  </label>
                  <div className="grid grid-cols-4 gap-2">
                    {(
                      [
                        { id: "30d", label: "30 days" },
                        { id: "90d", label: "90 days" },
                        { id: "365d", label: "1 year" },
                        { id: "never", label: "No expiry" },
                      ] as const
                    ).map((opt) => (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => setExpiryPreset(opt.id)}
                        className={`rounded-xl py-2.5 px-3 text-xs font-semibold border transition-colors ${
                          expiryPreset === opt.id
                            ? "bg-navy text-white border-navy"
                            : "bg-white text-navy/70 border-navy/10 hover:border-navy/25"
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                {createError && (
                  <p role="alert" className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-xl px-3.5 py-2.5">
                    {createError}
                  </p>
                )}

                <div className="pt-2 flex items-center justify-end gap-2.5">
                  <button
                    type="button"
                    disabled={creating}
                    onClick={() => setCreateOpen(false)}
                    className="rounded-full px-4 py-2.5 text-xs font-semibold text-navy/70 hover:bg-navy/5 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={creating}
                    className="inline-flex items-center gap-2 rounded-full bg-flux hover:bg-[#d4560f] text-white px-5 py-2.5 text-xs font-semibold transition-colors disabled:opacity-50"
                  >
                    {creating ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ShieldCheck className="w-4 h-4" />
                    )}
                    {creating ? "Generating…" : "Generate key"}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Revoke Confirmation Modal */}
      <AnimatePresence>
        {revokeTarget && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-navy/60 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={() => !revoking && setRevokeTarget(null)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 12 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md rounded-3xl bg-cream border border-navy/10 p-6 shadow-2xl"
            >
              <div className="w-11 h-11 rounded-2xl bg-red-100 text-red-700 flex items-center justify-center mb-4">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-semibold text-navy">
                Revoke &ldquo;{revokeTarget.name}&rdquo;?
              </h3>
              <p className="text-sm text-navy/65 mt-1.5 leading-relaxed">
                Any bank poller or SIEM worker using prefix{" "}
                <code className="font-mono text-xs bg-navy/5 px-1.5 py-0.5 rounded">
                  {revokeTarget.key_prefix}…
                </code>{" "}
                will immediately receive <code className="font-mono text-xs">401 Unauthorized</code>. This action is idempotent and cannot be undone.
              </p>

              <div className="mt-6 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  disabled={revoking}
                  onClick={() => setRevokeTarget(null)}
                  className="rounded-full px-4 py-2 text-xs font-semibold text-navy/70 hover:bg-navy/5 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={revoking}
                  onClick={() => void handleRevokeConfirm()}
                  className="inline-flex items-center gap-1.5 rounded-full bg-red-600 hover:bg-red-700 text-white px-5 py-2 text-xs font-semibold transition-colors disabled:opacity-50"
                >
                  {revoking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                  {revoking ? "Revoking…" : "Revoke key"}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
