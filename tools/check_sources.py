"""One-off check: does TheSportsDB (free key) list upcoming games for the leagues OpenFootAPI only has results for?"""
import json, re, time, unicodedata, urllib.request, glob
from datetime import date, timedelta
from difflib import SequenceMatcher

LEAGUES = [  # OpenFootAPI id, name, TheSportsDB league id (checked by name below)
    ("comp_scottish_prem_sco", "Scottish Premiership", 4330), ("comp_primeira_liga_pt", "Primeira Liga", 4344),
    ("comp_super_lig_tr", "Süper Lig", 4339), ("comp_pro_league_be", "Belgian Pro League", 4338),
    ("comp_super_league_grc", "Greek Super League", 4336), ("comp_brasileirao_bra", "Série A (Brazil)", 4351),
    ("comp_liga_profesional_arg", "Liga Profesional (Argentina)", 4406), ("comp_superliga_dnk", "Danish Superliga", 4340),
    ("comp_bundesliga_aut", "Austrian Bundesliga", 4621), ("comp_liga_mx_mex", "Liga MX", 4350),
    ("comp_ekstraklasa_pol", "Ekstraklasa", 4422), ("comp_serie_b_it", "Serie B (Italy)", 4394),
    ("comp_segunda_es", "Segunda División", 4400), ("comp_ligue_2_fr", "Ligue 2", 4401),
    ("comp_segunda_liga_pt", "Liga Portugal 2", None), ("comp_ligapro_ecu", "LigaPro (Ecuador)", None),
    ("comp_mls_usa", "MLS", 4346), ("comp_j1_league_jpn", "J-League (J1)", 4633), ("comp_eliteserien_nor", "Eliteserien", 4358),
]
SEARCH = {"comp_segunda_liga_pt": ("Portugal", "Liga Portugal 2 Segunda"), "comp_ligapro_ecu": ("Ecuador", "Serie A LigaPro")}
teams = json.load(open("data/archive/teams.json"))
arch = {}
for f in glob.glob("data/archive/20*.json"):
    for r in json.load(open(f)).values():
        arch.setdefault(r[0], set()).update([r[3], r[4]])

def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(fc|cf|sc|ac|afc|cd|ca|club|de|sk|fk|if|bk|ff|sv|calcio|the|sad)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def best(name, pool):
    n = norm(name)
    sc = sorted(((SequenceMatcher(None, n, norm(p)).ratio() + (0.3 if n and (n in norm(p) or norm(p) in n) else 0), p) for p in pool), reverse=True)
    return sc[0] if sc else (0, None)

def get(path):
    time.sleep(2.5)
    url = "https://www.thesportsdb.com/api/v1/json/123/" + path
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "goalscraper-check"}), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(20); continue
            return {"_error": f"HTTP {e.code}"}
        except Exception as e:
            return {"_error": str(e)[:80]}
    return {"_error": "rate limited"}

today = date(2026, 11, 20)
for ofid, name, lid in LEAGUES:
    pool = {teams[t][0] for t in teams if teams[t][1] == ofid and teams[t][0]} | arch.get(ofid, set())
    out = {"league": name, "openfoot_teams_known": len(pool)}
    if lid is None:
        c, hint = SEARCH[ofid]
        d = get(f"search_all_leagues.php?c={c}&s=Soccer")
        ls = [l for l in (d.get("countries") or d.get("countrys") or []) if l]
        out["candidates"] = [f'{l["idLeague"]} {l["strLeague"]}' for l in ls][:8]
        ls.sort(key=lambda l: -SequenceMatcher(None, norm(hint), norm(l["strLeague"])).ratio())
        lid = ls[0]["idLeague"] if ls else None
    if lid:
        L = (get(f"lookupleague.php?id={lid}").get("leagues") or [{}])[0]
        out["tsdb_league"] = f'{lid} {L.get("strLeague")} ({L.get("strCountry")}) season {L.get("strCurrentSeason")}'
        rows, names = [], []
        for k in range(5):
            dd = today + timedelta(days=k)
            de = get(f"eventsday.php?d={dd}&l={lid}")
            if "_error" in de:
                rows.append(f"{dd}: {de['_error']}"); continue
            for e in (de.get("events") or []):
                rows.append(f'{e.get("strTimestamp") or e.get("dateEvent")} {e.get("strHomeTeam")} v {e.get("strAwayTeam")} [{e.get("strStatus")}]')
                names += [e.get("strHomeTeam"), e.get("strAwayTeam")]
        matched = [(n, best(n, pool)) for n in names]
        good = sum(1 for n, (s, p) in matched if s >= 0.75)
        out.update({"games_next_5_days": len(names) // 2, "sample": rows[:4],
                    "names_matched": f"{good}/{len(names)}" if pool else "no OpenFootAPI team names yet",
                    "unmatched": [f"{n} ~ {p} ({s:.2f})" for n, (s, p) in matched if s < 0.75][:5]})
    print("RESULT " + json.dumps(out, ensure_ascii=False), flush=True)
