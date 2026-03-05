import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { getSupabaseServiceClient } from "@/lib/supabase/service";

async function checkProjectAccess(
  projectId: string,
  userId: string
): Promise<{ ok: boolean; error?: Response }> {
  const supabase = getSupabaseServiceClient();
  const { data } = await supabase
    .from("projects")
    .select("id")
    .eq("id", projectId)
    .eq("user_id", userId)
    .single();
  if (!data) {
    return { ok: false, error: NextResponse.json({ error: "Project not found" }, { status: 404 }) };
  }
  return { ok: true };
}

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  if (!projectId) {
    return NextResponse.json({ error: "Missing projectId" }, { status: 400 });
  }

  const auth = await createClient();
  const { data: { user } } = await auth.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const access = await checkProjectAccess(projectId, user.id);
  if (!access.ok) return access.error!;

  const supabase = getSupabaseServiceClient();
  const { data, error } = await supabase
    .from("run_chat_messages")
    .select("id, role, content, created_at")
    .eq("project_id", projectId)
    .eq("user_id", user.id)
    .order("created_at", { ascending: true });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const messages = (data ?? []).map((m) => ({
    id: m.id,
    role: m.role as "assistant" | "user",
    content: m.content,
  }));

  return NextResponse.json({ messages });
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  if (!projectId) {
    return NextResponse.json({ error: "Missing projectId" }, { status: 400 });
  }

  const auth = await createClient();
  const { data: { user } } = await auth.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const access = await checkProjectAccess(projectId, user.id);
  if (!access.ok) return access.error!;

  let body: { role?: string; content?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const role = body.role === "user" ? "user" : "assistant";
  const content = typeof body.content === "string" ? body.content.trim() : "";
  if (!content) {
    return NextResponse.json({ error: "content is required" }, { status: 400 });
  }

  const supabase = getSupabaseServiceClient();
  const { data, error } = await supabase
    .from("run_chat_messages")
    .insert({
      project_id: projectId,
      user_id: user.id,
      role,
      content,
    })
    .select("id, role, content")
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({
    id: data.id,
    role: data.role,
    content: data.content,
  });
}
