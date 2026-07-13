#!/usr/bin/env python3
"""
Transcribe AMA recordings that have a directly-downloadable audio/video file but
no transcript yet, then attach BOTH a "Transcript" toggle and an AI summary to
the Notion page (matching how the other AMAs look).

Only handles recordings we can actually fetch (e.g. public Google Drive files).
Zoom share links (passcode-gated) and pages with no recording are skipped.

Secrets (env): NOTION_WRITE_TOKEN, GEMINI_API_KEY

  python transcribe_recordings.py --dry-run   # list what it would transcribe
  python transcribe_recordings.py --go [N]    # transcribe + attach (optional cap N)
"""
import os, re, sys, json, time, tempfile
import urllib.request as U
from google import genai

WTOK = os.environ["NOTION_WRITE_TOKEN"]
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
NH = {"Authorization": f"Bearer {WTOK}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
SESSION_DB = "682f047c-c46b-4b40-b836-269c1758ec6a"
MAX_CHARS = 1900

# ── Notion helpers ──────────────────────────────────────────────────────────
def napi(method, url, body=None):
    last = None
    for _ in range(4):
        try:
            data = json.dumps(body).encode() if body is not None else None
            return json.loads(U.urlopen(U.Request(url, data=data, headers=NH, method=method), timeout=45).read())
        except Exception as e:
            last = e; time.sleep(2)
    raise last

def db_query(db):
    rows, cur = [], None
    while True:
        b = {"page_size": 100}
        if cur: b["start_cursor"] = cur
        d = napi("POST", f"https://api.notion.com/v1/databases/{db}/query", b)
        rows += d["results"]
        if not d.get("has_more"): break
        cur = d["next_cursor"]
    return rows

def title_of(p):
    for v in p["properties"].values():
        if v["type"] == "title":
            return "".join(t["plain_text"] for t in v["title"])
    return ""

def recording_href(p):
    v = p["properties"].get("Recording", {})
    for t in v.get("rich_text", []):
        if t.get("href"):
            return t["href"]
    return ""

def has_transcript(pid):
    d = napi("GET", f"https://api.notion.com/v1/blocks/{pid}/children?page_size=100")
    for b in d.get("results", []):
        t = b["type"]
        if (t == "toggle" or (t.startswith("heading") and b.get(t, {}).get("is_toggleable"))) and \
           "transcript" in "".join(x.get("plain_text", "") for x in b.get(t, {}).get("rich_text", [])).lower():
            return True
    return False

def _para(t):
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": t}}]}}

def _bullet(t):
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": t[:1990]}}]}}

def to_paragraphs(body):
    blocks, buf, n = [], [], 0
    for line in body.split("\n"):
        while len(line) > MAX_CHARS:
            if buf: blocks.append(_para("\n".join(buf))); buf = []; n = 0
            blocks.append(_para(line[:MAX_CHARS])); line = line[MAX_CHARS:]
        if n + len(line) + 1 > MAX_CHARS and buf:
            blocks.append(_para("\n".join(buf))); buf = []; n = 0
        buf.append(line); n += len(line) + 1
    if buf: blocks.append(_para("\n".join(buf)))
    return blocks

def attach_transcript(pid, transcript):
    resp = napi("PATCH", f"https://api.notion.com/v1/blocks/{pid}/children",
                {"children": [{"object": "block", "type": "heading_3",
                    "heading_3": {"rich_text": [{"type": "text", "text": {"content": "Transcript"}}],
                                  "is_toggleable": True}}]})
    hid = resp["results"][0]["id"]
    paras = to_paragraphs(transcript)
    for i in range(0, len(paras), 100):
        napi("PATCH", f"https://api.notion.com/v1/blocks/{hid}/children", {"children": paras[i:i + 100]})
        time.sleep(0.2)
    return len(paras)

def attach_summary(pid, summary_md):
    """Prepend the AI summary (bold section headers + bullets) above the transcript."""
    blocks = []
    for line in summary_md.splitlines():
        s = line.strip()
        if not s: continue
        if s.startswith("## "):
            blocks.append({"object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": s[3:].strip().strip("*")},
                                             "annotations": {"bold": True}}]}})
        elif s.startswith(("- ", "* ")):
            blocks.append(_bullet(s[2:].strip()))
        else:
            blocks.append(_para(s))
    for i in range(0, len(blocks), 100):
        napi("PATCH", f"https://api.notion.com/v1/blocks/{pid}/children", {"children": blocks[i:i + 100]})
        time.sleep(0.2)
    return len(blocks)

# ── Recording download ──────────────────────────────────────────────────────
def download_recording(href):
    """Return (bytes, ext) if the recording is a directly-fetchable media file, else None."""
    m = re.search(r"drive\.google\.com/file/d/([A-Za-z0-9_-]+)", href)
    if not m:
        return None  # only handle direct Google Drive files for now
    url = f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    r = U.urlopen(U.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=300)
    ct = r.headers.get("Content-Type", "")
    if "text/html" in ct:
        return None  # not public / needs sign-in
    data = r.read()
    ext = ".mp3" if "audio" in ct else (".mp4" if "video" in ct else ".bin")
    return data, ext

# ── Gemini transcription + summary ──────────────────────────────────────────
def transcribe(data, ext):
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
        tf.write(data); path = tf.name
    up = client.files.upload(file=path)
    while getattr(up.state, "name", str(up.state)) == "PROCESSING":
        time.sleep(5); up = client.files.get(name=up.name)
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[up, "Transcribe this recording verbatim as a clean, readable transcript. "
                      "Label speaker turns where discernible (e.g. 'Host:', 'Speaker:'). "
                      "Output only the transcript text."],
        config=genai.types.GenerateContentConfig(max_output_tokens=65536))
    try: client.files.delete(name=up.name)
    except Exception: pass
    return resp.text or ""

SUM_PROMPT = """Write structured notes for this Reach Capital AMA titled "{title}", for founders who missed it.
- 4-8 thematic SECTIONS, each starting with a header line prefixed "## " (3-7 words).
- Under each header, 3-6 concise "- " bullets capturing frameworks, advice, numbers, examples, takeaways.
- Specific and practical. Output ONLY the sections.

Transcript:
{t}"""

def summarize(title, transcript):
    r = client.models.generate_content(model="gemini-2.5-flash",
        contents=SUM_PROMPT.format(title=title, t=transcript[:40000]))
    return r.text or ""

# ── Driver ──────────────────────────────────────────────────────────────────
def targets():
    out = []
    for p in db_query(SESSION_DB):
        pid, ti = p["id"], title_of(p)
        if has_transcript(pid):
            continue
        href = recording_href(p)
        if "drive.google.com/file/d/" in href:
            out.append((ti, pid, href))
    return out

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--dry-run"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else None
    tg = targets()
    print(f"transcribable (downloadable Drive recording, no transcript yet): {len(tg)}")
    for ti, _, href in tg:
        print(f"  - {ti[:50]}")
    if mode == "--dry-run":
        return
    done = 0
    for ti, pid, href in (tg[:cap] if cap else tg):
        try:
            dl = download_recording(href)
            if not dl:
                print(f"  ! not downloadable: {ti}"); continue
            data, ext = dl
            print(f"  … transcribing {ti[:45]} ({len(data)//1_000_000} MB {ext})")
            transcript = transcribe(data, ext)
            if len(transcript) < 500:
                print(f"  ! transcript too short, skipping: {ti}"); continue
            nb = attach_transcript(pid, transcript)
            summary = summarize(ti, transcript)
            ns = attach_summary(pid, summary) if summary else 0
            # also drop the transcript into the repo so it enters the RAG index
            slug = re.sub(r"[^a-z0-9]+", "-", ti.lower()).strip("-")[:70]
            with open(f"transcripts/reach-ama-{slug}-transcribed.md", "w", encoding="utf-8") as f:
                f.write(f"---\ntitle: {ti}\nsource_url: https://www.notion.so/{pid.replace('-','')}\n---\n\n{transcript}")
            done += 1
            print(f"  ✓ {ti[:45]} — transcript {nb} blocks + summary {ns} blocks")
        except Exception as e:
            print(f"  ! FAILED {ti[:40]}: {str(e)[:100]}")
    print(f"\nTranscribed + summarized {done} recordings.")

if __name__ == "__main__":
    main()
