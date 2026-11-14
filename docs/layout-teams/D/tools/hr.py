"""hr.py <base run dir> <out dir> <routes.json> [more routes.json ...]
Hand routing on top of the generated power copper. Takes the base run's bare.kicad_pcb and spec.json (the copper
plan), adds the hand routes, writes <out>/hand.kicad_pcb (zones refilled round the new tracks) and runs DRC.
Score the result with:  bash tools/score/score_board.sh <dir> <out>/hand.kicad_pcb --keep-copper [--no-hot] [--route=0]

A routes file is JSON:
{ "routes": [ {"net": "/USB Port 1/HG1", "w": 0.2, "path": [["F.Cu", x, y], ["F.Cu", x, y], ["In3.Cu", x, y], ...]} ],
     a path is a list of points; a track is drawn between consecutive points on the layer of the SECOND point;
     where the layer changes between two points a via (0.45/0.3 through, or "via": [size, drill]) is put at the FIRST point.
  "vias":   [ {"net": "GND", "x": .., "y": ..} ],
  "cuts":   [ {"net": "PACK_P", "layer": "F.Cu", "box": [x0, y0, x1, y1]} ],     remove this net's pour inside the box
  "pours":  [ {"net": "GND", "layer": "F.Cu", "box": [x0, y0, x1, y1]} ],        add a rectangle of pour (priority 40)
  "drop":   [ {"net": "...", "layer": "F.Cu", "box": [...]} ]                    remove generated tracks/vias of a net inside the box
}
Prints: DRC errors that touch the hand items (with positions), and the total."""
import sys, os, json, subprocess, shutil
from shapely.geometry import Polygon, box as sbox
from shapely.ops import unary_union

base, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]); files = sys.argv[3:]
os.makedirs(out, exist_ok=True)
S = json.load(open(base + "/spec.json"))
R = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
hand = []                                                     # (kind, net, x, y) for reporting

def inbox(p, b): return b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]

for f in files:
    J = json.load(open(f))
    for d in J.get("drop", []):
        b = d["box"]
        S["tracks"] = [t for t in S["tracks"] if not (t["net"] == d["net"] and t["layer"] == d.get("layer", t["layer"]) and inbox(t["a"], b) and inbox(t["b"], b))]
        S["vias"] = [v for v in S["vias"] if not (v["net"] == d["net"] and inbox((v["x"], v["y"]), b))]
    for c in J.get("cuts", []):
        cb = sbox(*c["box"])
        for z in S["zones"]:
            if z["net"] != c["net"] or z["layer"] != c["layer"]: continue
            new = []
            for p in z["polys"]:
                g = Polygon(p["ring"], p.get("holes", [])).buffer(0).difference(cb)
                for q in (g.geoms if hasattr(g, "geoms") else [g]):
                    if q.is_empty or q.area < 0.01: continue
                    new.append({"ring": [list(c_) for c_ in q.exterior.coords[:-1]], "holes": [[list(c_) for c_ in h.coords[:-1]] for h in q.interiors]})
            z["polys"] = new
    for p in J.get("pours", []):
        b = p["box"]
        S["zones"].append({"net": p["net"], "layer": p["layer"], "priority": p.get("priority", 40), "soft": False, "kinds": ["hand"],
                           "polys": [{"ring": [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]], "holes": []}]})
    for v in J.get("vias", []):
        S["vias"].append({"net": v["net"], "x": v["x"], "y": v["y"], "size": v.get("size", 0.45), "drill": v.get("drill", 0.3)}); hand.append(("via", v["net"], v["x"], v["y"]))
    for r in J.get("routes", []):
        pts = r["path"]; vs = r.get("via", [0.45, 0.3])
        for a, b in zip(pts, pts[1:]):
            if a[0] != b[0] and not any(abs(v["x"] - a[1]) < 0.01 and abs(v["y"] - a[2]) < 0.01 for v in S["vias"]):
                S["vias"].append({"net": r["net"], "x": a[1], "y": a[2], "size": vs[0], "drill": vs[1]}); hand.append(("via", r["net"], a[1], a[2]))
            if (a[1], a[2]) != (b[1], b[2]):
                S["tracks"].append({"net": r["net"], "layer": b[0], "a": [a[1], a[2]], "b": [b[1], b[2]], "w": r.get("w", 0.2)}); hand.append(("track", r["net"], (a[1] + b[1]) / 2, (a[2] + b[2]) / 2))
# one zone per outline: KiCad keeps only the first outline of a multi-outline zone when the board is saved again, so the
# router's refill silently dropped the other pours (found on the first routed board: VBUS and PACK_P pours on F gone)
S["zones"] = [dict(z, polys=[p]) for z in S["zones"] for p in z["polys"]]
json.dump(S, open(out + "/spec.json", "w"))
for e in ("kicad_pro", "kicad_dru"): shutil.copy(base + "/bare." + e, out + "/hand." + e)
shutil.copy(base + "/bare.kicad_pcb", out + "/bare.kicad_pcb")
for t in ("copper/write_copper.py", "copper/cu_dump.py"): shutil.copy(R + "/tools/" + t, out)
K = ["docker", "run", "--rm", "-u", "0", "-v", out + ":/w", "-w", "/w", "kicad/kicad:10.0"]
subprocess.run(K + ["sh", "-c", "python3 write_copper.py bare.kicad_pcb spec.json hand.kicad_pcb > write.log 2>&1; kicad-cli pcb drc --severity-all --format json -o drc.json hand.kicad_pcb >/dev/null 2>&1"], check=False)
D = json.load(open(out + "/drc.json")); errs = [v for v in D.get("violations", []) if v.get("severity") == "error"]
nets = {h[1] for h in hand}
print("DRC errors: %d (base run: see its drc.json)" % len(errs))
for v in errs:
    txt = " | ".join(i.get("description", "") for i in v.get("items", []))
    pos = v["items"][0].get("pos", {}) if v.get("items") else {}
    print("  %s at (%.2f, %.2f): %s" % (v.get("type"), pos.get("x", 0), pos.get("y", 0), txt[:200]))
print("hand items: %d tracks, %d vias on %d nets -> %s/hand.kicad_pcb" % (sum(h[0] == "track" for h in hand), sum(h[0] == "via" for h in hand), len(nets), out))
