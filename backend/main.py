"""ReachBot backend — FastAPI service.

Endpoints:
  GET  /health   → readiness + chunk count
  POST /login    → check ACCESS_PASSWORD, set httpOnly signed cookie
  POST /logout   → clear cookie
  POST /chat     → SSE stream: first a `sources` event, then `token` events, then `done`

The frontend talks to this only through its own server-side proxy, so the auth
cookie is issued to / validated for that proxy. CORS is locked to ALLOWED_ORIGIN.

Env:
  GEMINI_API_KEY   (required, via rag.py)
  ACCESS_PASSWORD  (optional; if unset, /chat is open)
  SESSION_SECRET   (required if ACCESS_PASSWORD set — signs the auth cookie)
  ALLOWED_ORIGIN   (default: http://localhost:3000)
  INDEX_PATH       (default: index.npz, via rag.py)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import Cookie, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

import rag
from resource_types import classify
from resource_fields import parse_fields

MAX_QUESTION_CHARS = 2000  # reject oversized questions before embedding (cost guard)


def _client_key(request: Request) -> str:
    """Rate-limit key = the real client IP. Behind the Vercel proxy + Fly, the
    socket peer is an infra IP, so prefer the first hop in X-Forwarded-For;
    fall back to the direct peer."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(key_func=_client_key)

ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:3000")
COOKIE_NAME = "rb_auth"

if ACCESS_PASSWORD and not SESSION_SECRET:
    raise RuntimeError("ACCESS_PASSWORD is set but SESSION_SECRET is missing — "
                       "set SESSION_SECRET to sign auth cookies.")

app = FastAPI(title="ReachBot API")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests — please slow down and try again shortly."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Auth helpers ────────────────────────────────────────────────────────────────
def _auth_token() -> str:
    """Deterministic token = HMAC(secret, password). Rotating the password or the
    secret invalidates all outstanding cookies."""
    return hmac.new(
        SESSION_SECRET.encode(), ACCESS_PASSWORD.encode(), hashlib.sha256
    ).hexdigest()


def _is_authed(cookie_value: Optional[str]) -> bool:
    if not ACCESS_PASSWORD:
        return True  # gate disabled
    return bool(cookie_value) and hmac.compare_digest(cookie_value, _auth_token())


# ── Startup: warm the index so the first request isn't slow ─────────────────────
@app.on_event("startup")
def _warm():
    rag.load_index()


def _index_synced_at() -> Optional[str]:
    """When the index was last built = mtime of index.npz. The weekly job rebuilds
    it and redeploys, so the file's mtime in the image reflects the last sync.
    ISO-8601 UTC, or None if the file isn't found."""
    try:
        ts = os.path.getmtime(rag.INDEX_PATH)
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except OSError:
        return None


@app.get("/health")
def health():
    idx = rag.load_index()
    return {
        "ok": True,
        "chunks": int(len(idx.chunks)),
        "gated": bool(ACCESS_PASSWORD),
        "last_synced": _index_synced_at(),
    }


# Cache the scope breakdown — it's a fixed scan over the index per process.
_scope_cache = None


@app.get("/scope")
def scope():
    """Unique-source counts by resource type, for the empty-state breakdown.
    Deduped by URL (the true page identity — distinct pages can share a title),
    and each page classified by the best category seen across its chunks (a
    page's chunks can carry inconsistent categories, some empty; prefer a
    non-empty one so classify() isn't fed an arbitrary blank)."""
    global _scope_cache
    if _scope_cache is None:
        idx = rag.load_index()
        page_title: dict = {}
        page_cat: dict = {}
        for t, u, c in zip(idx.titles, idx.urls, idx.categories):
            u, c = str(u), str(c)
            if u not in page_title:
                page_title[u] = str(t)
            # Upgrade to a non-empty category if we haven't got one yet.
            if u not in page_cat or (not page_cat[u] and c):
                page_cat[u] = c
        counts: dict = {}
        for u, title in page_title.items():
            typ = classify(title, page_cat[u])
            counts[typ] = counts.get(typ, 0) + 1
        _scope_cache = {"total": len(page_title), "by_type": counts}
    return _scope_cache


_page_fields_cache: Optional[dict] = None


def _page_fields(url: str, title: str, rtype: str) -> dict:
    """Richest parsed fields for a page, scanned across ALL its chunks in the
    index — not just the ones retrieved for this query.

    A page's metadata (AMA speaker/org, article publisher, deal offer) lives only
    in its header chunk; retrieval usually surfaces a body/transcript chunk that
    has none. Without this, cards for a cited page render with just a title. Built
    once per process and cached (keyed by URL)."""
    global _page_fields_cache
    if _page_fields_cache is None:
        idx = rag.load_index()
        cache: dict = {}
        for t, u, c, cat in zip(idx.titles, idx.urls, idx.chunks, idx.categories):
            u = str(u)
            f = parse_fields(str(c), classify(str(t), str(cat)))
            if not f:
                continue
            cur = cache.get(u)
            # Keep the chunk that yields the most fields for this page.
            if cur is None or len(f) > len(cur):
                cache[u] = f
        _page_fields_cache = cache
    return dict(_page_fields_cache.get(url, {}))


_samples_cache = None


@app.get("/samples")
def samples():
    """A couple of real, well-populated examples per resource type — powers the
    /preview design page. Picks chunks that actually have parsed fields so the
    cards preview with representative data."""
    global _samples_cache
    if _samples_cache is not None:
        return _samples_cache
    idx = rag.load_index()
    by_type: dict = {}
    seen_titles = set()
    # For contacts, span the three Notion sub-types instead of 4 of the same kind.
    contact_cats_seen: dict = {}
    for i in range(len(idx.chunks)):
        title = str(idx.titles[i])
        if title in seen_titles:
            continue
        cat = str(idx.categories[i])
        rtype = classify(title, cat)
        bucket = by_type.setdefault(rtype, [])
        if len(bucket) >= 4:  # 2 shown in the per-type section, the rest feed the mosaic
            continue
        # Keep contacts diverse: at most 2 per sub-category (advisor/coach/media).
        if rtype == "contact" and contact_cats_seen.get(cat, 0) >= 2:
            continue
        fields = parse_fields(str(idx.chunks[i]), rtype)
        # Prefer examples that actually have fields (skip bare external-link chunks).
        if not fields and rtype in ("article", "report"):
            continue
        seen_titles.add(title)
        if rtype == "contact":
            contact_cats_seen[cat] = contact_cats_seen.get(cat, 0) + 1
        bucket.append({
            "title": title,
            "url": str(idx.urls[i]),
            "type": rtype,
            "fields": fields,
        })
    _samples_cache = by_type
    return by_type


class LoginBody(BaseModel):
    password: str


@app.post("/login")
@limiter.limit("5/minute")
def login(request: Request, body: LoginBody):
    if not ACCESS_PASSWORD:
        return JSONResponse({"ok": True, "gated": False})
    if not hmac.compare_digest(body.password, ACCESS_PASSWORD):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        COOKIE_NAME, _auth_token(),
        httponly=True, secure=True, samesite="none",
        max_age=60 * 60 * 24 * 30,  # 30 days
    )
    return resp


@app.post("/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE_NAME)
    return resp


class ChatTurn(BaseModel):
    role: str = Field(max_length=16)
    content: str = Field(max_length=8000)


class ChatBody(BaseModel):
    # Hard cap at the schema layer too (returns 422 before the handler runs).
    question: str = Field(max_length=10000)
    # Recent conversation turns (oldest first) so follow-ups resolve. Optional —
    # an empty list keeps the old single-turn behavior. Capped to bound cost.
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


@app.post("/chat")
@limiter.limit("20/minute")
def chat(request: Request, body: ChatBody, rb_auth: Optional[str] = Cookie(default=None)):
    if not _is_authed(rb_auth):
        raise HTTPException(status_code=401, detail="Unauthorized.")

    question = (body.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Empty question.")
    if len(question) > MAX_QUESTION_CHARS:
        # Guard against cost amplification — an oversized question balloons the
        # embed + prompt. Reject before doing any paid work.
        raise HTTPException(
            status_code=400,
            detail=f"Question too long (max {MAX_QUESTION_CHARS} characters).",
        )

    def sse(event: str, data) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    def stream():
        # Wrap the WHOLE body: retrieval (embed call) can fail too, and if it raises
        # after the response headers are sent the client gets a silent empty stream.
        try:
            history = [{"role": t.role, "content": t.content} for t in body.history]
            # Follow-ups ("more on that") embed poorly — retrieve with a
            # history-resolved standalone query, but answer the raw question.
            search_q = rag.standalone_query(question, history)
            hits, quality = rag.retrieve(search_q)
            # One entry per unique page, with the per-type card fields parsed
            # from the chunk text (merged across a page's chunks) so the frontend
            # can render inline-citation chips + resource cards.
            by_url: dict = {}
            order: list = []
            for c, t, u, cat in hits:
                rtype = classify(t, cat)
                fields = parse_fields(str(c), rtype)
                if u not in by_url:
                    by_url[u] = {"title": t, "url": u, "type": rtype, "fields": fields}
                    order.append(u)
                else:
                    for k, v in fields.items():
                        by_url[u]["fields"].setdefault(k, v)
            # Backfill from the page's richest chunk across the whole index —
            # the metadata (speaker/org/publisher/offer) is usually in a header
            # chunk retrieval didn't surface, so retrieved-chunk fields alone are
            # often empty (e.g. AMA cards showing only a title).
            for u in order:
                entry = by_url[u]
                for k, v in _page_fields(u, entry["title"], entry["type"]).items():
                    entry["fields"].setdefault(k, v)
            sources = [by_url[u] for u in order]
            yield sse("sources", sources)

            context = rag.build_context(hits, quality)
            for token in rag.generate_stream(context, question, history):
                yield sse("token", token)
        except Exception as e:  # never leak a stack trace to the client stream
            yield sse("token", f"\n\n_An error occurred: {type(e).__name__}._")
        yield sse("done", {})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
