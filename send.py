#!/usr/bin/env python3
"""Cupid's email builder and sender.

The routine writes the day's content to a JSON file with its Write tool, then runs:

    CUPID_RESEND_KEY=re_xxx python3 send.py /tmp/cupid/jobs.json

This script exists so the cloud run never has to generate a big heredoc or inline
Python in Bash. Those commands trip Claude Code's bash safety parser, which then
stops the unattended run to ask Ed for permission on his phone.

Flags:
    --dry-run   build /tmp/cupid/body.html and print a summary, send nothing
    --test      send only to Ed (no Lida, no cc), subject prefixed with [TEST]

jobs.json shape (jobs may hold 0-3 entries; 0 = "struck out today" note):
{
  "subject": "Cupid's Wednesday picks ...",
  "greeting": "Happy Wednesday, ...",            # HTML fragment allowed
  "jobs": [
    {
      "title": "Grant and Financial Specialist",
      "org": "Brown University",
      "location": "Providence, RI (hybrid)",
      "pay": "$60k-$70k",                         # optional, "" if unknown
      "reasoning": "2-4 playful sentences ...",   # HTML fragment allowed
      "starter": "Open with ...",                 # HTML fragment allowed
      "url": "https://...",
      "cover_letter": {"subject": "...", "body": "..."},
      "intro_email": {"subject": "...", "body": "..."}
    }
  ],
  "feedback_line": "Reply and tell me ...",       # optional
  "signoff": "Go get 'em, ..."                    # HTML fragment allowed; signature added
}
"""

import argparse
import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# Production recipients. Fixed here on purpose: nothing in jobs.json can change them.
FROM = "Ed \U0001F916❤️ <cupid@pinventory.app>"
TO = ["lidabrooke@gmail.com"]
CC = ["ed@edgiardina.com"]
REPLY_TO = "cupidrobot9@gmail.com"
TEST_TO = ["ed@edgiardina.com"]

SIGNATURE = "— Ed \U0001F916❤️"
DEFAULT_FEEDBACK = (
    "Reply and tell me if these stink or if there's a whole industry you'd rather "
    "I skip. I'll remember."
)
MAX_DRAFT_BODY = 1800
OUT_DIR = "/tmp/cupid" if os.name != "nt" else os.path.join(
    os.environ.get("TEMP", "."), "cupid")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

FONT = "font-family:Georgia,'Times New Roman',serif;"
LINK = "color:#c2185b;font-weight:bold;text-decoration:none;"


def esc(s):
    return html.escape(str(s or ""), quote=True)


def mailto(draft, label):
    subject = str(draft.get("subject", "")).strip()
    body = str(draft.get("body", "")).strip()
    if not body:
        raise ValueError(f"{label}: empty body")
    if len(body) > MAX_DRAFT_BODY:
        print(f"WARN {label}: body is {len(body)} chars (> {MAX_DRAFT_BODY})",
              file=sys.stderr)
    return ("mailto:?subject=" + urllib.parse.quote(subject)
            + "&body=" + urllib.parse.quote(body))


def job_block(i, job):
    for key in ("title", "org", "url", "reasoning", "cover_letter", "intro_email"):
        if not job.get(key):
            raise ValueError(f"job {i}: missing '{key}'")
    url = str(job["url"]).strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"job {i}: url must start with http(s): {url}")

    header_bits = [job["title"], job["org"], job.get("location"), job.get("pay")]
    header = " – ".join(esc(b) for b in header_bits if b)
    cover = mailto(job["cover_letter"], f"job {i} cover_letter")
    intro = mailto(job["intro_email"], f"job {i} intro_email")

    starter = ""
    if job.get("starter"):
        starter = (f'<p style="margin:8px 0;"><b>→ Starter:</b> '
                   f'{job["starter"]}</p>')

    return f"""
<div style="border-left:4px solid #e91e63;padding:10px 14px;margin:18px 0;background:#fff7fa;">
  <p style="margin:0 0 8px 0;font-size:16px;"><b>{i}. {header}</b></p>
  <p style="margin:8px 0;">{job["reasoning"]}</p>
  {starter}
  <p style="margin:10px 0 0 0;line-height:1.9;">
    <a href="{esc(url)}" style="{LINK}">\U0001F517 View the posting</a><br>
    <a href="{esc(cover)}" style="{LINK}">✍️ Draft my cover letter</a><br>
    <a href="{esc(intro)}" style="{LINK}">\U0001F4E7 Draft an intro email</a>
  </p>
</div>"""


def build_html(data):
    jobs = data.get("jobs") or []
    if len(jobs) > 3:
        raise ValueError(f"at most 3 jobs, got {len(jobs)}")
    blocks = "".join(job_block(i, j) for i, j in enumerate(jobs, 1))
    feedback = data.get("feedback_line") or DEFAULT_FEEDBACK
    signoff = data.get("signoff") or ""
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#ffffff;">
<div style="max-width:640px;margin:0 auto;padding:16px;{FONT}font-size:15px;color:#222;line-height:1.5;">
  <p style="margin:0 0 12px 0;">{data.get("greeting", "")}</p>
  {blocks}
  <p style="margin:18px 0 8px 0;font-style:italic;">{esc(feedback)}</p>
  <p style="margin:8px 0;">{signoff}</p>
  <p style="margin:8px 0;"><b>{SIGNATURE}</b></p>
</div>
</body></html>"""


def send(payload, key):
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "User-Agent": UA},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print("RESEND", r.status, r.read().decode())
            return 0
    except urllib.error.HTTPError as e:
        print("RESEND_ERR", e.code, e.read().decode())
        return 1
    except urllib.error.URLError as e:
        print("RESEND_ERR network", e.reason)
        return 1


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    ap =argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("jobs_json")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--test", action="store_true")
    args = ap.parse_args()

    with open(args.jobs_json, encoding="utf-8") as f:
        data = json.load(f)
    subject = str(data.get("subject", "")).strip()
    if not subject:
        print("ERROR jobs.json: missing 'subject'")
        return 2
    try:
        body = build_html(data)
    except ValueError as e:
        print("ERROR", e)
        return 2

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "body.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"built {out} ({len(body)} chars, {len(data.get('jobs') or [])} job(s))")

    if args.dry_run:
        print("DRY RUN: not sent. Subject:", subject)
        return 0

    key = os.environ.get("CUPID_RESEND_KEY") or os.environ.get("RESEND_API_KEY")
    if not key:
        print("ERROR no CUPID_RESEND_KEY in the environment")
        return 2

    payload = {"from": FROM, "reply_to": REPLY_TO, "html": body}
    if args.test:
        payload.update(to=TEST_TO, subject="[TEST] " + subject)
    else:
        payload.update(to=TO, cc=CC, subject=subject)
    return send(payload, key)


if __name__ == "__main__":
    sys.exit(main())
