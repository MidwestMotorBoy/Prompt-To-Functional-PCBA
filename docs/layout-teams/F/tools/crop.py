"""crop.py <dir> <board> x0 y0 x1 y1 out.png [layers=F.Cu,In2.Cu,In3.Cu,B.Cu] [px/mm]
Picture of a board region, one panel per signal layer, every copper item drawn in a colour per net with the net's short
name written on it. Pours are drawn pale, pads dark-edged, vias as rings. A 1 mm grid with coordinates is drawn on top."""
import sys, os, hashlib, colorsys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ml import ML
from PIL import Image, ImageDraw
from shapely.geometry import box
d, b = sys.argv[1:3]; x0, y0, x1, y1 = map(float, sys.argv[3:7]); out = sys.argv[7]
layers = sys.argv[8].split(",") if len(sys.argv) > 8 else ["F.Cu", "In2.Cu", "In3.Cu", "B.Cu"]
S = float(sys.argv[9]) if len(sys.argv) > 9 else 40.0
h = ML(d, b); B = box(x0, y0, x1, y1)
def col(net, pale):
    k = int(hashlib.md5(net.encode()).hexdigest()[:6], 16); hu = (k % 360) / 360.0
    if net == "GND": return (225, 225, 225) if pale else (150, 150, 150)
    r, g, bl = colorsys.hls_to_rgb(hu, 0.86 if pale else 0.5, 0.75); return (int(r * 255), int(g * 255), int(bl * 255))
def short(n): return n.split("/")[-1].replace("USB Port ", "P")[:12] + ("'" + n.split("/")[1][-1] if n.count("/") > 1 else "")
W, H = int((x1 - x0) * S), int((y1 - y0) * S); img = Image.new("RGB", (W * len(layers) + 8 * (len(layers) - 1), H + 14), "white"); D = ImageDraw.Draw(img)
def xy(p, ox): return (ox + (p[0] - x0) * S, 14 + (p[1] - y0) * S)
for li, L in enumerate(layers):
    ox = li * (W + 8); D.text((ox + 2, 1), "%s  x %.1f..%.1f  y %.1f..%.1f" % (L, x0, x1, y0, y1), fill="black")
    its = [h.items[L][int(i)] for i in h.tree[L].query(B)]
    order = {"pour": 0, "pad": 1, "track": 2, "via": 3}
    for g, net, kind, name in sorted(its, key=lambda t: order.get(t[2], 1)):
        gg = g.intersection(B)
        if gg.is_empty: continue
        for poly in (gg.geoms if hasattr(gg, "geoms") else [gg]):
            if poly.geom_type != "Polygon": continue
            D.polygon([xy(p, ox) for p in poly.exterior.coords], fill=col(net, kind == "pour"), outline=(60, 60, 60) if kind in ("pad", "via") else None)
            for r in poly.interiors: D.polygon([xy(p, ox) for p in r.coords], fill="white")
    seen = set()
    for g, net, kind, name in its:
        if kind == "pour" or net in ("GND",): continue
        c = g.representative_point()
        if not B.contains(c): continue
        key = (net, int(c.x * 1.2), int(c.y * 1.2))
        if key in seen: continue
        seen.add(key); D.text(xy((c.x, c.y), ox), short(net), fill="black")
    for gx in range(int(x0) + 1, int(x1) + 1):
        D.line([xy((gx, y0), ox), xy((gx, y1), ox)], fill=(200, 200, 255)); D.text(xy((gx, y0), ox), str(gx), fill=(0, 0, 200))
    for gy in range(int(y0) + 1, int(y1) + 1):
        D.line([xy((x0, gy), ox), xy((x1, gy), ox)], fill=(200, 200, 255)); D.text(xy((x0, gy), ox), str(gy), fill=(0, 0, 200))
img.save(out); print(out, img.size)
