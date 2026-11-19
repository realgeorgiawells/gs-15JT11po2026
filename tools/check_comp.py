"""One-off check: what OpenFootAPI has for one competition. Usage: python tools/check_comp.py comp_id season"""
import json, os, sys, urllib.parse, urllib.request
cid, season = sys.argv[1], sys.argv[2]
KEY = os.environ["OPENFOOT_API_KEY"].strip()

def get(**p):
    url = "https://openfootapi.com/v1/matches?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:300]}

def show(title, d):
    print(f"\n=== {title}")
    if "error" in d:
        print("  error", d); return
    m = d.get("meta", {})
    print(f"  total_count={m.get('total_count')} on this page={len(d.get('data', []))} remaining quota={m.get('access', {}).get('remaining')}")
    for x in sorted(d.get("data", []), key=lambda x: x.get("kickoffAt") or ""):
        s = x.get("score") or {}
        print(f"  {x.get('kickoffAt')}  {x.get('status'):10} {(x.get('homeTeam') or {}).get('name')} {s.get('home')}-{s.get('away')} {(x.get('awayTeam') or {}).get('name')}  [{x.get('round')}] {x.get('id')}")

show("scheduled (not yet played)", get(competition=cid, season=season, status="scheduled"))
show("finished (first page)", get(competition=cid, season=season, status="finished"))
show("18 Nov, this competition", get(competition=cid, date="2026-11-18"))
