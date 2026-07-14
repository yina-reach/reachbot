# ReachBot backend (FastAPI)

The RAG service. Loads the 100MB `index.npz` once at startup, embeds queries with
Gemini, retrieves with NumPy cosine similarity, and streams the answer from Gemini
back to the frontend as Server-Sent Events. Logic is lifted verbatim from the old
Streamlit `app.py` (retrieval semantics unchanged); the only change is that
generation now **streams**.

## Endpoints

| Method | Path       | Purpose                                                        |
|--------|------------|----------------------------------------------------------------|
| GET    | `/health`  | `{ ok, chunks, gated }` — readiness + whether a password is set |
| POST   | `/login`   | validate `ACCESS_PASSWORD`, set signed httpOnly cookie         |
| POST   | `/logout`  | clear the cookie                                               |
| POST   | `/chat`    | SSE stream: `sources` event → `token` events → `done`         |

## Local development

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # fill in GEMINI_API_KEY at minimum
set -a; source .env; set +a
uvicorn main:app --port 8000 --reload
```

`INDEX_PATH` defaults to `index.npz`; for local dev against the repo-root index,
set `INDEX_PATH=../index.npz` (already in `.env.example`).

## Environment

See `.env.example`. `GEMINI_API_KEY` is required. If `ACCESS_PASSWORD` is set,
`SESSION_SECRET` is required (it signs the auth cookie). `ALLOWED_ORIGIN` must be
the frontend origin (CORS).

## Deploy (Fly.io)

The image is built from the **repo root** (so the 100MB `index.npz` is in context)
via `../fly.toml` + this `Dockerfile`.

```bash
# from repo root
fly launch --no-deploy
fly secrets set GEMINI_API_KEY=... ACCESS_PASSWORD=... SESSION_SECRET=... \
               ALLOWED_ORIGIN=https://<your-vercel-app>.vercel.app
fly deploy
# create a token for the weekly GitHub Action to redeploy:
fly tokens create deploy   # → add as GitHub secret FLY_API_TOKEN
```

The index is baked into the image. The weekly workflow rebuilds `index.npz`,
commits it, then runs `flyctl deploy` to ship a fresh image the service reloads.

**Scale-to-zero note:** `fly.toml` sets `auto_stop_machines = "stop"` (cheap, but
the first request after idle reloads the 100MB index → a few seconds cold start).
Set `min_machines_running = 1` to keep it always warm.

**Index size watch:** `index.npz` is ~100MB, right at GitHub's per-file limit. If it
grows past 100MB, move it to object storage and have the app pull it at boot
(set `INDEX_PATH` to a downloaded path) instead of baking it into the image.
