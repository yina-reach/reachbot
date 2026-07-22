"""ReachBot RAG core — retrieval + streaming generation.

Lifted from the Streamlit app.py, unchanged in semantics:
  - load_index()  : loads index.npz once (module singleton, replaces st.cache_resource)
  - retrieve()    : NumPy cosine search + perk-query filtering + thin-chunk skipping
  - generate()    : Gemini chat, now STREAMING, with the same model fallback + quota handling

Env:
  GEMINI_API_KEY  (required)
  INDEX_PATH      (default: index.npz)
"""
import os
import re
import time
from typing import Iterator

import numpy as np
from google import genai

EMBED_MODEL = "gemini-embedding-001"
# Stable "-latest" aliases track Google's current recommended model and won't
# 404 out for newer API projects the way pinned gemini-2.5-flash did (it's
# blocked for generateContent on projects created after its deprecation).
CHAT_MODEL = "gemini-flash-latest"
CHAT_FALLBACKS = ["gemini-flash-lite-latest", "gemini-3.5-flash"]
TOP_K = 25
INDEX_PATH = os.environ.get("INDEX_PATH", "index.npz")

_API_KEY = os.environ.get("GEMINI_API_KEY")
if not _API_KEY:
    raise RuntimeError("Set GEMINI_API_KEY (https://aistudio.google.com/apikey).")
_client = genai.Client(api_key=_API_KEY)

MIN_BODY_CHARS = 120  # skip pure nav stubs / empty pages

# Perk/discount/partnership questions should answer ONLY from the partner-deals
# page, not pull in tangential pages. Detect intent + restrict the candidate pool.
PERK_CATEGORY = "Partner Access, Credits, Discounts"
PERK_KEYWORDS = (
    "discount", "credit", "perk", "coupon", "promo", "voucher", "redeem",
    "% off", "percent off", "free month", "free trial", "partner offer",
    "partner deal", "partner discount", "partnership offer", "exclusive deal",
)

SYSTEM_PROMPT = """You are ReachBot, an assistant for Reach Capital's portfolio founders.
Answer exclusively from the ReachIn context provided. Never fabricate facts or links.

CONTEXT FORMAT: Each block starts with [Title](NotionURL) then the page content.
The content may contain **Link:** or **Files & media:** fields with direct resource URLs.
The context may include Reach Capital Network Profiles for advisors, consultants, scouts, and media contacts — use these to answer questions about who is in the Reach network.

The context begins with a RETRIEVAL QUALITY line — a measured signal of how well the
knowledge base covers this question. Let it anchor your routing: STRONG → answer
normally. PARTIAL → default to LOW-CONFIDENCE framing; only answer plainly if a chunk
truly nails the question. WEAK → default to NOT-FOUND; the chunks you see are the
least-bad matches, not real coverage — do not stitch them into a confident answer.

STEP 1 — CLASSIFY, THEN ANSWER. Silently route every query into exactly ONE response
type below and follow its structure. Do not name the type in your answer.

1. RESOURCE-FIRST — the user wants one specific fact or artifact (a code, a date, a
   contact, a named doc), OR a set of matching resources (e.g. "what partner
   discounts are available for AI credits" → the matching deals). Structure: one
   short intro line, then the resources ONLY in the **Resources** list below — never
   as a bulleted prose list. When several resources match, make the intro a count
   ("I found 5 partner discounts for AI credits:") and let each card carry its own
   detail. Do NOT restate a resource's detail (offer, code, date, contact, stat) in
   the prose or in bullets — it already appears on the card. No inline bullet list of
   the resources; the **Resources** cards ARE the list.
2. SUMMARY-FIRST — the user wants interpretation or synthesis. Structure: the direct
   answer in the FIRST sentence, then supporting detail with inline citations woven
   into sentences ("...according to Maria's AMA"). One source: 40–80 words. Multiple
   sources: 80–150 words, citing at most 3 by name — name the two strongest and add
   "and a few others" if more apply. Never stack 5 citations in one paragraph.
3. BROWSE / ENUMERATE — the user wants a menu, not an answer. Trigger on breadth
   PHRASING ("what do you have on...", "show me all...", "everything related to..."),
   not on topic. Structure: a list of [Title](URL) lines with one short descriptor
   each, NO synthesis. Past ~8 results, show the strongest 8 and end with "want the
   full list?". A specific single-answer question is never enumerate.
4. NOT-FOUND — nothing in the context covers it. State the gap plainly in 1–2
   sentences. NEVER fill the gap with general AI knowledge disguised as a
   knowledge-base answer; if general knowledge would genuinely help, label it
   explicitly ("Outside the ReachIn knowledge base: ...").
5. LOW-CONFIDENCE / PARTIAL MATCH — the context is adjacent but doesn't directly
   answer. Answer only what's supported and flag the mismatch ("The closest resource
   covers X, not exactly what you asked"). Don't overstate relevance.
6. CONFLICTING SOURCES — two sources disagree (old vs. new report, two advisors).
   Surface both, attribute each, note recency if relevant. Never silently average
   the numbers or pick a winner.
7. DISAMBIGUATION — ask a clarifying question ONLY when ALL three hold: (a) answering
   the most likely interpretation would be WRONG (not just broader), (b) the query maps
   to 2+ specific named resources with materially different answers, (c) no reasonable
   default exists. Then ask ONE question offering the concrete named options. If any
   condition fails, answer with the most reasonable default and state the assumption in
   one clause ("using the most recent (Q2 2026) report..."). Never stack questions.
8. OUT-OF-SCOPE REDIRECT — the question belongs to a different tool or isn't
   knowledge-base material. Name what's actually needed and point there; don't force
   an answer from the wrong source.
9. META / CAPABILITY — "what can you help with?" / "what's in here?". Answer with the
   actual knowledge-base categories: AMA & session recordings, reports & research,
   articles & good reads, advisors/consultants/media contacts, partner credits &
   discounts.

STALENESS (applies to any type): if the best available source may be outdated
(an old vintage or a superseded report), append a short trailing caveat
("— from the 2023 report, the most recent in ReachIn"), never a blocking disclaimer.

LENGTH DISCIPLINE:
- Hard ceiling ~150 words of prose unless the user explicitly asked for depth
  ("walk me through", "compare", "give me the full picture").
- Length tracks evidence density, not completeness: a single thin data point gets a
  short honest answer, not padding.
- End with an opt-in next step ("Want the full report?") rather than front-loading
  every possible angle.

RULES:
- Only cite a source if it contains substantive information relevant to the question.
  Do NOT cite a page that only has a title with no real body content.
- If an AMA page has no notes or transcript content, do not pretend to know what was discussed.
  You may mention the AMA exists and link to it, but do not summarize it.
- ALWAYS format every link as markdown: [Descriptive Title](https://url.here)
  Never output a bare URL — always wrap it in [text](url) format.
- Place inline citations directly in the sentence — do NOT wrap the finished
  [Title](URL) link in an extra pair of parentheses.
- NEVER write a bracketed title with no URL, like [Some Report]. If you want to
  mention a source whose URL you don't have in front of you, name it in plain
  prose without brackets ("the K-12 Superintendents Roundtable transcript").
- When you name a specific person or entity that came from the network — an advisor,
  consultant, coach, scout, media contact, or partner/credit — hyperlink their NAME to
  their Notion source_url the FIRST time you mention them in the answer body, e.g.
  "[Myerhoff Consulting](https://www.notion.so/...) — sales strategy, fractional CRO".
  These profile pages ARE valid sources; every named profile must be clickable, not just
  the articles and recordings.
- For deck/slide links: prefer linking to the Notion page (source_url) rather than raw S3/PDF URLs,
  which expire. You may mention "includes slides" or "includes deck" in the description.
  Only use a direct PDF/S3 URL if no Notion page URL is available.
- When a retrieved Notion page's own content is minimal (a title, a tag, and a single
  outbound link with little original framing), cite and link the EXTERNAL source
  directly instead of the Notion page. If the Notion page includes original commentary,
  curation notes, or context beyond the link, prefer the Notion page — that framing is
  part of the citation's value.
- Attribution stays consistent regardless of where a link points: describe external
  destinations as coming via ReachIn's own categorization ("via ReachIn's Fundraising
  resources"), never as something you found on the open web.
- Inline citations are always present, separate from any resource list: every claim
  gets a citation woven into its sentence ("...according to Maria's AMA"), whether or
  not the source also appears as a resource line.

FORMATTING: use short paragraphs or bulleted lists with a blank line between items.
Quote AMA speakers when transcript content exists. For RESOURCE-FIRST and SUMMARY-FIRST
answers, end with a single **Resources** list — [Page Title](URL) — one sentence each,
NOT split into "Sources" and "Explore more" sections. For a SUMMARY-FIRST answer keep
this to max 3 entries (the sources used plus a related pick if useful). For a
RESOURCE-FIRST set (e.g. matching partner discounts), list EVERY matching resource
here — this list is the answer, and it renders as cards. Do NOT also enumerate those
resources as bullets in the prose above; the intro is just one line (a count when
several match). BROWSE, NOT-FOUND, and META answers need no Resources section (the
list, gap, or category overview IS the answer)."""


class _Index:
    """Singleton holder so the 100MB index loads exactly once per process."""
    vectors = None
    chunks = None
    titles = None
    urls = None
    categories = None

    @classmethod
    def load(cls):
        if cls.vectors is not None:
            return cls
        d = np.load(INDEX_PATH, allow_pickle=True)
        v = d["vectors"].astype(np.float32)
        v /= (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)
        cats = d["categories"] if "categories" in d.files \
            else np.array([""] * len(d["chunks"]), dtype=object)
        cls.vectors = v
        cls.chunks = d["chunks"]
        cls.titles = d["titles"]
        cls.urls = d["urls"]
        cls.categories = cats
        return cls


def load_index():
    return _Index.load()


def _is_perk_query(q: str) -> bool:
    ql = q.lower()
    return any(k in ql for k in PERK_KEYWORDS)


# ── Dynamic retrieval thresholds (calibrated on real score curves 2026-07-16;
#    see RESPONSE_DESIGN.md §6) ────────────────────────────────────────────────
# Absolute top-score tiers: on-topic queries top ~0.73-0.80, adjacent ~0.66,
# off-topic ~0.54 — cleanly separable.
TIER_STRONG = 0.70    # solid coverage
TIER_PARTIAL = 0.60   # adjacent / partial coverage
MARGIN = 0.08         # keep chunks within this of the top score
# Perk/deal chunks are near-duplicates in structure ("Category / Offer / Contact
# / …"), so they cluster tightly in embedding space — a bunch of IRRELEVANT deals
# sit within the normal 0.08 margin of the one the user actually asked about
# ("HR discounts" → TriNet 0.729, then Carta/Pave/Zendesk all ~0.68). A tighter
# margin cuts that cluster so only the genuinely-relevant deal(s) survive; the
# model still offers "want the full list?" for breadth.
PERK_MARGIN = 0.04
# For a narrow perk question ("HR discounts?") ONE relevant deal is a complete
# answer, not a starved one — so don't pad perks back up to MIN_KEEP with the
# next-best (irrelevant) deals. A browse query ("what discounts do you have?")
# takes the separate breadth branch and is unaffected.
PERK_MIN_KEEP = 1
# How many chunks each tier may pass to the model. Weak evidence gets LESS
# context on purpose: 25 noise chunks tempt the model to overreach; 5 lets it
# name "the closest thing" and honestly route to not-found/low-confidence.
TIER_CAPS = {"strong": TOP_K, "partial": 12, "weak": 5}
MIN_KEEP = 4          # never starve the model entirely

_BROWSE_RE = re.compile(
    r"what do (?:you|we) have|show me (?:all|everything)|everything (?:on|about|"
    r"related to)|list (?:all|everything)|what(?:'s| is) (?:in|available)|browse",
    re.IGNORECASE)


def retrieve(query: str):
    """Return (hits, quality). hits = [(raw_chunk, title, url, category)];
    quality = {tier, top, kept} describing evidence strength, surfaced to the
    model so not-found/low-confidence routing is grounded in scores."""
    idx = load_index()
    vectors, chunks, titles, urls, categories = (
        idx.vectors, idx.chunks, idx.titles, idx.urls, idx.categories,
    )
    r = _client.models.embed_content(model=EMBED_MODEL, contents=query)
    q = np.array(r.embeddings[0].values, dtype=np.float32)
    q /= (np.linalg.norm(q) + 1e-9)
    scores = vectors @ q

    perk = _is_perk_query(query)
    browse = bool(_BROWSE_RE.search(query))

    def allowed(i):
        if not perk:
            return True
        return categories[i] == PERK_CATEGORY or PERK_CATEGORY.lower() in str(chunks[i]).lower()

    # Walk candidates in score order, skipping thin chunks; keep scores.
    ranked = []
    for i in np.argsort(-scores):
        if not allowed(i):
            continue
        raw = chunks[i].strip()
        body_lines = [l for l in raw.split('\n')[1:] if l.strip()]
        body = '\n'.join(body_lines).strip()
        if len(body) < MIN_BODY_CHARS:
            continue  # nav stub, empty AMA header, etc.
        ranked.append((float(scores[i]), raw, str(titles[i]), str(urls[i]), str(categories[i])))
        if len(ranked) >= 40:  # enough headroom for browse dedup + margin cuts
            break

    if not ranked:
        return [], {"tier": "weak", "top": 0.0, "kept": 0}

    top = ranked[0][0]
    tier = "strong" if top >= TIER_STRONG else ("partial" if top >= TIER_PARTIAL else "weak")

    if browse and tier != "weak":
        # Breadth query: one best chunk per PAGE, up to 15 distinct sources.
        # Margin logic would starve these — "what do you have on X" often nails
        # one hub page then cliffs, but the user wants the catalog.
        seen, picked = set(), []
        for s, raw, t, u, cat in ranked:
            if s < TIER_PARTIAL or t in seen:
                continue
            seen.add(t)
            picked.append((s, raw, t, u, cat))
            if len(picked) >= 15:
                break
    else:
        # Dynamic cutoff relative to the best match: lookups cliff fast (3-8
        # survive), synthesis plateaus (cap applies), off-topic is flat+low
        # (weak tier cap applies).
        floor = top - (PERK_MARGIN if perk else MARGIN)
        picked = [h for h in ranked if h[0] >= floor][:TIER_CAPS[tier]]
        min_keep = PERK_MIN_KEEP if perk else MIN_KEEP
        if len(picked) < min_keep:
            picked = ranked[:min_keep]
        if not perk:
            # Diversity guard: one long transcript can't hog the context.
            per_page = {}
            capped = []
            for h in picked:
                per_page[h[2]] = per_page.get(h[2], 0) + 1
                if per_page[h[2]] <= 3:
                    capped.append(h)
            picked = capped

    hits = [(raw, t, u, cat) for _s, raw, t, u, cat in picked]
    return hits, {"tier": tier, "top": round(top, 3), "kept": len(hits)}


def build_context(hits, quality=None) -> str:
    body = "\n\n---\n\n".join(f"[{t}]({u})\n{c}" for c, t, u, _cat in hits)
    if quality:
        label = {"strong": "STRONG — the knowledge base covers this well",
                 "partial": "PARTIAL — closest matches are adjacent, not direct",
                 "weak": "WEAK — nothing in the knowledge base matches this well"}[quality["tier"]]
        body = (f"RETRIEVAL QUALITY: {label} "
                f"({quality['kept']} chunks passed the relevance bar).\n\n{body}")
    return body


def standalone_query(question: str, history) -> str:
    """Rewrite a follow-up ("more on that", "who ran it?") into a self-contained
    retrieval query using the chat so far. Falls back to the raw question."""
    if not history:
        return question
    convo = "\n".join(
        f"{'User' if m.get('role') == 'user' else 'ReachBot'}: {str(m.get('content', ''))[:500]}"
        for m in history[-6:]
    )
    try:
        resp = _client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=(
                "Rewrite the user's latest message as ONE self-contained search query "
                "for a knowledge base, resolving pronouns and references from the "
                "conversation. If it is already self-contained, return it unchanged. "
                "Output only the query, nothing else.\n\n"
                f"Conversation:\n{convo}\n\nLatest message: {question}"
            ),
        )
        q = (resp.text or "").strip()
        return q if 0 < len(q) < 400 else question
    except Exception:
        return question


def generate_stream(context: str, question: str, history=()) -> Iterator[str]:
    """Yield answer text chunks. Same model fallback + quota handling as the
    Streamlit version, but streamed token-by-token. `history` is a list of
    {role: "user"|"assistant", content: str} dicts; recent turns are included
    so follow-ups resolve, while the Context always applies to the LATEST question."""
    turns = [
        {"role": "user" if m.get("role") == "user" else "model",
         "parts": [{"text": str(m.get("content", ""))[:4000]}]}
        for m in list(history)[-6:]
    ]
    turns.append({"role": "user",
                  "parts": [{"text": f"Context:\n{context}\n\nQuestion: {question}"}]})
    config = genai.types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)

    for model in [CHAT_MODEL, *CHAT_FALLBACKS]:
        try:
            stream = _client.models.generate_content_stream(
                model=model, contents=turns, config=config,
            )
            for event in stream:
                if getattr(event, "text", None):
                    yield event.text
            return
        except Exception as e:
            err = str(e)
            if "503" in err or "UNAVAILABLE" in err:
                continue  # try next model
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                m = re.search(r"retry[^']*'(\d+)s'", err)
                wait = int(m.group(1)) if m else 20
                if "PerDay" in err or "limit: 0" in err:
                    yield (
                        "_Your Gemini free-tier **daily quota** is exhausted._ "
                        "To fix this, enable billing on your Google AI project at "
                        "[aistudio.google.com](https://aistudio.google.com) — "
                        "it's pay-as-you-go and costs pennies for typical usage. "
                        "Alternatively, try again tomorrow when the quota resets."
                    )
                    return
                time.sleep(wait)
                continue  # retry after per-minute quota clears
            raise
    yield "_Gemini is temporarily unavailable — please try again in a moment._"
