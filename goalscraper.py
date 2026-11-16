#!/usr/bin/env python3
"""
Goalscraper: each morning, rate every game in the next 24 hours for four sections:
  Easy Goals (at least one goal), Misses (a team not to win), Ballon d'Or (a team to win),
  Raining Goals (both teams to score). Every prediction is stored, settled and used to self-adjust the model.
Data: OpenFootAPI (free Starter plan, 5,000 requests a month).

  python goalscraper.py                    # normal daily run (needs OPENFOOT_API_KEY)
  python goalscraper.py --mock             # simulated data, no key needed (for testing)

Results are kept in data/store.json between runs, so after the first run only the last couple of days are
fetched. Writes data/*.json and site/ (the app that gets published). Python 3.9+, no packages needed.
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

    def save(self, keep_after_ts, keep_longer=(), longer_after_ts=None):
        """Drop old results; international competitions are kept longer (national teams play rarely)."""
        self.matches = {k: v for k, v in self.matches.items()
                        if v[2] >= keep_after_ts or (v[0] in keep_longer and v[2] >= (longer_after_ts or keep_after_ts))}
        save_json(self.path, {"matches": self.matches, "teams": self.teams, "comps": self.comps,
                              "backfilled": self.backfilled, "last_sweep": self.last_sweep, "seasons": self.seasons})

    def add(self, m):
        """m: an OpenFootAPI match object."""
        mid = m.get("id")
        if not mid:
            return None
        comp = m.get("competitionId") or ""
        season = str(m.get("season") or "")
        ht, at = m.get("homeTeam") or {}, m.get("awayTeam") or {}
        hid = ht.get("id") or ("name:" + norm(ht.get("name")))
        aid = at.get("id") or ("name:" + norm(at.get("name")))
        for t, tid in ((ht, hid), (at, aid)):
            prev = self.teams.get(tid, [None, None, None])
            home_comp = t.get("competitionId") or prev[1]
            if home_comp and self.is_cup(home_comp) and prev[1] and not self.is_cup(prev[1]):
                home_comp = prev[1]
            self.teams[tid] = [t.get("name") or prev[0], home_comp, t.get("country") or prev[2]]
        sc = m.get("score") or {}
        status = norm(m.get("status"))
        rec = [comp, season, to_ts(m["kickoffAt"]), hid, aid, sc.get("home"), sc.get("away"), status,
               m.get("round") or "", bool(m.get("kickoffTimeKnown", True))]
        self.matches[mid] = rec
        if season and comp:
            old = self.seasons.get(comp, "")
            if not old or season[:4] > old[:4] or (season[:4] == old[:4] and len(season) > len(old)):
                self.seasons[comp] = season
        return mid

    def comp_name(self, cid):
        return (self.comps.get(cid) or {}).get("name") or cid if cid != "_fetched" else cid

    def is_cup(self, cid):
        n = norm(self.comp_name(cid)) + " " + norm(cid.replace("_", " "))
        return any(w in n for w in CUP_WORDS)


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
    knot = min(S["min_score"], S["min_score_international"])
    sc = lambda f, k: scale_score(f, sec[k]["fail_at_100"], sec[k]["fail_at_50"], sec[k].get("fail_at_1", DEFAULT_AT1[k]), knot)
    out = {}
    g = sec["goals"]
    out["goals"] = {"listed": (1 - p["p00"]) <= g["max_chance_of_goal"] + 1e-9,
                    "score": sc(p["p00"], "goals"), "p": 1 - p["p00"]}
    fav = "home" if p["w"] >= p["l"] else "away"
    dog = "away" if fav == "home" else "home"
    pf, pd = (p["w"], p["l"]) if fav == "home" else (p["l"], p["w"])
    b, m = sec["ballon"], sec["misses"]
    out["ballon"] = {"listed": pf >= b["min_favourite"], "team": fav, "p": pf,
                     "score": sc(1 - pf, "ballon")}
    out["misses"] = {"listed": pf < b["min_favourite"] and pd >= 1 / (m["longest_price"] + 1), "team": dog, "p": 1 - pd,
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

    def load_range(self, from_ts, to_ts):
        d = datetime.fromtimestamp(from_ts, timezone.utc).replace(day=1)
        end = datetime.fromtimestamp(to_ts, timezone.utc)
        while d <= end:
            self.load(d.strftime("%Y-%m"))
            d = (d + timedelta(days=32)).replace(day=1)

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
        for month, m in self.months.items():
            for fid, e in m.items():
                if e.get("r") is not None or e["ts"] >= ref_ts:
                    continue
                v = store.matches.get(fid)
                if v and v[7] == "finished" and v[5] is not None and v[6] is not None:
                    e["r"] = [v[5], v[6]]
                elif (v and v[7] in ("postponed", "cancelled")) or e["ts"] < ref_ts - 4 * 86400:
                    e["r"] = "void"
                else:
                    continue
                self.dirty.add(month)

    def save(self):
        for month in self.dirty:
            save_json(self.folder / f"{month}.json", self.months[month])
        self.dirty = set()


# ----------------------------------------------------------------------------------------------
# Model state: what the daily self-adjustment has learned (data/model_state.json)
# ----------------------------------------------------------------------------------------------
LIMITS = {"rho": (-0.20, 0.05, 0.01), "fav": (-0.15, 0.15, 0.01), "z00": (-0.60, 0.60, 0.04), "btts": (-0.50, 0.50, 0.04)}
MIN_GAMES = {"club": 400, "intl": 150}
NAMES = {"rho": "Draw correction", "fav": "Favourite strength", "z00": "0-0 allowance", "btts": "Both-score allowance"}


def default_state(S):
    sv = S["starting_values"]
    return {"version": 1, "rho": {"club": sv["draw_correction"], "intl": sv["draw_correction"]},
            "fav": {"club": 0.0, "intl": 0.0}, "z00": {"club": 0.0, "intl": 0.0}, "btts": {"club": 0.0, "intl": 0.0},
            "form_weight": sv["form_weight"], "half_life": sv["strength_half_life_days"], "league_adj": {},
            "tuning": {}, "changes": [], "check": [], "replay_back_to": None}


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
            if isinstance(e.get("r"), list) and ("intl" if e.get("i") else "club") == group:
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

    def model_check(self):
        lines = []
        for group, label in (("club", "Clubs"), ("intl", "Internationals")):
            rows = [e for e in self.settled(group, days=90, limit=10**6) if e.get("p")]
            if len(rows) < 30:
                continue
            n = len(rows)
            f00 = sum(e["p"]["p00"] for e in rows) / n * 100
            a00 = sum(1 for e in rows if sum(e["r"]) == 0) / n * 100
            fd = sum(e["p"]["d"] for e in rows) / n * 100
            ad = sum(1 for e in rows if e["r"][0] == e["r"][1]) / n * 100
            fb = sum(e["p"]["btts"] for e in rows) / n * 100
            ab = sum(1 for e in rows if e["r"][0] > 0 and e["r"][1] > 0) / n * 100
            lines.append({"label": f"{label}: 0-0s per 100 games", "forecast": round(f00, 1), "actual": round(a00, 1), "n": n})
            lines.append({"label": f"{label}: draws per 100 games", "forecast": round(fd, 1), "actual": round(ad, 1), "n": n})
            lines.append({"label": f"{label}: both teams scored, per 100", "forecast": round(fb, 1), "actual": round(ab, 1), "n": n})
        self.ms["check"] = lines


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
        self.other = comp_doc["other_league_strength"]
        self.confed = comp_doc["confederation_strength"]
        self.nat_table_src = comp_doc.get("national_team_strength")
        self.tz = ZoneInfo(settings["timezone"])
        self.ref = ref_utc
        self.ref_ts = int(ref_utc.timestamp())
        self.end_ts = self.ref_ts + int(settings["window_hours"] * 3600)
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

        # 1) recent dates (results + the window's fixtures)
        today = self.ref.astimezone(timezone.utc).date()
        end_day = datetime.fromtimestamp(self.end_ts, timezone.utc).date()
        first = today - timedelta(days=R["sweep_days_back"])
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
        rank_sections(preds, self.S)
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
                plog.put(p["fid"], log_entry(p, [v[5], v[6]]), replay=True)
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


def rank_sections(preds, S):
    for key in SECTIONS:
        cand = sorted([p for p in preds if p["sec"][key]["listed"]], key=lambda p: (-p["sec"][key]["score"], p["ts"]))
        n = 0
        for r, p in enumerate(cand):
            s = p["sec"][key]
            s["rank"] = r + 1
            mn = S["min_score_international"] if p["intl"] else S["min_score"]
            s["pick"] = s["score"] >= mn and n < S["top_n"]
            n += s["pick"]
        for p in preds:
            if not p["sec"][key]["listed"]:
                p["sec"][key].update(rank=None, pick=False)


def log_entry(p, result=None):
    return {"ts": p["ts"], "c": p["comp_no"], "cn": p["comp"], "i": p["intl"], "h": p["home"]["name"], "a": p["away"]["name"],
            "lh": p["raw"][0], "la": p["raw"][1], "lim": "limited_data" in p["tags"],
            "p": {"p00": p["p00"], "w": p["pw_home"], "d": p["pd"], "l": p["pw_away"], "btts": p["p_btts"]},
            "s": {k: [v["score"], v.get("rank"), bool(v.get("pick")), v.get("team")] for k, v in p["sec"].items()},
            "r": result}


def record_summary(plog, ref_ts, S):
    """Section hit rates for the Record screen (real picks only, not replays)."""
    secs = {k: {"d30": {"won": 0, "lost": 0, "void": 0, "pending": 0}, "all": {"won": 0, "lost": 0, "void": 0, "pending": 0}}
            for k in SECTIONS}
    recent = defaultdict(list)
    for fid, e in plog.entries(ref_ts - S["history_days"] * 86400, ref_ts + 2 * 86400):
        if e.get("rp"):
            continue
        for k, (score, rank, pick, team) in e["s"].items():
            if not pick:
                continue
            r = e.get("r")
            res = "pending" if r is None else "void" if r == "void" else ("won" if pick_won(k, team, r[0], r[1]) else "lost")
            secs[k]["all"][res] += 1
            if e["ts"] >= ref_ts - 30 * 86400:
                secs[k]["d30"][res] += 1
            if e["ts"] >= ref_ts - 7 * 86400:
                day = datetime.fromtimestamp(e["ts"], timezone.utc).date().isoformat()
                recent[day].append({"ts": e["ts"], "h": e["h"], "a": e["a"], "comp": e["cn"], "section": k, "team": team,
                                    "score": score, "rank": rank, "result": r, "res": res})
    days = [{"date": d, "picks": sorted(v, key=lambda x: (x["ts"], x["section"]))} for d, v in sorted(recent.items(), reverse=True)]
    return {"sections": secs, "recent": days}


def build_site():
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(WEB, SITE)
    (SITE / "data").mkdir(exist_ok=True)
    for name in ("today.json", "coverage.json", "record.json"):
        if (DATA / name).exists():
            shutil.copy(DATA / name, SITE / "data" / name)


def gh_output(**kv):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as fh:
            for k, v in kv.items():
                fh.write(f"{k}={v}\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="run even if today's run already happened")
    ap.add_argument("--mock", action="store_true", help="use simulated data (testing)")
    ap.add_argument("--mock-quota", type=int, default=5000, help=argparse.SUPPRESS)
    ap.add_argument("--now", help=argparse.SUPPRESS)   # testing: pretend the run happens at this UTC time
    args = ap.parse_args(argv)

    settings = load_json(CONFIG / "settings.json", None)
    comp_doc = load_json(CONFIG / "competitions.json", None)
    if not settings or not comp_doc:
        sys.exit("config/settings.json or config/competitions.json is missing or not valid JSON")
    tz = ZoneInfo(settings["timezone"])
    state = load_json(DATA / "state.json", {})
    ref = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    now_local = ref.astimezone(tz)

    # Scheduled runs: 6:15 Irish time all year. GitHub wakes it at 05:15 and 06:15 UTC; only one proceeds.
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and not args.force:
        hh, mm = map(int, settings["run_time_local"].split(":"))
        start = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0) - timedelta(minutes=20)
        if now_local < start or state.get("last_run_local_date") == now_local.date().isoformat():
            print(f"Not time yet / already ran today ({now_local:%Y-%m-%d %H:%M} Irish time). Skipping.")
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
    print(f"Goalscraper: window starts {now_local:%a %d %b %Y %H:%M} Irish time")
    store = Store(DATA / "store.json")
    ms = load_json(DATA / "model_state.json", None) or default_state(settings)
    for k, v in default_state(settings).items():
        ms.setdefault(k, v)
    build = Build(api, settings, comp_doc, store, ref, ms)
    plog = PredLog(DATA / "log")
    plog.load_range(build.ref_ts - 400 * 86400, build.end_ts)

    days_left = max(1, (date(ref.year + (ref.month == 12), ref.month % 12 + 1, 1) - ref.date()).days)

    def budget_rule(remaining):
        # spread the monthly quota: at most max_per_run, never into the reserve
        per_run = min(R["max_per_run"], max(60, int((remaining - R["keep_in_reserve"]) / days_left * 3)))
        return min(per_run, remaining - R["keep_in_reserve"])

    api.budget_rule = budget_rule
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
    nat_ids = {i for no, ids in build.comp_ids.items() if build.comp_by_no[no]["pool"].endswith("nat") for i in ids}
    store.save(keep_after_ts=build.ref_ts - 500 * 86400, keep_longer=nat_ids, longer_after_ts=build.ref_ts - 1200 * 86400)
    if fatal:
        print("FAILED:", fatal)
        cov = load_json(DATA / "coverage.json", {})
        cov.update({"last_error": fatal, "last_error_at": datetime.now(timezone.utc).isoformat()})
        save_json(DATA / "coverage.json", cov)
        prev = (DATA / "today.json").exists()
        if prev:
            build_site()
        gh_output(ran="true" if prev else "false")
        return 1

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
    cal.model_check()
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
    plog.save()
    save_json(DATA / "model_state.json", ms)

    gen = datetime.now(timezone.utc)
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
        "app": "Goalscraper", "generated_utc": gen.isoformat(), "source": "OpenFootAPI", "plan": api.plan,
        "window_start_ts": build.ref_ts, "window_end_ts": build.end_ts, "timezone": settings["timezone"],
        "top_n": settings["top_n"], "min_club": settings["min_score"], "min_intl": settings["min_score_international"],
        "ballon_min": settings["sections"]["ballon"]["min_favourite"],
        "misses_longest": settings["sections"]["misses"]["longest_price"],
        "goals_max": settings["sections"]["goals"]["max_chance_of_goal"],
        "games": sorted(preds, key=lambda p: p["ts"]), "new_competitions": new_names,
    }
    comps_out = []
    for c in sorted(comp_doc["competitions"], key=lambda c: (-c["value"], c["prestige"], c["no"])):
        cv = build.cov.get(c["no"], {"status": "no_games", "games": 0, "note": ""})
        ids = build.comp_ids.get(c["no"]) or [i for n in c.get("virtual_of", []) for i in build.comp_ids.get(n, [])]
        comps_out.append({"no": c["no"], "name": c["name"], "group": c["group"], "value": c["value"],
                          "prestige": c["prestige"], **cv, "newly_found": c["no"] in recent,
                          "matched": [{"id": i, "name": store.comp_name(i)} for i in ids if i], "matched_count": len(ids)})
    coverage = {
        "generated_utc": gen.isoformat(), "plan": api.plan, "source": "OpenFootAPI",
        "requests_used": api.used, "requests_available": api.limit, "monthly_remaining": api.quota_remaining,
        "games_scored": len(preds), **stats, "competitions": comps_out, "notes": build.notes[:20], "last_error": None,
        "model": {"version": ms["version"], "changes": ms["changes"][:15], "check": ms.get("check", []),
                  "form_weight": ms["form_weight"], "half_life": ms["half_life"]},
    }
    record = record_summary(plog, build.ref_ts, settings)
    record["check"] = ms.get("check", [])
    record["generated_utc"] = gen.isoformat()
    save_json(DATA / "today.json", today)
    save_json(DATA / "coverage.json", coverage)
    save_json(DATA / "record.json", record)
    state.update({"last_run_local_date": now_local.date().isoformat(), "last_run_utc": gen.isoformat()})
    save_json(DATA / "state.json", state)
    build_site()
    gh_output(ran="true")
    print(f"Plan: {api.plan}. Scored {len(preds)} games. Requests used: {api.used} (run limit {api.limit}). "
          f"Monthly left: {api.quota_remaining}.")
    for key in SECTIONS:
        picks = sorted([p for p in preds if p["sec"][key]["pick"]], key=lambda p: p["sec"][key]["rank"])
        print(f"  {key:6} {len(picks):2} picks: " + ", ".join(f"{p['home']['name']} v {p['away']['name']} {p['sec'][key]['score']:.0f}"
                                                          for p in picks[:4]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
