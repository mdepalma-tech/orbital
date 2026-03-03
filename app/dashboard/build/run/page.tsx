"use client";

import { Suspense, useEffect, useRef, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { DashboardSidebar } from "@/components/dashboard/sidebar";

interface StepEvent {
  type: "step";
  id: string;
  title: string;
  reasoning: string;
}

interface ResultEvent {
  type: "result";
  id: string;
  title: string;
  status: "pass" | "fail" | "action" | "info" | "warn";
  metrics: Record<string, unknown>;
}

interface ErrorEvent {
  type: "error";
  id: string;
  message: string;
}

interface CompleteEvent {
  type: "complete";
  id: string;
  title: string;
  summary: Record<string, unknown>;
}

type PipelineEvent = StepEvent | ResultEvent | ErrorEvent | CompleteEvent;

interface ReasoningEntry {
  id: string;
  title: string;
  reasoning: string;
  status: "running" | "done" | "error";
}

interface ChatMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
}

type LeftTab = "assistant" | "log";

function buildDiagnosticsExplanation(metrics: Record<string, unknown>): string {
  const score = (metrics.score as number) ?? 0;
  const mode = (metrics.model_mode as string) ?? "diagnostic_stabilized";
  const band = (metrics.data_confidence_band as string) ?? "Low";
  const snapshot = metrics.snapshot as Record<string, unknown> | undefined;
  const reasons = metrics.gating_reasons as string[] | undefined;

  const modeName =
    mode === "causal_full"
      ? "Causal Full — the engine will run the complete econometric test suite (VIF, autocorrelation, heteroskedasticity, nonlinearity) with strict gating."
      : mode === "causal_cautious"
        ? "Causal Cautious — the engine runs econometric tests with a balanced approach between full causal inference and stability."
        : "Diagnostic Stabilized — the engine will use regularized estimation with relaxed gating thresholds to compensate for limited data strength.";

  let msg = `Your data scored **${score}/100** — Data Confidence Band: **${band}**.\n\n`;
  msg += `The engine selected **${modeName}**\n\n`;

  if (snapshot) {
    msg += `Here's what I looked at:\n`;
    msg += `- **${snapshot.n_obs}** weekly observations\n`;
    msg += `- Spend variability (CV): **${snapshot.cv_spend_total}**\n`;
    msg += `- Signal-to-noise ratio: **${snapshot.snr}**\n`;
    msg += `- Max channel correlation: **${snapshot.max_pairwise_corr}**\n\n`;
  }

  if (reasons && reasons.length > 0) {
    msg += `Areas that reduced your score:\n`;
    reasons.forEach((r) => {
      msg += `- ${r}\n`;
    });
    msg += `\nYou can improve this by adding more historical data or increasing spend variation across channels.`;
  } else {
    msg += `All diagnostic checks passed. Your data is well-suited for causal modeling.`;
  }

  return msg;
}

const STATUS_COLORS: Record<string, string> = {
  pass: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  fail: "text-red-400 bg-red-500/10 border-red-500/30",
  action: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  info: "text-blue-400 bg-blue-500/10 border-blue-500/30",
  warn: "text-orange-400 bg-orange-500/10 border-orange-500/30",
};

const STATUS_LABELS: Record<string, string> = {
  pass: "Passed",
  fail: "Failed",
  action: "Action Taken",
  info: "Info",
  warn: "Warning",
};

function formatMetricKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatMetricValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return value.toLocaleString(undefined, { maximumFractionDigits: 6 });
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => `${formatMetricKey(k)}: ${formatMetricValue(v)}`)
      .join(" · ");
  }
  return String(value);
}

function RunPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const projectId = searchParams.get("projectId");

  const [reasoning, setReasoning] = useState<ReasoningEntry[]>([]);
  const [results, setResults] = useState<ResultEvent[]>([]);
  const [complete, setComplete] = useState<CompleteEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [leftTab, setLeftTab] = useState<LeftTab>("assistant");
  const [collapsedResults, setCollapsedResults] = useState<Set<string>>(new Set());
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "I'm your modeling assistant. I'll walk you through what the engine is doing and explain the diagnostic results as they come in.\n\nThe pipeline is starting now — I'll update you once the data diagnostics are complete.",
    },
  ]);
  const [chatInput, setChatInput] = useState("");

  const doneRef = useRef(false);
  const diagnosticsSentRef = useRef(false);
  const reasoningEndRef = useRef<HTMLDivElement>(null);
  const resultsEndRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    reasoningEndRef.current?.scrollIntoView({ behavior: "smooth" });
    resultsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [reasoning, results, chatMessages, scrollToBottom]);

  useEffect(() => {
    if (!projectId) return;

    // Reset state for a fresh stream (handles React Strict Mode double-mount)
    setReasoning([]);
    setResults([]);
    setComplete(null);
    setError(null);
    diagnosticsSentRef.current = false;
    doneRef.current = false;

    const streamUrl =
      process.env.NEXT_PUBLIC_ORBITAL_BACKEND_URL
        ? `${process.env.NEXT_PUBLIC_ORBITAL_BACKEND_URL}/v1/projects/${projectId}/run/stream`
        : `/api/projects/${projectId}/run/stream`;
    const es = new EventSource(streamUrl);

    let cancelled = false;
    es.onmessage = (e) => {
      if (cancelled) return;
      let data: PipelineEvent;
      try {
        data = JSON.parse(e.data) as PipelineEvent;
      } catch (err) {
        console.error("Failed to parse stream event:", err);
        console.error("Raw data (first 200 chars):", String(e.data).slice(0, 200));
        return;
      }

      switch (data.type) {
        case "step":
          setReasoning((prev) => {
            const updated = prev.map((r) =>
              r.status === "running" ? { ...r, status: "done" as const } : r
            );
            return [
              ...updated,
              {
                id: data.id,
                title: data.title,
                reasoning: data.reasoning,
                status: "running",
              },
            ];
          });
          break;

        case "result":
          setReasoning((prev) =>
            prev.map((r) =>
              r.id === data.id ? { ...r, status: "done" as const } : r
            )
          );
          setResults((prev) => {
            const next = [...prev, data as ResultEvent];
            // If we got matrix/ols but never received diagnostics, inject placeholder
            if (
              (data.id === "matrix" || data.id === "ols") &&
              !next.some((r) => r.id === "diagnostics")
            ) {
              const placeholder: ResultEvent = {
                type: "result",
                id: "diagnostics",
                title: "Data Diagnostics",
                status: "warn",
                metrics: {
                  score: 0,
                  model_mode: "diagnostic_stabilized",
                  data_confidence_band: "Low",
                  snapshot: {},
                  gating_reasons: ["Diagnostics event was not received by client"],
                },
              };
              // Insert diagnostics before matrix in display order
              const insertIdx = next.findIndex((r) => r.id === "matrix" || r.id === "ols");
              next.splice(insertIdx, 0, placeholder);
            }
            return next;
          });

          if (
            (data.id === "matrix" || data.id === "ols") &&
            !diagnosticsSentRef.current
          ) {
            diagnosticsSentRef.current = true;
            setChatMessages((prev) => [
              ...prev,
              {
                id: `diag-fallback-${Date.now()}`,
                role: "assistant",
                content:
                  "The data diagnostics step ran on the server. If the diagnostics card shows a warning above, the event may not have been received by the client. Check your connection and backend logs.",
              },
            ]);
          }

          if (data.id === "diagnostics" && !diagnosticsSentRef.current) {
            diagnosticsSentRef.current = true;
            const explanation = buildDiagnosticsExplanation(
              (data as ResultEvent).metrics
            );
            setChatMessages((prev) => [
              ...prev,
              {
                id: `diag-${Date.now()}`,
                role: "assistant",
                content: explanation,
              },
            ]);
          }
          break;

        case "error":
          setReasoning((prev) =>
            prev.map((r) =>
              r.id === data.id ? { ...r, status: "error" as const } : r
            )
          );
          setError(data.message);
          es.close();
          break;

        case "complete":
          doneRef.current = true;
          setReasoning((prev) =>
            prev.map((r) => ({ ...r, status: "done" as const }))
          );
          setComplete(data as CompleteEvent);
          es.close();
          break;
      }
    };

    es.onerror = () => {
      if (!doneRef.current) {
        setError("Could not connect to modeling engine. Is it running?");
      }
      es.close();
    };

    return () => {
      cancelled = true;
      es.close();
    };
  }, [projectId]);

  function handleChatSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = chatInput.trim();
    if (!text) return;

    setChatMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: "user", content: text },
    ]);
    setChatInput("");

    setTimeout(() => {
      setChatMessages((prev) => [
        ...prev,
        {
          id: `ai-${Date.now()}`,
          role: "assistant",
          content:
            "I can currently explain the data diagnostics step — including how your data strength score is calculated, what model mode was selected, and what the gating reasons mean. Full conversational AI is coming soon.",
        },
      ]);
    }, 400);
  }

  if (!projectId) {
    return (
      <div className="flex h-screen bg-[#0B0F14] text-white items-center justify-center">
        <p className="text-gray-400">Missing project ID.</p>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#0B0F14] text-white overflow-hidden">
      <DashboardSidebar />

      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-8 py-5 border-b border-white/10 flex-shrink-0">
          <div className="flex items-center gap-3">
            {!complete && !error && (
              <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            )}
            {complete && (
              <div className="w-2 h-2 rounded-full bg-emerald-400" />
            )}
            {error && (
              <div className="w-2 h-2 rounded-full bg-red-400" />
            )}
            <h1 className="text-xl font-light tracking-wide">
              {complete
                ? "Model Complete"
                : error
                ? "Pipeline Error"
                : "Running Model Pipeline..."}
            </h1>
          </div>
        </div>

        {/* Two-column layout */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left: Tabbed panel */}
          <div className="w-[58%] border-r border-white/10 flex flex-col overflow-hidden">
            {/* Tab bar */}
            <div className="flex border-b border-white/10 flex-shrink-0">
              <button
                onClick={() => setLeftTab("assistant")}
                className={`flex-1 px-4 py-3 text-sm font-light tracking-wide transition-colors relative ${
                  leftTab === "assistant"
                    ? "text-white"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                AI Assistant
                {leftTab === "assistant" && (
                  <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-cyan-500 to-blue-500" />
                )}
              </button>
              <button
                onClick={() => setLeftTab("log")}
                className={`flex-1 px-4 py-3 text-sm font-light tracking-wide transition-colors relative ${
                  leftTab === "log"
                    ? "text-white"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                Pipeline Log
                {leftTab === "log" && (
                  <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-cyan-500 to-blue-500" />
                )}
              </button>
            </div>

            {/* Tab content */}
            {leftTab === "assistant" ? (
              <div className="flex-1 flex flex-col overflow-hidden">
                {/* Chat messages */}
                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                  {chatMessages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-2xl px-4 py-3 text-[13px] leading-relaxed font-light ${
                          msg.role === "user"
                            ? "bg-cyan-500/20 border border-cyan-500/30 text-white"
                            : "bg-white/5 border border-white/10 text-gray-300"
                        }`}
                      >
                        {msg.content.split("\n").map((line, li) => (
                          <p key={li} className={li > 0 ? "mt-1.5" : ""}>
                            {line.split(/(\*\*[^*]+\*\*)/).map((part, pi) =>
                              part.startsWith("**") && part.endsWith("**") ? (
                                <span key={pi} className="text-white font-medium">
                                  {part.slice(2, -2)}
                                </span>
                              ) : (
                                <span key={pi}>{part}</span>
                              )
                            )}
                          </p>
                        ))}
                      </div>
                    </div>
                  ))}
                  <div ref={chatEndRef} />
                </div>

                {/* Chat input */}
                <form
                  onSubmit={handleChatSubmit}
                  className="flex-shrink-0 border-t border-white/10 p-4"
                >
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      placeholder="Ask about the diagnostics..."
                      className="flex-1 px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder-gray-600 focus:border-cyan-500/50 focus:outline-none font-light"
                    />
                    <button
                      type="submit"
                      disabled={!chatInput.trim()}
                      className="px-4 py-2.5 bg-cyan-500/20 border border-cyan-500/30 rounded-xl text-cyan-400 text-sm font-light hover:bg-cyan-500/30 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                      </svg>
                    </button>
                  </div>
                </form>
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto p-6">
                <div className="space-y-1">
                  {reasoning.map((entry, i) => (
                    <div key={`${entry.id}-${i}`} className="group">
                      <div className="flex items-center gap-2.5 py-2">
                        {entry.status === "running" && (
                          <div className="w-4 h-4 flex-shrink-0 flex items-center justify-center">
                            <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                          </div>
                        )}
                        {entry.status === "done" && (
                          <div className="w-4 h-4 flex-shrink-0 flex items-center justify-center">
                            <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          </div>
                        )}
                        {entry.status === "error" && (
                          <div className="w-4 h-4 flex-shrink-0 flex items-center justify-center">
                            <svg className="w-3.5 h-3.5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </div>
                        )}
                        <span
                          className={`text-sm font-medium ${
                            entry.status === "running"
                              ? "text-white"
                              : entry.status === "error"
                              ? "text-red-400"
                              : "text-gray-400"
                          }`}
                        >
                          {entry.title}
                        </span>
                      </div>

                      <div className="ml-[26px] pl-4 border-l border-white/5 pb-3">
                        <p
                          className={`text-[13px] leading-relaxed font-light ${
                            entry.status === "running"
                              ? "text-gray-300"
                              : "text-gray-500"
                          }`}
                        >
                          {entry.reasoning}
                        </p>
                      </div>
                    </div>
                  ))}

                  {error && (
                    <div className="mt-4 p-4 rounded-lg bg-red-500/10 border border-red-500/30">
                      <p className="text-sm text-red-400 font-light">{error}</p>
                    </div>
                  )}

                  {complete && (
                    <div className="mt-4 p-5 rounded-xl bg-gradient-to-br from-emerald-500/10 to-cyan-500/10 border border-emerald-500/30">
                      <h3 className="text-emerald-400 font-light mb-3">Pipeline Complete</h3>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <span className="text-gray-500">Model Type</span>
                          <p className="text-white font-light uppercase">{complete.summary.model_type as string}</p>
                        </div>
                        <div>
                          <span className="text-gray-500">Confidence</span>
                          <p className={`font-light capitalize ${
                            complete.summary.confidence_level === "high"
                              ? "text-emerald-400"
                              : complete.summary.confidence_level === "medium"
                              ? "text-amber-400"
                              : "text-red-400"
                          }`}>
                            {complete.summary.confidence_level as string}
                          </p>
                        </div>
                        <div>
                          <span className="text-gray-500">R²</span>
                          <p className="text-white font-light">{(complete.summary.r2 as number).toFixed(4)}</p>
                        </div>
                        <div>
                          <span className="text-gray-500">Adjusted R²</span>
                          <p className="text-white font-light">{(complete.summary.adjusted_r2 as number).toFixed(4)}</p>
                        </div>
                        {complete.summary.oos_r2 != null && (
                          <>
                            <div>
                              <span className="text-gray-500">OOS R²</span>
                              <p className="text-cyan-400 font-light">{(complete.summary.oos_r2 as number).toFixed(4)}</p>
                            </div>
                            <div>
                              <span className="text-gray-500">OOS RMSE</span>
                              <p className="text-cyan-400 font-light">{(complete.summary.oos_rmse as number).toFixed(2)}</p>
                            </div>
                          </>
                        )}
                      </div>
                      <div className="mt-4 pt-4 border-t border-white/10">
                        <button
                          onClick={() => router.push("/dashboard")}
                          className="w-full px-6 py-3 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-lg font-light tracking-wide hover:shadow-lg hover:shadow-emerald-500/30 transition-all duration-300"
                        >
                          View Dashboard
                        </button>
                      </div>
                    </div>
                  )}
                </div>
                <div ref={reasoningEndRef} />
              </div>
            )}
          </div>

          {/* Right: Test result cards */}
          <div className="w-[42%] overflow-y-auto p-6">
            <h2 className="text-xs uppercase tracking-widest text-gray-500 mb-4">
              Test Results
            </h2>
            <div className="space-y-3">
              {results.map((r, i) => {
                const cardKey = `${r.id}-${i}`;
                const isCollapsed = collapsedResults.has(cardKey);
                const toggleCollapsed = () => {
                  setCollapsedResults((prev) => {
                    const next = new Set(prev);
                    if (next.has(cardKey)) next.delete(cardKey);
                    else next.add(cardKey);
                    return next;
                  });
                };
                return (
                <div
                  key={cardKey}
                  className={`rounded-xl border backdrop-blur-sm animate-in fade-in slide-in-from-right-4 duration-300 overflow-hidden ${
                    STATUS_COLORS[r.status] || STATUS_COLORS.info
                  }`}
                  style={{ animationDelay: `${i * 50}ms` }}
                >
                  {/* Card header - clickable to collapse/expand */}
                  <button
                    type="button"
                    onClick={toggleCollapsed}
                    className="w-full p-4 flex items-center justify-between gap-2 text-left hover:opacity-90 transition-opacity"
                  >
                    <span className="text-sm font-medium">{r.title}</span>
                    <span className="flex items-center gap-2">
                      <span className="text-[10px] uppercase tracking-wider opacity-70">
                        {STATUS_LABELS[r.status] || r.status}
                      </span>
                      <svg
                        className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${isCollapsed ? "" : "rotate-180"}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                      </svg>
                    </span>
                  </button>

                  {/* Metrics - collapsible */}
                  {!isCollapsed && (
                  <div className="px-4 pb-4 pt-0 space-y-1.5">
                    {Object.entries(r.metrics).map(([key, value]) => {
                      if (key === "top_anomalies" && Array.isArray(value)) {
                        if (value.length === 0) return null;
                        return (
                          <div key={key} className="mt-2">
                            <span className="text-[11px] text-gray-400 uppercase tracking-wider">
                              Top Anomalies
                            </span>
                            <div className="mt-1 space-y-1">
                              {(value as Array<Record<string, unknown>>).map((a, ai) => (
                                <div key={ai} className="text-[11px] text-gray-300 font-mono">
                                  {a.ts as string} · z={formatMetricValue(a.z_score)} · {a.direction as string}
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      }

                      if (key === "feature_names" && Array.isArray(value)) {
                        return (
                          <div key={key}>
                            <span className="text-[11px] text-gray-400">{formatMetricKey(key)}</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {(value as string[]).map((f) => (
                                <span
                                  key={f}
                                  className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-gray-300 font-mono"
                                >
                                  {f}
                                </span>
                              ))}
                            </div>
                          </div>
                        );
                      }

                      if (key === "decision") {
                        return (
                          <div key={key} className="mt-1.5 pt-1.5 border-t border-white/5">
                            <p className="text-[12px] font-light opacity-90">
                              {formatMetricValue(value)}
                            </p>
                          </div>
                        );
                      }

                      if (
                        typeof value === "object" &&
                        value !== null &&
                        !Array.isArray(value)
                      ) {
                        return (
                          <div key={key}>
                            <span className="text-[11px] text-gray-400 uppercase tracking-wider">
                              {formatMetricKey(key)}
                            </span>
                            <div className="mt-1 space-y-1">
                              {Object.entries(value as Record<string, unknown>).map(
                                ([subKey, subVal]) => (
                                  <div
                                    key={subKey}
                                    className="flex justify-between text-[12px]"
                                  >
                                    <span className="text-gray-400 font-light">
                                      {formatMetricKey(subKey)}
                                    </span>
                                    <span className="font-mono text-gray-200">
                                      {formatMetricValue(subVal)}
                                    </span>
                                  </div>
                                )
                              )}
                            </div>
                          </div>
                        );
                      }

                      return (
                        <div key={key} className="flex justify-between text-[12px]">
                          <span className="text-gray-400 font-light">
                            {formatMetricKey(key)}
                          </span>
                          <span className="font-mono text-gray-200">
                            {formatMetricValue(value)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  )}
                </div>
                );
              })}

              {/* Loading placeholder while streaming */}
              {!complete && !error && results.length > 0 && (
                <div className="flex items-center gap-2 py-3 px-4 text-gray-500 text-xs">
                  <div className="w-1.5 h-1.5 rounded-full bg-cyan-400/50 animate-pulse" />
                  Waiting for next result...
                </div>
              )}

              {results.length === 0 && !error && (
                <div className="text-center py-12 text-gray-600 text-sm font-light">
                  Results will appear here as each test completes...
                </div>
              )}
            </div>
            <div ref={resultsEndRef} />
          </div>
        </div>
      </main>
    </div>
  );
}

export default function RunPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen bg-[#0B0F14] text-white items-center justify-center">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-gray-400 font-light">Initializing pipeline...</span>
          </div>
        </div>
      }
    >
      <RunPageInner />
    </Suspense>
  );
}
