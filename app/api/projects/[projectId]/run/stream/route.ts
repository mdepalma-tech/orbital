import { NextRequest } from "next/server";

const BACKEND_URL =
  process.env.ORBITAL_BACKEND_URL || "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await params;
  if (!projectId) {
    return new Response("Missing projectId", { status: 400 });
  }

  try {
    const res = await fetch(
      `${BACKEND_URL}/v1/projects/${projectId}/run/stream`,
      {
        cache: "no-store",
        headers: {
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        },
      }
    );

    if (!res.ok) {
      return new Response(
        JSON.stringify({ error: `Backend error: ${res.status}` }),
        { status: res.status }
      );
    }

    return new Response(res.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (err) {
    console.error("Stream proxy error:", err);
    return new Response(
      JSON.stringify({ error: "Could not connect to modeling engine" }),
      { status: 502 }
    );
  }
}
