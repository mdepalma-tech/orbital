"use client";

import { useState, useRef } from "react";
import { randomUUID } from "@/lib/utils";

interface ParseSummary {
  totalEvents: number;
  stepEvents: number;
  pulseEvents: number;
  dateRange: { start: string; end: string };
  eventNames: string[];
}

interface ApiResponse {
  status: "success" | "preview" | "error";
  message?: string;
  summary?: ParseSummary;
}

interface ManualEvent {
  id: string;
  name: string;
  type: "step" | "pulse";
  start_date: string;
  end_date: string;
}

type CsvStage = "upload" | "parsing" | "preview" | "saving" | "saved" | "error";
type ManualStage = "editing" | "saving" | "saved" | "error";

export function EventsUploadSection({ projectId }: { projectId: string }) {
  // CSV state
  const [csvStage, setCsvStage] = useState<CsvStage>("upload");
  const [csvSummary, setCsvSummary] = useState<ParseSummary | null>(null);
  const [csvError, setCsvError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  // Manual state
  const [manualStage, setManualStage] = useState<ManualStage>("editing");
  const [manualError, setManualError] = useState<string | null>(null);
  const [manualSummary, setManualSummary] = useState<ParseSummary | null>(null);
  const [events, setEvents] = useState<ManualEvent[]>([
    { id: randomUUID(), name: "", type: "pulse", start_date: "", end_date: "" },
  ]);

  // --- CSV handlers ---

  async function handleCsvParse(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setCsvStage("parsing");
    setCsvError(null);
    setCsvSummary(null);

    const formData = new FormData(e.currentTarget);
    formData.set("mode", "preview");

    try {
      const res = await fetch(`/api/projects/${projectId}/upload-events`, {
        method: "POST",
        body: formData,
      });
      const data: ApiResponse = await res.json();

      if (data.status === "preview" && data.summary) {
        setCsvSummary(data.summary);
        setCsvStage("preview");
      } else {
        setCsvError(data.message || "Parsing failed");
        setCsvStage("error");
      }
    } catch {
      setCsvError("Failed to connect to server.");
      setCsvStage("error");
    }
  }

  async function handleCsvSave() {
    if (!selectedFile) return;
    setCsvStage("saving");

    const formData = new FormData();
    formData.set("file", selectedFile);
    formData.set("mode", "save");

    try {
      const res = await fetch(`/api/projects/${projectId}/upload-events`, {
        method: "POST",
        body: formData,
      });
      const data: ApiResponse = await res.json();

      if (data.status === "success" && data.summary) {
        setCsvSummary(data.summary);
        setCsvStage("saved");
      } else {
        setCsvError(data.message || "Save failed");
        setCsvStage("error");
      }
    } catch {
      setCsvError("Failed to save data.");
      setCsvStage("error");
    }
  }

  function handleCsvReset() {
    setCsvStage("upload");
    setCsvSummary(null);
    setCsvError(null);
    setSelectedFile(null);
    formRef.current?.reset();
  }

  // --- Manual handlers ---

  function addEvent() {
    setEvents((prev) => [
      ...prev,
      { id: randomUUID(), name: "", type: "pulse", start_date: "", end_date: "" },
    ]);
  }

  function removeEvent(id: string) {
    setEvents((prev) => (prev.length > 1 ? prev.filter((e) => e.id !== id) : prev));
  }

  function updateEvent(id: string, field: keyof ManualEvent, value: string) {
    setEvents((prev) =>
      prev.map((e) => (e.id === id ? { ...e, [field]: value } : e))
    );
  }

  async function handleManualSave() {
    const valid = events.filter((e) => e.name && e.start_date);
    if (valid.length === 0) {
      setManualError("Add at least one event with a name and start date.");
      setManualStage("error");
      return;
    }

    setManualStage("saving");
    setManualError(null);

    const payload = valid.map((e) => ({
      name: e.name,
      type: e.type,
      start_date: e.start_date,
      end_date: e.end_date || null,
    }));

    try {
      const res = await fetch(`/api/projects/${projectId}/upload-events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: payload, mode: "save" }),
      });
      const data: ApiResponse = await res.json();

      if (data.status === "success" && data.summary) {
        setManualSummary(data.summary);
        setManualStage("saved");
      } else {
        setManualError(data.message || "Save failed");
        setManualStage("error");
      }
    } catch {
      setManualError("Failed to save events.");
      setManualStage("error");
    }
  }

  function handleManualReset() {
    setManualStage("editing");
    setManualError(null);
    setManualSummary(null);
    setEvents([{ id: randomUUID(), name: "", type: "pulse", start_date: "", end_date: "" }]);
  }

  const Spinner = ({ text, color }: { text: string; color: string }) => (
    <div className="flex flex-col items-center justify-center py-10 gap-4">
      <svg className={`animate-spin h-10 w-10 ${color}`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
      </svg>
      <p className="text-gray-400 font-light animate-pulse">{text}</p>
    </div>
  );

  return (
    <div className="space-y-8">
      {/* ========== CSV Upload ========== */}
      <div className="p-6 rounded-xl border border-white/10 bg-gradient-to-br from-white/5 to-transparent">
        <div className="mb-4">
          <h3 className="text-lg font-light mb-2">Upload Events via CSV</h3>
          <p className="text-sm text-gray-400 font-light">
            CSV with columns: name, type (step or pulse), start_date, and optionally end_date
          </p>
        </div>

        <div className="space-y-4">
          <form ref={formRef} onSubmit={handleCsvParse} className="space-y-4">
            <label className="block">
              <span className="text-sm text-gray-400 font-light">Events CSV</span>
              <div className="mt-2">
                <input
                  type="file"
                  name="file"
                  accept=".csv"
                  required
                  onChange={(e) => {
                    setSelectedFile(e.target.files?.[0] || null);
                    setCsvError(null);
                    setCsvSummary(null);
                    if (csvStage !== "upload") setCsvStage("upload");
                  }}
                  disabled={csvStage === "parsing" || csvStage === "saving"}
                  className="w-full px-4 py-3 bg-black/40 border border-white/10 rounded-lg text-white file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-light file:bg-cyan-500 file:text-white hover:file:bg-cyan-600 file:cursor-pointer focus:border-cyan-500/50 focus:outline-none font-light disabled:opacity-50"
                />
              </div>
            </label>

            {(csvStage === "upload" || csvStage === "error") && (
              <button
                type="submit"
                disabled={!selectedFile}
                className="w-full px-8 py-4 border border-cyan-500/50 bg-cyan-500/10 text-cyan-300 rounded-lg font-light tracking-wide hover:bg-cyan-500/20 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Parse & Preview CSV
              </button>
            )}
          </form>

          {csvStage === "parsing" && <Spinner text="Parsing CSV..." color="text-cyan-400" />}
          {csvStage === "saving" && <Spinner text="Saving events..." color="text-cyan-400" />}

          {csvStage === "preview" && csvSummary && (
            <div className="p-5 rounded-xl border border-cyan-500/30 bg-cyan-500/5 space-y-4">
              <span className="text-lg font-light text-cyan-400">Parse Summary</span>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="p-3 rounded-lg bg-black/30 border border-white/5">
                  <p className="text-gray-500 text-xs font-light mb-1">Total Events</p>
                  <p className="text-white text-lg">{csvSummary.totalEvents}</p>
                </div>
                <div className="p-3 rounded-lg bg-black/30 border border-white/5">
                  <p className="text-gray-500 text-xs font-light mb-1">Date Range</p>
                  <p className="text-white font-mono text-sm">{csvSummary.dateRange.start} → {csvSummary.dateRange.end}</p>
                </div>
                <div className="p-3 rounded-lg bg-black/30 border border-white/5">
                  <p className="text-gray-500 text-xs font-light mb-1">Step Events</p>
                  <p className="text-amber-400 text-lg">{csvSummary.stepEvents}</p>
                </div>
                <div className="p-3 rounded-lg bg-black/30 border border-white/5">
                  <p className="text-gray-500 text-xs font-light mb-1">Pulse Events</p>
                  <p className="text-cyan-400 text-lg">{csvSummary.pulseEvents}</p>
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button onClick={handleCsvSave} className="flex-1 px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-lg font-light tracking-wide hover:shadow-lg hover:shadow-cyan-500/50 transition-all duration-300">
                  Confirm & Save
                </button>
                <button onClick={handleCsvReset} className="px-6 py-3 border border-white/20 rounded-lg font-light tracking-wide hover:bg-white/5 transition-all duration-300">
                  Re-upload
                </button>
              </div>
            </div>
          )}

          {csvStage === "saved" && csvSummary && (
            <div className="p-5 rounded-xl border border-emerald-500/30 bg-emerald-500/5 space-y-3">
              <div className="flex items-center gap-2 text-emerald-400">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span className="font-light">{csvSummary.totalEvents} events saved</span>
              </div>
              <button onClick={handleCsvReset} className="w-full px-6 py-3 border border-white/20 rounded-lg font-light tracking-wide hover:bg-white/5 transition-all duration-300 text-gray-400">
                Upload Different File
              </button>
            </div>
          )}

          {csvStage === "error" && csvError && (
            <div className="p-4 rounded-xl border border-red-500/30 bg-red-500/5">
              <p className="text-red-300 font-light text-sm">{csvError}</p>
            </div>
          )}
        </div>
      </div>

      {/* ========== Divider ========== */}
      <div className="flex items-center gap-4">
        <div className="flex-1 h-px bg-white/10" />
        <span className="text-gray-500 text-sm font-light">or add manually</span>
        <div className="flex-1 h-px bg-white/10" />
      </div>

      {/* ========== Manual Entry ========== */}
      <div className="p-6 rounded-xl border border-white/10 bg-gradient-to-br from-white/5 to-transparent">
        <div className="mb-5">
          <h3 className="text-lg font-light mb-2">Add Events Manually</h3>
          <p className="text-sm text-gray-400 font-light">
            Define individual events with their type and duration
          </p>
        </div>

        {manualStage === "saved" && manualSummary ? (
          <div className="space-y-4">
            <div className="p-5 rounded-xl border border-emerald-500/30 bg-emerald-500/5">
              <div className="flex items-center gap-2 text-emerald-400">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span className="font-light">{manualSummary.totalEvents} events saved</span>
              </div>
            </div>
            <button onClick={handleManualReset} className="w-full px-6 py-3 border border-white/20 rounded-lg font-light tracking-wide hover:bg-white/5 transition-all duration-300 text-gray-400">
              Add More Events
            </button>
          </div>
        ) : manualStage === "saving" ? (
          <Spinner text="Saving events..." color="text-cyan-400" />
        ) : (
          <div className="space-y-4">
            {events.map((event, idx) => (
              <div key={event.id} className="p-4 rounded-lg bg-black/30 border border-white/5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500 font-light">Event {idx + 1}</span>
                  {events.length > 1 && (
                    <button
                      onClick={() => removeEvent(event.id)}
                      className="text-xs text-red-400 hover:text-red-300 transition-colors"
                    >
                      Remove
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2">
                    <label className="block">
                      <span className="text-xs text-gray-400 font-light">Event Name</span>
                      <input
                        type="text"
                        value={event.name}
                        onChange={(e) => updateEvent(event.id, "name", e.target.value)}
                        placeholder="e.g., Black Friday Sale, New Product Launch"
                        className="mt-1 w-full px-3 py-2 bg-black/40 border border-white/10 rounded-lg text-white text-sm placeholder-gray-600 focus:border-cyan-500/50 focus:outline-none font-light"
                      />
                    </label>
                  </div>

                  <div>
                    <label className="block">
                      <span className="text-xs text-gray-400 font-light">Event Type</span>
                      <select
                        value={event.type}
                        onChange={(e) => {
                          updateEvent(event.id, "type", e.target.value);
                          if (e.target.value === "step") updateEvent(event.id, "end_date", "");
                        }}
                        className="mt-1 w-full px-3 py-2 bg-black/40 border border-white/10 rounded-lg text-white text-sm focus:border-cyan-500/50 focus:outline-none font-light"
                      >
                        <option value="pulse">Pulse</option>
                        <option value="step">Step</option>
                      </select>
                    </label>
                  </div>

                  <div>
                    <label className="block">
                      <span className="text-xs text-gray-400 font-light">Start Date</span>
                      <input
                        type="date"
                        value={event.start_date}
                        onChange={(e) => updateEvent(event.id, "start_date", e.target.value)}
                        className="mt-1 w-full px-3 py-2 bg-black/40 border border-white/10 rounded-lg text-white text-sm focus:border-cyan-500/50 focus:outline-none font-light"
                      />
                    </label>
                  </div>

                  {event.type === "pulse" && (
                    <div className="col-span-2">
                      <label className="block">
                        <span className="text-xs text-gray-400 font-light">End Date (optional)</span>
                        <input
                          type="date"
                          value={event.end_date}
                          onChange={(e) => updateEvent(event.id, "end_date", e.target.value)}
                          className="mt-1 w-full px-3 py-2 bg-black/40 border border-white/10 rounded-lg text-white text-sm focus:border-cyan-500/50 focus:outline-none font-light"
                        />
                      </label>
                    </div>
                  )}
                </div>
              </div>
            ))}

            <button
              onClick={addEvent}
              className="w-full px-4 py-3 border border-dashed border-white/20 rounded-lg font-light text-sm text-gray-400 hover:border-white/40 hover:text-gray-300 transition-all duration-300"
            >
              + Add Another Event
            </button>

            {manualStage === "error" && manualError && (
              <div className="p-4 rounded-xl border border-red-500/30 bg-red-500/5">
                <p className="text-red-300 font-light text-sm">{manualError}</p>
              </div>
            )}

            <button
              onClick={handleManualSave}
              className="w-full px-8 py-4 border border-cyan-500/50 bg-cyan-500/10 text-cyan-300 rounded-lg font-light tracking-wide hover:bg-cyan-500/20 transition-all duration-300"
            >
              Save Events
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
