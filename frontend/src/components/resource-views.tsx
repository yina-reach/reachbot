"use client";

import { useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { ArrowUpRight } from "lucide-react";
import { resourceDef } from "@/lib/resource-types";
import { cn } from "@/lib/utils";
import type { Source } from "@/lib/types";

/** Hover-marquee scroll speed for inline citations, px per second. Constant
 * across chips so long and short labels read at the same pace. */
const CITE_SCROLL_PX_PER_S = 35;

/** Extra scroll past the pure overflow so the label's tail clears the arrow
 * overlay on the right (arrow size-3.5 + pl-3 ≈ this many px are obscured). */
const CITE_ARROW_OVERLAP_PX = 26;

/**
 * The author/byline for a source, used as the inline-citation label:
 *   article/report → publisher   ("First Round Review")
 *   ama            → speaker + org ("Anna Siebelink, Balanced Image")
 *   contact        → the person's name (they ARE the author)
 * Falls back to the resource title when no byline exists (e.g. deals).
 */
function bylineOf(source: Source): string {
  const f = source.fields ?? {};
  switch (source.type) {
    case "article":
    case "report":
      return f.publisher || source.title;
    case "ama":
      return [f.speaker, f.org].filter(Boolean).join(", ") || source.title;
    case "contact":
      return f.name || source.title; // media rows carry a Name; others = the title
    default:
      return source.title; // deals etc. have no byline
  }
}

/**
 * INLINE CITATION — icon + author/byline, truncated. Used where a resource is
 * referenced within flowing text or a compact list. On hover, a diagonal ↗
 * appears at the right to signal the external link.
 */
export function InlineCitation({
  source,
  className,
}: {
  source: Source;
  className?: string;
}) {
  const def = resourceDef(source.type);
  const Icon = def.icon;
  const label = bylineOf(source);

  // Measure how far the label overflows its 20ch window so the hover scroll
  // runs at a CONSTANT speed (duration ∝ distance) instead of a fixed duration
  // that makes long labels race and short ones crawl. Re-measured once webfonts
  // finish loading, since that shifts text metrics.
  const labelRef = useRef<HTMLSpanElement>(null);
  const [scrollDist, setScrollDist] = useState(0);
  useLayoutEffect(() => {
    const measure = () => {
      const el = labelRef.current;
      if (!el) return;
      const overflow = el.scrollWidth - el.clientWidth;
      // Only scroll if the text actually overflows; then add the arrow overlap
      // so the tail ends up left of the arrow rather than hidden under it.
      setScrollDist(overflow > 0 ? overflow + CITE_ARROW_OVERLAP_PX : 0);
    };
    measure();
    document.fonts?.ready.then(measure);
  }, [label]);

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      title={source.title}
      className={cn(
        "group relative inline-flex max-w-full items-center gap-1.5 rounded-md border border-border/60 bg-card/40 py-0.5 pl-1.5 pr-2 align-middle text-[13px] text-foreground/90 transition-colors hover:border-border hover:bg-[var(--gray-100)] dark:hover:bg-accent",
        className
      )}
    >
      <Icon className="size-3.5 shrink-0 text-resource-accent" aria-hidden />
      {/* Label capped at 20ch. On a sustained hover (600ms delay) the inner span
          slides left at a constant px/s to reveal the full text, then snaps back
          quickly on mouse-out. Short labels have scrollDist 0 and never move. */}
      <span
        ref={labelRef}
        className="max-w-[20ch] truncate group-hover:[text-overflow:clip]"
      >
        <span
          className="inline-block transition-transform duration-300 ease-linear group-hover:[transition-delay:600ms] group-hover:[transition-duration:var(--cite-dur)] group-hover:[transform:translateX(var(--cite-scroll))]"
          style={
            {
              "--cite-scroll": `${-scrollDist}px`,
              "--cite-dur": `${scrollDist / CITE_SCROLL_PX_PER_S}s`,
            } as CSSProperties
          }
        >
          {label}
        </span>
      </span>
      {/* Diagonal external-link arrow — absolutely positioned so it adds NO
          width (chip sizes to icon + text). On hover it fades in over the
          text's right edge, with a bg matching the hovered chip so the text it
          overlaps reads as cropped beneath it. */}
      <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center rounded-r-md bg-gradient-to-l from-[var(--gray-100)] from-60% to-transparent pl-3 pr-2 opacity-0 transition-opacity duration-150 group-hover:opacity-100 dark:from-accent">
        <ArrowUpRight className="size-3.5 text-foreground/70" aria-hidden />
      </span>
    </a>
  );
}

/**
 * RESOURCE CARD — icon + title + the type's key fields (from resource-types.ts).
 * Fields missing from the parsed data are simply omitted. An accent hairline on
 * the left encodes the resource type at a glance.
 */
export function ResourceCard({ source }: { source: Source }) {
  const def = resourceDef(source.type);
  const Icon = def.icon;
  const fields = { ...(source.fields ?? {}) };

  // AMA cards show one "By" line = speaker + org ("Name, Org").
  if (source.type === "ama" && (fields.speaker || fields.org)) {
    fields.by = [fields.speaker, fields.org].filter(Boolean).join(", ");
  }

  const present = def.cardFields.filter((f) => fields[f.key]);
  const badge = present.find((f) => f.badge);
  const lead = present.find((f) => f.emphasis);
  const inlineLines = present.filter((f) => f.inline && !f.badge && !f.emphasis);
  const detail = present.filter((f) => !f.badge && !f.emphasis && !f.inline);

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block rounded-xl border border-border bg-card/50 p-4 transition-colors hover:border-foreground/20 hover:bg-accent/40"
    >
      {/* Header: type icon + label, with the badge field pinned top-right */}
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon className="size-4 shrink-0 text-resource-accent" aria-hidden />
          <span className="text-[10px] font-semibold uppercase tracking-wider text-resource-accent">
            {def.label}
          </span>
        </div>
        {badge && (
          <span className="shrink-0 rounded-full border border-border/70 px-2 py-0.5 text-[11px] text-muted-foreground">
            {fields[badge.key]}
          </span>
        )}
      </div>
      <div
        className="mb-2 text-[17px] font-medium leading-snug text-foreground"
        style={{ fontFamily: '"p22-mackinac-pro", ui-serif, Georgia, serif' }}
      >
        {source.title}
      </div>

      {/* Emphasis/lead field as body text */}
      {lead && (
        <p className="mb-3 line-clamp-3 text-sm text-muted-foreground">
          {fields[lead.key]}
        </p>
      )}

      {/* Byline — boxed on a muted background (no label). */}
      {inlineLines.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {inlineLines.map((f) => (
            <span
              key={f.key}
              // Light: gray-100, a soft fill on the white card (full gray-200
              // muted reads too heavy). Dark: the normal muted surface.
              className="inline-flex max-w-full items-center rounded-md bg-[var(--gray-100)] px-2 py-0.5 text-[13px] text-muted-foreground dark:bg-muted"
            >
              <span className="truncate">{fields[f.key]}</span>
            </span>
          ))}
        </div>
      )}

      {/* Remaining fields as label/value rows (or pills for tags) */}
      {detail.length > 0 && (
        <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[13px]">
          {detail.map((f) => (
            <div key={f.key} className="col-span-2 grid grid-cols-subgrid items-baseline">
              <dt className="text-muted-foreground/70">{f.label}</dt>
              <dd className="min-w-0 text-foreground/90">
                {f.pills ? (
                  <span className="flex flex-wrap gap-1">
                    {fields[f.key]
                      .split(",")
                      .map((t) => t.trim())
                      .filter(Boolean)
                      .map((t) => (
                        <span
                          key={t}
                          className="rounded-full border border-border/60 px-1.5 py-0.5 text-[11px] text-muted-foreground"
                        >
                          {t}
                        </span>
                      ))}
                  </span>
                ) : (
                  <span className="break-words">{fields[f.key]}</span>
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </a>
  );
}
