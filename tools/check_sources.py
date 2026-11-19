"""One-off check: can TheSportsDB or ESPN supply upcoming games for the leagues OpenFootAPI only has results for?"""
import json, re, unicodedata, urllib.request
from datetime import date, timedelta
from difflib import SequenceMatcher

LEAGUES = [  # OpenFootAPI id, name, ESPN slug, TheSportsDB country + name hint
    ("comp_scottish_prem_sco", "Scottish Premiership", "sco.1", "Scotland", "Premiership"),
    ("comp_primeira_liga_pt", "Primeira Liga", "por.1", "Portugal", "Primeira Liga"),
    ("comp_super_lig_tr", "Süper Lig", "tur.1", "Turkey", "Super Lig"),
    ("comp_pro_league_be", "Belgian Pro League", "bel.1", "Belgium", "Pro League"),
    ("comp_super_league_grc", "Greek Super League", "gre.1", "Greece", "Super League"),
    ("comp_brasileirao_bra", "Série A (Brazil)", "bra.1", "Brazil", "Serie A"),
    ("comp_liga_profesional_arg", "Liga Profesional (Argentina)", "arg.1", "Argentina", "Primera"),
    ("comp_superliga_dnk", "Danish Superliga", "den.1", "Denmark", "Superliga"),
    ("comp_bundesliga_aut", "Austrian Bundesliga", "aut.1", "Austria", "Bundesliga"),
    ("comp_liga_mx_mex", "Liga MX", "mex.1", "Mexico", "Liga MX"),
    ("comp_ekstraklasa_pol", "Ekstraklasa", "pol.1", "Poland", "Ekstraklasa"),
    ("comp_serie_b_it", "Serie B (Italy)", "ita.2", "Italy", "Serie B"),
    ("comp_segunda_es", "Segunda División", "esp.2", "Spain", "Segunda"),
    ("comp_ligue_2_fr", "Ligue 2", "fra.2", "France", "Ligue 2"),
    ("comp_segunda_liga_pt", "Liga Portugal 2", "por.2", "Portugal", "Segunda"),
    ("comp_ligapro_ecu", "LigaPro (Ecuador)", "ecu.1", "Ecuador", "Serie A"),
    ("comp_mls_usa", "MLS", "usa.1", "USA", "Major League Soccer"),
    ("comp_j1_league_jpn", "J-League (J1)", "jpn.1", "Japan", "J1"),
    ("comp_eliteserien_nor", "Eliteserien", "nor.1", "Norway", "Eliteserien"),
]
teams = json.load(open("data/archive/teams.json"))
arch = {}
import glob
for f in glob.glob("data/archive/20*.json"):
    for r in json.load(open(f)).values():
        arch.setdefault(r[0], set()).update([r[3], r[4]])

def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(fc|cf|sc|ac|afc|cd|ca|club|de|sk|fk|if|bk|ff|sv|calcio|the)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def best(name, pool):
    n = norm(name)
    sc = sorted(((SequenceMatcher(None, n, norm(p)).ratio() + (0.3 if n and (n in norm(p) or norm(p) in n) else 0), p) for p in pool), reverse=True)
    return sc[0] if sc else (0, None)

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 goalscraper-check"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except Exception as e:
        return {"_error": str(e)[:120]}

today = date(2026, 11, 20)
span = f"{today:%Y%m%d}-{today + timedelta(days=4):%Y%m%d}"
tsdb_leagues = {}
summary = []
for ofid, name, espn, country, hint in LEAGUES:
    pool = {teams[t][0] for t in teams if teams[t][1] == ofid and teams[t][0]} | arch.get(ofid, set())
    out = {"league": name, "openfoot_teams_known": len(pool)}
    # ---- ESPN
    d = get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{espn}/scoreboard?dates={span}")
    if "_error" in d:
        out["espn"] = d["_error"]
    else:
        evs = d.get("events", [])
        names, rows = [], []
        for e in evs:
            cs = (e.get("competitions") or [{}])[0].get("competitors", [])
            h = next((c["team"]["displayName"] for c in cs if c.get("homeAway") == "home"), "?")
            a = next((c["team"]["displayName"] for c in cs if c.get("homeAway") == "away"), "?")
            rows.append(f'{e.get("date", "")[:16]} {h} v {a}')
            names += [h, a]
        matched = [(n, best(n, pool)) for n in names]
        good = sum(1 for n, (s, p) in matched if s >= 0.75)
        out["espn"] = {"games_next_5_days": len(evs), "sample": rows[:3],
                       "names_matched": f"{good}/{len(names)}" if pool else "no OpenFootAPI teams known yet",
                       "unmatched": [f"{n} ~ {p} ({s:.2f})" for n, (s, p) in matched if s < 0.75][:4]}
    # ---- TheSportsDB (free key 123)
    if country not in tsdb_leagues:
        tsdb_leagues[country] = get(f"https://www.thesportsdb.com/api/v1/json/123/search_all_leagues.php?c={urllib.request.quote(country)}&s=Soccer")
    lg = [l for l in (tsdb_leagues[country].get("countries") or tsdb_leagues[country].get("countrys") or []) if l]
    cand = sorted(lg, key=lambda l: -SequenceMatcher(None, norm(hint), norm(l.get("strLeague"))).ratio())
    if not cand:
        out["thesportsdb"] = tsdb_leagues[country].get("_error", "league not found")
    else:
        L = cand[0]
        nx = get(f"https://www.thesportsdb.com/api/v1/json/123/eventsnextleague.php?id={L['idLeague']}")
        evs = [e for e in (nx.get("events") or []) if e]
        day_counts = {}
        for k in range(5):
            dd = today + timedelta(days=k)
            de = get(f"https://www.thesportsdb.com/api/v1/json/123/eventsday.php?d={dd}&l={L['idLeague']}")
            day_counts[str(dd)] = len([e for e in (de.get("events") or []) if e]) if "_error" not in de else de["_error"][:40]
        out["thesportsdb"] = {"league": f"{L['strLeague']} ({L['idLeague']})", "next_events_returned": len(evs),
                              "sample": [f'{e.get("strTimestamp") or e.get("dateEvent")} {e.get("strHomeTeam")} v {e.get("strAwayTeam")}' for e in evs[:3]],
                              "by_day": day_counts}
    summary.append(out)
    print("RESULT " + json.dumps(out, ensure_ascii=False), flush=True)
