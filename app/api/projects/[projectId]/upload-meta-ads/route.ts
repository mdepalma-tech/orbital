import { createClient } from "@supabase/supabase-js";
import { createClient as createServerClient } from "@/lib/supabase/server";
import { NextRequest, NextResponse } from "next/server";
import { parse } from "csv-parse/sync";

type CsvRow = Record<string, string | undefined>;

const DATE_COLS = ["date", "day", "date_start"];
const SPEND_COLS = ["amount_spent", "spend", "cost"];

interface ParseSummary {
  dateRange: { start: string; end: string };
  totalDays: number;
  totalRows: number;
  includedRows: number;
  excludedRows: number;
  totalSpend: number;
  averageDailySpend: number;
}

interface UploadResponse {
  status: "success" | "preview" | "error";
  message?: string;
  summary?: ParseSummary;
  warnings?: string[];
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

function resolveColumn(headers: string[], candidates: string[]): string | undefined {
  const headerSet = new Set(headers);
  for (const candidate of candidates) {
    const c = candidate.toLowerCase().trim().replace(/ /g, "_");
    if (headerSet.has(c)) return c;
  }
  return undefined;
}

function toLocalDate(dateStr: string, timezone: string): string {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) throw new Error(`Invalid date: ${dateStr}`);
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = formatter.formatToParts(date);
  const year = parts.find((p) => p.type === "year")?.value;
  const month = parts.find((p) => p.type === "month")?.value;
  const day = parts.find((p) => p.type === "day")?.value;
  return `${year}-${month}-${day}`;
}

function toDateString(dateStr: string, timezone?: string): string {
  const s = dateStr.trim();
  if (!s) throw new Error("Empty date string");

  if (/^\d{4}-\d{1,2}-\d{1,2}/.test(s)) {
    const match = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (match) {
      const month = parseInt(match[2], 10);
      const day = parseInt(match[3], 10);
      if (month < 1 || month > 12 || day < 1 || day > 31) {
        throw new Error(`Invalid date: ${dateStr}`);
      }
      return `${match[1]}-${match[2].padStart(2, "0")}-${match[3].padStart(2, "0")}`;
    }
  }

  const slashMatch = s.match(/(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})/);
  if (slashMatch) {
    const a = parseInt(slashMatch[1], 10);
    const b = parseInt(slashMatch[2], 10);
    let year = slashMatch[3];
    if (year.length === 2) year = `20${year}`;

    let month: number;
    let day: number;
    if (a > 12) {
      day = a;
      month = b;
    } else {
      month = a;
      day = b;
    }

    if (month < 1 || month > 12 || day < 1 || day > 31) {
      throw new Error(`Invalid date: ${dateStr}`);
    }

    return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  }

  const iso = new Date(s);
  if (!isNaN(iso.getTime())) {
    return timezone ? toLocalDate(s, timezone) : iso.toISOString().slice(0, 10);
  }

  throw new Error(`Invalid date: ${dateStr}`);
}

function parseMoney(raw: string): number | null {
  const s = raw.trim();
  if (!s) return null;

  let t = s;
  if (/^\([^)]+\)$/.test(t)) {
    t = "-" + t.slice(1, -1);
  }
  t = t.replace(/[$€£,\s]/g, "");
  const n = parseFloat(t);
  if (!Number.isFinite(n)) return null;
  return n;
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

async function getProjectTimezone(projectId: string): Promise<string> {
  const supabase = getSupabaseServiceClient();
  const { data } = await supabase
    .from("projects")
    .select("timezone")
    .eq("id", projectId)
    .single();
  return (data?.timezone as string) || "UTC";
}

async function ensureProjectExists(projectId: string, userId: string): Promise<void> {
  const supabase = getSupabaseServiceClient();
  const { data } = await supabase
    .from("projects")
    .select("id")
    .eq("id", projectId)
    .single();

  if (!data) {
    const { error } = await supabase.from("projects").insert({
      id: projectId,
      user_id: userId,
      name: "Default Project",
      shopify_store_domain: "",
    });
    if (error && error.code !== "23505") {
      throw new Error(`Failed to create project: ${error.message}`);
    }
  }
}

function aggregateRows(
  rows: CsvRow[],
  dateCol: string,
  spendCol: string,
  timezone?: string
): { dailySpend: Map<string, number>; includedRows: number } {
  const dailySpend = new Map<string, number>();
  let includedRows = 0;

  for (const row of rows) {
    const dateRaw = row[dateCol];
    if (!dateRaw?.trim()) continue;

    let date: string;
    try {
      date = toDateString(dateRaw, timezone);
    } catch {
      continue;
    }

    const spendRaw = row[spendCol];
    if (spendRaw === undefined || spendRaw === null) continue;

    const spend = parseMoney(spendRaw);
    if (spend === null) continue;

    const daily = dailySpend.get(date) ?? 0;
    dailySpend.set(date, daily + spend);
    includedRows++;
  }

  return { dailySpend, includedRows };
}

async function upsertMetaSpend(
  projectId: string,
  dailyRows: { project_id: string; ts: string; meta_spend: number }[]
): Promise<void> {
  const supabase = getSupabaseServiceClient();
  const batchSize = 500;
  for (let i = 0; i < dailyRows.length; i += batchSize) {
    const batch = dailyRows.slice(i, i + batchSize);
    const { error } = await supabase
      .from("project_spend")
      .upsert(batch, { onConflict: "project_id,ts", ignoreDuplicates: false });
    if (error) throw new Error(`Database upsert failed: ${error.message}`);
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

    const formData = await request.formData();
    const file = formData.get("file") as File | null;
    const mode = (formData.get("mode") as string) || "save";

    if (!file) {
      return NextResponse.json(
        { status: "error", message: "No file provided" },
        { status: 400 }
      );
    }

    if (!file.name.endsWith(".csv")) {
      return NextResponse.json(
        { status: "error", message: "File must be a CSV" },
        { status: 400 }
      );
    }

    const fileContent = await file.text();
    if (!fileContent || fileContent.trim().length === 0) {
      return NextResponse.json(
        { status: "error", message: "File is empty" },
        { status: 400 }
      );
    }

    let parsedRows: CsvRow[];
    try {
      parsedRows = parseCSV(fileContent);
    } catch (error) {
      return NextResponse.json(
        {
          status: "error",
          message: error instanceof Error ? error.message : "CSV parsing failed",
        },
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
    const dateCol = resolveColumn(headers, DATE_COLS);
    const spendCol = resolveColumn(headers, SPEND_COLS);

    if (!dateCol) {
      return NextResponse.json(
        { status: "error", message: "No date column found. Expected one of: date, day, date_start" },
        { status: 400 }
      );
    }

    if (!spendCol) {
      return NextResponse.json(
        { status: "error", message: "No spend column found. Expected one of: amount_spent, spend, cost" },
        { status: 400 }
      );
    }

    const timezone = await getProjectTimezone(projectId);
    const { dailySpend, includedRows } = aggregateRows(parsedRows, dateCol, spendCol, timezone);

    const sortedDates = Array.from(dailySpend.keys()).sort();
    const totalSpend = sortedDates.reduce(
      (sum, d) => sum + (dailySpend.get(d) ?? 0),
      0
    );
    const totalDays = sortedDates.length;
    const excludedRows = Math.max(0, parsedRows.length - includedRows);

    const summary: ParseSummary = {
      dateRange: {
        start: totalDays > 0 ? sortedDates[0] : "N/A",
        end: totalDays > 0 ? sortedDates[sortedDates.length - 1] : "N/A",
      },
      totalDays,
      totalRows: parsedRows.length,
      includedRows,
      excludedRows,
      totalSpend: Math.round(totalSpend * 100) / 100,
      averageDailySpend:
        totalDays > 0 ? Math.round((totalSpend / totalDays) * 100) / 100 : 0,
    };

    const warnings: string[] = [];
    if (totalDays < 30) {
      warnings.push(`Only ${totalDays} distinct days found (recommend at least 30).`);
    }
    if (totalSpend === 0) {
      warnings.push("Total Meta spend is $0 across all included rows.");
    }
    if (includedRows === 0) {
      warnings.push("No rows with valid date + spend were found after parsing.");
    }

    if (mode === "preview") {
      return NextResponse.json(
        { status: "preview", summary, warnings: warnings.length > 0 ? warnings : undefined },
        { status: 200 }
      );
    }

    await ensureProjectExists(projectId, user.id);

    const dailyRows = sortedDates.map((date) => ({
      project_id: projectId,
      ts: date,
      meta_spend: Math.round((dailySpend.get(date) ?? 0) * 100) / 100,
    }));

    await upsertMetaSpend(projectId, dailyRows);

    return NextResponse.json(
      { status: "success", summary, warnings: warnings.length > 0 ? warnings : undefined },
      { status: 200 }
    );
  } catch (error) {
    console.error("Meta Ads upload error:", error);
    return NextResponse.json(
      {
        status: "error",
        message: error instanceof Error ? error.message : "Internal server error",
      },
      { status: 500 }
    );
  }
}
