#!/usr/bin/env python3
"""
ReachBot Zoom transcript puller.

Pulls cloud-recording transcripts from the Reach Zoom account (events@reachcapital.com)
via a Server-to-Server OAuth app, converts each VTT to clean text, and writes one
markdown file per recording into ./transcripts/ with a header that links back to the
recording so the bot can cite the primary source.

Backfill (first run):   transcribes the whole archive, month by month, from 2020.
Weekly (Monday cron):   pass --since-days 8 to only fetch the past week's recordings.

Setup (one-time, by a Zoom admin):
  Create a Server-to-Server OAuth app -> grant scopes:
    cloud_recording:read:list_user_recordings:admin  (or recording:read:admin)
  Copy Account ID, Client ID, Client Secret.

  pip install requests webvtt-py
  export ZOOM_ACCOUNT_ID=...   ZOOM_CLIENT_ID=...   ZOOM_CLIENT_SECRET=...
  python zoom_transcripts.py                 # full backfill
  python zoom_transcripts.py --since-days 8  # weekly incremental

If a recording has NO Zoom transcript (e.g. Pro plan), this logs it to
transcripts/_missing.txt so you can transcribe the audio separately (Whisper/Gemini).
"""
import os, sys, base64, datetime, re, argparse, time
from pathlib import Path

try:
    import requests
    import webvtt
    from io import StringIO
except ImportError:
    sys.exit("pip install requests webvtt-py")

ACCOUNT_ID = os.environ["ZOOM_ACCOUNT_ID"]
CLIENT_ID = os.environ["ZOOM_CLIENT_ID"]
CLIENT_SECRET = os.environ["ZOOM_CLIENT_SECRET"]
USER = os.environ.get("ZOOM_USER", "me")   # the recordings owner; "me" = token owner

OUT = Path("transcripts"); OUT.mkdir(exist_ok=True)
MISSING = OUT / "_missing.txt"


def token():
    """Server-to-Server OAuth: exchange account creds for a short-lived access token."""
    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    r = requests.post("https://zoom.us/oauth/token",
                      params={"grant_type": "account_credentials", "account_id": ACCOUNT_ID},
                      headers={"Authorization": f"Basic {basic}"})
    r.raise_for_status()
    return r.json()["access_token"]


def month_ranges(start, end):
    """Yield (from, to) date strings in <=30-day windows; Zoom caps the recordings query."""
    cur = start
    while cur < end:
        nxt = min(cur + datetime.timedelta(days=30), end)
        yield cur.isoformat(), nxt.isoformat()
        cur = nxt


def list_recordings(tok, frm, to):
    recs, page = [], None
    while True:
        r = requests.get(
            f"https://api.zoom.us/v2/users/{USER}/recordings",
            headers={"Authorization": f"Bearer {tok}"},
            params={"from": frm, "to": to, "page_size": 300, "next_page_token": page or ""},
        )
        r.raise_for_status()
        data = r.json()
        recs.extend(data.get("meetings", []))
        page = data.get("next_page_token")
        if not page:
            return recs
        time.sleep(0.3)


def vtt_to_text(vtt_str):
    """Strip VTT timestamps/cues to plain prose."""
    out = []
    for cap in webvtt.read_buffer(StringIO(vtt_str)):
        line = cap.text.strip().replace("\n", " ")
        if line and (not out or out[-1] != line):
            out.append(line)
    return "\n".join(out)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:80] or "ama"


def process(meeting, tok):
    topic = meeting.get("topic", "Untitled")
    date = (meeting.get("start_time", "") or "")[:10]
    share_url = meeting.get("share_url", "")
    transcript_file = next(
        (f for f in meeting.get("recording_files", []) if f.get("file_type") == "TRANSCRIPT"),
        None,
    )
    if not transcript_file:
        with open(MISSING, "a") as m:
            m.write(f"{date}\t{topic}\t{share_url}\n")
        return False
    dl = transcript_file["download_url"]
    r = requests.get(dl, headers={"Authorization": f"Bearer {tok}"})
    r.raise_for_status()
    text = vtt_to_text(r.text)
    header = (f"---\ntitle: AMA — {topic}\nsource_url: {share_url}\n"
              f"date: {date}\ntype: ama_transcript\n---\n\n# AMA: {topic}\n\n")
    (OUT / f"{date}-{slug(topic)}.md").write_text(header + text, encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since-days", type=int, default=None,
                    help="Only fetch recordings from the last N days (weekly mode).")
    args = ap.parse_args()

    end = datetime.date.today()
    start = (end - datetime.timedelta(days=args.since_days)) if args.since_days \
        else datetime.date(2020, 1, 1)

    tok = token()
    ok = miss = 0
    for frm, to in month_ranges(start, end):
        for meeting in list_recordings(tok, frm, to):
            try:
                if process(meeting, tok):
                    ok += 1
                else:
                    miss += 1
            except Exception as e:
                print(f"  ! {meeting.get('topic')}: {e}")
        print(f"  window {frm}..{to} done (ok={ok}, missing={miss})")
        tok = token()  # refresh; token is short-lived during a long backfill
    print(f"\nDone. {ok} transcripts -> {OUT.resolve()}. {miss} had no Zoom transcript "
          f"(see {MISSING}).")


if __name__ == "__main__":
    main()
