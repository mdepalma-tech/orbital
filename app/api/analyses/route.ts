import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { getSupabaseServiceClient } from "@/lib/supabase/service";

export async function GET() {
  const auth = await createClient();
  const { data: { user } } = await auth.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const supabase = getSupabaseServiceClient();

  const { data: projects, error: projErr } = await supabase
    .from("projects")
    .select("id, name, created_at")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  if (projErr || !projects?.length) {
    return NextResponse.json({ analyses: [] });
  }

  const projectIds = projects.map((p) => p.id);

  const { data: models } = await supabase
    .from("models")
    .select("id, project_id")
    .in("project_id", projectIds);

  if (!models?.length) {
    return NextResponse.json({
      analyses: projects.map((p) => ({
        id: p.id,
        projectId: p.id,
        name: p.name || "Untitled Analysis",
        status: "complete",
        metrics: { revenue_impact: "—", roi: "—", confidence: "—" },
        created_at: p.created_at,
      })),
    });
  }

  const modelIds = models.map((m) => m.id);
  const { data: versions } = await supabase
    .from("model_versions")
    .select("id, model_id, r2, confidence_level, created_at")
    .in("model_id", modelIds)
    .order("created_at", { ascending: false });

  const modelToProject = new Map(models.map((m) => [m.id, m.project_id]));
  type VersionRow = { id: string; model_id: string; r2: number; confidence_level: string; created_at: string };
  const projectToVersion = new Map<string, VersionRow>();
  for (const v of versions || []) {
    const pid = modelToProject.get(v.model_id);
    if (pid && !projectToVersion.has(pid)) {
      projectToVersion.set(pid, v);
    }
  }

  const analyses = projects.map((p) => {
    const mv = projectToVersion.get(p.id);
    return {
      id: p.id,
      projectId: p.id,
      name: p.name || "Untitled Analysis",
      status: "complete" as const,
      metrics: {
        revenue_impact: mv ? `R² ${(Number(mv.r2) * 100).toFixed(1)}%` : "—",
        roi: "—",
        confidence: mv?.confidence_level ?? "—",
      },
      created_at: mv?.created_at ?? p.created_at,
    };
  });

  return NextResponse.json({ analyses });
}
