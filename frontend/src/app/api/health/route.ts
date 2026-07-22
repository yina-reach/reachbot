import { NextResponse } from "next/server";
import { BACKEND_URL } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Proxy backend readiness + the index's last-synced time (for the header). */
export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/health`, { cache: "no-store" });
    if (!res.ok) return NextResponse.json({ ok: false });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ ok: false });
  }
}
