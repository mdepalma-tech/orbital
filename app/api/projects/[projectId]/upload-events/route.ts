import { createClient } from "@supabase/supabase-js";
import { createClient as createServerClient } from "@/lib/supabase/server";
import { NextRequest, NextResponse } from "next/server";
import { parse } from "csv-parse/sync";

type CsvRow = Record<string, string | undefined>;

interface EventRecord {
  name: string;
  type: "step" | "pulse";
  start_date: string;
  end_date: string | null;
}

interface ParseSummary {
  totalEvents: number;
  stepEvents: number;
  pulseEvents: number;
  dateRange: { start: string; end: string };
  eventNames: string[];
}

interface UploadResponse {
  status: "success" | "preview" | "error";
  message?: string;
  summary?: ParseSummary;
}

function getSupabaseServiceClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!supabaseUrl || !supabaseServiceKey) {
    throw new Error("Missing Supabase environment variables");
  }

  return createClient(supabaseUrl, supabaseServiceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

function toDateString(dateStr: string): string {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) {
    const parts = dateStr.match(/(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})/);
    if (parts) {
      const year = parts[3].length === 2 ? `20${parts[3]}` : parts[3];
      return `${year}-${parts[1].padStart(2, "0")}-${parts[2].padStart(2, "0")}`;
    }
    throw new Error(`Invalid date: ${dateStr}`);
  }
  return date.toISOString().slice(0, 10);
}

function parseCSV(fileContent: string): CsvRow[] {
  try {
    return parse(fileContent, {
      columns: (header: string[]) =>
        header.map((col: string) => col.toLowerCase().trim().replace(/ /g, "_")),
      skip_empty_lines: true,
      trim: true,
      cast: false,
      relax_column_count: true,
    });
  } catch (error) {
    throw new Error(
      `CSV parsing failed: ${error instanceof Error ? error.message : "Unknown error"}`
    );
  }
}

function extractEvents(rows: CsvRow[]): EventRecord[] {
  const events: EventRecord[] = [];

  for (const row of rows) {
    const name = (row.name || row.event_name || row.event || "").trim();
    if (!name) continue;

    const rawType = (row.type || row.event_type || "").trim().toLowerCase();
    const type: "step" | "pulse" = rawType === "step" ? "step" : "pulse";

    const rawStart = (row.start_date || row.date || "").trim();
    if (!rawStart) continue;

    let startDate: string;
    try {
      startDate = toDateString(rawStart);
    } catch {
      continue;
    }

    let endDate: string | null = null;
    const rawEnd = (row.end_date || "").trim();
    if (rawEnd) {
      try {
        endDate = toDateString(rawEnd);
      } catch {
        // pulse events don't need end_date
      }
    }

    events.push({ name, type, start_date: startDate, end_date: endDate });
  }

  return events.sort((a, b) => a.start_date.localeCompare(b.start_date));
}

function buildSummary(events: EventRecord[]): ParseSummary {
  const stepEvents = events.filter((e) => e.type === "step").length;
  const pulseEvents = events.filter((e) => e.type === "pulse").length;
  const allDates = events
    .flatMap((e) => [e.start_date, e.end_date].filter(Boolean) as string[])
    .sort();

  return {
    totalEvents: events.length,
    stepEvents,
    pulseEvents,
    dateRange: {
      start: allDates.length > 0 ? allDates[0] : "N/A",
      end: allDates.length > 0 ? allDates[allDates.length - 1] : "N/A",
    },
    eventNames: [...new Set(events.map((e) => e.name))],
  };
}

async function upsertEvents(projectId: string, events: EventRecord[]): Promise<void> {
  const supabase = getSupabaseServiceClient();

  const rows = events.map((e) => ({
    project_id: projectId,
    event_name: e.name,
    event_type: e.type,
    start_ts: e.start_date,
    end_ts: e.end_date || null,
  }));

  const batchSize = 500;
  for (let i = 0; i < rows.length; i += batchSize) {
    const batch = rows.slice(i, i + batchSize);
    const { error } = await supabase
      .from("project_events")
      .insert(batch);

    if (error) {
      throw new Error(`Database upsert failed: ${error.message}`);
    }
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ projectId: string }> }
): Promise<NextResponse<UploadResponse>> {
  try {
    const { projectId } = await params;

    const supabaseAuth = await createServerClient();
    const { data: { user } } = await supabaseAuth.auth.getUser();
    if (!user) {
      return NextResponse.json(
        { status: "error", message: "Not authenticated" },
        { status: 401 }
      );
    }

    const contentType = request.headers.get("content-type") || "";

    // JSON body = manual entry
    if (contentType.includes("application/json")) {
      const body = await request.json();
      const { events, mode } = body as { events: EventRecord[]; mode?: string };

      if (!events || !Array.isArray(events) || events.length === 0) {
        return NextResponse.json(
          { status: "error", message: "No events provided" },
          { status: 400 }
        );
      }

      for (const e of events) {
        if (!e.name || !e.type || !e.start_date) {
          return NextResponse.json(
            { status: "error", message: "Each event must have name, type, and start_date" },
            { status: 400 }
          );
        }
        if (e.type !== "step" && e.type !== "pulse") {
          return NextResponse.json(
            { status: "error", message: `Invalid event type "${e.type}". Must be "step" or "pulse"` },
            { status: 400 }
          );
        }
      }

      const summary = buildSummary(events);

      if (mode === "preview") {
        return NextResponse.json({ status: "preview", summary }, { status: 200 });
      }

      await upsertEvents(projectId, events);
      return NextResponse.json({ status: "success", summary }, { status: 200 });
    }

    // FormData = CSV upload
    const formData = await request.formData();
    const file = formData.get("file") as File | null;
    const mode = (formData.get("mode") as string) || "save";

    if (!file) {
      return NextResponse.json({ status: "error", message: "No file provided" }, { status: 400 });
    }

    if (!file.name.endsWith(".csv")) {
      return NextResponse.json({ status: "error", message: "File must be a CSV" }, { status: 400 });
    }

    const fileContent = await file.text();
    if (!fileContent || fileContent.trim().length === 0) {
      return NextResponse.json({ status: "error", message: "File is empty" }, { status: 400 });
    }

    let parsedRows: CsvRow[];
    try {
      parsedRows = parseCSV(fileContent);
    } catch (error) {
      return NextResponse.json(
        { status: "error", message: error instanceof Error ? error.message : "CSV parsing failed" },
        { status: 400 }
      );
    }

    if (parsedRows.length === 0) {
      return NextResponse.json(
        { status: "error", message: "No data rows found in CSV" },
        { status: 400 }
      );
    }

    const headers = Object.keys(parsedRows[0]);
    const hasName = headers.some((h) => ["name", "event_name", "event"].includes(h));
    const hasDate = headers.some((h) => ["start_date", "date"].includes(h));

    if (!hasName || !hasDate) {
      const missing = [];
      if (!hasName) missing.push("name (or event_name)");
      if (!hasDate) missing.push("start_date (or date)");
      return NextResponse.json(
        { status: "error", message: `Missing required columns: ${missing.join(", ")}` },
        { status: 400 }
      );
    }

    const events = extractEvents(parsedRows);

    if (events.length === 0) {
      return NextResponse.json(
        { status: "error", message: "No valid events found in CSV" },
        { status: 400 }
      );
    }

    const summary = buildSummary(events);

    if (mode === "preview") {
      return NextResponse.json({ status: "preview", summary }, { status: 200 });
    }

    await upsertEvents(projectId, events);
    return NextResponse.json({ status: "success", summary }, { status: 200 });
  } catch (error) {
    console.error("Events upload error:", error);
    return NextResponse.json(
      { status: "error", message: error instanceof Error ? error.message : "Internal server error" },
      { status: 500 }
    );
  }
}
