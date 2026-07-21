import { useMemo, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { InlineCitation } from "@/components/resource-views";
import { buildSourceLookup, findSource } from "@/lib/citations";
import type { Source } from "@/lib/types";

/** Flatten a link's rendered children to plain text (react-markdown may pass a
 * string OR an array of nodes, e.g. when the text contains entities). */
function textOf(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  return "";
}

/**
 * Render the assistant's markdown answer. Replaces the regex md_to_html from the
 * Streamlit app — safe (no dangerouslySetInnerHTML), links open in a new tab.
 *
 * When `sources` are provided, links pointing at a retrieved source render as the
 * designed InlineCitation chip (icon + byline) instead of a plain underlined link.
 */
export function Markdown({
  children,
  sources,
}: {
  children: string;
  sources?: Source[];
}) {
  const lookup = useMemo(() => buildSourceLookup(sources), [sources]);
  return (
    <div className="prose-chat">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            if (!href) return <a>{children}</a>;
            const label = textOf(children);
            // Every link in an answer is a citation — ALWAYS render the designed
            // chip, never a bare underlined link. Links that don't match any
            // retrieved source (external URLs, model-mangled ones) get a generic
            // chip labeled with the link text: contact for mailto, article else.
            const src: Source = findSource(lookup, href, label) ?? {
              title: label || href,
              url: href,
              type: href.startsWith("mailto:") ? "contact" : "article",
            };
            return <InlineCitation source={src} className="rb-cite" />;
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
