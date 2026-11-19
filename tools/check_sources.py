"""One-off check: what TheSportsDB (free key) has for the competitions OpenFootAPI doesn't cover."""
import json, re, time, urllib.request
from datetime import datetime, timezone

WANT = [  # no, our name, regex for TheSportsDB league name, country filter (or None)
    (21, "League of Ireland First Division", r"irish.*first|ireland.*first|league of ireland first", "Ireland"),
    (42, "World Cup qualifiers", r"world cup qualif", None),
    (43, "European Championship finals", r"^uefa european championship$|^uefa euro", None),
    (44, "Euro qualifiers", r"euro.*qualif|european championship qualif", None),
    (46, "Copa America", r"^copa am[eé]rica$", None),
    (47, "Women's World Cup", r"women.*world cup$", None),
    (49, "Women's Euro finals", r"women.*euro(pean championship)?$", None),
    (5, "National League (England)", r"national league$|english national league", "England"),
    (31, "Women's Champions League", r"women.*champions league", None),
    (25, "Women's Super League", r"women.*super league|wsl", "England"),
    (26, "LOI Women's Premier Division", r"women", "Ireland"),
    (32, "Women's Europa Cup", r"women.*europa", None),
    (52, "Women's Copa America", r"women.*copa am", None),
    (48, "Women's World Cup qualifiers", r"women.*world cup qualif", None),
    (50, "Women's Euro qualifiers", r"women.*euro.*qualif", None),
    (51, "Women's Nations League", r"women.*nations league", None),
    (39, "AFC Champions League Two", r"afc champions league two|afc cup", None),
    (7, "Scottish Championship", r"scottish championship", "Scotland"),
    (8, "Scottish League One", r"scottish league one", "Scotland"),
    (9, "Scottish League Two", r"scottish league two", "Scotland"),
    (36, "CAF Champions League", r"caf champions league", None),
    (37, "CAF Confederation Cup", r"caf confederation", None),
    (40, "OFC Champions League", r"ofc champions league", None),
]

def get(path):
    time.sleep(2.6)
    url = "https://www.thesportsdb.com/api/v1/json/123/" + path
    for _ in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "goalscraper-check"}), timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(25); continue
            return {"_error": f"HTTP {e.code}"}
        except Exception as e:
            return {"_error": str(e)[:80]}
    return {"_error": "rate limited"}

allL = [l for l in (get("all_leagues.php").get("leagues") or []) if l.get("strSport") == "Soccer"]
print("soccer leagues in TheSportsDB list:", len(allL))
by_country = {}
now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
for no, name, rx, country in WANT:
    pool = allL
    if country:
        if country not in by_country:
            d = get(f"search_all_leagues.php?c={country}&s=Soccer")
            by_country[country] = [l for l in (d.get("countries") or d.get("countrys") or []) if l]
        pool = by_country[country] + allL
    cands, seen = [], set()
    for l in pool:
        if re.search(rx, l.get("strLeague", ""), re.I) and l["idLeague"] not in seen:
            seen.add(l["idLeague"]); cands.append(l)
    out = {"no": no, "name": name, "candidates": [f'{l["idLeague"]} {l["strLeague"]}' for l in cands[:5]]}
    if cands:
        L = (get(f'lookupleague.php?id={cands[0]["idLeague"]}').get("leagues") or [{}])[0]
        season = L.get("strCurrentSeason")
        out["league"] = f'{cands[0]["idLeague"]} {L.get("strLeague")} current season {season}'
        if season:
            ev = [e for e in (get(f'eventsseason.php?id={cands[0]["idLeague"]}&s={season}').get("events") or []) if e]
            played = [e for e in ev if e.get("intHomeScore") not in (None, "")]
            upcoming = sorted((e for e in ev if (e.get("dateEvent") or "") >= now and e.get("intHomeScore") in (None, "")), key=lambda e: e.get("strTimestamp") or e.get("dateEvent") or "")
            out.update({"season_events_returned": len(ev), "with_scores": len(played), "upcoming": len(upcoming),
                        "next": [f'{e.get("strTimestamp") or e.get("dateEvent")} {e.get("strHomeTeam")} v {e.get("strAwayTeam")}' for e in upcoming[:2]],
                        "last_result": max((e.get("dateEvent") or "") for e in played) if played else None})
            m = re.match(r"(\d{4})(?:-(\d{4}))?$", season)
            if m:
                prev = f"{int(m.group(1)) - 1}-{int(m.group(1))}" if m.group(2) else str(int(m.group(1)) - 1)
                pe = [e for e in (get(f'eventsseason.php?id={cands[0]["idLeague"]}&s={prev}').get("events") or []) if e]
                out["previous_season_events"] = f"{prev}: {len(pe)} ({sum(1 for e in pe if e.get('intHomeScore') not in (None, ''))} with scores)"
    print("RESULT " + json.dumps(out, ensure_ascii=False), flush=True)
