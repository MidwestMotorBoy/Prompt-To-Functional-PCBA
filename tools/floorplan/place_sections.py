"""place_sections.py <board dump.json> <netlist.json> <constraints.json> <out clusters.json> [fixed ref prefixes, default J,H,TP,SW] [intent.json]
Step 1 of the section placer: build each (section, side) group as a tight cluster on its own, in local
coordinates, with no knowledge of where the parts sit on the dump board (the dump supplies pad geometry only).
Order: the part with the most pads first, then always the unplaced part most connected to what is placed.
Each part goes to the spot and rotation (0.25 mm search grid, four rotations) with the least wiring to the pads
already placed, with a strong pull from a decoupling capacitor to the pin it serves, and no body overlap.
Prints, per group and in total, the wiring inside the group and the box area, next to the same numbers taken
from the dump board, so a hand placement and this placer can be compared group by group.
With an intent file (intent.py), its `near` statements are the pulls, in place of the plain serves list.
Fixed parts (connectors, holes, test points) are left out: they stay where the board has them."""
import json, sys, math
from collections import defaultdict
import floorplan as F

GAP = 0.05     # clearance between bodies, mm (bodies are courtyards when the dump has them, else pad boxes)

def rot(v, k):
    x, y = v
    for _ in range(k): x, y = -y, x
    return x, y

def main(dumpf, netf, consf, outf, fixed_prefixes="J,H,TP,SW", intentf=None):
    pre = tuple(fixed_prefixes.split(","))
    comps = json.load(open(netf))["comps"]; cons = json.load(open(consf))
    F.SECTIONS = {r: f"{v['block']} / {v.get('section') or 'main'}" for r, v in comps.items()}
    d, pos0, side, blk, pads0 = F.load(dumpf); power = F.power_nets(pads0)
    lp = defaultdict(list); bb = {}
    for p in d["pads"]:
        x0, y0 = pos0[p["ref"]]; lp[p["ref"]].append((p["x"] - x0, p["y"] - y0, p["net"], p["num"]))
        b = bb.setdefault(p["ref"], [1e9, 1e9, -1e9, -1e9]); bx = p["box"]
        b[0] = min(b[0], bx[0] - x0); b[1] = min(b[1], bx[1] - y0); b[2] = max(b[2], bx[2] - x0); b[3] = max(b[3], bx[3] - y0)
    for f in d["fps"]:                    # courtyards, where the dump has them, are the bodies
        if "court" in f and f["ref"] in bb:
            c = f["court"]; b = bb[f["ref"]]; bb[f["ref"]] = [min(b[0], c[0] - f["x"]), min(b[1], c[1] - f["y"]), max(b[2], c[2] - f["x"]), max(b[3], c[3] - f["y"])]
    def body(r, k):
        b = bb[r]; cs = [rot((b[0], b[1]), k), rot((b[2], b[3]), k)]
        return min(c[0] for c in cs), min(c[1] for c in cs), max(c[0] for c in cs), max(c[1] for c in cs)
    serves = {}
    for c, t in cons.get("serves", {}).items():
        tr, tp = t.split(".", 1); serves[c] = (tr, tp)
    near = defaultdict(list)             # part -> [(target part, pad number or None, weight)]
    if intentf:
        for st in json.load(open(intentf)).get("near", []):
            for t in st["to"]:
                tr, _, tp = t.partition("."); near[st["part"]].append((tr, tp or None, 8.0 if st["max_mm"] <= 2.0 else 4.0))
    else:
        for c, (tr, tp) in serves.items(): near[c].append((tr, tp, 4.0))
    groups = defaultdict(list)
    for r in pos0:
        if r in bb and r.rstrip("0123456789").upper() not in pre: groups[(blk[r], side[r])].append(r)
    def inner_nets(rs):
        s = set(rs); nets = defaultdict(list)
        for r in rs:
            for i, (_, _, n, _) in enumerate(lp[r]):
                if n and n not in power: nets[n].append((r, i))
        allp = defaultdict(set)
        for n, ps in pads0.items():
            for p in ps: allp[n].add(p[2])
        return {n: ps for n, ps in nets.items() if len(ps) >= 2}, {n for n in nets if allp[n] <= s}
    def hpwl(nets, P, only=None):
        t = 0.0
        for n, ps in nets.items():
            if only is not None and n not in only: continue
            q = [(P[r][0] + rot(lp[r][i][:2], P[r][2])[0], P[r][1] + rot(lp[r][i][:2], P[r][2])[1]) for r, i in ps if r in P]
            if len(q) > 1: t += max(a for a, _ in q) - min(a for a, _ in q) + max(b for _, b in q) - min(b for _, b in q)
        return t
    def area(P):
        xs = []; ys = []
        for r, (x, y, k) in P.items():
            b = body(r, k); xs += [x + b[0], x + b[2]]; ys += [y + b[1], y + b[3]]
        return (max(xs) - min(xs)) * (max(ys) - min(ys))
    out = {}; tot = dict(new_wire=0, ref_wire=0, new_area=0, ref_area=0, new_serve=0, ref_serve=0, served=0)
    print("| Section (side) | Parts | Wiring inside: placer / board, mm | Box area: placer / board, mm2 |\n|---|---|---|---|")
    for g, rs in sorted(groups.items()):
        nets, closed = inner_nets(rs)
        conn = defaultdict(lambda: defaultdict(int))
        for n, ps in nets.items():
            rr = sorted({r for r, _ in ps})
            for a in rr:
                for b in rr:
                    if a != b: conn[a][b] += 1
        for c, ts in near.items():
            for tr, _, _ in ts:
                if c in rs and tr in rs: conn[c][tr] += 5; conn[tr][c] += 5
        order = [max(rs, key=lambda r: (len(lp[r]), r))]; left = set(rs) - set(order)
        while left:
            nxt = max(left, key=lambda r: (sum(conn[r][q] for q in order), len(lp[r]), r)); order.append(nxt); left.remove(nxt)
        P = {order[0]: (0.0, 0.0, 0)}
        def pinxy(tr, tp):
            for lx, ly, _, num in lp[tr]:
                if num == tp: dx, dy = rot((lx, ly), P[tr][2]); return P[tr][0] + dx, P[tr][1] + dy
            return P[tr][0], P[tr][1]
        for r in order[1:]:
            # targets: pads of placed parts on this part's nets, and the served pin
            tg = []
            for i, (lx, ly, n, _) in enumerate(lp[r]):
                if n in nets:
                    for q, j in nets[n]:
                        if q in P and q != r: dx, dy = rot(lp[q][j][:2], P[q][2]); tg.append((i, P[q][0] + dx, P[q][1] + dy, 1.0))
            for tr, tp, w in near.get(r, []):
                if tr in P: sx, sy = pinxy(tr, tp); tg.append((None, sx, sy, w))
            placed = [(P[q][0] + body(q, P[q][2])[0] - GAP, P[q][1] + body(q, P[q][2])[1] - GAP, P[q][0] + body(q, P[q][2])[2] + GAP, P[q][1] + body(q, P[q][2])[3] + GAP) for q in P]
            X0 = min(b[0] for b in placed) - 6; X1 = max(b[2] for b in placed) + 6; Y0 = min(b[1] for b in placed) - 6; Y1 = max(b[3] for b in placed) + 6
            cx = sum(b[0] + b[2] for b in placed) / 2 / len(placed); cy = sum(b[1] + b[3] for b in placed) / 2 / len(placed)
            best = None; st = 0.25
            for k in range(4):
                b = body(r, k); lpk = [rot(v[:2], k) for v in lp[r]]
                y = Y0
                while y <= Y1:
                    x = X0
                    while x <= X1:
                        A = (x + b[0], y + b[1], x + b[2], y + b[3])
                        if not any(A[0] < q[2] and A[2] > q[0] and A[1] < q[3] and A[3] > q[1] for q in placed):
                            c = 0.0
                            for i, tx, ty, w in tg:
                                px, py = (x + lpk[i][0], y + lpk[i][1]) if i is not None else (x, y)
                                c += w * (abs(px - tx) + abs(py - ty))
                            c += 0.05 * (abs(x - cx) + abs(y - cy))            # weak pull to the cluster, breaks ties and handles parts with no target
                            if best is None or c < best[0]: best = (c, x, y, k)
                        x += st
                    y += st
            P[r] = (best[1], best[2], best[3])
        ref = {r: (pos0[r][0], pos0[r][1], 0) for r in rs}
        nw, rw, na, ra = hpwl(nets, P, closed), hpwl(nets, ref, closed), area(P), area(ref)
        for c, (tr, tp) in serves.items():
            if c in P and tr in P:
                tot["served"] += 1
                for name, Q in (("new_serve", P), ("ref_serve", ref)):
                    tx, ty = next(((Q[tr][0] + rot((lx, ly), Q[tr][2])[0], Q[tr][1] + rot((lx, ly), Q[tr][2])[1]) for lx, ly, _, num in lp[tr] if num == tp), (Q[tr][0], Q[tr][1]))
                    tot[name] += abs(Q[c][0] - tx) + abs(Q[c][1] - ty)
        tot["new_wire"] += nw; tot["ref_wire"] += rw; tot["new_area"] += na; tot["ref_area"] += ra
        if len(rs) > 1: print(f"| {g[0]} ({g[1][0]}) | {len(rs)} | {nw:.0f} / {rw:.0f} | {na:.0f} / {ra:.0f} |")
        out[f"{g[0]} | {g[1]}"] = {r: [round(P[r][0], 3), round(P[r][1], 3), P[r][2] * 90] for r in P}
    print(f"| **Total** | {sum(len(v) for v in out.values())} | {tot['new_wire']:.0f} / {tot['ref_wire']:.0f} | {tot['new_area']:.0f} / {tot['ref_area']:.0f} |")
    print(f"\nDecoupling: {tot['served']} served capacitors in the same group as their pin; summed distance to the pin: placer {tot['new_serve']:.0f} mm, board {tot['ref_serve']:.0f} mm")
    json.dump(out, open(outf, "w"))

if __name__ == "__main__":
    main(*sys.argv[1:])
