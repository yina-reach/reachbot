import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Render the assistant's markdown answer. Replaces the regex md_to_html from the
 * Streamlit app — safe (no dangerouslySetInnerHTML), links open in a new tab.
 */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose-chat">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
