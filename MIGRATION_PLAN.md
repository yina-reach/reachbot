# ReachBot: Streamlit → Next.js + shadcn/ui Migration Plan

**Goal:** Replace the Streamlit frontend with a React (Next.js App Router) + shadcn/ui
interface, while keeping the existing Python RAG logic (Gemini embeddings, NumPy
retrieval over `index.npz`, Gemini chat) behind a FastAPI service.

**Decisions locked in:**
- Architecture: **Next.js frontend + FastAPI Python backend**
- Design: **Clean shadcn redesign** (shadcn default design language, dark mode)
- The 100MB `index.npz` and `retrieve()`/`generate()` logic stay in Python — reused nearly verbatim.

---

## 1. Target architecture

```
┌─────────────────────────────┐        ┌──────────────────────────────────┐
│  Next.js app (React)        │  HTTP  │  FastAPI service (Python)        │
│  - shadcn/ui components     │ ─────► │  - loads index.npz once at boot  │
│  - Tailwind theming         │  POST  │  - retrieve()  (NumPy cosine)    │
│  - streaming chat UI        │ /chat  │  - generate()  (Gemini chat)     │
│  - password gate (client)   │ ◄───── │  - streams tokens back (SSE)     │
└─────────────────────────────┘        └──────────────────────────────────┘
        Vercel / Node                       Container (Fly/Render/Cloud Run)
```

Why split this way: the index is 100MB and retrieval is NumPy. Loading that per
serverless cold-start (option B) is slow and costly; rewriting cosine search + the
perk-filtering heuristics in TS (option C) is throwaway work. A long-lived FastAPI
process loads the index **once** and reuses it — this maps directly onto the current
`@st.cache_resource load_index()` pattern.

---

## 2. Repository layout (after migration)

```
reachbot/
├── backend/                     # NEW — Python RAG service
│   ├── main.py                  # FastAPI app: /chat (SSE), /health
│   ├── rag.py                   # retrieve() + generate() lifted from app.py
│   ├── index.npz                # (moved here, or path via env; stays git-tracked)
│   └── requirements.txt         # fastapi, uvicorn, google-genai, numpy, sse-starlette
│
├── frontend/                    # NEW — Next.js app
│   ├── app/
│   │   ├── page.tsx             # main chat page
│   │   ├── layout.tsx           # root, fonts, theme provider
│   │   ├── globals.css          # tailwind + shadcn tokens
│   │   └── api/chat/route.ts    # thin proxy → FastAPI (keeps API key server-side)
│   ├── components/
│   │   ├── ui/                  # shadcn primitives (button, card, input, scroll-area…)
│   │   ├── chat-thread.tsx      # message list
│   │   ├── message.tsx          # user bubble + assistant card (markdown render)
│   │   ├── resource-card.tsx    # typed resource citation (5-type system)
│   │   ├── suggestion-chips.tsx # welcome chips
│   │   ├── welcome.tsx          # hero / empty state
│   │   ├── chat-input.tsx       # composer
│   │   └── password-gate.tsx    # access gate
│   ├── lib/
│   │   ├── resource-types.ts    # RESOURCE_TYPES + CATEGORY_TYPE (ported from memory)
│   │   └── markdown.tsx         # markdown → React (replaces md_to_html)
│   ├── components.json          # shadcn config
│   ├── tailwind.config.ts
│   └── package.json
│
├── reachin_export.py            # UNCHANGED (ingest pipeline)
├── zoom_transcripts.py          # UNCHANGED
├── ingest.py                    # UNCHANGED (still writes index.npz)
├── app.py                       # KEPT during transition; removed once React is live
├── .github/workflows/weekly.yml # UPDATED: write index to backend/, redeploy backend
└── MIGRATION_PLAN.md            # this file
```

---

## 3. Backend (FastAPI) — what moves and how

Lift **verbatim** from `app.py` into `backend/rag.py`:
- `load_index()` → module-level singleton loaded at import/startup (replaces `@st.cache_resource`).
- `MIN_BODY_CHARS`, `PERK_CATEGORY`, `PERK_KEYWORDS`, `_is_perk_query()`, `retrieve()` — unchanged logic.
- `generate()` — unchanged, **except** convert it to **stream** (`generate_content_stream`)
  so the UI can render tokens live. Keep the model-fallback + 429/quota handling.

`backend/main.py` endpoints:
- `POST /chat` → body `{ "question": str }`. Runs `retrieve()`, builds context, then
  **streams** the answer as Server-Sent Events. Also emits the structured `hits`
  (title/url/category → resource type) as a first SSE event so the UI can render
  resource cards independent of the model's inline links.
- `GET /health` → `{ "ok": true, "chunks": N }` for readiness checks.

Config via env: `GEMINI_API_KEY`, `INDEX_PATH` (default `index.npz`),
`ACCESS_PASSWORD` (validated server-side — see §6), `ALLOWED_ORIGIN` (CORS).

CORS: allow only the frontend origin.

---

## 4. Frontend (Next.js + shadcn)

**Init:** `create-next-app` (TS, App Router, Tailwind) → `npx shadcn@latest init` →
add `button card input scroll-area avatar skeleton badge sonner`.

**Data flow:** `app/api/chat/route.ts` is a thin server-side proxy to FastAPI. The
browser never talks to FastAPI directly — this keeps the backend URL/any shared secret
server-side and sidesteps CORS. The route streams the SSE response straight through to
the client.

**Components (clean shadcn design language):**
- `welcome.tsx` — empty state: title, one-line subtitle, `suggestion-chips`.
- `suggestion-chips.tsx` — shadcn `Button variant="outline"` pills; clicking submits.
- `chat-thread.tsx` — `ScrollArea` of messages, auto-scroll to bottom.
- `message.tsx` — user = right-aligned bubble; assistant = `Card` with markdown body +
  a typing skeleton while streaming.
- `resource-card.tsx` — renders each retrieved hit as a typed citation using the
  5-type system (§5).
- `chat-input.tsx` — `Textarea` + send `Button`; Enter-to-send, Shift+Enter newline.
- `password-gate.tsx` — see §6.

**Markdown:** replace the regex `md_to_html` with `react-markdown` + `remark-gfm`
(safe, no `dangerouslySetInnerHTML`), styled with `@tailwindcss/typography` (`prose`).
Links open in new tab.

**Streaming:** consume the SSE stream from `/api/chat`; append tokens to the active
assistant message as they arrive.

---

## 5. Resource-type system (port from memory, not from current app.py)

⚠️ **Important discrepancy:** the `reachbot-resource-type-system` memory describes a
`RESOURCE_TYPES` + `CATEGORY_TYPE` registry in `app.py`, but the `app.py` currently on
disk does **not** contain it (it's the earlier version). The *data* it depends on —
per-chunk `categories` — **is** present in `index.npz`. So we rebuild the registry
fresh in TypeScript from the memory's spec:

`frontend/lib/resource-types.ts`:
- 5 types with fixed accent + icon (lucide):
  - `article` `#7EB6FF` (file) · `report` `#B9A5FF` (bar-chart) ·
    `contact` `#4FD8A8` (user) · `ama` `#FFC94D` (mic) · `deal` `#FF8FC0` (tag)
- `CATEGORY_TYPE` map: `Session Recordings→ama`; `Reach Advisors`/`Consultants &
  Coaches`/`Media Contacts→contact`; `Partner Access, Credits, Discounts→deal`.
- Title-keyword fallback for report vs article; empty category (~44%, external links)
  → `article`.

This drives resource cards, chip accents, and inline-citation accents — mirrors the
original single-registry approach.

---

## 6. Password gate

Current gate is client-visible logic in Streamlit. In React we do it properly:
- A server route `POST /api/login` compares against `ACCESS_PASSWORD` (env, server-side)
  and sets an httpOnly cookie / short-lived signed token.
- Middleware (or a check in `/api/chat`) rejects unauthenticated chat requests.
- `password-gate.tsx` shows the branded lock screen until authed.

This is strictly better than the Streamlit version (password no longer shipped to client).
If you'd rather keep it dead-simple, we can gate only in the proxy route — I'll confirm
before implementing.

---

## 7. Deployment changes

**Frontend → Vercel:** connect `frontend/`, set `BACKEND_URL` + `ACCESS_PASSWORD` env.

**Backend → container host** (Fly.io / Render / Cloud Run): Dockerfile runs
`uvicorn main:app`. Ships `index.npz` in the image **or** pulls it at boot. Set
`GEMINI_API_KEY`, `ACCESS_PASSWORD`, `ALLOWED_ORIGIN`.

**`weekly.yml` changes:**
- Still runs `reachin_export.py` → `ingest.py` → produces `index.npz`.
- Write/commit index to `backend/index.npz` (path update only).
- Add a final step to **redeploy the backend** so it reloads the new index
  (deploy hook / `flyctl deploy` / trigger). The current job just commits the index and
  lets Streamlit Cloud auto-pull; the backend needs an explicit reload trigger.

**Streamlit Cloud:** decommission after the React app is verified. Keep `app.py` until then.

⚠️ **100MB index + git:** `index.npz` is 100MB and already committed weekly. Confirm
it's within GitHub's 100MB file limit (it's right at the edge — 104,728,396 bytes ≈
99.9MB, so it currently squeaks under). If it grows past 100MB, we must move it to Git
LFS or object storage and have the backend pull it at boot. Flag to watch.

---

## 8. Migration steps (execution order)

1. **Backend:** create `backend/` with `rag.py` (lifted logic, `generate()` → streaming)
   + `main.py` (FastAPI, `/chat` SSE, `/health`) + `requirements.txt`. Run locally
   against the existing `index.npz`; verify `/health` and a curl to `/chat`.
2. **Frontend scaffold:** `create-next-app` + shadcn init + add primitives.
3. **Core chat:** `page.tsx`, thread, message, input, proxy route → working
   end-to-end streaming chat against local backend.
4. **Resource types + welcome/chips:** port `resource-types.ts`, resource cards,
   welcome hero, suggestion chips.
5. **Markdown + polish:** `react-markdown` styling, auto-scroll, loading states,
   error/quota messages (reuse the daily-quota copy from `generate()`).
6. **Password gate.**
7. **Deploy:** backend container + Vercel; wire env; smoke test.
8. **Update `weekly.yml`** (index path + backend redeploy trigger).
9. **Verify** end-to-end on deployed URLs, then remove `app.py` + streamlit dep.

---

## 9. What stays identical (de-risks the migration)

- The entire ingest pipeline (`reachin_export.py`, `zoom_transcripts.py`, `ingest.py`)
  and the `index.npz` format — **untouched**.
- Retrieval semantics: TOP_K=25, MIN_BODY_CHARS=120, perk-query filtering, thin-chunk
  skipping — **identical** (same Python).
- The Gemini system prompt, model fallback chain, and quota/429 handling — **identical**.

## 10. Decisions (confirmed 2026-07-07)

1. **Backend host: Fly.io** — long-lived container holds the 100MB index in memory;
   single Dockerfile, `flyctl deploy` as the weekly redeploy trigger.
2. **Password gate: proper** — server-side check, httpOnly signed cookie; password
   never ships to the client.
3. **Streaming: yes** — `generate()` → `generate_content_stream`, SSE to the UI.
4. **Branding: fully neutral shadcn** — no gradient wordmark / branded accents. Resource
   *type* icons+colors kept only as functional affordances (distinguishing source kinds),
   not as brand styling.
```
