import { FileText, BarChart3, User, Mic, Tag, type LucideIcon } from "lucide-react";

/**
 * ReachBot's 5-type resource design system. The backend classifies each retrieved
 * hit into one of these types (see backend/resource_types.py) and sends the type
 * string + a `fields` object parsed from the chunk (backend/resource_fields.py);
 * here we map it to a functional icon + accent color and the card's field layout.
 *
 * Neutral branding: colors distinguish source *kinds* at a glance (a functional
 * affordance), not brand styling. Everything the cards render is driven by this
 * registry — add/re-style types here, not in per-type CSS.
 */
export type ResourceType = "article" | "report" | "contact" | "ama" | "deal";

/** A field row on a card. `key` matches the backend `fields` object. */
export interface CardField {
  key: string;
  label: string;
  /** render as the card's lead/body paragraph rather than a labeled row */
  emphasis?: boolean;
  /** render as small pill(s), splitting on commas (e.g. tags) */
  pills?: boolean;
  /** render as a badge in the card's top-right corner instead of a labeled row */
  badge?: boolean;
  /** render as one inline muted line ("By Name") rather than a label/value grid row */
  inline?: boolean;
}

export interface ResourceTypeDef {
  label: string;
  icon: LucideIcon;
  /** accent color (hex) used sparingly on the icon + a thin card marker */
  color: string;
  /** ordered fields the card shows; missing ones are omitted (graceful) */
  cardFields: CardField[];
}

export const RESOURCE_TYPES: Record<ResourceType, ResourceTypeDef> = {
  article: {
    label: "Article",
    icon: FileText,
    color: "#7EB6FF",
    cardFields: [
      { key: "sector", label: "Sector", badge: true },
      { key: "summary", label: "Summary", emphasis: true },
      { key: "publisher", label: "By", inline: true },
    ],
  },
  report: {
    label: "Report",
    icon: BarChart3,
    color: "#B9A5FF",
    cardFields: [
      { key: "sector", label: "Sector", badge: true },
      { key: "summary", label: "Summary", emphasis: true },
      { key: "publisher", label: "By", inline: true },
    ],
  },
  contact: {
    label: "Contact",
    icon: User,
    color: "#4FD8A8",
    cardFields: [
      { key: "specialty", label: "Specialty", emphasis: true },
      { key: "name", label: "Name" },
      { key: "role", label: "Role" },
      { key: "contact_info", label: "Contact" },
    ],
  },
  ama: {
    label: "AMA",
    icon: Mic,
    color: "#FFC94D",
    cardFields: [
      // `by` is synthesized in ResourceCard from speaker + org ("Name, Org").
      { key: "by", label: "By", inline: true },
    ],
  },
  deal: {
    label: "Deal",
    icon: Tag,
    color: "#FF8FC0",
    cardFields: [
      { key: "category", label: "Type", badge: true },
      { key: "offer", label: "Offer", emphasis: true },
    ],
  },
};

export function resourceDef(type: string): ResourceTypeDef {
  return RESOURCE_TYPES[(type as ResourceType)] ?? RESOURCE_TYPES.article;
}
