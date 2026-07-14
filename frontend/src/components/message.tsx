import { Markdown } from "@/components/markdown";
import { RetrievedDisclosure } from "@/components/resource-card";
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

export function Message({ message }: { message: ChatMessage }) {
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

  return (
    <div className="py-1">
      {/* Raw-retrieval disclosure sits ABOVE the answer, collapsed by default. */}
      {hasSources && (
        <RetrievedDisclosure
          sources={message.sources!}
          streaming={message.streaming}
        />
      )}

      {/* The answer itself — includes the model's curated "Resources" list. */}
      {answerEmpty ? (
        // Only show bare dots if sources haven't arrived yet (else the disclosure
        // already provides the thinking state).
        message.streaming && !hasSources ? <TypingDots /> : null
      ) : (
        <Markdown>{message.content}</Markdown>
      )}
    </div>
  );
}
