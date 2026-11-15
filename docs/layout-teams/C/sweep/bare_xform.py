"""bare_xform.py <template bare.json> <placement.json> <out bare.json>
A cu_dump of the placed bare board WITHOUT KiCad: moves every pad (centre and copper polygons) of the template's
cu_dump (hand placement, e.g. /home/claude/work/C/hand_screen/bare.json) to the placement's pose. A 4th element
"F"/"B" that differs from the template side mirrors local x before the turn and swaps the copper layers
(F<->B, In1<->In4, In2<->In3) as KiCad's flip does. Footprint-owned keep-outs are NOT moved (on Monolith the only
ones belong to fixed parts; checked against a KiCad-made bare.json, see sweep/README.md).
Used by sweep.py 'plan' to run the copper planner on the host (about 1 min) and predict power opens."""
import json, sys
FLIP = {"F.Cu": "B.Cu", "B.Cu": "F.Cu", "In1.Cu": "In4.Cu", "In4.Cu": "In1.Cu", "In2.Cu": "In3.Cu", "In3.Cu": "In2.Cu"}

def rot(x, y, k):
    for _ in range(k % 4): x, y = -y, x
    return x, y

def xform(b, P):
    fp = {f["ref"]: f for f in b["fps"]}; pose = {}
    for r, v in P.items():
        if r not in fp: continue
        f = fp[r]; s0 = f["layer"][0]; s = v[3] if len(v) > 3 else s0
        pose[r] = (f["x"], f["y"], v[0], v[1], int(v[2]) // 90, s != s0)
    for r, (x0, y0, x, y, k, mir) in pose.items():
        f = fp[r]; f["x"], f["y"] = x, y; f["rot"] = (f["rot"] + 90 * k) % 360       # rot: informational only
        if mir: f["layer"] = FLIP.get(f["layer"], f["layer"])
    def tf(r, px, py):
        x0, y0, x, y, k, mir = pose[r]; lx, ly = px - x0, py - y0
        if mir: lx = -lx
        dx, dy = rot(lx, ly, k); return round(x + dx, 4), round(y + dy, 4)
    for p in b["pads"]:
        r = p["ref"]
        if r not in pose: continue
        p["x"], p["y"] = tf(r, p["x"], p["y"]); mir = pose[r][5]; sh = {}
        for lay, polys in p["shapes"].items():
            sh[FLIP.get(lay, lay) if mir else lay] = [dict(ring=[list(tf(r, *q)) for q in pl["ring"]], holes=[[list(tf(r, *q)) for q in h] for h in pl["holes"]]) for pl in polys]
        p["shapes"] = sh
    return b

if __name__ == "__main__":
    b = json.load(open(sys.argv[1])); P = json.load(open(sys.argv[2])); json.dump(xform(b, P), open(sys.argv[3], "w"))
