"use client";

import { useEffect, useRef, useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { ArrowUp } from "lucide-react";

export function ChatInput({
  onSend,
  disabled,
  minRows = 1,
  placeholder: placeholderProp,
}: {
  onSend: (q: string) => void;
  disabled?: boolean;
  /** Minimum visible rows before autosize grows (desktop only; mobile is always 1). */
  minRows?: number;
  /** Override the placeholder. Omit on the empty state (uses the responsive
   *  look-up/synthesize/browse text); pass "Ask ReachBot" in the conversation. */
  placeholder?: string;
}) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  // Mobile stays single-line regardless of minRows; desktop honors it (Tailwind sm = 640px).
  const [effectiveRows, setEffectiveRows] = useState(1);
  // Desktop shows the fuller placeholder; the narrow mobile composer gets a short one.
  const [isDesktop, setIsDesktop] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 640px)");
    const apply = () => {
      setEffectiveRows(mq.matches ? minRows : 1);
      setIsDesktop(mq.matches);
    };
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [minRows]);

  const placeholder =
    placeholderProp ??
    (isDesktop
      ? "Look up, synthesize, or browse ReachIn's library of curated and exclusive resources"
      : "Look up, synthesize, or browse ReachIn");

  // Grow to fit content, but never shrink below the row floor.
  function autosize(el: HTMLTextAreaElement) {
    el.style.height = "auto";
    const floor = effectiveRows * LINE_HEIGHT + VERTICAL_PAD;
    el.style.height = `${Math.min(Math.max(el.scrollHeight, floor), 200)}px`;
  }

  // Apply the initial floor on mount / when the row floor changes.
  useEffect(() => {
    if (ref.current) autosize(ref.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveRows]);

  function submit() {
    const q = value.trim();
    if (!q || disabled) return;
    onSend(q);
    setValue("");
    if (ref.current) {
      ref.current.value = "";
      autosize(ref.current);
    }
  }

  return (
    <div className="relative flex items-end gap-2 rounded-2xl border bg-card p-2 shadow-sm focus-within:ring-1 focus-within:ring-ring">
      <Textarea
        ref={ref}
        value={value}
        rows={effectiveRows}
        onChange={(e) => {
          setValue(e.target.value);
          autosize(e.target);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        placeholder={placeholder}
        className="max-h-[200px] min-h-0 resize-none border-0 bg-transparent px-2 py-1.5 text-base leading-6 shadow-none focus-visible:ring-0 dark:bg-transparent"
      />
      <Button
        size="icon"
        // Brand blue #0055FF in both themes; overrides the theme primary.
        className="size-8 shrink-0 rounded-full bg-[#0055FF] text-white hover:bg-[#0048d6] disabled:bg-[#0055FF]/40 disabled:text-white/70"
        onClick={submit}
        disabled={disabled || !value.trim()}
        aria-label="Send"
      >
        <ArrowUp className="size-4" />
      </Button>
    </div>
  );
}

// Matches the textarea's `leading-6` (24px) + `py-1.5` (6px top+bottom).
const LINE_HEIGHT = 24;
const VERTICAL_PAD = 12;
