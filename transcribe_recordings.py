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

def page_blocks(pid):
    """ALL top-level blocks (paginated — pages can exceed the 100-block page size)."""
    out, cur = [], None
    while True:
        url = f"https://api.notion.com/v1/blocks/{pid}/children?page_size=100"
        if cur:
            url += f"&start_cursor={cur}"
        d = napi("GET", url)
        out += d.get("results", [])
        if not d.get("has_more"):
            break
        cur = d["next_cursor"]
    return out

def _transcript_headers(pid):
    """Return (nonempty_found, first_empty_header_id) among transcript toggles/headings."""
    empty_id = None
    for b in page_blocks(pid):
        t = b["type"]
        if (t == "toggle" or (t.startswith("heading") and b.get(t, {}).get("is_toggleable"))) and \
           "transcript" in "".join(x.get("plain_text", "") for x in b.get(t, {}).get("rich_text", [])).lower():
            if b.get("has_children"):
                return True, None
            if empty_id is None:
                empty_id = b["id"]
    return False, empty_id

def has_transcript(pid):
    # An empty "Transcript" heading (no children) doesn't count as a transcript.
    return _transcript_headers(pid)[0]

def page_video_url(pid):
    """Fresh presigned URL of a Notion-hosted video embedded on the page, if any."""
    for b in page_blocks(pid):
        if b["type"] == "video" and b["video"].get("type") == "file":
            return b["video"]["file"]["url"]
    return ""

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
    # Reuse an existing empty "Transcript" toggle/heading rather than adding a second one.
    hid = _transcript_headers(pid)[1]
    if hid is None:
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
    """Return (bytes, ext) if the recording is a directly-fetchable media file, else None.
    Handles public Google Drive files and Notion-hosted videos (href 'notion-video:<pid>')."""
    from urllib.parse import quote
    if href.startswith("notion-video:"):
        # Presigned S3 URLs expire — fetch a fresh one right before downloading.
        url = page_video_url(href.split(":", 1)[1])
        if not url:
            return None
        r = U.urlopen(U.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=600)
        return r.read(), ".mp4"
    m = re.search(r"drive\.google\.com/file/d/([A-Za-z0-9_-]+)", href)
    if not m:
        return None  # only handle direct Google Drive files for now
    hdrs = {"User-Agent": "Mozilla/5.0"}
    url = f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    r = U.urlopen(U.Request(url, headers=hdrs), timeout=600)
    ct = r.headers.get("Content-Type", "")
    if "text/html" in ct:
        # Large public files get a "can't scan for viruses" confirm page.
        # Re-submit its form (carries id/confirm/uuid hidden fields); if there is
        # no download form, the file needs sign-in and we skip it.
        html = r.read().decode("utf-8", "replace")
        action = re.search(r'action="([^"]*download[^"]*)"', html)
        if not action:
            return None
        fields = dict(re.findall(r'name="([^"]+)"\s+value="([^"]*)"', html))
        q = "&".join(f"{k}={quote(v)}" for k, v in fields.items())
        r = U.urlopen(U.Request(f"{action.group(1)}?{q}", headers=hdrs), timeout=600)
        ct = r.headers.get("Content-Type", "")
        if "text/html" in ct:
            return None
    data = r.read()
    ext = ".mp3" if "audio" in ct else (".mp4" if "video" in ct else ".bin")
    return data, ext

# ── Gemini transcription + summary ──────────────────────────────────────────
def transcribe(data, ext):
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
        tf.write(data); path = tf.name
    # Video costs ~263 tokens/sec — an hour-plus recording exceeds the model's
    # context and 400s. Audio is ~32 tokens/sec, so extract it when ffmpeg exists
    # (GitHub runners always have it; locally it's optional).
    if ext != ".mp3":
        import shutil, subprocess
        ff = shutil.which("ffmpeg") or ("/opt/homebrew/bin/ffmpeg" if os.path.exists("/opt/homebrew/bin/ffmpeg") else None)
        if ff:
            apath = path + ".mp3"
            try:
                subprocess.run([ff, "-y", "-i", path, "-vn", "-acodec", "libmp3lame",
                                "-b:a", "64k", apath], check=True, timeout=1800,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                os.unlink(path); path = apath
                print(f"  … extracted audio ({os.path.getsize(apath)//1_000_000} MB mp3)")
            except Exception:
                pass  # fall back to uploading the original video
    up = client.files.upload(file=path)
    os.unlink(path)  # local temp no longer needed once uploaded — don't leak GBs
    while getattr(up.state, "name", str(up.state)) == "PROCESSING":
        time.sleep(5); up = client.files.get(name=up.name)
    resp = None
    for attempt in range(5):
        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[up, "Transcribe this recording verbatim as a clean, readable transcript. "
                              "Label speaker turns where discernible (e.g. 'Host:', 'Speaker:'). "
                              "Output only the transcript text."],
                config=genai.types.GenerateContentConfig(max_output_tokens=65536))
            break
        except Exception as e:
            msg = str(e)
            transient = any(k in msg for k in (
                "503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "502",
                "disconnected", "Connection", "timed out", "timeout", "RemoteProtocol"))
            if attempt < 4 and transient:
                wait = 45 * (attempt + 1)
                print(f"  … gemini busy, retrying in {wait}s")
                time.sleep(wait)
                continue
            try: client.files.delete(name=up.name)
            except Exception: pass
            raise
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
    prompt = SUM_PROMPT.format(title=title, t=transcript[:40000])
    for model in ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-flash"):
        try:
            r = client.models.generate_content(model=model, contents=prompt)
            return r.text or ""
        except Exception as e:
            msg = str(e)
            if "503" in msg or "UNAVAILABLE" in msg:
                time.sleep(15); continue   # overloaded — wait, then try next model
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                m = re.search(r"retry[^']*'(\d+)s'", msg)
                time.sleep(int(m.group(1)) if m else 20); continue
            raise
    return ""

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
        elif page_video_url(pid):
            out.append((ti, pid, f"notion-video:{pid}"))
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
