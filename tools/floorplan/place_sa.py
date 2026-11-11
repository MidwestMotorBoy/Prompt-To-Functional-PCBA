"""place_sa.py <intent.json> <board dump.json> <netlist.json> <constraints.json> <out placement.json> [moves] [seed]
Generic placer for the floorplan stage: simulated annealing of every part that is not fixed, inside its region
from the intent file, on its own side. Cost = half-perimeter of every net with fewer than 12 pads (pad level)
+ a spring from each part to the pin it serves (constraints "serves") + a penalty for overlapping bodies.
Bodies are the box round a part's pads plus 0.25 mm. Start is random inside the region, so the result owes
nothing to the positions in the dump; the dump only supplies pad geometry.
This is an experiment: it knows nothing about hot loops, heat, keep-outs inside a region, or assembly rules."""
import json, sys, math, random
from collections import defaultdict
import floorplan as F

def main(intentf, dumpf, netf, consf, outf, moves=400000, seed=1):
    rnd = random.Random(int(seed)); moves = int(moves)
    comps = json.load(open(netf))["comps"]; cons = json.load(open(consf))
    F.SECTIONS = {r: f"{v['block']} / {v.get('section') or 'main'}" for r, v in comps.items()}
    it = json.load(open(intentf)); d, pos0, side, blk, pads0 = F.load(dumpf)
    reg = {(b, r["side"]): r["box"] for b, rs in it["blocks"].items() for r in rs}
    # local geometry per part: pad offsets and body half-sizes, in the dump's orientation
    lp = defaultdict(list); bb = {}
    for p in d["pads"]:
        x0, y0 = pos0[p["ref"]]; lp[p["ref"]].append((p["x"] - x0, p["y"] - y0, p["net"], p["num"]))
        b = bb.setdefault(p["ref"], [1e9, 1e9, -1e9, -1e9]); bx = p["box"]
        b[0] = min(b[0], bx[0] - x0); b[1] = min(b[1], bx[1] - y0); b[2] = max(b[2], bx[2] - x0); b[3] = max(b[3], bx[3] - y0)
    refs = [r for r in pos0 if r in bb]; M = 0.25
    def rot(v, k):
        x, y = v
        for _ in range(k): x, y = -y, x
        return x, y
    def body(r, k):
        b = bb[r]; cs = [rot((b[0], b[1]), k), rot((b[2], b[3]), k)]
        return min(c[0] for c in cs) - M, min(c[1] for c in cs) - M, max(c[0] for c in cs) + M, max(c[1] for c in cs) + M
    fixed = {r for r in refs if r in it["fixed"] or (blk[r], side[r]) not in reg}
    P = {}
    for r in refs:
        if r in fixed: P[r] = (pos0[r][0], pos0[r][1], 0); continue
        g = reg[(blk[r], side[r])]; P[r] = (rnd.uniform(g[0] + 1, g[2] - 1), rnd.uniform(g[1] + 1, g[3] - 1), rnd.randrange(4))
    netpads = defaultdict(list)
    for r in refs:
        for i, (lx, ly, n, num) in enumerate(lp[r]):
            if n: netpads[n].append((r, i))
    nets = {n: ps for n, ps in netpads.items() if 2 <= len(ps) < 12}; nets_of = defaultdict(set)
    for n, ps in nets.items():
        for r, _ in ps: nets_of[r].add(n)
    def padxy(r, i, p=None):
        x, y, k = p or P[r]; dx, dy = rot(lp[r][i][:2], k); return x + dx, y + dy
    def hp(n, sub=None):
        xs = []; ys = []
        for r, i in nets[n]:
            x, y = padxy(r, i, sub[1] if sub and sub[0] == r else None); xs.append(x); ys.append(y)
        return max(xs) - min(xs) + max(ys) - min(ys)
    pinidx = {(r, num): i for r in refs for i, (_, _, _, num) in enumerate(lp[r])}
    serves = {}
    for c, t in cons.get("serves", {}).items():
        tr, tp = t.split(".", 1)
        cand = [i for i, (_, _, _, num) in enumerate(lp.get(tr, [])) if num == tp]
        if not cand and tr in comps:      # pin given by name: fall back to the part's centre
            cand = [None]
        if c in P and tr in P and cand: serves[c] = (tr, cand[0])
    def spring(c, p=None, other=None):
        tr, i = serves[c]; q = other if other is not None else P[tr]
        tx, ty = padxy(tr, i, q) if i is not None else (q[0], q[1]); x, y, _ = p or P[c]
        return abs(x - tx) + abs(y - ty)
    served_by = defaultdict(list)
    for c, (tr, _) in serves.items(): served_by[tr].append(c)
    byside = defaultdict(list)
    for r in refs: byside[side[r]].append(r)
    def overlap(r, p):
        a = body(r, p[2]); A = (a[0] + p[0], a[1] + p[1], a[2] + p[0], a[3] + p[1]); s = 0.0
        for q in byside[side[r]]:
            if q == r: continue
            x, y, k = P[q]
            if abs(x - p[0]) > 12 or abs(y - p[1]) > 12: continue
            b = body(q, k); ox = min(A[2], b[2] + x) - max(A[0], b[0] + x)
            if ox <= 0: continue
            oy = min(A[3], b[3] + y) - max(A[1], b[1] + y)
            if oy > 0: s += ox * oy
        return s
    def inside(r, p):
        g = reg[(blk[r], side[r])]; a = body(r, p[2]); B = it["box"]
        return g[0] <= p[0] <= g[2] and g[1] <= p[1] <= g[3] and B[0] <= a[0] + p[0] and a[2] + p[0] <= B[2] and B[1] <= a[1] + p[1] and a[3] + p[1] <= B[3]
    WS, WO = 1.0, 40.0
    def local(r, p=None):
        c = sum(hp(n, (r, p) if p else None) for n in nets_of[r]) + WO * overlap(r, p or P[r])
        if r in serves: c += WS * spring(r, p)
        for s in served_by[r]: c += WS * spring(s, None, p)
        return c
    mov = [r for r in refs if r not in fixed]; T0, T1 = 3.0, 0.02
    for step in range(moves):
        T = T0 * (T1 / T0) ** (step / moves); r = rnd.choice(mov); x, y, k = P[r]; rad = 0.3 + 6 * T / T0
        if rnd.random() < 0.15: p = (x, y, rnd.randrange(4))
        else: p = (x + rnd.uniform(-rad, rad), y + rnd.uniform(-rad, rad), k)
        if not inside(r, p): continue
        dc = local(r, p) - local(r)
        if dc < 0 or rnd.random() < math.exp(-dc / T): P[r] = p
    tot = sum(hp(n) for n in nets); ov = sum(overlap(r, P[r]) for r in refs) / 2
    # the score's own definition, for comparison with floorplan.py
    power = F.power_nets(pads0, it); sig = sum(hp(n) for n in nets if n not in power)
    json.dump({r: [round(P[r][0], 3), round(P[r][1], 3), P[r][2] * 90] for r in refs}, open(outf, "w"))
    print(json.dumps(dict(parts=len(refs), moved=len(mov), nets=len(nets), half_perimeter_mm=round(tot), signal_half_perimeter_mm=round(sig), overlap_mm2=round(ov, 2),
                          serve_distance_mm=round(sum(spring(c) for c in serves)), served=len(serves))))

if __name__ == "__main__":
    main(*sys.argv[1:])
