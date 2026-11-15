#!/usr/bin/env python3
"""apply_overrides.py <in_gu.json> <out_gu.json> <override.json> [...]
Apply override files ({ref: [x, y, absolute rot]}, keys starting with '_' ignored) in the order given (later wins).
Every ref must already exist in the placement. Prints one line per file with the refs it changed."""
import json, sys
P = json.load(open(sys.argv[1]))
for o in sys.argv[3:]:
    ch = []
    for r, v in json.load(open(o)).items():
        if r.startswith('_'): continue
        if r not in P: sys.exit(f'{o}: unknown ref {r}')
        if list(P[r]) != list(v): ch.append(r)
        P[r] = list(v)
    print(f'override {o.split("/")[-1]}: {len(ch)} refs changed {" ".join(ch)}')
json.dump(P, open(sys.argv[2], 'w'), indent=0)
