"""split_zones.py <spec.json> [<spec.json out>]   (out defaults to in place)
One zone per outline. KiCad keeps only the first outline of a multi-outline zone when a board is saved again,
so the router's zone refill dropped most power pours (fix from team D, hr.py)."""
import sys, json
src = sys.argv[1]; dst = sys.argv[2] if len(sys.argv) > 2 else src
S = json.load(open(src)); n0 = len(S["zones"])
S["zones"] = [dict(z, polys=[p]) for z in S["zones"] for p in z["polys"]]
json.dump(S, open(dst, "w"))
print(f"split_zones: {n0} zones -> {len(S['zones'])} (one outline each)")
