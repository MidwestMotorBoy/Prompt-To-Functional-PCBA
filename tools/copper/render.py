"""render.py <board.kicad_pcb, filled> <cu_dump.json> <out.png> [layer, default F.Cu] [x0,y0,x1,y1 window] [px per mm, default 12]
A picture of one copper layer: filled zones and tracks coloured by net (planes left out), pads in grey with their
own net's colour where they are power, vias as rings. For a person checking the generated power copper by eye."""
import sys, os, json, colorsys, zlib
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dc_score import load_copper
a = sys.argv[1:]; pcb, dump, out = a[:3]; L = a[3] if len(a) > 3 else "F.Cu"; S = float(a[5]) if len(a) > 5 else 12.0
D = json.load(open(dump)); Z, T, V = load_copper(pcb)
xs = [x for o in D["outline"] for x, _ in o["ring"]]; ys = [y for o in D["outline"] for _, y in o["ring"]]
x0, y0, x1, y1 = [float(v) for v in a[4].split(",")] if len(a) > 4 and a[4] != "-" else (min(xs), min(ys), max(xs), max(ys))
W, H = int((x1 - x0) * S) + 1, int((y1 - y0) * S) + 1; im = Image.new("RGB", (W, H), (250, 250, 248)); d = ImageDraw.Draw(im, "RGBA")
P = lambda x, y: ((x - x0) * S, (y - y0) * S)
def col(n, a=200):
    if n == "GND": return (90, 90, 90, a)
    h = (zlib.crc32(n.encode()) % 360) / 360; r, g, b = colorsys.hsv_to_rgb(h, 0.65, 0.85); return (int(r * 255), int(g * 255), int(b * 255), a)
for o in D["outline"]: d.line([P(*q) for q in o["ring"] + o["ring"][:1]], fill=(0, 0, 0), width=2)
big = {}
for z in Z:
    if z["layer"] == L and len(z["pts"]) > 2:
        big[z["net"]] = big.get(z["net"], 0) + 1
for z in Z:
    if z["layer"] != L or len(z["pts"]) < 3: continue
    d.polygon([P(*q) for q in z["pts"]], fill=col(z["net"], 150))
for t in T:
    if t["layer"] == L: d.line([P(*t["a"]), P(*t["b"])], fill=col(t["net"], 230), width=max(1, int(t["w"] * S)))
for p in D["pads"]:
    for r in p["shapes"].get(L, []):
        d.polygon([P(*q) for q in r["ring"]], fill=(200, 200, 200, 120), outline=(60, 60, 60, 255))
for v in V:
    c = P(v["x"], v["y"]); r = v["size"] / 2 * S; d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=col(v["net"], 255), width=2)
# labels: each power zone's net name at its largest piece
done = set()
for z in sorted(Z, key=lambda z: -len(z["pts"])):
    if z["layer"] != L or z["net"] in done or z["net"] == "GND" or len(z["pts"]) < 3: continue
    done.add(z["net"]); cx = sum(q[0] for q in z["pts"]) / len(z["pts"]); cy = sum(q[1] for q in z["pts"]) / len(z["pts"])
    d.text(P(cx, cy), z["net"].split("/")[-1], fill=(0, 0, 0, 255))
im.save(out); print(out, im.size)
