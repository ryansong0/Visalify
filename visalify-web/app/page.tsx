"use client";

import { useState } from "react";

type Gap = {
  category: string;
  detected_risk: string;
  optimization_strategy: string;
};

type MatchResult = {
  overall_match_score: number;
  compliance_verdict: string;
  detected_gaps: Gap[];
  optimized_profile: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export default function Home() {
  const [profile, setProfile] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MatchResult | null>(null);
  
  const handleSubmit = async () => {
    setError(null);
    setResult(null);

    if (!profile.trim() || !jobDescription.trim()) {
      setError("Add both your resume and the target job description to run the check.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/match`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_profile: profile,
          job_description: jobDescription,
        }),
      });

      if (!res.ok) {
        setError("The analysis engine returned an error. Try again in a moment.");
        return;
      }

      const data: MatchResult = await res.json();
      setResult(data);
    } catch (e) {
      setError("Couldn't reach the analysis engine. Make sure the backend server is running.");
    } finally {
      setLoading(false);
    }
  };

  const verdictRaw = result?.compliance_verdict ?? "";
  const isClear = verdictRaw === "SAFE" || verdictRaw === "LOW_RISK";

  const formatVerdict = (v: string) =>
    v.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <main className="min-h-screen px-6 py-16 md:py-24">
      <div className="mx-auto max-w-4xl">

        {/* Header */}
        <header className="mb-14">
          <div className="mb-6 flex items-center gap-2 text-xs font-medium tracking-wide text-stamp uppercase">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-stamp" />
            Visa-safe resume review
          </div>
          <h1 className="font-display text-5xl md:text-6xl font-medium tracking-tight text-ink leading-[1.05]">
            Visalify
          </h1>
          <p className="mt-5 max-w-2xl text-[1.05rem] leading-relaxed text-muted">
            Typical resume advice pushes leadership words like &ldquo;managed&rdquo; or &ldquo;led.&rdquo;
            Immigration officers often read those same words as a sign you&rsquo;ve moved into management,
            which can put a specialized technical visa at risk.
          </p>

          <div className="mt-6 border-l-2 border-seal bg-seal-light/60 px-5 py-4 max-w-2xl">
            <p className="text-sm leading-relaxed text-ink/80">
              <span className="font-semibold text-ink">How it works:</span> paste your resume on the left,
              the job you&rsquo;re targeting on the right. Visalify flags language that could read as a visa
              risk, and rewrites it to keep your match strength intact.
            </p>
          </div>
        </header>

        {/* Input form */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-muted">
              Your resume or profile text
            </label>
            <textarea
              value={profile}
              onChange={(e) => setProfile(e.target.value)}
              placeholder="Paste your resume or experience history here..."
              className="h-56 w-full resize-none rounded-lg border border-line bg-white/70 p-4 text-[0.95rem] leading-relaxed text-ink placeholder:text-muted/70 transition focus:border-stamp focus:bg-white focus:ring-4 focus:ring-stamp-light"
            />
          </div>
          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-muted">
              Target job requirements
            </label>
            <textarea
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="Paste the target job description or requirements here..."
              className="h-56 w-full resize-none rounded-lg border border-line bg-white/70 p-4 text-[0.95rem] leading-relaxed text-ink placeholder:text-muted/70 transition focus:border-stamp focus:bg-white focus:ring-4 focus:ring-stamp-light"
            />
          </div>
        </section>

        <div className="mb-16 flex justify-center">
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="rounded-full bg-stamp px-8 py-3 text-sm font-semibold text-white tracking-wide shadow-[0_4px_14px_rgba(11,110,79,0.28)] transition hover:bg-stamp-dark hover:shadow-[0_6px_20px_rgba(11,110,79,0.38)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Reviewing your application…" : "Check my application match"}
          </button>
        </div>

        {error && (
          <div className="mb-10 rounded-lg border border-risk/30 bg-risk-light px-5 py-4 text-sm text-risk">
            {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <section className="border-t border-line pt-12">
            <div className="mb-12 grid grid-cols-1 sm:grid-cols-2 gap-6 items-stretch">
              <div className="rounded-xl border border-line bg-white p-6">
                <div className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
                  Job match score
                </div>
                <div className="font-display text-5xl font-medium text-ink">
                  {result.overall_match_score}%
                </div>
              </div>

              <div className="relative flex items-center justify-between rounded-xl border border-line bg-white p-6 overflow-hidden">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
                    Visa risk verdict
                  </div>
                  <div className="font-display text-2xl font-medium text-ink">
                    {formatVerdict(result.compliance_verdict)}
                  </div>
                </div>
                <div
                  className={`stamp-animate select-none rounded-md border-[3px] px-3 py-1 text-xs font-bold tracking-widest uppercase ${
                    isClear
                      ? "border-stamp text-stamp"
                      : "border-risk text-risk"
                  }`}
                  style={{ transform: "rotate(-8deg)" }}
                >
                  {isClear ? "Clear" : "Flagged"}
                </div>
              </div>
            </div>

            <h2 className="font-display text-2xl font-medium text-ink mb-5">
              Issues found &amp; how to fix them
            </h2>
            <div className="mb-14 space-y-3">
              {result.detected_gaps.map((gap, i) => (
                <details
                  key={i}
                  className="group rounded-lg border border-line bg-white px-5 py-4 open:pb-5"
                >
                  <summary className="cursor-pointer list-none font-medium text-ink flex items-center justify-between">
                    <span>Focus area: {gap.category}</span>
                    <span className="text-muted transition group-open:rotate-45">+</span>
                  </summary>
                  <div className="mt-3 space-y-2 text-sm leading-relaxed text-muted">
                    <p><span className="font-semibold text-ink">Identified risk/mismatch: </span>{gap.detected_risk}</p>
                    <p><span className="font-semibold text-ink">Optimization strategy: </span>{gap.optimization_strategy}</p>
                  </div>
                </details>
              ))}
            </div>

            <h2 className="font-display text-2xl font-medium text-ink mb-2">
              Safe, rewritten version of your resume
            </h2>
            <p className="text-sm text-muted mb-4">
              Technical terms updated to match the job, high-risk management language removed.
            </p>
            <pre className="whitespace-pre-wrap rounded-xl bg-ink text-[#E8E6DD] p-6 font-mono text-sm leading-relaxed overflow-x-auto">
              {result.optimized_profile}
            </pre>
          </section>
        )}
      </div>
    </main>
  );
}
