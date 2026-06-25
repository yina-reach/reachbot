#!/usr/bin/env python3
"""
Populate AI summaries on Reach Capital "Session Recordings" (AMA) Notion pages
that are missing them, generated from the matching Zoom transcript.

Format matches the existing summaries exactly:
  - bold paragraph blocks as section headers
  - bulleted_list_item blocks underneath

Idempotent: skips any page that already has >= MIN_NOTES note blocks, so re-runs
never double-post.

Secrets come from the environment only (NOTION_WRITE_TOKEN, GEMINI_API_KEY).

Usage:
  python gen_summaries.py --dry-run        # show matches + one sample, NO writes
  python gen_summaries.py --test           # write exactly ONE page, print its URL
  python gen_summaries.py --go [N]         # write all confident matches (optional cap N)
"""
import os, sys, re, glob, time, json
import urllib.request as _ur
import urllib.error

from google import genai

WTOK = os.environ.get("NOTION_WRITE_TOKEN")
GKEY = os.environ.get("GEMINI_API_KEY")
if not WTOK or not GKEY:
    sys.exit("Set NOTION_WRITE_TOKEN and GEMINI_API_KEY in the environment.")

H = {"Authorization": f"Bearer {WTOK}", "Notion-Version": "2022-06-28",
     "Content-Type": "application/json"}
client = genai.Client(api_key=GKEY,
                      http_options=genai.types.HttpOptions(timeout=120_000))  # ms

SESSION_DB = "682f047c-c46b-4b40-b836-269c1758ec6a"
MIN_NOTES = 4          # >= this many note blocks  => already has a summary
MATCH_THRESHOLD = 0.5  # title-token overlap to even consider a transcript
MIN_CONF = 0.66        # overlap required to actually WRITE (high-confidence only)
MIN_WORDS = 300        # transcript must have at least this many words


# ── Notion REST helpers ─────────────────────────────────────────────────────
def _req(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = _ur.Request(url, data=data, headers=H, method=method)
    for attempt in range(5):
        try:
            with _ur.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503) and attempt < 4:
                time.sleep(2 * (attempt + 1)); continue
            raise
        except Exception:
            if attempt < 4:
                time.sleep(2 * (attempt + 1)); continue
            raise


def db_query(db_id):
    rows, cur = [], None
    while True:
        b = {"page_size": 100}
        if cur:
            b["start_cursor"] = cur
        d = _req("POST", f"https://api.notion.com/v1/databases/{db_id}/query", b)
        rows += d["results"]
        if not d.get("has_more"):
            break
        cur = d["next_cursor"]
    return rows


def page_blocks(pid):
    out, cur = [], None
    while True:
        u = f"https://api.notion.com/v1/blocks/{pid}/children?page_size=100"
        if cur:
            u += f"&start_cursor={cur}"
        d = _req("GET", u)
        out += d["results"]
        if not d.get("has_more"):
            break
        cur = d["next_cursor"]
    return out


TEXTUAL = ("paragraph", "bulleted_list_item", "numbered_list_item",
           "heading_1", "heading_2", "heading_3", "toggle")


def note_count(pid):
    n = 0
    for b in page_blocks(pid):
        t = b["type"]
        if t in TEXTUAL:
            txt = "".join(x.get("plain_text", "") for x in b.get(t, {}).get("rich_text", []))
            if len(txt.strip()) > 3:
                n += 1
    return n


def title_of(p):
    for pr in p["properties"].values():
        if pr["type"] == "title":
            return "".join(t["plain_text"] for t in pr["title"]) or "untitled"
    return "untitled"


def append_blocks(pid, blocks):
    # Notion accepts <=100 children per call
    for i in range(0, len(blocks), 100):
        _req("PATCH", f"https://api.notion.com/v1/blocks/{pid}/children",
             {"children": blocks[i:i + 100]})
        time.sleep(0.34)


# ── Transcript matching ─────────────────────────────────────────────────────
STOP = {"the", "and", "for", "reach", "ama", "with", "how", "you", "your", "from"}


def toks(s):
    s = s.lower().replace("&", " ").replace("’", "").replace("'", "")
    return set(w for w in re.findall(r"[a-z0-9]+", s) if len(w) > 2 and w not in STOP)


def load_transcripts():
    out = []
    for f in glob.glob("transcripts/*.md"):
        if os.path.basename(f).startswith("_"):
            continue
        raw = open(f, encoding="utf-8", errors="ignore").read()
        body = re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.DOTALL)
        out.append((f, toks(os.path.basename(f)), body, len(body.split())))
    return out


def best_match(title, transcripts):
    tt = toks(title)
    if not tt:
        return None
    best, score = None, 0.0
    for f, ft, body, wc in transcripts:
        ov = len(tt & ft) / len(tt)
        if ov > score:
            score, best = ov, (f, body, wc)
    if best and score >= MATCH_THRESHOLD and best[2] >= MIN_WORDS:
        return (best[0], best[1], best[2], score)  # (path, body, wordcount, score)
    return None


# ── Summary generation ──────────────────────────────────────────────────────
SUM_PROMPT = """You are writing structured notes for a Reach Capital AMA / session \
recording titled "{title}", for portfolio founders who could not attend.

Summarize the transcript below into the SAME format Reach uses for its other AMA notes:
- Break the content into 4-8 thematic SECTIONS.
- Each section begins with a short header line prefixed with "## " (3-7 words).
- Under each header, 3-6 concise bullet points, each prefixed with "- ".
- Capture concrete frameworks, advice, numbers, examples, and quotable takeaways.
- Be specific and practical; avoid generic filler. Do not invent anything not in the transcript.
- Output ONLY the sections. No title, no preamble, no closing remarks.

Transcript:
{transcript}
"""


def generate_summary(title, transcript):
    words = transcript.split()
    if len(words) > 40000:
        transcript = " ".join(words[:40000])
    prompt = SUM_PROMPT.format(title=title, transcript=transcript)
    for model in ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-flash"):
        try:
            r = client.models.generate_content(model=model, contents=prompt)
            return r.text
        except Exception as e:
            msg = str(e)
            if "503" in msg or "UNAVAILABLE" in msg:
                continue
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                m = re.search(r"retry[^']*'(\d+)s'", msg)
                time.sleep(int(m.group(1)) if m else 20); continue
            if any(k in msg.lower() for k in ("timeout", "timed out", "deadline",
                   "connection", "disconnected", "remoteprotocol")):
                time.sleep(5); continue   # transient network stall — try next
            raise
    raise RuntimeError("Gemini unavailable")


def _rich(text):
    """Split **bold** spans into Notion rich_text runs."""
    runs, i = [], 0
    for m in re.finditer(r"\*\*(.+?)\*\*", text):
        if m.start() > i:
            runs.append({"type": "text", "text": {"content": text[i:m.start()]}})
        runs.append({"type": "text", "text": {"content": m.group(1)},
                     "annotations": {"bold": True}})
        i = m.end()
    if i < len(text):
        runs.append({"type": "text", "text": {"content": text[i:]}})
    return runs or [{"type": "text", "text": {"content": text}}]


def to_blocks(md):
    blocks = []
    for line in md.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("## "):
            txt = s[3:].strip().strip("*")
            blocks.append({"object": "block", "type": "paragraph",
                           "paragraph": {"rich_text": [{"type": "text",
                               "text": {"content": txt},
                               "annotations": {"bold": True}}]}})
        elif s.startswith(("- ", "* ")):
            blocks.append({"object": "block", "type": "bulleted_list_item",
                           "bulleted_list_item": {"rich_text": _rich(s[2:].strip())}})
        elif re.match(r"^\d+\.\s", s):
            blocks.append({"object": "block", "type": "numbered_list_item",
                           "numbered_list_item": {"rich_text": _rich(re.sub(r'^\d+\.\s', '', s))}})
        else:
            blocks.append({"object": "block", "type": "paragraph",
                           "paragraph": {"rich_text": _rich(s)}})
    return blocks


# ── Driver ──────────────────────────────────────────────────────────────────
def build_worklist():
    transcripts = load_transcripts()
    rows = db_query(SESSION_DB)
    candidates = []    # (title, pid, path, body, wc, score)
    no_transcript = [] # (title, pid)
    for p in rows:
        pid, ti = p["id"], title_of(p)
        if note_count(pid) >= MIN_NOTES:
            continue   # already has a summary
        m = best_match(ti, transcripts)
        if m:
            candidates.append((ti, pid, m[0], m[1], m[2], m[3]))
        else:
            no_transcript.append((ti, pid))

    # Dedupe: each transcript file may only feed its single highest-overlap page.
    # Losers (a page whose only match is a transcript already claimed) are dropped
    # to the review pile — they almost always lack a real transcript of their own.
    best_for = {}      # transcript_path -> best candidate
    for c in candidates:
        path, score = c[2], c[5]
        if path not in best_for or score > best_for[path][5]:
            best_for[path] = c
    winners = set(id(c) for c in best_for.values())

    work, review = [], []
    for c in candidates:
        ti, pid, path, body, wc, score = c
        if id(c) in winners and score >= MIN_CONF:
            work.append((ti, pid, path, body))
        else:
            review.append((ti, score, os.path.basename(path)))
    return work, no_transcript, review


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--dry-run"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else None

    print("Scanning Session Recordings + matching transcripts...")
    work, no_t, review = build_worklist()
    print(f"\nHigh-confidence, deduped (will write): {len(work)}")
    print(f"Needs manual review (dupe/low-confidence): {len(review)}")
    print(f"No transcript at all: {len(no_t)}")

    if mode == "--dry-run":
        print("\n=== matches (title  <-  transcript) ===")
        for ti, pid, tp, _ in work:
            print(f"  {ti[:50]:50s}  <-  {os.path.basename(tp)}")
        if work:
            ti, pid, tp, body = work[0]
            print(f"\n=== SAMPLE summary for: {ti} ===\n")
            print(generate_summary(ti, body))
        return

    targets = work[:1] if mode == "--test" else (work[:cap] if cap else work)
    print(f"\nWriting summaries to {len(targets)} page(s)...\n")
    done = 0
    for ti, pid, tp, body in targets:
        # idempotency re-check right before writing
        if note_count(pid) >= MIN_NOTES:
            print(f"  skip (now has notes): {ti}")
            continue
        try:
            summary = generate_summary(ti, body)
            blocks = to_blocks(summary)
            if len(blocks) < 3:
                print(f"  skip (thin summary): {ti}")
                continue
            append_blocks(pid, blocks)
            done += 1
            url = f"https://www.notion.so/{pid.replace('-', '')}"
            print(f"  ✓ {ti[:55]}  ({len(blocks)} blocks)\n     {url}")
        except Exception as e:
            print(f"  ! FAILED {ti}: {e}")
        time.sleep(0.5)
    print(f"\nDone. Wrote summaries to {done} page(s).")


if __name__ == "__main__":
    main()
