"""copper_repair.py <board_dump.json> <copper plan spec.json> <placed board cu_dump.json> <constraints.json> <out dump.json> [round]
One round of copper-aware placement repair. The copper plan (tools/copper/plan_copper.py) reports each power-net
terminal it could not join ("no path", "path winds"). For each, this writes a no-footprint keep-out into a copy of
the board dump along the straight line from the terminal's pads to the nearest pad of the same net on a joined
terminal, as wide as the current needs plus room, from the edge of one part to the edge of the other. place_pack.py
run on that dump from the same placement (PLACE_START, BLOCK_FLOORPLAN) then moves the small parts out of the way,
and the copper is planned again.

Why: on Monolith round 2 (a 73 % full top side) every placement inside the reviewed boxes left 2 to 4 power paths
with no room, and which ones changed from seed to seed: the parts in the way are small and could sit elsewhere.
Keep-outs from earlier rounds in the input dump stay, so rounds add up."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "copper"))
from roles import Design, width_mm
ROOM_MM = 0.6        # beyond the copper width, both sides together: clearance
MARGIN_MM = 0.3      # the corridor starts this far outside each end part's pads

def main(dumpf, specf, cuf, consf, outf, rnd="1"):
    D = json.load(open(dumpf)); S = json.load(open(specf))["report"]["nets"]; P = json.load(open(cuf)); d = Design(cuf, consf)
    pads = {}
    for p in P["pads"]:
        if p.get("npth"): continue
        xs = [c[0] for L in p["shapes"].values() for r in L for c in r["ring"]] or [p["x"]]; ys = [c[1] for L in p["shapes"].values() for r in L for c in r["ring"]] or [p["y"]]
        pads.setdefault(p["ref"], []).append(dict(net=p["net"], x=p["x"], y=p["y"], box=(min(xs), min(ys), max(xs), max(ys)), layers=list(p["shapes"])))
    def pbox(ref):
        b = [q["box"] for q in pads[ref]]; return (min(v[0] for v in b) - MARGIN_MM, min(v[1] for v in b) - MARGIN_MM, max(v[2] for v in b) + MARGIN_MM, max(v[3] for v in b) + MARGIN_MM)
    def inside(b, x, y): return b[0] <= x <= b[2] and b[1] <= y <= b[3]
    side = {f["ref"]: f["layer"] for f in P["fps"]}; n = 0
    for net, r in S.items():
        joined = [j.split(" ")[0] for j in r.get("joined", [])]
        for t in r.get("left_to_router", []):
            if "no path" not in t and "winds" not in t: continue
            ref = t.split(" ")[0]; I = r["current_a"]
            A = [q for q in pads.get(ref, []) if q["net"] == net]
            B = [(o, q) for o in (joined or [g["ref"] for g in d.terminals(net) if g["ref"] != ref]) if o != ref for q in pads.get(o, []) if q["net"] == net]
            if not A or not B: continue
            a, (o, b) = min(((u, v) for u in A for v in B), key=lambda uv: math.dist((uv[0]["x"], uv[0]["y"]), (uv[1][1]["x"], uv[1][1]["y"])))
            ax, ay, bx, by = a["x"], a["y"], b["x"], b["y"]; L = math.dist((ax, ay), (bx, by))
            if L < 0.5: continue
            w = width_mm(I) + ROOM_MM; k = max(2, int(L / (w / 2))); ba, bb = pbox(ref), pbox(o); boxes = 0
            for i in range(k + 1):
                x, y = ax + (bx - ax) * i / k, ay + (by - ay) * i / k
                if inside(ba, x, y) or inside(bb, x, y): continue       # the end parts themselves stay
                D.setdefault("keepouts", []).append(dict(name=f"copper repair {rnd}: {net.strip('/')} {ref}-{o}", box=[x - w / 2, y - w / 2, x + w / 2, y + w / 2],
                                                         layers=[side.get(ref, "F.Cu")], no_footprints=True, no_tracks=False, no_vias=False, no_pours=False)); boxes += 1
            if boxes: n += 1; print(f"{net}: {ref} to {o}, {L:.1f} mm, {w:.1f} mm wide, {boxes} boxes")
    json.dump(D, open(outf, "w")); print(f"{n} corridors kept clear -> {outf}")

if __name__ == "__main__":
    main(*sys.argv[1:7])
