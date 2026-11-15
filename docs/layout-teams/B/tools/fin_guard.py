"""fin_guard.py <routed.kicad_pcb> <its cu.json> <candidate.kicad_pcb> <routed dc.json> <candidate dc.json> [--tol=0.001]
(team B, finishing pass) Says whether a finished candidate may replace the routed board:
  - power: dc_score loss (sum over the scored nets) no more than routed + tol W, and no more power opens;
  - hot loops: no new track of another net through a hot-loop pour of the routed board (filled copper, tools/pinlib.py
    hot_polys: supply / return pours on F/B touching a loop's caps or switch parts), no new via of another net inside
    one; new same-net vias in a hot pour are listed, not refused.
Prints one line 'guard ok|FAIL: ...' and exits 0 when the candidate passes, 1 when it does not."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pinlib
from shapely.geometry import LineString, Point

A = [a for a in sys.argv[1:] if not a.startswith("--")]
O = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in sys.argv[1:] if a.startswith("--"))
r_pcb, r_cu, c_pcb, r_dc, c_dc = A[:5]
TOL = float(O.get("tol", 0.001))
sys.path.insert(0, os.path.join(pinlib.REPO, "tools/copper"))
from dc_score import load_copper

D, G, (Z0, T0, V0) = pinlib.load_board(r_pcb, r_cu)
_, T1, V1 = load_copper(c_pcb)
k_t = lambda t: (t["net"], t["layer"], round(t["a"][0], 4), round(t["a"][1], 4), round(t["b"][0], 4), round(t["b"][1], 4), round(t["w"], 4))
k_v = lambda v: (v["net"], round(v["x"], 4), round(v["y"], 4))
old_t = {k_t(t) for t in T0}; old_v = {k_v(v) for v in V0}
new_t = [t for t in T1 if k_t(t) not in old_t and t["layer"] in pinlib.CU]
new_v = [v for v in V1 if k_v(v) not in old_v]
hot = {L: [(n, g) for n, k, g, _ in G.items[L] if k == "hotzone"] for L in pinlib.CU}
bad, same = [], []
for t in new_t:
    g = LineString([t["a"], t["b"]]).buffer(t["w"] / 2) if t["a"] != t["b"] else Point(t["a"]).buffer(t["w"] / 2)
    for n, h in hot[t["layer"]]:
        if n != t["net"] and g.intersects(h):
            bad.append("track %s %s %s-%s through the hot pour of %s" % (t["net"], t["layer"], t["a"], t["b"], n))
for v in new_v:
    g = Point(v["x"], v["y"]).buffer(v.get("size", pinlib.VIA_D) / 2)
    for L in ("F.Cu", "B.Cu"):
        for n, h in hot[L]:
            if h.contains(Point(v["x"], v["y"])) or g.intersects(h):
                (same if n == v["net"] else bad).append("via %s at %.2f,%.2f in the hot pour of %s on %s" % (v["net"], v["x"], v["y"], n, L))


def dcsum(p):
    d = json.load(open(p)); d = d.get("nets", d)
    return sum(v.get("loss_W", 0) for v in d.values()), sorted("%s:%s" % (k, o) for k, v in d.items() for o in v.get("open", []))


l0, o0 = dcsum(r_dc); l1, o1 = dcsum(c_dc)
why = []
if l1 > l0 + TOL: why.append("loss %.4f W > routed %.4f W" % (l1, l0))
if len(o1) > len(o0) or not set(o1) <= set(o0): why.append("power open %s (routed %s)" % (o1, o0))
why += bad
print("guard %s: %d new tracks, %d new vias; loss %.4f -> %.4f W; power open %d -> %d; hot-pour violations %d%s%s" % (
    "FAIL" if why else "ok", len(new_t), len(new_v), l0, l1, len(o0), len(o1), len(bad),
    ("; same-net vias in hot pours %d" % len(same)) if same else "", ("; " + "; ".join(why[:6])) if why else ""))
for s in same[:10]: print("  note:", s)
sys.exit(1 if why else 0)
