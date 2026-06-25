import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const year  = searchParams.get("year");
  const round = searchParams.get("round");

  if (!year || !round) {
    return NextResponse.json({ error: "year and round are required" }, { status: 400 });
  }

  try {
    const upstream = await fetch(
      `${API_URL}/race?year=${year}&round=${round}`,
      { cache: "no-store" },
    );

    if (!upstream.ok) {
      const text = await upstream.text();
      return NextResponse.json(
        { error: `Backend error: ${upstream.status}`, detail: text },
        { status: upstream.status },
      );
    }

    const data = await upstream.json();
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { error: "Could not reach Python backend", detail: String(err) },
      { status: 503 },
    );
  }
}
