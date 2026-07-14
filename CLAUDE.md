# CLAUDE.md — REACHBOT project context

You are helping build **REACHBOT**, a RAG chatbot over Reach Capital's "ReachIn" Notion
hub for portfolio founders. This file orients you; `README.md` and `REACHBOT_build_guide.md`
have full detail.

## What this is
A retrieval-augmented chatbot (NOT fine-tuned). It extracts ReachIn content + AMA Zoom
transcripts into markdown, embeds them into a local vector index, and answers founder
questions with citations + "explore more" pointers. Reach edits only Notion; a weekly job
refreshes the bot.

## The files
- `reachin_export.py`  — Notion API → `reachin_md/*.md` (needs `NOTION_TOKEN`)
- `zoom_transcripts.py` — Zoom API → `transcripts/*.md` (needs `ZOOM_ACCOUNT_ID/CLIENT_ID/CLIENT_SECRET`)
- `ingest.py`          — markdown → `index.npz` (needs `GEMINI_API_KEY`)
- `backend/`           — **FastAPI** RAG service (retrieval + streaming Gemini chat). Loads
  `index.npz` once; serves `/chat` (SSE), `/health`, `/login`. Deploys to Fly.io. See `backend/README.md`.
- `frontend/`          — **Next.js + shadcn/ui** React chat UI. Talks only to its own
  `/api/*` proxy routes → FastAPI. Deploys to Vercel. See `frontend/README.md`.
  (The old single-file Streamlit `app.py` was removed once the React app went live in prod.)
- `.github/workflows/weekly.yml` — Monday cron: re-runs the ingest pipeline, commits the new
  `index.npz`, then `flyctl deploy`s the backend so it reloads the index.

## Architecture (post-Streamlit migration, 2026-07)
`frontend` (Vercel, React/shadcn) → same-origin `/api/*` proxy → `backend` (Fly.io, FastAPI)
→ Gemini + NumPy over `index.npz`. The proxy keeps the backend URL + auth cookie server-side.
Retrieval semantics + the Gemini system prompt are **identical** to the old `app.py` (lifted
verbatim into `backend/rag.py`); generation now streams token-by-token. `MIGRATION_PLAN.md`
has the full detail. The ingest pipeline (export/transcripts/ingest → `index.npz`) is unchanged.

## Build sequence (run on this machine — it has the network access)
1. `pip install -r requirements.txt`
2. Create a `.env` (DO NOT COMMIT — it's gitignored) with the secrets:
   ```
   NOTION_TOKEN=ntn_...
   GEMINI_API_KEY=...
   ZOOM_ACCOUNT_ID=...
   ZOOM_CLIENT_ID=...
   ZOOM_CLIENT_SECRET=...
   ```
   then `set -a; source .env; set +a`
3. `python reachin_export.py`        # written content
4. `python zoom_transcripts.py`      # AMA transcripts (full backfill; skip if no Zoom creds yet)
5. `python ingest.py`                # build the index
6. Run the app locally (two processes):
   - backend: `cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && INDEX_PATH=../index.npz uvicorn main:app --port 8000`
   - frontend: `cd frontend && npm install && npm run dev`  (needs `.env.local` → `BACKEND_URL=http://127.0.0.1:8000`)
7. Deploy: backend → Fly.io (`fly deploy`, see `backend/README.md`); frontend → Vercel
   (import `frontend/`, set `BACKEND_URL`). Set backend secrets via `fly secrets set`.
8. Automate: add `GEMINI_API_KEY`, `NOTION_TOKEN`, Zoom creds, and `FLY_API_TOKEN` to GitHub
   Actions secrets; the weekly workflow rebuilds the index and redeploys the backend Mondays.

## Important
- **Secrets:** only via `.env` / environment / GitHub secrets. Never hardcode or commit them.
  Tokens already shared in chat should be rotated.
- **Zoom plan tier** decides transcription: Business/Enterprise = transcripts already exist;
  Pro = transcribe audio with Whisper/Gemini (recordings logged to `transcripts/_missing.txt`).
- You can build and demo on written content ALONE first, then add AMA transcripts once Zoom
  creds exist. Don't block the whole thing on Zoom.
- Verify `reachin_export.py` captures Notion database row *properties* (recording/deck links),
  not just page bodies — extend it if a spot-check shows gaps.

## First thing to do
Confirm which secrets the user has, then run steps 1→6 for whatever's available. Report what
got extracted (file counts) and any errors.
