import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { getSupabaseServiceClient } from "@/lib/supabase/service";

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  if (!projectId) {
    return NextResponse.json({ error: "Missing projectId" }, { status: 400 });
  }

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const { data, error } = await supabase
    .from("projects")
    .select("id, name, created_at")
    .eq("id", projectId)
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: error?.message ?? "Project not found" },
      { status: error?.code === "PGRST116" ? 404 : 500 }
    );
  }

  return NextResponse.json(data);
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  if (!projectId) {
    return NextResponse.json({ error: "Missing projectId" }, { status: 400 });
  }

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  let body: { name?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  if (typeof body.name !== "string" || body.name.trim().length === 0) {
    return NextResponse.json({ error: "name must be a non-empty string" }, { status: 400 });
  }

  const name = body.name.trim();
  const supabaseAdmin = getSupabaseServiceClient();

  // Upsert: insert if not exists, update name if exists (updated_at set by trigger/default)
  const row: Record<string, unknown> = {
    id: projectId,
    user_id: user.id,
    name,
  };
  // Include shopify_store_domain if column exists (upload routes use it when creating projects)
  const { data, error } = await supabaseAdmin
    .from("projects")
    .upsert(row, { onConflict: "id" })
    .select("id, name")
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  return NextResponse.json(data);
}
