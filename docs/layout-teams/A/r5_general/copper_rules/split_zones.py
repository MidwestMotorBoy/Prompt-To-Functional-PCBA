#!/usr/bin/env python3
"""split_zones.py <spec.json> [out.json]: one zone per outline (in place if no out path).

Why: tools/copper/write_copper.py writes one KiCad zone per net and layer holding every outline the plan has for it.
KiCad keeps only the FIRST outline of such a zone when the board is saved again (router.py refills and saves), so most
power pours vanish on a routed board and route counts are flattered (team A round 1: a 10 A bus pour on F.Cu 8 outlines -> 1,
return net F.Cu 17 -> 1). Splitting before write_copper keeps every pour. Same output as docs/layout-teams/A/tools/
split_spec.py (it is that file, made importable). The one-line upstream fix in write_copper.py is in upstream.diff:
create a new ZONE per outline (move `zn = pcbnew.ZONE(b) ...` inside the `for p in z["polys"]` loop)."""
import sys, json


def split(s):
    out = []
    for z in s["zones"]:
        for p in z["polys"]:
            y = dict(z); y["polys"] = [p]; out.append(y)
    n0 = len(s["zones"]); s["zones"] = out
    return n0, len(out)


if __name__ == "__main__":
    s = json.load(open(sys.argv[1])); n0, n1 = split(s)
    json.dump(s, open(sys.argv[2] if len(sys.argv) > 2 else sys.argv[1], "w"))
    print(f"split_spec: {n0} zones -> {n1} single-outline zones")
