#!/usr/bin/env python3
"""
ReachBot ingest: chunk the exported markdown + transcripts, embed with Gemini,
and write a single index file. Run after reachin_export.py.

  pip install google-generativeai numpy pyyaml
  export GEMINI_API_KEY="..."   # from https://aistudio.google.com/apikey
  python ingest.py

Input:  ./reachin_md/*.md   (Notion export, each with a YAML header)
        ./transcripts/*.md  (optional AMA transcripts, same header format)
Output: ./index.npz         (chunks + vectors, committed to the repo)
"""
import os, glob, re, sys
import numpy as np

try:
    from google import genai
    import yaml
except ImportError:
    sys.exit("pip install google-genai numpy pyyaml")

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    sys.exit("Set GEMINI_API_KEY (https://aistudio.google.com/apikey).")
_client = genai.Client(api_key=API_KEY)

EMBED_MODEL = "gemini-embedding-001"
CHUNK_WORDS = 400      # ~chunk size; transcripts are long so we split them
OVERLAP_WORDS = 60     # keep context across chunk boundaries


def parse_md(path):
    """Return (metadata dict, body text) from a file with a YAML front-matter header."""
    text = open(path, encoding="utf-8").read()
    meta = {}
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except Exception:
            meta = {}
        body = m.group(2)
    else:
        body = text
    return meta, body


def chunk(words, size, overlap):
    i = 0
    while i < len(words):
        yield " ".join(words[i:i + size])
        i += size - overlap


def embed_one(text, retries=6):
    import time
    delay = 45
    for attempt in range(retries):
        try:
            r = _client.models.embed_content(model=EMBED_MODEL, contents=text)
            return r.embeddings[0].values
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print(f"  rate limit — waiting {delay}s...")
                time.sleep(delay)
                delay = min(delay * 2, 120)
            else:
                raise
    raise RuntimeError(f"Failed to embed after {retries} retries")


def embed_batch(texts):
    import time
    vecs = []
    for i, t in enumerate(texts):
        vecs.append(embed_one(t))
        if (i + 1) % 80 == 0:
            time.sleep(62)  # stay under 100 req/min
    return vecs


def main():
    files = glob.glob("reachin_md/*.md") + glob.glob("transcripts/*.md")
    if not files:
        sys.exit("No input files found in reachin_md/ or transcripts/.")

    chunks, metas = [], []
    for path in files:
        meta, body = parse_md(path)
        title = meta.get("title", os.path.basename(path))
        url = meta.get("source_url", "")
        # Boost short advisor/consultant/contact profiles so they embed with context
        notion_src = meta.get("notion_source", "") or url
        is_profile = any(k in notion_src.lower() for k in ["advisor", "consultant", "coach", "contact", "scout"])
        if is_profile and len(body.split()) < 100:
            body = f"Reach Capital Network Profile\n\n{body}"
        words = body.split()
        if not words:
            continue
        for c in chunk(words, CHUNK_WORDS, OVERLAP_WORDS):
            chunks.append(f"{title}\n\n{c}")
            metas.append({"title": title, "url": url})

    print(f"{len(chunks)} chunks from {len(files)} files. Embedding...")
    vectors = []
    checkpoint = "index_partial.npz"
    start = 0
    if os.path.exists(checkpoint):
        cp = np.load(checkpoint, allow_pickle=True)
        vectors = list(cp["vectors"])
        start = len(vectors)
        print(f"  resuming from checkpoint: {start} already embedded")

    for i in range(start, len(chunks), 50):
        vectors.extend(embed_batch(chunks[i:i + 50]))
        done = min(i + 50, len(chunks))
        print(f"  embedded {done}/{len(chunks)}")
        np.savez_compressed(checkpoint, vectors=np.array(vectors, dtype=np.float32))

    arr = np.array(vectors, dtype=np.float32)
    np.savez_compressed(
        "index.npz",
        vectors=arr,
        chunks=np.array(chunks, dtype=object),
        titles=np.array([m["title"] for m in metas], dtype=object),
        urls=np.array([m["url"] for m in metas], dtype=object),
    )
    print(f"Wrote index.npz ({arr.shape[0]} chunks, dim {arr.shape[1]}).")


if __name__ == "__main__":
    main()
