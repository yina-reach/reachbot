export interface Source {
  title: string;
  url: string;
  type: string; // ResourceType, but backend-provided so keep it loose
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  /** true while tokens are still streaming into this assistant message */
  streaming?: boolean;
}
