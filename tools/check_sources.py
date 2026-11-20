import json, time, urllib.request, urllib.parse
def get(p):
    time.sleep(4)
    try:
        with urllib.request.urlopen(urllib.request.Request("https://www.thesportsdb.com/api/v1/json/123/" + p, headers={"User-Agent": "Goalscraper"}), timeout=40) as r:
            return json.load(r)
    except Exception as e:
        return {"_error": str(e)}
for t in ("Yeovil Town", "Southend United", "Forest Green Rovers"):
    d = get("searchteams.php?t=" + urllib.parse.quote(t))
    print("TEAM", t, [(x.get("idLeague"), x.get("strLeague"), x.get("idLeague2"), x.get("strLeague2")) for x in (d.get("teams") or [])][:3], d.get("_error", ""))
