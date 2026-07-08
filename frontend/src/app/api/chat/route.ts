import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL, AUTH_COOKIE } from "@/lib/backend";

export const runtime = "nodejs";
// SSE must not be buffered or statically optimized.
export const dynamic = "force-dynamic";

/**
 * Proxy the chat request to FastAPI, forwarding the auth cookie, and stream the
 * SSE response straight back to the browser. The backend URL / cookie stay
 * server-side; the client only ever talks to this same-origin route.
 */
export async function POST(req: NextRequest) {
  let question = "";
  try {
    ({ question } = await req.json());
  } catch {
    return NextResponse.json({ error: "Invalid body." }, { status: 400 });
  }

  const token = req.cookies.get(AUTH_COOKIE)?.value;

  const upstream = await fetch(`${BACKEND_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Cookie: `${AUTH_COOKIE}=${token}` } : {}),
    },
    body: JSON.stringify({ question }),
  });

  if (upstream.status === 401) {
    return NextResponse.json({ error: "Unauthorized." }, { status: 401 });
  }
  if (!upstream.ok || !upstream.body) {
    return NextResponse.json(
      { error: "Upstream error." },
      { status: upstream.status || 502 }
    );
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
