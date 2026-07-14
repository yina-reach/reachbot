export interface Source {
  title: string;
  url: string;
  type: string; // ResourceType, but backend-provided so keep it loose
  /** structured fields parsed from the chunk (see backend/resource_fields.py) */
  fields?: Record<string, string>;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  /** true while tokens are still streaming into this assistant message */
  streaming?: boolean;
}
