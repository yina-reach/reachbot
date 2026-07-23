"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Lock } from "lucide-react";

// The backend scales to zero when idle, so the first login after a quiet spell
// pays a cold start (VM boot + ~100MB index load, ~30s). If the request runs
// past this threshold it's clearly a cold boot, not a fast auth check — show a
// reassuring "waking up" message so the wait doesn't read as a freeze.
const WAKING_MS = 2500;

export function PasswordGate({ onUnlock }: { onUnlock: () => void }) {
  const [pw, setPw] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [waking, setWaking] = useState(false);

  async function submit() {
    if (!pw || busy) return;
    setBusy(true);
    setError("");
    setWaking(false);
    const wakeTimer = setTimeout(() => setWaking(true), WAKING_MS);
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: pw }),
      });
      if (res.ok) {
        onUnlock();
        return; // leave busy true; the app view takes over on unlock
      }
      setError("Incorrect password.");
      setPw("");
    } catch {
      setError("Couldn't reach the server. Please try again.");
    } finally {
      clearTimeout(wakeTimer);
      setBusy(false);
      setWaking(false);
    }
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-6">
      <div className="flex size-10 items-center justify-center rounded-xl border">
        <Lock className="size-5 text-muted-foreground" />
      </div>
      <div className="text-center">
        <div className="text-base font-medium">ReachBot</div>
        <div className="text-xs text-muted-foreground">
          Reach Capital · Portfolio Founders
        </div>
      </div>
      <div className="flex w-full max-w-xs flex-col gap-2">
        <Input
          type="password"
          value={pw}
          autoFocus
          placeholder="Access password"
          onChange={(e) => setPw(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        {error && <p className="text-xs text-destructive">{error}</p>}
        <Button onClick={submit} disabled={busy || !pw}>
          {busy ? (waking ? "Waking up the server…" : "Checking…") : "Enter"}
        </Button>
        {waking && (
          <p className="text-center text-xs text-muted-foreground">
            The server sleeps when idle — this first load takes a few seconds.
          </p>
        )}
      </div>
    </div>
  );
}
