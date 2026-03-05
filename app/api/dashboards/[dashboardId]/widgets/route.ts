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
  request: NextRequest,
  { params }: { params: Promise<{ dashboardId: string }> }
) {
  const { dashboardId } = await params;
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
  const { data, error } = await supabase
    .from("dashboard_widgets")
    .select("id, project_id, x, y, w, h")
    .eq("dashboard_id", dashboardId);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ widgets: data ?? [] });
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ dashboardId: string }> }
) {
  const { dashboardId } = await params;
  const auth = await createClient();
  const { data: { user } } = await auth.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const ok = await checkOwnership(dashboardId, user.id);
  if (!ok) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  let body: { project_id?: string; x?: number; y?: number; w?: number; h?: number };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const project_id = body?.project_id;
  if (!project_id || typeof project_id !== "string") {
    return NextResponse.json({ error: "project_id is required" }, { status: 400 });
  }

  const supabase = getSupabaseServiceClient();

  const { data: proj } = await supabase
    .from("projects")
    .select("id")
    .eq("id", project_id)
    .eq("user_id", user.id)
    .single();

  if (!proj) {
    return NextResponse.json({ error: "Project not found or access denied" }, { status: 404 });
  }

  const x = typeof body?.x === "number" ? body.x : 0;
  const y = typeof body?.y === "number" ? body.y : 0;
  const w = typeof body?.w === "number" ? body.w : 2;
  const h = typeof body?.h === "number" ? body.h : 1;

  const { data, error } = await supabase
    .from("dashboard_widgets")
    .insert({ dashboard_id: dashboardId, project_id, x, y, w, h })
    .select("id, project_id, x, y, w, h")
    .single();

  if (error) {
    if (error.code === "23505") {
      return NextResponse.json({ error: "Analysis already on dashboard" }, { status: 409 });
    }
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}
