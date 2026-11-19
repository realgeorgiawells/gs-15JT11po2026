"""One-off check: for every competition with an OpenFootAPI id, does OpenFootAPI list upcoming games, results, or both?"""
import json, os, re, urllib.parse, urllib.request
KEY = os.environ["OPENFOOT_API_KEY"].strip()
comps = [c for c in json.load(open("config/competitions.json"))["competitions"] if c.get("openfoot_id")]
known = json.load(open("data/archive/meta.json")).get("seasons", {})
CAL = {"sweden", "ireland", "usa", "japan", "brazil", "argentina", "norway", "finland", "south korea", "korea republic",
       "colombia", "uruguay", "uzbekistan", "china", "chile", "peru", "paraguay", "ecuador", "iceland", "estonia", "lithuania"}

def get(**p):
    url = "https://openfootapi.com/v1/matches?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": e.code, "data": [], "meta": {}}

def seasons_for(c):
    cid = c["openfoot_id"]
    out = [known[cid]] if cid in known else []
    for s in ("2026/27", "2026", "2025/26"):
        if s not in out:
            out.append(s)
    return out

for c in comps:
    cid = c["openfoot_id"]
    row = {"no": c["no"], "name": c["name"], "value": c["value"], "id": cid}
    d = get(competition=cid, status="scheduled")
    row["sched_any"] = d.get("meta", {}).get("total_count", len(d.get("data", []))) if "error" not in d else f"err{d['error']}"
    first = sorted(x.get("kickoffAt") or "" for x in d.get("data", []))
    row["next"] = first[0][:16] if first else None
    if not first:
        for s in seasons_for(c)[:2]:
            d = get(competition=cid, season=s, status="scheduled")
            k = sorted(x.get("kickoffAt") or "" for x in d.get("data", []))
            if k:
                row["next"], row["sched_season"], row["sched_any"] = k[0][:16], s, d.get("meta", {}).get("total_count")
                break
    for s in seasons_for(c)[:3]:
        d = get(competition=cid, season=s, status="finished")
        n = d.get("meta", {}).get("total_count", len(d.get("data", [])))
        if n:
            row["fin_season"], row["finished"] = s, n
            break
    else:
        row["finished"] = 0
    row["quota"] = d.get("meta", {}).get("access", {}).get("remaining")
    print("ROW " + json.dumps(row, ensure_ascii=False), flush=True)
