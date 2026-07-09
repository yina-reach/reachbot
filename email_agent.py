#!/usr/bin/env python3
"""
ReachIn Connect — email intake agent.

Anyone in the org emails a PDF (attached) or a URL (in the body) to the ReachIn
Connect inbox. The agent:
  1. extracts the content (PDF text or fetched article),
  2. picks the right ReachIn database AND fills its actual properties using only
     the database's existing option vocabularies (Format/Sector/Area/Tags/etc.),
  3. emails Tony a fully-formed proposed entry he can APPROVE, EDIT, redirect
     (USE: <db>), or REJECT,
  4. on approval, creates the row in the chosen Notion database exactly as shown.

State is tracked with Gmail labels so reruns are safe; the proposed entry is
embedded in Tony's email so approval re-creates exactly what he saw.

Secrets (environment only):
  REACHIN_EMAIL, REACHIN_EMAIL_APP_PASSWORD   # dedicated Gmail + app password
  TONY_EMAIL                                  # approver
  NOTION_WRITE_TOKEN, GEMINI_API_KEY

Run modes:
  python email_agent.py --classify <url|path.pdf>   # test the brain only (no email, no write)
  python email_agent.py --poll                       # one full intake+approval cycle
"""
import os, sys, re, json, io, ssl, email, imaplib, smtplib
from email.message import EmailMessage
from email.header import decode_header
import urllib.request as _ur

from google import genai

GKEY = os.environ.get("GEMINI_API_KEY")
WTOK = os.environ.get("NOTION_WRITE_TOKEN")
client = genai.Client(api_key=GKEY) if GKEY else None
NH = {"Authorization": f"Bearer {WTOK}", "Notion-Version": "2022-06-28",
      "Content-Type": "application/json"}

# ── ReachIn database registry (id + one-line purpose for routing) ────────────
DATABASES = {
    "Library Database": {
        "id": "ed219eb3-2159-4205-9347-4e8b736dcf5c",
        "purpose": "Reports, research, datasets, guides, frameworks and reference "
                   "resources (often PDFs/decks). Default home for substantive documents.",
    },
    "Good Reads": {
        "id": "2a03dcf7-495b-4d0a-919e-d87adbf68999",
        "purpose": "Articles, blog posts, and newsletters worth reading (usually a "
                   "URL). Default home for online articles/opinion pieces.",
    },
    "Marketing & Branding": {
        "id": "5c685825-f988-4187-af0c-35982ea13cfe",
        "purpose": "Marketing/branding playbooks, templates, or agency resources.",
    },
    "Consultants & Coaches": {
        "id": "2a9dddf0-18dc-4c1f-a739-a6b194c22bd8",
        "purpose": "A consultant, coach, or agency offering services to portfolio companies.",
    },
    "Reach Advisors": {
        "id": "1a5a896b-b9b6-8094-a648-f8400fd5de3d",
        "purpose": "A person who serves as an advisor to Reach portfolio companies.",
    },
    "Media Contacts": {
        "id": "dd6e081b-c541-4e81-80e3-cfb010ae0103",
        "purpose": "A journalist, reporter, editor, or press/media contact.",
    },
    "Session Recordings": {
        "id": "682f047c-c46b-4b40-b836-269c1758ec6a",
        "purpose": "A recording or transcript of an AMA / session / talk.",
    },
}
# Properties the agent never sets (system-managed / need human/file input).
SKIP_TYPES = {"files", "people", "created_time", "last_edited_time", "last_edited_by",
              "created_by", "verification", "rollup", "formula", "relation", "status"}

# ── Notion helpers ──────────────────────────────────────────────────────────
def _napi(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = _ur.Request(url, data=data, headers=NH, method=method)
    with _ur.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

_schema_cache = {}
def db_schema(db_id):
    if db_id not in _schema_cache:
        _schema_cache[db_id] = _napi("GET", f"https://api.notion.com/v1/databases/{db_id}")["properties"]
    return _schema_cache[db_id]

def _options(prop):
    t = prop["type"]
    return [o["name"] for o in prop[t]["options"]] if t in ("select", "multi_select") else []

def schema_for_prompt(db_name):
    """Human-readable list of fillable properties + allowed options for the LLM."""
    props = db_schema(DATABASES[db_name]["id"])
    lines = []
    for name, p in props.items():
        t = p["type"]
        if t in SKIP_TYPES:
            continue
        if t == "title":
            lines.append(f'- "{name}" (TITLE, required): a concise entry title')
        elif t == "rich_text":
            lines.append(f'- "{name}" (text)')
        elif t == "url":
            lines.append(f'- "{name}" (url)')
        elif t == "email":
            lines.append(f'- "{name}" (email)')
        elif t == "number":
            lines.append(f'- "{name}" (number)')
        elif t == "date":
            lines.append(f'- "{name}" (date, YYYY-MM-DD)')
        elif t == "select":
            lines.append(f'- "{name}" (pick ONE, only from: {_options(p)})')
        elif t == "multi_select":
            lines.append(f'- "{name}" (pick ANY that apply, only from: {_options(p)})')
    return "\n".join(lines)

def notion_upload_file(name, data, content_type="application/pdf"):
    """Upload bytes to Notion (2-step file upload) and return the file_upload id.
    The id must be attached to a page within ~1 hour, so upload at file time."""
    up = _napi("POST", "https://api.notion.com/v1/file_uploads",
               {"filename": name[:900], "content_type": content_type})
    b = "----reachinBOUNDARY7f3a2c"
    pre = (f'--{b}\r\nContent-Disposition: form-data; name="file"; '
           f'filename="{name}"\r\nContent-Type: {content_type}\r\n\r\n').encode()
    body = pre + data + f"\r\n--{b}--\r\n".encode()
    req = _ur.Request(up["upload_url"], data=body, method="POST",
                      headers={"Authorization": f"Bearer {WTOK}", "Notion-Version": "2022-06-28",
                               "Content-Type": f"multipart/form-data; boundary={b}"})
    with _ur.urlopen(req, timeout=120) as r:
        r.read()
    return up["id"]

def create_row(db_name, fields, attach=None):
    """Build a Notion row from {property_name: value}, coercing to each property's
    type and dropping any select/multi-select value not already in the vocabulary
    (so the agent never invents new options). `attach` = (filename, bytes) uploads
    and links the file into the database's files property."""
    props = db_schema(DATABASES[db_name]["id"])
    payload = {}
    if attach and attach[1]:
        fname, fbytes = attach
        files_prop = next((n for n, p in props.items() if p["type"] == "files"), None)
        if files_prop:
            try:
                fid = notion_upload_file(fname, fbytes)
                payload[files_prop] = {"files": [{"type": "file_upload",
                    "name": fname[:100], "file_upload": {"id": fid}}]}
            except Exception as e:
                print(f"  ! file upload/attach failed: {e}")
    for name, val in (fields or {}).items():
        if name not in props or val in (None, "", []):
            continue
        t = props[name]["type"]
        if t == "title":
            payload[name] = {"title": [{"text": {"content": str(val)[:2000]}}]}
        elif t == "rich_text":
            payload[name] = {"rich_text": [{"text": {"content": str(val)[:2000]}}]}
        elif t == "url":
            payload[name] = {"url": str(val)}
        elif t == "email":
            payload[name] = {"email": str(val)}
        elif t == "number":
            try: payload[name] = {"number": float(val)}
            except Exception: pass
        elif t == "date":
            payload[name] = {"date": {"start": str(val)}}
        elif t == "select":
            if val in _options(props[name]):
                payload[name] = {"select": {"name": val}}
        elif t == "multi_select":
            allowed = set(_options(props[name]))
            vals = [v for v in (val if isinstance(val, list) else [val]) if v in allowed]
            if vals:
                payload[name] = {"multi_select": [{"name": v} for v in vals]}
    page = _napi("POST", "https://api.notion.com/v1/pages",
                 {"parent": {"database_id": DATABASES[db_name]["id"]}, "properties": payload})
    return f"https://www.notion.so/{page['id'].replace('-', '')}"

# ── Content extraction ──────────────────────────────────────────────────────
def extract_pdf(data):
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)

def fetch_url(url):
    try:
        import trafilatura
        dl = trafilatura.fetch_url(url)
        if dl:
            txt = trafilatura.extract(dl, include_comments=False) or ""
            md = trafilatura.metadata.extract_metadata(dl)
            return ((md.title if md else "") or ""), txt
    except Exception:
        pass
    req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = _ur.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return (m.group(1).strip() if m else ""), re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))[:9000]

# ── Two-step brain: route, then fill ────────────────────────────────────────
def _gen_json(prompt, retries=4):
    last = None
    for _ in range(retries):
        try:
            resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            txt = (getattr(resp, "text", None) or "").strip()
            if not txt:
                fr = None
                try: fr = resp.candidates[0].finish_reason
                except Exception: pass
                last = f"empty response (finish_reason={fr})"
                continue
            raw = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.M).strip()
            m = re.search(r"\{.*\}", raw, re.S)  # outermost JSON object
            if m:
                return json.loads(m.group(0))
            last = f"no JSON object in response: {raw[:200]!r}"
        except Exception as e:
            last = repr(e)
    raise ValueError(f"no valid JSON after {retries} tries: {last}")

def pick_database(content, source, title):
    catalog = "\n".join(f"- {n}: {d['purpose']}" for n, d in DATABASES.items())
    try:
        out = _gen_json(
            f"Route this incoming item to the single best Reach Capital 'ReachIn' database.\n\n"
            f"Databases:\n{catalog}\n\nSource: {source}\nTitle: {title or '(none)'}\n\n"
            f"Content (may be truncated):\n\"\"\"\n{content[:6000]}\n\"\"\"\n\n"
            f'Return ONLY JSON: {{"database":"<exact name>","confidence":"high|medium|low",'
            f'"reasoning":"<one sentence>"}}')
    except Exception as e:
        print(f"  ! routing classifier failed: {e}")
        out = {"database": "Library Database", "confidence": "low",
               "reasoning": f"defaulted (classifier error: {str(e)[:120]})"}
    if out.get("database") not in DATABASES:
        out["database"] = "Library Database"
    return out

def fill_entry(db_name, content, source, title):
    try:
        fields = _gen_json(
        f'Create a new "{db_name}" entry from the item below. Fill these properties.\n'
        f'For select/multi-select, use ONLY the listed options; if none truly fit, omit '
        f'the property (do NOT invent options). Omit any property you cannot fill from '
        f'the content. The TITLE property is required. Put the source URL in any url property.\n\n'
        f'Properties:\n{schema_for_prompt(db_name)}\n\n'
        f'Source: {source}\nKnown title: {title or "(none)"}\n\n'
        f'Content (may be truncated):\n"""\n{content[:18000]}\n"""\n\n'
        f'Return ONLY a JSON object mapping property names to values. Use strings for '
        f'text/url/email/date/select and arrays of strings for multi-select.')
    except Exception as e:
        print(f"  ! fill classifier failed: {e}")
        fields = {}   # degrade to title/url/description backfill below
    # ensure a title exists
    title_prop = next((n for n, p in db_schema(DATABASES[db_name]["id"]).items()
                       if p["type"] == "title"), None)
    if title_prop and not fields.get(title_prop):
        fields[title_prop] = title or "Untitled"
    # backfill a URL property if we have a source URL and the model missed it
    if source.startswith("http"):
        for n, p in db_schema(DATABASES[db_name]["id"]).items():
            if p["type"] == "url" and not fields.get(n):
                fields[n] = source
                break
    return fields

def _generic_snapshot(db_name, fields):
    """Pull logical title/description/url out of a db-specific field dict so a
    later USE:<other-db> redirect can remap into the new schema."""
    props = db_schema(DATABASES[db_name]["id"])
    g = {"title": "", "description": "", "url": ""}
    for n, v in fields.items():
        if n not in props or not v:
            continue
        t = props[n]["type"]
        if t == "title" and not g["title"]:
            g["title"] = v
        elif t == "rich_text" and not g["description"]:
            g["description"] = v
        elif t == "url" and not g["url"]:
            g["url"] = v
    return g

def _remap_generic(db_name, generic):
    """Build a minimal field dict for db_name from a generic snapshot."""
    props = db_schema(DATABASES[db_name]["id"])
    out = {}
    for n, p in props.items():
        if p["type"] == "title" and generic.get("title"):
            out[n] = generic["title"]
        elif p["type"] == "rich_text" and "description" not in [x.lower() for x in out] and generic.get("description"):
            if any(h in n.lower() for h in ("description", "notes", "bio", "summary")):
                out[n] = generic["description"]
        elif p["type"] == "url" and generic.get("url"):
            out[n] = generic["url"]
    return out

def propose(content, source, title="", note=""):
    # A submitter's one-line note ("great fundraising resource for the Library")
    # is strong routing signal — prepend it (labeled, since it may be a signature).
    note = (note or "").strip()
    ai = f"Note from the person who submitted this (may include an email signature — weigh accordingly):\n{note[:500]}\n\n---\n\n{content}" if note else content
    routing = pick_database(ai, source, title)
    db = routing["database"]
    fields = fill_entry(db, ai, source, title)
    return {"database": db, "confidence": routing.get("confidence"),
            "reasoning": routing.get("reasoning"), "fields": fields,
            "generic": _generic_snapshot(db, fields)}

# ── Proposal email (machine-readable block lets approval rebuild it exactly) ──
def proposal_email(source, proposal):
    db = proposal["database"]
    pretty = "\n".join(f"  {k}: {v}" for k, v in proposal["fields"].items())
    opts = " | ".join(DATABASES.keys())
    blob = json.dumps(proposal, ensure_ascii=False)
    return (
        f"A new item came in for ReachIn Connect.\n\n"
        f"PROPOSED DATABASE:  {db}   (confidence: {proposal.get('confidence')})\n"
        f"Why: {proposal.get('reasoning')}\n"
        f"Source: {source}\n\n"
        f"PROPOSED ENTRY:\n{pretty}\n\n"
        f"────────────────────────────────────────\n"
        f"Reply with one of:\n"
        f"  APPROVE                         file it exactly as above\n"
        f"  REJECT                          discard it\n"
        f"  USE: <Database>                 re-file into a different database\n"
        f"                                  ({opts})\n"
        f"  EDIT, then lines like           change fields before filing, e.g.\n"
        f"     Area: Fundraising               Area: Fundraising\n"
        f"     Tags: fundraising, markets      Tags: fundraising, markets\n\n"
        f"(For multi-select/select fields, only existing options are kept.)\n\n"
        f"-- do not delete below; the agent reads it on approval --\n"
        f"@@PROPOSAL@@ {blob}\n"
    )

def parse_proposal_blob(text):
    """Recover the embedded proposal JSON. Tolerant of email clients that wrap the
    single-line blob and add '>' quote prefixes when replying/forwarding, and never
    raises — returns None if it can't parse (the thread-lookup fallback then runs)."""
    i = text.find("@@PROPOSAL@@")
    if i == -1:
        return None
    tail = text[i + len("@@PROPOSAL@@"):]
    unquoted = re.sub(r"(?m)^\s*>+\s?", "", tail)      # drop email quote prefixes ('> ')
    # The blob was one line; email soft-wrap inserted CR/LF (incl. inside string
    # values, which is invalid JSON). Collapse all CR/LF to a single space.
    flat = re.sub(r"[\r\n]+", " ", unquoted)
    for candidate in (unquoted, flat):
        j = candidate.find("{")
        if j == -1:
            continue
        try:
            return json.JSONDecoder().raw_decode(candidate[j:])[0]  # first object, ignore trailing
        except Exception:
            continue
    return None

def apply_reply_edits(proposal, reply_text):
    """Apply Tony's reply: returns (action, proposal). action in approve/reject/none.
    Only reads Tony's OWN words — the quoted original proposal (lines starting with
    '>' or after the "On … wrote:" attribution) contains the keyword instructions and
    field labels, which must not be mistaken for his commands/edits."""
    own_lines = []
    for ln in reply_text.splitlines():
        if ln.lstrip().startswith(">") or re.match(r"\s*On .*wrote:\s*$", ln):
            break
        own_lines.append(ln)
    own = "\n".join(own_lines)
    low = own.lower()
    if re.search(r"\breject\b", low):
        return "reject", proposal
    use = re.search(r"use:\s*(.+)", own, re.I)
    if use:
        cand = use.group(1).strip().splitlines()[0].strip()
        match = next((d for d in DATABASES if d.lower() == cand.lower()), None)
        if match and match != proposal["database"]:
            proposal["database"] = match  # re-fill happens in the poller before create
            proposal["_refill"] = True
    # field overrides: "Prop: value" lines (from Tony's own text only)
    for line in own.splitlines():
        m = re.match(r"\s*([A-Za-z][A-Za-z &/]+?):\s*(.+)", line)
        if not m:
            continue
        key, val = m.group(1).strip(), m.group(2).strip()
        if key.lower() in ("use", "from", "to", "subject", "approve", "edit"):
            continue
        # match to a real property name (case-insensitive)
        props = db_schema(DATABASES[proposal["database"]]["id"])
        pname = next((n for n in props if n.lower() == key.lower()), None)
        if pname:
            proposal["fields"][pname] = [v.strip() for v in val.split(",")] \
                if props[pname]["type"] == "multi_select" else val
    if re.search(r"\bapprove\b|\bedit\b", low) or use:
        return "approve", proposal
    return "none", proposal


# ── Email plumbing (Stage 2) ────────────────────────────────────────────────
IMAP_HOST, SMTP_HOST = "imap.gmail.com", "smtp.gmail.com"
L_PENDING, L_FILED, L_REJECTED, L_DONE = ("ReachInPending", "ReachInFiled",
                                          "ReachInRejected", "ReachInProcessed")
L_IGNORED = "ReachInIgnored"
# Only treat mail from these domains as real submissions (it's an internal org
# tool). Set REACHIN_ALLOWED_DOMAINS="*" to accept anyone.
ALLOWED_DOMAINS = set(d.strip().lower() for d in
                      os.environ.get("REACHIN_ALLOWED_DOMAINS", "reachcapital.com").split(",") if d.strip())
AUTO_SENDERS = ("no-reply", "noreply", "mailer-daemon", "postmaster", "donotreply",
                "notifications@", "@google.com", "@accounts.google.com")

def _decode(s):
    if not s:
        return ""
    return "".join(p.decode(enc or "utf-8", "ignore") if isinstance(p, bytes) else p
                   for p, enc in decode_header(s))

def _send(to, subject, body, in_reply_to=None):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = os.environ["REACHIN_EMAIL"], to, subject
    if in_reply_to:
        msg["In-Reply-To"] = msg["References"] = in_reply_to
    msg.set_content(body)
    with smtplib.SMTP(SMTP_HOST, 587) as s:
        s.starttls(context=ssl.create_default_context())
        s.login(os.environ["REACHIN_EMAIL"], os.environ["REACHIN_EMAIL_APP_PASSWORD"])
        s.send_message(msg)
    return msg["Message-ID"]

def plain_text(msg):
    out = ""
    for part in msg.walk():
        if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition") or ""):
            out += (part.get_payload(decode=True) or b"").decode("utf-8", "ignore")
    return out

def from_addr(msg):
    return email.utils.parseaddr(msg.get("From", ""))[1].lower()

def extract_item(msg):
    """(title, content, source, note) from an email: PDF attachment or first URL in
    body. `note` is the submitter's message text (used as routing signal)."""
    body, pdf, pdf_name = "", None, None
    for part in msg.walk():
        ctype, disp = part.get_content_type(), str(part.get("Content-Disposition") or "")
        if ctype == "application/pdf" or ".pdf" in disp.lower():
            pdf, pdf_name = part.get_payload(decode=True), _decode(part.get_filename()) or "attachment.pdf"
        elif ctype == "text/plain" and "attachment" not in disp:
            body += (part.get_payload(decode=True) or b"").decode("utf-8", "ignore")
    body = body.strip()
    if pdf:
        return pdf_name, extract_pdf(pdf), f"PDF attachment: {pdf_name}", body
    m = re.search(r"https?://[^\s>\])]+", body)
    if m:
        t, txt = fetch_url(m.group(0))
        note = body.replace(m.group(0), "").strip()  # body minus the URL itself
        return (t or m.group(0)), txt, m.group(0), note
    return None, body, "no PDF or URL found", ""

# ── IMAP state helpers (Gmail labels) ───────────────────────────────────────
def imap_login():
    M = imaplib.IMAP4_SSL(IMAP_HOST)
    M.login(os.environ["REACHIN_EMAIL"], os.environ["REACHIN_EMAIL_APP_PASSWORD"])
    return M

def ensure_labels(M):
    for lbl in (L_PENDING, L_FILED, L_REJECTED, L_DONE, L_IGNORED):
        try: M.create(lbl)
        except Exception: pass

def search_raw(M, gmail_query, retries=2):
    import time as _t
    esc = gmail_query.replace("\\", "\\\\").replace('"', '\\"')  # IMAP-quote the value
    for attempt in range(retries + 1):
        try:
            typ, data = M.uid("SEARCH", None, "X-GM-RAW", f'"{esc}"')
            return data[0].split() if data and data[0] else []
        except imaplib.IMAP4.error:
            if attempt == retries:
                raise
            _t.sleep(1)

def fetch_msg(M, uid):
    typ, data = M.uid("FETCH", uid, "(RFC822)")
    return email.message_from_bytes(data[0][1])

def add_label(M, uid, label):
    M.uid("STORE", uid, "+X-GM-LABELS", f"({label})")

def find_proposal_in_thread(M, uid):
    """Locate the agent's original @@PROPOSAL@@ blob in the same Gmail thread."""
    typ, data = M.uid("FETCH", uid, "(X-GM-THRID)")
    m = re.search(rb"X-GM-THRID (\d+)", data[0] if isinstance(data[0], bytes) else data[0][0])
    if not m:
        return None
    thrid = m.group(1).decode()
    typ, data = M.uid("SEARCH", None, "X-GM-THRID", thrid)
    for u in (data[0].split() if data and data[0] else []):
        p = parse_proposal_blob(plain_text(fetch_msg(M, u)))
        if p:
            return p
    return None

def file_proposal(proposal, attach=None):
    """Create the Notion row, remapping fields if Tony changed the database."""
    db = proposal["database"]
    fields = proposal["fields"]
    if proposal.get("_refill") and proposal.get("generic"):
        fields = _remap_generic(db, proposal["generic"])
    return create_row(db, fields, attach=attach)

def fetch_submission_pdf(M, msgid):
    """Re-fetch the PDF from the original submission email (by Message-ID) so it can
    be uploaded fresh at approval time (Notion uploads expire ~1h after creation)."""
    if not msgid:
        return None
    mid = msgid.strip().strip("<>")
    try:
        for u in search_raw(M, f"rfc822msgid:{mid}"):
            sm = fetch_msg(M, u)
            for part in sm.walk():
                if part.get_content_type() == "application/pdf":
                    return (_decode(part.get_filename()) or "attachment.pdf",
                            part.get_payload(decode=True))
    except Exception as e:
        print(f"  ! could not re-fetch submission PDF: {e}")
    return None

# ── Run modes ───────────────────────────────────────────────────────────────
def cmd_classify(arg):
    if arg.lower().endswith(".pdf") and os.path.exists(arg):
        title, content, source = os.path.basename(arg), extract_pdf(open(arg, "rb").read()), f"PDF: {arg}"
    elif arg.startswith("http"):
        title, content = fetch_url(arg); source = arg
    else:
        title, content, source = "", arg, "raw text"
    print(f"source: {source}\nextracted ~{len(content.split())} words\n")
    p = propose(content, source, title)
    print(json.dumps(p, indent=2, ensure_ascii=False))
    print("\n--- email Tony would receive ---\n")
    print(proposal_email(source, p))

def cmd_poll(verbose=True):
    tony = os.environ["TONY_EMAIL"].lower()
    me = os.environ["REACHIN_EMAIL"].lower()
    M = imap_login(); M.select("INBOX"); ensure_labels(M)
    log = (lambda *a: print(*a)) if verbose else (lambda *a: None)

    # ── 1) Approvals: replies from Tony we haven't acted on ──────────────────
    for uid in search_raw(M, f"from:{tony} -label:{L_DONE}"):
        msg = fetch_msg(M, uid)
        if not msg.get("In-Reply-To"):
            continue  # an original email from Tony, not a reply to a proposal
        reply = plain_text(msg)
        proposal = parse_proposal_blob(reply) or find_proposal_in_thread(M, uid)
        if not proposal:
            continue
        action, proposal = apply_reply_edits(proposal, reply)
        mid = msg.get("Message-ID")
        if action == "approve":
            try:
                # re-fetch the original PDF (if any) so it's attached to the row
                attach = fetch_submission_pdf(M, proposal.get("_submission_msgid"))
                url = file_proposal(proposal, attach=attach)
                filed_note = " (with PDF)" if attach else ""
                _send(tony, "Re: ReachIn Connect — filed ✅",
                      f"Filed into {proposal['database']}{filed_note}:\n{url}", mid)
                add_label(M, uid, L_DONE)
                log(f"  ✓ filed approval → {proposal['database']}: {url}")
            except Exception as e:
                log(f"  ! file failed: {e}")
        elif action == "reject":
            _send(tony, "Re: ReachIn Connect — discarded", "Discarded, nothing filed.", mid)
            add_label(M, uid, L_DONE)
            log("  ✓ rejection handled")

    # ── 2) New submissions: inbox mail not yet proposed ─────────────────────
    # Don't exclude Tony here — he may submit too. Approvals are distinguished
    # from submissions below by the In-Reply-To check, not by sender.
    q = (f"-from:{me} -label:{L_PENDING} -label:{L_FILED} "
         f"-label:{L_REJECTED} -label:{L_DONE} -label:{L_IGNORED}")
    for uid in search_raw(M, q):
        msg = fetch_msg(M, uid)
        if msg.get("In-Reply-To") or parse_proposal_blob(plain_text(msg)):
            continue  # a reply / a proposal echo, not a fresh submission
        sender = from_addr(msg)
        dom = sender.split("@")[-1] if "@" in sender else ""
        # ignore automated mail and anyone outside the allowed org domains
        if any(x in sender for x in AUTO_SENDERS) or \
           ("*" not in ALLOWED_DOMAINS and dom not in ALLOWED_DOMAINS):
            add_label(M, uid, L_IGNORED)
            log(f"  · ignored non-submission from {sender}")
            continue
        title, content, source, note = extract_item(msg)
        if source == "no PDF or URL found":
            _send(sender, "ReachIn Connect — please resend with a PDF or link",
                  "Thanks for the submission! I couldn't find a PDF attachment or a "
                  "URL in your email. Please resend with the PDF attached or the link "
                  "in the body and I'll file it.", msg.get("Message-ID"))
            add_label(M, uid, L_PENDING)
            log(f"  · no content from {sender}; asked to resend")
            continue
        proposal = propose(content, source, title, note=note)
        proposal["_submission_msgid"] = msg.get("Message-ID")  # so approval can re-attach the PDF
        subj = f"ReachIn Connect: review — {proposal['generic'].get('title') or title or 'new item'}"
        _send(tony, subj, proposal_email(source, proposal))
        add_label(M, uid, L_PENDING)
        log(f"  → proposed '{proposal['generic'].get('title')}' → {proposal['database']} (sent to {tony})")

    M.logout()
    log("poll complete.")

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--classify":
        cmd_classify(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "--poll":
        cmd_poll()
    else:
        sys.exit(__doc__)
