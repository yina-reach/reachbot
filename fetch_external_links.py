#!/usr/bin/env python3
"""
Scan all reachin_md/*.md files for external URLs, fetch their content,
and save as additional markdown files in reachin_md/.

Run after reachin_export.py:
    python fetch_external_links.py

Requires: pip install trafilatura requests
"""

import os
import re
import json
import time
import hashlib
from pathlib import Path

try:
    import trafilatura
    import requests
except ImportError:
    import sys
    sys.exit("Run: pip install trafilatura requests")

OUT = Path("reachin_md")
SEEN_FILE = OUT / "_external_seen.json"

# Domains to skip — not article content
SKIP_DOMAINS = {
    "notion.so", "app.notion.com",
    "zoom.us",
    "linkedin.com",
    "airtable.com",
    "loom.com",
    "docs.google.com", "drive.google.com", "google.com",
    "calendly.com",
    "twitter.com", "x.com",
    "instagram.com", "facebook.com",
    "youtube.com", "youtu.be",
    "app.pitch.com",
    "discord.com",
    "bsky.app",
    "splashthat.com",
    "docsend.com",
    "mailto:",
    "github.com",
    "slack.com",
}

# URL patterns to skip
SKIP_PATTERNS = [
    r"hs-sales-engage\.com",  # HubSpot tracking
    r"email\.carta\.com",     # email tracking
    r"utm_",                  # tracking params
    r"/login$",
    r"/signup$",
    r"/refer-",
]

URL_RE = re.compile(r'https?://[^\s\)\]"\'>]+')


def should_skip(url: str) -> bool:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.lstrip("www.")
    if any(domain == s or domain.endswith("." + s) for s in SKIP_DOMAINS):
        return True
    if any(re.search(p, url) for p in SKIP_PATTERNS):
        return True
    return False


def url_to_filename(url: str) -> str:
    h = hashlib.md5(url.encode()).hexdigest()[:8]
    # Extract a readable slug from the URL path
    from urllib.parse import urlparse
    path = urlparse(url).path.strip("/").replace("/", "-")
    slug = re.sub(r"[^\w-]", "", path)[:60] or "external"
    return f"external-{slug}-{h}.md"


def fetch_article(url: str) -> str | None:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ReachBot/1.0)"}
    try:
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            return None
        content_type = resp.headers.get("content-type", "")
        if "pdf" in content_type:
            return None  # skip PDFs for now
        text = trafilatura.extract(
            resp.text,
            include_links=False,
            include_images=False,
            include_tables=True,
            no_fallback=False,
        )
        return text if text and len(text) > 200 else None
    except Exception:
        return None


def collect_urls() -> dict[str, list[str]]:
    """Return {url: [source_page_title, ...]} from all markdown files."""
    url_sources: dict[str, list[str]] = {}
    for md in sorted(OUT.glob("*.md")):
        if md.name.startswith("_") or md.name.startswith("external-"):
            continue
        text = md.read_text(errors="ignore")
        # Get title from frontmatter
        title_m = re.search(r"^title:\s*(.+)$", text, re.MULTILINE)
        title = title_m.group(1).strip() if title_m else md.stem
        for url in URL_RE.findall(text):
            url = url.rstrip(".,;)")
            if should_skip(url):
                continue
            url_sources.setdefault(url, [])
            if title not in url_sources[url]:
                url_sources[url].append(title)
    return url_sources


def load_seen() -> dict:
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {}


def save_seen(seen: dict):
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def main():
    seen = load_seen()
    url_sources = collect_urls()

    new_urls = {u: s for u, s in url_sources.items() if u not in seen}
    print(f"Found {len(url_sources)} external URLs total, {len(new_urls)} new.")

    saved = 0
    failed = 0
    skipped = 0

    for i, (url, sources) in enumerate(new_urls.items(), 1):
        print(f"[{i}/{len(new_urls)}] {url[:80]}")
        text = fetch_article(url)
        if not text:
            print(f"  ✗ No content")
            seen[url] = "failed"
            failed += 1
            save_seen(seen)
            time.sleep(0.5)
            continue

        fname = url_to_filename(url)
        fpath = OUT / fname
        source_note = ", ".join(sources[:3])
        md = f"---\ntitle: {url}\nsource_url: {url}\nnotion_source: {source_note}\n---\n\n{text}\n"
        fpath.write_text(md)
        seen[url] = fname
        saved += 1
        print(f"  ✓ {len(text):,} chars → {fname}")
        save_seen(seen)
        time.sleep(1)  # be polite

    print(f"\nDone. Saved: {saved}  Failed/empty: {failed}  Already seen: {len(url_sources) - len(new_urls)}")


if __name__ == "__main__":
    main()
