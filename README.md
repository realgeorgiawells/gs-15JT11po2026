# Goalscraper

Every morning at 6:15 Irish time, Goalscraper scores each game in the next 24 hours, in your chosen
competitions, on how unlikely it is to end 0-0 (1.00 to 100.00), and publishes the list as a phone app.

**Setting it up:** follow the Goalscraper setup guide from the chat with Claude.

## What's in here

| Path | What it is |
| --- | --- |
| `goalscraper.py` | The daily job: fetches data from OpenFootAPI, rates teams, scores games, writes the app |
| `config/settings.json` | Top-tier size, form weight, request limits per run |
| `config/competitions.json` | Your 52 competitions, priority values, starting league strengths, OpenFootAPI IDs |
| `web/` | The app itself (page, logo, icons, offline support) |
| `.github/workflows/goalscraper.yml` | Runs the job daily on GitHub and publishes the app |
| `WORKFLOW-COPY.txt` | A copy of the workflow file, for pasting in if the `.github` folder didn't upload |
| `tools/` | Logo generator, a simulated OpenFootAPI for testing, and a preview builder |
| `data/` | Created by the runs: today's list, coverage report, tracking history. `store.json` (saved results) is kept in GitHub's cache, not the repo |

## How a game is scored

1. Team strength: attack and defence ratings fitted to this season's results (plus last season when a
   team has few games), adjusted for the strength of each opponent and each team's league.
   Teams in cups and European competitions are rated from their own league's results too.
2. Recent form nudges those ratings slightly (15% by default).
3. P(0-0) comes from the expected goals; the score maps P(0-0) of 1% or less to 100 and 30% or more to 1.
   Teams with little data are tagged and trimmed slightly. (OpenFootAPI's free plan has no odds.)

## Requests

OpenFootAPI's free plan allows 5,000 requests a month, 50 results per request. Each run fetches the last
couple of days for all competitions in a few requests, and the full season for a competition only the first
time it has games. A normal day uses about 10-20 requests; each run is capped so the month's quota is spread out.

## Running it yourself

```
export OPENFOOT_API_KEY=your_key
python goalscraper.py           # normal run
python goalscraper.py --mock    # simulated data, no key needed
```
Needs Python 3.9 or newer and nothing else. The output goes to `site/` (open `site/index.html` through a
local web server, e.g. `python -m http.server -d site`).
