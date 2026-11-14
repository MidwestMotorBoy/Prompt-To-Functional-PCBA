"""yard_check.py <fragment or placement> x0,y0,x1,y1 [--side=F] [--clr=0.15] [--esc=0.4] [--png=out.png]
Can power copper reach a yard? Free room for power copper on one side = everything not within clr+esc of a signal
pad or within clr of any other pad (the planner's rule for grown copper; tracks and vias are not known here).
Prints the free area inside the box and whether that free room connects to the room outside the box (within a 6 mm
frame round it), and where it leaks. All parts of all groups present: the fragment's parts at their spots, every other
part at the template (or pass a stitched placement). For walling an escape yard before running the planner."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blib
from shapely.geometry import box as sbox
from shapely.ops import unary_union
a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict((x[2:].split("=", 1) + [""])[:2] for x in sys.argv[1:] if x.startswith("--"))
B = blib.Board(); F = blib.load_placement(a[0]); W = [float(v) for v in a[1].split(",")]
side = opt.get("side", "F"); clr = float(opt.get("clr", 0.15)); esc = float(opt.get("esc", 0.4))
frame = sbox(W[0] - 6, W[1] - 6, W[2] + 6, W[3] + 6); yard = sbox(*W)
ob = []
for r, P in B.parts.items():
    v = F.get(r)
    for p in B.pads(r, v):
        if side not in p[5]: continue
        b = p[4]
        if b[2] < W[0] - 7 or b[0] > W[2] + 7 or b[3] < W[1] - 7 or b[1] > W[3] + 7: continue
        m = clr + (esc if B.is_signal_net(p[1]) else 0.0)
        ob.append(sbox(*b).buffer(m, 8))
free = frame.difference(unary_union(ob))
# copper narrower than 0.1 mm does not count (raster); open the free room by 0.05
free = free.buffer(-0.05).buffer(0.05)
inside = free.intersection(yard)
print(f"free power-copper room inside the yard: {inside.area:.2f} mm2")
leak = []
for g in getattr(free, "geoms", [free]):
    if g.intersects(yard) and g.intersection(yard).area > 0.01:
        out = g.difference(yard.buffer(0.3))
        if out.area > 0.05:
            leak.append(g); print(f"  LEAK: a free piece of {g.intersection(yard).area:.2f} mm2 in the yard joins {out.area:.1f} mm2 outside; bounds {tuple(round(c, 2) for c in g.intersection(yard.buffer(0.6)).bounds)}")
        else: print(f"  closed piece {g.intersection(yard).area:.2f} mm2 at {tuple(round(c, 2) for c in g.bounds)}")
print("yard closed" if not leak else f"yard open: {len(leak)} leak(s)")
if opt.get("png"):
    from PIL import Image, ImageDraw
    S = 30; x0, y0 = W[0] - 6, W[1] - 6; im = Image.new("RGB", (int((W[2] - W[0] + 12) * S), int((W[3] - W[1] + 12) * S)), "white"); d = ImageDraw.Draw(im)
    P = lambda q: [((x - x0) * S, (y - y0) * S) for x, y in q]
    for g in getattr(free, "geoms", [free]): d.polygon(P(g.exterior.coords), fill=(200, 230, 255) if g not in leak else (255, 190, 190))
    for o in ob: d.polygon(P(o.exterior.coords), outline=(120, 120, 120))
    d.rectangle([(W[0] - x0) * S, (W[1] - y0) * S, (W[2] - x0) * S, (W[3] - y0) * S], outline=(0, 120, 0), width=2)
    im.save(opt["png"])
