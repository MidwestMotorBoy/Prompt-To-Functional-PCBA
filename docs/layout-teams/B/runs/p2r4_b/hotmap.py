"""hotmap.py: hot-loop pours (plan board) near the Port 2 corner, and a test of candidate via spots."""
import sys, os
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/B/tools')
import pinlib
from shapely.geometry import Point, box
D, G, _ = pinlib.load_board('runs/p2-m6/cu.kicad_pcb', 'runs/p2-m6/cu.json')
win = box(78, 78, 97, 100)
for L in ('F.Cu', 'B.Cu'):
    for n, k, g, _ in G.items[L]:
        if k == 'hotzone' and g.intersects(win):
            b = g.intersection(win).bounds
            print(L, n, 'bounds in window %.2f,%.2f %.2f,%.2f area %.1f' % (*b, g.intersection(win).area))
pts = [tuple(map(float, a.split(','))) for a in sys.argv[1:]]
for x, y in pts:
    v = Point(x, y).buffer(0.225)
    hits = [(L, n, round(g.distance(Point(x, y)) - 0.225, 3)) for L in ('F.Cu', 'B.Cu') for n, k, g, _ in G.items[L] if k == 'hotzone' and g.distance(Point(x, y)) < 1.5]
    print('via %.3f,%.3f:' % (x, y), hits)
