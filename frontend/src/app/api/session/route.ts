import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL, AUTH_COOKIE } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Tells the client whether the app is gated and whether the caller already holds a
 * valid session. We verify the cookie by making a cheap authenticated probe to the
 * backend /chat (with an empty body → 400 if authed, 401 if not) — but to avoid a
 * wasted embed, we instead check gating via /health and trust cookie presence for
 * the optimistic render; /api/chat re-validates on the real request anyway.
 */
export async function GET(req: NextRequest) {
  let gated = false;
  try {
    const health = await fetch(`${BACKEND_URL}/health`, { cache: "no-store" });
    if (health.ok) {
      const j = await health.json();
      gated = Boolean(j.gated);
    }
  } catch {
    // Backend unreachable — treat as gated=false so the UI still renders; the
    // chat call will surface the real error.
    gated = false;
  }

  const hasCookie = Boolean(req.cookies.get(AUTH_COOKIE)?.value);
  return NextResponse.json({ gated, authed: !gated || hasCookie });
}
