# Putting ReachBot on Slack — options & process

Goal: let people ask ReachBot questions from Slack instead of (or in addition to)
the web app — possibly for Reach's portfolio companies.

The **brain doesn't change**: it's the same `retrieve()` + Gemini answer the backend
(`backend/rag.py`) already does. What changes is the *surface* (how users talk to it)
and the *hosting* (where the code that answers Slack lives).

---

## The two questions that decide everything

**1. Who uses it?**
- **Just Reach's own Slack workspace** → small, do it in ~a day.
- **Portfolio companies, in their own Slack workspaces** → much bigger (multi-tenant
  OAuth, hosting, Slack review). See "Distribution" below.

**2. How do users invoke it?**
- **Slash command** — `/reachbot how do I price my product?` (discoverable, explicit)
- **@-mention** — `@ReachBot how do I…` in a channel, replies in a thread (conversational)
- **DM** — private 1:1 chat with the bot (good for founders asking sensitive things)

You can support all three; they're just different event handlers.

---

## How a Slack bot actually works

A Slack app is your code + a set of permissions ("scopes"). When someone triggers it,
Slack delivers an event to your code, and your code replies via Slack's API. Two ways
your code can receive events:

- **Socket Mode** — your app opens a WebSocket *out* to Slack. **No public URL needed.**
  Perfect for an internal app; simplest to host. *Cannot* be publicly distributed.
- **HTTP Request URL** — Slack POSTs events to a public HTTPS endpoint you host.
  Required for distributing the app to other workspaces.

Use **Slack Bolt for Python** (`slack_bolt`) — it handles all the plumbing and pairs
cleanly with the existing Python code.

---

## Option A — Internal Reach Slack app (recommended first step)

**What it is:** one bot in Reach's workspace. Anyone at Reach types `/reachbot …` or
@-mentions it and gets an answer with source links, same as the web app.

**Build outline (~1 day):**
1. The shared brain already lives in `backend/rag.py` (`load_index()`, `retrieve()`,
   `generate_stream()`) — import it, or have the Slack bot call the backend's `/chat`.
2. Write `slack_bot.py` using Bolt in **Socket Mode**:
   ```python
   @app.command("/reachbot")
   def handle(ack, respond, command):
       ack()
       hits = retrieve(command["text"], *INDEX)
       respond(generate(context(hits), command["text"]))
   ```
3. Create the Slack app at api.slack.com/apps → add scopes (`commands`,
   `app_mentions:read`, `chat:write`, `im:history`) → enable Socket Mode → install.
4. Host the process somewhere always-on (it needs `index.npz` + `GEMINI_API_KEY`):
   a cheap VM, Render/Fly.io/Railway, or Google Cloud Run. Bundle `index.npz` or
   pull it from the repo on startup so it stays in sync with the weekly refresh.

**Cost/effort:** low. No public URL, no OAuth, no database.

---

## Option B — Distribute to portfolio companies

Two sub-paths, very different in effort:

### B1. Just share the web app (zero extra work)
The web app is already a shareable URL. Send portfolio companies the link
(optionally behind the existing password gate). This is the **80/20** — no Slack
work at all, works on any device. Worth doing first regardless.

### B2. A real distributed Slack app (biggest lift)
Portfolio companies install ReachBot into *their own* Slack workspaces.

**What it requires:**
- **HTTP endpoints** (not Socket Mode) on reliable public hosting.
- **OAuth "Add to Slack" flow** + a **datastore** for each workspace's install token
  (multi-tenant).
- **Slack app review / distribution:** either a direct install link for an approved
  set of companies, or full **App Directory** listing (a review process) for public
  discovery.
- **Ops ownership:** you're now running a service other companies depend on — uptime,
  support, and a security/data posture (what each workspace can query).

**Good news:** the *data* is the same ReachIn knowledge base for everyone (it's the
founder resource hub), so there's no per-company data isolation to build — the
complexity is purely Slack distribution + hosting, not the content.

**Effort:** ~1–2 weeks to build + ongoing maintenance.

---

## Recommendation

1. **Now:** ship **Option A** (internal Reach Slack app) — high value, ~a day, reuses
   the existing brain.
2. **For portfolio companies:** start with **B1** (share the web app link). Only invest
   in **B2** (distributed Slack app) if founders specifically want it inside their own
   Slack and there's an owner to run it long-term.

## Prerequisite either way
The shared RAG logic already lives in `backend/rag.py` (`load_index` / `retrieve` /
`generate_stream`). The Slack app should reuse it — import the module, or just call the
backend's `/chat` endpoint — so the Slack and web surfaces never drift.
