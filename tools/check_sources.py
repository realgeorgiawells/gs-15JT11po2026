import json, time, urllib.request
def get(p):
    time.sleep(3)
    try:
        with urllib.request.urlopen(urllib.request.Request("https://www.thesportsdb.com/api/v1/json/123/" + p, headers={"User-Agent": "Goalscraper"}), timeout=40) as r:
            return json.load(r)
    except Exception as e:
        return {"_error": str(e)}
for d in ("2026-11-21", "2026-11-22", "2026-11-24"):
    ev = get(f"eventsday.php?d={d}&s=Soccer").get("events") or []
    print("DAY", d, len(ev), sorted({(e.get("idLeague"), e.get("strLeague")) for e in ev if "Eng" in (e.get("strLeague") or "") or "National" in (e.get("strLeague") or "")}))
for c in ("England",):
    d = get(f"search_all_leagues.php?c={c}&s=Soccer")
    print("LEAGUES", [(l["idLeague"], l["strLeague"]) for l in (d.get("countries") or d.get("countrys") or []) if l])
for lid in range(4620, 4640):
    L = (get(f"lookupleague.php?id={lid}").get("leagues") or [{}])[0]
    print("ID", lid, L.get("strLeague"), L.get("strCountry"))
