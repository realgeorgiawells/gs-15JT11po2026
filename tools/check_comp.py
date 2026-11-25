import json, os, urllib.parse, urllib.request
KEY = os.environ["OPENFOOT_API_KEY"].strip()
def get(**p):
    req = urllib.request.Request("https://openfootapi.com/v1/matches?" + urllib.parse.urlencode(p), headers={"Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
for cid, season in (("comp_laliga_es", "2026/27"), ("comp_laliga_es", "2025/26"), ("comp_premier_league_eng", "2026/27")):
    d = get(competition=cid, season=season, status="finished")
    ks = sorted(x.get("kickoffAt") or "" for x in d.get("data", []))
    ids = {x["id"].split("_")[1] for x in d.get("data", [])}
    print("CHECK", cid, season, "total", d["meta"].get("total_count"), "first page", ks[:1], ks[-1:], "feeds", ids, "next", bool(d["meta"].get("pagination", {}).get("next_cursor")), "left", d["meta"].get("access", {}).get("remaining"))
