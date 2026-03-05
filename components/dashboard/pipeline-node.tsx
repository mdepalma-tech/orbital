"use client";

import { memo } from "react";
import { Handle, Position } from "@xyflow/react";

interface PipelineNodeData {
  step_number: string;
  name: string;
  description: string;
  module_path: string;
  function_name: string;
  inputs: string[];
  outputs: string[];
  parameters?: Record<string, unknown>;
  branch_condition?: string | null;
  function_signature?: string | null;
  line_number?: number | null;
  sectionColor: "blue" | "violet";
  isChild?: boolean;
  hasBranch?: boolean;
  expanded?: boolean;
  onToggleExpand?: () => void;
}

const COLORS = {
  blue: {
    badge: "bg-blue-500/20 text-blue-300 border border-blue-500/30",
    border: "border-blue-500/20 hover:border-blue-500/40",
  },
  violet: {
    badge: "bg-violet-500/20 text-violet-300 border border-violet-500/30",
    border: "border-violet-500/20 hover:border-violet-500/40",
  },
};

export const PipelineNode = memo(function PipelineNode({
  data,
}: {
  data: PipelineNodeData;
}) {
  const {
    step_number,
    name,
    description,
    module_path,
    function_name,
    inputs,
    outputs,
    parameters,
    branch_condition,
    function_signature,
    line_number,
    sectionColor,
    isChild,
    hasBranch,
    expanded,
    onToggleExpand,
  } = data;

  const colors = COLORS[sectionColor] || COLORS.blue;

  return (
    <div
      className={`
        w-[320px] rounded-xl border bg-gradient-to-br from-white/[0.06] to-white/[0.02]
        backdrop-blur-sm transition-all duration-200
        ${colors.border}
        ${isChild ? "opacity-90 w-[280px]" : ""}
        ${expanded ? "shadow-lg shadow-black/30" : "hover:shadow-md hover:shadow-black/20"}
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-gray-600 !w-2 !h-2 !border-0"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-gray-600 !w-2 !h-2 !border-0"
      />

      {/* Header — always visible */}
      <div
        className="flex items-center gap-3 p-4 cursor-pointer select-none"
        onClick={onToggleExpand}
      >
        <div
          className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-medium ${colors.badge}`}
        >
          {step_number}
        </div>

        <div className="flex-1 min-w-0">
          <div className="text-sm text-white font-light truncate">{name}</div>
          <div className="text-[11px] text-gray-500 font-light truncate">
            {module_path}
            {line_number != null ? `:${line_number}` : ""}
          </div>
        </div>

        {hasBranch && (
          <div className="flex-shrink-0 w-5 h-5 rounded flex items-center justify-center bg-amber-500/10 text-amber-400 text-[10px]">
            &#x2442;
          </div>
        )}

        <svg
          className={`flex-shrink-0 w-4 h-4 text-gray-500 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-white/5 pt-3">
          <p className="text-xs text-gray-400 font-light leading-relaxed">
            {description}
          </p>

          {function_signature && (
            <div className="p-2 rounded-lg bg-black/30 border border-white/5 overflow-x-auto">
              <code className="text-[11px] text-cyan-300/80 font-mono whitespace-pre-wrap break-all">
                {function_signature}
              </code>
            </div>
          )}

          {inputs && inputs.length > 0 && (
            <div>
              <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wider">
                Inputs
              </div>
              <div className="flex flex-wrap gap-1">
                {inputs.map((inp: string, i: number) => (
                  <span
                    key={i}
                    className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400/80 border border-emerald-500/20"
                  >
                    {inp}
                  </span>
                ))}
              </div>
            </div>
          )}

          {outputs && outputs.length > 0 && (
            <div>
              <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wider">
                Outputs
              </div>
              <div className="flex flex-wrap gap-1">
                {outputs.map((out: string, i: number) => (
                  <span
                    key={i}
                    className="px-1.5 py-0.5 rounded text-[10px] bg-blue-500/10 text-blue-400/80 border border-blue-500/20"
                  >
                    {out}
                  </span>
                ))}
              </div>
            </div>
          )}

          {parameters && Object.keys(parameters).length > 0 && (
            <div>
              <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wider">
                Parameters
              </div>
              <div className="p-2 rounded-lg bg-black/20 text-[10px] text-gray-400 font-mono space-y-0.5">
                {Object.entries(parameters).map(([k, v]) => (
                  <div key={k} className="break-all">
                    <span className="text-gray-500">{k}:</span>{" "}
                    <span className="text-gray-300">
                      {typeof v === "object" ? JSON.stringify(v) : String(v)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {branch_condition && (
            <div className="p-2 rounded-lg bg-amber-500/5 border border-amber-500/20">
              <div className="text-[11px] text-amber-400/80 font-light break-all">
                <span className="text-amber-500 font-medium">Branch: </span>
                {branch_condition}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
});
