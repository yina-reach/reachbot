"use client";

import { useEffect, useState } from "react";
import { resourceDef } from "@/lib/resource-types";

const NOTION_DB_URL =
  "https://www.notion.so/reachcapital/ReachIn-1499d627cdb04c81a3e48c1f31f83199?source=copy_link";

// Example questions spanning three ways to use ReachBot: a precise lookup, a
// synthesized interpretation across sources, and finding a contact.
// Full sentences teach phrasing + set depth; the label names the mode.
const PROMPTS: { label: string; text: string }[] = [
  {
    label: "Look up",
    text: "What partner discounts are available for HR or payroll tools?",
  },
  {
    label: "Synthesize",
    text: "Across the AMAs, what do speakers say about pricing pilots vs. paid contracts?",
  },
  {
    label: "Find a contact",
    text: "Who in the Reach network can advise on outbound sales?",
  },
];

interface Scope {
  total: number;
  by_type: Record<string, number>;
}

// Order + label the scope chips. Only types with a nonzero count are shown.
const SCOPE_ORDER: { type: string; singular: string; plural: string }[] = [
  { type: "ama", singular: "AMA", plural: "AMAs" },
  { type: "report", singular: "report", plural: "reports" },
  { type: "article", singular: "article", plural: "articles" },
  { type: "contact", singular: "contact", plural: "contacts" },
  { type: "deal", singular: "deal", plural: "deals" },
];

export function Welcome() {
  return (
    <div className="flex flex-col items-center px-4 text-center">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/reachbot-logo.svg"
        alt="ReachBot"
        width={56}
        height={56}
        className="mb-5 size-14 rounded-2xl bg-[#1E2015]"
      />
      <h1
        className="text-4xl font-medium tracking-tight sm:whitespace-nowrap sm:text-5xl"
        style={{ fontFamily: '"p22-mackinac-pro", ui-serif, Georgia, serif' }}
      >
        {/* Mobile wraps "you find?" together to avoid a "find?" orphan; sm+ is one line. */}
        What can I help{" "}
        <span className="whitespace-nowrap">you find?</span>
      </h1>
    </div>
  );
}

/**
 * The example-prompt suggestions, rendered UNDER the input in the centered empty
 * state. Kept separate from <Welcome> so the page can place them below the dock.
 */
export function PromptSuggestions({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="mt-10 w-full">
      <p
        className="mb-2 px-1 text-base text-muted-foreground"
        style={{ fontFamily: '"p22-mackinac-pro", ui-serif, Georgia, serif' }}
      >
        Some things you can ask me:
      </p>
      {/* Divided list rather than cards: a hairline between each suggestion, no
          per-item box. Lighter on the empty state than a stack of bordered cards. */}
      <div className="flex w-full flex-col divide-y divide-border/60 border-y border-border/60">
        {PROMPTS.map((p) => (
        <button
          key={p.text}
          onClick={() => onPick(p.text)}
          className="group flex flex-col gap-1 px-1 py-3 text-left"
        >
          {/* On hover the content slides right so its text left-aligns with the
              composer's (composer text sits at p-2 + px-2 = 16px; list is at
              px-1 = 4px, so shift 12px). */}
          <span className="flex flex-col gap-1 transition-transform duration-200 ease-out group-hover:translate-x-3">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/50 group-hover:text-muted-foreground">
              {p.label}
            </span>
            <span className="text-base text-muted-foreground group-hover:text-foreground">
              {p.text}
            </span>
          </span>
        </button>
        ))}
      </div>
    </div>
  );
}

/**
 * Scope breakdown chips + subtle Notion link. Placed at the very bottom of the
 * empty state — builds trust ("curated, not open-ended") before the first query.
 */
export function ScopeFooter() {
  const [scope, setScope] = useState<Scope | null>(null);

  useEffect(() => {
    fetch("/api/scope")
      .then((r) => r.json())
      .then((s) => setScope(s))
      .catch(() => {});
  }, []);

  const chips =
    scope && scope.total > 0
      ? SCOPE_ORDER.map(({ type, singular, plural }) => {
          const n = scope.by_type[type] ?? 0;
          if (!n) return null;
          const def = resourceDef(type);
          const Icon = def.icon;
          return (
            <span
              key={type}
              className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-card/40 px-2.5 py-1 text-xs text-muted-foreground"
            >
              <Icon className="size-3 text-resource-accent" aria-hidden />
              {n} {n === 1 ? singular : plural}
            </span>
          );
        }).filter(Boolean)
      : [];

  return (
    <div className="flex flex-col items-center gap-3 px-4 text-center">
      {scope && scope.total > 0 && (
        <>
          <div className="text-xs font-medium text-muted-foreground/80">
            {scope.total} curated sources
          </div>
          {/* Type breakdown is desktop-only; mobile keeps just the total + link. */}
          <div className="hidden max-w-xl flex-wrap justify-center gap-1.5 sm:flex">
            {chips}
          </div>
        </>
      )}
      <a
        href={NOTION_DB_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs text-muted-foreground/60 underline-offset-2 transition-colors hover:text-muted-foreground hover:underline"
      >
        Browse the full ReachIn library in Notion →
      </a>
    </div>
  );
}
