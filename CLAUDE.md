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
- `app.py`             — Streamlit chat UI (needs `GEMINI_API_KEY`)
- `.github/workflows/weekly.yml` — Monday cron that re-runs all of the above

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
6. `streamlit run app.py`            # test locally
7. Deploy: push to GitHub (private), connect at share.streamlit.io, add secrets there.
8. Automate: add the same secrets to GitHub Actions secrets; the weekly workflow runs Mondays.

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
