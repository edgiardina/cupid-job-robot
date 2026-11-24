#!/usr/bin/env python3
"""Watch the Ladd Observatory Eventbrite page and push an alert the moment tickets open.

It does NOT register for you. It tells your phone, fast, so a human can grab them.

Env (set at least one):
  HA_WEBHOOK_URL  Home Assistant webhook URL. Gets a JSON POST:
                  {"title","message","url","events":[{name,when,url}...]}
  NTFY_TOPIC      ntfy.sh topic to push to.
  START_ET     poll window start, HH:MM America/New_York (default 07:00)
  END_ET       poll window end   (default 08:45)
  INTERVAL     seconds between checks (default 20)
  ONCE=1       check once, print what it sees, exit (for testing)
"""
import json, os, re, sys, time, urllib.request
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

ORG_URL = "https://www.eventbrite.com/o/34803107253"
ET = ZoneInfo("America/New_York")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def hm(s):
    h, m = s.split(":")
    return dtime(int(h), int(m))


def fetch_events():
    req = urllib.request.Request(ORG_URL, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("page layout changed: no __NEXT_DATA__")
    found = {}

    def walk(o):
        if isinstance(o, dict):
            if "eventbrite_event_id" in o and "event_sales_status" in o:
                found[o["id"]] = o
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(json.loads(m.group(1)))
    return list(found.values())


def summarize(e):
    return {
        "id": e["id"],
        "name": e.get("name", "?"),
        "when": f'{e.get("start_date", "?")} {e.get("start_time", "")[:5]}',
        "status": (e.get("event_sales_status") or {}).get("sales_status", "?"),
        "available": bool((e.get("ticket_availability") or {}).get("has_available_tickets")),
        "url": e.get("url") or f'https://www.eventbrite.com/e/{e["id"]}',
    }


def notify(title, body, url, events=(), priority="urgent"):
    hook = os.environ.get("HA_WEBHOOK_URL", "").strip()
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if hook:
        payload = {"title": title, "message": body, "url": url,
                   "events": [{k: e[k] for k in ("name", "when", "url")} for e in events]}
        req = urllib.request.Request(hook, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=20).read()
    if topic:
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}",
            data=body.encode(),
            headers={"Title": title, "Priority": priority, "Tags": "telescope", "Click": url},
        )
        urllib.request.urlopen(req, timeout=20).read()


def main():
    once = os.environ.get("ONCE") == "1"
    topic = bool(os.environ.get("NTFY_TOPIC", "").strip() or os.environ.get("HA_WEBHOOK_URL", "").strip())
    if not topic and not once:
        sys.exit("set HA_WEBHOOK_URL or NTFY_TOPIC")
    start, end = hm(os.environ.get("START_ET", "07:00")), hm(os.environ.get("END_ET", "08:45"))
    interval = int(os.environ.get("INTERVAL", "20"))

    alerted, errors = set(), 0
    while True:
        now = datetime.now(ET)
        if not once and now.time() >= end:
            print(f"{now:%H:%M:%S} window over, nothing more to do")
            return
        if not once and now.time() < start:
            wait = (datetime.combine(now.date(), start, ET) - now).total_seconds()
            print(f"{now:%H:%M:%S} waiting {int(wait)}s for window start")
            time.sleep(min(wait, 300))
            continue
        try:
            events = [summarize(e) for e in fetch_events()]
            errors = 0
        except Exception as ex:  # network blip or layout change
            errors += 1
            print(f"{now:%H:%M:%S} fetch failed ({errors}): {ex}")
            if errors == 10 and topic:
                notify("Ladd watcher is failing", f"10 failed checks in a row: {ex}\nCheck manually: {ORG_URL}", ORG_URL, priority="high")
            if once:
                sys.exit(1)
            time.sleep(interval)
            continue

        open_now = [e for e in events if e["available"] or e["status"] == "on_sale"]
        print(f"{now:%H:%M:%S} {len(events)} events; " +
              "; ".join(f'{e["when"]} {e["status"]}{"*" if e["available"] else ""}' for e in events))
        new = [e for e in open_now if e["id"] not in alerted]
        if new and topic:
            lines = [f'{e["name"]} — {e["when"]}' for e in new]
            notify("LADD TICKETS ARE OPEN", "\n".join(lines) + "\nTap to register.", new[0]["url"], new)
            alerted.update(e["id"] for e in new)
            print("ALERT SENT:", ", ".join(lines))
        if once:
            return
        time.sleep(interval)


if __name__ == "__main__":
    main()
