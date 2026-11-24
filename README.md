# cupid-job-robot 🤖❤️

The memory for Ed's weekday job-scout robot. Every weekday at 8am (America/New_York) a
scheduled Claude cloud agent reads this repo, finds 3 fresh jobs for Lida, drafts her cover
letters, emails them, and then writes back here so it never repeats itself.

This repo holds **state only** — no resume, no passwords. The robot's instructions and
Lida's profile live in the scheduled routine itself.

## Files

- **`state/exclude.json`** — jobs / companies the robot must NEVER suggest. Add anything
  Lida passes on. The robot skips any posting whose org + title matches an entry here
  (fuzzy match — close is close enough).
- **`state/history.md`** — append-only log of what the robot has already sent, so it doesn't
  repeat a job and can make the occasional callback ("you ghosted Tuesday's three, so…").

## How to kill a job forever

Hate a suggestion? Add it to `state/exclude.json`:

```json
{ "org": "Acme Corp", "title": "Office Manager", "reason": "too far a commute", "added": "2026-07-20" }
```

…or just tell Ed and he'll add it.

## Sending (`send.py`)

The routine does not build the email in Bash. It writes the day's picks to
`/tmp/cupid/jobs.json` with its Write tool, then runs one short command:

```sh
CUPID_RESEND_KEY=re_xxx python3 /tmp/cupid/send.py /tmp/cupid/jobs.json
```

`send.py` builds the HTML, URL-encodes the cover-letter and intro-email `mailto:` links,
and posts to Resend. The recipients are fixed in the script, except Ed's own address:
the script reads it from the `CUPID_CC` environment variable (set it on the cloud
environment). It is the CC on real sends and the only recipient of `--test` sends, and the
script refuses to send without it. See `example.jobs.json` for the input shape. Use
`--dry-run` to build without sending, and `--test` to send to Ed only.

Ed's address is kept out of the script on purpose: a privacy plugin in the cloud
environment refuses to run any script that holds the account's email address next to a
browser-style User-Agent. For the same reason the User-Agent is a plain `cupid-sender/1.0`.

Why: long heredocs and inline `python3 -c` scripts trip the Claude Code bash safety
parser. The parser then stops the unattended run and asks Ed for permission on his phone.

---

## Ladd Observatory ticket watcher (`ladd/`, `.github/workflows/ladd-tickets.yml`)

Separate from the job robot. Every Tuesday, a GitHub Action polls the
[Ladd Observatory Eventbrite page](https://www.eventbrite.com/o/34803107253) every 20s from
7:00 to 8:45am ET. The moment a show has tickets, it fires a Home Assistant webhook, and HA
pushes to your phones through the companion app. Tap the alert → event page → register.

It does not register for you. A human still has to click through checkout.

### Setup (once)
1. In Home Assistant, create the automation in `ladd/home-assistant-automation.yaml`
   (set your own random `webhook_id` and your `notify.mobile_app_*` targets).
2. Your webhook URL must be reachable from the internet:
   - Nabu Casa: Settings → Home Assistant Cloud → Webhooks → copy the `hooks.nabu.casa/...` URL.
   - Otherwise: `https://<your-external-ha-host>/api/webhook/<webhook_id>`.
3. In this repo: Settings → Secrets and variables → Actions → New secret
   `LADD_HA_WEBHOOK_URL` = that URL. (Optional backup: `LADD_NTFY_TOPIC` also works.)
4. Actions tab → "Ladd ticket watcher" → Run workflow (leave "once" checked) to confirm it can
   read the page. To test the HA side, `curl -X POST -H 'Content-Type: application/json'
   -d '{"title":"test","message":"test","url":"https://example.com"}' <webhook url>`.

To change the window or poll rate, edit `START_ET` / `END_ET` / `INTERVAL` in the workflow.
Run locally: `HA_WEBHOOK_URL=... python3 ladd/watch.py`.
