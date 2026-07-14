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
