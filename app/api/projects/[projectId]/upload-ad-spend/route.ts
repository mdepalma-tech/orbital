import { createClient } from "@supabase/supabase-js";
import { createClient as createServerClient } from "@/lib/supabase/server";
import { NextRequest, NextResponse } from "next/server";
import { parse } from "csv-parse/sync";

type CsvRow = Record<string, string | undefined>;

const KNOWN_SPEND_COLUMNS: Record<string, string> = {
  meta_spend: "Meta",
  google_spend: "Google",
  tiktok_spend: "TikTok",
};

interface ChannelDay {
  date: string;
  channel: string;
  spend: number;
}

interface ParseSummary {
  dateRange: { start: string; end: string };
  totalDays: number;
  totalRows: number;
  channels: string[];
  channelTotals: Record<string, number>;
  totalSpend: number;
  averageDailySpend: number;
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

function detectSpendColumns(headers: string[]): Record<string, string> {
  const found: Record<string, string> = {};

  for (const header of headers) {
    if (KNOWN_SPEND_COLUMNS[header]) {
      found[header] = KNOWN_SPEND_COLUMNS[header];
    }
  }

  return found;
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

function pivotRows(rows: CsvRow[], spendColumns: Record<string, string>): ChannelDay[] {
  const results: ChannelDay[] = [];

  for (const row of rows) {
    if (!row.date) continue;

    let date: string;
    try {
      date = toDateString(row.date);
    } catch {
      continue;
    }

    for (const [col, channelName] of Object.entries(spendColumns)) {
      const raw = row[col];
      if (raw === undefined || raw === null || raw.trim() === "") continue;

      const spend = parseFloat(raw.replace(/[^0-9.-]/g, "")) || 0;

      results.push({ date, channel: channelName, spend: Math.round(spend * 100) / 100 });
    }
  }

  return results.sort(
    (a, b) => a.date.localeCompare(b.date) || a.channel.localeCompare(b.channel)
  );
}

async function upsertAdSpend(
  projectId: string,
  rows: CsvRow[],
  spendColumns: Record<string, string>
): Promise<void> {
  const supabase = getSupabaseServiceClient();

  const dbRows = [];
  for (const row of rows) {
    if (!row.date) continue;

    let date: string;
    try {
      date = toDateString(row.date);
    } catch {
      continue;
    }

    const dbRow: Record<string, unknown> = {
      project_id: projectId,
      ts: date,
    };

    for (const col of Object.keys(spendColumns)) {
      const raw = row[col];
      dbRow[col] = raw !== undefined && raw !== null && raw.trim() !== ""
        ? Math.round(parseFloat(raw.replace(/[^0-9.-]/g, "")) * 100) / 100 || 0
        : 0;
    }

    dbRows.push(dbRow);
  }

  const batchSize = 500;
  for (let i = 0; i < dbRows.length; i += batchSize) {
    const batch = dbRows.slice(i, i + batchSize);
    const { error } = await supabase
      .from("project_spend")
      .upsert(batch, { onConflict: "project_id,ts", ignoreDuplicates: false });

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
    const {
      data: { user },
    } = await supabaseAuth.auth.getUser();
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

    if (!headers.includes("date")) {
      return NextResponse.json(
        { status: "error", message: 'Missing required "Date" column' },
        { status: 400 }
      );
    }

    const spendColumns = detectSpendColumns(headers);

    if (Object.keys(spendColumns).length === 0) {
      return NextResponse.json(
        {
          status: "error",
          message:
            "No spend columns found. Expected at least one of: meta_spend, google_spend, tiktok_spend",
        },
        { status: 400 }
      );
    }

    let pivoted: ChannelDay[];
    try {
      pivoted = pivotRows(parsedRows, spendColumns);
    } catch (error) {
      return NextResponse.json(
        { status: "error", message: error instanceof Error ? error.message : "Data processing failed" },
        { status: 400 }
      );
    }

    const channels = [...new Set(pivoted.map((d) => d.channel))].sort();
    const dates = [...new Set(pivoted.map((d) => d.date))].sort();
    const totalSpend = pivoted.reduce((sum, d) => sum + d.spend, 0);

    const channelTotals: Record<string, number> = {};
    for (const ch of channels) {
      channelTotals[ch] = Math.round(
        pivoted.filter((d) => d.channel === ch).reduce((sum, d) => sum + d.spend, 0) * 100
      ) / 100;
    }

    const summary: ParseSummary = {
      dateRange: {
        start: dates.length > 0 ? dates[0] : "N/A",
        end: dates.length > 0 ? dates[dates.length - 1] : "N/A",
      },
      totalDays: dates.length,
      totalRows: parsedRows.length,
      channels,
      channelTotals,
      totalSpend: Math.round(totalSpend * 100) / 100,
      averageDailySpend:
        dates.length > 0 ? Math.round((totalSpend / dates.length) * 100) / 100 : 0,
    };

    if (mode === "preview") {
      const warnings: string[] = [];
      if (dates.length < 30) {
        warnings.push(`Only ${dates.length} distinct days found (recommend at least 30)`);
      }
      if (totalSpend === 0) {
        warnings.push("Total spend is $0 across all channels");
      }

      return NextResponse.json(
        { status: "preview", summary, message: warnings.length > 0 ? warnings.join(". ") : undefined },
        { status: 200 }
      );
    }

    await ensureProjectExists(projectId, user.id);
    await upsertAdSpend(projectId, parsedRows, spendColumns);

    return NextResponse.json({ status: "success", summary }, { status: 200 });
  } catch (error) {
    console.error("Ad spend upload error:", error);
    return NextResponse.json(
      { status: "error", message: error instanceof Error ? error.message : "Internal server error" },
      { status: 500 }
    );
  }
}
