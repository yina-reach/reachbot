#!/usr/bin/env python3
"""ReachBot — Reach Capital's AI assistant for portfolio founders."""
import os, re
import numpy as np
import streamlit as st
from google import genai

EMBED_MODEL = "gemini-embedding-001"
CHAT_MODEL  = "gemini-2.5-flash"
TOP_K       = 25

def _secret(key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

API_KEY = os.environ.get("GEMINI_API_KEY") or _secret("GEMINI_API_KEY")
_client = genai.Client(api_key=API_KEY)

st.set_page_config(
    page_title="ReachBot",
    page_icon="⬡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&display=swap');

/* ── Tokens ── */
:root {
  --bg:       #070B12;
  --surface:  #0D1420;
  --surface2: #111D2E;
  --border:   rgba(255,255,255,0.06);
  --border2:  rgba(255,255,255,0.10);
  --text:     #EEF2F7;
  --text2:    rgba(186,205,232,0.78);  /* muted body — lifted for WCAG contrast */
  --text3:    rgba(148,172,205,0.62);  /* labels/metadata — likewise lifted */
  --accent:   #60A5FA;
  --blue1:    #2563EB;
  --blue2:    #60A5FA;
  --purple:   #818CF8;
  --font: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Reset ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body, [class*="css"], .stApp {
  font-family: var(--font) !important;
  background: var(--bg) !important;
  color: var(--text) !important;
  -webkit-font-smoothing: antialiased;
}

/* Dot-grid overlay (like InvestorMatch) */
html::after {
  content: '';
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image: radial-gradient(rgba(96,165,250,0.07) 1px, transparent 1px);
  background-size: 28px 28px;
}

/* ── Kill Streamlit chrome ── */
header[data-testid="stHeader"], footer,
[data-testid="stDecoration"], [data-testid="stToolbar"],
#MainMenu { display: none !important; }
.block-container { padding: 0 !important; max-width: 100% !important; }
section[data-testid="stMain"] > div { padding: 0 !important; }

/* Everything above the canvas layer */
.rb-nav, .rb-welcome, .rb-thread,
.rb-footer, [data-testid="stBottom"],
[data-testid="stHorizontalBlock"] {
  position: relative; z-index: 10;
}

/* ── Nav ── */
.rb-nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 200;
  height: 56px;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 32px;
  background: rgba(7,11,18,0.75);
  backdrop-filter: blur(24px) saturate(1.4);
  border-bottom: 1px solid var(--border);
}
.rb-nav-left { display: flex; align-items: center; gap: 10px; }
.rb-mark {
  width: 28px; height: 28px; border-radius: 7px;
  background: linear-gradient(135deg, var(--blue1) 0%, var(--blue2) 100%);
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: #fff; flex-shrink: 0;
  box-shadow: 0 4px 16px rgba(37,99,235,0.4);
}
.rb-wordmark {
  font-size: 14px; font-weight: 500; color: var(--text);
  letter-spacing: -0.02em;
}
.rb-status {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 500; color: var(--text3);
  letter-spacing: 0.04em; text-transform: uppercase;
}
.rb-dot { width: 6px; height: 6px; border-radius: 50%; background: #22C55E;
  box-shadow: 0 0 6px rgba(34,197,94,0.6); }

/* ── Welcome hero ── */
.rb-welcome {
  display: flex; flex-direction: column; align-items: center;
  padding: 20vh 24px 56px;
  text-align: center;
}

.rb-eyebrow {
  font-size: 11px; font-weight: 500;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--accent); opacity: 0.8;
  margin-bottom: 22px;
}

.rb-headline {
  font-size: clamp(38px, 6vw, 58px);
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.04em;
  line-height: 1.1;
  margin-bottom: 20px;
  max-width: 640px;
}

/* Blue gradient on the highlight span — matches InvestorMatch "entire portfolio history" */
.rb-hl {
  background: linear-gradient(135deg, var(--blue2) 0%, var(--purple) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.rb-subline {
  font-size: 16px; font-weight: 400;
  color: var(--text2); line-height: 1.65;
  max-width: 460px; margin-bottom: 20px;
}

/* Scope line — "curated, not open-ended": real counts from the index */
.rb-scope {
  display: flex; flex-wrap: wrap; justify-content: center;
  gap: 6px 16px; align-items: baseline;
  font-size: 13px; color: var(--text3);
  margin-bottom: 40px;
}
.rb-scope-total { color: var(--text2); font-weight: 600; margin-right: 4px; }
.rb-scope-item { white-space: nowrap; }

/* Subtle browse-the-library link under the chips */
.rb-browse {
  text-align: center; margin-top: 22px;
  font-size: 13px; color: var(--text3);
  position: relative; z-index: 10;
}
.rb-browse a {
  color: var(--text2); text-decoration: none;
  border-bottom: 1px solid rgba(186,205,232,0.25);
}
.rb-browse a:hover { color: var(--text); border-color: var(--accent); }

/* ── Chips ── */
[data-testid="stHorizontalBlock"]:has(button) {
  display: flex !important;
  flex-wrap: wrap !important;
  justify-content: center !important;
  gap: 8px !important;
  max-width: 720px !important;
  margin: 0 auto !important;
  padding: 0 16px !important;
}
[data-testid="stHorizontalBlock"]:has(button) [data-testid="stColumn"] {
  width: auto !important;
  flex: 0 0 auto !important;
  min-width: 0 !important;
  padding: 0 !important;
}
[data-testid="stHorizontalBlock"]:has(button) button {
  font-family: var(--font) !important;
  font-size: 13px !important; font-weight: 450 !important;
  color: var(--text2) !important;
  background: rgba(13,20,32,0.8) !important;
  border: 1px solid var(--border2) !important;
  border-radius: 24px !important;
  padding: 8px 16px !important;
  transition: all 0.18s ease !important;
  white-space: normal !important; cursor: pointer !important;  /* full questions wrap on small screens */
  max-width: min(92vw, 560px) !important;
  box-shadow: none !important;
  height: auto !important; min-height: unset !important;
  line-height: 1.45 !important;
  width: auto !important;
  backdrop-filter: blur(8px) !important;
}
[data-testid="stHorizontalBlock"]:has(button) button:hover {
  color: var(--text) !important;
  border-color: rgba(96,165,250,0.45) !important;
  background: rgba(37,99,235,0.08) !important;
  box-shadow: 0 0 16px rgba(37,99,235,0.12) !important;
}

/* ── Thread ── */
.rb-thread {
  max-width: 700px; margin: 0 auto;
  padding: 80px 24px 180px;
  display: flex; flex-direction: column; gap: 0;
}

/* Each message constrains its own width — Streamlit auto-closes wrapper divs
   across markdown calls, so a shared .rb-thread container can't do it. 700px at
   15.5px ≈ 75ch, the readable line-length target; also the mobile-safe padding. */
.rb-user, .rb-bot {
  max-width: 700px;
  margin-left: auto; margin-right: auto;
  padding-left: 24px; padding-right: 24px;
  box-sizing: content-box;
}

/* User message */
.rb-user {
  display: flex; justify-content: flex-end;
  padding-top: 20px; padding-bottom: 8px;
  animation: fadeUp 0.22s ease;
}
.rb-user-bubble {
  max-width: 72%;
  background: var(--surface2);
  border: 1px solid var(--border2);
  border-radius: 18px 18px 4px 18px;
  padding: 12px 18px;
  font-size: 15px; font-weight: 400;
  color: var(--text); line-height: 1.6;
  letter-spacing: -0.005em;
}

/* Bot message card */
.rb-bot {
  padding-top: 8px;
  animation: fadeUp 0.22s ease;
}
/* Clear the fixed nav and give the composer breathing room at the bottom */
section[data-testid="stMain"] { padding-top: 64px !important; padding-bottom: 140px !important; }
.rb-bot-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 2px solid rgba(96,165,250,0.35);
  border-radius: 12px;
  padding: 20px 22px 20px 22px;
  margin-bottom: 20px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.25);
  transition: border-left-color 0.2s;
}
.rb-bot-card:hover { border-left-color: rgba(96,165,250,0.65); }

.rb-bot-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 14px;
}
.rb-bot-mark {
  width: 22px; height: 22px; border-radius: 6px;
  background: linear-gradient(135deg, var(--blue1), var(--blue2));
  display: flex; align-items: center; justify-content: center;
  font-size: 9px; font-weight: 700; color: #fff; flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(37,99,235,0.35);
}
.rb-bot-label {
  font-size: 11px; font-weight: 500;
  color: var(--text3); letter-spacing: 0.06em; text-transform: uppercase;
}

.rb-bot-body {
  /* 15.5px on a 700px column ≈ 75 characters per line — the readable target */
  font-size: 15.5px; font-weight: 400;
  color: var(--text); line-height: 1.75;
  letter-spacing: -0.005em;
}

/* ── Resource cards ── */
.rb-res-label {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--text3);
  margin: 18px 0 10px;
}
.rb-cards {
  display: grid; grid-template-columns: 1fr;
  gap: 8px; margin: 10px 0 4px;
}
@media (min-width: 560px) {
  .rb-cards { grid-template-columns: 1fr 1fr; }
  .rb-cards > .rb-card:only-child { grid-column: 1 / -1; }
}
.rb-card {
  display: block; text-decoration: none !important;
  background: var(--surface2);
  border: 1px solid var(--border2) !important;
  border-left: 3px solid var(--card-accent) !important;
  border-radius: 10px;
  padding: 12px 14px;
  transition: border-color 0.15s ease, background 0.15s ease, transform 0.15s ease;
}
.rb-card:hover {
  background: rgba(23,33,50,0.95);
  border-color: var(--card-accent) !important;
  transform: translateY(-1px);
}
.rb-card-type {
  font-size: 10.5px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.08em; margin-bottom: 5px;
}
.rb-card-title {
  font-size: 15px; font-weight: 600; color: var(--text);
  line-height: 1.35; margin-bottom: 4px;
}
.rb-card-desc {
  font-size: 13px; color: var(--text2); line-height: 1.5;
}
.rb-card-meta {
  font-size: 12px; color: var(--text3); margin-top: 6px;
  overflow: hidden; text-overflow: ellipsis;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.rb-bot-body p { margin-bottom: 12px; }
.rb-bot-body p:last-child { margin-bottom: 0; }
.rb-bot-body strong { font-weight: 600; color: #fff; }
.rb-bot-body a {
  color: var(--accent); text-decoration: none; font-weight: 500;
  border-bottom: 1px solid rgba(96,165,250,0.25);
  transition: border-color 0.12s, color 0.12s;
}
.rb-bot-body a:hover { border-color: var(--accent); color: #fff; }
.rb-bot-body h1,.rb-bot-body h2,.rb-bot-body h3 {
  font-size: 13px !important; font-weight: 600 !important;
  color: var(--text); letter-spacing: -0.01em; text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 18px 0 8px !important;
  color: var(--text3) !important;
}
.rb-bot-body ul,.rb-bot-body ol { padding-left: 20px; margin-bottom: 12px; }
.rb-bot-body li { margin-bottom: 6px; }
.rb-bot-body code {
  font-size: 12px; font-family: "SF Mono","Fira Code",monospace;
  background: var(--surface2); border: 1px solid var(--border2);
  border-radius: 4px; padding: 1px 5px; color: var(--accent);
}

/* Typing animation */
.rb-typing {
  display: flex; gap: 4px; align-items: center; padding: 2px 0;
}
.rb-typing span {
  width: 5px; height: 5px; border-radius: 50%;
  background: var(--text3);
  animation: pulse 1.2s ease-in-out infinite;
}
.rb-typing span:nth-child(2) { animation-delay: 0.16s; }
.rb-typing span:nth-child(3) { animation-delay: 0.32s; }
@keyframes pulse {
  0%,80%,100% { opacity: 0.2; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ── Input bar ── */
[data-testid="stBottom"],
[data-testid="stBottom"] > div,
[data-testid="stChatInputContainer"],
[data-testid="stChatInputContainer"] > div {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
}
[data-testid="stBottom"] {
  background: linear-gradient(to top, #070B12 60%, transparent) !important;
  padding: 0 0 28px !important;
  z-index: 100 !important;
}
[data-testid="stChatInput"] {
  background: transparent !important;
  border: none !important;
  padding: 0 24px !important;
  max-width: 700px !important;
  margin: 0 auto !important;
  display: block !important;
  box-shadow: none !important;
}
[data-testid="stChatInput"] > div {
  background: rgba(13,20,32,0.92) !important;
  border: 1px solid var(--border2) !important;
  border-radius: 16px !important;
  padding: 0 6px !important;
  backdrop-filter: blur(20px) !important;
  box-shadow:
    0 0 0 0 transparent,
    0 8px 40px rgba(0,0,0,0.5),
    inset 0 1px 0 rgba(255,255,255,0.04) !important;
  transition: border-color 0.18s ease, box-shadow 0.18s ease !important;
}
[data-testid="stChatInput"] > div:focus-within {
  border-color: rgba(96,165,250,0.45) !important;
  box-shadow:
    0 0 0 3px rgba(37,99,235,0.10),
    0 8px 40px rgba(0,0,0,0.5),
    inset 0 1px 0 rgba(255,255,255,0.04) !important;
}
[data-testid="stChatInput"] textarea {
  font-family: var(--font) !important;
  font-size: 15px !important; font-weight: 400 !important;
  color: var(--text) !important; letter-spacing: -0.01em !important;
  background: transparent !important;
  border: none !important; box-shadow: none !important;
  caret-color: var(--accent) !important;
  padding: 16px 14px !important; line-height: 1.5 !important;
}
[data-testid="stChatInput"] textarea::placeholder {
  color: rgba(100,130,165,0.4) !important; font-weight: 400 !important;
}
button[data-testid="stChatInputSubmitButton"] {
  background: linear-gradient(135deg, var(--blue1) 0%, var(--blue2) 100%) !important;
  border-radius: 50% !important; margin: 8px !important;
  width: 34px !important; height: 34px !important;
  min-width: 34px !important; min-height: 34px !important;
  color: #fff !important; opacity: 1 !important;
  box-shadow: 0 2px 14px rgba(37,99,235,0.5) !important;
  transition: opacity 0.15s, transform 0.12s !important;
  border: none !important;
  display: flex !important; align-items: center !important; justify-content: center !important;
}
button[data-testid="stChatInputSubmitButton"]:hover {
  opacity: 0.88 !important; transform: scale(1.07) !important;
}
button[data-testid="stChatInputSubmitButton"]:disabled {
  background: #1a2030 !important; box-shadow: none !important;
}
button[data-testid="stChatInputSubmitButton"] svg { fill: #fff !important; }

/* Hide native Streamlit chat bubbles */
[data-testid="stChatMessage"] { display: none !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(96,165,250,0.15); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(96,165,250,0.3); }

/* Footer */
.rb-footer {
  font-size: 11px; color: var(--text3);
  text-align: center; padding: 6px 0 0;
  letter-spacing: 0.02em;
}
.rb-footer a { color: var(--text3); text-decoration: none; transition: color 0.15s; }
.rb-footer a:hover { color: var(--accent); }
</style>
""", unsafe_allow_html=True)

# Inject parallax particles + mouse-glow (runs once, guards against double-inject on rerun)
st.markdown("""
<script>
(function() {
  if (document.getElementById('rb-particles')) return;

  // ── Floating particle canvas ──────────────────────────────────────────────
  const canvas = document.createElement('canvas');
  canvas.id = 'rb-particles';
  canvas.style.cssText =
    'position:fixed;top:0;left:0;width:100vw;height:100vh;' +
    'z-index:1;pointer-events:none;';
  document.body.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  function resize() {
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  const N = 65;
  const pts = Array.from({length: N}, () => ({
    x:  Math.random() * window.innerWidth,
    y:  Math.random() * window.innerHeight,
    r:  Math.random() * 1.1 + 0.25,
    vx: (Math.random() - 0.5) * 0.18,
    vy: (Math.random() - 0.5) * 0.18,
    a:  Math.random() * 0.35 + 0.08,
  }));

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const p of pts) {
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(96,165,250,' + p.a + ')';
      ctx.fill();
      p.x += p.vx;  p.y += p.vy;
      if (p.x < -4) p.x = canvas.width  + 4;
      if (p.x > canvas.width  + 4) p.x = -4;
      if (p.y < -4) p.y = canvas.height + 4;
      if (p.y > canvas.height + 4) p.y = -4;
    }
    requestAnimationFrame(draw);
  }
  draw();

  // ── Mouse-tracking glow (parallax feel) ──────────────────────────────────
  const glow = document.createElement('div');
  glow.id = 'rb-glow';
  glow.style.cssText =
    'position:fixed;width:700px;height:700px;border-radius:50%;' +
    'pointer-events:none;z-index:2;' +
    'background:radial-gradient(ellipse,rgba(37,99,235,0.11) 0%,transparent 68%);' +
    'transform:translate(-50%,-50%);' +
    'transition:left 1s cubic-bezier(.25,.46,.45,.94),' +
               'top 1s cubic-bezier(.25,.46,.45,.94);' +
    'left:50%;top:42%;';
  document.body.appendChild(glow);

  let mx = window.innerWidth / 2, my = window.innerHeight * 0.42;
  document.addEventListener('mousemove', e => {
    mx = e.clientX; my = e.clientY;
    glow.style.left = mx + 'px';
    glow.style.top  = my + 'px';
  });

  // ── Scroll parallax on hero text ─────────────────────────────────────────
  const scrollContainer =
    document.querySelector('[data-testid="stAppViewContainer"]') || window;

  function onScroll() {
    const y = scrollContainer.scrollTop || window.scrollY || 0;
    const hero = document.querySelector('.rb-welcome');
    if (hero) hero.style.transform = 'translateY(' + (y * 0.28) + 'px)';
    // dots grid also drifts — via the ::after on html we can't easily move,
    // so instead shift the glow slightly for depth
    glow.style.top = (my + y * 0.12) + 'px';
  }
  scrollContainer.addEventListener('scroll', onScroll, {passive: true});
})();
</script>
""", unsafe_allow_html=True)

# ── Password gate ──────────────────────────────────────────────────────────────
GATE = os.environ.get("ACCESS_PASSWORD") or _secret("ACCESS_PASSWORD")
if GATE and st.session_state.get("ok") is not True:
    st.markdown("""
<div style="min-height:100dvh;display:flex;flex-direction:column;
            align-items:center;justify-content:center;gap:16px;padding:40px;
            background:#070B12;">
  <div style="width:36px;height:36px;border-radius:9px;
              background:linear-gradient(135deg,#2563EB,#60A5FA);
              display:flex;align-items:center;justify-content:center;
              box-shadow:0 4px 20px rgba(37,99,235,0.4);">
    <span style="color:#fff;font-weight:700;font-size:14px;">R</span>
  </div>
  <div style="font-size:16px;font-weight:500;color:#EEF2F7;letter-spacing:-0.02em;">ReachBot</div>
  <div style="font-size:12px;color:rgba(100,130,165,0.5);">Reach Capital · Portfolio Founders</div>
</div>
""", unsafe_allow_html=True)
    pw = st.text_input("", type="password", placeholder="Access password",
                       label_visibility="collapsed")
    if pw and pw == GATE:
        st.session_state.ok = True
        st.rerun()
    elif pw:
        st.error("Incorrect password.")
    st.stop()

# ── Index ──────────────────────────────────────────────────────────────────────
@st.cache_resource
def load_index():
    d = np.load("index.npz", allow_pickle=True)
    v = d["vectors"].astype(np.float32)
    v /= (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)
    cats = d["categories"] if "categories" in d.files \
        else np.array([""] * len(d["chunks"]), dtype=object)
    return v, d["chunks"], d["titles"], d["urls"], cats

MIN_BODY_CHARS = 120  # skip pure nav stubs / empty pages

# Perk/discount/partnership questions should answer ONLY from the partner-deals
# page, not pull in tangential pages. Detect intent + restrict the candidate pool.
PERK_CATEGORY = "Partner Access, Credits, Discounts"
PERK_KEYWORDS = (
    "discount", "credit", "perk", "coupon", "promo", "voucher", "redeem",
    "% off", "percent off", "free month", "free trial", "partner offer",
    "partner deal", "partner discount", "partnership offer", "exclusive deal",
)

def _is_perk_query(q):
    ql = q.lower()
    return any(k in ql for k in PERK_KEYWORDS)

def retrieve(query, vectors, chunks, titles, urls, categories):
    r = _client.models.embed_content(model=EMBED_MODEL, contents=query)
    q = np.array(r.embeddings[0].values, dtype=np.float32)
    q /= (np.linalg.norm(q) + 1e-9)
    scores = vectors @ q

    # For perk/discount/partnership queries, only consider partner-deal chunks.
    perk = _is_perk_query(query)
    def allowed(i):
        if not perk:
            return True
        return categories[i] == PERK_CATEGORY or PERK_CATEGORY.lower() in str(chunks[i]).lower()

    # Walk candidates in score order, skip thin/empty chunks
    results = []
    for i in np.argsort(-scores):
        if not allowed(i):
            continue
        raw = chunks[i].strip()
        # Strip the title line(s) — real body is everything after the first heading
        body_lines = [l for l in raw.split('\n')[1:] if l.strip()]
        body = '\n'.join(body_lines).strip()
        if len(body) < MIN_BODY_CHARS:
            continue   # nav stub, empty AMA header, etc.
        results.append((raw, str(titles[i]), str(urls[i]), str(categories[i])))
        if len(results) >= TOP_K:
            break
    return results

def standalone_query(question, history):
    """Rewrite a follow-up ("more on that", "who ran it?") into a self-contained
    retrieval query using the chat so far. Falls back to the raw question."""
    if not history:
        return question
    convo = "\n".join(
        f"{'User' if entry[0] == 'user' else 'ReachBot'}: {entry[1][:500]}"
        for entry in history[-6:]
    )
    try:
        resp = _client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=(
                "Rewrite the user's latest message as ONE self-contained search query "
                "for a knowledge base, resolving pronouns and references from the "
                "conversation. If it is already self-contained, return it unchanged. "
                "Output only the query, nothing else.\n\n"
                f"Conversation:\n{convo}\n\nLatest message: {question}"
            ),
        )
        q = (resp.text or "").strip()
        return q if 0 < len(q) < 400 else question
    except Exception:
        return question

def generate(context, question, history=()):
    import re as _re, time as _time
    system = """You are ReachBot, an assistant for Reach Capital's portfolio founders.
Answer exclusively from the ReachIn context provided. Never fabricate facts or links.

CONTEXT FORMAT: Each block starts with [Title](NotionURL) then the page content.
The content may contain **Link:** or **Files & media:** fields with direct resource URLs.
The context may include Reach Capital Network Profiles for advisors, consultants, scouts, and media contacts — use these to answer questions about who is in the Reach network.

STEP 1 — CLASSIFY, THEN ANSWER. Silently route every query into exactly ONE response
type below and follow its structure. Do not name the type in your answer.

1. RESOURCE-FIRST — the user wants one specific fact or artifact (a code, a date, a
   contact, a named doc). Structure: one clause of prose (max 20 words), then 1–3
   resource links. The linked line carries the detail; do NOT repeat in prose a fact
   (code, date, contact, stat) that already appears on the resource line.
2. SUMMARY-FIRST — the user wants interpretation or synthesis. Structure: the direct
   answer in the FIRST sentence, then supporting detail with inline citations woven
   into sentences ("...according to Maria's AMA"). One source: 40–80 words. Multiple
   sources: 80–150 words, citing at most 3 by name — name the two strongest and add
   "and a few others" if more apply. Never stack 5 citations in one paragraph.
3. BROWSE / ENUMERATE — the user wants a menu, not an answer. Trigger on breadth
   PHRASING ("what do you have on...", "show me all...", "everything related to..."),
   not on topic. Structure: a list of [Title](URL) lines with one short descriptor
   each, NO synthesis. Past ~8 results, show the strongest 8 and end with "want the
   full list?". A specific single-answer question is never enumerate.
4. NOT-FOUND — nothing in the context covers it. State the gap plainly in 1–2
   sentences. NEVER fill the gap with general AI knowledge disguised as a
   knowledge-base answer; if general knowledge would genuinely help, label it
   explicitly ("Outside the ReachIn knowledge base: ...").
5. LOW-CONFIDENCE / PARTIAL MATCH — the context is adjacent but doesn't directly
   answer. Answer only what's supported and flag the mismatch ("The closest resource
   covers X, not exactly what you asked"). Don't overstate relevance.
6. CONFLICTING SOURCES — two sources disagree (old vs. new report, two advisors).
   Surface both, attribute each, note recency if relevant. Never silently average
   the numbers or pick a winner.
7. DISAMBIGUATION — ask a clarifying question ONLY when ALL three hold: (a) answering
   the most likely interpretation would be WRONG (not just broader), (b) the query maps
   to 2+ specific named resources with materially different answers, (c) no reasonable
   default exists. Then ask ONE question offering the concrete named options. If any
   condition fails, answer with the most reasonable default and state the assumption in
   one clause ("using the most recent (Q2 2026) report..."). Never stack questions.
8. OUT-OF-SCOPE REDIRECT — the question belongs to a different tool or isn't
   knowledge-base material. Name what's actually needed and point there; don't force
   an answer from the wrong source.
9. META / CAPABILITY — "what can you help with?" / "what's in here?". Answer with the
   actual knowledge-base categories: AMA & session recordings, reports & research,
   articles & good reads, advisors/consultants/media contacts, partner credits &
   discounts.

STALENESS (applies to any type): if the best available source may be outdated
(an old vintage or a superseded report), append a short trailing caveat
("— from the 2023 report, the most recent in ReachIn"), never a blocking disclaimer.

LENGTH DISCIPLINE:
- Hard ceiling ~150 words of prose unless the user explicitly asked for depth
  ("walk me through", "compare", "give me the full picture").
- Length tracks evidence density, not completeness: a single thin data point gets a
  short honest answer, not padding.
- End with an opt-in next step ("Want the full report?") rather than front-loading
  every possible angle.

RULES:
- Only cite a source if it contains substantive information relevant to the question.
  Do NOT cite a page that only has a title with no real body content.
- If an AMA page has no notes or transcript content, do not pretend to know what was discussed.
  You may mention the AMA exists and link to it, but do not summarize it.
- ALWAYS format every link as markdown: [Descriptive Title](https://url.here)
  Never output a bare URL — always wrap it in [text](url) format.
- When you name a specific person or entity that came from the network — an advisor,
  consultant, coach, scout, media contact, or partner/credit — hyperlink their NAME to
  their Notion source_url the FIRST time you mention them in the answer body, e.g.
  "[Myerhoff Consulting](https://www.notion.so/...) — sales strategy, fractional CRO".
  These profile pages ARE valid sources; every named profile must be clickable, not just
  the articles and recordings.
- For deck/slide links: prefer linking to the Notion page (source_url) rather than raw S3/PDF URLs,
  which expire. You may mention "includes slides" or "includes deck" in the description.
  Only use a direct PDF/S3 URL if no Notion page URL is available.
- When a retrieved Notion page's own content is minimal (a title, a tag, and a single
  outbound link with little original framing), cite and link the EXTERNAL source
  directly instead of the Notion page. If the Notion page includes original commentary,
  curation notes, or context beyond the link, prefer the Notion page — that framing is
  part of the citation's value.
- Attribution stays consistent regardless of where a link points: describe external
  destinations as coming via ReachIn's own categorization ("via ReachIn's Fundraising
  resources"), never as something you found on the open web.
- Inline citations are always present, separate from any resource list: every claim
  gets a citation woven into its sentence ("...according to Maria's AMA"), whether or
  not the source also appears as a resource line.

FORMATTING: use short paragraphs or bulleted lists with a blank line between items.
Quote AMA speakers when transcript content exists. For RESOURCE-FIRST and SUMMARY-FIRST
answers, end with a single **Resources** list (max 3 entries: the sources you used,
plus a related pick if genuinely useful) — [Page Title](URL) — one sentence each. Do
not split into separate "Sources" and "Explore more" sections. BROWSE, NOT-FOUND, and
META answers need no Resources section (the list, gap, or category overview IS the
answer)."""
    # Include recent chat turns so follow-ups ("summarize the second one",
    # "more like that") resolve. The Context block always applies to the
    # LATEST question; earlier turns are conversational grounding only.
    turns = [
        {"role": "user" if entry[0] == "user" else "model", "parts": [{"text": entry[1][:4000]}]}
        for entry in list(history)[-6:]
    ]
    turns.append({"role": "user",
                  "parts": [{"text": f"Context:\n{context}\n\nQuestion: {question}"}]})
    for model in [CHAT_MODEL, "gemini-2.5-flash-lite", "gemini-2.5-flash"]:
        try:
            resp = _client.models.generate_content(
                model=model,
                contents=turns,
                config=genai.types.GenerateContentConfig(system_instruction=system),
            )
            return resp.text
        except Exception as e:
            err = str(e)
            if "503" in err or "UNAVAILABLE" in err:
                continue  # try next model
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                # Extract retry delay if present (e.g. "retryDelay': '18s'")
                m = _re.search(r"retry[^']*'(\d+)s'", err)
                wait = int(m.group(1)) if m else 20
                # Check if it's a daily quota (won't recover in seconds)
                if "PerDay" in err or "limit: 0" in err:
                    return (
                        "_Your Gemini free-tier **daily quota** is exhausted._ "
                        "To fix this, enable billing on your Google AI project at "
                        "[aistudio.google.com](https://aistudio.google.com) — "
                        "it's pay-as-you-go and costs pennies for typical usage. "
                        "Alternatively, try again tomorrow when the quota resets."
                    )
                _time.sleep(wait)
                continue  # retry after per-minute quota clears
            raise
    return "_Gemini is temporarily unavailable — please try again in a moment._"

# ── Resource cards (per-type identity — see backend/resource_types.py) ────────
import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
from resource_types import classify
from resource_fields import parse_fields

# icon, accent color, label — one identity per resource shape, reused on chips,
# cards, and enumerate lists so users can pattern-match source type at a glance.
TYPE_META = {
    "article": ("📄", "#7EB6FF", "Article"),
    "report":  ("📊", "#A5AFFB", "Report"),
    "contact": ("👤", "#4ADE9E", "Contact"),
    "ama":     ("🎙️", "#FBBF24", "AMA"),
    "deal":    ("🎁", "#F97FBC", "Deal"),
}

# Which parsed fields a card shows, per type (order = display order).
CARD_FIELDS = {
    "deal":    ("offer", "contact", "email", "reach_point"),
    "contact": ("role", "specialty", "contact_info"),
    "ama":     ("speaker", "date", "tags"),
    "report":  ("publisher", "sector", "tags"),
    "article": ("publisher", "sector"),
}

def build_srcmap(hits):
    """Map url AND title → type/fields for every retrieved hit, so the renderer
    can type any resource the model cites."""
    m = {}
    for chunk, title, url, cat in hits:
        rtype = classify(title, cat)
        entry = {"type": rtype, "fields": parse_fields(chunk, rtype), "category": cat}
        m.setdefault(url, entry)
        m.setdefault(title.casefold(), entry)
    return m

_RES_LINE = re.compile(r'^\s*[-\*]\s*\[([^\]]+)\]\(([^)]+)\)\s*(?:[—–:-]\s*)?(.*)$')
_RES_HEADER = re.compile(r'^\s*(?:#{1,3}\s*)?\*{0,2}Resources:?\*{0,2}\s*$', re.IGNORECASE)

def _card_html(title, url, desc, meta):
    icon, color, label = TYPE_META.get(meta["type"], TYPE_META["article"])
    fields = meta.get("fields", {})
    bits = [str(fields[k]) for k in CARD_FIELDS.get(meta["type"], ()) if fields.get(k)][:3]
    meta_line = f'<div class="rb-card-meta">{" · ".join(bits)}</div>' if bits else ""
    desc_html = f'<div class="rb-card-desc">{desc}</div>' if desc else ""
    return f'''<a class="rb-card" style="--card-accent:{color}" href="{url}" target="_blank">
  <div class="rb-card-type" style="color:{color}">{icon}&nbsp; {label}</div>
  <div class="rb-card-title">{title}</div>
  {desc_html}{meta_line}
</a>'''

def render_answer(md, srcmap):
    """Prose renders as before; any run of '- [Title](url) — desc' lines becomes a
    grid of typed resource cards (this covers both the Resources tail and
    browse/enumerate answers — the latter is intentionally uncapped)."""
    segments, prose, cards = [], [], []
    def flush_prose():
        if prose:
            segments.append(md_to_html("\n".join(prose))); prose.clear()
    def flush_cards():
        if cards:
            segments.append('<div class="rb-cards">' + "".join(cards) + "</div>"); cards.clear()
    for line in md.split("\n"):
        m = _RES_LINE.match(line)
        if m:
            title, url, desc = m.group(1), m.group(2), re.sub(r'\*\*(.+?)\*\*', r'\1', m.group(3)).strip()
            meta = srcmap.get(url) or srcmap.get(title.casefold()) \
                   or {"type": classify(title, ""), "fields": {}}
            flush_prose()
            cards.append(_card_html(title, url, desc, meta))
        elif _RES_HEADER.match(line):
            flush_prose(); flush_cards()
            segments.append('<div class="rb-res-label">Resources</div>')
        else:
            flush_cards()
            prose.append(line)
    flush_prose(); flush_cards()
    return "\n".join(segments)

def md_to_html(md):
    # Bold
    md = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', md)
    # Markdown links [text](url) → <a>
    md = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', md)
    # Bare URLs not already inside an href — convert to clickable links
    md = re.sub(
        r'(?<!href=")(https?://[^\s<>"\)]+)',
        lambda m: f'<a href="{m.group(1)}" target="_blank">{m.group(1)}</a>',
        md
    )
    # Headings
    md = re.sub(r'^### (.+)$', r'<h3>\1</h3>', md, flags=re.MULTILINE)
    md = re.sub(r'^## (.+)$',  r'<h2>\1</h2>', md, flags=re.MULTILINE)
    md = re.sub(r'^# (.+)$',   r'<h1>\1</h1>', md, flags=re.MULTILINE)
    # Lists (both - and * bullets — the model emits either)
    md = re.sub(r'^[\-\*] (.+)$',  r'<li>\1</li>', md, flags=re.MULTILINE)
    md = re.sub(r'(<li>.*?</li>(\n|$))+', lambda m: f'<ul>{m.group(0)}</ul>', md, flags=re.DOTALL)
    # Paragraphs
    paras = [p.strip() for p in re.split(r'\n{2,}', md.strip()) if p.strip()]
    out = []
    for p in paras:
        if p.startswith(('<h','<ul','<li','<a ')):
            out.append(p)
        else:
            out.append(f'<p>{p}</p>')
    return '\n'.join(out)

vectors, chunks, titles, urls, categories = load_index()

# The ReachIn hub on Notion — the browsable home of everything the bot indexes.
REACHIN_HUB = "https://app.notion.com/p/ReachIn-1499d627cdb04c81a3e48c1f31f83199"

@st.cache_resource
def scope_counts():
    """Unique-source counts by resource type (deduped by title, so it reflects
    pages, not chunks) — shown on the empty state to make the bot's bounds legible."""
    seen, counts = set(), {}
    for t, c in zip(titles, categories):
        key = str(t)
        if key in seen:
            continue
        seen.add(key)
        rtype = classify(str(t), str(c))
        counts[rtype] = counts.get(rtype, 0) + 1
    return len(seen), counts

def scope_line_html():
    total, counts = scope_counts()
    order = [("ama", "AMAs"), ("report", "reports"), ("article", "articles"),
             ("contact", "contacts"), ("deal", "deals")]
    parts = []
    for rtype, noun in order:
        n = counts.get(rtype, 0)
        if n:
            icon = TYPE_META[rtype][0]
            parts.append(f'<span class="rb-scope-item">{icon}&thinsp;{n} {noun}</span>')
    return f'<span class="rb-scope-total">{total:,} sources</span>' + "".join(parts)

# ── Nav ────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="rb-nav">
  <div class="rb-nav-left">
    <div class="rb-mark">R</div>
    <span class="rb-wordmark">ReachBot</span>
  </div>
  <div class="rb-status">
    <span class="rb-dot"></span>
    ReachIn · Portfolio
  </div>
</div>
""", unsafe_allow_html=True)

# ── State ──────────────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "prefill" not in st.session_state:
    st.session_state.prefill = None

# ── Welcome ────────────────────────────────────────────────────────────────────
# Chips are full example QUESTIONS (not topics) — they teach phrasing and set
# depth expectations. Each carries its expected resource-type icon.
CHIPS = [
    "🎙️ What are the biggest GTM mistakes early-stage EdTech founders make?",
    "🎁 What's the AWS credit for portfolio companies, and how do I redeem it?",
    "👤 Who in the Reach network can help me with K-12 district sales?",
    "📊 What benchmarks should a seed-stage EdTech startup hit before Series A?",
    "📄 What do you have on seed fundraising?",
    "🎙️ How should I structure comp when hiring my first sales leader?",
]

if not st.session_state.history:
    st.markdown(f"""
<div class="rb-welcome">
  <div class="rb-eyebrow">ReachIn Assistant</div>
  <div class="rb-headline">
    What resource can<br>I help you <span class="rb-hl">find?</span>
  </div>
  <div class="rb-subline">
    Search ReachIn's curated knowledge base — AMA recordings, research and
    reports, advisor and media contacts, and partner deals. Every answer
    links back to its source.
  </div>
  <div class="rb-scope">{scope_line_html()}</div>
</div>
""", unsafe_allow_html=True)

    # Chips — real Streamlit buttons re-flowed into pill row via CSS
    st.markdown('<div id="rb-chip-row">', unsafe_allow_html=True)
    cols = st.columns(len(CHIPS))
    for i, chip in enumerate(CHIPS):
        with cols[i]:
            if st.button(chip, key=f"chip_{i}"):
                # Send the question without its type icon
                st.session_state.prefill = chip.split(" ", 1)[1]
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Subtle path into the underlying knowledge base — browsable, not a CTA.
    st.markdown(f"""
<div class="rb-browse">
  Or <a href="{REACHIN_HUB}" target="_blank">browse the ReachIn library on Notion&nbsp;↗</a>
</div>
""", unsafe_allow_html=True)

# ── Conversation ───────────────────────────────────────────────────────────────
else:
    st.markdown('<div class="rb-thread">', unsafe_allow_html=True)
    for entry in st.session_state.history:
        role, text = entry[0], entry[1]
        srcmap = entry[2] if len(entry) > 2 and entry[2] else {}
        if role == "user":
            st.markdown(f"""
<div class="rb-user">
  <div class="rb-user-bubble">{text}</div>
</div>""", unsafe_allow_html=True)
        else:
            body = render_answer(text, srcmap)
            st.markdown(f"""
<div class="rb-bot">
  <div class="rb-bot-card">
    <div class="rb-bot-header">
      <div class="rb-bot-mark">R</div>
      <span class="rb-bot-label">ReachBot</span>
    </div>
    <div class="rb-bot-body">{body}</div>
  </div>
</div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="rb-footer">
  Answers from ReachIn only &nbsp;·&nbsp;
  <a href="https://reachcapital.com" target="_blank">Reach Capital</a>
</div>
""", unsafe_allow_html=True)

# ── Input ──────────────────────────────────────────────────────────────────────
_prefill = st.session_state.pop("prefill", None) if st.session_state.get("prefill") else None
if _prefill:
    prompt = _prefill
elif prompt := st.chat_input("Ask anything about ReachIn…"):
    pass
else:
    prompt = None

if prompt:
    st.markdown(f"""
<div style="max-width:700px;margin:0 auto;padding:0 24px;">
  <div class="rb-user">
    <div class="rb-user-bubble">{prompt}</div>
  </div>
</div>""", unsafe_allow_html=True)

    ph = st.empty()
    ph.markdown("""
<div style="max-width:700px;margin:0 auto;padding:0 24px;">
  <div class="rb-bot">
    <div class="rb-bot-card">
      <div class="rb-bot-header">
        <div class="rb-bot-mark">R</div>
        <span class="rb-bot-label">ReachBot</span>
      </div>
      <div class="rb-typing"><span></span><span></span><span></span></div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    search_q = standalone_query(prompt, st.session_state.history)
    hits    = retrieve(search_q, vectors, chunks, titles, urls, categories)
    context = "\n\n---\n\n".join(f"[{t}]({u})\n{c}" for c, t, u, _cat in hits)
    answer  = generate(context, prompt, st.session_state.history)
    ph.empty()

    st.session_state.history.append(("user", prompt, None))
    st.session_state.history.append(("assistant", answer, build_srcmap(hits)))
    st.rerun()
