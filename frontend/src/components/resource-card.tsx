"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { resourceDef } from "@/lib/resource-types";
import { LogoAnimation } from "@/components/logo-animation";
import type { Source } from "@/lib/types";

/**
 * The "thinking" disclosure: shows how many resources retrieval surfaced for this
 * question, expandable to reveal the raw list. While the answer streams it reads as
 * a live thinking state; afterward it persists (default collapsed) above the answer.
 *
 * This is the RAW retrieval — distinct from the model's curated "Resources" list
 * inside the answer, which recommends the handful actually worth reading.
 */
export function RetrievedDisclosure({
  sources,
  streaming,
  searching,
}: {
  sources: Source[];
  streaming?: boolean;
  /** Actively retrieving (no answer text yet) — drives the animation. Distinct
   *  from `streaming`, which also covers the answer-generation phase. */
  searching?: boolean;
}) {
  // De-dupe by url — retrieval returns multiple chunks from the same page.
  const seen = new Set<string>();
  const unique = sources.filter((s) => {
    const key = s.url || s.title;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  const [open, setOpen] = useState(false);
  const n = unique.length;
  // Nothing to show only when we're done AND found nothing.
  if (n === 0 && !streaming) return null;

  // Before any sources arrive (streaming, n === 0) this is the "searching" state;
  // once they land it relabels to the count; when done it's the persisted summary.
  const label =
    n === 0
      ? "Searching resources…"
      : streaming
        ? `Found ${n} relevant ${n === 1 ? "resource" : "resources"} to review…`
        : `Reviewed ${n} ${n === 1 ? "resource" : "resources"}`;

  return (
    <div className="mb-3">
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={n === 0}
        className="flex items-center gap-1.5 py-1 text-left text-xs font-medium text-muted-foreground transition-colors hover:text-foreground disabled:cursor-default disabled:hover:text-muted-foreground"
        aria-expanded={open}
      >
        {searching && <LogoAnimation className="size-5 shrink-0 opacity-80" />}
        <span>{label}</span>
        {/* Chevron only once there's something to expand. */}
        {n > 0 && (
          <ChevronRight
            className={`size-3.5 shrink-0 transition-transform ${open ? "rotate-90" : ""}`}
            aria-hidden
          />
        )}
      </button>

      {open && (
        <div className="mt-1 flex flex-col divide-y divide-border/60 overflow-hidden rounded-lg border border-border bg-background">
          {unique.map((s, i) => {
            const def = resourceDef(s.type);
            const Icon = def.icon;
            return (
              <a
                key={`${s.url}-${i}`}
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-center gap-2 px-3 py-2 text-[13px] text-muted-foreground transition-colors hover:bg-[var(--gray-200)] hover:text-foreground dark:hover:bg-[var(--gray-950)]"
              >
                <Icon className="size-3.5 shrink-0" aria-hidden />
                <span className="truncate">{s.title}</span>
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}
