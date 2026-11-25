import json, datetime as dt
from collections import Counter
s = json.load(open("data/store.json"))
m = s["matches"]
print("STORE matches", len(m), "backfilled", len(s["backfilled"]))
bar = sorted((v for v in m.values() if any("barcelona" in str(x).lower() for x in (v[3], v[4]))), key=lambda v: v[2])
print("STORE barca", len(bar))
for v in bar: print("STORE  ", dt.datetime.fromtimestamp(v[2], dt.timezone.utc).date(), v[0], v[1], v[3], v[5], v[6], v[4], v[7])
c = Counter((v[0], v[1]) for v in m.values() if v[0] in ("comp_laliga_es", "comp_premier_league_eng", "comp_serie_a_it"))
print("STORE counts", c)
print("STORE laliga backfill", {k: v for k, v in s["backfilled"].items() if "laliga" in k})
