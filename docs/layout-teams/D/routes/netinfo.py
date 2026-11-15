"""netinfo.py <dir> <board> <net> ...: pads (with layer and centre) and copper pieces of each net."""
import sys; sys.path.insert(0, '../tools')
from mroute import MR
from shapely.ops import unary_union
m = MR(sys.argv[1], sys.argv[2])
for net in sys.argv[3:]:
    print(net, m.cls(net))
    for i, c in enumerate(m.clusters(net)):
        pads = sorted({(name, L[:-3], round(g.centroid.x, 2), round(g.centroid.y, 2)) for L in c for g in c[L] for geo, n, kind, name in m.items[L] if kind == "pad" and n == net and geo.equals(g)})
        b = unary_union([g for gs in c.values() for g in gs]).bounds
        print("  piece %d (%.1f, %.1f)-(%.1f, %.1f): %s" % (i, *b, pads))
