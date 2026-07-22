# Changing ReachBot: what to touch

A task-oriented map. Find what you want to change on the left, edit the file on the
right. Line numbers drift as the code changes — search for the named constant if the
line has moved.

> **The #1 rule:** the bot's brain lives in `backend/rag.py` (retrieval +
> the Gemini system prompt). The frontend (`frontend/`) only renders; it never
> makes retrieval or prompt decisions.

> **Where to work:** after editing, `git commit` and `git push origin main` —
> the frontend redeploys from GitHub automatically (Vercel). Backend changes
> (`backend/`) also need a `fly deploy` (or wait for the weekly job, which
> redeploys it). See `MAINTENANCE.md`.

---

## Content & knowledge (the common case — usually NO code)

| I want to… | What to do |
|---|---|
| Add / edit / remove a resource the bot knows | **Just edit Notion.** Monday's job re-syncs it. For an instant update, run the "Weekly ReachBot Refresh" workflow manually (GitHub → Actions → Run workflow). |
| Add a whole new Notion database to the bot's knowledge | Nothing — `reachin_export.py` auto-discovers any database the Notion integration can see. Just make sure the integration is **shared** with the new database in Notion. |
| Fix "the bot says it doesn't know X" when X exists | The content is probably a file attachment (PDFs/decks aren't indexed, only their titles/links) or the index is stale. Re-run the weekly job. |
| Force a full re-embed (after changing chunking or the embed model) | Run the weekly workflow with `force_ingest = true`, or `python ingest.py --force` locally. |

---

## The bot's behavior & answers

| I want to change… | File → what to edit |
|---|---|
| **How it answers** (tone, the 10 response types, length rules, citation style) | The `SYSTEM_PROMPT` in `backend/rag.py` (~line 40). Spec is in `RESPONSE_DESIGN.md`. |
| **How many chunks it retrieves** (precision vs. breadth) | `TIER_CAPS`, `TOP_K`, `MARGIN` (and `PERK_MARGIN`) at the top of `retrieve()` in `backend/rag.py` (~line 185). Bigger caps = more context, more cost, more chance of noise. |
| **When it says "strong / partial / weak coverage"** | `TIER_STRONG` (0.70) and `TIER_PARTIAL` (0.60) in `backend/rag.py`. **Re-run the calibration script if you change the embedding model** — the score curves shift. See `RESPONSE_DESIGN.md` §6. |
| **Which model writes answers** | `CHAT_MODEL` / `CHAT_FALLBACKS` in `backend/rag.py` (~line 21). `EMBED_MODEL` — ⚠️ changing this **invalidates the whole index**; you must full-rebuild and re-calibrate thresholds. |
| **What counts as a "discount/perk" question** (scoped to partner deals only) | `PERK_KEYWORDS` list in `backend/rag.py`. |
| **Chunk size** (how text is split) | `CHUNK_WORDS` / `OVERLAP_WORDS` in `ingest.py:29`. ⚠️ Requires a full `--force` re-embed to take effect. |

---

## The front-end (empty state, chips, look)

| I want to change… | File → what to edit |
|---|---|
| **Empty state** (headline, logo, the example-question suggestions) | `frontend/src/components/welcome.tsx` (heading + `PROMPTS`) and the header in `frontend/src/app/page.tsx`. |
| **Colors / theming** (brand grayscale, resource accent, light/dark) | `frontend/src/app/globals.css` — the CSS-variable token blocks (`:root` / `.dark`). Styling elsewhere is Tailwind. |
| **Resource card types / icons / fields** | `backend/resource_types.py` (what maps to article/report/contact/ama/deal), `backend/resource_fields.py` (which fields each card parses), and `frontend/src/lib/resource-types.ts` (icon + which fields the card renders). |

---

## The email agent (ReachIn Connect)

| I want to… | What to do |
|---|---|
| **Let it file into a new Notion database** | Add one entry to the `DATABASES` registry in `email_agent.py:40` (name → id + one-line purpose), AND share the Notion integration with that database. That's it — it reads the live schema automatically. |
| **Change new tags / options / fields in an existing database** | Nothing in code — just change them in Notion. The agent reads the live schema every run. |
| **Change who approves** | The `TONY_EMAIL` GitHub secret. |
| **Change how often it polls** | The `schedule:` cron in `.github/workflows/reachin_agent.yml` (currently every 30 min). |
| **Pause it** | Comment out the `schedule:` block in that workflow. |

---

## The weekly automation

| I want to change… | File |
|---|---|
| When the refresh runs / what steps it does | `.github/workflows/weekly.yml` |
| When new AMA recordings get transcribed | `.github/workflows/transcribe.yml` (Monday 4 AM cron) |
| The transcription logic (how recordings are fetched/transcribed) | `transcribe_recordings.py` (Drive + Notion-embedded video) and `zoom_transcripts.py` (passcode-gated Zoom) |
| The "every transcript gets an AI summary" rule | `ensure_summaries.py` |

---

## Secrets (never in code)

Secrets live in a few places, kept in sync: local `.env`, **Fly secrets** (backend
runtime — `fly secrets set`), **Vercel env vars** (the frontend's `BACKEND_URL`), and
**GitHub Actions secrets** (the weekly/agent workflows). The list and rotation steps
are in `MAINTENANCE.md §3`. To rotate anything ever pasted in chat/email: update
everywhere it lives.

---

## Before you ship a behavior change — sanity check it

The bot is probabilistic; eyeball it before trusting it. Run it locally:

```
set -a && source backend/.env && set +a
cd backend && INDEX_PATH=../index.npz uvicorn main:app --port 8000 &
cd ../frontend && npm run dev   # needs .env.local → BACKEND_URL=http://127.0.0.1:8000
# open localhost:3000
```

Then ask it a few real questions AND a few it shouldn't be able to answer (a made-up
AMA, an off-topic request) to confirm it still refuses gracefully. A documented set of
adversarial probes lives in `tests/redteam.py` — a good thing to run after any prompt
or retrieval change. A formal eval suite is the top open next-step.

---

*See also: `MAINTENANCE.md` (run/deploy/handoff), `RESPONSE_DESIGN.md` (the answer
design spec).*
