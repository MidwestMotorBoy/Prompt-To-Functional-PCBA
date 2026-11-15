"""diag.py <dir> <board>: for every net still in pieces, what is in the way (routes of any net that a path would have to cross)."""
import sys; sys.path.insert(0, '../tools')
from mroute import MR
from shapely.ops import unary_union
m = MR(sys.argv[1], sys.argv[2])
nets = sorted({n for L in m.items for _, n, kind, _ in m.items[L] if n and n not in ("GND", "<keepout>")})
for net in nets:
    cs = m.clusters(net)
    for small in cs[1:]:
        b = [round(v, 1) for v in unary_union([g for gs in small.values() for g in gs]).bounds]
        r = m.join(net, small, cs[0], w=0.15, margin=9.0, quiet=True, ghost=set(nets) - {net})
        print(net, b, '->', r[1] if r else 'WALLED by pads / power pours / board edge even with every route gone', flush=True)
