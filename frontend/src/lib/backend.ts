/**
 * Server-only backend config. The browser never sees BACKEND_URL — all traffic
 * goes through the Next.js /api proxy routes, which attach the auth cookie and
 * forward to FastAPI.
 */
export const BACKEND_URL = (
  process.env.BACKEND_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

/** Name of the httpOnly auth cookie issued by the backend. */
export const AUTH_COOKIE = "rb_auth";
