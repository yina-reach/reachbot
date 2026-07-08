import { resourceDef } from "@/lib/resource-types";
import type { Source } from "@/lib/types";

/**
 * INLINE CITATION — icon + resource name, truncated. Used where a resource is
 * referenced within flowing text or a compact list (the retrieval disclosure,
 * inline mentions). Deliberately minimal: type icon + name + link, one line.
 */
export function InlineCitation({ source }: { source: Source }) {
  const def = resourceDef(source.type);
  const Icon = def.icon;
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      title={source.title}
      className="group inline-flex max-w-full items-center gap-1.5 rounded-md border border-border/60 bg-card/40 px-2 py-0.5 align-middle text-[13px] text-foreground/90 transition-colors hover:border-border hover:bg-accent"
    >
      <Icon className="size-3.5 shrink-0" style={{ color: def.color }} aria-hidden />
      <span className="truncate group-hover:underline">{source.title}</span>
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
  const fields = source.fields ?? {};

  const rows = def.cardFields.filter((f) => fields[f.key]);
  const lead = rows.find((f) => f.emphasis && fields[f.key]);
  const detail = rows.filter((f) => f !== lead);

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block rounded-xl border border-border bg-card/50 p-4 transition-colors hover:border-foreground/20 hover:bg-accent/40"
      style={{ borderLeft: `2px solid ${def.color}` }}
    >
      {/* Header: type icon + label + title */}
      <div className="mb-2 flex items-center gap-2">
        <Icon className="size-4 shrink-0" style={{ color: def.color }} aria-hidden />
        <span
          className="text-[10px] font-semibold uppercase tracking-wider"
          style={{ color: def.color }}
        >
          {def.label}
        </span>
      </div>
      <div className="mb-2 font-medium leading-snug text-foreground group-hover:underline">
        {source.title}
      </div>

      {/* Emphasis/lead field as body text */}
      {lead && (
        <p className="mb-3 line-clamp-3 text-sm text-muted-foreground">
          {fields[lead.key]}
        </p>
      )}

      {/* Remaining fields as label/value rows (or pills for tags) */}
      {detail.length > 0 && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[13px]">
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
