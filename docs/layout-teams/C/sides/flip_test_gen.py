"""flip_test_gen.py <dump.json> <clusters.json> <outdir>: writes 4 test placements flip_q0..3.json. Each flips the same
32 parts (8 per template rotation 0/90/180/-90, a mix of 2-pad passives, diodes, SOT-23 and multi-pad ICs) to B, part i
turned by (i + run) % 4 quarter turns, so over the 4 files every part sees every turn. Positions stay at the template
origin (overlaps do not matter for this test). Also writes want_qN.json: the pad positions the placer convention gives
(origin + rotv(-lx, ly, q)), computed here from the dump without KiCad."""
import json, sys, collections
d = json.load(open(sys.argv[1])); cl = json.load(open(sys.argv[2])); out = sys.argv[3]
fill = {r for v in cl.values() for r in v}
pads = collections.defaultdict(list)
for p in d["pads"]: pads[p["ref"]].append(p)
by = collections.defaultdict(list)
for f in sorted(d["fps"], key=lambda f: f["ref"]):
    if f["ref"] in fill and f["side"] == "F.Cu": by[f["rot"]].append(f)
pick = []
for rot, fs in sorted(by.items()):
    small = [f for f in fs if len(pads[f["ref"]]) == 2][:5]; big = [f for f in fs if len(pads[f["ref"]]) >= 3][:3]
    pick += small + big
    if len(small) + len(big) < 8: pick += [f for f in fs if f not in small and f not in big][:8 - len(small) - len(big)]
def rotv(x, y, k):
    for _ in range(k % 4): x, y = -y, x
    return x, y
for run in range(4):
    P = {}; W = {}
    for i, f in enumerate(pick):
        q = (i + run) % 4; P[f["ref"]] = [f["x"], f["y"], 90 * q, "B"]
        W[f["ref"]] = [[p["num"], p["net"]] + list(map(lambda v: round(v, 4), (lambda o: (f["x"] + o[0], f["y"] + o[1]))(rotv(-(p["x"] - f["x"]), p["y"] - f["y"], q)))) for p in pads[f["ref"]]]
    json.dump(P, open(f"{out}/flip_q{run}.json", "w")); json.dump(W, open(f"{out}/want_q{run}.json", "w"))
print(len(pick), "parts:", " ".join(f"{f['ref']}({f['rot']:.0f},{len(pads[f['ref']])}p)" for f in pick))
