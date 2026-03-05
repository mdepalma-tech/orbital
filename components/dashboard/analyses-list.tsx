"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { randomUUID } from "@/lib/utils";

interface Analysis {
  id: string;
  projectId: string;
  name: string;
  created_at: string;
  status: "running" | "complete" | "error";
  metrics: {
    revenue_impact: string;
    roi: string;
    confidence: string;
  };
}

export function AnalysesList({ userId }: { userId: string }) {
  const router = useRouter();
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/analyses")
      .then((r) => r.json())
      .then((d) => setAnalyses(d?.analyses ?? []))
      .catch(() => setAnalyses([]))
      .finally(() => setLoading(false));
  }, [userId]);

  function startNewModel() {
    router.push(`/dashboard/build?projectId=${randomUUID()}`);
  }

  if (loading) {
    return (
      <div className="flex justify-center min-h-[300px] items-center">
        <div className="w-8 h-8 border-2 border-violet-500/50 border-t-violet-400 rounded-full animate-spin" />
      </div>
    );
  }

  if (analyses.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[500px]">
        <div className="text-center max-w-md">
          {/* Empty State Orbital Visual */}
          <div className="relative w-48 h-48 mx-auto mb-8">
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-24 h-24 rounded-full bg-gradient-to-br from-blue-500/20 to-violet-500/20 border border-blue-500/30 flex items-center justify-center">
                <div className="text-4xl">🧠</div>
              </div>
            </div>
            <div className="absolute inset-0 border-2 border-dashed border-white/10 rounded-full animate-spin-slow" />
          </div>

          <h2 className="text-2xl font-light mb-4">No Analyses Yet</h2>
          <p className="text-gray-400 font-light mb-8 leading-relaxed">
            Start building your first causal intelligence model to understand what truly drives your revenue.
          </p>

          <button
            onClick={startNewModel}
            className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-blue-500 to-violet-500 rounded-lg font-light tracking-wide hover:shadow-lg hover:shadow-blue-500/50 transition-all duration-300 hover:scale-105"
          >
            <span>Build a Model</span>
            <span className="text-xl">→</span>
          </button>
        </div>
      </div>
    );
  }

  // If there are analyses, show them in a grid
  return (
    <div>
      {/* Build New Button */}
      <div className="mb-6">
        <button
          onClick={startNewModel}
          className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-500 to-violet-500 rounded-lg font-light tracking-wide hover:shadow-lg hover:shadow-blue-500/50 transition-all duration-300"
        >
          <span>+ Build New Model</span>
        </button>
      </div>

      {/* Analyses Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {analyses.map((analysis) => (
          <Link
            key={analysis.id}
            href={`/dashboard/build/run?projectId=${analysis.projectId ?? analysis.id}`}
            className="group p-6 rounded-xl border border-white/10 bg-gradient-to-br from-white/5 to-transparent backdrop-blur-sm hover:border-blue-500/50 hover:shadow-lg hover:shadow-blue-500/20 transition-all duration-300"
          >
            <div className="flex items-start justify-between mb-4">
              <h3 className="text-lg font-light">{analysis.name}</h3>
              <span
                className={`px-2 py-1 text-xs rounded-full ${
                  analysis.status === "running"
                    ? "bg-blue-500/20 text-blue-400"
                    : analysis.status === "complete"
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "bg-red-500/20 text-red-400"
                }`}
              >
                {analysis.status}
              </span>
            </div>

            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Revenue Impact</span>
                <span className="text-emerald-400">{analysis.metrics.revenue_impact}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">ROI</span>
                <span className="text-blue-400">{analysis.metrics.roi}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Confidence</span>
                <span className="text-violet-400">{analysis.metrics.confidence}</span>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-white/5 text-xs text-gray-500">
              Created {new Date(analysis.created_at).toLocaleDateString()}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
