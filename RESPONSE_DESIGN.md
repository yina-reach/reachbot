# ReachBot Response Design

How ReachBot decides *what kind of answer* to give, how long it should be, and how
resources get shown. This is the spec behind the system prompt (in `app.py` and
`backend/rag.py` — kept identical) and the card renderer. Based on the 7/7 feedback.

---

## 1. The ten response types

Every query is silently routed into exactly ONE type. The model never names the
type in its answer — the type just dictates the answer's shape.

| # | Type | Triggered when… | Answer shape |
|---|------|-----------------|--------------|
| 1 | **Resource-first** | User wants one specific fact/artifact: a code, date, contact, named doc | ≤ 20 words of prose + 1–3 resource cards. The card carries the detail — prose never repeats a fact (code, date, stat) that's on the card |
| 2 | **Summary-first** | User wants interpretation or synthesis | Direct answer in the FIRST sentence, then supporting detail with inline citations. 40–80 words (one source) / 80–150 (multi, ≤ 3 named citations — name the two strongest + "and a few others") |
| 3 | **Browse / enumerate** | Breadth *phrasing* — "what do you have on…", "show me all…", "everything related to…" (phrasing, never topic) | List of title cards with one-line descriptors, NO synthesis. Past ~8 results: show the strongest 8 + "want the full list?" |
| 4 | **Not-found** | Nothing in the knowledge base covers it | State the gap plainly in 1–2 sentences. NEVER pass off general AI knowledge as a knowledge-base answer — if general knowledge helps, label it: "Outside the ReachIn knowledge base: …" |
| 5 | **Low-confidence / partial** | Context is adjacent but doesn't directly answer | Answer only what's supported + flag the mismatch ("the closest resource covers X, not exactly what you asked"). Never overstate relevance |
| 6 | **Conflicting sources** | Two sources disagree (old vs. new report, two advisors) | Surface both, attribute each, note recency. Never silently average or pick a winner |
| 7 | **Disambiguation** | See §3 — the only case where the bot asks instead of answers | ONE question offering concrete named options (never vague categories) |
| 8 | **Out-of-scope redirect** | Question belongs to a different tool or isn't knowledge-base material | Name what's actually needed, point there. Don't force an answer from the wrong source |
| 9 | **Meta / capability** | "What can you help with?" / "What's in here?" | Answer with the real knowledge-base categories — consistent with the empty state's scope line |
| 10 | **Staleness caveat** | (Modifier on any type) best source may be outdated | Short *trailing* caveat ("— from the 2023 report, the most recent in ReachIn"), never a blocking disclaimer |

**Trust-critical group:** not-found, low-confidence, conflicting, staleness. These
are what stop the model from quietly turning thin or absent evidence into a
confident-sounding answer — the core risk for a "curated, bounded, trustworthy"
product. When in doubt, err toward honesty about the gap.

## 2. Length rules

- **Hard ceiling ~150 words** of prose, unless the user explicitly asked for depth
  ("walk me through", "compare", "give me the full picture").
- **Length tracks evidence density, not completeness** — one thin data point gets a
  short honest answer, not padding.
- **No card restating:** a fact about to appear on a card must not also appear in
  the prose above it.
- **Follow-up depth is opt-in:** end with a next step ("Want the full report?")
  rather than front-loading every angle.
- Eval note: over-answering is the likelier failure mode than under-answering —
  the source material is deep, and the model loves to relay it.

## 3. When the bot may ask a clarifying question

**Default: answer, don't ask.** Every question taxes the fast-bounded-answer value
prop. It may ask ONLY when all three hold:

1. Answering the most likely interpretation would be **wrong** (not just broader);
2. The query maps to **2+ specific named resources** with materially different answers;
3. **No reasonable default** exists.

If any condition fails → answer with the best default and state the assumption in
one clause ("using the most recent (Q2 2026) report…").

Anti-patterns (all prohibited): confirming scope inferable from phrasing; asking
when a default costs nothing to state; stacking questions; asking about things a
search would resolve. One-line test: *clarify on resource collision, not topic
breadth.*

## 4. Resource cards

Cards are typed by the **shape of the data**, not the Notion folder name. One
visual identity per type (icon + accent), reused across chips, the scope line,
and cards:

| Type | Icon | Covers | Key fields shown |
|------|------|--------|------------------|
| Article | 📄 | Content folders, Reach blog, Good Reads | publisher, sector |
| Report | 📊 | Markets & Research, Reach Reports | publisher, sector/vintage, tags |
| Contact | 👤 | Advisors, Scouts, Consultants & Coaches, Media | role, specialty, contact method |
| Session / AMA | 🎙️ | Session Recordings | speaker, date, tags |
| Deal / offer | 🎁 | Partner Access, Credits, Discounts | offer, contact, Reach point-of-contact |

Card caps: **1–3** for resource-first and summary-first (cards are exceptions
carved out of prose); **uncapped** for browse/enumerate (that type exists to
surface everything), with the ~8-result soft rendering threshold.

**Citations are a separate tier from cards:** every claim gets an inline citation
woven into its sentence ("…according to Maria's AMA"), whether or not that source
also gets a card.

*Implementation note:* the model emits `- [Title](url) — description` lines; the
renderer turns any run of them into typed cards, looking up each source's type and
fields from the retrieval results (`resource_types.py` / `resource_fields.py`).

## 5. Where links point (thin-wrapper rule)

Some Notion pages are just a title + an outbound link. Two layers keep clicks
useful:

1. **Ingest-time (durable):** pages with < ~50 words of original text whose only
   substance is an external link get the **external URL as their canonical link**
   in the index. Pages with real curation notes keep their Notion link — that
   framing is part of the value.
2. **Prompt fallback:** if retrieval still surfaces a minimal wrapper page, the
   model cites the external source directly.

**Attribution stays consistent either way:** external destinations are described
as "via ReachIn's <category> resources" — never as something found on the open web.

## 6. Evidence-aware retrieval (dynamic thresholding)

Retrieval depth adapts to the similarity-score curve instead of always returning a
fixed top-25. Calibrated 2026-07-16 on real queries (top scores: on-topic ~0.73–0.80,
adjacent ~0.66, off-topic ~0.54):

- **Coverage tier from the absolute top score:** ≥ 0.70 STRONG · 0.60–0.70 PARTIAL ·
  < 0.60 WEAK.
- **Dynamic cutoff:** keep chunks within 0.08 of the best match. Lookup queries cliff
  fast (3–8 survive → fewer distractors); synthesis plateaus (up to 25); WEAK is
  capped at 5 — *less* context on purpose, because 25 noise chunks tempt the model to
  overreach, while 5 let it honestly name "the closest thing."
- **Browse queries** (breadth phrasing) skip margin logic: best chunk per page, up to
  15 distinct sources ≥ 0.60 — the user wants the catalog, not depth.
- **Diversity guard:** max 3 chunks per page (except perk queries, where one page
  legitimately holds all the deals), so a single long transcript can't hog context.
- **The model is told what retrieval found:** context opens with a
  `RETRIEVAL QUALITY: STRONG/PARTIAL/WEAK` line, and the prompt anchors routing to it
  — STRONG answers normally, PARTIAL defaults to low-confidence framing, WEAK
  defaults to not-found. This grounds the trust-critical types in a *measured*
  signal instead of the model's own judgment of the chunks.

Thresholds live at the top of `retrieve()` in both implementations. If the embedding
model or chunking ever changes, re-run the calibration (score curves shift) before
trusting the old numbers.

---

*Maintained alongside the prompt — if you change one, change the other. The prompt
lives in `app.py` (`generate()`) and `backend/rag.py` (`SYSTEM_PROMPT`).*
