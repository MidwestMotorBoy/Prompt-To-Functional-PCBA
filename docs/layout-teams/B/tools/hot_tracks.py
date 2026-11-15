"""hot_tracks.py <board before routing.kicad_pcb> <its cu.json> <routed or finished board.kicad_pcb> [out.json]
(team B lead, phase 2) Gate 7 as a number: every track and via the router (or the finishing pass) added that lies in a
hot-loop pour of another net. Hot-loop pours are those of tools/pinlib.py hot_polys (the filled supply / return pours on
F.Cu and B.Cu that touch a loop's capacitors or switch pins, constraints.json), read from the board before routing.
Same test as tools/fin_guard.py, but against the copper board, complete, and grouped by net.
Prints one line per net and 'hot-pour items: N tracks, M vias on K nets'; out.json holds the full list.
Exit 0 always (it is a report; final_route.sh puts the count into final.json as routed.hot_pour_items)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pinlib
from shapely.geometry import LineString, Point
sys.path.insert(0, os.path.join(pinlib.REPO, "tools/copper"))
from dc_score import load_copper

A = [a for a in sys.argv[1:] if not a.startswith("--")]
if len(A) < 3: print(__doc__); sys.exit(2)
D, G, (Z0, T0, V0) = pinlib.load_board(A[0], A[1])
_, T1, V1 = load_copper(A[2])
k_t = lambda t: (t["net"], t["layer"], round(t["a"][0], 4), round(t["a"][1], 4), round(t["b"][0], 4), round(t["b"][1], 4), round(t["w"], 4))
k_v = lambda v: (v["net"], round(v["x"], 4), round(v["y"], 4))
old_t = {k_t(t) for t in T0}; old_v = {k_v(v) for v in V0}
hot = {L: [(n, g) for n, k, g, _ in G.items[L] if k == "hotzone"] for L in pinlib.CU}
out = []
for t in T1:
    if k_t(t) in old_t or t["layer"] not in pinlib.CU: continue
    g = LineString([t["a"], t["b"]]).buffer(t["w"] / 2) if t["a"] != t["b"] else Point(t["a"]).buffer(t["w"] / 2)
    for n, h in hot[t["layer"]]:
        if n != t["net"] and g.intersects(h):
            out.append(dict(kind="track", net=t["net"], layer=t["layer"], a=t["a"], b=t["b"], pour=n)); break
for v in V1:
    if k_v(v) in old_v: continue
    g = Point(v["x"], v["y"]).buffer(v.get("size", pinlib.VIA_D) / 2)
    for L in ("F.Cu", "B.Cu"):
        hit = [n for n, h in hot[L] if n != v["net"] and g.intersects(h)]
        if hit:
            out.append(dict(kind="via", net=v["net"], layer=L, a=[v["x"], v["y"]], b=[v["x"], v["y"]], pour=hit[0])); break
nets = {}
for o in out: nets.setdefault(o["net"], []).append(o)
for n in sorted(nets):
    its = nets[n]; xs = [p[0] for o in its for p in (o["a"], o["b"])]; ys = [p[1] for o in its for p in (o["a"], o["b"])]
    print("  %-28s %d tracks, %d vias in the hot pour of %s, x %.1f to %.1f, y %.1f to %.1f" % (
        n, sum(o["kind"] == "track" for o in its), sum(o["kind"] == "via" for o in its),
        "/".join(sorted({o["pour"] for o in its})), min(xs), max(xs), min(ys), max(ys)))
print("hot-pour items: %d tracks, %d vias on %d nets" % (sum(o["kind"] == "track" for o in out), sum(o["kind"] == "via" for o in out), len(nets)))
if len(A) > 3: json.dump(dict(items=out, tracks=sum(o["kind"] == "track" for o in out), vias=sum(o["kind"] == "via" for o in out), nets=sorted(nets)), open(A[3], "w"), indent=1)
