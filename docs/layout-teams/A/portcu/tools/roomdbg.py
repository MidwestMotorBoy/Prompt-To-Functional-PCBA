"""roomdbg.py <bare.json> <x,y of a return pad> <planner options...>: run plan_copper_p with the options and, when the
return step looks for a via at that pad, print the via room grid (mm; a via fits where >= 0.325) on F and B,
x/y -1.2..+1.2 mm round the pad, and which via sites it took. For finding what took a GND pin's via site."""
import sys, math, numpy as np
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/portcu/tools')
import plan_copper_p as pp, plan_copper as pc, plan_copper_a as pa
bare, xy = sys.argv[1], tuple(map(float, sys.argv[2].split(','))); opts = dict(a[2:].split('=', 1) for a in sys.argv[3:])
for k, v in opts.items():
    if k in pp.OPT: pp.OPT[k] = type(pp.OPT[k])(float(v)) if not isinstance(pp.OPT[k], str) else v
pa.SEALED = int(opts.get('sealed', 0)); pa.TAPS = int(opts.get('taps', 0))
pl = pp.PlannerP(bare, '/home/claude/repo/tools/floorplan/example/monolith/constraints.json', None, escape=0.4, grow=1.5, mirror=3)
orig = pl.place_vias
def pv(net, near, count, layers_ok=None, inside=None, toward=None, link=None, link_w=0.4):
    c = near.centroid
    hit = link and abs(c.x - xy[0]) < 0.05 and abs(c.y - xy[1]) < 0.05
    if hit:
        for L in pl.outer:
            rm = pl.room(net, L, loose=True); print(L)
            for y in np.arange(xy[1] - 1.6, xy[1] + 0.81, 0.2):
                i = int((y - pl.y0) / pc.RES); print(' y%.1f ' % y + ' '.join('%5.2f' % rm[i, int((x - pl.x0) / pc.RES)] for x in np.arange(xy[0] - 1.2, xy[0] + 1.21, 0.2)))
        own = {}
        for L in pl.outer:
            for y in np.arange(xy[1] - 1.6, xy[1] + 0.01, 0.4):
                for x in np.arange(xy[0] - 1.2, xy[0] + 1.21, 0.4):
                    i, j = int((y - pl.y0) / pc.RES), int((x - pl.x0) / pc.RES); n = pl.cu[L][i, j]
                    if n >= 0: own.setdefault(L, set()).add(pl.d.board_nets[n])
        print('copper owners near:', own, 'vias of other nets near:', [(v['net'][-8:], v['x'], v['y']) for v in pl.vias if math.hypot(v['x'] - xy[0], v['y'] - xy[1]) < 1.8 and v['net'] != net])
    out = orig(net, near, count, layers_ok, inside, toward, link, link_w)
    if hit: print('placed', [(v['x'], v['y']) for v in out])
    return out
pl.place_vias = pv
pl.run()
