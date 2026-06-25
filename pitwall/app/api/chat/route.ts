import { NextRequest, NextResponse } from "next/server";

const PYTHON_API = process.env.PYTHON_API_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const query: string = body.query ?? "";

  if (!query.trim()) {
    return NextResponse.json({ error: "Empty query" }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${PYTHON_API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });

    if (!upstream.ok) {
      const text = await upstream.text();
      return NextResponse.json(
        { error: `Backend error: ${upstream.status}`, detail: text },
        { status: 502 }
      );
    }

    const data = await upstream.json();
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { error: "Could not reach Python backend", detail: String(err) },
      { status: 503 }
    );
  }
}
