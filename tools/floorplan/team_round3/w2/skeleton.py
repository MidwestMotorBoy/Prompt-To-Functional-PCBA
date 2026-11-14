"""skeleton.py: power parts and their copper first, everything else round them (Monolith round 2).

  skeleton.py refs <constraints.json> <board_dump.json>
      the skeleton: anchors.py --power (cell path, PD switches, power FETs, inductors, shunts, bucks) plus every
      hot-loop capacitor
  skeleton.py cut <board_dump.json> <clusters.json> <intent.json> <REF,REF,...> <out prefix>
      <prefix>_dump.json, _clusters.json, _intent.json holding only the skeleton (and the fixed parts), for
      place_pack.py (with BLOCK_FLOORPLAN, so each part stays in its section's box)
  skeleton.py strip <cu_dump.json of a placed board> <REF,REF,...> <out cu_dump.json>
      the placed board's dump with only the skeleton and the fixed parts, for plan_copper.py
  skeleton.py freeze <board_dump.json> <clusters.json> <skeleton placement.json> <copper spec.json> <out prefix> [room mm]
      <prefix>_dump.json: the skeleton parts moved to where the skeleton placement put them, and the skeleton's
      planned power copper (outer layers) as no-footprint keep-outs grown by [room] (default 0.3);
      <prefix>_clusters.json without the skeleton parts, so place_pack.py keeps them fixed.

Why: inside the reviewed boxes, the placer packed the top side (73 % full) so that 2 to 4 power paths had no room on
every seed, and repairing lanes afterwards moved the problem around (copper_repair.py). The one trial that joined
every 5 A path had the power parts placed first (by hand, with each hot loop's first capacitor). This does that
step by script: place the power parts alone, plan their copper, then keep both and fill in the rest."""
import sys, os, json, math
import numpy as np

FIX = ("J", "H", "TP", "SW")

def turn(v, q):
    x, y = v
    for _ in range(q % 4): x, y = -y, x
    return x, y

def refs(consf, dumpf):
    import subprocess
    here = os.path.dirname(os.path.abspath(__file__))
    out = subprocess.run([sys.executable, os.path.join(here, "anchors.py"), dumpf, consf, "--power"], capture_output=True, text=True).stdout.strip().splitlines()[-1]
    C = json.load(open(consf)); s = set(out.split(","))
    for hl in C.get("hot_loops", {}).values(): s |= set(hl["caps"])
    return sorted(s)

W2_RES = [x for x in os.environ.get("W2_RESERVE", "").split(",") if x]; W2_RES_MM = float(os.environ.get("W2_RES_MM", "3"))

def cut(dumpf, clf, itf, rl, pre):
    S = set(rl.split(",")) | set(W2_RES); keep = lambda r: r in S or r.rstrip("0123456789") in FIX
    D = json.load(open(dumpf)); D["fps"] = [f for f in D["fps"] if keep(f["ref"])]; D["pads"] = [p for p in D["pads"] if keep(p["ref"])]
    for f in D["fps"]:      # w2 reserve: the controller stands for itself plus the room its support parts need
        if f["ref"] in W2_RES and "court" in f: c = f["court"]; m = W2_RES_MM; f["court"] = [c[0] - m, c[1] - m, c[2] + m, c[3] + m]
    if W2_RES and os.environ.get("W2_RES_FIX") == "1":   # reserved controllers fixed at their box centres, out of the clusters
        BF = json.load(open(os.environ.get("W2_FP", "/home/claude/work/bfp7/floorplan_2.json")))["blocks"]; CL0 = json.load(open(clf)); fix = {}
        for k, parts in CL0.items():
            for r in W2_RES:
                if r in parts and k in BF: b = BF[k]; fix[r] = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
        for f in D["fps"]:
            if f["ref"] in fix:
                dx, dy = fix[f["ref"]][0] - f["x"], fix[f["ref"]][1] - f["y"]; f["x"] += dx; f["y"] += dy
                if "court" in f: c = f["court"]; f["court"] = [c[0] + dx, c[1] + dy, c[2] + dx, c[3] + dy]
                for p in D["pads"]:
                    if p["ref"] == f["ref"]: p["x"] += dx; p["y"] += dy; b = p["box"]; p["box"] = [b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy]
        S -= set(fix); json.dump({r: [x, y, 0] for r, (x, y) in fix.items()}, open(f"{pre}_resfix.json", "w"))
    CL = {k: {r: v for r, v in parts.items() if r in S} for k, parts in json.load(open(clf)).items()}; CL = {k: v for k, v in CL.items() if v}
    it = json.load(open(itf)); have = lambda t: keep(t.split(".")[0])
    it["near"] = [s for s in it.get("near", []) if keep(s["part"]) and all(have(t) for t in s["to"])]
    it["keepapart"] = []
    for x, o in ((D, "dump"), (CL, "clusters"), (it, "intent")): json.dump(x, open(f"{pre}_{o}.json", "w"))
    print(f"skeleton: {len(S)} parts in {len(CL)} sections -> {pre}_*.json")

def strip(cuf, rl, outf):
    S = set(rl.split(",")); keep = lambda r: r in S or r.rstrip("0123456789") in FIX
    P = json.load(open(cuf))
    if W2_RES:              # w2 reserve: the reserved controllers leave the copper plan, their rooms become pour keep-outs
        E0 = json.load(open(os.environ.get("W2_DUMP", "/home/claude/prompt-to-functional-pcba/tools/floorplan/example/monolith/board_dump.json")))
        f0 = {f["ref"]: f for f in E0["fps"]}; PL = json.load(open(os.environ["W2_SKP"]))
        for r in W2_RES:
            f = f0[r]; x, y, a = PL[r][:3]; q = int(a) // 90; c = f["court"]; m = W2_RES_MM
            a_ = turn((c[0] - f["x"], c[1] - f["y"]), q); b_ = turn((c[2] - f["x"], c[3] - f["y"]), q)
            bx = [x + min(a_[0], b_[0]) - m, y + min(a_[1], b_[1]) - m, x + max(a_[0], b_[0]) + m, y + max(a_[1], b_[1]) + m]
            P.setdefault("keepouts", []).append(dict(name="w2 reserve " + r, layers=[f["side"]], poly=[dict(ring=[[bx[0], bx[1]], [bx[2], bx[1]], [bx[2], bx[3]], [bx[0], bx[3]]], holes=[])], no_tracks=True, no_vias=True, no_pours=True, no_footprints=False))
        S -= set(W2_RES)
    P["fps"] = [f for f in P["fps"] if keep(f["ref"])]; P["pads"] = [p for p in P["pads"] if keep(p["ref"])]
    json.dump(P, open(outf, "w")); print(f"{len(P['fps'])} parts kept -> {outf}")

# ---- w2 variants (env): W2_ERODE mm negative buffer per zone, W2_MINA min net current kept out, W2_RASTER intersects|center,
# W2_HOTFULL=1 keeps hot-loop zones un-eroded, W2_SKIP comma list of net substrings not kept out
W2_ERODE = float(os.environ.get("W2_ERODE", "0")); W2_MINA = float(os.environ.get("W2_MINA", "0"))
W2_RASTER = os.environ.get("W2_RASTER", "intersects"); W2_HOTFULL = os.environ.get("W2_HOTFULL", "0") == "1"
W2_SKIP = {x for x in os.environ.get("W2_SKIP", "").split(",") if x}
_w2_area = {}; _w2_cur = None
def _w2_current(net):
    global _w2_cur
    if _w2_cur is None:
        C = json.load(open(os.environ.get("W2_CONS", "/home/claude/prompt-to-functional-pcba/tools/floorplan/example/monolith/constraints.json")))
        _w2_cur = {k.lstrip("/"): v.get("current_a", 0) for k, v in C.get("nets", {}).items() if isinstance(v, dict)}
    return _w2_cur.get(net.lstrip("/"), None)
def _w2_keep(z):
    if any(x in z["net"] for x in W2_SKIP): return False
    if any(x in z["net"] for x in os.environ.get("W2_ADD", "").split(",") if x): return True
    if W2_MINA > 0:
        hot = any(k.startswith("hot loop") for k in z["kinds"])
        c = _w2_current(z["net"])
        if c is None: return hot          # GND: keep only when it carries a hot loop
        return c >= W2_MINA
    return True
def _w2_zone(z, room):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    g = unary_union([Polygon(r["ring"], r.get("holes", [])).buffer(0) for r in z["polys"]])
    hot = any(k.startswith("hot loop") for k in z["kinds"])
    if W2_ERODE > 0 and not (W2_HOTFULL and hot):
        e = g.buffer(-W2_ERODE)
        if os.environ.get("W2_THIN") == "1": g = e.union(g.difference(e.buffer(W2_ERODE + 0.05)))   # thin necks stay whole, only bulk rims go
        else: g = e
    if any(x in z["net"] for x in os.environ.get("W2_FULL", "").split(",") if x): g = unary_union([Polygon(r["ring"], r.get("holes", [])).buffer(0) for r in z["polys"]])
    return g.buffer(room) if room else g

def freeze(dumpf, clf, plf, specf, pre, room="0.3"):
    from shapely.geometry import Point
    from shapely.geometry import Polygon, box as sbox
    from shapely.ops import unary_union
    room = float(room); D = json.load(open(dumpf)); PL = json.load(open(plf)); CL = json.load(open(clf)); spec = json.load(open(specf))
    fp = {f["ref"]: f for f in D["fps"]}; S = {r for r in PL if r.rstrip("0123456789") not in FIX and r in fp}
    if os.environ.get("W2_RELEASE") == "1": S -= set(W2_RES)
    for p in D["pads"]:
        if p["ref"] not in S: continue
        f = fp[p["ref"]]; x, y, a = PL[p["ref"]][:3]; q = int(a) // 90
        mv = lambda u, v: (x + turn((u - f["x"], v - f["y"]), q)[0], y + turn((u - f["x"], v - f["y"]), q)[1])
        p["x"], p["y"] = mv(p["x"], p["y"]); b = p["box"]; a_, b_ = mv(b[0], b[1]), mv(b[2], b[3])
        p["box"] = [min(a_[0], b_[0]), min(a_[1], b_[1]), max(a_[0], b_[0]), max(a_[1], b_[1])]
    for r in S:
        f = fp[r]; x, y, a = PL[r][:3]; q = int(a) // 90
        if "court" in f:
            c = f["court"]; a_ = turn((c[0] - f["x"], c[1] - f["y"]), q); b_ = turn((c[2] - f["x"], c[3] - f["y"]), q)
            f["court"] = [x + min(a_[0], b_[0]), y + min(a_[1], b_[1]), x + max(a_[0], b_[0]), y + max(a_[1], b_[1])]
        f["x"], f["y"] = x, y; f["rot"] = (f.get("rot", 0) + 90 * q) % 360
    # the skeleton's power copper on the outer layers, as boxes (rows of a 0.5 mm raster, merged along x)
    outer = [D["layers"][0], D["layers"][-1]] if D.get("layers") else ["F.Cu", "B.Cu"]; n = 0; G = 0.5
    for L in outer:
        g = unary_union([_w2_zone(z, room) for z in spec["zones"] if z["layer"] == L and "plane" not in z["kinds"] and _w2_keep(z)])
        if g.is_empty: continue
        g = g.buffer(0); _w2_area[L] = 0.0
        x0, y0, x1, y1 = g.bounds
        for yy in np.arange(y0, y1, G):
            run = None
            for xx in np.arange(x0, x1 + G, G):
                hit = xx <= x1 and (g.contains(Point(xx + G / 2, yy + G / 2)) if W2_RASTER == "center" else g.intersects(sbox(xx, yy, xx + G, yy + G)))
                if hit and run is None: run = xx
                if not hit and run is not None:
                    D.setdefault("keepouts", []).append(dict(name="skeleton copper", box=[run, yy, xx, yy + G], layers=[L], no_footprints=True, no_tracks=False, no_vias=False, no_pours=False)); n += 1; run = None; _w2_area[L] += (D["keepouts"][-1]["box"][2] - D["keepouts"][-1]["box"][0]) * G
    CL = {k: {r: v for r, v in parts.items() if r not in S} for k, parts in CL.items()}; CL = {k: v for k, v in CL.items() if v}
    json.dump(D, open(f"{pre}_dump.json", "w")); json.dump(CL, open(f"{pre}_clusters.json", "w"))
    print(f"{len(S)} skeleton parts fixed, {n} copper keep-out boxes -> {pre}_dump.json, {pre}_clusters.json")
    print("W2 keep-out area mm2:", {k: round(v, 1) for k, v in _w2_area.items()}, "erode", W2_ERODE, "minA", W2_MINA, "raster", W2_RASTER, "hot_full", W2_HOTFULL, "skip", sorted(W2_SKIP))

if __name__ == "__main__":
    cmd, *a = sys.argv[1:]
    if cmd == "refs": print(",".join(refs(a[0], a[1])))
    else: {"cut": cut, "strip": strip, "freeze": freeze}[cmd](*a)
