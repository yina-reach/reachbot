"use client";

import { useCallback, useState } from "react";
import type { ChatMessage, Source } from "@/lib/types";

/**
 * Minimal streaming-chat hook. POSTs to the same-origin /api/chat proxy and parses
 * the SSE events emitted by the FastAPI backend:
 *   event: sources  → Source[]   (once, before tokens)
 *   event: token    → string     (appended to the answer as it streams)
 *   event: done     → {}         (end)
 */
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);

  const send = useCallback(
    async (question: string) => {
      if (busy) return;
      setBusy(true);

      // Append the user message + a placeholder assistant message (streaming).
      setMessages((m) => [
        ...m,
        { role: "user", content: question },
        { role: "assistant", content: "", streaming: true },
      ]);

      // Index of the assistant message we're filling in.
      const patchLast = (fn: (msg: ChatMessage) => ChatMessage) =>
        setMessages((m) => {
          const copy = [...m];
          const i = copy.length - 1;
          copy[i] = fn(copy[i]);
          return copy;
        });

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question }),
        });

        if (res.status === 401) {
          patchLast((msg) => ({
            ...msg,
            content: "_Session expired — please log in again._",
            streaming: false,
          }));
          setBusy(false);
          return { unauthorized: true };
        }
        if (!res.ok || !res.body) {
          patchLast((msg) => ({
            ...msg,
            content: "_Something went wrong. Please try again._",
            streaming: false,
          }));
          setBusy(false);
          return {};
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        // Parse SSE frames separated by a blank line.
        // Each frame: "event: <name>\ndata: <json>\n\n"
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let sep;
          while ((sep = buffer.indexOf("\n\n")) !== -1) {
            const frame = buffer.slice(0, sep);
            buffer = buffer.slice(sep + 2);

            let event = "message";
            let data = "";
            for (const line of frame.split("\n")) {
              if (line.startsWith("event:")) event = line.slice(6).trim();
              else if (line.startsWith("data:")) data += line.slice(5).trim();
            }
            if (!data) continue;

            if (event === "sources") {
              const sources = JSON.parse(data) as Source[];
              patchLast((msg) => ({ ...msg, sources }));
            } else if (event === "token") {
              const token = JSON.parse(data) as string;
              patchLast((msg) => ({ ...msg, content: msg.content + token }));
            } else if (event === "done") {
              patchLast((msg) => ({ ...msg, streaming: false }));
            }
          }
        }
        patchLast((msg) => ({ ...msg, streaming: false }));
      } catch {
        patchLast((msg) => ({
          ...msg,
          content: "_Connection error. Please try again._",
          streaming: false,
        }));
      } finally {
        setBusy(false);
      }
      return {};
    },
    [busy]
  );

  return { messages, busy, send };
}
