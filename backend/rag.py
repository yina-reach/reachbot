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

Structure every response:
1. **Direct answer** — specific, practical, with each key point on its own line. Use numbered or bulleted lists with a blank line between each item for readability. Quote AMA speakers if transcript content exists.
2. **Resources** — combine sources used AND 2-3 related resources into one unified list. For each, output: [Page Title](URL) — one sentence on what it covers. Do not split into separate "Sources" and "Explore more" sections.

If the context doesn't cover the question well, say so honestly."""


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


def generate_stream(context: str, question: str) -> Iterator[str]:
    """Yield answer text chunks. Same model fallback + quota handling as the
    Streamlit version, but streamed token-by-token."""
    contents = f"Context:\n{context}\n\nQuestion: {question}"
    config = genai.types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)

    for model in [CHAT_MODEL, "gemini-2.5-flash-lite", "gemini-2.5-flash"]:
        try:
            stream = _client.models.generate_content_stream(
                model=model, contents=contents, config=config,
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
