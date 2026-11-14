"""zoom.py <run dir> <out.png> <x0,y0,x1,y1> [layer F.Cu|B.Cu] [px per mm, default 40]
A zoomed picture of one window of a screened board (run dir holds cu.kicad_pcb, cu.json, ghost.log):
planned power copper coloured by net, pads grey with their pad number, refs at the part centre, vias as rings,
and every blocked edge of ghost.log drawn as a red line between its two pads (red dot for a pad-to-zone edge).
For the lead and the workers: see what stands round a blocked pin before moving parts."""
import sys, os, json, re, colorsys, zlib
from PIL import Image, ImageDraw
R = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))
sys.path.insert(0, os.path.join(R, "tools/copper"))
from dc_score import load_copper
a = sys.argv[1:]; run, out = a[0], a[1]; x0, y0, x1, y1 = [float(v) for v in a[2].split(",")]
L = a[3] if len(a) > 3 else "F.Cu"; S = float(a[4]) if len(a) > 4 else 40.0
D = json.load(open(os.path.join(run, "cu.json"))); Z, T, V = load_copper(os.path.join(run, "cu.kicad_pcb"))
W, H = int((x1 - x0) * S) + 1, int((y1 - y0) * S) + 1
im = Image.new("RGB", (W, H), (250, 250, 248)); d = ImageDraw.Draw(im, "RGBA")
P = lambda x, y: ((x - x0) * S, (y - y0) * S)
def col(n, al=200):
    if n == "GND": return (90, 90, 90, al)
    h = (zlib.crc32(n.encode()) % 360) / 360; r, g, b = colorsys.hsv_to_rgb(h, 0.65, 0.85); return (int(r * 255), int(g * 255), int(b * 255), al)
inwin = lambda x, y: x0 - 1 <= x <= x1 + 1 and y0 - 1 <= y <= y1 + 1
for o in D["outline"]: d.line([P(*q) for q in o["ring"] + o["ring"][:1]], fill=(0, 0, 0), width=2)
for z in Z:
    if z["layer"] == L and len(z["pts"]) > 2: d.polygon([P(*q) for q in z["pts"]], fill=col(z["net"], 120))
for t in T:
    if t["layer"] == L: d.line([P(*t["a"]), P(*t["b"])], fill=col(t["net"], 220), width=max(1, int(t["w"] * S)))
for k in D["keepouts"]:
    if L in k["layers"]:
        for p in k["poly"]: d.line([P(*q) for q in p["ring"] + p["ring"][:1]], fill=(200, 120, 0, 255), width=1)
padpos = {}
for p in D["pads"]:
    padpos[(p["ref"], p["num"])] = (p["x"], p["y"])
    for r in p["shapes"].get(L, []):
        d.polygon([P(*q) for q in r["ring"]], fill=(200, 200, 200, 150), outline=(60, 60, 60, 255))
    if p["shapes"].get(L) and inwin(p["x"], p["y"]) and p["num"]:
        c = P(p["x"], p["y"]); d.text((c[0] - 4, c[1] - 5), p["num"], fill=(0, 0, 120, 255))
for v in V:
    c = P(v["x"], v["y"]); r = v["size"] / 2 * S; d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=col(v["net"], 255), width=2)
for f in D["fps"]:
    if inwin(f["x"], f["y"]):
        c = P(f["x"], f["y"]); on = f["layer"] == L
        d.text((c[0] - 10, c[1] - 14), f["ref"], fill=(0, 0, 0, 255) if on else (150, 150, 150, 255))
g = os.path.join(run, "ghost.log")
if os.path.exists(g):
    for l in open(g):
        if not l.startswith("GHOSTFAIL"): continue
        m = re.findall(r"Pad (\S+) \[[^\]]*\] of (\S+) on", l)
        pts = [padpos[(r, n)] for n, r in m if (r, n) in padpos]
        if len(pts) == 2: d.line([P(*pts[0]), P(*pts[1])], fill=(255, 0, 0, 255), width=2)
        for q in pts:
            c = P(*q); d.ellipse([c[0] - 5, c[1] - 5, c[0] + 5, c[1] + 5], outline=(255, 0, 0, 255), width=2)
im.save(out); print(out, im.size)
