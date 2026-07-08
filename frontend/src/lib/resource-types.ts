import { FileText, BarChart3, User, Mic, Tag, type LucideIcon } from "lucide-react";

/**
 * ReachBot's 5-type resource design system. The backend classifies each retrieved
 * hit into one of these types (see backend/resource_types.py) and sends the type
 * string; here we map it to a functional icon + accent color for the UI.
 *
 * Neutral branding: these colors are used ONLY to distinguish source *kinds* at a
 * glance (a functional affordance), not as brand styling.
 */
export type ResourceType = "article" | "report" | "contact" | "ama" | "deal";

export interface ResourceTypeDef {
  label: string;
  icon: LucideIcon;
  /** accent color (hex) used sparingly on the icon + a thin card marker */
  color: string;
}

export const RESOURCE_TYPES: Record<ResourceType, ResourceTypeDef> = {
  article: { label: "Article", icon: FileText, color: "#7EB6FF" },
  report: { label: "Report", icon: BarChart3, color: "#B9A5FF" },
  contact: { label: "Contact", icon: User, color: "#4FD8A8" },
  ama: { label: "AMA", icon: Mic, color: "#FFC94D" },
  deal: { label: "Deal", icon: Tag, color: "#FF8FC0" },
};

export function resourceDef(type: string): ResourceTypeDef {
  return RESOURCE_TYPES[(type as ResourceType)] ?? RESOURCE_TYPES.article;
}
