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
      { key: "summary", label: "Summary", emphasis: true },
      { key: "publisher", label: "Publisher" },
      { key: "sector", label: "Sector" },
    ],
  },
  report: {
    label: "Report",
    icon: BarChart3,
    color: "#B9A5FF",
    cardFields: [
      { key: "summary", label: "Summary", emphasis: true },
      { key: "publisher", label: "Publisher" },
      { key: "sector", label: "Sector" },
      { key: "tags", label: "Tags", pills: true },
    ],
  },
  contact: {
    label: "Contact",
    icon: User,
    color: "#4FD8A8",
    cardFields: [
      { key: "specialty", label: "Specialty", emphasis: true },
      { key: "role", label: "Role" },
      { key: "contact_info", label: "Contact" },
      { key: "reach_contact", label: "Reach point" },
    ],
  },
  ama: {
    label: "AMA",
    icon: Mic,
    color: "#FFC94D",
    cardFields: [
      { key: "speaker", label: "Speaker" },
      { key: "org", label: "Org" },
      { key: "date", label: "Date" },
      { key: "tags", label: "Tags", pills: true },
    ],
  },
  deal: {
    label: "Deal",
    icon: Tag,
    color: "#FF8FC0",
    cardFields: [
      { key: "offer", label: "Offer", emphasis: true },
      { key: "category", label: "Type" },
      { key: "contact", label: "Contact" },
      { key: "email", label: "Email" },
      { key: "reach_point", label: "Reach point" },
    ],
  },
};

export function resourceDef(type: string): ResourceTypeDef {
  return RESOURCE_TYPES[(type as ResourceType)] ?? RESOURCE_TYPES.article;
}
