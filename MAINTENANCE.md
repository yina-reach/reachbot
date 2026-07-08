# ReachBot — Maintenance & Handoff Guide

Everything a new maintainer needs to run, update, and hand off ReachBot.
Last updated: 2026-07.

---

## 1. What this project is

Two systems that both sit on top of Reach Capital's **ReachIn** Notion hub:

1. **ReachBot** — a retrieval-augmented (RAG) chatbot that answers portfolio-founder
   questions over ReachIn content + AMA transcripts, with source links. A
   **Next.js/shadcn frontend on Vercel** talks to a **FastAPI backend on Fly.io**.
2. **ReachIn Connect** — an email agent. Someone emails a PDF/URL to a dedicated
   inbox; it classifies the item into the right Notion database, emails Tony a
   proposal, and files it on approval. Runs on **GitHub Actions** (a cron poller).

Nobody edits the bot's data directly — Reach edits **Notion**, and a weekly job
re-syncs everything.

---

## 2. The moving parts

| File | What it does | Needs |
|------|--------------|-------|
| `reachin_export.py` | Notion API → `reachin_md/*.md` (pages + all database rows) | `NOTION_TOKEN` |
| `fetch_external_links.py` | Scrapes external article URLs found in Notion pages | `trafilatura` |
| `zoom_transcripts.py` | Zoom API → `transcripts/*.md` | `ZOOM_*` |
| `ingest.py` | Chunks markdown → embeds with Gemini → `index.npz` | `GEMINI_API_KEY` |
| `backend/` | FastAPI RAG service (retrieval + streaming answer); deploys to Fly.io | `GEMINI_API_KEY`, `ACCESS_PASSWORD`, `SESSION_SECRET`, `ALLOWED_ORIGIN` |
| `frontend/` | Next.js + shadcn chat UI; deploys to Vercel | `BACKEND_URL` |
| `email_agent.py` | ReachIn Connect email intake agent | see §7 |
| `gen_summaries.py` | One-off: backfilled AI summaries onto AMA Notion pages | `NOTION_WRITE_TOKEN`, `GEMINI_API_KEY` |
| `add_transcripts.py` | One-off: added raw-transcript toggles to AMA pages | `NOTION_WRITE_TOKEN` |
| `.github/workflows/weekly.yml` | Monday cron: export → fetch → zoom → rebuild index → commit | repo secrets |
| `.github/workflows/reachin_agent.yml` | Email-agent poll (manual until enabled) | repo secrets |

**The index** (`index.npz`) is a ~100 MB file of vectors + chunks + titles + urls +
categories, committed to the repo. The backend loads it into memory; the Fly image
bakes it in (so it's never publicly downloadable — important, it contains
portfolio-confidential partner-deal contacts + claim links). It's near GitHub's 100 MB
per-file limit; if it grows past, move it to object storage and have the backend pull
it at boot (`INDEX_PATH`).

---

## 3. Secrets (never commit these)

All secrets live in these places, never in code:
- **`.env`** locally (gitignored) — for ingest + local backend
- **Fly.io secrets** (`fly secrets set`) — for the deployed backend
- **Vercel env vars** — for the deployed frontend (`BACKEND_URL`)
- **GitHub Actions secrets** — for the workflows (incl. `FLY_API_TOKEN` for weekly redeploy)

| Secret | Used by | Notes |
|--------|---------|-------|
| `GEMINI_API_KEY` | ingest, backend, email agent | Google AI Studio key |
| `ACCESS_PASSWORD` / `SESSION_SECRET` | backend gate | password + cookie-signing secret |
| `ALLOWED_ORIGIN` | backend CORS | the Vercel frontend URL |
| `BACKEND_URL` | frontend | the Fly backend URL |
| `FLY_API_TOKEN` | weekly workflow | lets the Monday job redeploy the backend (`fly tokens create deploy`) |
| `NOTION_TOKEN` | export (read) | Notion internal integration, read access to ReachIn |
| `NOTION_WRITE_TOKEN` | email agent, one-off scripts (write) | Notion integration with **write** access |
| `ZOOM_ACCOUNT_ID` / `ZOOM_CLIENT_ID` / `ZOOM_CLIENT_SECRET` | zoom transcripts | Optional; weekly job skips if unset |
| `REACHIN_EMAIL` | email agent | `reachin@reachcapital.com` |
| `REACHIN_EMAIL_APP_PASSWORD` | email agent | Gmail **App Password** (needs 2FA on the account) |
| `TONY_EMAIL` | email agent | approver address |

**Rotating a secret:** update it wherever it's used (`.env`, Fly secrets, Vercel env,
GitHub secrets). Rotate anything that's ever been pasted into chat/email/Slack.

---

## 4. How the chatbot works

1. `ingest.py` splits every `.md` file into ~400-word overlapping chunks, prepends
   the title, and embeds each with Gemini (`gemini-embedding-001`, 3072-dim).
2. The backend (`backend/rag.py`) embeds the user's question, cosine-ranks all chunks,
   takes the top 25, and asks `gemini-2.5-flash` to answer **only** from that context
   with source links — streamed back token-by-token.
3. **Perk routing:** questions about discounts/credits/partnerships are restricted to
   the "Partner Access, Credits, Discounts" content so they don't pull in tangents.

### Updating the chatbot's knowledge
- **Normal:** just edit ReachIn in Notion. The Monday job re-syncs automatically.
- **Manual refresh:** Actions → "Weekly ReachBot Refresh" → Run workflow.
- **After a manual local rebuild:** `python ingest.py`, commit `index.npz`, push,
  then **redeploy the backend** (`fly deploy` from repo root) so it reloads the new
  index — the index is baked into the Fly image, so a redeploy is what picks it up.

---

## 5. The weekly refresh job

`weekly.yml` runs every Monday 6 AM UTC (and on-demand). Steps: export Notion →
fetch external links → pull Zoom transcripts (if creds set) → rebuild index →
commit `index.npz` → **`fly deploy` to redeploy the backend** with the fresh index
(needs the `FLY_API_TOKEN` repo secret; the step is skipped if it's unset).

**If it fails:** Actions tab → open the red run → read the failing step's log.
Common causes are in §8.

---

## 6. Adding / changing Notion databases

If Reach adds a new ReachIn database or renames fields:
- **Export:** `reachin_export.py` auto-discovers databases via search — usually no
  change needed. Verify new rows show up in `reachin_md/` after a run.
- **Email agent:** add the new database to the `DATABASES` dict in `email_agent.py`
  (name → id + one-line purpose). The agent reads each DB's live schema/options
  automatically, so only the registry entry is needed.

---

## 7. The email agent (ReachIn Connect)

**Flow:** org member emails a PDF/URL to `reachin@reachcapital.com` → agent extracts
content → Gemini picks the database + fills fields (using only existing options) →
emails Tony a proposal → Tony replies `APPROVE` / `REJECT` / `USE: <db>` / `EDIT`
+ field lines → agent files the Notion row. State lives in Gmail labels
(`ReachInPending/Filed/Rejected/Ignored/Processed`).

**Run modes:**
- `python email_agent.py --classify <url|file.pdf>` — test the brain, no email/write
- `python email_agent.py --poll` — one full intake+approval cycle

**Deployment status: LIVE.** Secrets are set and `reachin_agent.yml` runs on an
**hourly** cron (`0 * * * *`). Kept at 60 min so Actions minutes stay within the
free tier alongside the weekly rebuild; tighten the cron if you upgrade the plan.
To pause it, comment the `schedule:` block back out.

**Safety:** only `@reachcapital.com` senders are treated as submissions; only Tony's
replies can write to Notion; invalid select/multi-select values are dropped.

---

## 8. Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| Weekly job fails on "Fetch external article links" | `trafilatura` missing — it's installed inline in that step; if it moves, keep the `pip install trafilatura` line |
| Bot answers "no info" for things that exist | Index stale → run the weekly job; or the content is a file attachment (PDFs/decks aren't indexed, only their titles/links) |
| Bot shows a `.md` filename as a link | Old index — the parser fix removed this; rebuild the index |
| "Gemini daily quota exhausted" in the app | Free-tier limit — enable billing on the Google AI project, or wait for reset |
| Notion export 401 / empty | `NOTION_TOKEN` expired or integration removed from ReachIn — regenerate + re-share |
| Email agent won't log in (IMAP/SMTP) | Not an App Password, or 2FA off on the account — see §7 / regenerate app password |
| `git index.lock ... Operation timed out` locally | iCloud sync stall on the Documents folder — `rm -f .git/index.lock` and retry |

---

## 9. Handing off the GitHub repo

The repo is currently under a **personal GitHub account**. To hand it to Reach:

**Best option — transfer into a Reach Capital GitHub org** (or the boss's account):
1. Create/choose the destination: a Reach org (github.com/organizations/new) is
   ideal, or the boss's personal account.
2. Repo → **Settings → General → Danger Zone → Transfer ownership** → enter the
   destination org/user. The new owner accepts.
3. **Re-point the deployments** (they don't move automatically):
   - **Fly.io (backend):** the app lives in a Fly account. Either transfer the Fly app
     to a Reach-owned Fly org, or redeploy from the new repo owner's account; re-set the
     backend secrets (§3) via `fly secrets set`.
   - **Vercel (frontend):** redeploy `frontend/` from the new owner's Vercel account and
     set `BACKEND_URL`. Update the backend's `ALLOWED_ORIGIN` to the new Vercel URL.
   - **GitHub Actions secrets** do NOT transfer — the new owner re-adds all secrets
     (§3, incl. `FLY_API_TOKEN`) under the new repo's Settings → Secrets → Actions.
4. **Rotate every credential** after handoff (§3) so the departing intern's copies
   stop working: Gemini key, both Notion tokens, Zoom creds, the Gmail app password.
5. Update the API integrations' ownership where possible (Notion integration, Google
   AI project, Zoom app) to a Reach-owned account so they don't die when the intern's
   accounts are deprovisioned.

> ⚠️ The biggest handoff risk is **credentials tied to a personal account** (Gemini
> key on a personal Google account, Notion integration owned by the intern). Recreate
> these under Reach-owned accounts before the intern leaves, or the bot breaks later.

---

## 10. Putting the bot on Slack — options

See `SLACK_OPTIONS.md` for the full analysis. Short version: a Slack app that wraps
the same retrieval + Gemini answer as the backend, exposed as either a slash command
(`/reachbot ...`) or an @-mention bot. Internal-to-Reach is a small lift; distributing
it to portfolio companies' own workspaces is a bigger one (OAuth, hosting, review).
