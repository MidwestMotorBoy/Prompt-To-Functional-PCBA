"""viadbg.py <bare.json> x,y [x,y ...] : run the copper planner (tools/copper/plan_copper.py, unchanged) and, when the
return step tries to place a via for a pad centred at one of the given points, print why each candidate site within
1.2 mm is refused (novia / room on F / room on B / hole pitch / track / link). Explains 'joined_on_layer' and
'left_to_router' GND pins of fine-pitch ICs."""
import sys, math, json, numpy as np
sys.path.insert(0, '/home/claude/repo/tools/copper'); import plan_copper as pc
from shapely.geometry import Point, LineString, Polygon
C = '/home/claude/repo/tools/floorplan/example/monolith/constraints.json'
pts = [tuple(map(float, a.split(','))) for a in sys.argv[2:]]
pl = pc.Planner(sys.argv[1], C, None, escape=0.4, grow=1.5, mirror=3)
orig = pl.place_vias
def pv(net, near, count, layers_ok=None, inside=None, toward=None, link=None, link_w=0.4):
    c = near.centroid; hit = [p for p in pts if math.hypot(p[0] - c.x, p[1] - c.y) < 0.05]
    if hit and link:
        self = pl; r = pc.VIA_D / 2
        roomF = self.room(net, self.outer[0], loose=True); roomB = self.room(net, self.outer[1], loose=True)
        holes = [(v["x"], v["y"], pc.VIA_DRILL) for v in self.vias] + self.drilled
        lroom = self.room(net, link[0], loose=True); pg = link[1]
        print(f"== {net} pad at ({c.x:.3f},{c.y:.3f})")
        for yy in np.arange(c.y - 1.2, c.y + 1.21, 0.2):
            row = ''
            for xx in np.arange(c.x - 1.2, c.x + 1.21, 0.2):
                i, j = int((yy - self.y0) / pc.RES), int((xx - self.x0) / pc.RES); x, y = self.xy(i, j)
                if near.contains(Point(x, y)): row += 'P'; continue
                if self.novia[i, j]: row += 'n'; continue
                if roomF[i, j] < r + pc.RAST_MM: row += 'f'; continue
                if roomB[i, j] < r + pc.RAST_MM: row += 'b'; continue
                if any(math.hypot(x - a, y - b) < max(pc.VIA_PITCH, (d + pc.VIA_DRILL) / 2 + (pc.PAD_HOLE_GAP if d >= .5 else pc.HOLE_GAP)) for a, b, d in holes): row += 'h'; continue
                if any(LineString([t["a"], t["b"]]).distance(Point(x, y)) < r + t["w"] / 2 + self.clr for t in self.tracks if t["net"] != net): row += 't'; continue
                q = pg.exterior.interpolate(pg.exterior.project(Point(x, y)))
                q = LineString([(q.x, q.y), pg.centroid.coords[0]]).interpolate(min(0.1, q.distance(pg.centroid)))
                seg = LineString([(q.x, q.y), (x, y)]); bad = False
                for k in range(int(seg.length / 0.05) + 1):
                    pt = seg.interpolate(k * 0.05)
                    if pg.contains(pt): continue
                    if lroom[int((pt.y - self.y0) / pc.RES), int((pt.x - self.x0) / pc.RES)] < link_w / 2 + pc.RAST_MM: bad = True; break
                row += 'l' if bad else '.'
            print(f"  y {yy:7.2f} x {c.x-1.2:.2f}.. {row}")
    out = orig(net, near, count, layers_ok, inside, toward, link, link_w)
    if hit: print('  placed', [(v['x'], v['y']) for v in out])
    return out
pl.place_vias = pv
spec = pl.run(); print('return pads', json.dumps(spec['report']['return_pads'])[:600])
