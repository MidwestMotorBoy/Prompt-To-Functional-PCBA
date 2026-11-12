"""power_chains.py <board_dump.json> <constraints.json> <intent in.json> <intent out.json> [--min-a=1] [--check=<board_dump of a placement>]
Placement statements for the power paths, from the circuit code: the parts that carry a power net's current (its
series terminals, tools/copper/roles.py: connector, PD switch, FETs, fuse, inductor, shunt, an IC's power pins)
must sit close together, so the copper between them can be short and wide.

Why: the placer scores signal wiring and the hot loops, and leaves power nets out of the wiring sum. Nothing kept
a power path's parts together, so on Monolith seed 9 the Port 2 PD switch U501 landed 69 mm from its USB-C
connector J501 (19 mm on the hand board), and no copper can carry 5 A well over that.

For every power net of at least --min-a amps (except buses, BUS_TERMINALS series terminals or more): the series terminals carrying at least half the net's current, each
tied by a `near` statement to the one that carries the most (the source: the connector or switch the current
enters by). The limit is pad edge to pad edge: CHAIN_MM_HIGH at 3 A or more, CHAIN_MM_LOW below; the weight
grows with the current (a 10 A path pulls harder than a 1 A one). Statements already in the intent file for the
same pair are left as they are. Written with why = "power path <net>" so a person can find and edit them.

--corridors=<out dump.json> --anchors=REF,REF,...: a copy of the board dump with a no-footprint keep-out along the
straight line between the nearest pads of every chained pair whose two parts are both anchors (placed by a
person, anchors.py), as wide as the current needs (roles.width_mm) plus CORRIDOR_ROOM_MM, on the parts' side. The
placer then keeps its fill-in parts out of the power path (the first anchored trial lost two switch-node joins
and most of PP5V to small parts dropped in the way). Keep-outs are boxes, so the line is a row of squares.
--check=<board_dump.json>[,<placement.json>]: print each chain's distance on a board, or on the dump moved to a
placement from place_pack.py, against its limit (to see what a placement does)."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "copper"))
from roles import Design

CHAIN_MM_HIGH = 10.0   # set so the hand board meets them but for its two shunt runs (17 mm, carried on In3)
CHAIN_MM_LOW = 20.0
CORRIDOR_ROOM_MM = 0.8 # clearance and escape room on both sides of the corridor's copper
BUS_TERMINALS = 6      # a net with this many series terminals is a bus (an inner-layer pour carries it): no chain

def design(dumpf, consf):
    D = json.load(open(dumpf)); side = {f["ref"]: f.get("side", "F.Cu") for f in D["fps"]}
    pads = []
    for p in D["pads"]:
        x0, y0, x1, y1 = p["box"]; ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        L = [l for l in p["layers"] if l.endswith(".Cu") and "*" not in l] or [side[p["ref"]]]
        pads.append(dict(ref=p["ref"], num=p["num"], net=p["net"], x=p["x"], y=p["y"], pinfn=p.get("pinfn", ""), npth=not p["net"] and False,
                         shapes={l: [dict(ring=ring)] for l in L}))
    fps = [dict(ref=f["ref"], value=f.get("value", ""), layer=side[f["ref"]]) for f in D["fps"]]
    return Design(dict(pads=pads, fps=fps), consf), D

def chains(d, min_a):
    out = []
    for net in sorted(d.power, key=lambda n: -d.current(n)):
        I = d.current(net)
        if I < min_a: continue
        S = [g for g in d.terminals(net) if g["kind"] == "series"]
        if len(S) >= BUS_TERMINALS: continue
        T = [g for g in S if g["current_a"] >= 0.5 * I]
        if len(T) < 2: continue
        T.sort(key=lambda g: (-g["current_a"], not g["ref"].startswith("J"), g["ref"]))
        src = T[0]
        for g in T[1:]:
            out.append(dict(part=g["ref"], to=[f'{src["ref"]}.{p["num"]}' for p in src["pads"]], pads=[f'{g["ref"]}.{p["num"]}' for p in g["pads"]],
                            max_mm=CHAIN_MM_HIGH if I >= 3 else CHAIN_MM_LOW, weight=max(1, min(4, round(I / 2.5))),
                            net=net, current_a=round(min(I, g["current_a"]), 2)))
    return out

def gap(D, a_pads, b_pads):
    P = {f'{p["ref"]}.{p["num"]}': p["box"] for p in D["pads"]}
    def d(a, b):
        dx = max(b[0] - a[2], a[0] - b[2], 0); dy = max(b[1] - a[3], a[1] - b[3], 0); return math.hypot(dx, dy)
    return min(d(P[a], P[b]) for a in a_pads for b in b_pads if a in P and b in P)

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
    d, D = design(a[0], a[1]); ch = chains(d, float(opt.get("min-a", 1)))
    if "check" in opt:
        f = opt["check"].split(","); P = json.load(open(f[0]))
        if len(f) > 1:          # the dump's pads moved to a placement (x, y, rotation in degrees relative to the dump)
            pl = json.load(open(f[1])); pos = {q["ref"]: (q["x"], q["y"]) for q in P["fps"]}
            for p in P["pads"]:
                if p["ref"] not in pl: continue
                x0, y0 = pos[p["ref"]]; px, py, rot = pl[p["ref"]][:3]; b = p["box"]; q = [(b[0] - x0, b[1] - y0), (b[2] - x0, b[3] - y0)]
                for _ in range(int(rot) // 90 % 4): q = [(-v, u) for u, v in q]
                p["box"] = [px + min(q[0][0], q[1][0]), py + min(q[0][1], q[1][1]), px + max(q[0][0], q[1][0]), py + max(q[0][1], q[1][1])]
        for c in ch:
            g = gap(P, c["pads"], c["to"]); print(f'{"FAIL" if g > c["max_mm"] else "ok  "} {c["net"]:28} {c["part"]:6} to {c["to"][0].split(".")[0]:6} {g:5.1f} mm (limit {c["max_mm"]})')
    if "corridors" in opt:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "copper")); from roles import width_mm
        anc = set(opt.get("anchors", "").split(",")); FIX = ("J", "H", "TP", "SW"); n = 0
        isfix = lambda r: r in anc or r.rstrip("0123456789") in FIX
        side = {f["ref"]: f.get("side", "F.Cu") for f in D["fps"]}; B = {f'{p["ref"]}.{p["num"]}': p["box"] for p in D["pads"]}
        for c in ch:
            src = c["to"][0].split(".")[0]
            if not (isfix(c["part"]) and isfix(src)) or side[c["part"]] != side[src]: continue
            pa = [B[k] for k in c["pads"] if k in B]; pb = [B[k] for k in c["to"] if k in B]
            ctr = lambda b: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
            (ax, ay), (bx, by) = min(((ctr(u), ctr(v)) for u in pa for v in pb), key=lambda q: math.dist(*q))
            w = width_mm(c["current_a"]) + 2 * CORRIDOR_ROOM_MM; L = math.dist((ax, ay), (bx, by)); k = max(1, int(L / (w / 2)))
            for i in range(k + 1):
                x, y = ax + (bx - ax) * i / k, ay + (by - ay) * i / k
                D.setdefault("keepouts", []).append(dict(name=f'power path {c["net"].strip("/")} {c["part"]}-{src}', box=[x - w / 2, y - w / 2, x + w / 2, y + w / 2], layers=[side[src]], no_footprints=True, no_tracks=False, no_vias=False, no_pours=False))
            n += 1
        json.dump(D, open(opt["corridors"], "w")); print(f"{n} power corridors kept clear -> {opt['corridors']}")
    if len(a) >= 4:
        it = json.load(open(a[2])); have = {(s["part"], s["to"][0].split(".")[0]) for s in it.get("near", [])}; n = 0
        for c in ch:
            if (c["part"], c["to"][0].split(".")[0]) in have: continue
            it.setdefault("near", []).append(dict(part=c["part"], to=c["to"], max_mm=c["max_mm"], weight=c["weight"], why=f'power path {c["net"].strip("/")} ({c["current_a"]} A)')); n += 1
        json.dump(it, open(a[3], "w"), indent=1); print(f"{n} power-path statements added, {len(it['near'])} near statements in all -> {a[3]}")
