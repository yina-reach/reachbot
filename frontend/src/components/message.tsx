import { Markdown } from "@/components/markdown";
import { RetrievedDisclosure } from "@/components/resource-card";
import { InlineCitation, ResourceCard } from "@/components/resource-views";
import {
  buildSourceLookup,
  findSource,
  repairCitations,
  splitAnswer,
} from "@/lib/citations";
import type { ChatMessage } from "@/lib/types";

function TypingDots() {
  return (
    <div className="flex items-center gap-1 py-1" aria-label="ReachBot is typing">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}

export function Message({
  message,
  allSources,
}: {
  message: ChatMessage;
  /** sources from every turn so far — citations may refer back to earlier turns */
  allSources?: ChatMessage["sources"];
}) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-secondary px-4 py-2.5 text-base text-secondary-foreground">
          {message.content}
        </div>
      </div>
    );
  }

  const hasSources = message.sources && message.sources.length > 0;
  const answerEmpty = !message.content;

  // Normalize citation markup (unwrap parens, re-link naked [Title] brackets),
  // then split the answer at its "Resources" list: prose renders as markdown
  // (with inline-citation chips); the list renders as the designed resource cards.
  // Own sources first so the current turn wins duplicate URLs/titles.
  const knownSources = [...(message.sources ?? []), ...(allSources ?? [])];
  const lookup = buildSourceLookup(knownSources);
  const repaired = repairCitations(message.content, lookup, message.streaming);
  const { prose, items, footer } = splitAnswer(repaired, message.streaming);

  return (
    <div className="py-1">
      {/* Raw-retrieval disclosure sits ABOVE the answer, collapsed by default. */}
      {hasSources && (
        <RetrievedDisclosure
          sources={message.sources!}
          streaming={message.streaming}
        />
      )}

      {/* The answer itself. */}
      {answerEmpty ? (
        // Only show bare dots if sources haven't arrived yet (else the disclosure
        // already provides the thinking state).
        message.streaming && !hasSources ? <TypingDots /> : null
      ) : (
        <>
          {prose && <Markdown sources={knownSources}>{prose}</Markdown>}

          {items.length > 0 && (
            <div className="mt-4">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Resources
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {items.map((it, i) => {
                  const src = findSource(lookup, it.url, it.title);
                  return src ? (
                    <ResourceCard key={`${it.url}-${i}`} source={src} />
                  ) : (
                    // Unknown to retrieval — render the citation chip rather
                    // than a bare link, without guessing a full card's type.
                    <div key={`${it.url}-${i}`} className="self-start">
                      <InlineCitation
                        source={{ title: it.title, url: it.url, type: "article" }}
                      />
                    </div>
                  );
                })}
              </div>
              {footer && (
                <div className="mt-2">
                  <Markdown sources={knownSources}>{footer}</Markdown>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
