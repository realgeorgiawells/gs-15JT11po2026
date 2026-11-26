#!/usr/bin/env python3
"""
Goalscraper: each morning, rate every game in the next 24 hours for four sections:
  Easy Goals (at least one goal), Misses (a team not to win), Ballon d'Or (a team to win),
  Raining Goals (both teams to score). Every prediction is stored, settled and used to self-adjust the model.
Data: OpenFootAPI (free Starter plan, 5,000 requests a month).

  python goalscraper.py                    # full run: new list for the next 24 hours (needs OPENFOOT_API_KEY)
  python goalscraper.py --evening          # evening update: results so far and postponements, no new list
  python goalscraper.py --mock             # simulated data, no key needed (for testing)

Scheduled on GitHub: the full run at 6:15 and the evening update at 18:00, Irish time.
Results are kept in data/store.json between runs (GitHub's cache), so only the last couple of days are fetched,
and every result is also kept for good in data/archive/ (one file per month), which rebuilds the store if the
cache is ever lost. Writes data/*.json and site/ (the app that gets published). Python 3.9+, no packages needed.
"""
import argparse
import base64
import json
import math
import os
import re
import shutil
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from difflib import SequenceMatcher
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
CONFIG, DATA, WEB, SITE = ROOT / "config", ROOT / "data", ROOT / "web", ROOT / "site"
BASE = "https://openfootapi.com/v1"
CALENDAR_COUNTRIES = {"sweden", "ireland", "usa", "united states", "japan", "brazil", "argentina", "norway", "finland",
                      "iceland", "china", "korea republic", "south korea", "colombia", "chile", "uruguay", "ecuador",
                      "peru", "paraguay", "bolivia", "venezuela", "canada", "latvia", "lithuania", "estonia",
                      "belarus", "faroe islands", "kazakhstan", "uzbekistan", "georgia", "moldova"}
CUP_WORDS = ("cup", "pokal", "copa", "coppa", "coupe", "cupa", "champions", "europa", "conference", "libertadores",
             "sudamericana", "nations league", "world cup", "concacaf", "afc ")


class BudgetExhausted(Exception):
    pass


class PlanBlocked(Exception):
    pass


class ApiError(Exception):
    pass


# ----------------------------------------------------------------------------------------------
# OpenFootAPI client: request budget + cursor paging
# ----------------------------------------------------------------------------------------------
class OpenFoot:
    def __init__(self, key, delay=0.35):
        self.key, self.delay = key, delay
        self.used, self.limit = 0, 10**9
        self.quota_remaining = None
        self.plan = "unknown"
        self.cursor_param = None
        self.budget_rule = None      # function(monthly remaining) -> max requests for this run
        self._budget_set = False
        self._last = 0.0

    def get(self, path, **params):
        if self.used >= self.limit:
            raise BudgetExhausted()
        url = f"{BASE}/{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.key}", "Accept": "application/json",
                                                   "User-Agent": "Goalscraper/1.0"})
        for attempt in range(4):
            wait = self.delay - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    data = json.load(r)
                break
            except urllib.error.HTTPError as e:
                self.used += 1
                try:
                    err = (json.load(e) or {}).get("error") or {}
                except Exception:
                    err = {}
                code, msg = err.get("code", ""), err.get("message", "")
                if e.code == 429 and "quota" in code:
                    self.used = self.limit
                    raise BudgetExhausted()
                if e.code == 429 and attempt < 3:
                    time.sleep(61)
                    continue
                if e.code in (401, 403):
                    raise PlanBlocked(f"{e.code} {code} {msg}".strip())
                if e.code in (502, 503, 504) and attempt < 3:
                    time.sleep(10 * (attempt + 1))
                    continue
                raise ApiError(f"HTTP {e.code} {code} {msg}".strip())
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if attempt < 3:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise ApiError(f"network: {e}")
        else:
            raise ApiError("gave up after retries")
        self.used += 1
        acc = ((data.get("meta") or {}).get("access") or {})
        if acc.get("remaining") is not None:
            self.quota_remaining = int(acc["remaining"])
        if acc.get("plan"):
            self.plan = acc["plan"]
        if self.budget_rule and not self._budget_set and self.quota_remaining is not None:
            self.limit = self.used + max(0, self.budget_rule(self.quota_remaining))
            self._budget_set = True
        return data

    def get_all(self, path, max_pages=40, **params):
        """Every page of a list. OpenFootAPI pages 50 at a time with meta.pagination.next_cursor."""
        out, seen = [], set()
        d = self.get(path, **params)
        page = d.get("data") or []
        for x in page:
            seen.add(x.get("id"))
        out += page
        meta = d.get("meta") or {}
        total = meta.get("total_count")
        cursor = (meta.get("pagination") or {}).get("next_cursor")
        pages = 1
        while cursor and pages < max_pages and (total is None or len(out) < total):
            names = [self.cursor_param] if self.cursor_param else ["cursor", "after", "next_cursor", "page_cursor"]
            got = False
            for name in names:
                d = self.get(path, **params, **{name: cursor})
                pages += 1
                new = [x for x in (d.get("data") or []) if x.get("id") not in seen]
                if new:
                    self.cursor_param = name
                    for x in new:
                        seen.add(x.get("id"))
                    out += new
                    meta = d.get("meta") or {}
                    cursor = (meta.get("pagination") or {}).get("next_cursor")
                    got = True
                    break
            if not got:
                print(f"  warning: could not get the next page for {path} {params}; kept {len(out)} of {total}")
                break
        return out


# ----------------------------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------------------------
def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def save_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def to_ts(iso):
    return int(datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp())


def is_qualifying_round(rnd):
    r = norm(rnd)
    return "qualif" in r or "preliminary" in r or r in ("play offs", "playoff", "play off round")


def season_label(start_year, calendar):
    return str(start_year) if calendar else f"{start_year}/{(start_year + 1) % 100:02d}"


def season_prev(label):
    m = re.match(r"^(\d{4})/(\d{2})$", str(label))
    if m:
        y = int(m.group(1)) - 1
        return season_label(y, False)
    if re.match(r"^\d{4}$", str(label)):
        return str(int(label) - 1)
    return None


def poisson_pmf(k, lam):
    return math.exp(-lam) * lam**k / math.factorial(k)


def rating(x, spread):
    return round(50 + 50 * math.tanh(x / spread), 1)


# ----------------------------------------------------------------------------------------------
# Results store (kept between runs)
#   matches: id -> [comp, season, ts, home, away, home_goals, away_goals, status, round]
#   teams:   id -> [name, home competition, country]
# ----------------------------------------------------------------------------------------------
class Store:
    def __init__(self, path):
        self.path = path
        d = load_json(path, {})
        self.matches = d.get("matches", {})
        self.teams = d.get("teams", {})
        self.comps = d.get("comps", {})
        self.backfilled = d.get("backfilled", {})
        self.last_sweep = d.get("last_sweep")
        self.seasons = d.get("seasons", {})      # comp -> latest season label seen
        self.upcoming = d.get("upcoming", {})    # comp -> last date OpenFootAPI listed a game before it was played
        self.upcoming_since = d.get("upcoming_since")   # when that tracking started
        self.team_alias = {}                     # European/continental id -> the same club's league id (rebuilt each run)

    def save(self, keep_after_ts, keep_longer=(), longer_after_ts=None):
        """Drop old results; international competitions are kept longer (national teams play rarely)."""
        self.matches = {k: v for k, v in self.matches.items()
                        if v[2] >= keep_after_ts or (v[0] in keep_longer and v[2] >= (longer_after_ts or keep_after_ts))}
        save_json(self.path, {"matches": self.matches, "teams": self.teams, "comps": self.comps,
                              "backfilled": self.backfilled, "last_sweep": self.last_sweep, "seasons": self.seasons,
                              "upcoming": self.upcoming, "upcoming_since": self.upcoming_since})

    def add(self, m):
        """m: an OpenFootAPI match object."""
        mid = m.get("id")
        if not mid:
            return None
        comp = fix_comp(mid, m.get("competitionId") or "")
        if comp is None:
            return None
        season = str(m.get("season") or "")
        ht, at = m.get("homeTeam") or {}, m.get("awayTeam") or {}
        hid = fix_team(mid, ht.get("id") or ("name:" + norm(ht.get("name"))))
        aid = fix_team(mid, at.get("id") or ("name:" + norm(at.get("name"))))
        for t in (hid, aid):
            if t in self.team_alias and t not in self.teams:
                self.teams[t] = [t, None, None]
        for t, tid in ((ht, hid), (at, aid)):
            prev = self.teams.get(tid, [None, None, None])
            home_comp = fix_comp(mid, t.get("competitionId")) or prev[1]
            if home_comp and self.is_cup(home_comp) and prev[1] and not self.is_cup(prev[1]):
                home_comp = prev[1]
            self.teams[tid] = [t.get("name") or prev[0], home_comp, t.get("country") or prev[2]]
        sc = m.get("score") or {}
        status = norm(m.get("status"))
        rec = [comp, season, to_ts(m["kickoffAt"]), self.team_alias.get(hid, hid), self.team_alias.get(aid, aid),
               sc.get("home"), sc.get("away"), status, m.get("round") or "", bool(m.get("kickoffTimeKnown", True))]
        if comp != (m.get("competitionId") or "") and self.duplicate(mid, rec):
            return None
        self.matches[mid] = rec
        if comp and status in ("scheduled", "unknown", "") and rec[2] > time.time():
            self.upcoming[comp] = datetime.now(timezone.utc).date().isoformat()
        if season and comp:
            old = self.seasons.get(comp, "")
            if not old or season[:4] > old[:4] or (season[:4] == old[:4] and len(season) > len(old)):
                self.seasons[comp] = season
        return mid

    def duplicate(self, mid, rec):
        """A relabelled game that the store already has under its proper competition."""
        day = rec[2] // 86400
        return any(k != mid and v[0] == rec[0] and v[3] == rec[3] and v[4] == rec[4] and v[2] // 86400 == day
                   for k, v in self.matches.items())

    def comp_name(self, cid):
        return (self.comps.get(cid) or {}).get("name") or cid if cid != "_fetched" else cid

    def is_cup(self, cid):
        n = norm(self.comp_name(cid)) + " " + norm(cid.replace("_", " "))
        return any(w in n for w in CUP_WORDS)


# ----------------------------------------------------------------------------------------------
# Fixes for OpenFootAPI's results-only ("fd") feed, which files some leagues under the wrong competition
# (e.g. England's National League under "LigaPro (Ecuador)" and "World Cup"). Set in settings.json.
# ----------------------------------------------------------------------------------------------
FEED_FIXES = {"remap": {}, "drop": set(), "teams": {}}


def fix_team(mid, tid):
    """Same club, different id in a mislabelled copy (e.g. team_southend_worl -> team_southend_ecua)."""
    if str(mid).startswith("match_fd_"):
        for old, new in FEED_FIXES["teams"].items():
            if str(tid).endswith(old):
                return str(tid)[: -len(old)] + new
    return tid


def fix_comp(mid, comp):
    """The right competition for a game, or None to ignore it."""
    if comp and str(mid).startswith("match_fd_"):
        if comp in FEED_FIXES["drop"]:
            return None
        return FEED_FIXES["remap"].get(comp, comp)
    return comp


def apply_feed_fixes(store, archive):
    """Apply the fixes to what is already saved (store and archive). Mislabelled copies are removed."""
    if not FEED_FIXES["remap"] and not FEED_FIXES["drop"]:
        return 0
    n = 0

    def fixed(mid, comp, h, a):
        return fix_comp(mid, comp), fix_team(mid, h), fix_team(mid, a)

    keys = {(v[0], v[2] // 86400, v[3], v[4]) for k, v in store.matches.items() if fixed(k, v[0], v[3], v[4]) == (v[0], v[3], v[4])}
    for mid in list(store.matches):
        v = store.matches[mid]
        new = fixed(mid, v[0], v[3], v[4])
        if new == (v[0], v[3], v[4]):
            continue
        key = (new[0], v[2] // 86400, new[1], new[2])
        if new[0] is None or key in keys:
            del store.matches[mid]
        else:
            v[0], v[3], v[4] = new
            keys.add(key)
        n += 1
    for tid in list(store.teams):
        t = store.teams[tid]
        if t[1] in FEED_FIXES["remap"]:
            t[1] = FEED_FIXES["remap"][t[1]]
        new = fix_team("match_fd_", tid)
        if new != tid:
            store.teams.setdefault(new, t)
            del store.teams[tid]
    for month in archive.months_on_disk():
        rows = archive.load(month)
        keys = {(r[0], r[2] // 86400, r[9], r[10]) for k, r in rows.items() if fixed(k, r[0], r[9], r[10]) == (r[0], r[9], r[10])}
        for mid in list(rows):
            r = rows[mid]
            new = fixed(mid, r[0], r[9], r[10])
            if new == (r[0], r[9], r[10]):
                continue
            key = (new[0], r[2] // 86400, new[1], new[2])
            if new[0] is None or key in keys:
                del rows[mid]
            else:
                r[0], r[9], r[10] = new
                keys.add(key)
            archive.dirty.add(month)
            n += 1
    tf = archive.folder / "teams.json"
    teams = load_json(tf, {})
    moved = {k: fix_team("match_fd_", k) for k in teams if fix_team("match_fd_", k) != k}
    if moved:
        for old, new in moved.items():
            teams.setdefault(new, teams[old])
            del teams[old]
        save_json(tf, teams)
    archive.save()
    return n


# ----------------------------------------------------------------------------------------------
# TheSportsDB (free key): upcoming games for competitions where OpenFootAPI only has results
# ----------------------------------------------------------------------------------------------
class SportsDB:
    BASE = "https://www.thesportsdb.com/api/v1/json/{key}/"

    def __init__(self, key="123", gap=3.0):
        self.key, self.gap = key, gap
        self.used, self.last, self.errors = 0, 0.0, []

    def get(self, path):
        for attempt in range(6):
            wait = self.gap - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            self.used += 1
            req = urllib.request.Request(self.BASE.format(key=self.key) + path, headers={"User-Agent": "Goalscraper"})
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code == 429:              # free key: about 30 a minute
                    time.sleep(30)
                    continue
                self.errors.append(f"TheSportsDB {path.split('?')[0]}: HTTP {e.code}")
                return None
            except Exception as e:
                self.errors.append(f"TheSportsDB {path.split('?')[0]}: {e}"[:120])
                return None
        self.errors.append("TheSportsDB: too many requests, gave up")
        return None

    def day(self, league_id, d):
        return [e for e in ((self.get(f"eventsday.php?d={d}&l={league_id}") or {}).get("events") or []) if e]


TEAM_FILLER = {"fc", "cf", "sc", "ac", "afc", "cd", "ca", "club", "de", "sk", "fk", "if", "bk", "ff", "sv", "calcio",
               "the", "sad", "ec", "se", "cr", "us", "as", "rc", "kv", "krc", "fcv"}


def team_key(name):
    return " ".join(w for w in norm(name).split() if w not in TEAM_FILLER)


def match_team(name, pool, aliases):
    """Strict match of a TheSportsDB team name to one OpenFootAPI team (pool: id -> name). None if unsure."""
    if not pool:
        return None
    target = aliases.get(name)
    keys = {tid: team_key(nm) for tid, nm in pool.items()}
    for want in ([team_key(target)] if target else []) + [team_key(name)]:
        exact = [t for t, k in keys.items() if k == want]
        if len(exact) == 1:
            return exact[0]
    k = team_key(name)
    if len(k) >= 4:
        within = [t for t, pk in keys.items() if len(pk) >= 4 and (k in pk or pk in k)]
        if len(within) == 1:
            return within[0]
    ranked = sorted(((SequenceMatcher(None, k, pk).ratio(), t) for t, pk in keys.items()), reverse=True)
    if ranked and ranked[0][0] >= 0.86 and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= 0.08):
        return ranked[0][1]
    return None


def tsdb_time(e):
    ts = e.get("strTimestamp")
    if ts:
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return int((t if t.tzinfo else t.replace(tzinfo=timezone.utc)).timestamp())
        except ValueError:
            pass
    if e.get("dateEvent") and e.get("strTime"):
        try:
            return int(datetime.fromisoformat(f"{e['dateEvent']}T{e['strTime'][:8]}+00:00").timestamp())
        except ValueError:
            pass
    return None


# ----------------------------------------------------------------------------------------------
# Permanent results archive (data/archive/, committed to the repository, never pruned)
#   YYYY-MM.json:      id -> [comp, season, ts, home name, away name, home goals, away goals, status, round, home id, away id]
#   teams.json:        id -> [name, home competition, country]
#   competitions.json: id -> {name, country}
#   meta.json:         which seasons have been collected, so a rebuilt store needs no extra requests
# ----------------------------------------------------------------------------------------------
FINAL_STATUSES = ("finished", "cancelled", "abandoned", "awarded")


def month_of(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m")


class Archive:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.months, self.dirty = {}, set()

    def months_on_disk(self):
        return sorted(p.stem for p in self.folder.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].json"))

    def load(self, month):
        if month not in self.months:
            self.months[month] = load_json(self.folder / f"{month}.json", {})
        return self.months[month]

    def update_from(self, store):
        """Copy every final result in the store that the archive doesn't hold yet. Nothing is ever removed."""
        added = 0
        for mid, v in store.matches.items():
            if v[7] not in FINAL_STATUSES:
                continue
            m = month_of(v[2])
            rows = self.load(m)
            th = store.teams.get(v[3]) or [v[3]]
            ta = store.teams.get(v[4]) or [v[4]]
            row = [v[0], v[1], v[2], th[0] or v[3], ta[0] or v[4], v[5], v[6], v[7], v[8], v[3], v[4]]
            if rows.get(mid) != row:
                added += mid not in rows
                rows[mid] = row
                self.dirty.add(m)
        for name, new in (("teams.json", store.teams),
                          ("competitions.json", {k: v for k, v in store.comps.items() if k != "_fetched"})):
            old = load_json(self.folder / name, {})
            merged = {**old, **new}
            if merged != old:
                save_json(self.folder / name, merged)
        meta = {"backfilled": store.backfilled, "seasons": store.seasons, "last_sweep": store.last_sweep,
                "upcoming": store.upcoming, "upcoming_since": store.upcoming_since}
        if load_json(self.folder / "meta.json", {}) != meta:
            save_json(self.folder / "meta.json", meta)
        return added

    def save(self):
        for m in self.dirty:
            save_json(self.folder / f"{m}.json", self.months[m])
        self.dirty = set()

    def rebuild_store(self, store, keep_after_ts, longer_after_ts):
        """GitHub's cache was empty: refill the store from the archive (international results are kept longer)."""
        n = 0
        for m in self.months_on_disk():
            if m < month_of(longer_after_ts):
                continue
            for mid, r in self.load(m).items():
                if r[2] >= longer_after_ts:
                    store.matches[mid] = [r[0], r[1], r[2], r[9], r[10], r[5], r[6], r[7], r[8], True]
                    n += 1
        store.teams = load_json(self.folder / "teams.json", {})
        store.comps = load_json(self.folder / "competitions.json", {})
        meta = load_json(self.folder / "meta.json", {})
        store.backfilled = meta.get("backfilled", {})
        store.seasons = meta.get("seasons", {})
        store.last_sweep = meta.get("last_sweep")
        return n

    def merge_upcoming(self, store):
        """Keep the 'listed before it was played' record even if the cache is lost (it is kept in meta.json too)."""
        meta = load_json(self.folder / "meta.json", {})
        for k, v in (meta.get("upcoming") or {}).items():
            if v > store.upcoming.get(k, ""):
                store.upcoming[k] = v
        since = [x for x in (store.upcoming_since, meta.get("upcoming_since")) if x]
        store.upcoming_since = min(since) if since else datetime.now(timezone.utc).date().isoformat()


# ----------------------------------------------------------------------------------------------
# Rating model: opposition-adjusted Poisson attack/defence with priors (see README)
# ----------------------------------------------------------------------------------------------
def fit_pool(matches, priors, spread, half_life_days, ref_ts, iters=40):
    teams = set(priors)
    rows = []
    for m in matches:
        age = max(0.0, (ref_ts - m["ts"]) / 86400)
        w = m.get("w", 1.0) * 0.5 ** (age / half_life_days)
        if w > 1e-4:
            rows.append((m["home"], m["away"], m["gh"], m["ga"], w))
            teams.add(m["home"])
            teams.add(m["away"])
    att = {t: priors.get(t, (0.0, 0.0))[0] for t in teams}
    dfn = {t: priors.get(t, (0.0, 0.0))[1] for t in teams}
    goals = sum(r[4] * (r[2] + r[3]) for r in rows)
    wsum = sum(r[4] for r in rows) or 1.0
    mu = math.log(max(goals / (2 * wsum), 0.3)) if rows else math.log(1.35)
    h = 0.2
    inv = 1.0 / spread**2
    exp = math.exp
    for _ in range(iters):
        gm = hm = gh_ = hh = 0.0
        for H, A, x, y, w in rows:
            lh = exp(mu + h + att[H] - dfn[A])
            la = exp(mu + att[A] - dfn[H])
            gm += w * (x - lh + y - la)
            hm += w * (lh + la)
            gh_ += w * (x - lh)
            hh += w * lh
        if hm > 0:
            mu += gm / hm
            h = min(0.6, max(-0.1, h + gh_ / hh))
        g, hs = defaultdict(float), defaultdict(float)
        for H, A, x, y, w in rows:
            lh = exp(mu + h + att[H] - dfn[A])
            la = exp(mu + att[A] - dfn[H])
            g[H] += w * (x - lh)
            hs[H] += w * lh
            g[A] += w * (y - la)
            hs[A] += w * la
        for t in teams:
            p0 = priors.get(t, (0.0, 0.0))[0]
            att[t] += 0.8 * (g[t] - (att[t] - p0) * inv) / (hs[t] + inv)
        g, hs = defaultdict(float), defaultdict(float)
        for H, A, x, y, w in rows:
            lh = exp(mu + h + att[H] - dfn[A])
            la = exp(mu + att[A] - dfn[H])
            g[A] -= w * (x - lh)
            hs[A] += w * lh
            g[H] -= w * (y - la)
            hs[H] += w * la
        for t in teams:
            p0 = priors.get(t, (0.0, 0.0))[1]
            dfn[t] += 0.8 * (g[t] - (dfn[t] - p0) * inv) / (hs[t] + inv)
    return {"mu": mu, "home": h, "att": att, "def": dfn}


# ----------------------------------------------------------------------------------------------
# Probabilities for a game: win/draw/loss (with draw correction), 0-0, each side scoring, both scoring
# ----------------------------------------------------------------------------------------------
SECTIONS = ("goals", "misses", "ballon", "btts")
NEUTRAL_COMPS = (41, 43, 46, 47, 49, 52)


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def match_probs(lh, la, rho, maxg=10):
    """Dixon-Coles style matrix: rho < 0 adds a little weight to 0-0 and 1-1 (draws), which plain Poisson undercounts."""
    ph = [poisson_pmf(i, lh) for i in range(maxg)]
    pa = [poisson_pmf(j, la) for j in range(maxg)]
    H = D = A = tot = p00 = h0 = a0 = 0.0
    for i in range(maxg):
        for j in range(maxg):
            p = ph[i] * pa[j]
            if i == 0 and j == 0:
                p *= max(0.0, 1 - lh * la * rho)
            elif i == 0 and j == 1:
                p *= max(0.0, 1 + lh * rho)
            elif i == 1 and j == 0:
                p *= max(0.0, 1 + la * rho)
            elif i == 1 and j == 1:
                p *= max(0.0, 1 - rho)
            tot += p
            if i > j:
                H += p
            elif i == j:
                D += p
            else:
                A += p
            if i == 0:
                h0 += p
            if j == 0:
                a0 += p
            if i == 0 and j == 0:
                p00 = p
    return {"w": H / tot, "d": D / tot, "l": A / tot, "p00": p00 / tot,
            "hs": 1 - h0 / tot, "as": 1 - a0 / tot, "btts": (1 - h0 / tot - a0 / tot + p00 / tot)}


def calibrated(lh, la, group, ms):
    """Apply the self-adjusted factors for this group ('club' or 'intl')."""
    f = ms["fav"][group]
    if lh >= la:
        lh2, la2 = lh * math.exp(f), la * math.exp(-f)
    else:
        lh2, la2 = lh * math.exp(-f), la * math.exp(f)
    p = match_probs(lh2, la2, ms["rho"][group])
    p["p00"] = sigmoid(logit(p["p00"]) + ms["z00"][group])
    p["btts"] = sigmoid(logit(p["btts"]) + ms["btts"][group])
    return p


DEFAULT_AT1 = {"goals": 0.30, "misses": 0.60, "ballon": 0.45, "btts": 0.80}


def pass_marks(S, key):
    """(club, international) pass marks for a section. Each section can set its own (sections.X.min_score);
    internationals sit below it by the current international allowance, which shrinks to 0 as results build up."""
    club = S["sections"][key].get("min_score", S["min_score"])
    start, end, _ = intl_pass_cfg(S)
    gap = max(0, end - S.get("_pass_intl", start))
    return club, club - gap


def intl_pass_cfg(S):
    """(start, end, games per point) for the international pass mark, which rises as international results build up."""
    c = S.get("international_pass_mark") or {}
    start = c.get("start", 40)
    return start, c.get("end", S["min_score"]), max(1, c.get("games_per_point", 50))


def scale_score(fail, at100, at50, at1, knot=40):
    """1-100 from the chance of the pick going wrong, on a log scale: at100 -> 100 and at50 -> 50 (the pass mark).
    That line carries on down to the lowest pass mark ('knot', 40 for internationals), so no pick's score changes;
    below it the scale stretches out so the weakest games reach 1 only at at1."""
    f = max(fail, 1e-9)
    slope = 50 / (math.log(at50) - math.log(at100))
    line = 50 + slope * (math.log(at50) - math.log(f))
    if line >= knot:
        return min(100.0, line)
    f_knot = math.exp(math.log(at50) - (knot - 50) / slope)
    return max(1.0, 1 + (knot - 1) * (math.log(at1) - math.log(f)) / (math.log(at1) - math.log(f_knot)))


def section_scores(p, S):
    """Returns {section: {...}} with listed / score / team / p for one game's probabilities."""
    sec = S["sections"]
    knot = min(S["min_score"], intl_pass_cfg(S)[0])      # fixed at the lowest pass mark, so the scale never moves
    sc = lambda f, k: scale_score(f, sec[k]["fail_at_100"], sec[k]["fail_at_50"], sec[k].get("fail_at_1", DEFAULT_AT1[k]), knot)
    out = {}
    g = sec["goals"]
    out["goals"] = {"listed": (1 - p["p00"]) <= (g.get("max_chance_of_goal") or 1.0) + 1e-9,
                    "score": sc(p["p00"], "goals"), "p": 1 - p["p00"]}
    fav = "home" if p["w"] >= p["l"] else "away"
    dog = "away" if fav == "home" else "home"
    pf, pd = (p["w"], p["l"]) if fav == "home" else (p["l"], p["w"])
    b, m = sec["ballon"], sec["misses"]
    out["ballon"] = {"listed": pf >= (b.get("min_favourite") or 0), "team": fav, "p": pf,   # the pass mark decides
                     "score": sc(1 - pf, "ballon")}
    # Misses: any game, unless it's a Ballon d'Or pick (that check happens when ranking)
    out["misses"] = {"listed": not m.get("longest_price") or pd >= 1 / (m["longest_price"] + 1), "team": dog, "p": 1 - pd,
                     "score": sc(pd, "misses")}
    t = sec["btts"]
    out["btts"] = {"listed": True, "score": sc(1 - p["btts"], "btts"), "p": p["btts"]}
    return out


def pick_won(section, team, gh, ga):
    if section == "goals":
        return gh + ga >= 1
    if section == "btts":
        return gh > 0 and ga > 0
    won = gh > ga if team == "home" else ga > gh
    return won if section == "ballon" else not won


# ----------------------------------------------------------------------------------------------
# Prediction log: every game scored (and replayed), one file per month, results filled in later
# ----------------------------------------------------------------------------------------------
class PredLog:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.months, self.dirty = {}, set()

    def month_of(self, ts):
        return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m")

    def load(self, month):
        if month not in self.months:
            self.months[month] = load_json(self.folder / f"{month}.json", {})
        return self.months[month]

    def load_all(self):
        for p in sorted(self.folder.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].json")):
            self.load(p.stem)

    def put(self, fid, entry, replay=False):
        m = self.load(self.month_of(entry["ts"]))
        old = m.get(fid)
        if replay and old and not old.get("rp"):
            return                       # never overwrite a real prediction with a replay
        if old and old.get("r") is not None and entry.get("r") is None:
            entry["r"] = old["r"]
        m[fid] = entry
        self.dirty.add(self.month_of(entry["ts"]))

    def entries(self, from_ts=0, to_ts=10**12):
        for m in self.months.values():
            for fid, e in m.items():
                if from_ts <= e["ts"] < to_ts:
                    yield fid, e

    def settle(self, store, ref_ts):
        index = None
        for month, m in self.months.items():
            for fid, e in m.items():
                if e.get("r") is not None or e["ts"] >= ref_ts:
                    continue
                v = store.matches.get(fid)
                if fid.startswith("tsdb_"):
                    # games listed by TheSportsDB: the result arrives from OpenFootAPI under its own id, often days later
                    if index is None:
                        index = defaultdict(list)
                        for mid, w in store.matches.items():
                            if w[7] == "finished" and w[5] is not None and not mid.startswith("tsdb_"):
                                index[(w[0], w[3], w[4])].append((w[2], mid, w[5], w[6]))
                    hit = [x for x in index.get((v[0], v[3], v[4]), []) if abs(x[0] - v[2]) <= 36 * 3600] if v else []
                    if hit:
                        e["r"], e["m"] = [hit[0][2], hit[0][3]], hit[0][1]
                    elif e["ts"] < ref_ts - 14 * 86400:
                        e["r"] = "void"
                    else:
                        continue
                    self.dirty.add(month)
                    continue
                if v and v[7] == "finished" and v[5] is not None and v[6] is not None:
                    e["r"] = [v[5], v[6]]
                elif (v and v[7] in ("postponed", "cancelled")) or e["ts"] < ref_ts - 4 * 86400:
                    e["r"] = "void"
                else:
                    continue
                self.dirty.add(month)

    def mark_old_replays(self):
        """Earlier versions didn't mark replayed games. They're the ones never ranked (no rank in Raining Goals,
        where every real prediction has one)."""
        n = 0
        for month, m in self.months.items():
            for e in m.values():
                b = (e.get("s") or {}).get("btts")
                if not e.get("rp") and not e.get("v1") and b and b[1] is None:
                    e["rp"] = 1
                    self.dirty.add(month)
                    n += 1
        return n

    def save(self):
        for month in self.dirty:
            save_json(self.folder / f"{month}.json", self.months[month])
        self.dirty = set()


# ----------------------------------------------------------------------------------------------
# Model state: what the daily self-adjustment has learned (data/model_state.json)
# ----------------------------------------------------------------------------------------------
LIMITS = {"rho": (-0.20, 0.05, 0.01), "fav": (-0.15, 0.15, 0.01), "z00": (-0.60, 0.60, 0.04), "btts": (-0.50, 0.50, 0.04)}
MIN_GAMES = {"club": 400, "intl": 150}


def default_state(S):
    sv = S["starting_values"]
    return {"version": 1, "rho": {"club": sv["draw_correction"], "intl": sv["draw_correction"]},
            "fav": {"club": 0.0, "intl": 0.0}, "z00": {"club": 0.0, "intl": 0.0}, "btts": {"club": 0.0, "intl": 0.0},
            "form_weight": sv["form_weight"], "half_life": sv["strength_half_life_days"], "league_adj": {},
            "tuning": {}, "changes": [], "replay_back_to": None}


class Calibrator:
    """Daily: compares stored predictions with results and nudges the model where the evidence says it's off."""

    def __init__(self, state, log, ref_ts, say):
        self.ms, self.log, self.ref_ts, self.say = state, log, ref_ts, say
        self.changes = []

    def note(self, text):
        self.changes.append(text)

    def settled(self, group, days=365, limit=4000):
        out = []
        for fid, e in self.log.entries(self.ref_ts - days * 86400, self.ref_ts):
            if isinstance(e.get("r"), list) and e.get("lh") is not None and not e.get("v1") \
                    and ("intl" if e.get("i") else "club") == group:
                out.append(e)
        out.sort(key=lambda e: -e["ts"])
        return out[:limit]

    def loss(self, rows, param, group, value):
        ms = json.loads(json.dumps(self.ms))
        ms[param][group] = value
        tot = wsum = 0.0
        for e in rows:
            w = 0.5 ** (max(0, self.ref_ts - e["ts"]) / 86400 / 120)
            p = calibrated(e["lh"], e["la"], group, ms)
            gh, ga = e["r"]
            if param in ("rho", "fav"):
                q = p["w"] if gh > ga else p["d"] if gh == ga else p["l"]
            elif param == "z00":
                q = p["p00"] if gh + ga == 0 else 1 - p["p00"]
            else:
                q = p["btts"] if (gh > 0 and ga > 0) else 1 - p["btts"]
            tot -= w * math.log(max(q, 1e-9))
            wsum += w
        return tot / max(wsum, 1e-9)

    def step_probabilities(self):
        for group in ("club", "intl"):
            rows = self.settled(group)
            if len(rows) < MIN_GAMES[group]:
                continue
            for param in ("rho", "fav", "z00", "btts"):
                lo, hi, step = LIMITS[param]
                cur = self.ms[param][group]
                cands = {v: self.loss(rows, param, group, v) for v in (max(lo, cur - step), cur, min(hi, cur + step))}
                best = min(cands, key=cands.get)
                if best != cur and cands[cur] - cands[best] > 2e-5:
                    self.ms[param][group] = round(best, 4)
                    who = "Internationals" if group == "intl" else "Clubs"
                    more = (best < cur) if param == "rho" else (best > cur)
                    what = {"rho": ("draws forecast", "draws ran above forecast", "draws ran below forecast"),
                            "fav": ("favourites' strength", "favourites did better than forecast", "favourites did worse than forecast"),
                            "z00": ("0-0 allowance", "0-0s ran above forecast", "0-0s ran below forecast"),
                            "btts": ("both-score allowance", "both teams scored more than forecast", "both teams scored less than forecast")}[param]
                    self.note(f"{who}: {what[0]} {'raised' if more else 'lowered'} slightly "
                              f"({what[1] if more else what[2]}, {len(rows)} games).")


CHECK_DAYS, CHECK_MIN_GAMES, CHECK_Z = 180, 30, 2.5
CHECK_METRICS = (("p00", lambda p: p["p00"], lambda r: r[0] + r[1] == 0),
                 ("draw", lambda p: p["d"], lambda r: r[0] == r[1]),
                 ("home", lambda p: p["w"], lambda r: r[0] > r[1]),
                 ("btts", lambda p: p["btts"], lambda r: r[0] > 0 and r[1] > 0))


def model_check(plog, ref_ts):
    """Forecast against actual for every settled game (not just picks), overall and per competition, last 180 days.
    A figure is flagged for review when the gap is too big to be chance (more than 2.5 standard errors, 30+ games)."""
    groups = defaultdict(list)
    for fid, e in plog.entries(ref_ts - CHECK_DAYS * 86400, ref_ts):
        p = e.get("p") or {}
        if not isinstance(e.get("r"), list) or e.get("v1") or "d" not in p or "btts" not in p:
            continue
        groups[("1", "All internationals" if e.get("i") else "All club games")].append(e)
        groups[("2", e["cn"])].append(e)
    rows = []
    for (order, name), es in sorted(groups.items()):
        n, m = len(es), {}
        for key, fp, hit in CHECK_METRICS:
            ps = [fp(e["p"]) for e in es]
            f = sum(ps) / n
            a = sum(1 for e in es if hit(e["r"])) / n
            se = math.sqrt(sum(x * (1 - x) for x in ps)) / n
            m[key] = {"f": round(f * 100, 1), "a": round(a * 100, 1),
                      "off": n >= CHECK_MIN_GAMES and se > 0 and abs(a - f) > CHECK_Z * se}
        rows.append({"comp": name, "n": n, "overall": order == "1", "m": m, "review": any(v["off"] for v in m.values())})
    return {"days": CHECK_DAYS, "min_games": CHECK_MIN_GAMES, "rows": rows}


def update_intl_pass(ms, plog, S, check, note):
    """International pass mark: +1 per 50 settled international games (real predictions only), up to the club mark.
    It never goes down, and pauses while the model check flags internationals for review."""
    start, end, per = intl_pass_cfg(S)
    st = ms.setdefault("intl_pass", {"value": start, "games": 0, "paused": False})
    st["value"] = max(start, min(end, st.get("value", start)))
    n = sum(1 for _, e in plog.entries() if e.get("i") and not e.get("rp") and not e.get("v1") and isinstance(e.get("r"), list))
    st["games"] = n
    target = min(end, start + n // per)
    flagged = any(r["review"] for r in check["rows"] if r["overall"] and r["comp"] == "All internationals")
    if target > st["value"] and not flagged:
        note(f"International pass mark raised {st['value']} → {target} ({n} international games settled).")
        st["value"] = target
    elif target > st["value"] and flagged and not st.get("paused"):
        note("International pass mark rise paused: the model check flags internationals for review.")
    st["paused"] = bool(flagged and target > st["value"])
    st["next_at"] = None if st["value"] >= end else (st["value"] - start + 1) * per
    return st


# ----------------------------------------------------------------------------------------------
# The daily build
# ----------------------------------------------------------------------------------------------
class Build:
    def __init__(self, api, settings, comp_doc, store, ref_utc, model_state, log=print):
        self.api, self.S, self.store, self.log = api, settings, store, log
        self.ms = model_state
        self.comps = comp_doc["competitions"]
        self.comp_by_no = {c["no"]: c for c in self.comps}
        self.comp_ids = {c["no"]: [c["openfoot_id"]] for c in self.comps if c.get("openfoot_id")}
        self.of_to_no = {i: no for no, ids in self.comp_ids.items() for i in ids}
        self.discovered = {}        # no -> [ids] found later in OpenFootAPI's catalogue
        self.catchup_days = 0       # weekly catch-up: look this many days back for results added late
        self.tsdb = None            # SportsDB client (upcoming games where OpenFootAPI only has results)
        self.tsdb_aliases = {}
        self.fixture_fixes = {}     # config/fixture_fixes.json: wrong dates in TheSportsDB, corrected by hand
        self.tsdb_used, self.tsdb_skipped, self.tsdb_leagues = Counter(), [], {}
        self.other = comp_doc["other_league_strength"]
        self.confed = comp_doc["confederation_strength"]
        self.nat_table_src = comp_doc.get("national_team_strength")
        self.tz = ZoneInfo(settings["timezone"])
        self.ref = ref_utc
        self.ref_ts = int(ref_utc.timestamp())
        # scored window: from now to the end of tomorrow (Irish time); picks are chosen per day
        last_day = ref_utc.astimezone(self.tz).date() + timedelta(days=1 + int(settings.get("days_ahead", 1)) - 1)
        self.end_ts = int(datetime.combine(last_day + timedelta(days=1), datetime.min.time(), self.tz).timestamp())
        self.cov = {}
        self.notes = []

    # ---------------- competitions catalogue (refreshed every 3 days) ----------------
    def load_catalogue(self):
        if self.store.comps and self.ref_ts - self.store.comps.get("_fetched", {}).get("at", 0) < 3 * 86400:
            self.discover()
            return
        rows = self.api.get_all("competitions")
        comps = {}
        for c in rows:
            cid = c.get("id")
            if not cid:
                continue
            country = ""
            for k, v in c.items():
                if re.search(r"country|area|region", k, re.I):
                    country = v.get("name", "") if isinstance(v, dict) else str(v or "")
                    break
            comps[cid] = {"name": c.get("name") or cid, "country": country}
        comps["_fetched"] = {"at": self.ref_ts}
        self.store.comps = comps
        self.discover()

    def discover(self):
        """Look for any of the missing competitions in OpenFootAPI's catalogue (it may add them later)."""
        for c in self.comps:
            w = c.get("watch")
            if not w or c.get("openfoot_id"):
                continue
            pats = [re.compile(x) for x in w.get("name_patterns", [])]
            found = []
            for cid, meta in self.store.comps.items():
                if cid == "_fetched" or cid in self.of_to_no:
                    continue
                name = norm(meta.get("name", ""))
                where = norm(meta.get("country", "")) + " " + cid.lower()
                women_ok = "women" in norm(c["name"]) or "women" not in name
                if any(p.search(name) for p in pats) and women_ok and \
                        (not w.get("where") or any(x in where for x in w["where"])) and "northern" not in where:
                    if "qualif" not in norm(c["name"]) and "qualif" in name:
                        continue
                    found.append(cid)
            if found:
                self.comp_ids[c["no"]] = found
                self.discovered[c["no"]] = found
                for i in found:
                    self.of_to_no[i] = c["no"]

    # ---------------- results: sweep recent dates, backfill whole seasons once ----------------
    def sweep(self, dates):
        for d in dates:
            for m in self.api.get_all("matches", date=d):
                self.store.add(m)

    def guess_season(self, cid):
        if cid in self.store.seasons:
            return self.store.seasons[cid]
        country = norm((self.store.comps.get(cid) or {}).get("country", ""))
        if not country:
            for t in self.store.teams.values():
                if t[1] == cid and t[2]:
                    country = norm(t[2])
                    break
        y = self.ref.year
        if country in CALENDAR_COUNTRIES:
            return season_label(y, True)
        return season_label(y if self.ref.month >= 7 else y - 1, False)

    def backfill(self, cid, season):
        key = f"{cid}|{season}"
        if key in self.store.backfilled:
            return
        got = self.api.get_all("matches", competition=cid, season=season, status="finished")
        for m in got:
            self.store.add(m)
        self.store.backfilled[key] = date.today().isoformat()
        if not got:
            self.notes.append(f"No finished games returned for {self.store.comp_name(cid)} {season}")

    def add_tsdb_fixtures(self):
        """Competitions where OpenFootAPI only sends results: take the next 24 hours' games from TheSportsDB and
        match both teams to OpenFootAPI's (strictly; a game is skipped rather than guessed)."""
        old = self.ref_ts - 20 * 86400
        for k in [k for k, v in self.store.matches.items() if k.startswith("tsdb_") and v[2] < old]:
            del self.store.matches[k]
        if not self.tsdb:
            return
        days = sorted({datetime.fromtimestamp(t, timezone.utc).date().isoformat() for t in (self.ref_ts, self.end_ts - 1)})
        for c in sorted(self.comps, key=lambda c: (-c["value"], c["no"])):
            lid, ids = c.get("tsdb_id"), self.comp_ids.get(c["no"])
            if not lid or not ids:
                continue
            cid = ids[0]
            events = [e for d in days for e in self.tsdb.day(lid, d)]
            events = [e for e in events if (t := tsdb_time(e)) and self.ref_ts <= t < self.end_ts]
            if not events:
                continue
            self.tsdb_leagues[c["no"]] = sorted({e.get("strLeague") or "?" for e in events})
            self.backfill(cid, self.guess_season(cid))          # this league's results: team names and ratings
            since = self.ref_ts - 400 * 86400
            pool = {t: self.store.teams.get(t, [t])[0] for v in self.store.matches.values()
                    if v[0] == cid and v[2] >= since and not str(v[3]).startswith("tsdb") for t in (v[3], v[4])}
            pool.update({t: v[0] for t, v in self.store.teams.items() if v[1] == cid})
            aliases = {**self.tsdb_aliases.get("all", {}), **self.tsdb_aliases.get(str(c["no"]), {})}
            listed = {(v[3], v[4]) for k, v in self.store.matches.items()
                      if v[0] == cid and not k.startswith("tsdb_") and self.ref_ts - 86400 <= v[2] < self.end_ts + 86400}
            names = {n for e in events for n in (e.get("strHomeTeam") or "", e.get("strAwayTeam") or "")}
            found = {n: match_team(n, pool, aliases) for n in names}
            taken = Counter(t for t in found.values() if t)
            found = {n: (t if t and taken[t] == 1 else None) for n, t in found.items()}   # two names, one team: unsure
            for e in events:
                h, a = e.get("strHomeTeam") or "", e.get("strAwayTeam") or ""
                if norm(e.get("strStatus")) in ("postponed", "cancelled", "abandoned", "pst", "canc"):
                    continue
                hid, aid = found.get(h), found.get(a)
                if not hid or not aid or hid == aid:
                    miss = " and ".join(f"'{n}'" for n, t in ((h, hid), (a, aid)) if not t) or "teams"
                    self.tsdb_skipped.append(f"{c['name']}: {h} v {a} skipped (couldn't match {miss})")
                    continue
                if (hid, aid) in listed:
                    continue                               # OpenFootAPI lists it itself now
                rnd = f"Round {e['intRound']}" if str(e.get("intRound") or "").isdigit() else ""
                mid, ts = f"tsdb_{e.get('idEvent')}", tsdb_time(e)
                fix = self.fixture_fixes.get(mid) or {}
                if fix.get("skip"):
                    continue
                if fix.get("kickoff"):
                    ts = int(datetime.fromisoformat(fix["kickoff"]).timestamp())
                    if not (self.ref_ts <= ts < self.end_ts):
                        self.store.matches.pop(mid, None)
                        continue
                self.store.matches[mid] = [cid, self.guess_season(cid), ts, hid, aid, None, None, "scheduled", rnd, True]
                self.tsdb_used[c["no"]] += 1

    def team_games(self, tid, since_ts):
        return sum(1 for v in self.store.matches.values()
                   if v[7] == "finished" and v[5] is not None and since_ts <= v[2] < self.ref_ts and tid in (v[3], v[4]))

    def home_league(self, tid):
        t = self.store.teams.get(tid)
        if t and t[1] and not self.store.is_cup(t[1]):
            return t[1]
        cnt = Counter(v[0] for v in self.store.matches.values()
                      if tid in (v[3], v[4]) and not self.store.is_cup(v[0]))
        return cnt.most_common(1)[0][0] if cnt else None

    CONTINENTAL = ("eur", "asia", "sout", "conc", "afri", "ocea", "nort", "cent")

    def link_continental(self):
        """OpenFootAPI gives clubs a separate id in European/continental competitions (team_barcelona_eur vs
        team_barcelona_es). Link each to the same club's league id, so its league results count everywhere."""
        teams = self.store.teams
        by_base = defaultdict(list)
        for tid in teams:
            if "_" in tid and tid.rsplit("_", 1)[1] not in self.CONTINENTAL:
                by_base[tid.rsplit("_", 1)[0]].append(tid)
        alias = {}
        for tid, rec in teams.items():
            if "_" not in tid or tid.rsplit("_", 1)[1] not in self.CONTINENTAL:
                continue
            if rec[1] and self.pool_of(rec[1]).endswith("nat"):
                continue                                  # national teams stay as they are
            cands = by_base.get(tid.rsplit("_", 1)[0], [])
            if len(cands) > 1 and rec[0]:
                cands = [c for c in cands if norm(teams[c][0]) == norm(rec[0])] or cands
            if len(cands) == 1:
                alias[tid] = cands[0]
        self.store.team_alias = alias
        n = 0
        for v in self.store.matches.values():
            for i in (3, 4):
                if v[i] in alias:
                    v[i] = alias[v[i]]
                    n += 1
        return len(alias), n

    def pool_of(self, cid):
        no = self.of_to_no.get(cid)
        return self.comp_by_no[no]["pool"] if no else "men_club"

    def nat_history_comps(self):
        """Extra international competitions to collect when national teams play: World Cup and earlier Nations Leagues."""
        wanted = []
        wc = (self.comp_ids.get(41) or [None])[0]
        if wc:
            wanted += [(wc, "2026"), (wc, "2022")]
        nl = (self.comp_ids.get(45) or [None])[0]
        if nl:
            cur = self.store.seasons.get(nl) or season_label(self.ref.year if self.ref.month >= 7 else self.ref.year - 1, False)
            p1 = season_prev(cur)
            p2 = season_prev(p1) if p1 else None
            wanted += [(nl, cur)] + [(nl, s) for s in (p1, p2) if s]
        return wanted

    # ---------------- run ----------------
    def run(self):
        S, M, R = self.S, self.S["model"], self.S["requests"]
        stats = {"dropped_postponed": 0, "dropped_started": 0, "other_competitions": 0}
        linked, moved = self.link_continental()
        if moved:
            print(f"  linked {linked} clubs' European ids to their league ids ({moved} results)")

        # 1) recent dates (results + the window's fixtures)
        today = self.ref.astimezone(timezone.utc).date()
        end_day = datetime.fromtimestamp(self.end_ts, timezone.utc).date()
        first = today - timedelta(days=max(R["sweep_days_back"], self.catchup_days))
        if self.store.last_sweep:
            last = date.fromisoformat(self.store.last_sweep)
            if (today - last).days > 10:
                self.store.backfilled = {}          # too long a gap: rebuild seasons
            else:
                first = min(first, last - timedelta(days=1))
        dates, d = [], first
        while d <= end_day:
            dates.append(d.isoformat())
            d += timedelta(days=1)
        self.sweep(dates)
        self.store.last_sweep = today.isoformat()
        self.add_tsdb_fixtures()

        # 2) the window
        cands = defaultdict(list)
        for mid, v in self.store.matches.items():
            comp, season, ts, h, a, gh, ga, status, rnd, known = (v + [True])[:10]
            if not (self.ref_ts <= ts < self.end_ts):
                continue
            no = self.of_to_no.get(comp)
            if no is None:
                stats["other_competitions"] += 1
                continue
            if no in (27, 28, 29) and is_qualifying_round(rnd):
                no = 30
            if self.comp_by_no[no].get("picks") is False:   # switched off: results still kept, games not scored
                continue
            if status in ("postponed", "cancelled"):
                stats["dropped_postponed"] += 1
                continue
            if status not in ("scheduled", "unknown", ""):
                stats["dropped_started"] += 1
                continue
            cands[no].append({"id": mid, "comp": comp, "season": season, "ts": ts, "home": h, "away": a,
                              "round": rnd, "time_known": known})

        # 3) make sure each competition's season (and each cup side's home league) is in the store
        order = sorted(self.comps, key=lambda c: (-c["value"], c["prestige"], c["no"]))
        budget_out = False
        season_start = self.ref_ts - 330 * 86400
        for c in order:
            no = c["no"]
            cov = {"status": "no_games", "games": len(cands.get(no, [])), "note": ""}
            if self.tsdb_used.get(no):
                cov["note"] = "Games from TheSportsDB, results from OpenFootAPI"
            self.cov[no] = cov
            if not self.comp_ids.get(no) and not c.get("virtual_of"):
                cov["status"] = "not_available"
                cov["note"] = "Not on OpenFootAPI's free plan"
                continue
            if not cands.get(no):
                continue
            if budget_out:
                cov["status"] = "omitted_budget"
                continue
            try:
                for comp, season in sorted({(m["comp"], m["season"]) for m in cands[no]}):
                    self.backfill(comp, season or self.guess_season(comp))
                teams = {t for m in cands[no] for t in (m["home"], m["away"])}
                if c["pool"].endswith("nat"):
                    for comp, season in self.nat_history_comps():
                        self.backfill(comp, season)
                elif c["kind"] != "league":
                    for t in sorted(teams):
                        hl = self.home_league(t)
                        if hl and hl not in self.comp_ids.get(no, []):
                            self.backfill(hl, self.guess_season(hl))
                if not c["pool"].endswith("nat"):
                    thin = [t for t in teams if self.team_games(t, season_start) < M["previous_season_if_games_below"]]
                    if thin:
                        needed = {self.home_league(t) or m["comp"] for m in cands[no] for t in (m["home"], m["away"]) if t in thin}
                        for comp in sorted(x for x in needed if x):
                            prev = season_prev(self.guess_season(comp))
                            if prev:
                                self.backfill(comp, prev)
                cov["status"] = "covered"
            except BudgetExhausted:
                budget_out = True
                cov["status"] = "partial"
                cov["note"] = "Request limit reached part-way; scored with the results already saved"
            except PlanBlocked as e:
                cov["status"] = "blocked_plan"
                cov["note"] = str(e)[:200]
            except ApiError as e:
                cov["status"] = "error"
                cov["note"] = str(e)[:200]

        items = defaultdict(list)
        for no, ms in cands.items():
            if self.cov.get(no, {}).get("status") in ("omitted_budget", "blocked_plan", "error", "not_available"):
                continue
            for m in ms:
                items[self.comp_by_no[no]["pool"]].append((no, m))
        preds = []
        for pool, its in items.items():
            fit = self.fit_ratings(pool, self.ref_ts, {t for _, m in its for t in (m["home"], m["away"])})
            self.log(f"  {pool}: {len(fit['matches'])} results, {len(fit['pri'])} teams")
            preds += self.predict(its, fit)
        for no, cov in self.cov.items():
            if cov["status"] in ("covered", "partial"):
                cov["games"] = sum(1 for p in preds if p["comp_no"] == no)
        return preds, stats

    # ---------------- ratings ----------------
    def league_strength(self, cid):
        no = self.of_to_no.get(cid)
        adj = self.ms.get("league_adj", {}).get(cid, 0.0)
        if no and "strength" in self.comp_by_no[no]:
            return self.comp_by_no[no]["strength"] + adj
        meta = self.store.comps.get(cid) or {}
        country = meta.get("country") or ""
        if not country:
            for t in self.store.teams.values():
                if t[1] == cid and t[2]:
                    country = t[2]
                    break
        table = {norm(k): v for k, v in self.other["countries"].items()}
        base = table.get(norm(country), self.other["default"])
        n = norm(meta.get("name", "")) + " " + norm(cid.replace("_", " "))
        tier = 1
        if re.search(r"\b(3 liga|third|tercera|serie c|national 1)\b", n):
            tier = 3
        elif re.search(r"\b(2|ii|b|second|segunda|eerste|ligue 2|serie b|liga 2|j2|primera nacional|usl|championship)\b", n):
            tier = 2
        return max(10, base - self.other["lower_division_penalty"] * (tier - 1)) + adj

    def priors_for(self, pool, teams):
        M = self.S["model"]
        pri = {}
        for t in teams:
            if pool.endswith("club"):
                hl = self.home_league(t)
                s = self.league_strength(hl) if hl else self.other["default"]
                o = M["league_strength_scale"] * (s - 50) / 50
            else:
                s = self.nation_strength(t)
                if s is None:
                    s = self.confed.get(self.nat_confed(t), self.confed["unknown"])
                o = M.get("national_strength_scale", M["league_strength_scale"]) * (s - 50) / 50
            pri[t] = (o, o)
        return pri

    def nation_strength(self, t):
        if not hasattr(self, "_nat_table"):
            nt = self.nat_table_src or {}
            self._nat_table = {norm(k): v for k, v in (nt.get("teams") or {}).items()}
            for alias, real in (nt.get("aliases") or {}).items():
                if norm(real) in self._nat_table:
                    self._nat_table[norm(alias)] = self._nat_table[norm(real)]
        name = norm(re.sub(r"\b(women|w|u21|u23)\b", "", str((self.store.teams.get(t) or [t])[0])))
        return self._nat_table.get(name)

    def nat_confed(self, t):
        names = " ".join(norm(self.store.comp_name(v[0])) for v in self.store.matches.values() if t in (v[3], v[4]))
        for confed, keys in (("UEFA", ("uefa", "euro", "nations league")), ("CONMEBOL", ("copa america", "conmebol", "south america")),
                             ("CONCACAF", ("concacaf", "gold cup")), ("CAF", ("africa", "caf ")), ("AFC", ("asia", "afc")),
                             ("OFC", ("oceania", "ofc"))):
            if any(k in names for k in keys):
                return confed
        return "unknown"

    def pool_matches(self, pool, ref_ts):
        M = self.S["model"]
        nat = pool.endswith("nat")
        since = ref_ts - (M["international_window_days"] if nat else 450) * 86400
        cur_start = ref_ts - 330 * 86400
        out = []
        for v in self.store.matches.values():
            if v[7] != "finished" or v[5] is None or v[6] is None or not (since <= v[2] < ref_ts):
                continue
            if self.pool_of(v[0]) != pool:
                continue
            w = 1.0 if (nat or v[2] >= cur_start) else M["previous_season_weight"]
            out.append({"home": v[3], "away": v[4], "gh": v[5], "ga": v[6], "ts": v[2], "w": w})
        return out

    def fit_ratings(self, pool, ref_ts, extra_teams=(), half_life=None, matches=None):
        M = self.S["model"]
        nat = pool.endswith("nat")
        if matches is None:
            matches = self.pool_matches(pool, ref_ts)
        teams = {t for m in matches for t in (m["home"], m["away"])} | set(extra_teams)
        pri = self.priors_for(pool, teams)
        hl = half_life or (M["international_half_life_days"] if nat else self.ms["half_life"])
        long = fit_pool(matches, pri, M["prior_spread"], hl, ref_ts)
        long_pri = {t: (long["att"][t], long["def"][t]) for t in long["att"]}
        short = fit_pool(matches, long_pri, M["form_spread"], M["form_half_life_days"], ref_ts, iters=25)
        games = Counter()
        since = ref_ts - (M["international_window_days"] if nat else 330) * 86400
        for m in matches:
            if m["ts"] >= since:
                games[m["home"]] += 1
                games[m["away"]] += 1
        return {"long": long, "short": short, "pri": pri, "games": games, "matches": matches, "nat": nat}

    def lambdas(self, fit, home, away, neutral, wf=None):
        wf = self.ms["form_weight"] if wf is None else wf
        L, Sh, pri = fit["long"], fit["short"], fit["pri"]
        p0 = (0.0, 0.0)

        def team(t):
            a = (1 - wf) * L["att"].get(t, pri.get(t, p0)[0]) + wf * Sh["att"].get(t, pri.get(t, p0)[0])
            d = (1 - wf) * L["def"].get(t, pri.get(t, p0)[1]) + wf * Sh["def"].get(t, pri.get(t, p0)[1])
            return a, d
        mu = (1 - wf) * L["mu"] + wf * Sh["mu"]
        hadv = 0 if neutral else (1 - wf) * L["home"] + wf * Sh["home"]
        ah, dh = team(home)
        aa, da = team(away)
        return math.exp(mu + hadv + ah - da), math.exp(mu + aa - dh), (ah, dh), (aa, da)

    # ---------------- predictions ----------------
    def predict(self, items, fit):
        S, M = self.S, self.S["model"]
        out = []
        group = "intl" if fit["nat"] else "club"
        lim_n = M["limited_data_games_international"] if fit["nat"] else M["limited_data_games"]
        tn = lambda t: (self.store.teams.get(t) or [t])[0] or t
        for no, m in items:
            c = self.comp_by_no[no]
            lh, la, (ah, dh), (aa, da) = self.lambdas(fit, m["home"], m["away"], no in NEUTRAL_COMPS)
            p = calibrated(lh, la, group, self.ms)
            sec = section_scores(p, S)
            limited = min(fit["games"][m["home"]], fit["games"][m["away"]]) < lim_n
            for s in sec.values():
                if limited:
                    s["score"] *= M["limited_data_score_factor"]
                s["score"] = round(max(1.0, min(100.0, s["score"])), 2)
                s["p"] = round(s["p"], 4)
            tags = (["limited_data"] if limited else []) + ([] if m.get("time_known", True) else ["time_tbc"])
            if not sec["goals"]["listed"]:
                tags.append("too_short")
            out.append({
                "fid": m["id"], "ts": m["ts"], "comp_no": no, "comp": c["name"], "intl": fit["nat"],
                "round": m.get("round", ""), "league_name": self.store.comp_name(m["comp"]),
                "home": {"name": tn(m["home"]), "games": fit["games"][m["home"]],
                         "att": round(rating(ah, 0.6)), "def": round(rating(dh, 0.6)), "ovr": round(rating(ah + dh, 0.9))},
                "away": {"name": tn(m["away"]), "games": fit["games"][m["away"]],
                         "att": round(rating(aa, 0.6)), "def": round(rating(da, 0.6)), "ovr": round(rating(aa + da, 0.9))},
                "xg_home": round(lh, 2), "xg_away": round(la, 2), "raw": [round(lh, 4), round(la, 4)],
                "p00": round(p["p00"], 4), "pw_home": round(p["w"], 4), "pd": round(p["d"], 4), "pw_away": round(p["l"], 4),
                "p_home_score": round(p["hs"], 4), "p_away_score": round(p["as"], 4), "p_btts": round(p["btts"], 4),
                "tags": tags, "sec": sec,
            })
        return out

    # ---------------- replay past dates (gives the self-adjustment data to learn from straight away) ----------------
    def replay_week(self, start_ts, plog):
        end_ts = start_ts + 7 * 86400
        items = defaultdict(list)
        for mid, v in self.store.matches.items():
            if not (start_ts <= v[2] < end_ts) or v[7] != "finished" or v[5] is None:
                continue
            no = self.of_to_no.get(v[0])
            if no is None:
                continue
            items[self.comp_by_no[no]["pool"]].append((no, {"id": mid, "comp": v[0], "ts": v[2], "home": v[3], "away": v[4],
                                                             "round": v[8]}))
        n = 0
        for pool, its in items.items():
            fit = self.fit_ratings(pool, start_ts)
            if len(fit["matches"]) < 40:
                continue
            for p in self.predict(its, fit):
                v = self.store.matches[p["fid"]]
                plog.put(p["fid"], {**log_entry(p, [v[5], v[6]]), "rp": 1}, replay=True)
                n += 1
        return n

    # ---------------- daily tuning of form weight and fade speed ----------------
    def tune_daily(self, cal):
        """Score alternative form weights and fade speeds on the last 3 days' results; switch when one is clearly better."""
        t0 = self.ref_ts - 3 * 86400
        games = [v for v in self.store.matches.values()
                 if t0 <= v[2] < self.ref_ts and v[7] == "finished" and v[5] is not None and self.of_to_no.get(v[0])
                 and self.pool_of(v[0]) == "men_club"]
        if len(games) < 15:
            return
        matches = self.pool_matches("men_club", t0)
        hl, wf = self.ms["half_life"], self.ms["form_weight"]
        hls = sorted({max(90, round(hl / 1.25)), hl, min(540, round(hl * 1.25))})
        wfs = sorted({round(max(0.0, wf - 0.05), 2), round(wf, 2), round(min(0.4, wf + 0.05), 2)})

        def ll(fit, w):
            tot = 0.0
            for v in games:
                lh, la, _, _ = self.lambdas(fit, v[3], v[4], self.of_to_no.get(v[0]) in NEUTRAL_COMPS, wf=w)
                tot += math.log(max(poisson_pmf(v[5], lh) * poisson_pmf(v[6], la), 1e-12))
            return tot
        tun = self.ms.setdefault("tuning", {})
        for kind, cands in (("half_life", hls), ("form_weight", wfs)):
            acc = tun.setdefault(kind, {"days": 0, "n": 0, "ll": {}})
            if kind == "half_life":
                scores = {str(h): ll(self.fit_ratings("men_club", t0, half_life=h, matches=matches), wf) for h in cands}
            else:
                fit = self.fit_ratings("men_club", t0, matches=matches)
                scores = {str(w): ll(fit, w) for w in cands}
            for k in list(acc["ll"]):
                if k not in scores:
                    del acc["ll"][k]
            for k, v in scores.items():
                acc["ll"][k] = acc["ll"].get(k, 0.0) * 0.97 + v
            acc["days"] += 1
            acc["n"] += len(games)
            cur = str(hl if kind == "half_life" else round(wf, 2))
            if acc["days"] >= 21 and acc["n"] >= 600 and cur in acc["ll"]:
                best = max(acc["ll"], key=acc["ll"].get)
                if best != cur and (acc["ll"][best] - acc["ll"][cur]) / max(acc["n"], 1) > 0.0005:
                    if kind == "half_life":
                        self.ms["half_life"] = int(float(best))
                        cal.note(f"Older games now fade {'more slowly' if int(float(best)) > hl else 'faster'}: "
                                 f"strength half-life {hl} → {int(float(best))} days (better fit over {acc['n']} games).")
                    else:
                        self.ms["form_weight"] = float(best)
                        cal.note(f"Recent form now counts {'more' if float(best) > wf else 'less'}: "
                                 f"{round(wf * 100)}% → {round(float(best) * 100)}% (better fit over {acc['n']} games).")
                    tun[kind] = {"days": 0, "n": 0, "ll": {}}

    def adjust_league_strengths(self, cal):
        """Move each listed league's starting strength a little towards what cross-league results say."""
        M = self.S["model"]
        matches = self.pool_matches("men_club", self.ref_ts)
        if len(matches) < 200:
            return
        fit = self.fit_ratings("men_club", self.ref_ts, matches=matches)
        league_of = {}
        for m in matches:
            for t in (m["home"], m["away"]):
                if t not in league_of:
                    league_of[t] = self.home_league(t)
        cross = Counter()
        for m in matches:
            a, b = league_of.get(m["home"]), league_of.get(m["away"])
            if a and b and a != b:
                cross[a] += 1
                cross[b] += 1
        moved = []
        adj = self.ms.setdefault("league_adj", {})
        for c in self.comps:
            cid = c.get("openfoot_id")
            if not cid or c["kind"] != "league" or "strength" not in c or cross[cid] < 10:
                continue
            ts = [t for t, l in league_of.items() if l == cid]
            if len(ts) < 6:
                continue
            avg = sum(fit["long"]["att"].get(t, 0) + fit["long"]["def"].get(t, 0) for t in ts) / (2 * len(ts))
            implied = 50 + 50 * avg / M["league_strength_scale"]
            target = max(-15, min(15, implied - c["strength"]))
            old = adj.get(cid, 0.0)
            new = round(old + 0.1 * (target - old), 2)
            adj[cid] = new
            if int(abs(new)) != int(abs(old)) or (new > 0) != (old > 0) and abs(new) >= 1:
                moved.append(f"{c['name']} {'+' if new >= 0 else ''}{new:.1f}")
        if moved:
            cal.note("League strengths nudged by cross-league results: " + ", ".join(moved[:5]) + ".")


RANK_ORDER = ("goals", "ballon", "misses", "btts")    # Ballon d'Or first: its picks can't also be Misses


def eligible(g, key):
    s = g["sec"]
    return bool(s[key].get("listed")) and not (key == "misses" and s["ballon"].get("pick"))


def rank_by_day(games, S, tz):
    """Picks per Irish calendar day: every game over its section's pass mark. Games carried over from the last list (already kicked off) keep their
    pick and use up their place; the rest compete for the remaining places."""
    days = defaultdict(list)
    for g in games:
        g["day"] = datetime.fromtimestamp(g["ts"], tz).date().isoformat()
        days[g["day"]].append(g)
    for group in days.values():
        for key in RANK_ORDER:
            # ties (several games at 100) are broken by the actual chance, then kickoff
            listed = sorted([g for g in group if eligible(g, key)],
                            key=lambda g: (-g["sec"][key]["score"], -(g["sec"][key].get("p") or 0), g["ts"]))
            for r, g in enumerate(listed):
                sec = g["sec"][key]
                sec["rank"] = r + 1
                if g.get("_carry"):
                    continue
                mn = pass_marks(S, key)[1 if g["intl"] else 0]
                sec["pick"] = sec["score"] >= mn          # every game over the pass mark is a pick
            for g in group:
                if not eligible(g, key):
                    g["sec"][key].update(rank=None, pick=False)


def log_entry(p, result=None):
    return {"ts": p["ts"], "c": p["comp_no"], "cn": p["comp"], "i": p["intl"], "h": p["home"]["name"], "a": p["away"]["name"],
            "lh": p["raw"][0], "la": p["raw"][1], "lim": "limited_data" in p["tags"],
            "p": {"p00": p["p00"], "w": p["pw_home"], "d": p["pd"], "l": p["pw_away"], "btts": p["p_btts"]},
            "s": {k: [v["score"], v.get("rank"), bool(v.get("pick")), v.get("team")] for k, v in p["sec"].items()},
            "r": result}




# ----------------------------------------------------------------------------------------------
# Outputs for the app: Record (picks by section), All results (archive + Goalscraper's view), model check
# ----------------------------------------------------------------------------------------------
BANDS = ((80, 101, "80–100"), (65, 80, "65–79"), (50, 65, "50–64"), (0, 50, "Below 50 (internationals)"))


def tally():
    return {"won": 0, "lost": 0, "void": 0}


def record_summary(plog, ref_ts, tz):
    """Every real pick (not replays), settled or waiting, plus per-section summaries. First-version picks are listed
    but not counted."""
    secs = {k: {"d30": tally(), "all": tally(), "pending": 0, "v1": 0, "bands": {}, "comps": {}} for k in SECTIONS}
    days = defaultdict(list)
    for fid, e in plog.entries():
        if e.get("rp"):
            continue
        for k, v in e["s"].items():
            score, rank, pick, team = (list(v) + [None, None, None, None])[:4]
            if not pick or k not in secs:
                continue
            r = e.get("r")
            res = "pending" if r is None else "void" if r == "void" else ("won" if pick_won(k, team, r[0], r[1]) else "lost")
            day = datetime.fromtimestamp(e["ts"], tz).date().isoformat()
            row = {"t": e["ts"], "h": e["h"], "a": e["a"], "c": e["cn"], "k": k, "tm": team, "s": round(score, 1),
                   "rk": rank, "r": r if isinstance(r, list) else None, "res": res}
            if e.get("v1"):
                row["v1"] = 1
            days[day].append(row)
            S = secs[k]
            if e.get("v1"):
                S["v1"] += 1
                continue
            if res == "pending":
                S["pending"] += 1
                continue
            S["all"][res] += 1
            if e["ts"] >= ref_ts - 30 * 86400:
                S["d30"][res] += 1
            if res == "void":
                continue
            band = next(lab for lo, hi, lab in BANDS if lo <= score < hi)
            S["bands"].setdefault(band, tally())[res] += 1
            S["comps"].setdefault(e["cn"], tally())[res] += 1
    for S in secs.values():
        S["bands"] = [{"label": lab, **S["bands"][lab]} for _, _, lab in BANDS if lab in S["bands"]]
        S["comps"] = sorted(({"comp": c, **t} for c, t in S["comps"].items()),
                            key=lambda x: (-(x["won"] + x["lost"]), x["comp"]))
    order = {k: i for i, k in enumerate(SECTIONS)}
    return {"sections": secs,
            "days": [{"date": d, "picks": sorted(v, key=lambda x: (order[x["k"]], x["rk"] or 99, x["t"]))}
                     for d, v in sorted(days.items(), reverse=True)]}


def build_results(archive, plog, build, store, tz, check, gen):
    """All results for the app: one file per month (every result in the archive) with Goalscraper's section scores
    for the games it rated. Written to the published site only; the archive itself is the permanent copy."""
    logged = {}
    for fid, e in plog.entries():
        logged[e.get("m") or fid] = e          # TheSportsDB-listed games are archived under OpenFootAPI's id
    files, days = {}, set()
    for m in archive.months_on_disk() + sorted(set(archive.months) - set(archive.months_on_disk())):
        if m in files:
            continue
        games = []
        for mid, r in archive.load(m).items():
            comp, season, ts, hn, an, gh, ga, st = r[:8]
            e = logged.get(mid)
            no = build.of_to_no.get(comp)
            if e:
                name = e["cn"]
            elif no:
                name = build.comp_by_no[no]["name"]
            else:
                meta = store.comps.get(comp) or {}
                name = meta.get("name") or comp
                if meta.get("country") and norm(meta["country"]) not in norm(name):
                    name = f"{name} ({meta['country']})"
            g = {"id": mid, "t": ts, "c": name, "m": 1 if (no or e) else 0, "h": hn, "a": an,
                 "r": [gh, ga] if st == "finished" and gh is not None and ga is not None else None}
            if e:
                g["s"] = {k: [round(v[0], 1), v[1], 1 if v[2] else 0, v[3]] for k, v in e["s"].items()}
                if e.get("v1"):
                    g["v1"] = 1
            games.append(g)
            days.add(datetime.fromtimestamp(ts, tz).date().isoformat())
        games.sort(key=lambda g: -g["t"])
        files[m] = games
    index = {"generated_utc": gen, "months": sorted(files, reverse=True), "days": sorted(days, reverse=True)[:60],
             "check": check}
    return index, files


def import_first_version(plog, comp_doc, path):
    """One-off: the first version kept its Easy Goals picks in data/history.json. Add them to the log, marked as
    first-version picks (shown on Record, not counted), then remove the old file."""
    if not path.exists():
        return 0
    d = load_json(path, None)
    if not isinstance(d, dict) or not isinstance(d.get("games"), dict):
        return 0
    by_name = {c["name"]: c for c in comp_doc["competitions"]}
    n = 0
    for fid, g in d["games"].items():
        if not g.get("top10") or not g.get("ts"):
            continue
        month = plog.load(plog.month_of(g["ts"]))
        if fid in month and not month[fid].get("rp") and not month[fid].get("v1"):
            continue                                   # a real prediction already exists
        c = by_name.get(g.get("comp"))
        res = g.get("result")
        month[fid] = {"ts": g["ts"], "c": c["no"] if c else None, "cn": g.get("comp") or "", "h": g.get("home"),
                      "a": g.get("away"), "i": bool(c and c["pool"].endswith("nat")), "lh": None, "la": None,
                      "lim": False, "p": {"p00": g.get("p00")}, "s": {"goals": [g.get("score") or 0, g.get("rank"), True, None]},
                      "r": res if isinstance(res, list) else None, "v1": 1}
        plog.dirty.add(plog.month_of(g["ts"]))
        n += 1
    plog.save()
    path.unlink()
    return n


def write_outputs(build, store, plog, archive, tz, gen, first_archive):
    """Archive the latest results, then rebuild Record and All results. Returns the files for the site."""
    added = archive.update_from(store)
    archive.save()
    if added:
        print(f"  archive: {added} new results")
    check = model_check(plog, build.ref_ts)
    record = record_summary(plog, build.ref_ts, tz)
    record["generated_utc"] = gen
    save_json(DATA / "record.json", record)
    index, months = build_results(archive, plog, build, store, tz, check, gen)
    files = {"results/index.json": index}
    files.update({f"results/{m}.json": g for m, g in months.items()})
    return check, files


def build_site(extra=None):
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(WEB, SITE)
    (SITE / "data").mkdir(exist_ok=True)
    for name in ("today.json", "coverage.json", "record.json"):
        if (DATA / name).exists():
            shutil.copy(DATA / name, SITE / "data" / name)
    for name, obj in (extra or {}).items():
        save_json(SITE / "data" / name, obj)


def gh_output(**kv):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as fh:
            for k, v in kv.items():
                fh.write(f"{k}={v}\n")


def run_evening(api, build, store, plog, archive, tz, state, now_local, first_archive, scheduled=True):
    """Evening update: fetch today's (and tomorrow's) games again, settle finished picks, mark postponed games.
    The morning's list, scores and rankings are left exactly as they were."""
    err = None
    try:
        if store.comps:
            build.discover()
        d0 = build.ref.astimezone(timezone.utc).date()
        build.sweep([d0.isoformat(), (d0 + timedelta(days=1)).isoformat()])
    except BudgetExhausted:
        err = "Request limit reached, so the evening update was skipped."
    except (PlanBlocked, ApiError) as e:
        err = f"OpenFootAPI: {e}"[:200]
    before = sum(1 for _, e in plog.entries() if e.get("r") is not None)
    plog.settle(store, build.ref_ts)
    settled = sum(1 for _, e in plog.entries() if e.get("r") is not None) - before
    gen = datetime.now(timezone.utc).isoformat()
    today = load_json(DATA / "today.json", None)
    postponed = finished = 0
    if today:
        for g in today.get("games", []):
            v = store.matches.get(g["fid"])
            if not v:
                continue
            g["status"] = v[7]
            if v[7] in ("postponed", "cancelled") and "postponed" not in g["tags"]:
                g["tags"].append("postponed")
                postponed += 1
            if v[7] == "finished" and v[5] is not None and v[6] is not None:
                g["result"] = [v[5], v[6]]
                finished += 1
        today["updated_utc"] = gen
        save_json(DATA / "today.json", today)
    cov = load_json(DATA / "coverage.json", {})
    cov["evening"] = {"at": gen, "requests_used": api.used, "monthly_remaining": api.quota_remaining,
                      "settled": settled, "postponed": postponed, "error": err}
    save_json(DATA / "coverage.json", cov)
    plog.save()
    _, files = write_outputs(build, store, plog, archive, tz, gen, first_archive)
    if scheduled:                      # a manual evening update never cancels the 6 pm one
        state.update({"evening_local_date": now_local.date().isoformat(), "evening_utc": gen})
    save_json(DATA / "state.json", state)
    build_site(files)
    gh_output(ran="true")
    print(f"Evening update: {finished} of today's games finished, {settled} predictions settled, {postponed} postponed."
          f" Requests used: {api.used}. Monthly left: {api.quota_remaining}." + (f" Problem: {err}" if err else ""))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="full run now (a manual run never cancels the 6:15 run)")
    ap.add_argument("--evening", action="store_true", help="evening update now: results so far, no new list")
    ap.add_argument("--mock", action="store_true", help="use simulated data (testing)")
    ap.add_argument("--mock-quota", type=int, default=5000, help=argparse.SUPPRESS)
    ap.add_argument("--now", help=argparse.SUPPRESS)   # testing: pretend the run happens at this UTC time
    ap.add_argument("--scheduled", action="store_true", help=argparse.SUPPRESS)   # testing: act like a scheduled run
    args = ap.parse_args(argv)

    settings = load_json(CONFIG / "settings.json", None)
    comp_doc = load_json(CONFIG / "competitions.json", None)
    if not settings or not comp_doc:
        sys.exit("config/settings.json or config/competitions.json is missing or not valid JSON")
    tz = ZoneInfo(settings["timezone"])
    state = load_json(DATA / "state.json", {})
    ref = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    now_local = ref.astimezone(tz)
    today_s = now_local.date().isoformat()

    # Scheduled runs: GitHub wakes it at 05:15 and 06:15 UTC (the 6:15 run) and at 17:00 and 18:00 UTC (the 18:00
    # evening update), so one of each pair matches Irish time in summer and winter; the rest skip. If the morning
    # run didn't happen, the evening one does a full run instead. Manual runs never mark the day as done.
    scheduled = (os.environ.get("GITHUB_EVENT_NAME") == "schedule" or args.scheduled) and not args.force and not args.evening
    mode = "evening" if args.evening else "full"
    if scheduled:
        def at(hhmm):
            hh, mm = map(int, hhmm.split(":"))
            return now_local.replace(hour=hh, minute=mm, second=0, microsecond=0) - timedelta(minutes=20)
        m_start, e_start = at(settings["run_time_local"]), at(settings.get("evening_time_local", "18:00"))
        done = state.get("last_run_local_date") == today_s
        if now_local >= e_start and state.get("evening_local_date") != today_s:
            mode = "evening" if done else "full"
        elif m_start <= now_local < e_start and not done:
            mode = "full"
        else:
            print(f"Nothing due at {now_local:%Y-%m-%d %H:%M} Irish time (already ran, or not time yet). Skipping.")
            gh_output(ran="false")
            return 0

    if args.mock:
        sys.path.insert(0, str(ROOT / "tools"))
        from mockopenfoot import MockOpenFoot
        MockOpenFoot.get_all = OpenFoot.get_all      # same paging code as the real client
        api = MockOpenFoot(ref, quota=args.mock_quota, exc=(BudgetExhausted, PlanBlocked, ApiError),
                           add_new=bool(os.environ.get("MOCK_ADD_NEW")))
    else:
        key = os.environ.get("OPENFOOT_API_KEY", "").strip()
        if not key:
            sys.exit("OPENFOOT_API_KEY is not set (add it as a GitHub secret).")
        api = OpenFoot(key)

    R = settings["requests"]
    print(f"Goalscraper ({'evening update' if mode == 'evening' else 'full run'}): {now_local:%a %d %b %Y %H:%M} Irish time")
    store = Store(DATA / "store.json")
    archive = Archive(DATA / "archive")
    first_archive = not archive.months_on_disk()
    ms = load_json(DATA / "model_state.json", None) or default_state(settings)
    for k, v in default_state(settings).items():
        ms.setdefault(k, v)
    build = Build(api, settings, comp_doc, store, ref, ms)
    tcfg = settings.get("thesportsdb") or {}
    if tcfg.get("enabled", True) and mode == "full":
        if args.mock:
            from mockopenfoot import MockSportsDB
            build.tsdb = MockSportsDB(api)
        else:
            build.tsdb = SportsDB(os.environ.get("THESPORTSDB_KEY") or tcfg.get("key", "123"), tcfg.get("seconds_between_requests", 3.0))
        build.tsdb_aliases = load_json(CONFIG / "team_aliases.json", {})
    build.fixture_fixes = {k: v for k, v in load_json(CONFIG / "fixture_fixes.json", {}).items() if not k.startswith("_")}
    if not store.matches and not first_archive:
        n = archive.rebuild_store(store, build.ref_ts - 500 * 86400, build.ref_ts - 1200 * 86400)
        print(f"  saved results were missing (GitHub's cache was empty): rebuilt {n} from the archive")
    ff = settings.get("feed_fixes") or {}
    FEED_FIXES["remap"] = dict(ff.get("remap") or {})
    FEED_FIXES["drop"] = set(ff.get("drop") or [])
    FEED_FIXES["teams"] = dict(ff.get("team_ids") or {})
    fixed = apply_feed_fixes(store, archive)
    if fixed:
        print(f"  feed fixes: {fixed} mislabelled results moved or removed")
    archive.merge_upcoming(store)
    plog = PredLog(DATA / "log")
    plog.load_all()
    if plog.mark_old_replays():
        plog.save()
    n1 = import_first_version(plog, comp_doc, DATA / "history.json")
    if n1:
        print(f"  added {n1} first-version picks from data/history.json to the record")
    i_start, i_end, _ = intl_pass_cfg(settings)
    settings["_pass_intl"] = (ms.get("intl_pass") or {}).get("value", i_start)

    days_left = max(1, (date(ref.year + (ref.month == 12), ref.month % 12 + 1, 1) - ref.date()).days)

    def budget_rule(remaining):
        # spread the monthly quota: at most max_per_run, never into the reserve
        per_run = min(R["max_per_run"], max(60, int((remaining - R["keep_in_reserve"]) / days_left * 3)))
        return min(per_run, remaining - R["keep_in_reserve"])

    api.budget_rule = budget_rule
    nat_ids = {i for no, ids in build.comp_ids.items() if build.comp_by_no[no]["pool"].endswith("nat") for i in ids}

    def save_store():
        store.save(keep_after_ts=build.ref_ts - 500 * 86400, keep_longer=nat_ids, longer_after_ts=build.ref_ts - 1200 * 86400)

    if mode == "evening":
        try:
            return run_evening(api, build, store, plog, archive, tz, state, now_local, first_archive, scheduled)
        finally:
            save_store()

    # weekly catch-up: on Mondays (or if a week has gone by) look back 14 days for results OpenFootAPI added late
    last_cu = state.get("catchup_local_date")
    since_cu = (now_local.date() - date.fromisoformat(last_cu)).days if last_cu else None
    catchup = since_cu is None or (since_cu >= 1 and (now_local.weekday() == 0 or since_cu >= 8))
    if catchup:
        build.catchup_days = R.get("catchup_days_back", 14)
        print(f"  weekly catch-up: re-checking the last {build.catchup_days} days for late results")

    fatal = None
    try:
        build.load_catalogue()
        preds, stats = build.run()
    except BudgetExhausted:
        fatal = "The monthly request quota is used up, so no games could be scored. It resets on the 1st."
    except PlanBlocked as e:
        fatal = f"OpenFootAPI refused the key: {e}"
    except ApiError as e:
        fatal = f"OpenFootAPI error: {e}"
    nat_ids |= {i for no, ids in build.comp_ids.items() if build.comp_by_no[no]["pool"].endswith("nat") for i in ids}
    save_store()
    gen = datetime.now(timezone.utc).isoformat()
    if fatal:
        print("FAILED:", fatal)
        cov = load_json(DATA / "coverage.json", {})
        cov.update({"last_error": fatal, "last_error_at": gen})
        save_json(DATA / "coverage.json", cov)
        plog.settle(store, build.ref_ts)
        plog.save()
        _, files = write_outputs(build, store, plog, archive, tz, gen, first_archive)
        prev = (DATA / "today.json").exists()
        if prev:
            build_site(files)
        gh_output(ran="true" if prev else "false")
        return 1

    # ---- picks per day; games from the last list that have kicked off since are kept as they were ----
    old = load_json(DATA / "today.json", {}) or {}
    for fid, fix in build.fixture_fixes.items():
        if fix.get("skip") or fix.get("kickoff"):
            right = None if fix.get("skip") else int(datetime.fromisoformat(fix["kickoff"]).timestamp())
            for m in [plog.load(plog.month_of(build.ref_ts - 86400 * k)) for k in (0, 15, 31)]:
                e = m.get(fid)
                if e and (right is None or abs(e["ts"] - right) > 6 * 3600) and e.get("r") is None:
                    m.pop(fid)
                    plog.dirty.update(k for k, v in plog.months.items() if v is m)
    new_ids = {p["fid"] for p in preds}
    first_day = now_local.date().isoformat()
    carry = []
    for g in old.get("games", []):
        if g["fid"] in new_ids or g["ts"] > build.ref_ts or "postponed" in g.get("tags", []) or g["fid"] in build.fixture_fixes:
            continue
        if datetime.fromtimestamp(g["ts"], tz).date().isoformat() >= first_day:
            g["_carry"] = True
            carry.append(g)
    rank_by_day(preds + carry, settings, tz)
    for g in carry:
        g.pop("_carry", None)

    # ---- store today's predictions, settle earlier ones, learn from results ----
    for p in preds:
        plog.put(p["fid"], log_entry(p))
    plog.settle(store, build.ref_ts)
    cal = Calibrator(ms, plog, build.ref_ts, print)
    if settings.get("self_adjust", True):
        settled = sum(1 for _, e in plog.entries(build.ref_ts - 365 * 86400, build.ref_ts) if isinstance(e.get("r"), list))
        back = ms.get("replay_back_to") or build.ref_ts - 7 * 86400
        weeks = 0
        while settled < 3000 and back > build.ref_ts - 140 * 86400 and weeks < 2:
            prev, back = back, back - 7 * 86400
            n = build.replay_week(back, plog)
            if n == 0 and not any(v[2] < back and v[7] == "finished" and build.of_to_no.get(v[0])
                                  for v in store.matches.values()):
                back = prev               # results for that week aren't collected yet: try again another day
                break
            settled += n
            weeks += 1
            print(f"  replayed the week from {datetime.fromtimestamp(back, timezone.utc):%d %b}: {n} games")
        ms["replay_back_to"] = back
        cal.step_probabilities()
        try:
            build.tune_daily(cal)
            build.adjust_league_strengths(cal)
        except Exception as e:                    # tuning must never stop the daily list
            print("  tuning skipped:", repr(e))
    plog.save()
    check, files = write_outputs(build, store, plog, archive, tz, gen, first_archive)
    used_pass = settings["_pass_intl"]
    ipass = update_intl_pass(ms, plog, settings, check, cal.note)
    ms.pop("check", None)
    if cal.changes:
        ms["version"] = ms.get("version", 1) + 1
        for c in cal.changes:
            ms["changes"].insert(0, {"date": now_local.date().isoformat(), "text": c})
            print("  model:", c)
    elif settings.get("self_adjust", True):
        ms["changes"].insert(0, {"date": now_local.date().isoformat(), "text": "Checked against results: no changes needed."})
    # keep the change log short, and only one 'no changes' line in a row
    out, last_none = [], False
    for c in ms["changes"]:
        none = c["text"].startswith("Checked against results")
        if none and last_none:
            continue
        out.append(c)
        last_none = none
    ms["changes"] = out[:40]
    save_json(DATA / "model_state.json", ms)

    disc = state.setdefault("discovered", {})
    for no in build.discovered:
        disc.setdefault(str(no), now_local.date().isoformat())
    recent = {int(no) for no, d in disc.items() if int(no) in build.discovered
              and (now_local.date() - date.fromisoformat(d)).days <= 14}
    new_names = [build.comp_by_no[no]["name"] for no in sorted(recent)
                 if (now_local.date() - date.fromisoformat(disc[str(no)])).days <= 7]
    if new_names:
        print("New on OpenFootAPI and now included:", ", ".join(new_names))
    for p in preds:
        p.pop("raw", None)
    today = {
        "app": "Goalscraper", "generated_utc": gen, "source": "OpenFootAPI", "plan": api.plan,
        "window_start_ts": build.ref_ts, "window_end_ts": build.end_ts, "timezone": settings["timezone"],
        "pass": {k: list(pass_marks(settings, k)) + [settings["sections"][k].get("min_score", settings["min_score"])] for k in SECTIONS},
        "games": sorted(preds + carry, key=lambda p: p["ts"]), "new_competitions": new_names,
        "days": sorted({g["day"] for g in preds + carry}),
    }
    # Results only: 3+ results in the last 21 days, all from games played since Goalscraper started watching, and
    # none of them listed beforehand (every run looks at today and tomorrow, so a listed game is always seen first).
    # Clears itself as soon as a game is listed in advance.
    since_ts = int(datetime.fromisoformat(store.upcoming_since + "T00:00:00+00:00").timestamp()) if store.upcoming_since else build.ref_ts
    recent_cut = max(build.ref_ts - 21 * 86400, since_ts)
    upcoming_cut = (now_local.date() - timedelta(days=21)).isoformat()
    live_comps = {e.get("c") for _, e in plog.entries(build.ref_ts - 21 * 86400, build.ref_ts + 2 * 86400)
                  if not e.get("rp") and not e.get("v1")}

    def results_only(no, ids):
        if no in live_comps or not ids:
            return False
        if any(store.upcoming.get(i, "") >= upcoming_cut for i in ids):
            return False
        return sum(1 for v in store.matches.values() if v[0] in ids and v[7] == "finished" and v[2] >= recent_cut) >= 3

    comps_out = []
    for c in sorted(comp_doc["competitions"], key=lambda c: (-c["value"], c["prestige"], c["no"])):
        cv = dict(build.cov.get(c["no"], {"status": "no_games", "games": 0, "note": ""}))
        ids = build.comp_ids.get(c["no"]) or [i for n in c.get("virtual_of", []) for i in build.comp_ids.get(n, [])]
        if c.get("picks") is False:
            cv.update(status="switched_off", games=0, note="Switched off: results are kept (they help rate teams in Europe), games aren't scored")
        elif cv["status"] == "no_games" and c.get("tsdb_id") and build.comp_ids.get(c["no"]):
            cv["note"] = "Games come from TheSportsDB (OpenFootAPI only has results)"
        elif cv["status"] == "no_games" and not c.get("virtual_of") and results_only(c["no"], build.comp_ids.get(c["no"])):
            cv.update(status="results_only", note="OpenFootAPI only sends results here, never upcoming games, so they can't be scored")
        comps_out.append({"no": c["no"], "name": c["name"], "group": c["group"], "value": c["value"],
                          "prestige": c["prestige"], **cv, "newly_found": c["no"] in recent,
                          "matched": [{"id": i, "name": store.comp_name(i)} for i in ids if i], "matched_count": len(ids)})
    coverage = {
        "generated_utc": gen, "plan": api.plan, "source": "OpenFootAPI", "manual": not scheduled,
        "requests_used": api.used, "monthly_remaining": api.quota_remaining,
        "games_scored": len(preds), **stats, "competitions": comps_out,
        "notes": (build.tsdb_skipped + (build.tsdb.errors if build.tsdb else []) + build.notes)[:30], "last_error": None,
        "thesportsdb": {"requests": build.tsdb.used if build.tsdb else 0, "games": sum(build.tsdb_used.values()),
                        "skipped": len(build.tsdb_skipped), "leagues": {str(k): v for k, v in build.tsdb_leagues.items()}},
        "archive_months": len(archive.months_on_disk()), "catchup_last": today_s if catchup else state.get("catchup_local_date"),

        "model": {"version": ms["version"], "changes": ms["changes"][:15], "intl_pass": ipass, "intl_pass_end": i_end,
                  "form_weight": ms["form_weight"], "half_life": ms["half_life"]},
    }
    save_json(DATA / "today.json", today)
    save_json(DATA / "coverage.json", coverage)
    if catchup:
        state["catchup_local_date"] = today_s
    if scheduled:
        state.update({"last_run_local_date": today_s, "last_run_utc": gen})
        if mode == "full" and now_local >= now_local.replace(hour=17, minute=0):
            state["evening_local_date"] = today_s     # a late full run also covers the evening update
    else:
        state["last_manual_utc"] = gen
    save_json(DATA / "state.json", state)
    build_site(files)
    gh_output(ran="true")
    if build.tsdb:
        print(f"TheSportsDB: {sum(build.tsdb_used.values())} games added from {len(build.tsdb_used)} competitions, "
              f"{len(build.tsdb_skipped)} skipped, {build.tsdb.used} requests.")
        for line in build.tsdb_skipped[:10] + build.tsdb.errors[:5]:
            print("  " + line)
    print(f"Plan: {api.plan}. Scored {len(preds)} games. Requests used: {api.used} (run limit {api.limit}). "
          f"Monthly left: {api.quota_remaining}. International pass mark {ipass['value']} ({ipass['games']} games).")
    for key in SECTIONS:
        picks = sorted([p for p in preds if p["sec"][key]["pick"]], key=lambda p: p["sec"][key]["rank"])
        print(f"  {key:6} {len(picks):2} picks: " + ", ".join(f"{p['home']['name']} v {p['away']['name']} {p['sec'][key]['score']:.0f}"
                                                          for p in picks[:4]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
