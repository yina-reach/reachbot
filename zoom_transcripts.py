#!/usr/bin/env python3
"""
zoom_transcripts.py — Extract full transcript/summary content from Zoom AMA recordings.

Uses Playwright (headless Chromium) to:
  1. Navigate each Zoom share page and enter the passcode
  2. Capture the /nws/recording/1.0/play/info API response
  3. From that, get:
     a. Word-level VTT transcript (if hasTranscript=True)
     b. Zoom AI Smart Chapters (detailed chapter summaries — always available)
     c. Audio download → Gemini transcription (for recordings with no transcript)

All Notion AMA pages are parsed for recording URLs + passcodes automatically.
Tracks processed recordings in transcripts/_seen.json.

Usage:
  export GEMINI_API_KEY="..."
  python zoom_transcripts.py --dry-run     # see what's available
  python zoom_transcripts.py --limit 3     # test 3 recordings
  python zoom_transcripts.py               # full backfill
  python zoom_transcripts.py --local       # transcribe MP4s in ./recordings/

Dependencies:
  pip install google-genai python-slugify playwright requests
  python -m playwright install chromium
"""

import os, re, json, sys, time, argparse, tempfile
from pathlib import Path

try:
    from slugify import slugify
except ImportError:
    def slugify(s):
        return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

try:
    from google import genai
except ImportError:
    sys.exit("pip install google-genai")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("pip install playwright && python -m playwright install chromium")

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    sys.exit("Set GEMINI_API_KEY env var.")

_client = genai.Client(api_key=API_KEY)

MD_DIR        = Path("reachin_md")
OUT_DIR       = Path("transcripts")
RECORDINGS_DIR= Path("recordings")
SEEN_FILE     = OUT_DIR / "_seen.json"
AUDIO_MIMES   = {".mp4": "audio/mp4", ".m4a": "audio/mp4", ".webm": "audio/webm",
                 ".mp3": "audio/mpeg", ".wav": "audio/wav"}

OUT_DIR.mkdir(exist_ok=True)
RECORDINGS_DIR.mkdir(exist_ok=True)


# ── Seen tracking ─────────────────────────────────────────────────────────────

def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()

def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2))


# ── Parse Notion markdown for recording links ─────────────────────────────────

_REC_PATTERN = re.compile(
    r'\*\*Recording[^*]*\*\*:?\s*(?:\[[^\]]*\]\()?(https?://[^\s\)\n]+)\)?',
    re.IGNORECASE,
)
_PC_PATTERN  = re.compile(r'[Pp]asscode:?\s*([^\n\s]+)')
_TITLE_PAT   = re.compile(r'^title:\s*(.+)$', re.MULTILINE)
_URL_PAT     = re.compile(r'^source_url:\s*(.+)$', re.MULTILINE)
_GOOGLE_Q    = re.compile(r'[?&]q=(https?%3A%2F%2F[^&]+)')

def unwrap_url(url: str) -> str:
    m = _GOOGLE_Q.search(url)
    if m:
        from urllib.parse import unquote
        return unquote(m.group(1))
    return url

def fetch_full_urls_from_notion() -> dict:
    """
    Query the Notion AMA database via API to get full (untruncated) Zoom URLs + passcodes.
    Returns dict mapping truncated-url-prefix -> {url, passcode, title}.
    Recording property is rich_text: first element has link.url = full Zoom URL,
    subsequent text contains "\\nPasscode: XXXXX".
    """
    import urllib.request as _ur
    notion_token = os.environ.get("NOTION_TOKEN")
    if not notion_token:
        return {}
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    db_id = "682f047cc46b4b40b836269c1758ec6a"
    results = {}
    cursor = None
    while True:
        body: dict = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        req = _ur.Request(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            data=json.dumps(body).encode(),
            headers=headers, method="POST"
        )
        with _ur.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        if "results" not in data:
            break
        for page in data["results"]:
            props = page.get("properties", {})
            # Title
            title = ""
            title_prop = props.get("Title", {})
            if title_prop.get("title"):
                title = "".join(t["plain_text"] for t in title_prop["title"])
            # Recording: rich_text with link in first element, passcode in body text
            rec_prop = props.get("Recording", {})
            url = None
            passcode = None
            if rec_prop.get("type") == "rich_text":
                full_text = ""
                for rt in rec_prop.get("rich_text", []):
                    # URL is in the link field of the first hyperlinked text
                    if not url and rt.get("href") and "zoom.us" in rt["href"]:
                        url = rt["href"]
                    elif not url and rt.get("text", {}).get("link", {}) and \
                            rt["text"]["link"] and "zoom.us" in rt["text"]["link"].get("url", ""):
                        url = rt["text"]["link"]["url"]
                    full_text += rt.get("plain_text", "")
                # Extract passcode from concatenated text
                pc_m = re.search(r'[Pp]asscode:?\s*([^\n\s]+)', full_text)
                if pc_m:
                    passcode = pc_m.group(1).strip()
            elif rec_prop.get("type") == "url":
                url = rec_prop.get("url")
            if url and "zoom.us" in url:
                # Key by first 60 chars to match truncated markdown URLs
                key = url[:60]
                results[key] = {"url": url, "passcode": passcode, "title": title}
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    print(f"  [Notion API] Fetched {len(results)} full recording URLs")
    return results


def find_recordings() -> list:
    # Get full URLs from Notion API to fix truncated markdown exports
    full_url_map = fetch_full_urls_from_notion()

    recs = []
    for f in sorted(MD_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        for m in _REC_PATTERN.finditer(text):
            url = unwrap_url(m.group(1).rstrip(".,)"))
            if not url or "zoom.us" not in url:
                continue
            nearby = text[m.end():m.end() + 300]
            pc_m = _PC_PATTERN.search(nearby)
            passcode = pc_m.group(1).strip() if pc_m else None
            # Replace truncated URL + supplement passcode from Notion API
            if full_url_map:
                url_key = url[:60]
                api_entry = next(
                    (v for k, v in full_url_map.items() if k.startswith(url_key) or url_key.startswith(k)),
                    None
                )
                if api_entry:
                    url = api_entry["url"]
                    if not passcode and api_entry.get("passcode"):
                        passcode = api_entry["passcode"]
            title_m = _TITLE_PAT.search(text)
            title = title_m.group(1).strip() if title_m else f.stem
            url_m = _URL_PAT.search(text)
            notion_url = url_m.group(1).strip() if url_m else ""
            has_start_time = "startTime=" in url or "." in url.split("/rec/share/")[-1].split("?")[0]
            recs.append({"url": url, "passcode": passcode,
                         "title": title, "notion_url": notion_url,
                         "likely_live": has_start_time})
    # Sort: full-format URLs first
    recs.sort(key=lambda r: not r["likely_live"])
    return recs


# ── VTT → text ────────────────────────────────────────────────────────────────

def vtt_to_text(vtt: str) -> str:
    lines, seen_line = [], set()
    for line in vtt.splitlines():
        line = line.strip()
        if (not line or line.startswith("WEBVTT") or
                re.match(r'^\d{2}:\d{2}', line) or
                re.match(r'^\d+$', line) or
                line.startswith("NOTE")):
            continue
        line = re.sub(r'<[^>]+>', '', line).strip()
        if line and line not in seen_line:
            seen_line.add(line)
            lines.append(line)
    return " ".join(lines)


# ── Playwright: get recording data ────────────────────────────────────────────

def playwright_extract(url: str, passcode: str | None, timeout_ms: int = 45_000) -> dict:
    """
    Navigate the Zoom share page, enter passcode, and capture:
      - play_info: full /play/info API response
      - smart_chapters: AI chapter summaries
      - vtt_text: word-level transcript (if available)
      - mp4_url: direct video URL (for audio download fallback)
    """
    captured = {"play_info": None, "smart_chapters": [], "vtt_text": None,
                "mp4_url": None, "title": None, "cookies": []}

    def on_response(response):
        rurl = response.url
        try:
            body = response.body().decode("utf-8", errors="replace")
        except Exception:
            return

        if "/nws/recording/1.0/play/info/" in rurl:
            captured["play_info"] = body

        elif "/nws/recording/1.0/smart-chapters" in rurl:
            try:
                data = json.loads(body)
                chapters = (data.get("result") or {}).get(
                    "recordingSmartChapters", {}).get("itemList", [])
                if chapters:
                    captured["smart_chapters"] = chapters
            except Exception:
                pass

        elif "/nws/recording/1.0/play/vtt" in rurl:
            # This is the chapter-markers VTT, not the speech transcript
            pass

        elif ".vtt" in rurl and ("WEBVTT" in body or "-->" in body):
            # Real speech-level transcript VTT
            text = vtt_to_text(body)
            if text and len(text) > 200:
                captured["vtt_text"] = text

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = ctx.new_page()
        page.on("response", on_response)

        try:
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(8000)  # wait for React SPA to mount

            # Enter passcode if form appears
            try:
                pwd = page.wait_for_selector(
                    'input[type="password"][placeholder*="asscode"], '
                    'input[type="password"][placeholder*="assword"], '
                    'input[type="password"]',
                    timeout=6000,
                )
                if pwd and passcode:
                    pwd.fill(passcode)
                    try:
                        page.click('button[type="submit"]', timeout=3000)
                    except Exception:
                        try:
                            page.click('button:has-text("Watch")', timeout=2000)
                        except Exception:
                            pwd.press("Enter")
                    page.wait_for_timeout(12000)
            except Exception:
                pass  # No passcode form — already accessible or different flow

            captured["title"] = page.title()
            captured["cookies"] = ctx.cookies()

            # Extract MP4 URL from play_info for audio fallback
            if captured["play_info"]:
                try:
                    info = json.loads(captured["play_info"])
                    result = info.get("result") or {}
                    captured["mp4_url"] = result.get("mp4Url") or result.get("viewMp4Url")
                    captured["has_transcript"] = result.get("hasTranscript", False)
                    captured["has_ai_chapters"] = result.get("needGetSmartChapters", False)
                except Exception:
                    pass

        except Exception as e:
            print(f"    Playwright error: {e}")
        finally:
            try:
                browser.close()
            except Exception:
                pass

    return captured


# ── Build transcript text from captured data ──────────────────────────────────

def build_transcript(data: dict, title: str) -> str | None:
    parts = []

    # 1. Word-level VTT transcript (best quality)
    if data.get("vtt_text"):
        parts.append(data["vtt_text"])

    # 2. AI Smart Chapters (rich summaries with timestamps)
    chapters = data.get("smart_chapters") or []
    if chapters:
        parts.append("## AI-Generated Chapter Summaries\n")
        for ch in chapters:
            parts.append(
                f"**[{ch.get('startTime','?')} – {ch.get('endTime','?')}] "
                f"{ch.get('title', '')}**\n{ch.get('chapter', '')}\n"
            )

    return "\n\n".join(parts) if parts else None


# ── Gemini audio transcription (fallback) ────────────────────────────────────

def gemini_transcribe(audio_path: Path) -> str | None:
    mime = AUDIO_MIMES.get(audio_path.suffix.lower(), "audio/mp4")
    size_mb = audio_path.stat().st_size / 1_000_000
    print(f"    Uploading {size_mb:.1f} MB to Gemini Files API…")
    try:
        with open(audio_path, "rb") as fh:
            uploaded = _client.files.upload(
                file=fh,
                config={"mime_type": mime, "display_name": audio_path.name},
            )
        for _ in range(60):
            f = _client.files.get(name=uploaded.name)
            if f.state.name == "ACTIVE":
                break
            time.sleep(5)
        else:
            print("    Gemini file processing timed out.")
            return None

        print("    Transcribing with Gemini…")
        resp = None
        for _attempt in range(3):
            try:
                resp = _client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        uploaded,
                        "Please provide a complete, verbatim transcript of this audio. "
                        "Format as a readable document with paragraph breaks at natural pauses. "
                        "Include speaker labels where possible (Host:, Speaker:, Q:, A:). "
                        "Do not summarize — transcribe everything said.",
                    ],
                )
                break
            except Exception as e:
                print(f"    Gemini error (attempt {_attempt+1}/3): {e}")
                if _attempt < 2:
                    time.sleep(30)
        try:
            _client.files.delete(name=uploaded.name)
        except Exception:
            pass
        return resp.text if resp else None
    except Exception as e:
        print(f"    Gemini transcription error: {e}")
        return None


def download_and_transcribe(mp4_url: str, cookies: list | None = None) -> str | None:
    """Download MP4 audio track directly and transcribe with Gemini."""
    import urllib.request, urllib.error
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / "audio.mp4"
        try:
            req = urllib.request.Request(
                mp4_url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                         "Referer": "https://us02web.zoom.us/"},
            )
            if cookies:
                cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies
                                       if "zoom.us" in c.get("domain", ""))
                if cookie_str:
                    req.add_header("Cookie", cookie_str)
            print(f"    Downloading audio from Zoom CDN…")
            with urllib.request.urlopen(req) as resp, open(audio, "wb") as fh:
                fh.write(resp.read())
            if audio.exists() and audio.stat().st_size > 100_000:
                return gemini_transcribe(audio)
            print("    Download produced empty file.")
            return None
        except Exception as e:
            print(f"    Audio download failed: {e}")
            return None


# ── Save transcript ───────────────────────────────────────────────────────────

def save_transcript(rec: dict, transcript: str):
    slug = slugify(rec["title"])[:80] or "untitled"
    out  = OUT_DIR / f"{slug}.md"
    # Quote title in YAML to handle colons in "Reach AMA: ..." style names
    safe_title = rec["title"].replace('"', '\\"')
    content = (
        f'---\n'
        f'title: "{safe_title} (Full Transcript)"\n'
        f'source_url: {rec["notion_url"]}\n'
        f'recording_url: {rec["url"]}\n'
        f'---\n\n'
        f'# {rec["title"]} — Full Transcript & Notes\n\n'
        f'{transcript}\n'
    )
    out.write_text(content, encoding="utf-8")
    print(f"    ✓ Saved → {out}  ({len(transcript):,} chars)")
    return out


# ── Mode: local files ─────────────────────────────────────────────────────────

def run_local(seen: set, dry_run: bool, limit: int):
    audio_files = sorted(
        f for f in RECORDINGS_DIR.iterdir()
        if f.suffix.lower() in list(AUDIO_MIMES.keys()) + [".vtt"]
        and not f.name.startswith("_")
    )
    if not audio_files:
        print(f"No files found in {RECORDINGS_DIR}/")
        print("Drop .mp4 / .m4a / .vtt files there and re-run.")
        return

    new = [f for f in audio_files if str(f) not in seen]
    print(f"Found {len(audio_files)} files, {len(new)} unprocessed.")
    if dry_run:
        for f in new: print(f"  {f.name}")
        return
    if limit: new = new[:limit]

    for i, audio in enumerate(new, 1):
        title = audio.stem.replace("-", " ").replace("_", " ").title()
        print(f"\n[{i}/{len(new)}] {audio.name}")
        if audio.suffix.lower() == ".vtt":
            text = vtt_to_text(audio.read_text(encoding="utf-8"))
        else:
            text = gemini_transcribe(audio)
        if text and len(text.strip()) > 100:
            save_transcript({"title": title, "notion_url": "", "url": ""}, text)
            seen.add(str(audio))
            save_seen(seen)
        else:
            print("    ✗ Could not transcribe.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--local", action="store_true",
                        help="Transcribe files in ./recordings/ instead of scraping Zoom")
    parser.add_argument("--force", action="store_true",
                        help="Re-process already-seen recordings")
    parser.add_argument("--limit", type=int, default=0,
                        help="Process at most N recordings (0 = all)")
    parser.add_argument("--since-days", type=int, default=None,
                        help="Only process recordings whose Notion file was modified in last N days")
    args = parser.parse_args()

    seen = load_seen() if not args.force else set()

    if args.local:
        run_local(seen, args.dry_run, args.limit)
        return

    recordings = find_recordings()

    # Deduplicate by URL
    by_url = {}
    for r in recordings:
        if r["url"] not in by_url:
            by_url[r["url"]] = r
    recordings = list(by_url.values())

    new = [r for r in recordings if r["url"] not in seen]
    print(f"Found {len(recordings)} Zoom recording links, {len(new)} unprocessed.")

    if args.dry_run:
        for r in new:
            pc = f"[{r['passcode']}]" if r["passcode"] else "[no passcode]"
            print(f"  {pc}  {r['title']}")
        return

    if not new:
        print("Nothing new. Run with --force to reprocess all.")
        return

    if args.limit:
        new = new[:args.limit]
        print(f"Processing {len(new)} recordings.")

    processed, failed = 0, []
    for i, rec in enumerate(new, 1):
        print(f"\n[{i}/{len(new)}] {rec['title']}")
        print(f"  URL: {rec['url'][:90]}")

        data = playwright_extract(rec["url"], rec["passcode"])

        # Use detected title if available
        if data.get("title") and data["title"] not in ("Passcode Required - Zoom", "Error - Zoom"):
            rec["title"] = data["title"].replace(" - Zoom", "").strip()

        transcript = build_transcript(data, rec["title"])

        # Fallback: download MP4 audio and transcribe with Gemini
        if not transcript and data.get("mp4_url"):
            print("  → No transcript/chapters — downloading audio for Gemini…")
            audio_text = download_and_transcribe(data["mp4_url"], data.get("cookies"))
            if audio_text:
                transcript = audio_text

        if transcript and len(transcript.strip()) > 100:
            save_transcript(rec, transcript)
            seen.add(rec["url"])
            save_seen(seen)
            processed += 1
        else:
            print(f"    ✗ No content obtained")
            failed.append(rec["title"])

        time.sleep(2)

    print(f"\n{'='*60}")
    print(f"Done. {processed}/{len(new)} transcripts saved to {OUT_DIR}/")
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for t in failed: print(f"  - {t}")
    print(f"\nNext: python3.11 ingest.py to rebuild the index.")


if __name__ == "__main__":
    main()
