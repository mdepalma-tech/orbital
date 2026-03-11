import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { getSupabaseServiceClient } from "@/lib/supabase/service";

async function checkOwnership(dashboardId: string, userId: string): Promise<boolean> {
  const supabase = getSupabaseServiceClient();
  const { data } = await supabase
    .from("dashboards")
    .select("id")
    .eq("id", dashboardId)
    .eq("user_id", userId)
    .single();
  return !!data;
}

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ dashboardId: string }> }
) {
  const { dashboardId } = await context.params;
  const auth = await createClient();
  const { data: { user } } = await auth.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const ok = await checkOwnership(dashboardId, user.id);
  if (!ok) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const supabase = getSupabaseServiceClient();
  const { data: dashboard, error: dashErr } = await supabase
    .from("dashboards")
    .select("id, name, is_default, created_at")
    .eq("id", dashboardId)
    .single();

  if (dashErr || !dashboard) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const { data: widgets } = await supabase
    .from("dashboard_widgets")
    .select("id, project_id, x, y, w, h")
    .eq("dashboard_id", dashboardId);

  return NextResponse.json({ ...dashboard, widgets: widgets ?? [] });
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ dashboardId: string }> }
) {
  const { dashboardId } = await context.params;
  const auth = await createClient();
  const { data: { user } } = await auth.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const ok = await checkOwnership(dashboardId, user.id);
  if (!ok) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  let body: { name?: string; is_default?: boolean };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const updates: Record<string, unknown> = {};
  if (typeof body?.name === "string" && body.name.trim()) {
    updates.name = body.name.trim();
  }
  if (typeof body?.is_default === "boolean") {
    updates.is_default = body.is_default;
  }
  if (Object.keys(updates).length === 0) {
    return NextResponse.json({ error: "No valid updates" }, { status: 400 });
  }

  const supabase = getSupabaseServiceClient();

  if (body?.is_default === true) {
    await supabase
      .from("dashboards")
      .update({ is_default: false })
      .eq("user_id", user.id);
  }

  const { data, error } = await supabase
    .from("dashboards")
    .update({ ...updates, updated_at: new Date().toISOString() })
    .eq("id", dashboardId)
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}

export async function DELETE(
  _request: NextRequest,
  context: { params: Promise<{ dashboardId: string }> }
) {
  const { dashboardId } = await context.params;
  const auth = await createClient();
  const { data: { user } } = await auth.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const ok = await checkOwnership(dashboardId, user.id);
  if (!ok) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const supabase = getSupabaseServiceClient();
  const { error } = await supabase.from("dashboards").delete().eq("id", dashboardId);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ deleted: true });
}
