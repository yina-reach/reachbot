#!/usr/bin/env python3
"""Ensure every Session Recordings page with a Transcript also has an AI summary.

Detection: an AI summary (as written by gen_summaries.py / transcribe_recordings.py)
is >=2 top-level all-bold paragraphs (section headers) plus >=3 bulleted items.
Pages with a transcript toggle but no such signature get a summary generated from
the transcript text (read from the toggle's children) and appended in the same format.

  python fix_missing_summaries.py --dry-run   # list pages that would be fixed
  python fix_missing_summaries.py --go [N]
"""
import sys

from transcribe_recordings import (napi, db_query, title_of, has_transcript,
                                   attach_summary, summarize, SESSION_DB)

def blocks_of(pid):
    out, cur = [], None
    while True:
        url = f"https://api.notion.com/v1/blocks/{pid}/children?page_size=100"
        if cur: url += f"&start_cursor={cur}"
        d = napi("GET", url)
        out += d.get("results", [])
        if not d.get("has_more"): break
        cur = d["next_cursor"]
    return out

def plain(b, t):
    return "".join(x.get("plain_text", "") for x in b.get(t, {}).get("rich_text", []))

def is_bold_header(b):
    if b["type"] != "paragraph": return False
    rt = b["paragraph"].get("rich_text", [])
    return (len(rt) >= 1 and all(r.get("annotations", {}).get("bold") for r in rt)
            and 0 < len(plain(b, "paragraph")) < 90)

def transcript_block_id(blocks):
    for b in blocks:
        t = b["type"]
        if (t == "toggle" or (t.startswith("heading") and b.get(t, {}).get("is_toggleable"))) \
           and "transcript" in plain(b, t).lower():
            return b["id"]
    return None

def has_ai_summary(blocks):
    headers = sum(1 for b in blocks if is_bold_header(b))
    bullets = sum(1 for b in blocks if b["type"] in ("bulleted_list_item", "numbered_list_item"))
    return headers >= 2 and bullets >= 3

def transcript_text(tid):
    parts = [plain(b, b["type"]) for b in blocks_of(tid)]
    return "\n".join(p for p in parts if p)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--dry-run"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else None
    todo = []
    for p in db_query(SESSION_DB):
        pid, ti = p["id"], title_of(p)
        if not has_transcript(pid):
            continue
        blocks = blocks_of(pid)
        if has_ai_summary(blocks):
            continue
        todo.append((ti, pid, transcript_block_id(blocks)))
    print(f"transcript but NO AI summary: {len(todo)}")
    for ti, _, _ in todo:
        print(f"  - {ti[:60]}")
    if mode == "--dry-run":
        return
    done = 0
    for ti, pid, tid in (todo[:cap] if cap else todo):
        try:
            text = transcript_text(tid) if tid else ""
            if len(text) < 500:
                print(f"  ! transcript too thin, skipped: {ti[:50]}"); continue
            summary = summarize(ti, text)
            if not summary or "## " not in summary:
                print(f"  ! bad summary output, skipped: {ti[:50]}"); continue
            nb = attach_summary(pid, summary)
            done += 1
            print(f"  ✓ {ti[:55]} — summary {nb} blocks")
        except Exception as e:
            print(f"  ! FAILED {ti[:45]}: {str(e)[:90]}")
    print(f"\nAdded summaries to {done} pages.")

if __name__ == "__main__":
    main()
