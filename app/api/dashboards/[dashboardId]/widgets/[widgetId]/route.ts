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

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ dashboardId: string; widgetId: string }> }
) {
  const { dashboardId, widgetId } = await params;
  const auth = await createClient();
  const { data: { user } } = await auth.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const ok = await checkOwnership(dashboardId, user.id);
  if (!ok) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  let body: { x?: number; y?: number; w?: number; h?: number };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const updates: Record<string, number> = {};
  if (typeof body?.x === "number") updates.x = body.x;
  if (typeof body?.y === "number") updates.y = body.y;
  if (typeof body?.w === "number") updates.w = body.w;
  if (typeof body?.h === "number") updates.h = body.h;

  if (Object.keys(updates).length === 0) {
    return NextResponse.json({ error: "No valid updates" }, { status: 400 });
  }

  const supabase = getSupabaseServiceClient();
  const { data, error } = await supabase
    .from("dashboard_widgets")
    .update(updates)
    .eq("id", widgetId)
    .eq("dashboard_id", dashboardId)
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ dashboardId: string; widgetId: string }> }
) {
  const { dashboardId, widgetId } = await params;
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
  const { error } = await supabase
    .from("dashboard_widgets")
    .delete()
    .eq("id", widgetId)
    .eq("dashboard_id", dashboardId);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ deleted: true });
}
