import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL, AUTH_COOKIE } from "@/lib/backend";

export const runtime = "nodejs";

/**
 * Proxy login to FastAPI. The backend validates the password against its own
 * ACCESS_PASSWORD and returns a signed token cookie; we re-issue that cookie as a
 * first-party httpOnly cookie on the frontend domain, so the browser stores it and
 * the /api/chat proxy can read + forward it. The password never reaches the client.
 */
export async function POST(req: NextRequest) {
  let password = "";
  try {
    ({ password } = await req.json());
  } catch {
    return NextResponse.json({ error: "Invalid body." }, { status: 400 });
  }

  const upstream = await fetch(`${BACKEND_URL}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });

  if (!upstream.ok) {
    return NextResponse.json(
      { error: "Incorrect password." },
      { status: upstream.status }
    );
  }

  // Extract the backend's rb_auth token from its Set-Cookie header.
  const setCookie = upstream.headers.get("set-cookie") || "";
  const match = setCookie.match(new RegExp(`${AUTH_COOKIE}=([^;]+)`));

  const res = NextResponse.json({ ok: true });
  if (match) {
    res.cookies.set(AUTH_COOKIE, match[1], {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
  }
  return res;
}
