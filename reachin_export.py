#!/usr/bin/env python3
"""
ReachIn -> Markdown exporter for Project REACHBOT.

What it does:
  Walks every Notion page/database the integration can see, and writes each page
  to a .md file. Every file starts with a YAML header containing the page title
  and its Notion URL, so the chatbot can cite the primary source in its answers.

Setup (one-time):
  1. Go to https://www.notion.so/my-integrations -> "New integration"
     (internal). Copy the "Internal Integration Secret".
  2. In Notion, open the ReachIn top-level page -> "..." menu -> "Connections" ->
     add your integration. Sharing the top page shares everything nested under it.
  3. pip install notion-client python-slugify
  4. export NOTION_TOKEN="secret_xxx"
  5. python reachin_export.py

Output:
  ./reachin_md/<page-title-slug>.md  (one file per page)

This is the script the weekly scrape runs. For now, run it by hand to test the pull.
"""

import os
import sys
import time
from pathlib import Path

try:
    from notion_client import Client
    from notion_client.errors import APIResponseError
except ImportError:
    sys.exit("Run: pip install notion-client python-slugify")

from slugify import slugify

TOKEN = os.environ.get("NOTION_TOKEN")
if not TOKEN:
    sys.exit("Set NOTION_TOKEN env var first (export NOTION_TOKEN='secret_xxx').")

notion = Client(auth=TOKEN)
OUT = Path("reachin_md")
OUT.mkdir(exist_ok=True)


def rich_text(arr):
    """Flatten Notion rich-text array to plain string, keeping link URLs inline."""
    out = []
    for t in arr or []:
        txt = t.get("plain_text", "")
        href = t.get("href")
        out.append(f"[{txt}]({href})" if href else txt)
    return "".join(out)


def block_to_md(block, depth=0):
    """Convert a single block to a markdown line (best-effort for common types)."""
    t = block["type"]
    data = block.get(t, {})
    indent = "  " * depth
    rt = rich_text(data.get("rich_text", []))

    if t == "paragraph":
        return f"{indent}{rt}\n" if rt else ""
    if t in ("heading_1", "heading_2", "heading_3"):
        hashes = "#" * int(t[-1])
        return f"{hashes} {rt}\n"
    if t == "bulleted_list_item":
        return f"{indent}- {rt}\n"
    if t == "numbered_list_item":
        return f"{indent}1. {rt}\n"
    if t == "to_do":
        box = "[x]" if data.get("checked") else "[ ]"
        return f"{indent}- {box} {rt}\n"
    if t == "quote":
        return f"{indent}> {rt}\n"
    if t == "callout":
        return f"{indent}> {rt}\n"
    if t == "code":
        lang = data.get("language", "")
        return f"```{lang}\n{rt}\n```\n"
    if t == "bookmark" or t == "embed":
        url = data.get("url", "")
        return f"{indent}- {url}\n"
    if t in ("child_page", "child_database"):
        return ""  # handled by the crawler
    if rt:
        return f"{indent}{rt}\n"
    return ""


def get_blocks(block_id):
    """Fetch all child blocks of a page/block, paginated."""
    blocks, cursor = [], None
    while True:
        resp = notion.blocks.children.list(block_id=block_id, start_cursor=cursor, page_size=100)
        blocks.extend(resp["results"])
        if not resp.get("has_more"):
            break
        cursor = resp["next_cursor"]
        time.sleep(0.34)  # ~3 req/s rate limit
    return blocks


def render_page(block_id, depth=0):
    """Recursively render a page's blocks to markdown text."""
    md = ""
    for b in get_blocks(block_id):
        md += block_to_md(b, depth)
        if b.get("has_children") and b["type"] not in ("child_page", "child_database"):
            md += render_page(b["id"], depth + 1)
    return md


def page_title(page):
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            return rich_text(prop["title"]) or "untitled"
    return "untitled"


def export_page(page):
    title = page_title(page)
    url = page.get("url", "")
    body = render_page(page["id"])
    header = f"---\ntitle: {title}\nsource_url: {url}\nnotion_id: {page['id']}\n---\n\n"
    fname = OUT / f"{slugify(title)[:80] or 'untitled'}-{page['id'][:8]}.md"
    fname.write_text(header + f"# {title}\n\n{body}", encoding="utf-8")
    return fname


def main():
    print("Searching all pages the integration can access...")
    count, cursor = 0, None
    while True:
        try:
            resp = notion.search(
                filter={"property": "object", "value": "page"},
                start_cursor=cursor, page_size=100,
            )
        except APIResponseError as e:
            sys.exit(f"Notion API error: {e}")
        for page in resp["results"]:
            try:
                f = export_page(page)
                count += 1
                print(f"  [{count}] {f.name}")
            except Exception as e:
                print(f"  ! skipped {page.get('id')}: {e}")
        if not resp.get("has_more"):
            break
        cursor = resp["next_cursor"]
        time.sleep(0.34)
    print(f"\nDone. {count} pages -> {OUT.resolve()}")


if __name__ == "__main__":
    main()
