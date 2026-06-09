#!/usr/bin/env python3
"""ReachBot — Reach Capital's AI assistant for portfolio founders."""
import os
import numpy as np
import streamlit as st
from google import genai

EMBED_MODEL = "gemini-embedding-001"
CHAT_MODEL  = "gemini-2.5-flash"
TOP_K       = 12

def _secret(key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

API_KEY = os.environ.get("GEMINI_API_KEY") or _secret("GEMINI_API_KEY")
_client = genai.Client(api_key=API_KEY)

st.set_page_config(
    page_title="ReachBot",
    page_icon="🟢",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─── Global styles ────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,300;0,14..32,400;0,14..32,500;0,14..32,600;1,14..32,400&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"], .stApp {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background: #F5F5F3 !important;
  color: #111;
}

/* Kill default Streamlit chrome */
header[data-testid="stHeader"],
footer { display: none !important; }
.block-container {
  padding: 0 !important;
  max-width: 100% !important;
}
section[data-testid="stMain"] > div { padding: 0 !important; }

/* ── Layout shell ── */
.rb-shell {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  max-width: 760px;
  margin: 0 auto;
}

/* ── Top nav ── */
.rb-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px 16px;
  border-bottom: 1px solid rgba(0,0,0,0.07);
  background: rgba(245,245,243,0.9);
  backdrop-filter: blur(12px);
  position: sticky;
  top: 0;
  z-index: 50;
}
.rb-nav-left { display: flex; align-items: center; gap: 10px; }
.rb-logo {
  width: 28px; height: 28px;
  background: #1A6B55;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 700; color: white;
  letter-spacing: -0.5px;
  flex-shrink: 0;
}
.rb-brand { font-size: 15px; font-weight: 600; color: #111; letter-spacing: -0.2px; }
.rb-brand span { color: #1A6B55; }
.rb-badge {
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #6B8F85;
  background: #E8F3F0;
  padding: 3px 8px;
  border-radius: 20px;
}

/* ── Messages area ── */
.rb-messages {
  flex: 1;
  overflow-y: auto;
  padding: 28px 24px 8px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  scroll-behavior: smooth;
}

/* ── Empty / welcome state ── */
.rb-welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  text-align: center;
  gap: 12px;
}
.rb-welcome-icon {
  width: 52px; height: 52px;
  background: linear-gradient(135deg, #1A6B55 0%, #2E9E7A 100%);
  border-radius: 16px;
  display: flex; align-items: center; justify-content: center;
  font-size: 24px;
  margin-bottom: 4px;
  box-shadow: 0 8px 24px rgba(26,107,85,0.2);
}
.rb-welcome h2 {
  font-size: 22px !important;
  font-weight: 600 !important;
  color: #111 !important;
  margin: 0 !important;
  letter-spacing: -0.4px;
}
.rb-welcome p {
  font-size: 14px;
  color: #666;
  max-width: 380px;
  line-height: 1.6;
  margin: 0;
}

/* Suggestion cards grid */
.rb-suggestions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  width: 100%;
  max-width: 520px;
  margin-top: 16px;
}
.rb-sug-card {
  background: #fff;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 12px;
  padding: 12px 14px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.rb-sug-card:hover {
  border-color: #1A6B55;
  box-shadow: 0 2px 12px rgba(26,107,85,0.1);
}
.rb-sug-card .sug-icon { font-size: 16px; margin-bottom: 6px; }
.rb-sug-card .sug-text { font-size: 12.5px; color: #333; font-weight: 500; line-height: 1.4; }
.rb-sug-card .sug-sub  { font-size: 11px; color: #999; margin-top: 2px; line-height: 1.3; }

/* ── Individual messages ── */
.rb-msg {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  animation: fadeUp 0.2s ease;
}
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.rb-msg.user {
  flex-direction: row-reverse;
}
.rb-avatar {
  width: 30px; height: 30px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 600;
}
.rb-avatar.bot {
  background: linear-gradient(135deg, #1A6B55, #2E9E7A);
  color: white;
}
.rb-avatar.user {
  background: #E8E8E6;
  color: #444;
}
.rb-bubble {
  max-width: 88%;
  padding: 12px 16px;
  border-radius: 18px;
  font-size: 14px;
  line-height: 1.65;
  color: #1A1A1A;
}
.rb-bubble.bot {
  background: #FFFFFF;
  border: 1px solid rgba(0,0,0,0.07);
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.rb-bubble.user {
  background: #1A6B55;
  color: #fff;
  border-bottom-right-radius: 4px;
}
.rb-bubble.bot a { color: #1A6B55; font-weight: 500; }
.rb-bubble.bot strong { font-weight: 600; color: #111; }
.rb-bubble.bot h1,
.rb-bubble.bot h2,
.rb-bubble.bot h3 { font-size: 14px !important; font-weight: 600 !important; margin: 8px 0 4px !important; }

/* ── Typing indicator ── */
.rb-typing { display: flex; gap: 4px; align-items: center; padding: 4px 2px; }
.rb-typing span {
  width: 7px; height: 7px;
  background: #ccc;
  border-radius: 50%;
  animation: bounce 1.2s infinite;
}
.rb-typing span:nth-child(2) { animation-delay: 0.2s; }
.rb-typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-5px); }
}

/* ── Input bar ── */
.rb-input-wrap {
  padding: 12px 24px 20px;
  background: #F5F5F3;
  border-top: 1px solid rgba(0,0,0,0.06);
}
.rb-input-inner {
  display: flex;
  align-items: center;
  background: #fff;
  border: 1.5px solid rgba(0,0,0,0.12);
  border-radius: 14px;
  padding: 10px 14px;
  gap: 10px;
  transition: border-color 0.15s, box-shadow 0.15s;
  box-shadow: 0 1px 6px rgba(0,0,0,0.06);
}
.rb-input-inner:focus-within {
  border-color: #1A6B55;
  box-shadow: 0 0 0 3px rgba(26,107,85,0.1);
}

/* Streamlit chat input overrides */
[data-testid="stBottom"] {
  background: transparent !important;
  position: static !important;
}
[data-testid="stChatInputContainer"],
[data-testid="stChatInput"] {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
  box-shadow: none !important;
}
[data-testid="stChatInput"] > div {
  background: #fff !important;
  border: 1.5px solid rgba(0,0,0,0.12) !important;
  border-radius: 14px !important;
  box-shadow: 0 1px 6px rgba(0,0,0,0.06) !important;
  transition: border-color 0.15s, box-shadow 0.15s !important;
}
[data-testid="stChatInput"] > div:focus-within {
  border-color: #1A6B55 !important;
  box-shadow: 0 0 0 3px rgba(26,107,85,0.1) !important;
}
[data-testid="stChatInput"] textarea {
  font-family: 'Inter', sans-serif !important;
  font-size: 14px !important;
  color: #111 !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: #AAA !important; }
button[data-testid="stChatInputSubmitButton"] {
  background: #1A6B55 !important;
  border-radius: 8px !important;
  color: white !important;
}
button[data-testid="stChatInputSubmitButton"]:hover {
  background: #155a47 !important;
}

/* Streamlit chat message overrides — hide default avatars, use our markup */
[data-testid="stChatMessage"] {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
  box-shadow: none !important;
  gap: 0 !important;
}
[data-testid="stChatMessage"] [data-testid="chatAvatarIcon-user"],
[data-testid="stChatMessage"] [data-testid="chatAvatarIcon-assistant"] {
  display: none !important;
}

/* Scrollbar */
.rb-messages::-webkit-scrollbar { width: 4px; }
.rb-messages::-webkit-scrollbar-track { background: transparent; }
.rb-messages::-webkit-scrollbar-thumb { background: #DDD; border-radius: 4px; }

/* Footer note */
.rb-footer-note {
  text-align: center;
  font-size: 11px;
  color: #BBB;
  padding: 6px 0 2px;
}
</style>
""", unsafe_allow_html=True)

# ─── Password gate ────────────────────────────────────────────────────────────
GATE = os.environ.get("ACCESS_PASSWORD") or _secret("ACCESS_PASSWORD")
if GATE and st.session_state.get("ok") is not True:
    st.markdown("""
    <div style="min-height:100dvh;display:flex;flex-direction:column;
                align-items:center;justify-content:center;gap:16px;padding:32px;">
      <div style="width:48px;height:48px;background:linear-gradient(135deg,#1A6B55,#2E9E7A);
                  border-radius:14px;display:flex;align-items:center;justify-content:center;
                  font-size:22px;box-shadow:0 8px 24px rgba(26,107,85,0.2);">🟢</div>
      <h2 style="font-size:20px;font-weight:600;color:#111;margin:0;letter-spacing:-0.3px;">
        ReachBot
      </h2>
      <p style="font-size:13px;color:#888;margin:0;">For Reach Capital portfolio founders</p>
    </div>
    """, unsafe_allow_html=True)
    pw = st.text_input("", type="password", placeholder="Enter access password",
                       label_visibility="collapsed")
    if pw and pw == GATE:
        st.session_state.ok = True
        st.rerun()
    elif pw:
        st.error("Incorrect password.")
    st.stop()

# ─── Index ────────────────────────────────────────────────────────────────────
@st.cache_resource
def load_index():
    d = np.load("index.npz", allow_pickle=True)
    v = d["vectors"].astype(np.float32)
    v /= (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)
    return v, d["chunks"], d["titles"], d["urls"]

def retrieve(query, vectors, chunks, titles, urls):
    r = _client.models.embed_content(model=EMBED_MODEL, contents=query)
    q = np.array(r.embeddings[0].values, dtype=np.float32)
    q /= (np.linalg.norm(q) + 1e-9)
    scores = vectors @ q
    idx = np.argsort(-scores)[:TOP_K]
    return [(chunks[i], titles[i], urls[i]) for i in idx]

def generate(context, prompt):
    system = """You are ReachBot, an assistant for Reach Capital's portfolio founders.
You answer from ReachIn's resources: AMA transcripts, reports, decks, templates,
advisor/consultant directories, and partner discounts.

Use ONLY the provided context. Structure every answer in three parts:

1. **Direct answer** — Answer the question thoroughly and practically, drawing the
   substance from the content itself (especially AMA transcripts — quote or paraphrase
   what the speaker actually said). Be specific, not generic.

2. **Sources** — Cite the specific resources your answer came from, each as a
   markdown link, noting the speaker/title.

3. **Explore more in ReachIn** — List any OTHER resources in the context that are
   relevant but not directly quoted, as links, so the founder can go deeper.

If the context doesn't answer the question, say so plainly and suggest which ReachIn
database to browse. Never invent resources or links not in the context."""
    for model in [CHAT_MODEL, "gemini-2.0-flash"]:
        try:
            resp = _client.models.generate_content(
                model=model,
                contents=f"Context:\n{context}\n\nQuestion: {prompt}",
                config=genai.types.GenerateContentConfig(system_instruction=system),
            )
            return resp.text
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                continue
            raise
    return "Gemini is temporarily unavailable — please try again in a moment."

vectors, chunks, titles, urls = load_index()

# ─── Nav ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="rb-nav">
  <div class="rb-nav-left">
    <div class="rb-logo">R</div>
    <span class="rb-brand">Reach<span>Bot</span></span>
  </div>
  <span class="rb-badge">ReachIn · Portfolio Founders</span>
</div>
""", unsafe_allow_html=True)

# ─── Chat history ─────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []   # list of (role, text)

# Welcome state
if not st.session_state.history:
    st.markdown("""
    <div class="rb-welcome">
      <div class="rb-welcome-icon">🤝</div>
      <h2>How can I help you today?</h2>
      <p>I know everything in ReachIn — AMAs, research, advisors, templates, and partner perks. Ask me anything.</p>
      <div class="rb-suggestions">
        <div class="rb-sug-card">
          <div class="sug-icon">📈</div>
          <div class="sug-text">K-12 sales strategy</div>
          <div class="sug-sub">Who to talk to & what works</div>
        </div>
        <div class="rb-sug-card">
          <div class="sug-icon">💰</div>
          <div class="sug-text">Fundraising advice</div>
          <div class="sug-sub">Seed & Series A guidance</div>
        </div>
        <div class="rb-sug-card">
          <div class="sug-icon">👥</div>
          <div class="sug-text">Hiring your first AE</div>
          <div class="sug-sub">Frameworks & what to avoid</div>
        </div>
        <div class="rb-sug-card">
          <div class="sug-icon">🔍</div>
          <div class="sug-text">EdTech market research</div>
          <div class="sug-sub">Reports & benchmarks</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    # Render chat history as styled bubbles
    for role, msg in st.session_state.history:
        if role == "user":
            st.markdown(f"""
            <div class="rb-msg user">
              <div class="rb-avatar user">You</div>
              <div class="rb-bubble user">{msg}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Use st.chat_message for markdown rendering of assistant replies
            with st.chat_message("assistant", avatar="🟢"):
                st.markdown(msg)

# ─── Input ────────────────────────────────────────────────────────────────────
st.markdown('<div class="rb-footer-note">Answers sourced from ReachIn only · <a href="https://reachcapital.com" style="color:#1A6B55;text-decoration:none;">Reach Capital</a></div>', unsafe_allow_html=True)

if prompt := st.chat_input("Ask anything about ReachIn resources…"):
    # Show user message immediately
    st.markdown(f"""
    <div class="rb-msg user">
      <div class="rb-avatar user">You</div>
      <div class="rb-bubble user">{prompt}</div>
    </div>
    """, unsafe_allow_html=True)

    # Stream answer with typing indicator
    with st.chat_message("assistant", avatar="🟢"):
        with st.spinner(""):
            hits    = retrieve(prompt, vectors, chunks, titles, urls)
            context = "\n\n---\n\n".join(f"[{t}]({u})\n{c}" for c, t, u in hits)
            answer  = generate(context, prompt)
        st.markdown(answer)

    st.session_state.history.append(("user", prompt))
    st.session_state.history.append(("assistant", answer))
    st.rerun()
