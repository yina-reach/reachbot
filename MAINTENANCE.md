# ReachBot — Maintenance & Handoff Guide

Everything a new maintainer needs to run, update, and hand off ReachBot.
Last updated: 2026-07.

---

## 1. What this project is

Two systems that both sit on top of Reach Capital's **ReachIn** Notion hub:

1. **ReachBot** — a retrieval-augmented (RAG) chatbot that answers portfolio-founder
   questions over ReachIn content + AMA transcripts, with source links. Runs on
   **Streamlit Community Cloud**.
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
| `app.py` | Streamlit chat UI (retrieval + answer) | `GEMINI_API_KEY` |
| `email_agent.py` | ReachIn Connect email intake agent | see §7 |
| `gen_summaries.py` | One-off: backfilled AI summaries onto AMA Notion pages | `NOTION_WRITE_TOKEN`, `GEMINI_API_KEY` |
| `add_transcripts.py` | One-off: added raw-transcript toggles to AMA pages | `NOTION_WRITE_TOKEN` |
| `.github/workflows/weekly.yml` | Monday cron: export → fetch → zoom → rebuild index → commit | repo secrets |
| `.github/workflows/reachin_agent.yml` | Email-agent poll (manual until enabled) | repo secrets |

**The index** (`index.npz`) is a ~72 MB file of vectors + chunks + titles + urls +
categories, committed to the repo. It's what the chatbot loads. GitHub warns it's
over 50 MB — that's fine, it still works.

---

## 3. Secrets (never commit these)

All secrets live in three places, never in code:
- **`.env`** locally (gitignored)
- **Streamlit Cloud** app settings (for the chatbot)
- **GitHub Actions secrets** (for the workflows)

| Secret | Used by | Notes |
|--------|---------|-------|
| `GEMINI_API_KEY` | ingest, app, email agent | Google AI Studio key |
| `NOTION_TOKEN` | export (read) | Notion internal integration, read access to ReachIn |
| `NOTION_WRITE_TOKEN` | email agent, one-off scripts (write) | Notion integration with **write** access |
| `ZOOM_ACCOUNT_ID` / `ZOOM_CLIENT_ID` / `ZOOM_CLIENT_SECRET` | zoom transcripts | Optional; weekly job skips if unset |
| `REACHIN_EMAIL` | email agent | `reachin@reachcapital.com` |
| `REACHIN_EMAIL_APP_PASSWORD` | email agent | Gmail **App Password** (needs 2FA on the account) |
| `TONY_EMAIL` | email agent | approver address |

**Rotating a secret:** update it in all three places (`.env`, Streamlit, GitHub
secrets). Rotate anything that's ever been pasted into chat/email/Slack.

---

## 4. How the chatbot works

1. `ingest.py` splits every `.md` file into ~400-word overlapping chunks, prepends
   the title, and embeds each with Gemini (`gemini-embedding-001`, 3072-dim).
2. `app.py` embeds the user's question, cosine-ranks all chunks, takes the top 25,
   and asks `gemini-2.5-flash` to answer **only** from that context with source links.
3. **Perk routing:** questions about discounts/credits/partnerships are restricted to
   the "Partner Access, Credits, Discounts" content so they don't pull in tangents.

### Updating the chatbot's knowledge
- **Normal:** just edit ReachIn in Notion. The Monday job re-syncs automatically.
- **Manual refresh:** Actions → "Weekly ReachBot Refresh" → Run workflow.
- **After a manual local rebuild:** `python ingest.py`, commit `index.npz`, push,
  then **reboot the Streamlit app** (Manage app → Reboot) to load the new index.

---

## 5. The weekly refresh job

`weekly.yml` runs every Monday 6 AM UTC (and on-demand). Steps: export Notion →
fetch external links → pull Zoom transcripts (if creds set) → rebuild index →
commit `index.npz`. **The Streamlit app auto-redeploys** when the repo changes.

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

**To deploy (currently NOT live):**
1. Add the 5 secrets (§3) to GitHub Actions.
2. Test: Actions → "ReachIn Connect Agent" → Run workflow (after emailing a test item).
3. Enable the schedule: uncomment the `schedule:` block in `reachin_agent.yml`
   (recommend every 30–60 min — repo is private so Actions minutes count).

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
   - **Streamlit Cloud:** the app is tied to the repo owner's GitHub login. The new
     owner reconnects the transferred repo at share.streamlit.io and re-enters the
     app secrets (§3).
   - **GitHub Actions secrets** do NOT transfer — the new owner re-adds all secrets
     (§3) under the new repo's Settings → Secrets and variables → Actions.
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
the same retrieval + Gemini answer as `app.py`, exposed as either a slash command
(`/reachbot ...`) or an @-mention bot. Internal-to-Reach is a small lift; distributing
it to portfolio companies' own workspaces is a bigger one (OAuth, hosting, review).
