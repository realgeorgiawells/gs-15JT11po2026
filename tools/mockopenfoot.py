"""
Simulated OpenFootAPI for testing Goalscraper without a key. Same response shapes as the real API:
{"data": [...], "meta": {"total_count", "pagination": {"limit": 50, "next_cursor"}, "access": {...}}},
50 items per page with a base64 "offset:N" cursor. Deterministic world anchored to the run's month.
"""
import base64
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES = ["Rovers", "United", "City", "Athletic", "Town", "Wanderers", "Albion", "Celtic", "Rangers", "Dynamo",
         "Sporting", "Real", "Olympic", "Union", "Victoria", "Harbour"]
COUNTRY = {"eng": "England", "sco": "Scotland", "it": "Italy", "es": "Spain", "de": "Germany", "fr": "France",
           "pt": "Portugal", "be": "Belgium", "nl": "Netherlands", "tr": "Turkey", "grc": "Greece", "swe": "Sweden",
           "irl": "Ireland", "usa": "USA", "aus": "Australia", "jpn": "Japan", "dnk": "Denmark"}
CALENDAR = {"comp_allsvenskan_swe", "comp_premier_division_irl", "comp_mls_usa", "comp_j1_league_jpn"}


def _pois(rnd, lam):
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rnd.random()
        if p <= L:
            return k
        k += 1


class MockOpenFoot:
    def __init__(self, now_utc, quota=5000, exc=(Exception, Exception, Exception), add_new=False):
        self.add_new = add_new
        self.BudgetExhausted, self.PlanBlocked, self.ApiError = exc
        self.now = now_utc
        self.now_ts = int(now_utc.timestamp())
        self.quota_left0 = quota
        self.used, self.limit = 0, 10**9
        self.quota_remaining = None
        self.plan = "starter"
        self.cursor_param = None
        self.budget_rule = None
        self._budget_set = False
        self.calls = []
        self._build()

    # ------------------------------------------------------------------ world
    def _build(self):
        rnd = random.Random(42)
        comps = json.loads((ROOT / "config" / "competitions.json").read_text())["competitions"]
        self.comps = {}
        self.matches = []
        self.teams = {}
        anchor = datetime(self.now.year, self.now.month, 15, tzinfo=timezone.utc)
        ey = anchor.year if anchor.month >= 7 else anchor.year - 1

        def label(cid, back=0):
            return str(anchor.year - back) if cid in CALENDAR else f"{ey - back}/{(ey - back + 1) % 100:02d}"

        leagues = [(c["openfoot_id"], c["strength"], c["name"]) for c in comps
                   if c.get("openfoot_id") and c["kind"] == "league"]
        leagues += [("comp_superliga_dnk", 62, "Danish Superliga"), ("comp_serie_b_it", 70, "Serie B")]
        for c in comps:
            if c.get("openfoot_id"):
                self.comps[c["openfoot_id"]] = {"id": c["openfoot_id"], "name": c["name"].split(" (")[0],
                                                "country": COUNTRY.get(c["openfoot_id"].rsplit("_", 1)[-1], "World")}
        self.comps["comp_superliga_dnk"] = {"id": "comp_superliga_dnk", "name": "Danish Superliga", "country": "Denmark"}
        self.comps["comp_serie_b_it"] = {"id": "comp_serie_b_it", "name": "Serie B", "country": "Italy"}
        if getattr(self, "add_new", False):    # simulate OpenFootAPI adding competitions later
            self.comps["comp_national_league_eng"] = {"id": "comp_national_league_eng", "name": "National League", "country": "England"}
            self.comps["comp_championship_nir"] = {"id": "comp_championship_nir", "name": "Championship", "country": "Northern Ireland"}
            self.comps["comp_wsl_eng"] = {"id": "comp_wsl_eng", "name": "Women's Super League", "country": "England"}
        for i in range(60):   # padding so the catalogue needs several pages, like the real one (120)
            self.comps[f"comp_extra_{i}"] = {"id": f"comp_extra_{i}", "name": f"Extra League {i}", "country": "Elsewhere"}

        self.by_league = {}
        tid = 0
        for k, (cid, strength, name) in enumerate(leagues):
            n = 16 if cid in ("comp_premier_league_eng", "comp_laliga_es", "comp_serie_a_it") else 12
            base = 0.55 * ((strength - (12 if cid == "comp_serie_b_it" else 0)) - 50) / 50
            country = COUNTRY.get(cid.rsplit("_", 1)[-1], "")
            ids = []
            for i in range(n):
                tid += 1
                t = {"id": f"team_{tid}", "name": f"{country[:3]} {NAMES[i % 16]}", "country": country,
                     "competitionId": cid, "_a": base + rnd.gauss(0, 0.14), "_d": base + rnd.gauss(0, 0.14)}
                self.teams[t["id"]] = t
                ids.append(t["id"])
            self.by_league[cid] = ids
            rounds = 2 * (n - 1)
            start = anchor - timedelta(days=rounds * 3 // 2 + k % 3)
            self._rr(cid, label(cid), ids, start, 3, (k * 7) % 24)
            self._rr(cid, label(cid, 1), ids, start - timedelta(days=365), 3, (k * 7) % 24)

        pool = []
        for cid in ("comp_premier_league_eng", "comp_laliga_es", "comp_serie_a_it", "comp_bundesliga_de",
                    "comp_ligue_1_fr", "comp_primeira_liga_pt", "comp_eredivisie_nl", "comp_superliga_dnk",
                    "comp_scottish_prem_sco"):
            pool += self.by_league[cid][:3]
        rnd.shuffle(pool)
        for cid, teams in (("comp_uefa_champions_league", pool[:12]), ("comp_uefa_europa_league", pool[12:22]),
                           ("comp_uefa_conference_league", pool[22:27] + self.by_league["comp_premier_division_irl"][:3])):
            self._cup(cid, label(cid), teams, datetime(ey, 9, 16, 19, tzinfo=timezone.utc), 14, "League Stage - {}", rnd)
        # qualifying-round ties inside the window (tests the split into competition 30)
        for cid in ("comp_uefa_champions_league", "comp_uefa_europa_league"):
            a, b = rnd.sample(pool, 2)
            self._add(cid, label(cid), "3rd Qualifying Round", self.now_ts + 9 * 3600, a, b)

        nats = []
        for nme in ["England", "France", "Spain", "Ireland", "Scotland", "Wales", "Norway", "Poland"]:
            tid += 1
            t = {"id": f"team_{tid}", "name": nme, "country": nme, "competitionId": "comp_uefa_nations_league",
                 "_a": 0.2 + rnd.gauss(0, 0.2), "_d": 0.2 + rnd.gauss(0, 0.2)}
            self.teams[t["id"]] = t
            nats.append(t["id"])
        self._cup("comp_uefa_nations_league", label("comp_uefa_nations_league"), nats,
                  anchor - timedelta(days=60), 15, "League A - {}", rnd)

        window = sorted((m for m in self.matches if self.now_ts < m["_ts"] < self.now_ts + 86400), key=lambda m: m["_ts"])
        if len(window) > 2:
            window[0]["status"] = "postponed"
            window[1]["_live"] = True
        for m in self.matches:
            if m["_ts"] < self.now_ts and m["status"] == "scheduled":
                lh, la = self._lams(m["_h"], m["_aw"])
                r2 = random.Random(hash(m["id"]) & 0xFFFFFFFF)
                m["status"] = "finished"
                m["score"] = {"home": _pois(r2, lh), "away": _pois(r2, la)}
                m["period"] = "FT"
            elif m.get("_live"):
                m["status"] = "live"

    def _lams(self, h, a):
        th, ta = self.teams[h], self.teams[a]
        return math.exp(math.log(1.28) + 0.22 + th["_a"] - ta["_d"]), math.exp(math.log(1.28) + ta["_a"] - th["_d"])

    def _add(self, cid, season, rnd_label, ts, h, a):
        mid = f"match_{cid}_{season}_{ts}_{h}_{a}".replace("/", "-")
        self.matches.append({"id": mid, "competitionId": cid, "season": season, "round": rnd_label,
                             "kickoffAt": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                             "kickoffTimeKnown": True, "status": "scheduled", "_ts": ts, "_h": h, "_aw": a,
                             "score": {"home": None, "away": None}, "minute": None, "period": None})

    def _rr(self, cid, season, teams, start, every, off):
        n, order, rounds = len(teams), teams[:], []
        for _ in range(n - 1):
            rounds.append([(order[i], order[n - 1 - i]) for i in range(n // 2)])
            order = [order[0]] + [order[-1]] + order[1:-1]
        rounds += [[(b, a) for a, b in r] for r in rounds]
        for r, pairs in enumerate(rounds):
            base = start + timedelta(days=r * every, hours=off)
            for j, (h, a) in enumerate(pairs):
                self._add(cid, season, f"Round {r + 1}", int((base + timedelta(hours=12 + (j % 3) * 2)).timestamp()), h, a)

    def _cup(self, cid, season, teams, start, gap, label, rnd):
        teams = teams[:]
        for r in range(6):
            rnd.shuffle(teams)
            base = start + timedelta(days=r * gap)
            for j in range(0, len(teams) - 1, 2):
                self._add(cid, season, label.format(r + 1), int((base + timedelta(hours=(j // 2) % 3)).timestamp()),
                          teams[j], teams[j + 1])

    # ------------------------------------------------------------------ API surface
    def _team(self, tid):
        t = self.teams[tid]
        return {k: v for k, v in t.items() if not k.startswith("_")}

    def _out(self, m):
        o = {k: v for k, v in m.items() if not k.startswith("_")}
        o["homeTeam"], o["awayTeam"] = self._team(m["_h"]), self._team(m["_aw"])
        return o

    def get(self, path, **params):
        if self.used >= self.limit:
            raise self.BudgetExhausted()
        remaining = self.quota_left0 - self.used
        if remaining <= 0:
            raise self.BudgetExhausted()
        self.used += 1
        self.calls.append((path, params))
        if path == "competitions":
            items = list(self.comps.values())
        elif path == "matches":
            items = self.matches
            if "date" in params:
                items = [m for m in items if m["kickoffAt"][:10] == params["date"]]
            if "competition" in params:
                items = [m for m in items if m["competitionId"] == params["competition"]]
            if "season" in params:
                items = [m for m in items if m["season"] == params["season"]]
            if "status" in params:
                items = [m for m in items if m["status"] == params["status"]]
            items = sorted(items, key=lambda m: m["_ts"])
            items = [self._out(m) for m in items]
        else:
            raise self.ApiError(f"mock: unknown path {path}")
        off = 0
        if params.get("cursor"):
            off = int(base64.b64decode(params["cursor"]).decode().split(":")[1])
        page = items[off:off + 50]
        nxt = base64.b64encode(f"offset:{off + 50}".encode()).decode() if off + 50 < len(items) else None
        self.quota_remaining = self.quota_left0 - self.used
        if self.budget_rule and not self._budget_set:
            self.limit = self.used + max(0, self.budget_rule(self.quota_remaining))
            self._budget_set = True
        return {"data": page, "meta": {"count": len(page), "total_count": len(items),
                                       "pagination": {"limit": 50, "next_cursor": nxt},
                                       "access": {"plan": "starter", "quota": 5000, "used": 5000 - self.quota_remaining,
                                                  "remaining": self.quota_remaining}}}
