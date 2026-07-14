# ReachBot frontend (Next.js + shadcn/ui)

React chat UI for ReachBot. Talks **only** to its own same-origin `/api/*` proxy
routes, which forward to the FastAPI backend (`../backend`). The backend URL and
auth cookie stay server-side; the browser never sees them.

## Local development

1. Start the backend first (see `../backend/README.md`) — it serves on `:8000`.
2. Configure + run the frontend:

   ```bash
   cp .env.example .env.local     # BACKEND_URL=http://127.0.0.1:8000
   npm install
   npm run dev                    # http://localhost:3000
   ```

## How it works

- `app/page.tsx` — client page: password gate → chat thread → streaming answers.
- `app/api/chat/route.ts` — proxies `POST /chat` to FastAPI, streams the SSE
  response straight back (`sources` event, then `token` events, then `done`).
- `app/api/login|logout|session/route.ts` — auth: forwards the password to the
  backend, re-issues its signed token as a first-party httpOnly cookie.
- `lib/use-chat.ts` — parses the SSE stream and appends tokens live.
- `lib/resource-types.ts` — the 5 resource types (article/report/contact/ama/deal)
  → icon + accent color. The backend classifies each hit; this maps it to a UI
  affordance. **Keep this in sync with `backend/resource_types.py`.**

## Deploy (Vercel)

- Import `frontend/` as the project root.
- Set env var `BACKEND_URL` = your Fly.io backend URL (e.g.
  `https://reachbot-backend.fly.dev`).
- Deploy. The backend's `ALLOWED_ORIGIN` must be set to this Vercel URL.
