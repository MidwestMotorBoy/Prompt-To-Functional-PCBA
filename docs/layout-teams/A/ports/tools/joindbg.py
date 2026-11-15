"""joindbg.py <bare.json> [x0,y0,x1,y1]: run the copper planner unchanged and print every return_join it draws
(the GND pin, path start/end, length) inside the box, so you can see which fine-pitch GND pin's join walls which pins."""
import sys, json
sys.path.insert(0, '/home/claude/repo/tools/copper'); import plan_copper as pc
C = '/home/claude/repo/tools/floorplan/example/monolith/constraints.json'
box = tuple(map(float, sys.argv[2].split(','))) if len(sys.argv) > 2 else (-1e9, -1e9, 1e9, 1e9)
pl = pc.Planner(sys.argv[1], C, None, escape=0.4, grow=1.5, mirror=3)
orig_join = pl.return_join; orig_path = pl.path; last = {}
def path(*a, **k):
    r = orig_path(*a, **k); last['p'] = r[0]; return r
def rj(net, L, sh):
    last['p'] = None; ok = orig_join(net, L, sh); c = sh.centroid
    if box[0] <= c.x <= box[2] and box[1] <= c.y <= box[3]:
        p = last['p']; e = pl.xy(*p[-1]) if p else None
        print(f"join {net} {L} pad ({c.x:.2f},{c.y:.2f}) drawn={ok} len={len(p)*pc.RES if p else None:} end={tuple(round(v,2) for v in e) if e else None}")
    return ok
pl.path = path; pl.return_join = rj
spec = pl.run(); rp = spec['report']['return_pads']
print('joined', rp.get('joined_on_layer')); print('left', rp['left_to_router'])
