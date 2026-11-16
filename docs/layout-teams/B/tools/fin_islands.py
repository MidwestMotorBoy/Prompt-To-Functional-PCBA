"""fin_islands.py <board.kicad_pcb> <cu.json with its pads> [--nets=PACK_P,3V3,GND] [--out=dead.json]
(team B, finishing pass, phase 2 round 2) The copper pieces of the power nets as KiCad's connectivity sees them, from the
board file (filled zones, tracks, vias) and the pads of cu.json (tools/copper/cu_dump.py of any board with the same
placement): fill islands, tracks, vias and pads joined where they overlap on a common layer (a through via joins every
layer, a PTH pad likewise). The largest piece (most pads) is the net; every other piece is printed with what it holds:
  dead   - no pad: copper that carries nothing (a strap end the router cut off, a slab hanging on one via). Its tracks and
           vias are listed in --out for tools/fin_dead.py, which removes them and refills (a dead fill island then goes
           with them: KiCad keeps an island only while copper of its net touches it, or when its zone keeps islands).
  pads   - holds pads: a real open connection (the router or a hand track must join it); never removed.
Exit 0. Host python (shapely)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shapely.geometry import Polygon, LineString, Point
from shapely.strtree import STRtree
R = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))
sys.path.insert(0, os.path.join(R, "tools/copper"))
from dc_score import load_copper

CU = ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"]


def pieces(Z, T, V, D, net):
    """The copper pieces of one net, largest (most pads) first; each a list of nodes (kind, layers, geometry, info)."""
    nodes = []                                   # (kind, layers, geometry, info)
    for z in Z:
        if z["net"] == net and len(z["pts"]) > 2:
            g = Polygon(z["pts"]).buffer(0)
            if not g.is_empty:
                nodes.append(("fill", {z["layer"]}, g, dict(layer=z["layer"], area=round(g.area, 3), at=[round(g.representative_point().x, 2), round(g.representative_point().y, 2)])))
    for t in T:
        if t["net"] == net and t["layer"] in CU:
            g = (LineString([t["a"], t["b"]]) if t["a"] != t["b"] else Point(t["a"])).buffer(t["w"] / 2)
            nodes.append(("track", {t["layer"]}, g, dict(layer=t["layer"], a=list(t["a"]), b=list(t["b"]), w=t["w"])))
    for v in V:
        if v["net"] == net:
            nodes.append(("via", set(CU), Point(v["x"], v["y"]).buffer(v["size"] / 2), dict(x=v["x"], y=v["y"])))
    for p in D["pads"]:
        if p["net"] != net: continue
        for L, recs in p["shapes"].items():
            for r in recs:
                if len(r["ring"]) > 2:
                    g = Polygon(r["ring"]).buffer(0)
                    nodes.append(("pad", set(CU) if p.get("drill") else {L}, g, dict(pad="%s.%s" % (p["ref"], p["num"]), layer=L)))
    par = list(range(len(nodes)))
    def f(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    tree = STRtree([n[2] for n in nodes])
    for i, n in enumerate(nodes):
        for j in tree.query(n[2]):
            j = int(j)
            if j > i and (n[1] & nodes[j][1]) and n[2].intersects(nodes[j][2]):
                par[f(i)] = f(j)
    pcs = {}
    for i in range(len(nodes)): pcs.setdefault(f(i), []).append(nodes[i])
    return sorted(pcs.values(), key=lambda c: (-len({x[3]["pad"] for x in c if x[0] == "pad"}), -len(c)))


if __name__ == "__main__":
    A = [a for a in sys.argv[1:] if not a.startswith("--")]
    O = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in sys.argv[1:] if a.startswith("--"))
    if len(A) < 2: print(__doc__); sys.exit(2)
    NETS = O.get("nets", "PACK_P,3V3,GND").split(",")
    Z, T, V = load_copper(A[0])
    D = json.load(open(A[1]))
    out = dict(board=A[0], pieces=[])
    for net in NETS:
        pcs = pieces(Z, T, V, D, net)
        print("%s: %d pieces" % (net, len(pcs)))
        for k, c in enumerate(pcs[1:], 1):
            pads = sorted({x[3]["pad"] for x in c if x[0] == "pad"})
            kind = "pads" if pads else "dead"
            fills = [x[3] for x in c if x[0] == "fill"]; trk = [x[3] for x in c if x[0] == "track"]; vias = [x[3] for x in c if x[0] == "via"]
            print("  piece %d %s: pads %s; fills %s; tracks %d %s; vias %s" % (
                k, kind, pads, ["%s %.3f mm2 @%s" % (q["layer"], q["area"], q["at"]) for q in fills], len(trk),
                ["%s %s-%s w%.2f" % (q["layer"], q["a"], q["b"], q["w"]) for q in trk][:6], ["%.2f,%.2f" % (q["x"], q["y"]) for q in vias]))
            out["pieces"].append(dict(net=net, kind=kind, pads=pads, fills=fills, tracks=trk, vias=vias))
    if "out" in O: json.dump(out, open(O["out"], "w"), indent=1)
