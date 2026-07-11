"""Parse the structured `**Label:** value` fields embedded in ReachIn chunk text
into a normalized per-type field set for the UI's resource cards.

The index only stores title/url/category; the interesting fields (contact, offer,
speaker, publisher, …) live inline in the chunk body. This module extracts them and
maps the real (uneven) Notion labels onto the card schema from the design spec.

Missing fields are simply omitted — cards render what exists (graceful).
"""
import re

# Split a value at the next inline label so we don't swallow the rest of the chunk.
_LABEL_RE = re.compile(r"\*\*([A-Za-z][^:*]{1,34}):\*\*\s*(.*?)(?=\*\*[A-Za-z][^:*]{1,34}:\*\*|$)", re.DOTALL)

# Strip markdown links [text](url) → "text", and mailto wrappers, for display.
def _clean(v: str) -> str:
    v = v.strip()
    v = re.sub(r"\[([^\]]+)\]\((?:mailto:)?[^)]+\)", r"\1", v)  # [x](y) → x
    v = re.sub(r"\s+", " ", v).strip(" -–—·")
    # Drop an unbalanced trailing ')' left over from a stripped markdown link.
    if v.endswith(")") and v.count("(") < v.count(")"):
        v = v[:-1].rstrip()
    return v.strip()


# Field values are short metadata (a name, a date, a one-line description). When a
# label is the LAST one in the chunk, its value runs to the whole remaining body —
# so cap it. Description-like fields get a longer cap than name/date-like ones.
_LONG_FIELDS = {"description", "services offered", "notes", "focus"}
_SHORT_CAP, _LONG_CAP = 120, 400


def _raw_fields(chunk: str) -> dict:
    """All **Label:** → value pairs found in the chunk, label lowercased."""
    out = {}
    for label, value in _LABEL_RE.findall(chunk):
        key = label.strip().lower()
        val = _clean(value)
        if not val or key in out:
            continue
        cap = _LONG_CAP if key in _LONG_FIELDS else _SHORT_CAP
        if len(val) > cap:
            # Truncate at a word boundary; a runaway value means the label was last
            # in the chunk and swallowed the body — keep just the lead.
            val = val[:cap].rsplit(" ", 1)[0].rstrip() + "…"
        out[key] = val
    return out


def _first(raw: dict, *keys: str) -> str:
    for k in keys:
        if raw.get(k):
            return raw[k]
    return ""


def parse_fields(chunk: str, rtype: str) -> dict:
    """Return a normalized field dict for the given resource type. Only keys with
    real values are present. Shapes match the design spec's 'key fields' per card."""
    raw = _raw_fields(chunk)

    if rtype == "deal":
        return _compact({
            "category": _first(raw, "type"),           # e.g. "HR & Legal", "Credits"
            "offer": _first(raw, "description"),        # the discount/credit terms
            "contact": _first(raw, "contact"),
            "email": _first(raw, "email"),
            "reach_point": _first(raw, "reach point"),  # who at Reach to ask
            "link": _first(raw, "link"),
        })

    if rtype == "contact":
        # Three sub-types with different Notion vocabularies:
        #   Reach Advisors     → Current Title, Advisory Group, Areas of Expertise, LinkedIn
        #   Consultants&Coaches→ SERVICES OFFERED / FOCUS, TITLE/ROLE, CONTACT INFO
        #   Media Contacts     → Name, Category, TITLE/ROLE, EMAIL, WRITER PAGE
        specialty = _first(raw, "areas of expertise", "services offered", "focus")
        # Strip a leading emoji from the advisory group / media beat.
        group = _first(raw, "advisory group", "category")
        group = re.sub(r"^[^\w]+", "", group).strip()
        if group and group.lower() not in specialty.lower():
            specialty = f"{specialty} · {group}".strip(" ·") if specialty else group
        contact = _first(raw, "contact info", "email", "writer page", "linkedin")
        # "Current Title" (advisors) is a descriptive blurb — keep just the lead role.
        role = _first(raw, "title/role", "current title")
        role = re.split(r"\s{2,}|,\s|\bBoard member\b", role)[0].strip()
        if len(role) > 70:
            role = role[:70].rsplit(" ", 1)[0] + "…"
        return _compact({
            "name": _first(raw, "name"),  # media/coach rows; advisors use the title
            "role": role,
            "specialty": specialty,
            "contact_info": contact,
        })

    if rtype == "ama":
        # The Speaker field is often "Name(s) - <url/transcript run-on>". Keep just
        # the name(s): cut at the first " - ", URL, or timestamp like "(00:00".
        # Skip `recording` — it can carry a passcode, and the title links the AMA.
        speaker = _first(raw, "speaker")
        # Cut at the first structural break that signals the name has ended and a
        # topic/transcript begins: " - ", a URL, a "(00:00" timestamp, or a colon.
        speaker = re.split(r"\s+-\s+|\s*https?://|\s*\(\d{1,2}:\d{2}|\s*:\s", speaker)[0].strip()
        if len(speaker) > 48:
            speaker = speaker[:48].rsplit(" ", 1)[0] + "…"
        return _compact({
            "speaker": speaker,
            "org": _first(raw, "org"),
            "date": _first(raw, "date"),
            "tags": _first(raw, "tags"),
        })

    if rtype == "report":
        return _compact({
            "publisher": _first(raw, "source"),
            "sector": _first(raw, "sector", "area"),
            "summary": _first(raw, "description"),
            "tags": _first(raw, "tags"),
        })

    # article (default)
    return _compact({
        "publisher": _first(raw, "source"),
        "sector": _first(raw, "sector", "area"),
        "summary": _first(raw, "description"),
    })


def _compact(d: dict) -> dict:
    return {k: v for k, v in d.items() if v}
