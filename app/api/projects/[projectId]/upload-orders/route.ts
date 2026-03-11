import { createClient } from "@supabase/supabase-js";
import { createClient as createServerClient } from "@/lib/supabase/server";
import { NextRequest, NextResponse } from "next/server";
import { parse } from "csv-parse/sync";

// Types
interface ShopifyOrderRow {
  name?: string;
  created_at?: string;
  financial_status?: string;
  currency?: string;
  subtotal?: string;
  discount_amount?: string;
  total?: string;
  cancelled_at?: string;
}

interface AggregatedDay {
  date: string;
  revenue: number;
  orders: number;
}

interface ParseSummary {
  dateRange: { start: string; end: string };
  totalDays: number;
  totalRows: number;
  paidRows: number;
  excludedRows: number;
  totalOrders: number;
  totalRevenue: number;
  averageDailyRevenue: number;
}

interface UploadResponse {
  status: "success" | "preview" | "error";
  message?: string;
  summary?: ParseSummary;
  warnings?: string[];
  dateRange?: { start: string; end: string };
  totalDays?: number;
  totalOrders?: number;
  totalRevenue?: number;
  averageDailyRevenue?: number;
}

// Initialize Supabase client with service role key (server-side only)
function getSupabaseServiceClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!supabaseUrl || !supabaseServiceKey) {
    throw new Error("Missing Supabase environment variables");
  }

  return createClient(supabaseUrl, supabaseServiceKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });
}

// Validate CSV headers (after parseCSV, spaces are already replaced with underscores)
function validateHeaders(headers: string[]) {
  const normalizedHeaders = headers.map((h) =>
    h.toLowerCase().trim().replace(/ /g, "_")
  );

  const warnings: string[] = [];
  const errors: string[] = [];

  // Required: created_at
  if (!normalizedHeaders.includes("created_at")) {
    errors.push("created at");
  }

  // Revenue columns (at least one required)
  const revenueCandidates = [
    "total",
    "total_sales",
    "net_sales",
    "total_price",
    "subtotal",
    "amount",
    "amount_paid"
  ];

  const hasRevenue = revenueCandidates.some((col) =>
    normalizedHeaders.includes(col)
  );

  if (!hasRevenue) {
    errors.push("revenue column (total, net_sales, total_sales, etc.)");
  }

  // Optional columns
  if (!normalizedHeaders.includes("financial_status")) {
    warnings.push(
      "Financial status column not found — assuming all rows are paid."
    );
  }

  if (!normalizedHeaders.includes("cancelled_at")) {
    warnings.push(
      "Cancelled at column not found — assuming no cancelled orders."
    );
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

// Parse CSV with robust error handling
function parseCSV(fileContent: string): ShopifyOrderRow[] {
  try {
    const records = parse(fileContent, {
      columns: (header) => header.map((col: string) => col.toLowerCase().trim().replace(/ /g, "_")),
      skip_empty_lines: true,
      trim: true,
      cast: false,
      relax_column_count: true,
    });

    return records;
  } catch (error) {
    throw new Error(`CSV parsing failed: ${error instanceof Error ? error.message : "Unknown error"}`);
  }
}

// Parse date string to YYYY-MM-DD. No timezone conversion — assumes orders and spend use same dates.
// Extract date prefix from ISO-like strings (2022-12-25, 2022-12-25T..., 2022-12-25 ...) to avoid
// new Date() parsing shifts (e.g. "2022-12-25T00:00:00" = local midnight → toISOString = prev day in TZ east of UTC).
function toDateString(dateStr: string): string {
  const s = dateStr.trim();
  if (!s) throw new Error("Empty date string");

  // Any string starting with YYYY-MM-DD: extract date part (matches spend upload logic)
  if (/^\d{4}-\d{1,2}-\d{1,2}/.test(s)) {
    const match = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (match) {
      const month = parseInt(match[2], 10);
      const day = parseInt(match[3], 10);
      if (month >= 1 && month <= 12 && day >= 1 && day <= 31) {
        return `${match[1]}-${match[2].padStart(2, "0")}-${match[3].padStart(2, "0")}`;
      }
    }
  }

  const date = new Date(s);
  if (isNaN(date.getTime())) {
    const parts = s.match(/(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})/);
    if (parts) {
      const year = parts[3].length === 2 ? `20${parts[3]}` : parts[3];
      return `${year}-${parts[1].padStart(2, "0")}-${parts[2].padStart(2, "0")}`;
    }
    throw new Error(`Invalid date: ${dateStr}`);
  }
  return date.toISOString().slice(0, 10);
}

function resolveColumn<T extends Record<string, any>>(
  row: T,
  candidates: string[]
): string | undefined {
  const keys = Object.keys(row);
  for (const candidate of candidates) {
    if (keys.includes(candidate)) return candidate;
  }
  return undefined;
}

// Aggregate orders by date
function aggregateDaily(rows: ShopifyOrderRow[]): { aggregatedData: AggregatedDay[]; includedRows: number } {
  const dailyMap = new Map<string, { revenue: number; orders: number }>();
  let includedRows = 0;

  for (const row of rows) {
    // Skip cancelled orders (if cancelled_at column exists)
    if (row.cancelled_at && row.cancelled_at.trim() !== "") {
      continue;
    }

    // If financial_status exists, include paid/partially_paid; if missing, assume paid
    const status = row.financial_status?.toLowerCase().trim();
    if (status && !status.includes("paid")) {
      continue;
    }

    // Parse date
    if (!row.created_at) {
      continue;
    }

    let localDate: string;
    try {
      localDate = toDateString(row.created_at);
    } catch {
      continue; // Skip invalid dates
    }

    // Resolve revenue column dynamically (common Shopify exports)
    const revenueColumn = resolveColumn(row as Record<string, any>, [
      "total",
      "total_sales",
      "net_sales",
      "total_price",
      "amount",
      "amount_paid"
    ]);

    let total = 0;
    const rowRecord = row as Record<string, unknown>;

    if (revenueColumn && rowRecord[revenueColumn]) {
      const raw = String(rowRecord[revenueColumn]).trim();
      total = parseFloat(raw.replace(/[^0-9.-]/g, ""));
    } else {
      // Fallback: subtotal - discount_amount (if available)
      const subtotalRaw = String(row.subtotal || "0").trim();
      const discountRaw = String(row.discount_amount || "0").trim();
      const subtotal = parseFloat(subtotalRaw.replace(/[^0-9.-]/g, ""));
      const discount = parseFloat(discountRaw.replace(/[^0-9.-]/g, ""));
      total = (isNaN(subtotal) ? 0 : subtotal) - (isNaN(discount) ? 0 : discount);
    }

    // Skip rows with invalid revenue instead of failing the entire upload
    if (!Number.isFinite(total)) {
      continue;
    }

    // Aggregate
    const existing = dailyMap.get(localDate) || { revenue: 0, orders: 0 };
    dailyMap.set(localDate, {
      revenue: existing.revenue + total,
      orders: existing.orders + 1,
    });
    includedRows++;
  }

  // Convert to array and sort by date
  const aggregatedData = Array.from(dailyMap.entries())
    .map(([date, data]) => ({
      date,
      revenue: Math.round(data.revenue * 100) / 100, // Round to 2 decimals
      orders: data.orders,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));

  return { aggregatedData, includedRows };
}

// Ensure the project row exists (creates it if missing, using project name from first step)
async function ensureProjectExists(
  projectId: string,
  userId: string,
  projectName: string = "Untitled Analysis"
): Promise<void> {
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
      name: projectName.trim() || "Untitled Analysis",
      shopify_store_domain: "",
    });

    if (error && error.code !== "23505") {
      throw new Error(`Failed to create project: ${error.message}`);
    }
  }
}

// Upsert time series data to Supabase
async function upsertTimeseries(
  projectId: string,
  aggregatedData: AggregatedDay[]
): Promise<void> {
  const supabase = getSupabaseServiceClient();

  // Prepare rows for upsert
  const rows = aggregatedData.map((day) => ({
    project_id: projectId,
    ts: day.date,
    revenue: day.revenue,
    orders: day.orders,
    sessions: null, // Not provided in orders CSV
  }));

  // Batch upsert
  const { error } = await supabase
    .from("project_timeseries")
    .upsert(rows, {
      onConflict: "project_id,ts",
      ignoreDuplicates: false,
    });

  if (error) {
    throw new Error(`Database upsert failed: ${error.message}`);
  }
}

// Main POST handler
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ projectId: string }> }
): Promise<NextResponse<UploadResponse>> {
  try {
    const { projectId } = await params;

    // Get authenticated user
    const supabaseAuth = await createServerClient();
    const { data: { user } } = await supabaseAuth.auth.getUser();
    if (!user) {
      return NextResponse.json(
        { status: "error", message: "Not authenticated" },
        { status: 401 }
      );
    }

    // Parse multipart form data
    const formData = await request.formData();
    const file = formData.get("file") as File | null;
    const mode = (formData.get("mode") as string) || "save";
    const projectName = (formData.get("projectName") as string) || "Untitled Analysis";

    if (!file) {
      return NextResponse.json(
        {
          status: "error",
          message: "No file provided",
        },
        { status: 400 }
      );
    }

    // Validate file type
    if (!file.name.endsWith(".csv")) {
      return NextResponse.json(
        {
          status: "error",
          message: "File must be a CSV",
        },
        { status: 400 }
      );
    }

    // Read file content
    const fileContent = await file.text();

    if (!fileContent || fileContent.trim().length === 0) {
      return NextResponse.json(
        {
          status: "error",
          message: "File is empty",
        },
        { status: 400 }
      );
    }

    // Parse CSV
    let parsedRows: ShopifyOrderRow[];
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
        {
          status: "error",
          message: "No data rows found in CSV",
        },
        { status: 400 }
      );
    }

    // Validate headers
    const headers = Object.keys(parsedRows[0]);
    const validation = validateHeaders(headers);

    if (!validation.valid) {
      return NextResponse.json(
        {
          status: "error",
          message: `Missing required columns: ${validation.errors.join(", ")}`,
        },
        { status: 400 }
      );
    }

    // Aggregate by date
    let aggregatedData: AggregatedDay[];
    let includedRows: number;
    try {
      const result = aggregateDaily(parsedRows);
      aggregatedData = result.aggregatedData;
      includedRows = result.includedRows;
    } catch (error) {
      return NextResponse.json(
        {
          status: "error",
          message: error instanceof Error ? error.message : "Data aggregation failed",
        },
        { status: 400 }
      );
    }

    // Calculate summary statistics
    const totalOrders = aggregatedData.reduce((sum, day) => sum + day.orders, 0);
    const totalRevenue = aggregatedData.reduce((sum, day) => sum + day.revenue, 0);
    const averageDailyRevenue = aggregatedData.length > 0 ? totalRevenue / aggregatedData.length : 0;

    // Count excluded rows (filtered out by financial_status, cancelled_at, invalid date, or invalid revenue)
    const paidRows = includedRows;
    const excludedRows = Math.max(0, parsedRows.length - includedRows);

    const summary: ParseSummary = {
      dateRange: {
        start: aggregatedData.length > 0 ? aggregatedData[0].date : "N/A",
        end: aggregatedData.length > 0 ? aggregatedData[aggregatedData.length - 1].date : "N/A",
      },
      totalDays: aggregatedData.length,
      totalRows: parsedRows.length,
      paidRows,
      excludedRows,
      totalOrders,
      totalRevenue: Math.round(totalRevenue * 100) / 100,
      averageDailyRevenue: Math.round(averageDailyRevenue * 100) / 100,
    };

    // Preview mode: return summary without writing to DB
    if (mode === "preview") {
      // Still run validation checks so the user sees warnings
      const warnings: string[] = [];
      if (aggregatedData.length < 60) {
        warnings.push(`Only ${aggregatedData.length} distinct days found (minimum 60 required to save)`);
      }
      if (totalOrders === 0) {
        warnings.push("No paid orders found in the uploaded data");
      }

      const allWarnings = [...warnings, ...(validation.warnings || [])];

      return NextResponse.json(
        {
          status: "preview" as const,
          summary,
          warnings: allWarnings.length > 0 ? allWarnings : undefined,
        },
        { status: 200 }
      );
    }

    // Save mode: validate then write
    if (aggregatedData.length < 60) {
      return NextResponse.json(
        {
          status: "error",
          message: `Insufficient data: only ${aggregatedData.length} distinct days found (minimum 60 required)`,
        },
        { status: 400 }
      );
    }

    if (totalOrders === 0) {
      return NextResponse.json(
        {
          status: "error",
          message: "No paid orders found in the uploaded data",
        },
        { status: 400 }
      );
    }

    // Ensure project exists (creates with name from first step if new), then upsert timeseries
    await ensureProjectExists(projectId, user.id, projectName);
    await upsertTimeseries(projectId, aggregatedData);

    const allWarnings = validation.warnings || [];

    // Return success response
    return NextResponse.json(
      {
        status: "success",
        summary,
        dateRange: summary.dateRange,
        totalDays: summary.totalDays,
        totalOrders: summary.totalOrders,
        totalRevenue: summary.totalRevenue,
        averageDailyRevenue: summary.averageDailyRevenue,
        warnings: allWarnings.length > 0 ? allWarnings : undefined,
      },
      { status: 200 }
    );
  } catch (error) {
    console.error("Upload error:", error);

    return NextResponse.json(
      {
        status: "error",
        message: error instanceof Error ? error.message : "Internal server error",
      },
      { status: 500 }
    );
  }
}
