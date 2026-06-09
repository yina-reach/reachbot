# ReachBot

A free/near-free AI assistant over Reach Capital's ReachIn resources. Founders ask
questions in plain language; ReachBot answers from the ReachIn content and links the
primary source (Notion page, AMA recording, etc.). Reach only ever updates Notion —
ReachBot re-scrapes weekly on its own.

**Cost:** hosting is free; the only spend is the Gemini API key, ~$0–2/month.

## Stack
- `reachin_export.py` — pulls all ReachIn Notion pages to `reachin_md/` (markdown + source links)
- `ingest.py` — chunks + embeds the content into `index.npz` (Gemini embeddings)
- `app.py` — Streamlit chat UI, answers with Gemini Flash + citations
- `.github/workflows/weekly.yml` — re-runs the export + re-embed every Monday (free GitHub Actions cron)

## One-time setup
1. **Notion integration:** create one at https://www.notion.so/my-integrations, copy
   the secret, and add it to the ReachIn top page (Connections menu).
2. **Gemini API key:** https://aistudio.google.com/apikey (separate from any Gemini
   subscription — this is pay-as-you-go, but cents-scale for this use).
3. **Run locally to test:**
   ```
   pip install -r requirements.txt
   export NOTION_TOKEN="secret_..."
   export GEMINI_API_KEY="..."
   python reachin_export.py     # -> reachin_md/
   python ingest.py             # -> index.npz
   streamlit run app.py         # opens the chat locally
   ```
4. **Add AMA transcripts** (optional but high value): put each transcript as a
   markdown file in `transcripts/` with a header:
   ```
   ---
   title: AMA with <speaker> — <topic>
   source_url: <link to the Zoom recording>
   ---
   <transcript text>
   ```
   Re-run `ingest.py`.

## Deploy free (so founders can use it)
1. Push this folder to a private GitHub repo.
2. Go to https://share.streamlit.io, connect the repo, point it at `app.py`.
3. In the app's **Secrets**, add:
   ```
   GEMINI_API_KEY = "..."
   ACCESS_PASSWORD = "reachfounders"   # optional, keeps it Reach-only
   ```
4. You get a public URL to share with founders. Set a password if you want it gated.

## Automatic weekly refresh
In the GitHub repo settings → Secrets → Actions, add `NOTION_TOKEN` and
`GEMINI_API_KEY`. The workflow re-exports Notion, rebuilds the index, and commits it
every Monday; Streamlit redeploys automatically. You can also trigger it by hand from
the Actions tab.

## Swapping the model
`CHAT_MODEL` in `app.py` is the only thing to change to use a different/cheaper/
stronger model. Embeddings model is `EMBED_MODEL` in both `ingest.py` and `app.py`
(keep them matched).
