"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  Code2,
  Copy,
  FileJson,
  KeyRound,
  Layers,
  Loader2,
  Lock,
  Menu,
  Play,
  Radio,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Terminal,
  Webhook,
  X,
  Zap,
} from "lucide-react";
import { api, type BackendHealthStatus } from "@/lib/api";

type CodeLang = "curl" | "python" | "javascript";

interface DocSection {
  id: string;
  number: string;
  title: string;
  kicker: string;
  keywords: string[];
}

const SECTIONS: DocSection[] = [
  {
    id: "quickstart",
    number: "01",
    title: "Quickstart",
    kicker: "ZERO TO FIRST POLL IN 5 MINUTES",
    keywords: ["quickstart", "setup", "first poll", "cfx_api_", "demo", "zymic bank", "onboarding"],
  },
  {
    id: "authentication",
    number: "02",
    title: "Authentication & Scopes",
    kicker: "TWO DISTINCT CREDENTIAL PLANES",
    keywords: ["auth", "jwt", "bearer", "cfx_api_", "read", "operate", "scopes", "login", "bank_admin"],
  },
  {
    id: "polling",
    number: "03",
    title: "Polling the Handoff Feed",
    kicker: "VERSIONED CURSOR STREAM",
    keywords: ["polling", "updates", "cursor", "since", "truncated", "collections", "5s", "ticker", "machine/updates"],
  },
  {
    id: "try-it",
    number: "04",
    title: "Live API Explorer",
    kicker: "INTERACTIVE SANDBOX TESTER",
    keywords: ["try it", "live", "tester", "sandbox", "request", "json", "explorer"],
  },
  {
    id: "endpoints",
    number: "05",
    title: "Endpoint Reference",
    kicker: "MACHINE & INGESTION CONTRACT",
    keywords: [
      "endpoints",
      "machine/summary",
      "machine/incidents",
      "machine/complaints",
      "machine/audit",
      "machine/jobs/drain",
      "machine/investigations",
      "complaints",
      "payment_reference",
      "report_id",
      "api-keys",
    ],
  },
  {
    id: "webhooks",
    number: "06",
    title: "Provider Webhooks",
    kicker: "SIGNED SWITCH & PROVIDER EVIDENCE",
    keywords: [
      "webhooks",
      "forge",
      "x-forge-signature",
      "x-forge-timestamp",
      "x-forge-event",
      "hmac",
      "sha256",
      "provider_event_id",
      "event_id",
    ],
  },
  {
    id: "code-samples",
    number: "07",
    title: "Code Samples",
    kicker: "PRODUCTION POLLING & INTAKE",
    keywords: ["code", "curl", "python", "javascript", "nodejs", "typescript", "sdk", "examples"],
  },
  {
    id: "errors",
    number: "08",
    title: "Rate Limits & Errors",
    kicker: "STATUS CODES & GUARDRAILS",
    keywords: ["errors", "401", "403", "409", "413", "422", "503", "rate limits", "guardrails"],
  },
  {
    id: "changelog",
    number: "09",
    title: "Changelog",
    kicker: "API VERSION HISTORY",
    keywords: ["changelog", "version", "v1", "updates", "releases"],
  },
];

const SAMPLE_CODE: Record<string, Record<CodeLang, string>> = {
  pollLoop: {
    curl: `# 1. Initial pull (omit 'since' cursor to fetch baseline window)
curl -sS "http://127.0.0.1:8000/api/v1/machine/updates?collections=complaints,incidents&limit=20" \\
  -H "Authorization: Bearer cfx_api_your_key_here" \\
  -H "Accept: application/json"

# 2. Subsequent 5-second polls (pass returned 'cursor' as 'since')
curl -sS "http://127.0.0.1:8000/api/v1/machine/updates?since=2026-11-06T10%3A14%3A59%2B00%3A00&collections=complaints,incidents&limit=20" \\
  -H "Authorization: Bearer cfx_api_your_key_here" \\
  -H "Accept: application/json"`,
    python: `import time
import httpx

API_BASE = "http://127.0.0.1:8000/api/v1"
MACHINE_KEY = "cfx_api_your_key_here"

def poll_conflux_handoff():
    cursor: str | None = None
    headers = {"Authorization": f"Bearer {MACHINE_KEY}"}

    with httpx.Client(base_url=API_BASE, headers=headers, timeout=10.0) as client:
        while True:
            params: dict[str, str | int] = {
                "collections": "complaints,incidents",
                "limit": 20,
            }
            if cursor:
                params["since"] = cursor

            res = client.get("/machine/updates", params=params)
            res.raise_for_status()
            payload = res.json()

            for item in payload["items"]:
                print(f"[{item['collection'].upper()}] {item['id']} @ {item['updated_at']}")
                # Upsert item['data'] into your internal bank ops console

            cursor = payload["cursor"]

            # If truncated is True, more items remain under this cursor—poll immediately
            if not payload["truncated"]:
                time.sleep(payload.get("poll_interval_seconds", 5))

if __name__ == "__main__":
    poll_conflux_handoff()`,
    javascript: `const API_BASE = "http://127.0.0.1:8000/api/v1";
const MACHINE_KEY = process.env.CONFLUX_MACHINE_KEY || "cfx_api_your_key_here";

async function startHandoffPoller() {
  let cursor = null;

  while (true) {
    const query = new URLSearchParams({
      collections: "complaints,incidents",
      limit: "20",
    });
    if (cursor) query.set("since", cursor);

    const res = await fetch(\`\${API_BASE}/machine/updates?\${query}\`, {
      headers: {
        Authorization: \`Bearer \${MACHINE_KEY}\`,
        Accept: "application/json",
      },
    });

    if (!res.ok) {
      throw new Error(\`Conflux poll error (\${res.status}): \${await res.text()}\`);
    }

    const body = await res.json();
    for (const item of body.items) {
      console.log(\`[\${item.collection}] id=\${item.id}\`, item.data);
    }

    cursor = body.cursor;
    const waitMs = body.truncated ? 100 : (body.poll_interval_seconds ?? 5) * 1000;
    await new Promise((resolve) => setTimeout(resolve, waitMs));
  }
}

startHandoffPoller();`,
  },
  ingestComplaint: {
    curl: `curl -X POST "http://127.0.0.1:8000/api/v1/complaints" \\
  -H "Authorization: Bearer <BANK_OPERATOR_JWT>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "channel": "in_app",
    "text": "I was debited NGN 45,000 via USSD transfer ref TRF-90812231 but beneficiary has not received it.",
    "customer_ref": "CUST-NG-88412",
    "region": "Lagos",
    "language": "en"
  }'`,
    python: `import httpx

response = httpx.post(
    "http://127.0.0.1:8000/api/v1/complaints",
    headers={"Authorization": f"Bearer {operator_jwt}"},
    json={
        "channel": "in_app",
        "text": "I was debited NGN 45,000 via USSD transfer ref TRF-90812231 but beneficiary has not received it.",
        "customer_ref": "CUST-NG-88412",
        "region": "Lagos",
        "language": "en",
    },
)
print(response.status_code, response.json())`,
    javascript: `const res = await fetch("http://127.0.0.1:8000/api/v1/complaints", {
  method: "POST",
  headers: {
    Authorization: \`Bearer \${operatorJwt}\`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    channel: "in_app",
    text: "I was debited NGN 45,000 via USSD transfer ref TRF-90812231 but beneficiary has not received it.",
    customer_ref: "CUST-NG-88412",
    region: "Lagos",
    language: "en",
  }),
});
const complaint = await res.json();`,
  },
  operateActions: {
    curl: `# Request bounded AI + evidence investigation on an incident (requires 'operate' scope)
curl -X POST "http://127.0.0.1:8000/api/v1/machine/investigations" \\
  -H "Authorization: Bearer cfx_api_your_operate_key" \\
  -H "Content-Type: application/json" \\
  -d '{"incident_id": "2c8d45a1-7e10-4b9c-9a21-55f8e1a9d001"}'

# Drain pending classification & outbox worker jobs (requires 'operate' scope)
curl -X POST "http://127.0.0.1:8000/api/v1/machine/jobs/drain" \\
  -H "Authorization: Bearer cfx_api_your_operate_key" \\
  -H "Content-Type: application/json" \\
  -d '{"limit": 100}'`,
    python: `import httpx

headers = {"Authorization": "Bearer cfx_api_your_operate_key"}

# 1. Trigger investigation run (202 Accepted)
inv = httpx.post(
    "http://127.0.0.1:8000/api/v1/machine/investigations",
    headers=headers,
    json={"incident_id": "2c8d45a1-7e10-4b9c-9a21-55f8e1a9d001"},
)
print("Investigation run:", inv.json())

# 2. Drain worker queue
drain = httpx.post(
    "http://127.0.0.1:8000/api/v1/machine/jobs/drain",
    headers=headers,
    json={"limit": 100},
)
print("Queue drained:", drain.json())`,
    javascript: `const headers = {
  Authorization: "Bearer cfx_api_your_operate_key",
  "Content-Type": "application/json",
};

// 1. Trigger incident investigation
const runRes = await fetch("http://127.0.0.1:8000/api/v1/machine/investigations", {
  method: "POST",
  headers,
  body: JSON.stringify({ incident_id: "2c8d45a1-7e10-4b9c-9a21-55f8e1a9d001" }),
});

// 2. Drain worker queue
const drainRes = await fetch("http://127.0.0.1:8000/api/v1/machine/jobs/drain", {
  method: "POST",
  headers,
  body: JSON.stringify({ limit: 100 }),
});`,
  },
};

const TESTER_PRESETS = [
  {
    label: "GET /machine/updates (5s Handoff Feed)",
    method: "GET" as const,
    endpoint: "/api/v1/machine/updates?collections=complaints,incidents&limit=5",
    scope: "read",
    body: "",
  },
  {
    label: "GET /machine/summary (Analytics Summary)",
    method: "GET" as const,
    endpoint: "/api/v1/machine/summary",
    scope: "read",
    body: "",
  },
  {
    label: "GET /machine/incidents (Ranked Incidents)",
    method: "GET" as const,
    endpoint: "/api/v1/machine/incidents?limit=10",
    scope: "read",
    body: "",
  },
  {
    label: "GET /machine/complaints (Complaint Feed)",
    method: "GET" as const,
    endpoint: "/api/v1/machine/complaints?limit=5",
    scope: "read",
    body: "",
  },
  {
    label: "GET /machine/health/connectors (Posture)",
    method: "GET" as const,
    endpoint: "/api/v1/machine/health/connectors",
    scope: "read",
    body: "",
  },
  {
    label: "GET /machine/audit (Bank Audit Log)",
    method: "GET" as const,
    endpoint: "/api/v1/machine/audit?limit=10",
    scope: "read",
    body: "",
  },
  {
    label: "POST /machine/jobs/drain (Drain Queue)",
    method: "POST" as const,
    endpoint: "/api/v1/machine/jobs/drain",
    scope: "operate",
    body: JSON.stringify({ limit: 50 }, null, 2),
  },
  {
    label: "GET /health (Public Liveness)",
    method: "GET" as const,
    endpoint: "/api/v1/health",
    scope: "public",
    body: "",
  },
];

export default function DevelopersPage() {
  const [activeSection, setActiveSection] = useState("quickstart");
  const [codeTab, setCodeTab] = useState<CodeLang>("curl");
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [health, setHealth] = useState<BackendHealthStatus | null>(null);
  const [healthError, setHealthError] = useState(false);

  // Interactive Tester state
  const [testerKey, setTesterKey] = useState("");
  const [selectedPresetIdx, setSelectedPresetIdx] = useState(0);
  const [customEndpoint, setCustomEndpoint] = useState(TESTER_PRESETS[0].endpoint);
  const [customMethod, setCustomMethod] = useState<"GET" | "POST">(TESTER_PRESETS[0].method);
  const [customBody, setCustomBody] = useState(TESTER_PRESETS[0].body);
  const [testerLoading, setTesterLoading] = useState(false);
  const [provisioningKey, setProvisioningKey] = useState(false);
  const [testerResult, setTesterResult] = useState<{
    status: number;
    ok: boolean;
    durationMs: number;
    data: unknown;
  } | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => {
      setToast((prev) => (prev === msg ? null : prev));
    }, 3200);
  };

  const copyText = async (text: string, label = "Copied to clipboard") => {
    try {
      await navigator.clipboard.writeText(text);
      showToast(label);
    } catch {
      showToast("Copy failed — select and copy manually");
    }
  };

  // Load saved machine key if available & check backend health
  useEffect(() => {
    if (typeof window !== "undefined") {
      const savedKey = localStorage.getItem("conflux_last_machine_key");
      if (savedKey) setTesterKey(savedKey);
    }

    let mounted = true;
    const pollHealth = () => {
      api
        .checkHealth()
        .then((res) => {
          if (mounted) {
            setHealth(res);
            setHealthError(false);
          }
        })
        .catch(() => {
          if (mounted) setHealthError(true);
        });
    };
    pollHealth();
    const timer = setInterval(pollHealth, 15000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  // Command-K keyboard shortcut
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      } else if (e.key === "Escape") {
        setSearchOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // Scroll spy for sidebar
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: "-15% 0px -70% 0px" }
    );
    for (const section of SECTIONS) {
      const el = document.getElementById(section.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, []);

  const filteredSections = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return SECTIONS;
    return SECTIONS.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        s.kicker.toLowerCase().includes(q) ||
        s.keywords.some((k) => k.toLowerCase().includes(q))
    );
  }, [searchQuery]);

  const handlePresetChange = (idx: number) => {
    setSelectedPresetIdx(idx);
    const p = TESTER_PRESETS[idx];
    setCustomEndpoint(p.endpoint);
    setCustomMethod(p.method);
    setCustomBody(p.body);
  };

  const handleProvisionSandboxKey = async () => {
    setProvisioningKey(true);
    try {
      if (!api.hasStoredToken()) {
        await api.enterDemo();
      }
      const created = await api.createKey({
        name: `docs-explorer-${Math.floor(1000 + Math.random() * 9000)}`,
        scopes: ["read", "operate"],
        demo: true,
      });
      setTesterKey(created.token);
      showToast(`Generated live key ${created.key_prefix}… (saved in tester)`);
    } catch (err) {
      showToast(
        err instanceof Error
          ? err.message
          : "Could not provision key. Ensure backend is running on :8000."
      );
    } finally {
      setProvisioningKey(false);
    }
  };

  const handleRunTest = async () => {
    setTesterLoading(true);
    try {
      let parsedBody: unknown = undefined;
      if (customMethod === "POST" && customBody.trim()) {
        try {
          parsedBody = JSON.parse(customBody);
        } catch {
          showToast("Invalid JSON body");
          setTesterLoading(false);
          return;
        }
      }
      const res = await api.machineRequest(testerKey, customEndpoint, customMethod, parsedBody);
      setTesterResult(res);
    } catch (err) {
      setTesterResult({
        status: 0,
        ok: false,
        durationMs: 0,
        data: {
          error: "Network error — verify that the FastAPI backend is running at http://127.0.0.1:8000",
          detail: err instanceof Error ? err.message : String(err),
        },
      });
    } finally {
      setTesterLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f0f1eb] text-[#14233f] selection:bg-[#e8651a] selection:text-white">
      {/* Toast Notification */}
      {toast && (
        <div
          role="status"
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 rounded-full bg-[#14233f] text-[#f0f1eb] px-5 py-3 text-xs font-medium shadow-2xl border border-white/10"
        >
          <span className="h-2 w-2 rounded-full bg-[#e8651a]" />
          {toast}
        </div>
      )}

      {/* Command-K Search Modal */}
      {searchOpen && (
        <div
          className="fixed inset-0 z-50 bg-[#14233f]/60 backdrop-blur-sm flex items-start justify-center pt-24 px-4"
          onClick={() => setSearchOpen(false)}
        >
          <div
            className="w-full max-w-xl rounded-3xl bg-[#f0f1eb] border border-[#14233f]/15 shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 px-5 py-4 border-b border-[#14233f]/10 bg-white/60">
              <Search className="w-4 h-4 text-[#e8651a]" />
              <input
                type="text"
                autoFocus
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search endpoints, scopes, cursors, headers (e.g. cfx_api_, payment_reference, 422)…"
                className="w-full bg-transparent text-sm text-[#14233f] placeholder:text-[#485570]/60 outline-none"
              />
              <button
                type="button"
                onClick={() => setSearchOpen(false)}
                className="text-[11px] font-mono px-2 py-1 rounded-md bg-[#14233f]/5 text-[#485570]"
              >
                ESC
              </button>
            </div>
            <div className="max-h-96 overflow-y-auto p-3 space-y-1">
              {filteredSections.length === 0 ? (
                <p className="py-10 text-center text-sm text-[#485570]">
                  No matching documentation sections for &ldquo;{searchQuery}&rdquo;.
                </p>
              ) : (
                filteredSections.map((sec) => (
                  <a
                    key={sec.id}
                    href={`#${sec.id}`}
                    onClick={() => {
                      setSearchOpen(false);
                      setSearchQuery("");
                    }}
                    className="flex items-center justify-between gap-4 px-4 py-3 rounded-2xl hover:bg-[#14233f] hover:text-[#f0f1eb] group transition-colors"
                  >
                    <div>
                      <p className="text-[10px] font-semibold tracking-[0.14em] text-[#ad4814] group-hover:text-[#f4a261]">
                        {sec.number} · {sec.kicker}
                      </p>
                      <p className="text-sm font-medium mt-0.5">{sec.title}</p>
                    </div>
                    <ArrowRight className="w-4 h-4 opacity-40 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" />
                  </a>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Top Sticky Navbar (in sync with Landing Page) */}
      <header className="sticky top-0 z-40 bg-[#f0f1eb]/90 backdrop-blur-md border-b border-[#14233f]/10 px-6 lg:px-10 py-4">
        <div className="max-w-[1380px] mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2.5 text-[#14233f] font-semibold text-xl tracking-[-0.8px]">
              <Image
                src="/conflux-logo-full.jpg"
                alt="Conflux HQ"
                width={30}
                height={30}
                className="rounded-lg object-contain shadow-xs"
                priority
              />
              <span>
                conflux<span className="text-[9px] text-[#e8651a] align-super ml-1 tracking-[0.04em]">HQ</span>
              </span>
            </Link>
            <span className="hidden sm:inline-flex items-center gap-1.5 text-[11px] font-semibold tracking-[0.12em] uppercase text-[#ad4814] bg-[#e8651a]/10 px-3 py-1 rounded-full">
              <Code2 className="w-3.5 h-3.5" />
              Developers &amp; API
            </span>
          </div>

          <div className="flex items-center gap-3">
            {/* Live Health Status Pill */}
            <div
              title={
                health
                  ? `Backend: ${health.status} · DB: ${health.database || "connected"} (${health.environment || "dev"})`
                  : "Checking /api/v1/health…"
              }
              className="hidden md:inline-flex items-center gap-2 rounded-full bg-white/80 border border-[#14233f]/10 px-3.5 py-1.5 text-xs text-[#485570]"
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  healthError
                    ? "bg-amber-500"
                    : health?.status === "ok"
                    ? "bg-emerald-600 animate-pulse"
                    : "bg-slate-400"
                }`}
              />
              <span className="font-medium text-[#14233f]">
                {healthError
                  ? "Backend Offline"
                  : health?.status === "ok"
                  ? "API Operational"
                  : "Checking API…"}
              </span>
            </div>

            {/* Command-K Search Button */}
            <button
              type="button"
              onClick={() => setSearchOpen(true)}
              className="inline-flex items-center gap-3 rounded-full bg-white/90 hover:bg-white border border-[#14233f]/15 px-3.5 py-1.5 text-xs text-[#485570] transition-colors"
            >
              <Search className="w-3.5 h-3.5 text-[#e8651a]" />
              <span className="hidden sm:inline">Search docs…</span>
              <kbd className="rounded bg-[#14233f]/5 px-1.5 py-0.5 text-[10px] font-mono text-[#14233f]">
                ⌘K
              </kbd>
            </button>

            <a
              href="/docs"
              target="_blank"
              rel="noreferrer"
              className="hidden lg:inline-flex items-center gap-1.5 text-xs font-medium text-[#14233f] hover:text-[#b64c12] px-2.5 py-1.5 transition-colors"
            >
              OpenAPI /docs <ArrowUpRight className="w-3.5 h-3.5" />
            </a>

            <Link
              href="/dashboard/settings/keys"
              className="hidden sm:inline-flex items-center gap-2 rounded-full bg-[#e8651a] hover:bg-[#f4a261] text-[#14233f] font-semibold text-xs px-4 py-2.5 transition-colors"
            >
              <KeyRound className="w-3.5 h-3.5" />
              API Keys
            </Link>

            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 rounded-full bg-[#14233f] hover:bg-[#1d3358] text-[#f0f1eb] text-xs px-4 py-2.5 transition-colors"
            >
              Workspace <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>

            <button
              type="button"
              onClick={() => setMobileNavOpen(!mobileNavOpen)}
              className="lg:hidden p-2 rounded-full border border-[#14233f]/15 text-[#14233f]"
              aria-label="Toggle documentation menu"
            >
              {mobileNavOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Mobile Drawer */}
        {mobileNavOpen && (
          <nav className="lg:hidden mt-4 pt-4 border-t border-[#14233f]/10 grid grid-cols-2 gap-2">
            {SECTIONS.map((s) => (
              <a
                key={s.id}
                href={`#${s.id}`}
                onClick={() => setMobileNavOpen(false)}
                className="px-3 py-2 rounded-xl text-xs font-medium bg-white/60 text-[#14233f] hover:bg-[#14233f] hover:text-white"
              >
                <span className="text-[#e8651a] mr-1.5 font-mono">{s.number}</span>
                {s.title}
              </a>
            ))}
          </nav>
        )}
      </header>

      {/* Hero Banner (Synchronized with CastLanding Editorial Aesthetic) */}
      <section className="pt-16 pb-20 px-6 lg:px-10 border-b border-[#14233f]/10">
        <div className="max-w-[1380px] mx-auto grid lg:grid-cols-12 gap-12 items-end">
          <div className="lg:col-span-8">
            <p className="flex items-center gap-2 text-[10px] font-semibold tracking-[0.14em] uppercase text-[#ad4814] mb-5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#e8651a]" />
              BANK INTEGRATION &amp; MACHINE HANDOFF API
            </p>
            <h1
              className="text-[#14233f] font-normal leading-[1.03] tracking-[-0.06em]"
              style={{ fontSize: "clamp(40px, 6vw, 82px)" }}
            >
              Our UI proves the signal.
              <br />
              <span className="text-[#485570]">Your bank polls it via API.</span>
            </h1>
            <p className="mt-6 text-[#3d4a66] text-base md:text-lg leading-[1.75] max-w-2xl">
              ConfluxHQ ingests customer complaints across channels, correlates payment switch records,
              and detects statistical incident spikes. Provision a bank-scoped{" "}
              <code className="px-2 py-0.5 rounded-md bg-[#14233f]/8 font-mono text-sm text-[#14233f]">
                cfx_api_
              </code>{" "}
              credential and poll{" "}
              <code className="px-2 py-0.5 rounded-md bg-[#14233f]/8 font-mono text-sm text-[#14233f]">
                GET /api/v1/machine/updates
              </code>{" "}
              every 5 seconds to stream structured signal directly into your internal bank console.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <a
                href="#try-it"
                className="inline-flex items-center gap-3 rounded-full bg-[#e8651a] hover:bg-[#f4a261] text-[#14233f] font-semibold text-xs px-6 py-3.5 transition-all"
              >
                Launch Live API Tester <Play className="w-3.5 h-3.5 fill-current" />
              </a>
              <Link
                href="/dashboard/settings/keys"
                className="inline-flex items-center gap-3 rounded-full bg-[#14233f] hover:bg-[#1d3358] text-[#f0f1eb] text-xs px-6 py-3.5 transition-all"
              >
                Generate Machine Key <KeyRound className="w-3.5 h-3.5" />
              </Link>
              <a
                href="/openapi.json"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-full border border-[#14233f]/20 hover:border-[#14233f] px-5 py-3 text-xs font-medium text-[#14233f] transition-colors"
              >
                <FileJson className="w-3.5 h-3.5 text-[#e8651a]" />
                openapi.json
              </a>
            </div>
          </div>

          <div className="lg:col-span-4">
            <div className="rounded-3xl bg-[#14233f] text-[#f0f1eb] p-6 border border-white/10 shadow-xl">
              <div className="flex items-center justify-between text-[10px] tracking-[0.12em] uppercase text-[#f4a261] mb-4">
                <span>BASE CONFIGURATION</span>
                <span>API v1</span>
              </div>
              <div className="space-y-3 text-xs font-mono">
                <div className="p-3 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-between gap-2">
                  <div>
                    <span className="text-white/45 block text-[10px]">BASE URL</span>
                    <span className="text-[#f0f1eb]">http://127.0.0.1:8000/api/v1</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => copyText("http://127.0.0.1:8000/api/v1", "Copied Base URL")}
                    className="p-1.5 rounded-lg hover:bg-white/10 text-white/60 hover:text-white"
                    aria-label="Copy Base URL"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="p-3 rounded-2xl bg-white/5 border border-white/10">
                  <span className="text-white/45 block text-[10px]">MACHINE AUTH HEADER</span>
                  <span className="text-[#f4a261]">Authorization: Bearer cfx_api_…</span>
                </div>
                <div className="p-3 rounded-2xl bg-white/5 border border-white/10">
                  <span className="text-white/45 block text-[10px]">RECOMMENDED POLL CADENCE</span>
                  <span className="text-emerald-300">Every 5s · Cursor-based delta</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Main Docs Layout: Left Sticky Sidebar + Right Content Sheets */}
      <div className="max-w-[1380px] mx-auto px-6 lg:px-10 py-14 grid lg:grid-cols-12 gap-12 items-start">
        {/* Left Sidebar */}
        <aside className="hidden lg:block lg:col-span-3 sticky top-24 space-y-6">
          <div className="rounded-3xl bg-[#e7e9e1] border border-[#14233f]/10 p-5">
            <p className="text-[10px] font-semibold tracking-[0.14em] uppercase text-[#ad4814] mb-4">
              DOCUMENTATION INDEX
            </p>
            <nav aria-label="Documentation sections" className="space-y-1">
              {SECTIONS.map((sec) => {
                const isActive = activeSection === sec.id;
                return (
                  <a
                    key={sec.id}
                    href={`#${sec.id}`}
                    className={`flex items-center gap-3 px-3.5 py-2.5 rounded-2xl text-xs transition-all ${
                      isActive
                        ? "bg-[#14233f] text-[#f0f1eb] font-semibold shadow-sm"
                        : "text-[#485570] hover:text-[#14233f] hover:bg-[#14233f]/5"
                    }`}
                  >
                    <span
                      className={`font-mono text-[10px] ${
                        isActive ? "text-[#f4a261]" : "text-[#ad4814]"
                      }`}
                    >
                      {sec.number}
                    </span>
                    <span className="truncate">{sec.title}</span>
                  </a>
                );
              })}
            </nav>

            <div className="mt-6 pt-5 border-t border-[#14233f]/10 space-y-2">
              <a
                href="/docs"
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#14233f] hover:bg-[#14233f]/5"
              >
                <span>Swagger UI (/docs)</span>
                <ArrowUpRight className="w-3.5 h-3.5 text-[#e8651a]" />
              </a>
              <a
                href="/openapi.json"
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#14233f] hover:bg-[#14233f]/5"
              >
                <span>Raw OpenAPI Schema</span>
                <FileJson className="w-3.5 h-3.5 text-[#e8651a]" />
              </a>
            </div>
          </div>

          <div className="rounded-3xl bg-[#eadfcf] border border-[#14233f]/10 p-5">
            <p className="text-[10px] font-semibold tracking-[0.14em] uppercase text-[#ad4814]">
              DEMO CREDENTIALS
            </p>
            <p className="text-xs text-[#485570] mt-2 leading-relaxed">
              Sign in as the demo bank administrator to provision and revoke machine keys:
            </p>
            <div className="mt-3 space-y-1.5 text-xs font-mono bg-white/60 rounded-2xl p-3 border border-[#14233f]/10">
              <div className="flex justify-between">
                <span className="text-[#697388]">username:</span>
                <span className="font-semibold text-[#14233f]">Zymic Bank</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#697388]">password:</span>
                <span className="font-semibold text-[#14233f]">123</span>
              </div>
            </div>
          </div>
        </aside>

        {/* Main Content Column */}
        <main className="lg:col-span-9 space-y-12">
          {/* 01. QUICKSTART */}
          <section
            id="quickstart"
            className="scroll-mt-28 rounded-t-[36px] rounded-b-3xl bg-white/75 border border-[#14233f]/12 p-8 md:p-10 shadow-xs"
          >
            <p className="text-[10px] font-semibold tracking-[0.14em] uppercase text-[#ad4814] mb-3">
              01 · ZERO TO FIRST POLL IN &lt; 5 MINUTES
            </p>
            <h2 className="text-3xl md:text-4xl font-normal tracking-[-0.045em] text-[#14233f]">
              Quickstart: Connect your bank dashboard
            </h2>
            <p className="mt-3 text-sm md:text-base text-[#485570] leading-relaxed max-w-2xl">
              ConfluxHQ separates human governance from machine consumption. Your bank&apos;s developers
              never need to embed our UI—they poll our versioned handoff feed using a tenant-scoped
              machine API key.
            </p>

            <div className="grid md:grid-cols-3 gap-5 mt-8">
              {[
                {
                  step: "STEP 01",
                  title: "Authenticate as Bank Admin",
                  desc: "Sign in at /login with demo tenant credentials (Zymic Bank / 123) or via POST /api/v1/auth/login to obtain an admin JWT.",
                  href: "/login",
                  cta: "Open Sign In",
                },
                {
                  step: "STEP 02",
                  title: "Provision a cfx_api_ Key",
                  desc: "Visit Settings → API Keys and generate a key with 'read' (and optional 'operate') scope. Copy the raw token once.",
                  href: "/dashboard/settings/keys",
                  cta: "Manage API Keys",
                },
                {
                  step: "STEP 03",
                  title: "Poll /machine/updates (5s)",
                  desc: "Call GET /api/v1/machine/updates?collections=complaints,incidents&limit=20 every 5 seconds, advancing the 'since' cursor.",
                  href: "#try-it",
                  cta: "Try Live Poll",
                },
              ].map((item) => (
                <div
                  key={item.step}
                  className="rounded-2xl bg-[#f0f1eb] border border-[#14233f]/12 p-6 flex flex-col justify-between"
                >
                  <div>
                    <span className="text-[10px] font-mono font-semibold tracking-wider text-[#ad4814]">
                      {item.step}
                    </span>
                    <h3 className="text-lg font-medium text-[#14233f] mt-2 tracking-[-0.02em]">
                      {item.title}
                    </h3>
                    <p className="text-xs text-[#485570] leading-relaxed mt-2">{item.desc}</p>
                  </div>
                  <Link
                    href={item.href}
                    className="mt-5 inline-flex items-center gap-1.5 text-xs font-semibold text-[#14233f] hover:text-[#e8651a]"
                  >
                    {item.cta} <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              ))}
            </div>
          </section>

          {/* 02. AUTHENTICATION & SCOPES */}
          <section
            id="authentication"
            className="scroll-mt-28 rounded-t-[36px] rounded-b-3xl bg-[#14233f] text-[#b8c1d0] border border-white/10 p-8 md:p-10 shadow-xl"
          >
            <p className="text-[10px] font-semibold tracking-[0.14em] uppercase text-[#f4a261] mb-3">
              02 · TWO DISTINCT CREDENTIAL PLANES
            </p>
            <h2 className="text-3xl md:text-4xl font-normal tracking-[-0.045em] text-[#f0f1eb]">
              Authentication &amp; Key Scopes
            </h2>
            <p className="mt-3 text-sm md:text-base text-[#b8c1d0] leading-relaxed max-w-2xl">
              ConfluxHQ enforces strict privilege separation between interactive operator sessions and
              automated bank-to-bank machine integrations.
            </p>

            <div className="grid md:grid-cols-2 gap-6 mt-8">
              <div className="rounded-2xl bg-white/[0.05] border border-white/10 p-6">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold uppercase tracking-wider text-[#f4a261]">
                    1. Operator JWT (Human UI)
                  </span>
                  <Lock className="w-4 h-4 text-[#f4a261]" />
                </div>
                <p className="text-xs leading-relaxed text-[#b8c1d0]">
                  Issued by <code className="text-white font-mono">POST /api/v1/auth/login</code> (stored in{" "}
                  <code className="text-white font-mono">localStorage.conflux_demo_token</code>). Used by{" "}
                  <code className="text-white font-mono">bank_admin</code>,{" "}
                  <code className="text-white font-mono">agent</code>,{" "}
                  <code className="text-white font-mono">it</code>, and{" "}
                  <code className="text-white font-mono">manager</code> roles to review drafts, approve
                  reversals, and provision API keys.
                </p>
                <pre className="mt-4 p-3 rounded-xl bg-black/30 text-[11px] font-mono text-[#f0f1eb] overflow-x-auto">
{`POST /api/v1/auth/login
{"username": "Zymic Bank", "password": "123"}`}
                </pre>
              </div>

              <div className="rounded-2xl bg-white/[0.05] border border-white/10 p-6">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold uppercase tracking-wider text-emerald-300">
                    2. Machine Key (cfx_api_…)
                  </span>
                  <KeyRound className="w-4 h-4 text-emerald-300" />
                </div>
                <p className="text-xs leading-relaxed text-[#b8c1d0]">
                  Provisioned by <code className="text-white font-mono">bank_admin</code> at{" "}
                  <code className="text-white font-mono">POST /api/v1/api-keys</code>. Shown once at
                  creation, stored as a SHA-256 hash server-side. Scoped strictly to{" "}
                  <code className="text-white font-mono">/api/v1/machine/*</code> routes. Never grants
                  admin or key-creation privileges.
                </p>
                <pre className="mt-4 p-3 rounded-xl bg-black/30 text-[11px] font-mono text-emerald-300 overflow-x-auto">
{`Authorization: Bearer cfx_api_7f9a2b...`}
                </pre>
              </div>
            </div>

            {/* Scope Matrix */}
            <div className="mt-8 rounded-2xl bg-white/[0.04] border border-white/10 overflow-hidden">
              <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
                <h3 className="text-sm font-medium text-[#f0f1eb]">Machine Key Scopes</h3>
                <span className="text-[11px] font-mono text-[#f4a261]">ALLOWED_API_SCOPES</span>
              </div>
              <div className="divide-y divide-white/10 text-xs">
                <div className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <span className="inline-block font-mono font-semibold text-emerald-300 bg-emerald-500/15 px-2.5 py-1 rounded-md">
                      read
                    </span>
                    <span className="ml-2 text-[11px] uppercase tracking-wider text-white/50">
                      Required on all keys
                    </span>
                    <p className="mt-2 text-[#b8c1d0]">
                      Pulls bank-scoped signal: <code className="text-white font-mono">GET /machine/updates</code>,{" "}
                      <code className="text-white font-mono">/machine/summary</code>,{" "}
                      <code className="text-white font-mono">/machine/incidents</code>,{" "}
                      <code className="text-white font-mono">/machine/complaints</code>,{" "}
                      <code className="text-white font-mono">/machine/audit</code>, and{" "}
                      <code className="text-white font-mono">/machine/health/connectors</code>.
                    </p>
                  </div>
                </div>
                <div className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <span className="inline-block font-mono font-semibold text-[#f4a261] bg-[#e8651a]/20 px-2.5 py-1 rounded-md">
                      operate
                    </span>
                    <span className="ml-2 text-[11px] uppercase tracking-wider text-white/50">
                      Optional elevated scope
                    </span>
                    <p className="mt-2 text-[#b8c1d0]">
                      Enables explicit, audited operational triggers:{" "}
                      <code className="text-white font-mono">POST /machine/jobs/drain</code> (drain pending
                      classification/outbox worker jobs) and{" "}
                      <code className="text-white font-mono">POST /machine/investigations</code> (request
                      bounded AI root-cause investigation on an incident).
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* 03. POLLING THE HANDOFF FEED */}
          <section
            id="polling"
            className="scroll-mt-28 rounded-t-[36px] rounded-b-3xl bg-[#e7e9e1] border border-[#14233f]/12 p-8 md:p-10"
          >
            <p className="text-[10px] font-semibold tracking-[0.14em] uppercase text-[#ad4814] mb-3">
              03 · VERSIONED CURSOR STREAM
            </p>
            <h2 className="text-3xl md:text-4xl font-normal tracking-[-0.045em] text-[#14233f]">
              Polling <code className="font-mono text-2xl md:text-3xl">GET /api/v1/machine/updates</code>
            </h2>
            <p className="mt-3 text-sm md:text-base text-[#485570] leading-relaxed max-w-2xl">
              Banks mirror Conflux signal into their internal dashboards by polling{" "}
              <code className="font-mono text-[#14233f] bg-white/70 px-1.5 py-0.5 rounded">
                /api/v1/machine/updates
              </code>{" "}
              every <strong>5 seconds</strong>. The endpoint returns only records created or updated
              after your <code className="font-mono text-[#14233f]">since</code> cursor.
            </p>

            <div className="grid md:grid-cols-3 gap-4 mt-7">
              <div className="rounded-2xl bg-white/80 p-5 border border-[#14233f]/10">
                <p className="text-[10px] font-semibold tracking-wider uppercase text-[#ad4814]">
                  CURSOR MECHANICS
                </p>
                <p className="text-xs text-[#485570] mt-2 leading-relaxed">
                  Omit <code className="font-mono text-[#14233f]">since</code> on your first call. Store
                  the returned ISO-8601 UTC <code className="font-mono text-[#14233f]">cursor</code> and
                  pass it as <code className="font-mono text-[#14233f]">?since=&lt;cursor&gt;</code> on the
                  next poll. An empty <code className="font-mono text-[#14233f]">items: []</code> list
                  means nothing changed.
                </p>
              </div>
              <div className="rounded-2xl bg-white/80 p-5 border border-[#14233f]/10">
                <p className="text-[10px] font-semibold tracking-wider uppercase text-[#ad4814]">
                  TRUNCATED FLAG
                </p>
                <p className="text-xs text-[#485570] mt-2 leading-relaxed">
                  Results are ordered by <code className="font-mono text-[#14233f]">(updated_at, id)</code>{" "}
                  and capped at <code className="font-mono text-[#14233f]">limit</code> (1–500). When{" "}
                  <code className="font-mono text-[#14233f]">truncated: true</code>, poll immediately with
                  the new cursor before waiting 5 seconds.
                </p>
              </div>
              <div className="rounded-2xl bg-white/80 p-5 border border-[#14233f]/10">
                <p className="text-[10px] font-semibold tracking-wider uppercase text-[#ad4814]">
                  COLLECTIONS FILTER
                </p>
                <p className="text-xs text-[#485570] mt-2 leading-relaxed">
                  For a 5s live ticker, pass{" "}
                  <code className="font-mono text-[#14233f]">
                    collections=complaints,incidents&amp;limit=20
                  </code>
                  . Other collections (<code className="font-mono">drafts,actions,investigations,audit</code>)
                  can be polled less frequently.
                </p>
              </div>
            </div>

            <div className="mt-6 rounded-2xl bg-[#14233f] text-[#f0f1eb] p-6 overflow-x-auto">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[11px] font-mono text-[#f4a261]">
                  200 OK · GET /api/v1/machine/updates?collections=complaints,incidents&amp;limit=20
                </span>
                <button
                  type="button"
                  onClick={() =>
                    copyText(
                      JSON.stringify(
                        {
                          bank_id: "b0419e61-2d8a-4e11-94c8-001122334455",
                          since: "2026-11-06T10:00:00+00:00",
                          cursor: "2026-11-06T10:14:59+00:00",
                          count: 2,
                          truncated: false,
                          collections: ["complaints", "incidents"],
                          poll_interval_seconds: 5,
                          items: [
                            {
                              collection: "complaints",
                              id: "8a91c340-1b2e-4f88-9102-abcdef123456",
                              updated_at: "2026-11-06T10:14:12+00:00",
                              data: {
                                id: "8a91c340-1b2e-4f88-9102-abcdef123456",
                                channel: "in_app",
                                issue_type: "failed_transfer",
                                severity: "high",
                                text: "Debited ₦50,000 on USSD, recipient not credited.",
                                summary: "Failed USSD transfer debit without beneficiary credit",
                                region: "Lagos",
                                occurred_at: "2026-11-06T10:14:00+00:00",
                                incident_id: "2c8d45a1-7e10-4b9c-9a21-55f8e1a9d001",
                              },
                            },
                            {
                              collection: "incidents",
                              id: "2c8d45a1-7e10-4b9c-9a21-55f8e1a9d001",
                              updated_at: "2026-11-06T10:14:59+00:00",
                              data: {
                                id: "2c8d45a1-7e10-4b9c-9a21-55f8e1a9d001",
                                issue_type: "failed_transfer",
                                status: "open",
                                complaint_count: 30,
                                detected_at: "2026-11-06T10:14:59+00:00",
                              },
                            },
                          ],
                        },
                        null,
                        2
                      ),
                      "Copied sample response"
                    )
                  }
                  className="inline-flex items-center gap-1.5 text-xs text-white/70 hover:text-white"
                >
                  <Copy className="w-3.5 h-3.5" /> Copy JSON
                </button>
              </div>
              <pre className="text-xs font-mono leading-relaxed text-emerald-200/95">
{`{
  "bank_id": "b0419e61-2d8a-4e11-94c8-001122334455",
  "since": "2026-11-06T10:00:00+00:00",
  "cursor": "2026-11-06T10:14:59+00:00",
  "count": 2,
  "truncated": false,
  "collections": ["complaints", "incidents"],
  "poll_interval_seconds": 5,
  "items": [
    {
      "collection": "complaints",
      "id": "8a91c340-1b2e-4f88-9102-abcdef123456",
      "updated_at": "2026-11-06T10:14:12+00:00",
      "data": {
        "id": "8a91c340-1b2e-4f88-9102-abcdef123456",
        "channel": "in_app",
        "issue_type": "failed_transfer",
        "severity": "high",
        "text": "Debited ₦50,000 on USSD, recipient not credited.",
        "summary": "Failed USSD transfer debit without beneficiary credit",
        "region": "Lagos",
        "occurred_at": "2026-11-06T10:14:00+00:00",
        "incident_id": "2c8d45a1-7e10-4b9c-9a21-55f8e1a9d001"
      }
    },
    {
      "collection": "incidents",
      "id": "2c8d45a1-7e10-4b9c-9a21-55f8e1a9d001",
      "updated_at": "2026-11-06T10:14:59+00:00",
      "data": {
        "id": "2c8d45a1-7e10-4b9c-9a21-55f8e1a9d001",
        "issue_type": "failed_transfer",
        "status": "open",
        "complaint_count": 30,
        "detected_at": "2026-11-06T10:14:59+00:00"
      }
    }
  ]
}`}
              </pre>
            </div>
          </section>

          {/* 04. LIVE "TRY IT" API EXPLORER */}
          <section
            id="try-it"
            className="scroll-mt-28 rounded-t-[36px] rounded-b-3xl bg-[#14233f] text-[#f0f1eb] border border-white/10 p-8 md:p-10 shadow-2xl"
          >
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-[10px] font-semibold tracking-[0.14em] uppercase text-[#f4a261] mb-2">
                  04 · INTERACTIVE SANDBOX TESTER
                </p>
                <h2 className="text-3xl md:text-4xl font-normal tracking-[-0.045em] text-white">
                  Live &ldquo;Try It&rdquo; API Explorer
                </h2>
              </div>
              <button
                type="button"
                onClick={handleProvisionSandboxKey}
                disabled={provisioningKey}
                className="inline-flex items-center gap-2 rounded-full bg-white/10 hover:bg-white/15 border border-white/15 text-xs font-semibold text-[#f4a261] px-4 py-2.5 transition-colors disabled:opacity-50"
              >
                {provisioningKey ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Sparkles className="w-3.5 h-3.5" />
                )}
                {provisioningKey ? "Provisioning Key…" : "Auto-Provision Demo Key (Zymic Bank)"}
              </button>
            </div>
            <p className="mt-2 text-xs md:text-sm text-[#b8c1d0] max-w-2xl">
              Paste a <code className="font-mono text-white">cfx_api_…</code> key from{" "}
              <Link href="/dashboard/settings/keys" className="underline text-[#f4a261]">
                /dashboard/settings/keys
              </Link>{" "}
              (or click Auto-Provision above) to execute a real HTTP request against your running FastAPI
              backend at <code className="font-mono text-white">http://127.0.0.1:8000</code>.
            </p>

            <div className="mt-7 space-y-4">
              <div className="grid md:grid-cols-12 gap-4">
                <div className="md:col-span-5">
                  <label className="block text-[10px] font-mono uppercase tracking-wider text-white/60 mb-1.5">
                    Bearer Token (cfx_api_… or JWT)
                  </label>
                  <input
                    type="text"
                    value={testerKey}
                    onChange={(e) => setTesterKey(e.target.value)}
                    placeholder="cfx_api_..."
                    className="w-full rounded-2xl bg-white/5 border border-white/15 px-4 py-3 text-xs font-mono text-white placeholder:text-white/30 outline-none focus:border-[#e8651a]"
                  />
                </div>
                <div className="md:col-span-7">
                  <label className="block text-[10px] font-mono uppercase tracking-wider text-white/60 mb-1.5">
                    Preset Endpoint
                  </label>
                  <select
                    value={selectedPresetIdx}
                    onChange={(e) => handlePresetChange(Number(e.target.value))}
                    className="w-full rounded-2xl bg-[#1d3358] border border-white/15 px-4 py-3 text-xs text-white outline-none focus:border-[#e8651a]"
                  >
                    {TESTER_PRESETS.map((preset, i) => (
                      <option key={preset.label} value={i}>
                        [{preset.scope.toUpperCase()}] {preset.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-3">
                <select
                  value={customMethod}
                  onChange={(e) => setCustomMethod(e.target.value as "GET" | "POST")}
                  className="rounded-2xl bg-[#1d3358] border border-white/15 px-4 py-3 text-xs font-mono font-semibold text-[#f4a261] outline-none"
                >
                  <option value="GET">GET</option>
                  <option value="POST">POST</option>
                </select>
                <input
                  type="text"
                  value={customEndpoint}
                  onChange={(e) => setCustomEndpoint(e.target.value)}
                  className="flex-1 rounded-2xl bg-white/5 border border-white/15 px-4 py-3 text-xs font-mono text-white outline-none focus:border-[#e8651a]"
                />
                <button
                  type="button"
                  onClick={handleRunTest}
                  disabled={testerLoading}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#e8651a] hover:bg-[#f4a261] text-[#14233f] font-semibold text-xs px-6 py-3 transition-colors disabled:opacity-50 shrink-0"
                >
                  {testerLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-3.5 h-3.5" />
                  )}
                  Send Request
                </button>
              </div>

              {customMethod === "POST" && (
                <div>
                  <label className="block text-[10px] font-mono uppercase tracking-wider text-white/60 mb-1.5">
                    JSON Request Body
                  </label>
                  <textarea
                    rows={3}
                    value={customBody}
                    onChange={(e) => setCustomBody(e.target.value)}
                    className="w-full rounded-2xl bg-black/30 border border-white/15 p-3.5 text-xs font-mono text-white outline-none focus:border-[#e8651a]"
                  />
                </div>
              )}

              {/* Live Response Viewer */}
              <div className="rounded-2xl bg-black/40 border border-white/10 overflow-hidden">
                <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between text-xs font-mono">
                  <div className="flex items-center gap-3">
                    <span className="text-white/50">RESPONSE</span>
                    {testerResult && (
                      <>
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                            testerResult.ok
                              ? "bg-emerald-500/20 text-emerald-300"
                              : "bg-red-500/20 text-red-300"
                          }`}
                        >
                          HTTP {testerResult.status || "ERR"}
                        </span>
                        <span className="text-white/50">{testerResult.durationMs} ms</span>
                      </>
                    )}
                  </div>
                  {testerResult && (
                    <button
                      type="button"
                      onClick={() =>
                        copyText(JSON.stringify(testerResult.data, null, 2), "Copied response JSON")
                      }
                      className="inline-flex items-center gap-1 text-white/60 hover:text-white"
                    >
                      <Copy className="w-3.5 h-3.5" /> Copy
                    </button>
                  )}
                </div>
                <pre className="p-4 text-xs font-mono text-emerald-200 max-h-96 overflow-auto leading-relaxed">
                  {testerResult
                    ? JSON.stringify(testerResult.data, null, 2)
                    : "// Click 'Send Request' above to inspect live backend JSON output..."}
                </pre>
              </div>
            </div>
          </section>

          {/* 05. ENDPOINT REFERENCE */}
          <section
            id="endpoints"
            className="scroll-mt-28 rounded-t-[36px] rounded-b-3xl bg-white/80 border border-[#14233f]/12 p-8 md:p-10"
          >
            <p className="text-[10px] font-semibold tracking-[0.14em] uppercase text-[#ad4814] mb-3">
              05 · MACHINE &amp; INGESTION CONTRACT
            </p>
            <h2 className="text-3xl md:text-4xl font-normal tracking-[-0.045em] text-[#14233f]">
              Complete Endpoint Reference
            </h2>
            <p className="mt-3 text-sm text-[#485570] leading-relaxed max-w-2xl">
              All paths are prefixed with <code className="font-mono text-[#14233f]">/api/v1</code>.
              Machine endpoints authenticate via <code className="font-mono text-[#14233f]">cfx_api_</code>{" "}
              bearer keys; management and UI endpoints use operator JWTs.
            </p>

            <div className="mt-8 space-y-3">
              {[
                {
                  method: "GET",
                  path: "/api/v1/machine/updates",
                  auth: "cfx_api_ (read)",
                  desc: "Versioned 5s handoff feed. Query params: since (ISO-8601 UTC cursor), collections (complaints,incidents,drafts,actions,investigations,audit), limit (1–500).",
                },
                {
                  method: "GET",
                  path: "/api/v1/machine/summary",
                  auth: "cfx_api_ (read)",
                  desc: "Bank-scoped analytics summary: total_complaints, fraud_count, money_at_risk, open_incidents, repeat_complaint_rate, by_issue, by_channel, by_region.",
                },
                {
                  method: "GET",
                  path: "/api/v1/machine/incidents",
                  auth: "cfx_api_ (read)",
                  desc: "Ranked incidents list ordered by priority_score DESC. Optional ?status=open|investigating|resolved&limit=50.",
                },
                {
                  method: "GET",
                  path: "/api/v1/machine/incidents/{incident_id}",
                  auth: "cfx_api_ (read)",
                  desc: "Full incident overview bundle including attached complaints, payment evidence, hypotheses, and corrective actions.",
                },
                {
                  method: "GET",
                  path: "/api/v1/machine/complaints",
                  auth: "cfx_api_ (read)",
                  desc: "Paginated complaint feed. Filters: channel, issue_type, since, until, limit, offset.",
                },
                {
                  method: "GET",
                  path: "/api/v1/machine/audit",
                  auth: "cfx_api_ (read)",
                  desc: "Immutable bank audit trail entries (actor, action, entity_type, entity_id, details, created_at).",
                },
                {
                  method: "GET",
                  path: "/api/v1/machine/health/connectors",
                  auth: "cfx_api_ (read)",
                  desc: "Connector posture, active intake keys, and worker queue health (pending vs dead_lettered).",
                },
                {
                  method: "POST",
                  path: "/api/v1/machine/investigations",
                  auth: "cfx_api_ (operate)",
                  desc: "Request an asynchronous AI + payment evidence investigation run on an incident_id (returns 202 Accepted).",
                },
                {
                  method: "POST",
                  path: "/api/v1/machine/jobs/drain",
                  auth: "cfx_api_ (operate)",
                  desc: "Drain pending classification, spike detection, investigation, and approval outbox jobs.",
                },
                {
                  method: "POST",
                  path: "/api/v1/complaints",
                  auth: "Operator JWT",
                  desc: "Ingest a customer complaint with automatic PII masking and classification job enqueue.",
                },
                {
                  method: "POST",
                  path: "/api/v1/ingestion/complaints",
                  auth: "Connector Token",
                  desc: "Idempotent CRM/support ticket intake with source_system, external_id, payment_reference, amount, currency, occurred_at.",
                },
                {
                  method: "POST",
                  path: "/api/v1/api-keys",
                  auth: "Admin JWT",
                  desc: "Provision a new machine API key (name, scopes: ['read', 'operate'], expires_at). Returns raw token ONCE.",
                },
                {
                  method: "GET",
                  path: "/api/v1/api-keys",
                  auth: "Admin JWT",
                  desc: "List all machine keys for the current bank (key_prefix, scopes, status, last_used_at, revoked_at). Never returns raw tokens.",
                },
                {
                  method: "POST",
                  path: "/api/v1/api-keys/{key_id}/revoke",
                  auth: "Admin JWT",
                  desc: "Immediately and idempotently revoke a machine API key.",
                },
              ].map((ep) => (
                <div
                  key={ep.path}
                  className="rounded-2xl bg-[#f0f1eb] border border-[#14233f]/10 p-4 flex flex-col md:flex-row md:items-center justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <span
                        className={`text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-md ${
                          ep.method === "GET"
                            ? "bg-[#14233f] text-white"
                            : "bg-[#e8651a] text-[#14233f]"
                        }`}
                      >
                        {ep.method}
                      </span>
                      <code className="text-xs md:text-sm font-mono font-semibold text-[#14233f]">
                        {ep.path}
                      </code>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white border border-[#14233f]/10 text-[#485570]">
                        {ep.auth}
                      </span>
                    </div>
                    <p className="text-xs text-[#485570]">{ep.desc}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => copyText(ep.path, `Copied ${ep.path}`)}
                    className="self-start md:self-center p-2 rounded-xl hover:bg-[#14233f]/10 text-[#485570] hover:text-[#14233f] shrink-0"
                    title="Copy path"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </section>

          {/* 06. PROVIDER WEBHOOKS */}
          <section
            id="webhooks"
            className="scroll-mt-28 rounded-t-[36px] rounded-b-3xl bg-[#eadfcf] border border-[#14233f]/12 p-8 md:p-10"
          >
            <p className="text-[10px] font-semibold tracking-[0.14em] uppercase text-[#ad4814] mb-3">
              06 · SIGNED SWITCH &amp; PROVIDER EVIDENCE INTAKE
            </p>
            <h2 className="text-3xl md:text-4xl font-normal tracking-[-0.045em] text-[#14233f]">
              Provider Webhooks (<code className="font-mono text-2xl md:text-3xl">POST /api/v1/forge/webhooks</code>)
            </h2>
            <p className="mt-3 text-sm text-[#485570] leading-relaxed max-w-2xl">
              <strong>Note for Bank Developers:</strong> Your bank dashboard does <em>not</em> call this
              endpoint. ConfluxHQ receives signed payment switch and settlement telemetry from XtraDot
              Forge here, verifies the HMAC-SHA256 signature, and correlates the resulting payment
              evidence with customer complaints automatically.
            </p>

            <div className="grid md:grid-cols-3 gap-4 mt-7">
              <div className="rounded-2xl bg-white/75 p-5 border border-[#14233f]/10">
                <code className="text-xs font-mono font-bold text-[#14233f]">x-forge-event</code>
                <p className="text-xs text-[#485570] mt-2">
                  Event classification header (e.g. <code className="font-mono">transfer.failed</code>,{" "}
                  <code className="font-mono">reversal.pending</code>,{" "}
                  <code className="font-mono">settlement.delayed</code>). Max 160 chars.
                </p>
              </div>
              <div className="rounded-2xl bg-white/75 p-5 border border-[#14233f]/10">
                <code className="text-xs font-mono font-bold text-[#14233f]">x-forge-timestamp</code>
                <p className="text-xs text-[#485570] mt-2">
                  Delivery timestamp validated within a strict <strong>±5 minute</strong> replay window (
                  <code className="font-mono">unix-seconds</code> or <code className="font-mono">iso8601</code>).
                </p>
              </div>
              <div className="rounded-2xl bg-white/75 p-5 border border-[#14233f]/10">
                <code className="text-xs font-mono font-bold text-[#14233f]">x-forge-signature</code>
                <p className="text-xs text-[#485570] mt-2">
                  Hex-encoded <strong>HMAC-SHA256</strong> over{" "}
                  <code className="font-mono">{`\${timestamp}.\${raw_body}`}</code> signed with{" "}
                  <code className="font-mono">XTRADOT_WEBHOOK_SECRET</code>.
                </p>
              </div>
            </div>

            <div className="mt-6 rounded-2xl bg-[#14233f] text-[#f0f1eb] p-6 overflow-x-auto">
              <p className="text-[11px] font-mono text-[#f4a261] mb-2">
                Webhook Payload &amp; Evidence Correlation Fields (provider_event_id, payment_reference, report_id)
              </p>
              <pre className="text-xs font-mono leading-relaxed text-[#f0f1eb]">
{`POST /api/v1/forge/webhooks
x-forge-event: transfer.failed
x-forge-timestamp: 1762424099
x-forge-signature: sha256=9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08

{
  "event_id": "evt_forge_9920184a",
  "provider_event_id": "prov_sw_a_884120",
  "payment_reference": "TRF-90812231",
  "report_id": "rep_zymic_20261106_01",
  "status": "failed",
  "settlement_status": "unsettled",
  "amount": "45000.00",
  "currency": "NGN",
  "occurred_at": "2026-11-06T10:14:05Z"
}

// Response (202 Accepted):
{
  "receipt_id": "f41d8cd9-8f00-4204-a980-0998ecf8427e",
  "status": "received",
  "duplicate": false
}`}
              </pre>
            </div>
          </section>

          {/* 07. CODE SAMPLES */}
          <section
            id="code-samples"
            className="scroll-mt-28 rounded-t-[36px] rounded-b-3xl bg-white/80 border border-[#14233f]/12 p-8 md:p-10"
          >
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-[10px] font-semibold tracking-[0.14em] uppercase text-[#ad4814] mb-2">
                  07 · MULTI-LANGUAGE INTEGRATION SNIPPETS
                </p>
                <h2 className="text-3xl md:text-4xl font-normal tracking-[-0.045em] text-[#14233f]">
                  Production Code Samples
                </h2>
              </div>

              {/* Language Selector Tabs */}
              <div className="inline-flex rounded-full bg-[#f0f1eb] p-1 border border-[#14233f]/12">
                {(
                  [
                    ["curl", "cURL"],
                    ["python", "Python (httpx)"],
                    ["javascript", "JavaScript (fetch)"],
                  ] as const
                ).map(([lang, label]) => (
                  <button
                    key={lang}
                    type="button"
                    onClick={() => setCodeTab(lang)}
                    className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                      codeTab === lang
                        ? "bg-[#14233f] text-[#f0f1eb]"
                        : "text-[#485570] hover:text-[#14233f]"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-8 space-y-6">
              {[
                {
                  key: "pollLoop",
                  title: "A. 5-Second Cursor Handoff Poller (read scope)",
                },
                {
                  key: "ingestComplaint",
                  title: "B. Customer Complaint Intake with PII Masking",
                },
                {
                  key: "operateActions",
                  title: "C. Trigger Investigation & Drain Worker Queue (operate scope)",
                },
              ].map((block) => (
                <div
                  key={block.key}
                  className="rounded-2xl bg-[#14233f] text-[#f0f1eb] overflow-hidden border border-white/10"
                >
                  <div className="px-5 py-3.5 bg-white/5 border-b border-white/10 flex items-center justify-between">
                    <span className="text-xs font-medium text-[#f4a261]">{block.title}</span>
                    <button
                      type="button"
                      onClick={() =>
                        copyText(SAMPLE_CODE[block.key][codeTab], `Copied ${codeTab} snippet`)
                      }
                      className="inline-flex items-center gap-1.5 text-xs text-white/70 hover:text-white"
                    >
                      <Copy className="w-3.5 h-3.5" /> Copy {codeTab}
                    </button>
                  </div>
                  <pre className="p-5 text-xs font-mono leading-relaxed text-[#f0f1eb] overflow-x-auto">
                    {SAMPLE_CODE[block.key][codeTab]}
                  </pre>
                </div>
              ))}
            </div>
          </section>

          {/* 08. RATE LIMITS & ERRORS */}
          <section
            id="errors"
            className="scroll-mt-28 rounded-t-[36px] rounded-b-3xl bg-[#e7e9e1] border border-[#14233f]/12 p-8 md:p-10"
          >
            <p className="text-[10px] font-semibold tracking-[0.14em] uppercase text-[#ad4814] mb-3">
              08 · STATUS CODES &amp; GUARDRAILS
            </p>
            <h2 className="text-3xl md:text-4xl font-normal tracking-[-0.045em] text-[#14233f]">
              Rate Limits &amp; Error Handling
            </h2>
            <p className="mt-3 text-sm text-[#485570] leading-relaxed max-w-2xl">
              Errors follow FastAPI&apos;s standard JSON envelope{" "}
              <code className="font-mono text-[#14233f]">{`{"detail": "..."}`}</code>. Machine pollers
              should implement exponential backoff on <code className="font-mono">5xx</code> and halt
              immediately on <code className="font-mono">401</code> or <code className="font-mono">403</code>.
            </p>

            <div className="grid md:grid-cols-2 gap-4 mt-7">
              {[
                {
                  code: "401 Unauthorized",
                  cause: "Missing, expired, or revoked Bearer token, or invalid webhook HMAC signature.",
                  fix: "Verify Authorization: Bearer cfx_api_... header or provision a fresh key at /dashboard/settings/keys.",
                },
                {
                  code: "403 Forbidden",
                  cause: "Key lacks required scope (e.g. calling POST /machine/jobs/drain with a read-only key) or role is not bank_admin.",
                  fix: "Provision a machine key with both ['read', 'operate'] scopes.",
                },
                {
                  code: "409 Conflict",
                  cause: "Conflicting idempotent complaint replay or synthetic seed called when records already exist.",
                  fix: "Ensure external_id is unique per ticket or pass reset=true when seeding demo data.",
                },
                {
                  code: "422 Unprocessable Entity",
                  cause: "Invalid cursor format (since must be ISO-8601 UTC with Z or +00:00), unknown collection name, or schema validation failure.",
                  fix: "Pass the exact cursor string returned by the previous /machine/updates response.",
                },
                {
                  code: "503 Service Unavailable",
                  cause: "DEMO_TOKEN_SECRET (<32 chars) or XTRADOT_WEBHOOK_SECRET not configured on server.",
                  fix: "Configure required secrets in backend/.env and restart Uvicorn.",
                },
                {
                  code: "Spend & Rate Guardrails",
                  cause: "X API v2 daily read cap (500 posts/day = $2.50/day) or webhook body > 1 MB (413).",
                  fix: "Conflux automatically falls back to deterministic rules and recorded X replay when offline.",
                },
              ].map((err) => (
                <div
                  key={err.code}
                  className="rounded-2xl bg-white/80 border border-[#14233f]/10 p-5 space-y-1.5"
                >
                  <p className="text-xs font-mono font-bold text-[#ad4814]">{err.code}</p>
                  <p className="text-xs text-[#14233f] font-medium">{err.cause}</p>
                  <p className="text-xs text-[#485570]">{err.fix}</p>
                </div>
              ))}
            </div>
          </section>

          {/* 09. CHANGELOG */}
          <section
            id="changelog"
            className="scroll-mt-28 rounded-t-[36px] rounded-b-3xl bg-white/80 border border-[#14233f]/12 p-8 md:p-10"
          >
            <p className="text-[10px] font-semibold tracking-[0.14em] uppercase text-[#ad4814] mb-3">
              09 · API VERSION HISTORY
            </p>
            <h2 className="text-3xl font-normal tracking-[-0.045em] text-[#14233f]">
              Changelog
            </h2>
            <div className="mt-6 space-y-4 text-xs">
              {[
                {
                  version: "v1.2.0 — Machine Handoff Feed & Scoped Keys",
                  date: "November 2026",
                  notes:
                    "Added bank-scoped cfx_api_ credentials (/api/v1/api-keys) with read/operate scopes and the 5-second cursor handoff stream (GET /api/v1/machine/updates).",
                },
                {
                  version: "v1.1.0 — XtraDot Forge Signed Webhooks & Reconciliation",
                  date: "November 2026",
                  notes:
                    "Added HMAC-SHA256 webhook verification at POST /api/v1/forge/webhooks and payment exception reconciliation workflows.",
                },
                {
                  version: "v1.0.0 — Core Complaint Intake, Spike Detection & AI Investigation",
                  date: "November 2026",
                  notes:
                    "Initial release with multilingual Nigerian banking classifier, MAD statistical spike detector, bounded agent investigation, and human-in-the-loop draft approvals.",
                },
              ].map((rel) => (
                <div
                  key={rel.version}
                  className="rounded-2xl bg-[#f0f1eb] border border-[#14233f]/10 p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div>
                    <p className="font-semibold text-[#14233f] text-sm">{rel.version}</p>
                    <p className="text-[#485570] mt-1">{rel.notes}</p>
                  </div>
                  <span className="font-mono text-[11px] text-[#ad4814] shrink-0">{rel.date}</span>
                </div>
              ))}
            </div>
          </section>
        </main>
      </div>

      {/* Footer (Synchronized with Landing Page Footer + Large Product Text) */}
      <footer className="border-t border-[#14233f]/12 bg-[#f0f1eb] pt-14 pb-10 px-6 lg:px-10">
        <div className="max-w-[1380px] mx-auto">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 pb-12">
            <Link href="/" className="flex items-center gap-2.5 text-[#14233f] font-semibold text-xl tracking-[-0.8px]">
              <Image
                src="/conflux-logo-full.jpg"
                alt="Conflux HQ"
                width={30}
                height={30}
                className="rounded-lg object-contain"
              />
              <span>
                conflux<span className="text-[9px] text-[#e8651a] align-super ml-1">HQ</span>
              </span>
            </Link>
            <nav className="flex flex-wrap items-center gap-6 text-xs text-[#485570]">
              <Link href="/" className="hover:text-[#14233f]">
                Landing Page
              </Link>
              <Link href="/dashboard" className="hover:text-[#14233f]">
                Operations Console
              </Link>
              <Link href="/dashboard/settings/keys" className="hover:text-[#14233f]">
                API Keys
              </Link>
              <a href="/docs" target="_blank" rel="noreferrer" className="hover:text-[#14233f]">
                OpenAPI (/docs)
              </a>
              <Link href="/login" className="hover:text-[#14233f] font-semibold text-[#14233f]">
                Sign in →
              </Link>
            </nav>
          </div>

          <div
            aria-hidden="true"
            className="flex items-center justify-center gap-4 font-extrabold tracking-[-0.055em] leading-[0.9] text-center select-none pointer-events-none py-10 border-t border-[#14233f]/10 text-[#14233f]/[0.06]"
            style={{ fontSize: "clamp(3.2rem, 14vw, 11.5rem)" }}
          >
            <span>CONFLUX</span>
            <span className="text-[#e8651a]/20">HQ</span>
          </div>

          <div className="border-t border-[#14233f]/15 pt-6 flex flex-wrap items-center justify-between gap-4 text-[11px] text-[#697388]">
            <span>© Conflux HQ · Developer &amp; Machine Handoff Documentation</span>
            <a href="#" className="text-[#485570] hover:text-[#14233f]">
              Back to top ↑
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
