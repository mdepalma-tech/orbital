"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { OrdersUploadSection } from "@/components/dashboard/orders-upload-section";

interface BuildFormProps {
  projectId: string;
}

export function BuildForm({ projectId }: BuildFormProps) {
  const router = useRouter();
  const [analysisName, setAnalysisName] = useState("");
  const [loadingName, setLoadingName] = useState(true);

  useEffect(() => {
    fetch(`/api/projects/${projectId}`)
      .then((r) => r.json())
      .then((d) => {
        if (d?.name) setAnalysisName(d.name);
      })
      .catch(() => {})
      .finally(() => setLoadingName(false));
  }, [projectId]);

  const [saving, setSaving] = useState(false);

  const saveName = async (nameToSave: string) => {
    const name = nameToSave.trim() || "Untitled Analysis";
    const res = await fetch(`/api/projects/${projectId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
      credentials: "include",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      console.error("[BuildForm] PATCH /api/projects failed:", res.status, err);
    }
    return res.ok;
  };

  const handleNext = async () => {
    setSaving(true);
    try {
      await saveName(analysisName);
    } finally {
      setSaving(false);
    }
    router.push(`/dashboard/build/ad-spend?projectId=${projectId}`);
  };

  return (
    <div className="space-y-6">
      <div className="p-6 rounded-xl border border-white/10 bg-gradient-to-br from-white/5 to-transparent">
        <label className="block mb-4">
          <span className="text-sm text-gray-400 font-light">Analysis Name</span>
          <input
            type="text"
            value={analysisName}
            onChange={(e) => setAnalysisName(e.target.value)}
            onBlur={() => {
              if (analysisName.trim()) saveName(analysisName);
            }}
            placeholder="e.g., Q1 2024 Revenue Analysis"
            disabled={loadingName}
            className="mt-2 w-full px-4 py-3 bg-black/40 border border-white/10 rounded-lg text-white placeholder-gray-600 focus:border-blue-500/50 focus:outline-none font-light disabled:opacity-50"
          />
        </label>
        <p className="text-xs text-gray-500 font-light">
          Give your analysis a descriptive name for easy reference
        </p>
      </div>

      <div className="p-6 rounded-xl border border-white/10 bg-gradient-to-br from-white/5 to-transparent">
        <div className="mb-4">
          <h3 className="text-lg font-light mb-2">Upload Shopify Orders</h3>
          <p className="text-sm text-gray-400 font-light">
            Upload your Shopify orders export to analyze revenue patterns and order trends
          </p>
        </div>
        <OrdersUploadSection projectId={projectId} />
      </div>

      <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/30">
        <p className="text-sm text-blue-300 font-light">
          💡 <strong>Next steps:</strong> After uploading your orders data, we'll add channel spend data and run the causal analysis to identify what truly drives your revenue.
        </p>
      </div>

      <div className="flex gap-4 pt-4">
        <a
          href="/dashboard"
          className="px-8 py-4 border border-white/20 rounded-lg font-light tracking-wide hover:bg-white/5 transition-all duration-300 text-center"
        >
          Cancel
        </a>
        <button
          onClick={handleNext}
          disabled={saving}
          className="flex-1 px-8 py-4 bg-gradient-to-r from-blue-500 to-violet-500 backdrop-blur-md border border-white/20 rounded-lg font-light tracking-wide hover:shadow-lg hover:shadow-blue-500/50 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? "Saving..." : "Next: Upload Ad Spend"}
        </button>
      </div>
    </div>
  );
}
