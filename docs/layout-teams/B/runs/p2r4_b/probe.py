"""probe.py <board> x,y ... : filled zones (net, layer) that contain each point, and whether the plan board's hot-loop pours do"""
import sys
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/B/tools'); sys.path.insert(0, '/home/claude/repo/tools/copper')
import pinlib
from dc_score import load_copper
from shapely.geometry import Point, Polygon
Z, T, V = load_copper(sys.argv[1])
D, G, _ = pinlib.load_board('runs/p2-m6/cu.kicad_pcb', 'runs/p2-m6/cu.json')
for a in sys.argv[2:]:
    x, y = map(float, a.split(',')); p = Point(x, y)
    zs = sorted({(z['net'], z['layer']) for z in Z if len(z['pts']) > 2 and Polygon(z['pts']).buffer(0).distance(p) < 0.4})
    hot = [(L, n, round(g.distance(p), 2)) for L in ('F.Cu', 'B.Cu') for n, k, g, _ in G.items[L] if k == 'hotzone' and g.distance(p) < 0.6]
    print(a, 'zones within 0.4:', zs, 'hot within 0.6:', hot)
