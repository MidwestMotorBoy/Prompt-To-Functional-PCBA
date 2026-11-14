"""detour_peek.py <run dir> <net> <out.png> <x0,y0,x1,y1> [--escape=0.4]
Runs the shared copper planner (imported, unchanged) on a run's bare.json + constraints and, for every detour the
planner tries for <net>, prints the start vias, the number of landing cells over the tree, the nearest landing
distance and the other-layer path length (the planner draws a detour only up to DETOUR_MAX_MM), and draws the other
layer at that moment: obstacles dark, planned copper coloured, landing cells blue, the path red, start vias yellow."""
import sys, os, json, math
R = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))
sys.path.insert(0, os.path.join(R, "tools/copper"))
import plan_copper as pc
import numpy as np
from scipy import ndimage
from shapely.geometry import Point
from shapely.ops import unary_union
from PIL import Image
a = [x for x in sys.argv[1:] if not x.startswith("--")]; o = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
run, NET, out = a[0], a[1], a[2]; X0, Y0, X1, Y1 = [float(v) for v in a[3].split(",")]
cons = os.path.join(run, "constraints_part.json")
if not os.path.exists(cons): cons = os.path.join(R, "tools/floorplan/example/monolith/constraints.json")
orig = pc.Planner.detour; k = [0]
def detour(self, net, L, gp, w, I, tree):
    if net != NET: return orig(self, net, L, gp, w, I, tree)
    Lo = [l for l in self.outer if l != L][0]; n = pc.vias_for(I); r = pc.VIA_D / 2; c = gp.centroid
    vs = self.place_vias(net, gp, n, link=(L, gp))
    print(f"detour at {c.x:.2f},{c.y:.2f}: start vias {[(v['x'], v['y']) for v in vs]}")
    if vs:
        vg = unary_union([Point(v["x"], v["y"]).buffer(r, 8) for v in vs]); start = self.raster(vg)
        ok = tree & ~self.novia & ~ndimage.binary_dilation(start, iterations=int(1.5 / pc.RES))
        for l in self.outer: ok &= self.room(net, l, loose=True) >= r + pc.RAST_MM
        ok = ndimage.binary_erosion(ok, iterations=2)
        pth = None
        if ok.any():
            idx = np.argwhere(ok); d = min(math.hypot(*(np.array(self.xy(i, j)) - (c.x, c.y))) for i, j in idx); print(f"  landing cells {int(ok.sum())}, nearest {d:.2f} mm")
            near = ndimage.binary_dilation(start | ok, iterations=int(pc.NEAR_TERM_MM / pc.RES))
            pth, rr = self.path(net, Lo, start, ok, w, near)
            if pth is None: pth, rr = self.path(net, Lo, start, ok, w, near, tight=True)
            print("  path", None if pth is None else f"{self.plen(pth):.2f} mm (limit {pc.DETOUR_MAX_MM})", "end", None if pth is None else tuple(round(v, 2) for v in self.xy(*pth[-1])))
        else: print("  no landing cells")
        i0, i1 = int((Y0 - self.y0) / pc.RES), int((Y1 - self.y0) / pc.RES); j0, j1 = int((X0 - self.x0) / pc.RES), int((X1 - self.x0) / pc.RES)
        rm = self.room(net, Lo)[i0:i1, j0:j1]; cu = self.cu[Lo][i0:i1, j0:j1]; pn = self.padnet[Lo][i0:i1, j0:j1]; nid = self.netid[net]
        img = np.full(rm.shape + (3,), 250, np.uint8); img[rm >= pc.MIN_W / 2] = (215, 230, 255)
        img[(cu >= 0) & (cu != nid)] = (150, 150, 150); img[cu == nid] = (60, 200, 60)
        img[(pn >= 0) & (pn != nid)] = (40, 40, 40); img[pn == nid] = (200, 120, 0)
        vm = self.viamap[i0:i1, j0:j1]; img[(vm >= 0) & (vm != nid)] = (120, 0, 120)
        img[ok[i0:i1, j0:j1]] = (30, 60, 230); img[(tree & ~ok)[i0:i1, j0:j1]] = (120, 220, 240)
        if pth:
            for i, j in pth:
                if i0 <= i < i1 and j0 <= j < j1: img[i - i0, j - j0] = (230, 0, 0)
        img[start[i0:i1, j0:j1]] = (255, 220, 0)
        k[0] += 1; Image.fromarray(img).resize(((j1 - j0) * 4, (i1 - i0) * 4), Image.NEAREST).save(out.replace(".png", f"_{k[0]}.png"))
        self.unvia(vs)
    return orig(self, net, L, gp, w, I, tree)
pc.Planner.detour = detour
pl = pc.Planner(os.path.join(run, "bare.json"), cons, None, escape=float(o.get("escape", 0.4)), grow=1.5, mirror=3)
pl.run()
print(json.dumps(pl.report.get("nets", {}).get(NET), default=str)[:800])
