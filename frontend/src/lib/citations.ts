import type { Source } from "@/lib/types";

/**
 * Match markdown links in the model's answer back to the retrieved sources, so
 * the UI can swap them for the designed InlineCitation / ResourceCard components
 * (see components/resource-views.tsx and the /preview page).
 *
 * Matching is by Notion page id when present (robust to www./notion.so vs
 * app.notion.com URL variants), else by normalized URL, with an exact-title
 * fallback for the case where the model links a page's external URL instead of
 * its Notion source_url.
 */

/** Normalize a URL to a lookup key: last 32-hex Notion id if present, else the
 * scheme/www-stripped URL. Dashes are removed first so dashed UUIDs match too. */
function urlKey(url: string): string {
  const m = url.replace(/-/g, "").match(/[0-9a-f]{32}(?=[/?#]|$)/gi);
  if (m && m.length > 0) return m[m.length - 1].toLowerCase();
  return url
    .replace(/^https?:\/\/(www\.)?/, "")
    .replace(/\/+$/, "")
    .toLowerCase();
}

export interface SourceLookup {
  byUrl: Map<string, Source>;
  byTitle: Map<string, Source>;
}

export function buildSourceLookup(sources?: Source[]): SourceLookup {
  const byUrl = new Map<string, Source>();
  const byTitle = new Map<string, Source>();
  for (const s of sources ?? []) {
    const u = urlKey(s.url);
    if (!byUrl.has(u)) byUrl.set(u, s);
    const t = s.title.trim().toLowerCase();
    if (t && !byTitle.has(t)) byTitle.set(t, s);
  }
  return { byUrl, byTitle };
}

export function findSource(
  lookup: SourceLookup,
  url: string,
  linkText?: string
): Source | undefined {
  return (
    lookup.byUrl.get(urlKey(url)) ??
    (linkText ? lookup.byTitle.get(linkText.trim().toLowerCase()) : undefined)
  );
}

// ── Repairing citation markup the model got slightly wrong ─────────────────────

/**
 * Normalize citation markup in the raw answer BEFORE markdown rendering:
 *  1. "([Title](url))" → "[Title](url)" — chips carry their own visual boundary,
 *     surrounding parens read as clutter.
 *  2. Naked "[Title]" with no (url) — a known flash-model failure mode — gets
 *     re-linked when the bracket text matches a retrieved source's title, so it
 *     renders as a citation chip instead of literal plain text. If it matches
 *     nothing we can link to, the brackets/quotes are stripped so the title
 *     reads as plain prose instead of markdown junk.
 * While `streaming`, a naked bracket at the very end of the text is left alone:
 * its "(url)" part may simply not have arrived yet.
 */
export function repairCitations(
  content: string,
  lookup: SourceLookup,
  streaming?: boolean
): string {
  let out = content.replace(/\(\s*(\[[^\]]+\]\([^()\s]+\))\s*\)/g, "$1");
  out = out.replace(/\[([^\]]+)\](?!\()/g, (match, text: string, offset: number) => {
    if (streaming && offset + match.length >= out.length) return match;
    const clean = text.replace(/^["'“”\s]+|["'“”\s]+$/g, "");
    const src = lookup.byTitle.get(clean.toLowerCase());
    if (src) return `[${text}](${src.url})`;
    // Unlinkable citation-shaped bracket (title-length text): render the bare
    // title as prose. Short brackets like [1] or [sic] are left untouched.
    return clean.length >= 4 && !/^\d+$/.test(clean) ? clean : match;
  });
  return out;
}

// ── Splitting the answer around its trailing "Resources" list ──────────────────

export interface ResourceItem {
  title: string;
  url: string;
  /** the model's "— one sentence" description, used only for unmatched fallbacks */
  desc?: string;
}

export interface SplitAnswer {
  /** everything above the Resources heading — rendered as markdown prose */
  prose: string;
  /** parsed [Title](URL) list entries — rendered as ResourceCards */
  items: ResourceItem[];
  /** non-link lines after the heading (e.g. "want the full list?") */
  footer: string;
}

// "**Resources**", "### Resources", "2. **Resources:**", "Resources:" …
const HEADING_RE =
  /^\s*(?:#{1,4}\s*)?(?:\d+[.)]\s*)?\*{0,2}Resources:?\*{0,2}\s*$/i;
const LINK_RE = /\[([^\]]+)\]\(([^)\s]+)\)/;

/**
 * Split the assistant answer at its LAST "Resources" heading. While `streaming`,
 * non-link lines in the resources block are suppressed so half-received markdown
 * links don't flash as raw text.
 */
export function splitAnswer(content: string, streaming?: boolean): SplitAnswer {
  const lines = content.split("\n");
  let at = -1;
  for (let i = lines.length - 1; i >= 0; i--) {
    if (HEADING_RE.test(lines[i])) {
      at = i;
      break;
    }
  }
  if (at === -1) return { prose: content, items: [], footer: "" };

  const prose = lines.slice(0, at).join("\n").trimEnd();
  const items: ResourceItem[] = [];
  const footerLines: string[] = [];
  const seen = new Set<string>();

  for (const line of lines.slice(at + 1)) {
    if (!line.trim()) continue;
    const m = line.match(LINK_RE);
    if (m) {
      const url = m[2];
      if (seen.has(url)) continue;
      seen.add(url);
      const after = line.slice(line.indexOf(m[0]) + m[0].length);
      const desc = after.replace(/^[\s:—–·-]+/, "").trim();
      items.push({ title: m[1], url, desc: desc || undefined });
    } else if (!streaming) {
      footerLines.push(line.replace(/^\s*(?:[-*•]|\d+[.)])\s*/, ""));
    }
  }
  return { prose, items, footer: footerLines.join("\n") };
}
