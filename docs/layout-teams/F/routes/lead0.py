"""lead0.py <dir> <board> <out.json>   Lead copper laid BEFORE the router (team F), on the board made by hr.py.
1. PACK_P straps: hard tracks on B.Cu / In2.Cu along the pack power path, because the router treats the PACK_P pours
   as soft and cuts them into islands (team D lost the pack connector and the Port 2 5 V buck that way).
2. Kelvin taps of the four port shunts and the gauge shunt: via in the inner edge of the shunt pad, inner-layer track
   to the sense resistor. The router never attempts these.
3. Ground necks: QFN ground pins that sit between two power pins tie to the exposed pad with a 0.15 mm track.
Everything is found by tools/ml.py with the real rules; hr.py then runs the real DRC."""
import sys, math, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from ml import ML, SIG
from shapely.geometry import Point
d, board, out = sys.argv[1:4]
h = ML(d, board)
INNER = ("In2.Cu", "In3.Cu", "B.Cu")

def disc(x, y, r=0.2): return Point(x, y).buffer(r, 8)
def pvias(x0, y0, x1, y1):
    return [(v[0], v[1]) for v in h.vias if v[3] == "PACK_P" and x0 <= v[0] <= x1 and y0 <= v[1] <= y1]
def strap(a, b, layer, w, label):
    """a, b = PACK_P via centres; a hard track on one layer"""
    g = lambda p: {layer: [disc(p[0], p[1], 0.22)]}
    r = h.route("PACK_P", a, b, w=w, layers=(layer,), margin=6.0, start_geoms=g(a), goal_geoms=g(b), quiet=True)
    for w2 in (1.2, 0.8, 0.5):
        if r is None and w > w2: r = h.route("PACK_P", a, b, w=w2, layers=(layer,), margin=10.0, start_geoms=g(a), goal_geoms=g(b), quiet=True); w = w2 if r else w
    print("strap %-28s %s w=%.1f %s" % (label, layer, w, "ok %.1f mm" % sum(math.hypot(q[1] - p[1], q[2] - p[2]) for p, q in zip(r, r[1:])) if r else "NO PATH"))
    return r
def nearest(pts, p): return min(pts, key=lambda q: math.hypot(q[0] - p[0], q[1] - p[1]))

# ---- 1. PACK_P straps
q102 = pvias(98.5, 114.0, 104.5, 118.0)                       # vias at the discharge FET's output pads
if q102:
    P = lambda ref, num: h.pad(ref, num)[:2]
    j113 = pvias(118.5, 104.5, 121.5, 109.0); bulk = pvias(94.0, 100.0, 105.0, 112.5)
    east = max(q102, key=lambda p: p[0]); north = min(q102, key=lambda p: p[1])
    if j113:
        t = nearest(j113, east)
        strap(east, t, "B.Cu", 2.0, "FET -> pack connector"); strap(nearest(q102, (east[0] - 1.5, east[1])), nearest([p for p in j113 if p != t] or j113, east), "In2.Cu", 1.5, "FET -> pack connector")
    r527 = nearest(bulk, P("R527", "2")) if bulk else None
    if r527:
        strap(north, r527, "In2.Cu", 1.5, "FET -> Port 2 shunt / bulk")
        for v in sorted(bulk, key=lambda p: p[1])[::3]:      # a few ties into the bulk capacitor field
            if v != r527: strap(nearest([r527, north], v), v, "In2.Cu", 0.8, "bulk tie")
    for label, ref, num, frm in (("Port 2 5 V buck", "C546", "1", None), ("Port 2 9 V supply", "C557", "1", None), ("3V3 buck", "C206", "1", "C557"),
                                 ("Port 1 9 V supply", "C457", "1", "J113"), ("gauge D103", "D103", "1", None), ("Port 1 5 V buck", "C446", "1", None)):
        try: p = P(ref, num)
        except KeyError: continue
        near = [v for v in h.vias if v[3] == "PACK_P" and math.hypot(v[0] - p[0], v[1] - p[1]) < 2.5]
        if not near: print("strap %-28s no PACK_P via near %s" % (label, ref)); continue
        a = nearest([(v[0], v[1]) for v in near], p)
        if frm == "J113" and j113: b = nearest(j113, a)
        elif frm == "C557":
            c = P("C557", "1"); nb = [(v[0], v[1]) for v in h.vias if v[3] == "PACK_P" and math.hypot(v[0] - c[0], v[1] - c[1]) < 2.5]; b = nearest(nb or q102, a)
        else: b = nearest(q102 + (bulk or []), a)
        if math.hypot(a[0] - b[0], a[1] - b[1]) > 0.3: strap(b, a, "In2.Cu", 0.6, label)

# ---- 2. Kelvin taps
def tap(net, shunt, num, sense, snum="1"):
    sx, sy, sg, _, _ = h.pad(shunt, num); ox, oy = h.pad(shunt, "2" if num == "1" else "1")[:2]; rx, ry = h.pad(sense, snum)[:2]
    x0, y0, x1, y1 = sg.bounds
    # candidate via spots in the inner third of the shunt pad (the side facing the other pad)
    if abs(ox - sx) > abs(oy - sy): inner = sg.intersection(Point(sx, sy).buffer(5).envelope).intersection(__import__("shapely.geometry", fromlist=["box"]).box(*( (sx, y0, x1, y1) if ox > sx else (x0, y0, sx, y1))))
    else: inner = sg.intersection(__import__("shapely.geometry", fromlist=["box"]).box(*((x0, sy, x1, y1) if oy > sy else (x0, y0, x1, sy))))
    edge = (x1 if ox > sx else x0, sy) if abs(ox - sx) > abs(oy - sy) else (sx, y1 if oy > sy else y0)
    c = h.via_near(net, edge[0], edge[1], 1.0, n=1, inside=inner.buffer(-0.2)) or h.via_near(net, edge[0], edge[1], 1.2, n=1, inside=inner.buffer(-0.05)) or h.via_near(net, edge[0], edge[1], 1.5, n=1, inside=sg.buffer(-0.05))
    if not c:                                              # the planner already put vias of this net in the pad: use the innermost
        ex = sorted((math.hypot(v[0] - edge[0], v[1] - edge[1]), v[0], v[1]) for v in h.vias if v[3] == net and sg.buffer(0.1).contains(Point(v[0], v[1])))
        if not ex: print("tap %-24s %s.%s: no legal via in the pad" % (net, shunt, num)); return None
        vx, vy = ex[0][1], ex[0][2]
    else: vx, vy = c[0][1], c[0][2]; h.via(net, vx, vy)
    g = {L: [disc(vx, vy, 0.22)] for L in INNER}
    r = h.route(net, (vx, vy), (rx, ry), w=0.2, layers=SIG, margin=5.0, start_geoms=g, quiet=True) or h.route(net, (vx, vy), (rx, ry), w=0.15, layers=SIG, margin=10.0, start_geoms=g, quiet=True)
    print("tap %-24s %s.%s via (%.2f, %.2f) -> %s.%s %s" % (net, shunt, num, vx, vy, sense, snum, "ok" if r else "NO PATH")); return r
for port, k in (("1", "4"), ("2", "5")):
    N = "/USB Port %s/" % port
    tap(N + "PPHV", "R%s24" % k, "1", "R%s25" % k); tap(N + "AC_SNS_N", "R%s24" % k, "2", "R%s26" % k)
    tap(N + "BAT_SNS_P", "R%s27" % k, "1", "R%s28" % k); tap("PACK_P", "R%s27" % k, "2", "R%s29" % k)
tap("CELL_N", "RS101", "1", "R107")
def force(net, layer, pts, w):
    """a straight track the lead vouches for (exact geometry; the real DRC is the check)"""
    from shapely.geometry import LineString
    h.J["routes"].append({"net": net, "w": w, "path": [[layer, round(x, 3), round(y, 3)] for x, y in pts]}); h._add(layer, LineString(pts).buffer(w / 2, 8), net, "track")
gx, gy, gg = h.pad("RS101", "2")[:3]; rx, ry = h.pad("R108", "1")[:2]; b_ = gg.bounds; ox = h.pad("RS101", "1")[0]
e = (b_[0] + 0.15 if ox < gx else b_[2] - 0.15, gy)          # inner edge of the shunt's GND pad
r = h.route("GND", e, (rx, ry), w=0.2, layers=("F.Cu",), margin=3.0, start_geoms={"F.Cu": [disc(e[0], e[1], 0.1)]}, quiet=True)
print("tap GND RS101.2 inner edge -> R108.1 on F: %s" % ("ok" if r else "NO PATH"))

# ---- 3. ground necks at the PD controllers
for u in ("U401", "U501"):
    for pin in ("31", "36"):
        try: a = h.pad(u, pin); b = h.pad(u, "39")
        except KeyError: continue
        if a[3] != "GND" or b[3] != "GND": continue
        bb = b[2].bounds; ab = a[2].bounds
        if ab[3] - ab[1] > ab[2] - ab[0]: end = (a[0], bb[1] + 0.1 if a[1] < b[1] else bb[3] - 0.1)      # pin on the north / south row
        else: end = (bb[0] + 0.1 if a[0] < b[0] else bb[2] - 0.1, a[1])
        force("GND", "F.Cu", [a[:2], end], 0.15); print("neck GND %s.%s -> pad 39 (%.2f, %.2f)" % (u, pin, end[0], end[1]))
h.save(out)
