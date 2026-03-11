"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { randomUUID } from "@/lib/utils";
import GridLayout, { useContainerWidth, type Layout } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import { DashboardWidget } from "./dashboard-widget";

interface Analysis {
  id: string;
  projectId: string;
  name: string;
  status: string;
  metrics: { revenue_impact: string; roi: string; confidence: string };
  created_at: string;
}

interface Dashboard {
  id: string;
  name: string;
  is_default: boolean;
  created_at: string;
  widgets?: { id: string; project_id: string; x: number; y: number; w: number; h: number }[];
}

export function DashboardContent() {
  const router = useRouter();
  const { width, containerRef, mounted } = useContainerWidth();
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDashboard, setSelectedDashboard] = useState<Dashboard | null>(null);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [createDashboardModal, setCreateDashboardModal] = useState(false);
  const [newDashboardName, setNewDashboardName] = useState("");

  const fetchAnalyses = useCallback(() => {
    fetch("/api/analyses")
      .then((r) => r.json())
      .then((d) => setAnalyses(d?.analyses ?? []))
      .catch(() => setAnalyses([]));
  }, []);

  const fetchDashboards = useCallback(() => {
    fetch("/api/dashboards")
      .then((r) => r.json())
      .then((d) => {
        const list = d?.dashboards ?? [];
        setDashboards(list);
        const def = list.find((x: Dashboard) => x.is_default) ?? list[0];
        if (def) {
          fetch(`/api/dashboards/${def.id}`)
            .then((r) => r.json())
            .then((full) => setSelectedDashboard(full))
            .catch(() => setSelectedDashboard({ ...def, widgets: [] }));
        } else {
          setSelectedDashboard(null);
        }
      })
      .catch(() => {
        setDashboards([]);
        setSelectedDashboard(null);
      });
  }, []);

  useEffect(() => {
    Promise.all([
      fetch("/api/analyses").then((r) => r.json()),
      fetch("/api/dashboards").then((r) => r.json()),
    ])
      .then(([aRes, dRes]) => {
        const aList = aRes?.analyses ?? [];
        setAnalyses(aList);
        const dList = dRes?.dashboards ?? [];
        setDashboards(dList);
        const def = dList.find((x: Dashboard) => x.is_default) ?? dList[0];
        if (def) {
          return fetch(`/api/dashboards/${def.id}`)
            .then((r) => r.json())
            .then((full) => setSelectedDashboard(full));
        }
        setSelectedDashboard(null);
      })
      .catch(() => {
        setAnalyses([]);
        setDashboards([]);
        setSelectedDashboard(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const switchDashboard = useCallback((d: Dashboard) => {
    fetch(`/api/dashboards/${d.id}`)
      .then((r) => r.json())
      .then((full) => setSelectedDashboard(full))
      .catch(() => setSelectedDashboard({ ...d, widgets: [] }));
  }, []);

  const handleCreateDashboard = useCallback(() => {
    const name = newDashboardName.trim() || "New Dashboard";
    fetch("/api/dashboards", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.id) {
          setCreateDashboardModal(false);
          setNewDashboardName("");
          fetchDashboards();
        }
      })
      .catch(() => {});
  }, [newDashboardName, fetchDashboards]);

  const handleAddAnalysis = useCallback(
    (projectId: string) => {
      if (!selectedDashboard) return;
      fetch(`/api/dashboards/${selectedDashboard.id}/widgets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          x: 0,
          y: (selectedDashboard.widgets?.length ?? 0) * 2,
          w: 2,
          h: 1,
        }),
      })
        .then((r) => {
          if (r.ok) return r.json();
          throw new Error("Failed");
        })
        .then(() => {
          setAddModalOpen(false);
          fetch(`/api/dashboards/${selectedDashboard.id}`)
            .then((r) => r.json())
            .then((full) => setSelectedDashboard(full));
        })
        .catch(() => {});
    },
    [selectedDashboard]
  );

  const handleLayoutChange = useCallback(
    (layout: Layout) => {
      if (!selectedDashboard) return;
      layout.forEach((item) => {
        fetch(`/api/dashboards/${selectedDashboard.id}/widgets/${item.i}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            x: item.x,
            y: item.y,
            w: item.w,
            h: item.h,
          }),
        }).catch(() => {});
      });
    },
    [selectedDashboard]
  );

  const handleRemoveWidget = useCallback(
    (widgetId: string) => {
      if (!selectedDashboard) return;
      fetch(`/api/dashboards/${selectedDashboard.id}/widgets/${widgetId}`, {
        method: "DELETE",
      })
        .then(() => {
          fetch(`/api/dashboards/${selectedDashboard.id}`)
            .then((r) => r.json())
            .then((full) => setSelectedDashboard(full));
        })
        .catch(() => {});
    },
    [selectedDashboard]
  );

  const startNewModel = () => router.push(`/dashboard/build?projectId=${randomUUID()}`);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="w-8 h-8 border-2 border-violet-500/50 border-t-violet-400 rounded-full animate-spin" />
      </div>
    );
  }

  // No analyses: show empty state
  if (analyses.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[500px]">
        <div className="text-center max-w-md">
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

  // Has analyses, no dashboards: center buttons
  if (dashboards.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[500px] gap-6">
        <h2 className="text-2xl font-light">Create Your First Dashboard</h2>
        <p className="text-gray-400 font-light text-center max-w-md">
          Add a dashboard to arrange your analyses and track forecasts.
        </p>
        <div className="flex flex-wrap gap-4 justify-center">
          <button
            onClick={startNewModel}
            className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-blue-500 to-violet-500 rounded-lg font-light tracking-wide hover:shadow-lg hover:shadow-blue-500/50 transition-all duration-300"
          >
            <span>Build New Model</span>
            <span className="text-xl">→</span>
          </button>
          <button
            onClick={() => setCreateDashboardModal(true)}
            className="inline-flex items-center gap-2 px-8 py-4 border border-violet-500/50 rounded-lg font-light tracking-wide text-violet-300 hover:bg-violet-500/10 transition-all duration-300"
          >
            <span>Build New Dashboard</span>
          </button>
        </div>

        {createDashboardModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="p-6 rounded-xl border border-white/10 bg-[#0B0F14] max-w-sm w-full mx-4">
              <h4 className="text-lg font-light text-white mb-4">New Dashboard</h4>
              <input
                type="text"
                value={newDashboardName}
                onChange={(e) => setNewDashboardName(e.target.value)}
                placeholder="e.g. Revenue Overview"
                className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 font-light focus:border-violet-500/50 focus:outline-none mb-4"
              />
              <div className="flex gap-3">
                <button
                  onClick={() => setCreateDashboardModal(false)}
                  className="flex-1 px-4 py-2 border border-white/20 rounded-lg text-gray-400 font-light hover:bg-white/5"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateDashboard}
                  className="flex-1 px-4 py-2 bg-violet-500/30 border border-violet-500/40 rounded-lg text-violet-300 font-light hover:bg-violet-500/40"
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Has analyses and dashboards: show toggle + grid
  const layout = (selectedDashboard?.widgets ?? []).map((w) => ({
    i: w.id,
    x: w.x,
    y: w.y,
    w: w.w,
    h: w.h,
  }));

  const usedProjectIds = new Set((selectedDashboard?.widgets ?? []).map((w) => w.project_id));
  const availableAnalyses = analyses.filter((a) => !usedProjectIds.has(a.projectId));

  return (
    <div className="flex flex-col h-full">
      {/* Dashboard toggle + Add analysis */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        <select
          value={selectedDashboard?.id ?? ""}
          onChange={(e) => {
            const d = dashboards.find((x) => x.id === e.target.value);
            if (d) switchDashboard(d);
          }}
          className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white font-light focus:border-violet-500/50 focus:outline-none"
        >
          {dashboards.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <button
          onClick={() => setAddModalOpen(true)}
          className="px-4 py-2 bg-violet-500/20 border border-violet-500/30 rounded-lg text-violet-300 text-sm font-light hover:bg-violet-500/30"
        >
          Add analysis to dashboard
        </button>
        <button
          onClick={() => setCreateDashboardModal(true)}
          className="px-4 py-2 border border-white/20 rounded-lg text-gray-400 text-sm font-light hover:bg-white/5"
        >
          New dashboard
        </button>
      </div>

      {/* Grid */}
      <div ref={containerRef} className="flex-1 min-h-[400px]" style={{ width: "100%" }}>
        {mounted && width > 0 && (
          <GridLayout
            className="layout"
            layout={layout}
            width={width}
            gridConfig={{ cols: 12, rowHeight: 120 }}
            dragConfig={{ handle: ".widget-drag-handle", bounded: true }}
            resizeConfig={{ enabled: true, handles: ["se"] }}
            onLayoutChange={handleLayoutChange}
          >
            {(selectedDashboard?.widgets ?? []).map((w) => (
              <div key={w.id} className="w-full h-full min-h-0 rounded-xl border border-white/10 bg-white/5 overflow-hidden flex flex-col">
                <DashboardWidget
                  projectId={w.project_id}
                  widgetId={w.id}
                  analysisName={analyses.find((a) => a.projectId === w.project_id)?.name ?? "Analysis"}
                  onRemove={() => handleRemoveWidget(w.id)}
                />
              </div>
            ))}
          </GridLayout>
        )}
      </div>

      {/* Add analysis modal */}
      {addModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="p-6 rounded-xl border border-white/10 bg-[#0B0F14] max-w-md w-full mx-4 max-h-[80vh] overflow-y-auto">
            <h4 className="text-lg font-light text-white mb-4">Add analysis to dashboard</h4>
            {availableAnalyses.length === 0 ? (
              <p className="text-gray-400 text-sm">All analyses are already on this dashboard.</p>
            ) : (
              <div className="space-y-2">
                {availableAnalyses.map((a) => (
                  <button
                    key={a.id}
                    onClick={() => handleAddAnalysis(a.projectId)}
                    className="w-full text-left px-4 py-3 rounded-lg border border-white/10 hover:bg-white/5 text-white font-light"
                  >
                    {a.name}
                  </button>
                ))}
              </div>
            )}
            <button
              onClick={() => setAddModalOpen(false)}
              className="mt-4 w-full px-4 py-2 border border-white/20 rounded-lg text-gray-400 font-light hover:bg-white/5"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {createDashboardModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="p-6 rounded-xl border border-white/10 bg-[#0B0F14] max-w-sm w-full mx-4">
            <h4 className="text-lg font-light text-white mb-4">New Dashboard</h4>
            <input
              type="text"
              value={newDashboardName}
              onChange={(e) => setNewDashboardName(e.target.value)}
              placeholder="e.g. Revenue Overview"
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 font-light focus:border-violet-500/50 focus:outline-none mb-4"
            />
            <div className="flex gap-3">
              <button
                onClick={() => setCreateDashboardModal(false)}
                className="flex-1 px-4 py-2 border border-white/20 rounded-lg text-gray-400 font-light hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateDashboard}
                className="flex-1 px-4 py-2 bg-violet-500/30 border border-violet-500/40 rounded-lg text-violet-300 font-light hover:bg-violet-500/40"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
