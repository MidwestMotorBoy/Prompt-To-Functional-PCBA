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

def cut(dumpf, clf, itf, rl, pre):
    S = set(rl.split(",")); keep = lambda r: r in S or r.rstrip("0123456789") in FIX
    D = json.load(open(dumpf)); D["fps"] = [f for f in D["fps"] if keep(f["ref"])]; D["pads"] = [p for p in D["pads"] if keep(p["ref"])]
    CL = {k: {r: v for r, v in parts.items() if r in S} for k, parts in json.load(open(clf)).items()}; CL = {k: v for k, v in CL.items() if v}
    it = json.load(open(itf)); have = lambda t: keep(t.split(".")[0])
    it["near"] = [s for s in it.get("near", []) if keep(s["part"]) and all(have(t) for t in s["to"])]
    it["keepapart"] = []
    for x, o in ((D, "dump"), (CL, "clusters"), (it, "intent")): json.dump(x, open(f"{pre}_{o}.json", "w"))
    print(f"skeleton: {len(S)} parts in {len(CL)} sections -> {pre}_*.json")

def strip(cuf, rl, outf):
    S = set(rl.split(",")); keep = lambda r: r in S or r.rstrip("0123456789") in FIX
    P = json.load(open(cuf)); P["fps"] = [f for f in P["fps"] if keep(f["ref"])]; P["pads"] = [p for p in P["pads"] if keep(p["ref"])]
    json.dump(P, open(outf, "w")); print(f"{len(P['fps'])} parts kept -> {outf}")

def freeze(dumpf, clf, plf, specf, pre, room="0.3"):
    from shapely.geometry import Polygon, box as sbox
    from shapely.ops import unary_union
    room = float(room); D = json.load(open(dumpf)); PL = json.load(open(plf)); CL = json.load(open(clf)); spec = json.load(open(specf))
    fp = {f["ref"]: f for f in D["fps"]}; S = {r for r in PL if r.rstrip("0123456789") not in FIX and r in fp}
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
        g = unary_union([Polygon(r["ring"], r.get("holes", [])).buffer(room) for z in spec["zones"] if z["layer"] == L and "plane" not in z["kinds"] for r in z["polys"]])
        if g.is_empty: continue
        x0, y0, x1, y1 = g.bounds
        for yy in np.arange(y0, y1, G):
            run = None
            for xx in np.arange(x0, x1 + G, G):
                hit = xx <= x1 and g.intersects(sbox(xx, yy, xx + G, yy + G))
                if hit and run is None: run = xx
                if not hit and run is not None:
                    D.setdefault("keepouts", []).append(dict(name="skeleton copper", box=[run, yy, xx, yy + G], layers=[L], no_footprints=True, no_tracks=False, no_vias=False, no_pours=False)); n += 1; run = None
    CL = {k: {r: v for r, v in parts.items() if r not in S} for k, parts in CL.items()}; CL = {k: v for k, v in CL.items() if v}
    json.dump(D, open(f"{pre}_dump.json", "w")); json.dump(CL, open(f"{pre}_clusters.json", "w"))
    print(f"{len(S)} skeleton parts fixed, {n} copper keep-out boxes -> {pre}_dump.json, {pre}_clusters.json")

if __name__ == "__main__":
    cmd, *a = sys.argv[1:]
    if cmd == "refs": print(",".join(refs(a[0], a[1])))
    else: {"cut": cut, "strip": strip, "freeze": freeze}[cmd](*a)
