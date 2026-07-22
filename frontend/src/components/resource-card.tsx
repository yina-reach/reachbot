"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { resourceDef } from "@/lib/resource-types";
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
}: {
  sources: Source[];
  streaming?: boolean;
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
  if (n === 0) return null;

  const label = streaming
    ? `Found ${n} relevant ${n === 1 ? "resource" : "resources"} to review…`
    : `Reviewed ${n} ${n === 1 ? "resource" : "resources"}`;

  return (
    <div className="mb-3">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 py-1 text-left text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
        aria-expanded={open}
      >
        {streaming && (
          <span className="flex gap-0.5" aria-hidden>
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="size-1 animate-bounce rounded-full bg-muted-foreground/60"
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </span>
        )}
        <span>{label}</span>
        <ChevronRight
          className={`size-3.5 shrink-0 transition-transform ${open ? "rotate-90" : ""}`}
          aria-hidden
        />
      </button>

      {open && (
        <div className="mt-1 flex flex-col divide-y divide-border/60 overflow-hidden rounded-lg border border-border bg-card dark:bg-black/30">
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
                <Icon className="size-3.5 shrink-0 text-resource-accent" aria-hidden />
                <span className="truncate">{s.title}</span>
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}
