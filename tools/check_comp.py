import json, re
from collections import defaultdict, Counter
s = json.load(open("data/store.json")); T = s["teams"]; M = s["matches"]
suf = Counter(k.rsplit("_", 1)[-1] for k in T)
print("TEAMS suffixes", suf.most_common(40))
base = defaultdict(list)
for k, v in T.items():
    b = k.rsplit("_", 1)[0]
    base[b].append((k, v))
eur = [k for k in T if k.endswith("_eur")]
ok = amb = none = 0
ex = []
for k in eur:
    b = k.rsplit("_", 1)[0]
    c = [x for x, v in base[b] if not x.endswith(("_eur",)) and x != k]
    ctry = T[k][2]
    c2 = [x for x in c if T[x][2] == ctry] if len(c) > 1 else c
    if len(c2) == 1: ok += 1
    elif len(c2) > 1: amb += 1; ex.append((k, T[k], [(x, T[x]) for x in c2]))
    else: none += 1; ex.append((k, T[k], "none"))
print("TEAMS eur", len(eur), "match", ok, "ambiguous", amb, "none", none)
for e in ex[:25]: print("TEAMS ", e)
print("TEAMS sample", [(k, T[k]) for k in ("team_barcelona_eur", "team_barcelona_es", "team_sabah_eur") if k in T])
print("TEAMS sabah", [(k, v) for k, v in T.items() if "sabah" in k])
