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
  --text2:    rgba(170,195,230,0.55);
  --text3:    rgba(100,130,165,0.40);
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
  font-size: 15px; font-weight: 400;
  color: var(--text2); line-height: 1.65;
  max-width: 400px; margin-bottom: 52px;
}

/* ── Chips ── */
[data-testid="stHorizontalBlock"]:has(button) {
  display: flex !important;
  flex-wrap: wrap !important;
  justify-content: center !important;
  gap: 8px !important;
  max-width: 640px !important;
  margin: 0 auto !important;
}
[data-testid="stHorizontalBlock"]:has(button) [data-testid="stColumn"] {
  width: auto !important;
  flex: 0 0 auto !important;
  min-width: 0 !important;
  padding: 0 !important;
}
[data-testid="stHorizontalBlock"]:has(button) button {
  font-family: var(--font) !important;
  font-size: 12px !important; font-weight: 400 !important;
  color: var(--text2) !important;
  background: rgba(13,20,32,0.8) !important;
  border: 1px solid var(--border2) !important;
  border-radius: 24px !important;
  padding: 7px 16px !important;
  transition: all 0.18s ease !important;
  white-space: nowrap !important; cursor: pointer !important;
  box-shadow: none !important;
  height: auto !important; min-height: unset !important;
  line-height: 1.4 !important;
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

/* User message */
.rb-user {
  display: flex; justify-content: flex-end;
  padding: 20px 0 8px;
  animation: fadeUp 0.22s ease;
}
.rb-user-bubble {
  max-width: 72%;
  background: var(--surface2);
  border: 1px solid var(--border2);
  border-radius: 18px 18px 4px 18px;
  padding: 12px 18px;
  font-size: 14px; font-weight: 400;
  color: var(--text); line-height: 1.6;
  letter-spacing: -0.005em;
}

/* Bot message card */
.rb-bot {
  padding: 8px 0 0;
  animation: fadeUp 0.22s ease;
}
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
  font-size: 14px; font-weight: 400;
  color: var(--text); line-height: 1.8;
  letter-spacing: -0.005em;
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
        results.append((raw, str(titles[i]), str(urls[i])))
        if len(results) >= TOP_K:
            break
    return results

def generate(context, question):
    import re as _re, time as _time
    system = """You are ReachBot, an assistant for Reach Capital's portfolio founders.
Answer exclusively from the ReachIn context provided. Never fabricate facts or links.

CONTEXT FORMAT: Each block starts with [Title](NotionURL) then the page content.
The content may contain **Link:** or **Files & media:** fields with direct resource URLs.
The context may include Reach Capital Network Profiles for advisors, consultants, scouts, and media contacts — use these to answer questions about who is in the Reach network.

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

Structure every response:
1. **Direct answer** — specific, practical, with each key point on its own line. Use numbered or bulleted lists with a blank line between each item for readability. Quote AMA speakers if transcript content exists.
2. **Resources** — combine sources used AND 2-3 related resources into one unified list. For each, output: [Page Title](URL) — one sentence on what it covers. Do not split into separate "Sources" and "Explore more" sections.

If the context doesn't cover the question well, say so honestly."""
    for model in [CHAT_MODEL, "gemini-2.5-flash-lite", "gemini-2.5-flash"]:
        try:
            resp = _client.models.generate_content(
                model=model,
                contents=f"Context:\n{context}\n\nQuestion: {question}",
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
    # Lists
    md = re.sub(r'^\- (.+)$',  r'<li>\1</li>', md, flags=re.MULTILINE)
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
CHIPS = [
    "K–12 sales strategy",
    "Seed fundraising",
    "Hiring your first AE",
    "GTM mistakes to avoid",
    "EdTech benchmarks",
    "Partner discounts",
    "AI in education",
    "Scaling B2B sales",
]

if not st.session_state.history:
    st.markdown("""
<div class="rb-welcome">
  <div class="rb-eyebrow">ReachIn Assistant</div>
  <div class="rb-headline">
    What do you need<br>to <span class="rb-hl">build?</span>
  </div>
  <div class="rb-subline">
    Ask about AMAs, research, advisors, benchmarks, or partner discounts.
    I'll find it and link you back to the source.
  </div>
</div>
""", unsafe_allow_html=True)

    # Chips — real Streamlit buttons re-flowed into pill row via CSS
    st.markdown('<div id="rb-chip-row">', unsafe_allow_html=True)
    cols = st.columns(len(CHIPS))
    for i, chip in enumerate(CHIPS):
        with cols[i]:
            if st.button(chip, key=f"chip_{i}"):
                st.session_state.prefill = chip
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ── Conversation ───────────────────────────────────────────────────────────────
else:
    st.markdown('<div class="rb-thread">', unsafe_allow_html=True)
    for role, text in st.session_state.history:
        if role == "user":
            st.markdown(f"""
<div class="rb-user">
  <div class="rb-user-bubble">{text}</div>
</div>""", unsafe_allow_html=True)
        else:
            body = md_to_html(text)
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

    hits    = retrieve(prompt, vectors, chunks, titles, urls, categories)
    context = "\n\n---\n\n".join(f"[{t}]({u})\n{c}" for c, t, u in hits)
    answer  = generate(context, prompt)
    ph.empty()

    st.session_state.history.append(("user", prompt))
    st.session_state.history.append(("assistant", answer))
    st.rerun()
