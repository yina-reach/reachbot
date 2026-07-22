"use client";

import { useEffect, useRef, useState } from "react";
import { useChat } from "@/lib/use-chat";
import { Welcome, PromptSuggestions, ScopeFooter } from "@/components/welcome";
import { Message } from "@/components/message";
import { ChatInput } from "@/components/chat-input";
import { PasswordGate } from "@/components/password-gate";
import { ThemeToggle } from "@/components/theme-toggle";

function Header() {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b bg-background/80 px-4 backdrop-blur sm:px-6">
      <div className="flex items-center gap-2">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/reachbot-logo.svg"
          alt="ReachBot"
          width={24}
          height={24}
          className="size-6 rounded-md bg-[#1E2015]"
        />
        <span className="text-sm font-medium">ReachBot</span>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="size-1.5 rounded-full bg-emerald-500" />
          ReachIn · Portfolio
        </div>
        <ThemeToggle />
      </div>
    </header>
  );
}

export default function Home() {
  const { messages, busy, send } = useChat();
  const [gate, setGate] = useState<"loading" | "locked" | "open">("loading");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/session")
      .then((r) => r.json())
      .then((j) => setGate(j.authed ? "open" : "locked"))
      .catch(() => setGate("open")); // fail open; chat call re-validates
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(q: string) {
    const r = await send(q);
    if (r?.unauthorized) setGate("locked");
  }

  if (gate === "loading") {
    return <div className="min-h-dvh" />;
  }
  if (gate === "locked") {
    return <PasswordGate onUnlock={() => setGate("open")} />;
  }

  const empty = messages.length === 0;

  // ── Empty state: input vertically centered, prompts under it, scope at bottom ──
  if (empty) {
    return (
      <div className="flex min-h-dvh flex-col">
        <Header />
        <main className="flex flex-1 flex-col">
          <div className="flex flex-1 flex-col items-center justify-center gap-8 px-4 py-10">
            <Welcome />
            <div className="w-full max-w-3xl">
              <ChatInput onSend={handleSend} disabled={busy} minRows={2} />
              {/* Prompt suggestions are desktop-only — mobile keeps the empty state lean. */}
              <div className="hidden sm:block">
                <PromptSuggestions onPick={handleSend} />
              </div>
            </div>
          </div>
          <div className="pb-8 pt-4">
            <ScopeFooter />
          </div>
        </main>
      </div>
    );
  }

  // ── Conversation: thread scrolls, input docked to the bottom ──────────────────
  return (
    <div className="flex min-h-dvh flex-col">
      <Header />
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 pb-40 pt-4 sm:px-6">
        <div className="flex flex-col gap-4">
          {messages.map((m, i) => (
            // All sources retrieved so far — answers may cite a resource from an
            // earlier turn, and its chip/card must still resolve.
            <Message
              key={i}
              message={m}
              allSources={messages.flatMap((msg) => msg.sources ?? [])}
            />
          ))}
        </div>
        <div ref={bottomRef} />
      </main>

      <div className="fixed inset-x-0 bottom-0 z-20 bg-gradient-to-t from-background via-background to-transparent pb-6 pt-8">
        <div className="mx-auto w-full max-w-3xl px-4 sm:px-6">
          <ChatInput onSend={handleSend} disabled={busy} />
          <p className="mt-2 text-center text-xs text-muted-foreground">
            Answers from ReachIn only ·{" "}
            <a
              href="https://reachcapital.com"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:underline"
            >
              Reach Capital
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
