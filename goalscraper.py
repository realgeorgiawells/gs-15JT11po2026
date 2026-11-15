#!/usr/bin/env python3
"""
Goalscraper: each morning, score every game in the next 24 hours on how unlikely it is to end 0-0.
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


def score_from_p00(p00, scale):
    hi, lo = scale["p00_at_100"], scale["p00_at_1"]
    p = min(max(p00, hi), lo)
    return 1 + 99 * (math.log(lo) - math.log(p)) / (math.log(lo) - math.log(hi))


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

    def save(self, keep_after_ts):
        self.matches = {k: v for k, v in self.matches.items() if v[2] >= keep_after_ts}
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
# The daily build
# ----------------------------------------------------------------------------------------------
class Build:
    def __init__(self, api, settings, comp_doc, store, ref_utc, log=print):
        self.api, self.S, self.store, self.log = api, settings, store, log
        self.comps = comp_doc["competitions"]
        self.comp_by_no = {c["no"]: c for c in self.comps}
        self.comp_ids = {c["no"]: [c["openfoot_id"]] for c in self.comps if c.get("openfoot_id")}
        self.of_to_no = {i: no for no, ids in self.comp_ids.items() for i in ids}
        self.discovered = {}        # no -> [ids] found later in OpenFootAPI's catalogue
        self.other = comp_doc["other_league_strength"]
        self.confed = comp_doc["confederation_strength"]
        self.tz = ZoneInfo(settings["timezone"])
        self.ref = ref_utc
        self.ref_ts = int(ref_utc.timestamp())
        self.end_ts = self.ref_ts + int(settings["window_hours"] * 3600)
        self.cov = {}
        self.notes = []

    # ---------------- competitions catalogue (refreshed weekly) ----------------
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
        calendar = country in CALENDAR_COUNTRIES
        if calendar:
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

    # ---------------- run ----------------
    def run(self, history):
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
        dates = []
        d = first
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

        # 3) settle earlier predictions from stored results
        self.settle(history)

        # 4) make sure each competition's season (and each cup side's home league) is in the store
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
                if c["kind"] != "league":
                    for t in sorted(teams):
                        hl = self.home_league(t)
                        if hl and hl not in self.comp_ids.get(no, []):
                            self.backfill(hl, self.guess_season(hl))
                thin = [t for t in teams if self.team_games(t, season_start) < M["previous_season_if_games_below"]]
                if thin:
                    comps_needed = {self.home_league(t) or m["comp"] for m in cands[no] for t in (m["home"], m["away"]) if t in thin}
                    for comp in sorted(x for x in comps_needed if x):
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

        preds = self.predict(cands)
        for no, cov in self.cov.items():
            if cov["status"] in ("covered", "partial"):
                cov["games"] = sum(1 for p in preds if p["comp_no"] == no)
        return preds, stats

    # ---------------- model ----------------
    def league_strength(self, cid):
        no = self.of_to_no.get(cid)
        if no and "strength" in self.comp_by_no[no]:
            return self.comp_by_no[no]["strength"]
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
        return max(10, base - self.other["lower_division_penalty"] * (tier - 1))

    def priors_for(self, pool, teams):
        scale = self.S["model"]["league_strength_scale"]
        pri = {}
        for t in teams:
            if pool.endswith("club"):
                hl = self.home_league(t)
                s = self.league_strength(hl) if hl else self.other["default"]
            else:
                s = self.confed.get(self.nat_confed(t), self.confed["unknown"])
            o = scale * (s - 50) / 50
            pri[t] = (o, o)
        return pri

    def nat_confed(self, t):
        names = " ".join(norm(self.store.comp_name(v[0])) for v in self.store.matches.values() if t in (v[3], v[4]))
        for confed, keys in (("UEFA", ("uefa", "euro", "nations league")), ("CONMEBOL", ("copa america", "conmebol", "south america")),
                             ("CONCACAF", ("concacaf", "gold cup")), ("CAF", ("africa", "caf ")), ("AFC", ("asia", "afc")),
                             ("OFC", ("oceania", "ofc"))):
            if any(k in names for k in keys):
                return confed
        return "unknown"

    def predict(self, cands):
        S, M = self.S, self.S["model"]
        wf = S["weights"]["form"]
        pool_of = {i: self.comp_by_no[no]["pool"] for i, no in self.of_to_no.items()}
        since = self.ref_ts - 450 * 86400
        pools = defaultdict(list)
        for no, ms in cands.items():
            if self.cov.get(no, {}).get("status") in ("omitted_budget", "blocked_plan", "error", "not_available"):
                continue
            for m in ms:
                pools[self.comp_by_no[no]["pool"]].append((no, m))
        preds = []
        cur_season_start = self.ref_ts - 330 * 86400
        for pool, items in pools.items():
            matches = []
            for v in self.store.matches.values():
                if v[7] != "finished" or v[5] is None or v[6] is None or not (since <= v[2] < self.ref_ts):
                    continue
                if pool_of.get(v[0], "men_club") != pool:
                    continue
                w = 1.0 if v[2] >= cur_season_start else M["previous_season_weight"]
                matches.append({"home": v[3], "away": v[4], "gh": v[5], "ga": v[6], "ts": v[2], "w": w})
            teams = {t for m in matches for t in (m["home"], m["away"])} | {t for _, m in items for t in (m["home"], m["away"])}
            pri = self.priors_for(pool, teams)
            self.log(f"  fitting {pool}: {len(matches)} results, {len(teams)} teams")
            long = fit_pool(matches, pri, M["prior_spread"], M["strength_half_life_days"], self.ref_ts)
            long_pri = {t: (long["att"][t], long["def"][t]) for t in long["att"]}
            short = fit_pool(matches, long_pri, M["form_spread"], M["form_half_life_days"], self.ref_ts, iters=25)
            games = Counter()
            for m in matches:
                if m["ts"] >= cur_season_start:
                    games[m["home"]] += 1
                    games[m["away"]] += 1
            mu = (1 - wf) * long["mu"] + wf * short["mu"]
            hadv = (1 - wf) * long["home"] + wf * short["home"]

            def team(t):
                a = (1 - wf) * long["att"].get(t, pri[t][0]) + wf * short["att"].get(t, pri[t][0])
                d = (1 - wf) * long["def"].get(t, pri[t][1]) + wf * short["def"].get(t, pri[t][1])
                return a, d

            for no, m in items:
                c = self.comp_by_no[no]
                ah, dh = team(m["home"])
                aa, da = team(m["away"])
                h = 0 if no in (41, 43, 46, 47, 49, 52) else hadv
                lh = math.exp(mu + h + ah - da)
                la = math.exp(mu + aa - dh)
                p00 = math.exp(-(lh + la))
                limited = min(games[m["home"]], games[m["away"]]) < M["limited_data_games"]
                score = score_from_p00(p00, S["score_scale"])
                if limited:
                    score *= M["limited_data_score_factor"]
                tags = ["limited_data"] if limited else []
                if not m["time_known"]:
                    tags.append("time_tbc")
                tn = lambda t: (self.store.teams.get(t) or [t])[0] or t
                preds.append({
                    "fid": m["id"], "ts": m["ts"], "comp_no": no, "comp": c["name"], "group": c["group"],
                    "round": m["round"], "league_name": self.store.comp_name(m["comp"]),
                    "home": {"id": m["home"], "name": tn(m["home"]), "games": games[m["home"]],
                             "att": rating(ah, 0.6), "def": rating(dh, 0.6), "ovr": rating(ah + dh, 0.9)},
                    "away": {"id": m["away"], "name": tn(m["away"]), "games": games[m["away"]],
                             "att": rating(aa, 0.6), "def": rating(da, 0.6), "ovr": rating(aa + da, 0.9)},
                    "xg_home": round(lh, 2), "xg_away": round(la, 2), "p00": round(p00, 4), "p00_model": round(p00, 4),
                    "p00_market": None, "market_used": False,
                    "score": round(max(1.0, min(100.0, score)), 2),
                    "odds": None, "bookie": None, "implied": None, "edge": None, "tags": tags,
                })
        preds.sort(key=lambda p: (-p["score"], p["ts"]))
        for i, p in enumerate(preds):
            p["rank"] = i + 1
            p["top10"] = i < S["top_n"]
        return preds

    # ---------------- tracking ----------------
    def settle(self, history):
        for fid, g in history["games"].items():
            if g.get("result") is not None:
                continue
            v = self.store.matches.get(fid)
            if v and v[7] == "finished" and v[5] is not None:
                g["result"] = {"h": v[5], "a": v[6], "status": "FT"}
            elif v and v[7] in ("postponed", "cancelled"):
                g["result"] = {"status": v[7], "void": True}
            elif g["ts"] < self.ref_ts - 4 * 86400:
                g["result"] = {"status": "no result", "void": True}


def record_history(history, preds, settings):
    for p in preds:
        g = history["games"].get(str(p["fid"]), {})
        g.update({"ts": p["ts"], "comp": p["comp"], "home": p["home"]["name"], "away": p["away"]["name"],
                  "score": p["score"], "p00": p["p00"], "odds": p["odds"], "top10": p["top10"], "rank": p["rank"]})
        g.setdefault("result", None)
        history["games"][str(p["fid"])] = g
    cutoff = time.time() - settings["history_days"] * 86400
    history["games"] = {k: v for k, v in history["games"].items() if v["ts"] >= cutoff}
    return history


def build_site():
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(WEB, SITE)
    (SITE / "data").mkdir(exist_ok=True)
    for name in ("today.json", "coverage.json", "history.json"):
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
    history = load_json(DATA / "history.json", {"games": {}})
    history.setdefault("games", {})
    if history.get("mode") == "rehearsal":
        history = {"games": {}}
    history["mode"] = "live"
    build = Build(api, settings, comp_doc, store, ref)

    days_left = max(1, (date(ref.year + (ref.month == 12), ref.month % 12 + 1, 1) - ref.date()).days)

    def budget_rule(remaining):
        # spread the monthly quota: at most max_per_run, never into the reserve
        per_run = min(R["max_per_run"], max(60, int((remaining - R["keep_in_reserve"]) / days_left * 3)))
        return min(per_run, remaining - R["keep_in_reserve"])

    api.budget_rule = budget_rule
    fatal = None
    try:
        build.load_catalogue()
        preds, stats = build.run(history)
    except BudgetExhausted:
        fatal = "The monthly request quota is used up, so no games could be scored. It resets on the 1st."
    except PlanBlocked as e:
        fatal = f"OpenFootAPI refused the key: {e}"
    except ApiError as e:
        fatal = f"OpenFootAPI error: {e}"
    store.save(keep_after_ts=build.ref_ts - 500 * 86400)
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

    history = record_history(history, preds, settings)
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
    today = {
        "app": "Goalscraper", "generated_utc": gen.isoformat(), "mode": "live", "source": "OpenFootAPI",
        "odds_enabled": False, "plan": api.plan, "window_start_ts": build.ref_ts, "window_end_ts": build.end_ts,
        "timezone": settings["timezone"], "min_odds": settings["min_odds"], "top_n": settings["top_n"],
        "weights": {"form": settings["weights"]["form"], "market": 0}, "games": preds,
        "new_competitions": new_names,
    }
    comps_out = []
    for c in sorted(comp_doc["competitions"], key=lambda c: (-c["value"], c["prestige"], c["no"])):
        cv = build.cov.get(c["no"], {"status": "no_games", "games": 0, "note": ""})
        ids = build.comp_ids.get(c["no"]) or [i for n in c.get("virtual_of", []) for i in build.comp_ids.get(n, [])]
        comps_out.append({"no": c["no"], "name": c["name"], "group": c["group"], "value": c["value"],
                          "prestige": c["prestige"], **cv, "with_odds": 0, "newly_found": c["no"] in recent,
                          "matched": [{"id": i, "name": store.comp_name(i)} for i in ids if i], "matched_count": len(ids),
                          "odds_supported": None})
    coverage = {
        "generated_utc": gen.isoformat(), "mode": "live", "plan": api.plan, "source": "OpenFootAPI",
        "requests_used": api.used, "requests_available": api.limit, "monthly_remaining": api.quota_remaining,
        "games_scored": len(preds), **stats, "competitions": comps_out, "notes": build.notes[:20], "last_error": None,
    }
    save_json(DATA / "today.json", today)
    save_json(DATA / "coverage.json", coverage)
    save_json(DATA / "history.json", history)
    state.update({"last_run_local_date": now_local.date().isoformat(), "last_run_utc": gen.isoformat()})
    save_json(DATA / "state.json", state)
    build_site()
    gh_output(ran="true")
    print(f"Plan: {api.plan}. Scored {len(preds)} games. Requests used: {api.used} (run limit {api.limit}). Monthly left: {api.quota_remaining}.")
    for p in preds[: settings["top_n"]]:
        print(f"  {p['score']:6.2f}  P(0-0) {p['p00']*100:4.1f}%  {p['home']['name']} v {p['away']['name']}  ({p['comp']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
