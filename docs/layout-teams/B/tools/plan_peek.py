"""plan_peek.py <run dir> <net> <out.png> <x0,y0,x1,y1> [--escape=0.4] [--layer=F.Cu]
Runs the shared copper planner (unchanged, imported) on a screened run's bare.json + constraints_part.json (or
constraints.json) and, right before <net> is planned, saves a picture of the planning raster on the layer: planned
copper by net (GND grey, the net itself green, others colour), pads (dark), cells where <net>'s copper fits with the
escape room (light) and with clearance only (lighter), and the net's terminals (red). For finding why a power net
says 'no path'. Prints the net's report line after the run."""
import sys, os, json, zlib, colorsys
R = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))
sys.path.insert(0, os.path.join(R, "tools/copper"))
import plan_copper as pc
import numpy as np
from PIL import Image
a = [x for x in sys.argv[1:] if not x.startswith("--")]; o = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
run, NET, out = a[0], a[1], a[2]; x0, y0, x1, y1 = [float(v) for v in a[3].split(",")]
LAY = o.get("layer", "F.Cu"); esc = float(o.get("escape", 0.4))
cons = os.path.join(run, "constraints_part.json")
if not os.path.exists(cons): cons = os.path.join(R, "tools/score/constraints.json") if not os.path.exists(os.path.join(run, "constraints.json")) else os.path.join(run, "constraints.json")
orig = pc.Planner.net_step
def peek(self, net):
    if net.strip("/") == NET.strip("/"):
        L = LAY; i0, i1 = int((y0 - self.y0) / pc.RES), int((y1 - self.y0) / pc.RES); j0, j1 = int((x0 - self.x0) / pc.RES), int((x1 - self.x0) / pc.RES)
        nid = self.netid[net]; cu = self.cu[L][i0:i1, j0:j1]; pn = self.padnet[L][i0:i1, j0:j1]
        rm = self.room(net, L)[i0:i1, j0:j1]; rl = self.room(net, L, loose=True)[i0:i1, j0:j1]
        img = np.full(cu.shape + (3,), 250, np.uint8)
        img[rl >= pc.MIN_W / 2] = (225, 235, 255); img[rm >= pc.MIN_W / 2] = (200, 220, 255)
        for n in np.unique(cu[cu >= 0]):
            nm = self.d.board_nets[n]; h = (zlib.crc32(nm.encode()) % 360) / 360; c = [int(v * 255) for v in colorsys.hsv_to_rgb(h, 0.6, 0.85)]
            if nm == "GND": c = (110, 110, 110)
            if n == nid: c = (40, 200, 60)
            img[cu == n] = c
        img[(pn >= 0) & (pn != nid)] = (40, 40, 40); img[pn == nid] = (230, 30, 30)
        r = self.reserve[L][i0:i1, j0:j1]; img[(r >= 0) & (r != nid) & (cu < 0) & (pn < 0)] = (255, 200, 120)
        Image.fromarray(img).resize(((j1 - j0) * 4, (i1 - i0) * 4), Image.NEAREST).save(out)
    return orig(self, net)
pc.Planner.net_step = peek
pl = pc.Planner(os.path.join(run, "bare.json"), cons, None, escape=esc, grow=1.5, mirror=3)
pl.run()
print(json.dumps(pl.report.get("nets", {}).get(NET if NET.startswith("/") else "/" + NET, pl.report.get("nets", {}).get(NET)), default=str)[:1500])
