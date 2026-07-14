# ReachBot

An AI assistant over Reach Capital's ReachIn resources. Founders ask questions in
plain language; ReachBot answers from the ReachIn content and links the primary source
(Notion page, AMA recording, etc.). Reach only ever updates Notion — ReachBot re-scrapes
weekly on its own.

**Cost:** frontend hosting is free (Vercel); the backend runs a few dollars/month on
Fly.io (scale-to-zero); plus the Gemini API key (~$0–2/month).

## Stack

**Ingest pipeline** (produces the vector index):
- `reachin_export.py` — pulls all ReachIn Notion pages to `reachin_md/` (markdown + source links)
- `zoom_transcripts.py` — pulls AMA Zoom transcripts to `transcripts/`
- `ingest.py` — chunks + embeds the content into `index.npz` (Gemini embeddings)

**App** (two services):
- `backend/` — **FastAPI** RAG service. Loads `index.npz`, retrieves, and streams the
  Gemini answer as SSE. Deploys to Fly.io. See [`backend/README.md`](backend/README.md).
- `frontend/` — **Next.js + shadcn/ui** chat UI. Talks only to its own `/api/*` proxy
  routes → the backend. Deploys to Vercel. See [`frontend/README.md`](frontend/README.md).

**Automation:**
- `.github/workflows/weekly.yml` — re-runs the export + re-embed every Monday (GitHub
  Actions cron), commits the new `index.npz`, and redeploys the backend.

## One-time setup
1. **Notion integration:** create one at https://www.notion.so/my-integrations, copy
   the secret, and add it to the ReachIn top page (Connections menu).
2. **Gemini API key:** https://aistudio.google.com/apikey (pay-as-you-go, cents-scale).
3. **Build the index locally:**
   ```
   pip install -r requirements.txt
   export NOTION_TOKEN="ntn_..."
   export GEMINI_API_KEY="..."
   python reachin_export.py     # -> reachin_md/
   python zoom_transcripts.py   # -> transcripts/  (optional; skip if no Zoom creds)
   python ingest.py             # -> index.npz
   ```
4. **Run the app locally** (two processes):
   - Backend: `cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && INDEX_PATH=../index.npz uvicorn main:app --port 8000`
   - Frontend: `cd frontend && npm install && npm run dev` (needs `.env.local` → `BACKEND_URL=http://127.0.0.1:8000`)

## Deploy
- **Backend → Fly.io:** `fly deploy` from the repo root (see [`backend/README.md`](backend/README.md)).
  Secrets via `fly secrets set`: `GEMINI_API_KEY`, `ACCESS_PASSWORD`, `SESSION_SECRET`, `ALLOWED_ORIGIN`.
- **Frontend → Vercel:** deploy `frontend/` with `BACKEND_URL` set to the Fly URL.

## Automatic weekly refresh
In GitHub repo settings → Secrets → Actions, add `NOTION_TOKEN`, `GEMINI_API_KEY`, and
`FLY_API_TOKEN`. The workflow re-exports Notion, rebuilds the index, commits it, and
redeploys the backend every Monday. You can also trigger it by hand from the Actions tab.

## Swapping the model
`CHAT_MODEL` in `backend/rag.py` is the only thing to change to use a different model.
The embeddings model is `EMBED_MODEL` in both `ingest.py` and `backend/rag.py` (keep them matched).
