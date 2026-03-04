import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.ORBITAL_BACKEND_URL || "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ projectId: string; scenarioId: string }> }
) {
  const { projectId, scenarioId } = await params;
  if (!projectId || !scenarioId) {
    return NextResponse.json(
      { error: "Missing projectId or scenarioId" },
      { status: 400 }
    );
  }

  try {
    const res = await fetch(
      `${BACKEND_URL}/v1/projects/${projectId}/forecast/scenarios/${scenarioId}`,
      { method: "GET" }
    );
    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json(
        data || { error: `Backend error: ${res.status}` },
        { status: res.status }
      );
    }
    return NextResponse.json(data);
  } catch (err) {
    console.error("Forecast scenario get error:", err);
    return NextResponse.json(
      { error: "Could not connect to modeling engine" },
      { status: 502 }
    );
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ projectId: string; scenarioId: string }> }
) {
  const { projectId, scenarioId } = await params;
  if (!projectId || !scenarioId) {
    return NextResponse.json(
      { error: "Missing projectId or scenarioId" },
      { status: 400 }
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  try {
    const res = await fetch(
      `${BACKEND_URL}/v1/projects/${projectId}/forecast/scenarios/${scenarioId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    );
    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json(
        data || { error: `Backend error: ${res.status}` },
        { status: res.status }
      );
    }
    return NextResponse.json(data);
  } catch (err) {
    console.error("Forecast scenario update error:", err);
    return NextResponse.json(
      { error: "Could not connect to modeling engine" },
      { status: 502 }
    );
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ projectId: string; scenarioId: string }> }
) {
  const { projectId, scenarioId } = await params;
  if (!projectId || !scenarioId) {
    return NextResponse.json(
      { error: "Missing projectId or scenarioId" },
      { status: 400 }
    );
  }

  try {
    const res = await fetch(
      `${BACKEND_URL}/v1/projects/${projectId}/forecast/scenarios/${scenarioId}`,
      { method: "DELETE" }
    );
    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json(
        data || { error: `Backend error: ${res.status}` },
        { status: res.status }
      );
    }
    return NextResponse.json(data);
  } catch (err) {
    console.error("Forecast scenario delete error:", err);
    return NextResponse.json(
      { error: "Could not connect to modeling engine" },
      { status: 502 }
    );
  }
}
