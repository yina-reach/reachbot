#!/usr/bin/env python3
"""
Drop raw Zoom transcripts into their matching AMA / Session Recording Notion
pages as a collapsible "Transcript" toggle heading.

Reuses the confident, deduped transcript->page matching from gen_summaries
(>= MIN_CONF title overlap, one transcript per page). Idempotent: skips any
page that already has a transcript toggle.

Usage:
  python add_transcripts.py --dry-run     # show what would be added
  python add_transcripts.py --test        # add to ONE page, print its URL
  python add_transcripts.py --go [N]      # add to all confident matches (optional cap)
"""
import os, sys, re, glob
import gen_summaries as G

MAX_CHARS = 1900          # Notion rich_text hard limit is 2000 chars
HEADING = "Transcript"


def transcript_body(path):
    raw = open(path, encoding="utf-8", errors="ignore").read()
    return re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.DOTALL).strip()


def _para(text):
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def to_paragraphs(body):
    """Pack transcript lines into <=MAX_CHARS paragraph blocks, preserving breaks."""
    blocks, buf, n = [], [], 0
    def flush():
        if buf:
            blocks.append(_para("\n".join(buf)))
    for line in body.split("\n"):
        # hard-split any single oversized line
        while len(line) > MAX_CHARS:
            flush(); buf.clear(); n = 0
            blocks.append(_para(line[:MAX_CHARS]))
            line = line[MAX_CHARS:]
        if n + len(line) + 1 > MAX_CHARS and buf:
            flush(); buf.clear(); n = 0
        buf.append(line); n += len(line) + 1
    flush()
    return blocks


def has_transcript_toggle(pid):
    for b in G.page_blocks(pid):
        t = b["type"]
        if t in ("toggle", "heading_1", "heading_2", "heading_3"):
            txt = "".join(x.get("plain_text", "") for x in b.get(t, {}).get("rich_text", []))
            if "transcript" in txt.lower():
                # only count it as "already there" if it's a toggle/toggleable heading
                if t == "toggle" or b.get(t, {}).get("is_toggleable"):
                    return True
    return False


def add_transcript(pid, body):
    paras = to_paragraphs(body)
    # 1) create the toggleable heading, capture its id
    resp = G._req("PATCH", f"https://api.notion.com/v1/blocks/{pid}/children",
                  {"children": [{"object": "block", "type": "heading_3",
                                 "heading_3": {"rich_text": [{"type": "text",
                                     "text": {"content": HEADING}}],
                                 "is_toggleable": True}}]})
    hid = resp["results"][0]["id"]
    # 2) append the transcript paragraphs as children of the toggle
    G.append_blocks(hid, paras)
    return len(paras)


def build_worklist():
    transcripts = G.load_transcripts()
    rows = G.db_query(G.SESSION_DB)
    cand = []
    for p in rows:
        ti = G.title_of(p)
        m = G.best_match(ti, transcripts)   # (path, body, wc, score)
        if m:
            cand.append({"ti": ti, "pid": p["id"], "path": m[0], "sc": m[3]})
    # dedupe: each transcript feeds only its highest-overlap page
    best = {}
    for c in cand:
        if c["path"] not in best or c["sc"] > best[c["path"]]["sc"]:
            best[c["path"]] = c
    return [c for c in best.values() if c["sc"] >= G.MIN_CONF]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--dry-run"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else None

    work = build_worklist()
    work.sort(key=lambda c: -c["sc"])
    print(f"Confident transcript->page matches: {len(work)}\n")

    if mode == "--dry-run":
        for c in work:
            print(f"  {c['sc']:.2f}  {c['ti'][:50]:50s} <- {os.path.basename(c['path'])}")
        return

    targets = work[:1] if mode == "--test" else (work[:cap] if cap else work)
    done = 0
    for c in targets:
        pid, ti = c["pid"], c["ti"]
        if has_transcript_toggle(pid):
            print(f"  skip (already has transcript): {ti}")
            continue
        try:
            n = add_transcript(pid, transcript_body(c["path"]))
            done += 1
            print(f"  ✓ {ti[:55]}  ({n} blocks)\n     https://www.notion.so/{pid.replace('-','')}")
        except Exception as e:
            print(f"  ! FAILED {ti}: {e}")
    print(f"\nDone. Added transcripts to {done} page(s).")


if __name__ == "__main__":
    main()
