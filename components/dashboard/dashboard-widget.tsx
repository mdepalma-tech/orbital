"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

interface DashboardWidgetProps {
  projectId: string;
  widgetId: string;
  analysisName: string;
  onRemove: () => void;
}

function addDays(dateStr: string, days: number): string {
  const d = new Date(dateStr);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function formatShortDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function DashboardWidget({ projectId, widgetId, analysisName, onRemove }: DashboardWidgetProps) {
  const [scenarios, setScenarios] = useState<
    { id: string; name: string; weeks?: { week_index?: number; meta_spend?: number; google_spend?: number; tiktok_spend?: number }[] }[]
  >([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);
  const [predictions, setPredictions] = useState<number[] | null>(null);
  const [historical, setHistorical] = useState<{ week_start: string; revenue: number }[]>([]);
  const [loading, setLoading] = useState(true);

  const runForecast = useCallback(
    (weeksOverride?: { week_index: number; meta_spend: number; google_spend: number; tiktok_spend: number }[]) => {
      const url = `/api/projects/${projectId}/forecast`;
      const body = weeksOverride
        ? { weeks: weeksOverride, history_weeks: 8 }
        : { horizon: 4, spend_multiplier: 1.0, history_weeks: 8 };
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
        .then((r) => r.json())
        .then((d) => {
          if (d.predictions) {
            setPredictions(d.predictions);
            setHistorical((d.historical as { week_start: string; revenue: number }[]) ?? []);
          }
        })
        .catch(() => {})
        .finally(() => setLoading(false));
    },
    [projectId]
  );

  useEffect(() => {
    setLoading(true);
    runForecast();
  }, [runForecast]);

  useEffect(() => {
    const baseUrl = process.env.NEXT_PUBLIC_ORBITAL_BACKEND_URL || "";
    const url = baseUrl
      ? `${baseUrl}/v1/projects/${projectId}/forecast/scenarios`
      : `/api/projects/${projectId}/forecast/scenarios`;
    fetch(url)
      .then((r) => r.json())
      .then((d) => {
        const list = d?.scenarios ?? [];
        setScenarios(Array.isArray(list) ? list : []);
      })
      .catch(() => {});
  }, [projectId]);

  const chartData = historical.length > 0 && predictions && predictions.length > 0
    ? [
        ...historical.map((h) => ({ date: h.week_start, revenue: h.revenue, type: "actual" })),
        ...predictions.map((rev, i) => ({
          date: addDays(historical[historical.length - 1].week_start, 7 * (i + 1)),
          revenue: rev,
          type: "forecast",
        })),
      ]
    : [];

  const firstForecastDate =
    predictions && predictions.length > 0 && historical.length > 0
      ? addDays(historical[historical.length - 1].week_start, 7)
      : null;

  return (
    <div className="h-full flex flex-col bg-[#0B0F14]/80">
      {/* Header with drag handle */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/10 flex-shrink-0">
        <div className="widget-drag-handle cursor-move flex items-center gap-2 min-w-0">
          <span className="text-gray-500 text-sm">⋮⋮</span>
          <span className="text-sm font-light text-white truncate">{analysisName}</span>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <Link
            href={`/dashboard/build/run?projectId=${projectId}`}
            className="px-2 py-1 text-xs text-violet-400 hover:text-violet-300"
          >
            Open
          </Link>
          <button
            onClick={onRemove}
            className="px-2 py-1 text-xs text-gray-500 hover:text-red-400"
            title="Remove from dashboard"
          >
            ×
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0 p-2 overflow-auto flex flex-col">
        {loading ? (
          <div className="flex items-center justify-center h-20 flex-shrink-0">
            <div className="w-4 h-4 border-2 border-violet-500/50 border-t-violet-400 rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {(chartData.length > 0 || (predictions && predictions.length > 0)) && (
              <select
                value={selectedScenarioId ?? ""}
                onChange={(e) => {
                  const id = e.target.value || null;
                  setSelectedScenarioId(id);
                  setLoading(true);
                  if (id) {
                    const scen = scenarios.find((s) => s.id === id);
                    if (scen?.weeks && Array.isArray(scen.weeks)) {
                      runForecast(
                        scen.weeks.map((w: Record<string, unknown>) => ({
                          week_index: (w.week_index as number) ?? 0,
                          meta_spend: (w.meta_spend as number) ?? 0,
                          google_spend: (w.google_spend as number) ?? 0,
                          tiktok_spend: (w.tiktok_spend as number) ?? 0,
                        }))
                      );
                    } else {
                      const baseUrl = process.env.NEXT_PUBLIC_ORBITAL_BACKEND_URL || "";
                      const scenUrl = baseUrl
                        ? `${baseUrl}/v1/projects/${projectId}/forecast/scenarios/${id}`
                        : `/api/projects/${projectId}/forecast/scenarios/${id}`;
                      fetch(scenUrl)
                        .then((r) => r.json())
                        .then((s) => {
                          if (s?.weeks && Array.isArray(s.weeks)) {
                            runForecast(
                              s.weeks.map((w: Record<string, unknown>) => ({
                                week_index: (w.week_index as number) ?? 0,
                                meta_spend: (w.meta_spend as number) ?? 0,
                                google_spend: (w.google_spend as number) ?? 0,
                                tiktok_spend: (w.tiktok_spend as number) ?? 0,
                              }))
                            );
                          } else {
                            runForecast();
                          }
                        })
                        .catch(() => runForecast());
                    }
                  } else {
                    runForecast();
                  }
                }}
                className="w-full mb-2 px-2 py-1.5 bg-white/5 border border-white/10 rounded text-xs text-white font-light focus:border-violet-500/50 focus:outline-none flex-shrink-0"
              >
                <option value="">Baseline</option>
                {scenarios.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            )}

            {chartData.length > 0 ? (
              <div className="flex-1 min-h-[80px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
                    <XAxis
                      dataKey="date"
                      stroke="#6b7280"
                      fontSize={11}
                      tickFormatter={formatShortDate}
                    />
                    <YAxis
                      stroke="#6b7280"
                      fontSize={11}
                      tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "#0B0F14",
                        border: "1px solid rgba(255,255,255,0.12)",
                        borderRadius: 8,
                        fontSize: 11,
                      }}
                      formatter={(v, _n, props) => [
                        `$${Number(v ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
                        (props?.payload as { type?: string })?.type === "actual" ? "Actual" : "Forecast",
                      ]}
                      labelFormatter={(d) => formatShortDate(d)}
                    />
                    {firstForecastDate && (
                      <ReferenceLine
                        x={firstForecastDate}
                        stroke="#a78bfa"
                        strokeDasharray="4 4"
                        strokeOpacity={0.5}
                      />
                    )}
                    <Line
                      dataKey="revenue"
                      stroke="#60a5fa"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      connectNulls
                      name="Revenue"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : predictions && predictions.length > 0 ? (
              <div className="text-xs text-gray-400">
                Total: $
                {predictions
                  .reduce((a, b) => a + b, 0)
                  .toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
