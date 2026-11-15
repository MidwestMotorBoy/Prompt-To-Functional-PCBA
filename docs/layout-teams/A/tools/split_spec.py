#!/usr/bin/env python3
"""split_spec.py <spec.json> [out.json]: one zone per outline.
KiCad keeps only the first outline of a multi-outline zone when a board is re-saved (found by team D), so
write_copper.py's one-zone-per-net-and-layer pours lose most outlines when the router refills and saves.
Splitting before write_copper keeps every pour. Writes in place if no out path."""
import json, sys
s = json.load(open(sys.argv[1])); out = []
for z in s["zones"]:
    for p in z["polys"]:
        y = dict(z); y["polys"] = [p]; out.append(y)
n0 = len(s["zones"]); s["zones"] = out
json.dump(s, open(sys.argv[2] if len(sys.argv) > 2 else sys.argv[1], "w"))
print(f"split_spec: {n0} zones -> {len(out)} single-outline zones")
