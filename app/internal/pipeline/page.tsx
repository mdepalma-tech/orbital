"use client";

import { useEffect, useState } from "react";
import { PipelineTreeGraph } from "@/components/dashboard/pipeline-tree";

interface PipelineNodeData {
  step_id: string;
  step_number: string;
  name: string;
  description: string;
  module_path: string;
  function_name: string;
  inputs: string[];
  outputs: string[];
  parameters?: Record<string, unknown>;
  children?: PipelineNodeData[];
  branch_condition?: string | null;
  function_signature?: string | null;
  line_number?: number | null;
}

interface PipelineTreeData {
  version: string;
  source_hash: string;
  pipeline_name: string;
  entry_point: string;
  steps: PipelineNodeData[];
  forecast_steps: PipelineNodeData[];
}

export default function PipelinePage() {
  const [treeData, setTreeData] = useState<PipelineTreeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<"modeling" | "forecast">(
    "modeling",
  );

  useEffect(() => {
    fetch("/api/pipeline/tree")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: PipelineTreeData) => setTreeData(data))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col h-screen bg-[#0B0F14] text-white overflow-hidden">
      {/* Header */}
      <div className="px-8 pt-6 pb-4 flex-shrink-0 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-light tracking-wide">
              Pipeline Tree
            </h1>
            <p className="text-sm text-gray-500 font-light mt-1">
              {treeData
                ? `${treeData.pipeline_name} \u00b7 ${treeData.source_hash.slice(0, 12)}...`
                : "Modeling pipeline structure and data flow"}
            </p>
          </div>

          {treeData && (
            <div className="flex gap-2">
              <button
                onClick={() => setActiveSection("modeling")}
                className={`px-4 py-2 rounded-lg text-sm font-light transition-all ${
                  activeSection === "modeling"
                    ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                    : "text-gray-400 hover:text-white hover:bg-white/5 border border-transparent"
                }`}
              >
                Modeling ({treeData.steps.length} steps)
              </button>
              <button
                onClick={() => setActiveSection("forecast")}
                className={`px-4 py-2 rounded-lg text-sm font-light transition-all ${
                  activeSection === "forecast"
                    ? "bg-violet-500/20 text-violet-300 border border-violet-500/30"
                    : "text-gray-400 hover:text-white hover:bg-white/5 border border-transparent"
                }`}
              >
                Forecast ({treeData.forecast_steps.length} steps)
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Graph area */}
      <div className="flex-1 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="w-8 h-8 border-2 border-violet-500/50 border-t-violet-400 rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full">
            <div className="p-6 rounded-xl border border-red-500/30 bg-red-500/10 max-w-md text-center">
              <p className="text-red-400 font-light">
                Failed to load pipeline tree
              </p>
              <p className="text-gray-500 text-sm mt-2">{error}</p>
              <p className="text-gray-600 text-xs mt-3">
                Make sure the backend is running at localhost:8000
              </p>
            </div>
          </div>
        ) : treeData ? (
          <PipelineTreeGraph
            steps={
              activeSection === "modeling"
                ? treeData.steps
                : treeData.forecast_steps
            }
            entryPoint={
              activeSection === "modeling"
                ? treeData.entry_point
                : "routers/models.py :: forecast()"
            }
            section={activeSection}
          />
        ) : null}
      </div>
    </div>
  );
}
