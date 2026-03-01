"use client";

import { useState, useRef } from "react";

interface ParseSummary {
  dateRange: { start: string; end: string };
  totalDays: number;
  totalRows: number;
  includedRows: number;
  excludedRows: number;
  totalSpend: number;
  averageDailySpend: number;
  breakdownTotals?: Record<string, number>;
}

interface ApiResponse {
  status: "success" | "preview" | "error";
  message?: string;
  summary?: ParseSummary;
  warnings?: string[];
}

type Stage = "upload" | "parsing" | "preview" | "saving" | "saved" | "error";

const BREAKDOWN_LABELS: Record<string, string> = {
  search_total: "Search",
  pmax_total: "Performance Max",
  other_total: "Other",
  search_brand_total: "Search (Brand)",
  search_nonbrand_total: "Search (Non-Brand)",
};

export function GoogleAdsUploadSection({ projectId }: { projectId: string }) {
  const [stage, setStage] = useState<Stage>("upload");
  const [summary, setSummary] = useState<ParseSummary | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [brandTerms, setBrandTerms] = useState("");
  const formRef = useRef<HTMLFormElement>(null);

  async function handleParse(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStage("parsing");
    setError(null);
    setWarnings([]);
    setSummary(null);

    const formData = new FormData(e.currentTarget);
    formData.set("mode", "preview");
    if (brandTerms.trim()) formData.set("brand_terms", brandTerms.trim());

    try {
      const response = await fetch(
        `/api/projects/${projectId}/upload-google-ads`,
        { method: "POST", body: formData }
      );
      const data: ApiResponse = await response.json();

      if (data.status === "preview" && data.summary) {
        setSummary(data.summary);
        setWarnings(data.warnings ?? []);
        setStage("preview");
      } else if (data.status === "error") {
        setError(data.message || "Parsing failed");
        setStage("error");
      }
    } catch {
      setError("Failed to connect to server. Please try again.");
      setStage("error");
    }
  }

  async function handleConfirmSave() {
    if (!formRef.current || !selectedFile) return;
    setStage("saving");

    const formData = new FormData();
    formData.set("file", selectedFile);
    formData.set("mode", "save");
    if (brandTerms.trim()) formData.set("brand_terms", brandTerms.trim());

    try {
      const response = await fetch(
        `/api/projects/${projectId}/upload-google-ads`,
        { method: "POST", body: formData }
      );
      const data: ApiResponse = await response.json();

      if (data.status === "success" && data.summary) {
        setSummary(data.summary);
        setWarnings(data.warnings ?? []);
        setStage("saved");
      } else if (data.status === "error") {
        setError(data.message || "Save failed");
        setStage("error");
      }
    } catch {
      setError("Failed to save data. Please try again.");
      setStage("error");
    }
  }

  function handleReset() {
    setStage("upload");
    setSummary(null);
    setWarnings([]);
    setError(null);
    setSelectedFile(null);
    formRef.current?.reset();
    setBrandTerms("");
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    setSelectedFile(file || null);
    setError(null);
    setSummary(null);
    if (stage !== "upload") setStage("upload");
  }

  const hasWarnings = warnings.length > 0;
  const canSave = !!summary;

  return (
    <div className="space-y-4">
      <form ref={formRef} onSubmit={handleParse} className="space-y-4">
        <div>
          <label className="block mb-2">
            <span className="text-sm text-gray-400 font-light">
              Google Ads Campaign Export CSV
            </span>
            <div className="mt-2">
              <input
                type="file"
                name="file"
                accept=".csv"
                required
                onChange={handleFileChange}
                disabled={stage === "parsing" || stage === "saving"}
                className="w-full px-4 py-3 bg-black/40 border border-white/10 rounded-lg text-white file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-light file:bg-blue-500 file:text-white hover:file:bg-blue-600 file:cursor-pointer focus:border-blue-500/50 focus:outline-none font-light disabled:opacity-50"
              />
            </div>
            <p className="mt-2 text-xs text-gray-500 font-light">
              Campaign-level export segmented by day. Requires: day/date, cost, campaign columns.
            </p>
          </label>
        </div>

        <div>
          <label className="block mb-2">
            <span className="text-sm text-gray-400 font-light">
              Brand terms <span className="text-gray-500">(optional)</span>
            </span>
            <input
              type="text"
              name="brand_terms"
              value={brandTerms}
              onChange={(e) => setBrandTerms(e.target.value)}
              placeholder="e.g. brand, company name"
              className="mt-2 w-full px-4 py-2.5 bg-black/40 border border-white/10 rounded-lg text-white placeholder:text-gray-500 focus:border-blue-500/50 focus:outline-none font-light"
            />
            <p className="mt-1 text-xs text-gray-500 font-light">
              Comma-separated. Used to split Search spend into brand vs non-brand.
            </p>
          </label>
        </div>

        {(stage === "upload" || stage === "error") && (
          <button
            type="submit"
            disabled={!selectedFile || stage === "parsing"}
            className="w-full px-8 py-4 border border-blue-500/50 bg-blue-500/10 text-blue-300 rounded-lg font-light tracking-wide hover:bg-blue-500/20 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Parse & Preview CSV
          </button>
        )}
      </form>

      {stage === "parsing" && (
        <div className="flex flex-col items-center justify-center py-12 gap-4">
          <svg className="animate-spin h-10 w-10 text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <p className="text-gray-400 font-light animate-pulse">Parsing Google Ads CSV...</p>
        </div>
      )}

      {stage === "saving" && (
        <div className="flex flex-col items-center justify-center py-12 gap-4">
          <svg className="animate-spin h-10 w-10 text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <p className="text-gray-400 font-light animate-pulse">Saving to database...</p>
        </div>
      )}

      {stage === "preview" && summary && (
        <div className="p-6 rounded-xl border border-blue-500/30 bg-blue-500/5 space-y-5">
          <div className="flex items-center gap-2 text-blue-400">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <span className="text-lg font-light">Google Ads Parse Summary</span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="p-3 rounded-lg bg-black/30 border border-white/5">
              <p className="text-gray-500 text-xs font-light mb-1">Start Date</p>
              <p className="text-white font-mono">{summary.dateRange.start}</p>
            </div>
            <div className="p-3 rounded-lg bg-black/30 border border-white/5">
              <p className="text-gray-500 text-xs font-light mb-1">End Date</p>
              <p className="text-white font-mono">{summary.dateRange.end}</p>
            </div>
            <div className="p-3 rounded-lg bg-black/30 border border-white/5">
              <p className="text-gray-500 text-xs font-light mb-1">Total Rows in CSV</p>
              <p className="text-white text-lg">{summary.totalRows.toLocaleString()}</p>
            </div>
            <div className="p-3 rounded-lg bg-black/30 border border-white/5">
              <p className="text-gray-500 text-xs font-light mb-1">Included Rows</p>
              <p className="text-white text-lg">{summary.includedRows.toLocaleString()}</p>
            </div>
            <div className="p-3 rounded-lg bg-black/30 border border-white/5">
              <p className="text-gray-500 text-xs font-light mb-1">Distinct Days</p>
              <p className="text-white text-lg">{summary.totalDays.toLocaleString()}</p>
            </div>
            <div className="p-3 rounded-lg bg-black/30 border border-white/5">
              <p className="text-gray-500 text-xs font-light mb-1">Total Google Spend</p>
              <p className="text-blue-400 text-lg">
                ${summary.totalSpend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
            <div className="p-3 rounded-lg bg-black/30 border border-white/5">
              <p className="text-gray-500 text-xs font-light mb-1">Avg Daily Spend</p>
              <p className="text-blue-400 text-lg">
                ${summary.averageDailySpend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
          </div>

          {summary.breakdownTotals && Object.keys(summary.breakdownTotals).length > 0 && (
            <div className="p-3 rounded-lg bg-black/30 border border-white/5">
              <p className="text-gray-500 text-xs font-light mb-3">Spend by Channel Type</p>
              <div className="space-y-2">
                {Object.entries(summary.breakdownTotals).map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="px-3 py-1 rounded-full text-xs font-light bg-blue-500/20 text-blue-300 border border-blue-500/30">
                      {BREAKDOWN_LABELS[key] ?? key}
                    </span>
                    <span className="text-sm text-white font-mono">
                      ${(val ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {hasWarnings && (
            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 space-y-1">
              {warnings.map((w, i) => (
                <p key={i} className="text-sm text-amber-300 font-light">
                  {w}
                </p>
              ))}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={handleConfirmSave}
              disabled={!canSave}
              className="flex-1 px-6 py-3 bg-gradient-to-r from-blue-500 to-cyan-500 rounded-lg font-light tracking-wide hover:shadow-lg hover:shadow-blue-500/50 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Confirm & Save
            </button>
            <button
              type="button"
              onClick={handleReset}
              className="px-6 py-3 border border-white/20 rounded-lg font-light tracking-wide hover:bg-white/5 transition-all duration-300"
            >
              Re-upload
            </button>
          </div>
        </div>
      )}

      {stage === "saved" && summary && (
        <div className="p-6 rounded-xl border border-emerald-500/30 bg-emerald-500/5 space-y-4">
          <div className="flex items-center gap-2 text-emerald-400">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-lg font-light">Google Spend Saved Successfully</span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="p-3 rounded-lg bg-black/30 border border-white/5">
              <p className="text-gray-500 text-xs font-light mb-1">Date Range</p>
              <p className="text-white font-mono text-sm">{summary.dateRange.start} → {summary.dateRange.end}</p>
            </div>
            <div className="p-3 rounded-lg bg-black/30 border border-white/5">
              <p className="text-gray-500 text-xs font-light mb-1">Days Stored</p>
              <p className="text-white text-lg">{summary.totalDays}</p>
            </div>
            <div className="p-3 rounded-lg bg-black/30 border border-white/5">
              <p className="text-gray-500 text-xs font-light mb-1">Total Google Spend</p>
              <p className="text-blue-400 text-lg">
                ${summary.totalSpend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/30">
            <p className="text-sm text-blue-300 font-light">
              Google Ads spend has been stored in the google_spend column. You can combine with other channel uploads or run your causal analysis.
            </p>
          </div>

          <button
            type="button"
            onClick={handleReset}
            className="w-full px-6 py-3 border border-white/20 rounded-lg font-light tracking-wide hover:bg-white/5 transition-all duration-300 text-gray-400"
          >
            Upload Different File
          </button>
        </div>
      )}

      {stage === "error" && error && (
        <div className="p-6 rounded-xl border border-red-500/30 bg-red-500/5 space-y-3">
          <div className="flex items-center gap-2 text-red-400">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-lg font-light">Upload Failed</span>
          </div>
          <p className="text-red-300 font-light">{error}</p>
          <div className="p-3 rounded-lg bg-black/20 text-xs text-gray-400 font-light">
            <p className="font-medium text-gray-300 mb-2">Expected Google Ads CSV format:</p>
            <ul className="list-disc list-inside space-y-1">
              <li>Required: day/date, cost (or amount_spent, spend), campaign</li>
              <li>Optional: advertising_channel_type for Search / PMax / Other split</li>
              <li>Campaign-level export segmented by day</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
