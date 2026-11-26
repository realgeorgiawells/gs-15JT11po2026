# Goalscraper

Every morning at 6:15 Irish time, Goalscraper rates today's and tomorrow's games in your chosen competitions for
four sections and picks the best for each day. The phone app shows today's picks (games that have kicked off move to
the bottom) and switches to tomorrow's at midnight. At about 6 pm a short update brings in the results so far and
marks postponed games. Every prediction and every result is kept, and the model checks itself against them each
morning.

## The four sections

| Section | A pick goes wrong if… | Rules |
| --- | --- | --- |
| Easy Goals | the game ends 0-0 | — |
| Misses | the team wins | any game that isn't a Ballon d'Or pick |
| Ballon d'Or | the team doesn't win | the favourite in any game |
| Raining Goals | either team fails to score | — |

Each game gets a 1-100 score per section, on that section's own scale (set in `config/settings.json`). **Every game
over its section's pass mark is a pick**, however many that is: 65 in every section (about a 95% chance of a goal in
Easy Goals, an 83% chance of not winning in Misses, an 84% chance of winning in Ballon d'Or, a 66% chance of both
scoring in Raining Goals). Picks are chosen per day; the app shows today's and switches to tomorrow's at 23:50. The
Selected tab lists the picks from Easy Goals, Misses and Ballon d'Or in kickoff order.

Old limits can be switched back on in `config/settings.json` if needed: `max_chance_of_goal` (Easy Goals "too
short"), `longest_price` (Misses underdogs) and `min_favourite` (Ballon d'Or).

**Internationals** have a pass mark 10 below each section's, because national teams play few games and their scores
run lower. The gap shrinks by 1 point for every 50 international games Goalscraper has predicted and settled, never
grows, and pauses while the model check flags internationals for review.

**Clubs in Europe:** OpenFootAPI gives clubs a separate id in European and other continental competitions; each is
linked to the club's league id, so its league results count in every competition.

## The app

- **Selected / Easy Goals / Misses / Ballon d'Or / Raining Goals** (bottom bar): today's picks, with the next best below.
- **Menu (≡):** All games, By competition, Record, Coverage, How it works.
- **Record:** a tab per section (last 30 days and all time, by score, by competition, every settled pick by day)
  and **All results**: every stored result, with Goalscraper's scores for the games it rated, and the **model
  check**: forecast against actual (0-0s, draws, home wins, both scoring) for each competition over 180 days,
  flagged for review when the gap is too big to be bad luck.
- **Coverage:** the last run, requests used, the evening update, the international pass mark and every change the
  model has made to itself.

## How the model works

1. Team strength: attack and defence ratings fitted to results (this season plus last), adjusted for each opponent and
   league. Cup and European sides are rated from their own league too. National teams use three years of internationals.
2. Recent form adds a little on top. Win, draw and loss chances use a draw correction.
3. Every prediction is saved in `data/log/` (one file per month) and settled with the result.
4. Each morning the model checks itself against those results and nudges, within limits: draw correction, favourite
   strength, 0-0 and both-score allowances (clubs and internationals separately), form weight, how fast old games fade,
   and league strengths. What it has learned is in `data/model_state.json`.

## What's in here

| Path | What it is |
| --- | --- |
| `goalscraper.py` | The program: fetches data from OpenFootAPI, rates teams, scores games, writes the app |
| `config/settings.json` | Pass marks, section scales, run times, request limits |
| `config/competitions.json` | Your competitions, priority values, starting league strengths, OpenFootAPI IDs |
| `web/` | The app itself (page, logo, icons, offline support) |
| `.github/workflows/goalscraper.yml` | Runs it on GitHub (6:15 and 18:00 Irish time) and publishes the app |
| `data/archive/` | **Permanent results archive:** every result OpenFootAPI has returned, one file per month, never deleted |
| `data/log/` | Every prediction Goalscraper has made, with its result |
| `data/` (other files) | Today's list, record, coverage report, model state |
| `tools/mockopenfoot.py` | A simulated OpenFootAPI for testing (`python goalscraper.py --mock`) |

`data/store.json` (the working copy of recent results) lives in GitHub's cache, not the repository. If GitHub ever
clears it, the next run rebuilds it from `data/archive/` without extra requests.

## Requests

OpenFootAPI's free plan allows 5,000 requests a month, 50 results per request. The morning run fetches the last
couple of days for all competitions in a few requests, and a competition's full season only the first time it has
games: usually 10-20 requests. The evening update uses about 3-5. Each run is capped so the month's quota is spread
out, with 100 always kept in reserve. Every Monday the morning run also looks back 14 days for results OpenFootAPI added
late (about 30 requests).

**Results only:** some competitions on OpenFootAPI only get results after the games are played, never the games
beforehand. For those with a `tsdb_id` in `config/competitions.json` (Scotland, Portugal, Turkey, Belgium, Greece,
Brazil, Argentina, Denmark, Austria, Mexico, Poland, Serie B, Segunda, Ligue 2, Ecuador, MLS, J-League, Norway and
more), the upcoming games come from TheSportsDB's free API (about 40 requests a day, no key needed) and both teams are
matched strictly to OpenFootAPI's names. A game that can't be matched is skipped and listed under Notes on Coverage;
add the pair to `config/team_aliases.json` to fix it. Their picks settle when OpenFootAPI adds the results (up to 14
days). Any other results-only competition is labelled "Results only" on Coverage.

## Running it by hand

On GitHub: **Actions → Goalscraper daily → Run workflow**, then pick **full** (a new list now) or **evening**
(results so far). A manual run never stops the 6:15 run.

On a computer:

```
export OPENFOOT_API_KEY=your_key
python goalscraper.py             # full run
python goalscraper.py --evening   # evening update
python goalscraper.py --mock      # simulated data, no key needed
```

Needs Python 3.9 or newer and nothing else. The output goes to `site/` (open it through a local web server,
e.g. `python -m http.server -d site`).
