"""hpwl.py <board_dump.json> [placement.json] [--boxes=<floorplan.json> --clusters=<clusters.json>]
Signal wiring estimate: half-perimeter of every net with 2 to 11 pads, at pad level (the floorplan README's measure).
  no placement          the dump board itself (the hand placement)
  placement.json        {ref: [x, y, quarter-turn degrees relative to the dump, optional "F"/"B"]}; other parts stay as dumped
  --boxes + --clusters  every part of a cluster at the centre of its box (fixed parts keep their pads): the box-centre reference
Prints the total, and the split into nets inside one sheet and nets between sheets."""
import sys, json
from collections import defaultdict
def rot(x, y, q):
    for _ in range(q % 4): x, y = -y, x
    return x, y
def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
    d = json.load(open(a[0])); fp = {f["ref"]: f for f in d["fps"]}; P = json.load(open(a[1])) if len(a) > 1 else {}
    cen = {}
    if "boxes" in opt:
        B = json.load(open(opt["boxes"]))["blocks"]; C = json.load(open(opt["clusters"]))
        for name, parts in C.items():
            b = B[name]
            for r in parts: cen[r] = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    nets = defaultdict(list)
    for p in d["pads"]:
        if not p["net"]: continue
        r = p["ref"]; f = fp[r]; x, y = p["x"], p["y"]
        if r in cen: x, y = cen[r]
        elif r in P:
            lx, ly = x - f["x"], y - f["y"]; v = P[r]
            if len(v) > 3 and str(v[3])[:1] in "FB" and str(v[3])[0] != f["side"][0]: lx = -lx
            lx, ly = rot(lx, ly, int(v[2]) // 90); x, y = v[0] + lx, v[1] + ly
        nets[p["net"]].append((x, y, f["sheet"]))
    tot = ins = btw = 0.0; n = 0
    for net, ps in nets.items():
        if not 2 <= len(ps) < 12: continue
        h = max(p[0] for p in ps) - min(p[0] for p in ps) + max(p[1] for p in ps) - min(p[1] for p in ps)
        tot += h; n += 1
        if len({p[2] for p in ps}) == 1: ins += h
        else: btw += h
    print(f"signal half-perimeter {tot:.0f} mm over {n} nets (inside one sheet {ins:.0f}, between sheets {btw:.0f})")
if __name__ == "__main__": main()
