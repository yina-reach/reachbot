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
CHAT_MODEL = "gemini-2.5-flash"
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

STEP 1 — CLASSIFY, THEN ANSWER. Silently route every query into exactly ONE response
type below and follow its structure. Do not name the type in your answer.

1. RESOURCE-FIRST — the user wants one specific fact or artifact (a code, a date, a
   contact, a named doc). Structure: one clause of prose (max 20 words), then 1–3
   resource links. The linked line carries the detail; do NOT repeat in prose a fact
   (code, date, contact, stat) that already appears on the resource line.
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
- When you name a specific person or entity that came from the network — an advisor,
  consultant, coach, scout, media contact, or partner/credit — hyperlink their NAME to
  their Notion source_url the FIRST time you mention them in the answer body, e.g.
  "[Myerhoff Consulting](https://www.notion.so/...) — sales strategy, fractional CRO".
  These profile pages ARE valid sources; every named profile must be clickable, not just
  the articles and recordings.
- For deck/slide links: prefer linking to the Notion page (source_url) rather than raw S3/PDF URLs,
  which expire. You may mention "includes slides" or "includes deck" in the description.
  Only use a direct PDF/S3 URL if no Notion page URL is available.

FORMATTING: use short paragraphs or bulleted lists with a blank line between items.
Quote AMA speakers when transcript content exists. For RESOURCE-FIRST and SUMMARY-FIRST
answers, end with a single **Resources** list (max 3 entries: the sources you used,
plus a related pick if genuinely useful) — [Page Title](URL) — one sentence each. Do
not split into separate "Sources" and "Explore more" sections. BROWSE, NOT-FOUND, and
META answers need no Resources section (the list, gap, or category overview IS the
answer)."""


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


def retrieve(query: str):
    """Return list of (raw_chunk, title, url, category) top hits."""
    idx = load_index()
    vectors, chunks, titles, urls, categories = (
        idx.vectors, idx.chunks, idx.titles, idx.urls, idx.categories,
    )
    r = _client.models.embed_content(model=EMBED_MODEL, contents=query)
    q = np.array(r.embeddings[0].values, dtype=np.float32)
    q /= (np.linalg.norm(q) + 1e-9)
    scores = vectors @ q

    perk = _is_perk_query(query)

    def allowed(i):
        if not perk:
            return True
        return categories[i] == PERK_CATEGORY or PERK_CATEGORY.lower() in str(chunks[i]).lower()

    results = []
    for i in np.argsort(-scores):
        if not allowed(i):
            continue
        raw = chunks[i].strip()
        body_lines = [l for l in raw.split('\n')[1:] if l.strip()]
        body = '\n'.join(body_lines).strip()
        if len(body) < MIN_BODY_CHARS:
            continue  # nav stub, empty AMA header, etc.
        results.append((raw, str(titles[i]), str(urls[i]), str(categories[i])))
        if len(results) >= TOP_K:
            break
    return results


def build_context(hits) -> str:
    return "\n\n---\n\n".join(f"[{t}]({u})\n{c}" for c, t, u, _cat in hits)


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
            model="gemini-2.5-flash-lite",
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

    for model in [CHAT_MODEL, "gemini-2.5-flash-lite", "gemini-2.5-flash"]:
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
