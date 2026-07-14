"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Lock } from "lucide-react";

export function PasswordGate({ onUnlock }: { onUnlock: () => void }) {
  const [pw, setPw] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!pw || busy) return;
    setBusy(true);
    setError("");
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw }),
    });
    setBusy(false);
    if (res.ok) {
      onUnlock();
    } else {
      setError("Incorrect password.");
      setPw("");
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
          {busy ? "Checking…" : "Enter"}
        </Button>
      </div>
    </div>
  );
}
