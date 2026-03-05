import { NextRequest } from "next/server";

const BACKEND_URL =
  process.env.ORBITAL_BACKEND_URL || "http://localhost:8000";

export async function GET(request: NextRequest) {
  const force = request.nextUrl.searchParams.get("force") === "true";
  const url = `${BACKEND_URL}/v1/pipeline/tree${force ? "?force=true" : ""}`;

  try {
    const res = await fetch(url, { cache: "no-store" });

    if (!res.ok) {
      return new Response(
        JSON.stringify({ error: `Backend error: ${res.status}` }),
        { status: res.status }
      );
    }

    const data = await res.json();
    return Response.json(data);
  } catch (err) {
    console.error("Pipeline tree proxy error:", err);
    return new Response(
      JSON.stringify({ error: "Could not connect to modeling engine" }),
      { status: 502 }
    );
  }
}
