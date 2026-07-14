"use client";

import { useEffect, useState } from "react";
import { InlineCitation, ResourceCard } from "@/components/resource-views";
import { RESOURCE_TYPES, type ResourceType } from "@/lib/resource-types";
import type { Source } from "@/lib/types";

const TYPE_ORDER: ResourceType[] = ["article", "report", "contact", "ama", "deal"];

export default function PreviewPage() {
  const [samples, setSamples] = useState<Record<string, Source[]>>({});
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch("/api/samples")
      .then((r) => r.json())
      .then((s) => setSamples(s))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  return (
    <div className="mx-auto min-h-dvh w-full max-w-4xl px-6 py-12">
      <header className="mb-10 border-b pb-6">
        <div className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
          Design preview
        </div>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">
          Resource components
        </h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Both views for each of the five resource types, rendered with real parsed
          ReachIn data. Inline citation = icon + name (truncated). Card = key fields
          for that type; missing fields are omitted.
        </p>
      </header>

      {!loaded && (
        <p className="text-sm text-muted-foreground">Loading samples…</p>
      )}

      {loaded &&
        TYPE_ORDER.map((type) => {
          const def = RESOURCE_TYPES[type];
          // Show more contacts so the three sub-types (advisor / coach / media) are visible.
          const items = (samples[type] ?? []).slice(0, type === "contact" ? 4 : 2);
          return (
            <section key={type} className="mb-14">
              <div className="mb-4 flex items-center gap-2">
                <def.icon
                  className="size-5"
                  style={{ color: def.color }}
                  aria-hidden
                />
                <h2 className="text-lg font-medium">{def.label}</h2>
                <span className="text-xs text-muted-foreground">
                  {def.cardFields.map((f) => f.label).join(" · ")}
                </span>
              </div>

              {items.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No sample available.
                </p>
              ) : (
                <div className="grid gap-8 sm:grid-cols-2">
                  {/* Inline variant */}
                  <div>
                    <div className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60">
                      Inline citation
                    </div>
                    <div className="flex flex-col items-start gap-2">
                      {items.map((s, i) => (
                        <InlineCitation key={i} source={s} />
                      ))}
                      {/* Truncation demo with a deliberately long name */}
                      <InlineCitation
                        source={{
                          ...items[0],
                          title:
                            "A deliberately very long resource title to show how inline truncation behaves in a narrow column",
                        }}
                      />
                    </div>
                  </div>

                  {/* Card variant */}
                  <div>
                    <div className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60">
                      Card
                    </div>
                    <div className="flex flex-col gap-3">
                      {items.map((s, i) => (
                        <ResourceCard key={i} source={s} />
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </section>
          );
        })}

      {/* ── Mosaic lockup: all card types mixed together, masonry-packed ── */}
      {loaded && (
        <section className="mt-6 border-t pt-10">
          <div className="mb-1 text-xs font-medium uppercase tracking-widest text-muted-foreground">
            Lockup
          </div>
          <h2 className="mb-1 text-lg font-medium">Mixed resource grid</h2>
          <p className="mb-6 max-w-xl text-sm text-muted-foreground">
            All card types together, packed masonry-style — how a resource list
            reads as one set when an answer cites across types.
          </p>
          <div className="[column-fill:balance] gap-4 [column-width:16rem] sm:[column-count:2] lg:[column-count:3]">
            {interleave(TYPE_ORDER.flatMap((t) => samples[t] ?? [])).map((s, i) => (
              <div key={i} className="mb-4 break-inside-avoid">
                <ResourceCard source={s} />
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

/**
 * Round-robin across types so the mosaic mixes card kinds instead of clustering
 * all articles, then all reports, etc. Groups by type, then takes one from each
 * in turn.
 */
function interleave(items: Source[]): Source[] {
  const byType = new Map<string, Source[]>();
  for (const s of items) {
    const arr = byType.get(s.type) ?? [];
    arr.push(s);
    byType.set(s.type, arr);
  }
  const queues = [...byType.values()];
  const out: Source[] = [];
  let added = true;
  while (added) {
    added = false;
    for (const q of queues) {
      const next = q.shift();
      if (next) {
        out.push(next);
        added = true;
      }
    }
  }
  return out;
}
