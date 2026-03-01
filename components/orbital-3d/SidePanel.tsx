"use client";

import { VARIABLES } from "./data";

interface SidePanelProps {
  selectedId: string | null;
  onClose: () => void;
}

export function SidePanel({ selectedId, onClose }: SidePanelProps) {
  const variable = VARIABLES.find((v) => v.id === selectedId);
  const isOpen = variable != null;

  return (
    <div
      className={`absolute top-0 right-0 h-full w-80 z-[16777280] transition-transform duration-500 ease-out ${
        isOpen ? "translate-x-0" : "translate-x-full"
      }`}
    >
      {variable && (
        <div className="h-full p-6 bg-black/60 backdrop-blur-xl border-l border-white/10 overflow-y-auto">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 text-gray-500 hover:text-white transition-colors text-sm"
          >
            Close
          </button>

          <div
            className="w-3 h-3 rounded-full mb-4 mt-2"
            style={{ backgroundColor: variable.color }}
          />
          <h3 className="text-xl font-light text-white mb-1">
            {variable.label}
          </h3>
          <p className="text-xs text-gray-500 uppercase tracking-widest mb-6">
            {variable.group === "paidMedia"
              ? "Paid Media"
              : variable.group === "funnel"
              ? "Funnel"
              : variable.group === "demand"
              ? "Demand"
              : "Events & Shocks"}
          </p>

          <div className="space-y-3">
            {variable.panelCopy.map((line, i) => (
              <div key={i} className="flex items-start gap-2.5">
                <div
                  className="w-1 h-1 rounded-full mt-2 flex-shrink-0"
                  style={{ backgroundColor: variable.color, opacity: 0.6 }}
                />
                <p className="text-sm text-gray-400 font-light leading-relaxed">
                  {line}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
