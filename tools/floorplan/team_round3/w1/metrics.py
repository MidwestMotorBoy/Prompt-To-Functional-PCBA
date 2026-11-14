"""metrics.py <dump.json> <fill placement.json | -> [clusters.json]
Signal half-perimeter (same nets as place_pack: non-power, >= 2 pads), IC crowd counts (parts with a pad within
2.5 mm of the IC's pad box) and the number of 2- and 3-pad signal nets with half-perimeter over 10 mm.
'-' as placement scores the dump as it is (e.g. the hand board dump)."""
import json, sys
from collections import defaultdict

ICS = ["U403", "U503", "U401", "U501", "U102", "U301"]
HAND = dict(U403=26, U503=23, U401=15, U501=15, U102=13, U301=18)

def rot(x, y, k):
    for _ in range(k % 4): x, y = -y, x
    return x, y

def pads_at(d, P):
    pos0 = {f["ref"]: (f["x"], f["y"]) for f in d["fps"]}; out = []
    for p in d["pads"]:
        r = p["ref"]
        if r in P:
            x, y, a = P[r]; k = int(a) // 90; x0, y0 = pos0[r]
            dx, dy = rot(p["x"] - x0, p["y"] - y0, k); bx = [rot(p["box"][0] - x0, p["box"][1] - y0, k), rot(p["box"][2] - x0, p["box"][3] - y0, k)]
            out.append(dict(ref=r, net=p["net"], x=x + dx, y=y + dy, box=[x + min(bx[0][0], bx[1][0]), y + min(bx[0][1], bx[1][1]), x + max(bx[0][0], bx[1][0]), y + max(bx[0][1], bx[1][1])]))
        else:
            out.append(dict(ref=r, net=p["net"], x=p["x"], y=p["y"], box=p["box"]))
    return out

def metrics(d, P):
    pads = pads_at(d, P); nets = defaultdict(list)
    for p in pads:
        if p["net"]: nets[p["net"]].append(p)
    power = {n for n, ps in nets.items() if len(ps) >= 12}
    hp = 0.0; long23 = []
    for n, ps in nets.items():
        if n in power or len(ps) < 2: continue
        h = max(p["x"] for p in ps) - min(p["x"] for p in ps) + max(p["y"] for p in ps) - min(p["y"] for p in ps); hp += h
        if len(ps) <= 3 and h > 10: long23.append((round(h, 1), n))
    crowd = {}
    for ic in ICS:
        mine = [p for p in pads if p["ref"] == ic]
        if not mine: continue
        B = [min(p["box"][0] for p in mine), min(p["box"][1] for p in mine), max(p["box"][2] for p in mine), max(p["box"][3] for p in mine)]
        s = set()
        for p in pads:
            if p["ref"] == ic: continue
            dx = max(B[0] - p["box"][2], p["box"][0] - B[2], 0); dy = max(B[1] - p["box"][3], p["box"][1] - B[3], 0)
            if (dx * dx + dy * dy) ** 0.5 <= 2.5: s.add(p["ref"])
        crowd[ic] = len(s)
    return hp, crowd, sorted(long23, reverse=True)

if __name__ == "__main__":
    d = json.load(open(sys.argv[1])); P = {} if sys.argv[2] == "-" else json.load(open(sys.argv[2]))
    if len(sys.argv) > 3:
        fill = {r for v in json.load(open(sys.argv[3])).values() for r in v}; P = {r: v for r, v in P.items() if r in fill}
    hp, crowd, l23 = metrics(d, P)
    print(f"signal_hp {hp:.0f} (q7s2 4100, hand 2064) | crowd " + " ".join(f"{k} {v}/{HAND[k]}" for k, v in crowd.items()) + f" | 2-3 pad nets > 10 mm: {len(l23)}")
    if "-v" in sys.argv[4:] or len(sys.argv) == 3: print("  longest:", l23[:12])
