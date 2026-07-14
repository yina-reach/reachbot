import { NextResponse } from "next/server";
import { BACKEND_URL } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Proxy the per-type sample resources that power the /preview design page. */
export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/samples`, { cache: "no-store" });
    if (!res.ok) return NextResponse.json({});
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({});
  }
}
