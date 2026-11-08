"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  Lock,
  Mail,
  Radio,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import LogoIcon from "@/components/LogoIcon";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");

  // Sign-in state
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);

  // Register state
  const [bankName, setBankName] = useState("");
  const [cacNumber, setCacNumber] = useState("");
  const [adminName, setAdminName] = useState("");
  const [email, setEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!identifier.trim() || !password) return;
    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await api.login(identifier.trim(), password);
      setSuccessMsg(
        `Authenticated as ${res.user?.full_name || identifier} (${res.user?.bank?.name || identifier}). Redirecting…`
      );
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bankName.trim() || !adminName.trim() || !email.trim() || !regPassword) return;
    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await api.registerBank({
        bank_name: bankName.trim(),
        cac_number: cacNumber.trim() || undefined,
        country: "NG",
        admin_full_name: adminName.trim(),
        email: email.trim(),
        password: regPassword,
      });
      setSuccessMsg(`Bank tenant '${res.user?.bank?.name || bankName}' provisioned. Redirecting to console…`);
      router.push("/dashboard");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Registration failed. Ensure password has at least 8 characters with letters and numbers."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-cream flex flex-col lg:flex-row">
      {/* Left Brand & Architecture Panel */}
      <div className="lg:w-[46%] bg-navy text-white p-8 md:p-12 lg:p-16 flex flex-col justify-between relative overflow-hidden">
        <div
          className="pointer-events-none absolute -top-24 -right-24 w-96 h-96 rounded-full opacity-20 blur-3xl"
          style={{ background: "radial-gradient(circle, #E8651A 0%, transparent 70%)" }}
        />

        <div>
          <div className="flex items-center justify-between mb-12">
            <Link href="/" className="inline-flex items-center gap-2.5">
              <LogoIcon className="w-9 h-9" />
              <span className="text-2xl font-semibold tracking-tight">
                Conflux <span className="text-flux">HQ</span>
              </span>
            </Link>
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-white/60 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Back to site
            </Link>
          </div>

          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 border border-white/10 text-xs font-semibold text-flux-soft mb-6">
            <Radio className="w-3.5 h-3.5 text-flux animate-pulse" />
            Real-Time Complaint Intelligence Engine
          </div>

          <h1
            className="text-3xl md:text-4xl lg:text-5xl font-semibold leading-[1.08] tracking-tight"
            style={{ letterSpacing: "-0.03em" }}
          >
            Bank-grade complaint intelligence, ready for live operations.
          </h1>
          <p className="text-white/65 text-base md:text-lg mt-4 max-w-md leading-relaxed">
            Sign in to monitor every Nigerian customer channel, detect systemic switch spikes within minutes, and review AI-drafted responses with human sign-off.
          </p>

          <div className="mt-10 space-y-4">
            {[
              [
                "Multilingual AI Classification",
                "Classifies English, Pidgin, Yoruba, Hausa, and Igbo complaints across X, Instagram, USSD, App, and Branch.",
              ],
              [
                "Deterministic Spike Detection",
                "Flags volume anomalies exceeding trailing median + 3 MAD and correlates against switch transactions.",
              ],
              [
                "Human-in-the-Loop Guardrails",
                "Drafts customer holding messages and IT tickets while enforcing strict core-banking sign-off for reversals.",
              ],
            ].map(([title, desc]) => (
              <div
                key={title}
                className="flex items-start gap-3.5 rounded-2xl bg-white/[0.04] border border-white/[0.06] p-4"
              >
                <CheckCircle2 className="w-5 h-5 text-flux shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-sm text-white">{title}</p>
                  <p className="text-xs text-white/60 mt-0.5 leading-relaxed">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-white/10 flex flex-wrap items-center justify-between gap-4 text-xs text-white/50">
          <span className="flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            Tenant-isolated JWT bearer authentication
          </span>
          <span>NDPR &amp; CBN Consumer Protection aligned</span>
        </div>
      </div>

      {/* Right Authentication Form Panel */}
      <div className="flex-1 flex items-center justify-center p-6 md:p-12 lg:p-16">
        <div className="w-full max-w-md">
          {/* Mode Switcher */}
          <div className="flex rounded-full bg-navy/[0.05] p-1 mb-8 border border-navy/[0.06]">
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError(null);
              }}
              className={`flex-1 py-2.5 text-sm font-semibold rounded-full transition-all ${
                mode === "login" ? "bg-navy text-white shadow-sm" : "text-navy/60 hover:text-navy"
              }`}
            >
              Operator Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("register");
                setError(null);
              }}
              className={`flex-1 py-2.5 text-sm font-semibold rounded-full transition-all ${
                mode === "register" ? "bg-navy text-white shadow-sm" : "text-navy/60 hover:text-navy"
              }`}
            >
              Register Bank Tenant
            </button>
          </div>

          {error && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-6 rounded-2xl bg-red-50 border border-red-200 p-4 text-xs font-medium text-red-700"
            >
              {error}
            </motion.div>
          )}

          {successMsg && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-6 rounded-2xl bg-emerald-50 border border-emerald-200 p-4 text-xs font-medium text-emerald-800"
            >
              {successMsg}
            </motion.div>
          )}

          {mode === "login" ? (
            <div className="rounded-3xl bg-white border border-navy/[0.08] p-7 md:p-8 shadow-[0_20px_50px_-24px_rgba(20,35,63,.12)]">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-semibold text-navy" style={{ letterSpacing: "-0.02em" }}>
                    Sign in to Console
                  </h2>
                  <p className="text-sm text-navy/55 mt-0.5">
                    Enter your bank workspace and operator credentials
                  </p>
                </div>
                <div className="w-10 h-10 rounded-2xl bg-flux/10 flex items-center justify-center text-flux">
                  <Lock className="w-5 h-5" />
                </div>
              </div>

              <form onSubmit={handleLogin} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-navy/60 mb-1.5">
                    Bank Name or Operator Email
                  </label>
                  <div className="relative">
                    <Building2 className="w-4 h-4 text-navy/40 absolute left-4 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      required
                      value={identifier}
                      onChange={(e) => setIdentifier(e.target.value)}
                      placeholder="Enter bank name or operator email"
                      className="w-full rounded-2xl bg-navy/[0.03] border border-navy/10 pl-11 pr-4 py-3 text-sm text-navy outline-none focus:border-flux focus:bg-white transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-navy/60 mb-1.5">
                    Password
                  </label>
                  <div className="relative">
                    <KeyRound className="w-4 h-4 text-navy/40 absolute left-4 top-1/2 -translate-y-1/2" />
                    <input
                      type={showPw ? "text" : "password"}
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter password"
                      className="w-full rounded-2xl bg-navy/[0.03] border border-navy/10 pl-11 pr-11 py-3 text-sm text-navy outline-none focus:border-flux focus:bg-white transition-colors"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPw((s) => !s)}
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-navy/40 hover:text-navy"
                      aria-label="Toggle password visibility"
                    >
                      {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full mt-2 inline-flex items-center justify-center gap-2 rounded-full bg-navy text-white font-semibold py-3.5 px-6 hover:bg-navy-600 transition-colors disabled:opacity-60 shadow-sm"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Authenticating…
                    </>
                  ) : (
                    <>
                      Sign in to Conflux HQ
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </form>
            </div>
          ) : (
            <div className="rounded-3xl bg-white border border-navy/[0.08] p-7 md:p-8 shadow-[0_20px_50px_-24px_rgba(20,35,63,.12)]">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-semibold text-navy" style={{ letterSpacing: "-0.02em" }}>
                    Onboard Bank Tenant
                  </h2>
                  <p className="text-sm text-navy/55 mt-0.5">
                    Provision a dedicated bank tenant &amp; administrator account
                  </p>
                </div>
                <div className="w-10 h-10 rounded-2xl bg-flux/10 flex items-center justify-center text-flux">
                  <UserCheck className="w-5 h-5" />
                </div>
              </div>

              <form onSubmit={handleRegister} className="space-y-3.5">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-navy/60 mb-1">
                    Bank Name
                  </label>
                  <div className="relative">
                    <Building2 className="w-4 h-4 text-navy/40 absolute left-4 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      required
                      value={bankName}
                      onChange={(e) => setBankName(e.target.value)}
                      placeholder="Enter bank institution name"
                      className="w-full rounded-2xl bg-navy/[0.03] border border-navy/10 pl-11 pr-4 py-2.5 text-sm text-navy outline-none focus:border-flux focus:bg-white"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-navy/60 mb-1">
                    CAC Number (Optional)
                  </label>
                  <input
                    type="text"
                    value={cacNumber}
                    onChange={(e) => setCacNumber(e.target.value)}
                    placeholder="Corporate registration number"
                    className="w-full rounded-2xl bg-navy/[0.03] border border-navy/10 px-4 py-2.5 text-sm text-navy outline-none focus:border-flux focus:bg-white"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-navy/60 mb-1">
                    Admin Full Name
                  </label>
                  <input
                    type="text"
                    required
                    value={adminName}
                    onChange={(e) => setAdminName(e.target.value)}
                    placeholder="Enter administrator full name"
                    className="w-full rounded-2xl bg-navy/[0.03] border border-navy/10 px-4 py-2.5 text-sm text-navy outline-none focus:border-flux focus:bg-white"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-navy/60 mb-1">
                    Official Bank Email
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-navy/40 absolute left-4 top-1/2 -translate-y-1/2" />
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="Enter work email address"
                      className="w-full rounded-2xl bg-navy/[0.03] border border-navy/10 pl-11 pr-4 py-2.5 text-sm text-navy outline-none focus:border-flux focus:bg-white"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-navy/60 mb-1">
                    Password (8+ chars, letter &amp; number)
                  </label>
                  <div className="relative">
                    <KeyRound className="w-4 h-4 text-navy/40 absolute left-4 top-1/2 -translate-y-1/2" />
                    <input
                      type="password"
                      required
                      minLength={8}
                      value={regPassword}
                      onChange={(e) => setRegPassword(e.target.value)}
                      placeholder="Create strong password"
                      className="w-full rounded-2xl bg-navy/[0.03] border border-navy/10 pl-11 pr-4 py-2.5 text-sm text-navy outline-none focus:border-flux focus:bg-white"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full mt-2 inline-flex items-center justify-center gap-2 rounded-full bg-flux text-white font-semibold py-3.5 px-6 hover:bg-[#d25a14] transition-colors disabled:opacity-60 shadow-sm"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Provisioning Bank…
                    </>
                  ) : (
                    <>
                      Create Bank Workspace
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
