import { createClient } from "@supabase/supabase-js";
import { createClient as createServerClient } from "@/lib/supabase/server";
import { NextRequest, NextResponse } from "next/server";
import { parse } from "csv-parse/sync";

type CsvRow = Record<string, string | undefined>;

const DATE_COLS = [
  "day",
  "date",
  "segments.date",
  "date_(utc)",
  "date_utc",
];
const COST_COLS = [
  "cost",
  "amount_spent",
  "spend",
  "cost_(usd)",
  "cost_(eur)",
];
const CAMPAIGN_COLS = ["campaign", "campaign_name"];
const CHANNEL_TYPE_COLS = [
  "advertising_channel_type",
  "advertising_channel",
  "campaign_type",
  "advertising_channel_type_(campaign)",
];

interface ParseSummary {
  dateRange: { start: string; end: string };
  totalDays: number;
  totalRows: number;
  includedRows: number;
  excludedRows: number;
  totalSpend: number;
  averageDailySpend: number;
  breakdownTotals?: Record<string, number>;
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

function toDateString(dateStr: string): string {
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
    return iso.toISOString().slice(0, 10);
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

type ChannelType = "search" | "pmax" | "other" | "search_brand" | "search_nonbrand";

function classifyChannelType(
  channelTypeRaw: string | undefined,
  campaignName: string,
  brandTerms: string[]
): { type: ChannelType; isBrand: boolean } {
  const ct = channelTypeRaw?.toLowerCase().trim() ?? "";
  let baseType: "search" | "pmax" | "other" = "search";

  if (
    ct === "performance_max" ||
    ct === "performance max" ||
    ct === "pmax" ||
    ct === "performancemax"
  ) {
    baseType = "pmax";
  } else if (ct === "search") {
    baseType = "search";
  } else if (ct) {
    baseType = "other";
  }

  if (baseType === "search" && brandTerms.length > 0 && campaignName.trim() !== "") {
    const campaignLower = campaignName.toLowerCase();
    const isBrand = brandTerms.some((term) => campaignLower.includes(term.toLowerCase()));
    return {
      type: isBrand ? "search_brand" : "search_nonbrand",
      isBrand,
    };
  }

  return {
    type: baseType,
    isBrand: false,
  };
}

interface AggregationResult {
  dailySpend: Map<string, number>;
  dailySearchBrand: Map<string, number>;
  dailySearchNonbrand: Map<string, number>;
  dailyPmax: Map<string, number>;
  includedRows: number;
  breakdownTotals: Record<string, number>;
}

function aggregateRows(
  rows: CsvRow[],
  dateCol: string,
  costCol: string,
  campaignCol: string,
  channelTypeCol: string | undefined,
  brandTerms: string[]
): AggregationResult {
  const dailySpend = new Map<string, number>();
  const dailySearchBrand = new Map<string, number>();
  const dailySearchNonbrand = new Map<string, number>();
  const dailyPmax = new Map<string, number>();
  let includedRows = 0;
  const breakdownTotals: Record<string, number> = {
    search_total: 0,
    pmax_total: 0,
    other_total: 0,
    search_brand_total: 0,
    search_nonbrand_total: 0,
  };

  for (const row of rows) {
    const dateRaw = row[dateCol];
    if (!dateRaw?.trim()) continue;

    let date: string;
    try {
      date = toDateString(dateRaw);
    } catch {
      continue;
    }

    const costRaw = row[costCol];
    if (costRaw === undefined || costRaw === null) continue;

    const cost = parseMoney(costRaw);
    if (cost === null) continue;

    const campaignName = (row[campaignCol] ?? "").trim();
    const channelTypeRaw = channelTypeCol ? row[channelTypeCol] : undefined;

    const { type } = classifyChannelType(channelTypeRaw, campaignName, brandTerms);

    const daily = dailySpend.get(date) ?? 0;
    dailySpend.set(date, daily + cost);
    includedRows++;

    if (type === "search" || type === "search_brand" || type === "search_nonbrand") {
      breakdownTotals.search_total += cost;
      if (type === "search_brand") {
        breakdownTotals.search_brand_total += cost;
        const sb = dailySearchBrand.get(date) ?? 0;
        dailySearchBrand.set(date, sb + cost);
      } else {
        breakdownTotals.search_nonbrand_total += cost;
        const snb = dailySearchNonbrand.get(date) ?? 0;
        dailySearchNonbrand.set(date, snb + cost);
      }
    } else if (type === "pmax") {
      breakdownTotals.pmax_total += cost;
      const pmax = dailyPmax.get(date) ?? 0;
      dailyPmax.set(date, pmax + cost);
    } else {
      breakdownTotals.other_total += cost;
    }
  }

  for (const k of Object.keys(breakdownTotals)) {
    breakdownTotals[k] = Math.round(breakdownTotals[k] * 100) / 100;
  }

  return {
    dailySpend,
    dailySearchBrand,
    dailySearchNonbrand,
    dailyPmax,
    includedRows,
    breakdownTotals,
  };
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

interface SpendRow {
  project_id: string;
  ts: string;
  google_spend: number;
  google_search_brand_spend: number;
  google_search_nonbrand_spend: number;
  google_pmax_spend: number;
}

async function upsertGoogleSpend(
  projectId: string,
  dailyRows: SpendRow[]
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
    const brandTermsRaw = (formData.get("brand_terms") as string) || "";
    const brandTerms = brandTermsRaw
      .split(",")
      .map((t) => t.trim().toLowerCase())
      .filter(Boolean);

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
    const costCol = resolveColumn(headers, COST_COLS);
    const campaignCol = resolveColumn(headers, CAMPAIGN_COLS);
    const channelTypeCol = resolveColumn(headers, CHANNEL_TYPE_COLS);

    if (!dateCol) {
      return NextResponse.json(
        { status: "error", message: "No date column found. Expected one of: day, date, segments.date, date_(utc)" },
        { status: 400 }
      );
    }

    if (!costCol) {
      return NextResponse.json(
        { status: "error", message: "No cost column found. Expected one of: cost, amount_spent, spend, cost_(usd), cost_(eur)" },
        { status: 400 }
      );
    }

    if (!campaignCol) {
      return NextResponse.json(
        { status: "error", message: "No campaign column found. Expected one of: campaign, campaign_name" },
        { status: 400 }
      );
    }

    const channelTypeMissing = !channelTypeCol;
    const warnings: string[] = [];
    if (channelTypeMissing) {
      warnings.push(
        "Advertising channel type column not found — assuming all spend is SEARCH."
      );
    }

    const { dailySpend, dailySearchBrand, dailySearchNonbrand, dailyPmax, includedRows, breakdownTotals } = aggregateRows(
      parsedRows,
      dateCol,
      costCol,
      campaignCol,
      channelTypeCol ?? undefined,
      brandTerms
    );

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
      breakdownTotals,
    };

    if (totalDays < 30) {
      warnings.push(`Only ${totalDays} distinct days found (recommend at least 30).`);
    }
    if (totalSpend === 0) {
      warnings.push("Total Google spend is $0 across all included rows.");
    }
    if (includedRows === 0) {
      warnings.push("No rows with valid date + cost were found after parsing.");
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
      google_spend: Math.round((dailySpend.get(date) ?? 0) * 100) / 100,
      google_search_brand_spend: Math.round((dailySearchBrand.get(date) ?? 0) * 100) / 100,
      google_search_nonbrand_spend: Math.round((dailySearchNonbrand.get(date) ?? 0) * 100) / 100,
      google_pmax_spend: Math.round((dailyPmax.get(date) ?? 0) * 100) / 100,
    }));

    await upsertGoogleSpend(projectId, dailyRows);

    return NextResponse.json(
      { status: "success", summary, warnings: warnings.length > 0 ? warnings : undefined },
      { status: 200 }
    );
  } catch (error) {
    console.error("Google Ads upload error:", error);
    return NextResponse.json(
      {
        status: "error",
        message: error instanceof Error ? error.message : "Internal server error",
      },
      { status: 500 }
    );
  }
}
