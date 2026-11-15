"""edbg.py <dir> <board> <net name> <out.png> [x0,y0,x1,y1] [px per mm] [--routes=file] [--layer=0]
Why can a net not be routed: draws the window with, for a 0.15 mm track of this net on the layer,
  white = track centre legal, light red = blocked by pads / pours / board copper, orange = blocked only by routed tracks,
  green dot = a via fits; the net's own copper in blue, each piece numbered."""
import sys, os, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import er, eroute
from PIL import Image, ImageDraw, ImageFont
a = [x for x in sys.argv[1:] if not x.startswith("--")]; O = dict(x[2:].split("=", 1) if "=" in x else (x[2:], "1") for x in sys.argv[1:] if x.startswith("--"))
d, board, net, out = a[0], a[1], a[2], a[3]
W = er.World("%s/%s.e.json" % (d, board), verbose=False)
if "routes" in O: eroute.load_routes(W, O["routes"])
n = W.netid[net]; L = int(O.get("layer", 0))
if len(a) > 4 and a[4] != "-": x0, y0, x1, y1 = [float(v) for v in a[4].split(",")]
else:
    w = W.net_window(n, 1.5); x0, y0 = W.xy(w[0], w[1]); x1, y1 = W.xy(w[2], w[3])
S = float(a[5]) if len(a) > 5 else 40.0
cx0, cy0 = W.cell(x0, y0); cx1, cy1 = W.cell(x1, y1); win = (max(cx0, 0), max(cy0, 0), min(cx1, W.NX), min(cy1, W.NY))
fs, fsd, vs, bd, bdd, vbd = W.masks(n, win, 0.075, ghost=True)
win2, lab, k, cu, thr = W.pieces(n, win)
h, w = fs.shape[1:]
img = np.zeros((h, w, 3), np.uint8); img[:] = (255, 205, 205)
img[fs[L] & bd[L]] = (255, 190, 90); img[fs[L] & ~bd[L]] = (255, 255, 255)
img[(lab[L] > 0)] = (90, 140, 255)
other = (W.As.d1[L, win[1]:win[3], win[0]:win[2]] <= 0.001) & (lab[L] == 0)
img[other] = (120, 120, 120)
dynm = (W.Ad.d1[L, win[1]:win[3], win[0]:win[2]] <= 0.001) & (lab[L] == 0)
img[dynm] = (200, 110, 30)
k_ = max(1, int(round(S * er.G)))
im = Image.fromarray(img).resize((w * k_, h * k_), Image.NEAREST); dr = ImageDraw.Draw(im)
vv = vs & ~vbd
for yy in range(0, h, 4):
    for xx in range(0, w, 4):
        if vv[yy, xx]: dr.ellipse([xx * k_ - 1, yy * k_ - 1, xx * k_ + 2, yy * k_ + 2], fill=(0, 170, 0))
try: f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
except Exception: f = ImageFont.load_default()
for i in range(1, k + 1):
    ys, xs = np.nonzero((lab == i).any(axis=0))
    if len(xs): dr.text((xs.mean() * k_, ys.mean() * k_), str(i), fill=(200, 0, 0), font=f)
for p in W.D["pads"]:
    if x0 <= p["x"] <= x1 and y0 <= p["y"] <= y1 and LAYERS_OK(p) if False else (x0 <= p["x"] <= x1 and y0 <= p["y"] <= y1):
        if er.LAYERS[L] in p["shapes"] or max(p["drill"]) > 0:
            dr.text((((p["x"] - W.X0) / er.G - win[0]) * k_ - 8, ((p["y"] - W.Y0) / er.G - win[1]) * k_ - 6), p["ref"] + "." + p["num"], fill=(0, 0, 0), font=f)
im.save(out); print(out, im.size, "pieces", k, "window", [round(v, 2) for v in (x0, y0, x1, y1)])
