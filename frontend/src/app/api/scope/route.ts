import { NextResponse } from "next/server";
import { BACKEND_URL } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Proxy the index scope breakdown (source counts by type) for the empty state. */
export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/scope`, { cache: "no-store" });
    if (!res.ok) return NextResponse.json({ total: 0, by_type: {} });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ total: 0, by_type: {} });
  }
}
