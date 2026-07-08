"""Classify a retrieved hit into one of 5 resource types.

Mirrors the CATEGORY_TYPE / title-keyword logic from the ReachBot design system.
The frontend has an identical map for icons/colors; the backend only needs to emit
the *type string* alongside each hit so the UI can render the right affordance.

Types: article | report | contact | ama | deal
"""

CATEGORY_TYPE = {
    "Session Recordings": "ama",
    "Reach Advisors": "contact",
    "Consultants & Coaches": "contact",
    "Media Contacts": "contact",
    "Partner Access, Credits, Discounts": "deal",
}

_REPORT_KEYWORDS = (
    "report", "benchmark", "benchmarks", "market map", "landscape",
    "state of", "survey", "analysis", "research", "whitepaper", "study",
)


def classify(title: str, category: str) -> str:
    cat = (category or "").strip()
    if cat in CATEGORY_TYPE:
        return CATEGORY_TYPE[cat]
    # Library Database mixes reports and articles — split on title keywords.
    tl = (title or "").lower()
    if any(k in tl for k in _REPORT_KEYWORDS):
        return "report"
    # Empty category (~44%, external links) and everything else → article.
    return "article"
