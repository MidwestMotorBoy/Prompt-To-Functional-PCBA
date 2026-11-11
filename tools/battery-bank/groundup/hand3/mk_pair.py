"""mk_pair.py cu.json mover_net_suffix keepbox out_del.json out_corr.json partner_key partner_side: delete the mover's long haul (everything
outside keepbox), write the partner's path (from ../cmp/senspair_dbg.json) as the corridor polyline."""
import json, sys
sys.path.insert(0, '.')
from seglib import *
d = json.load(open(sys.argv[1])); net = sys.argv[2]; kb = [float(v) for v in sys.argv[3].split(',')]
spec = []; add = []
for L in ('F', 'In2', 'In3', 'In4', 'B'):
    it, ex = dels(d, net, L, lambda t: not inbox(t, kb)); spec += it; add += readd(ex)
    if it: print(L, len(it), 'del points, collateral', len(ex))
for v in vias(d, net):
    if not (kb[0] <= v['x'] <= kb[2] and kb[1] <= v['y'] <= kb[3]): spec.append(delvia(v))
json.dump(spec + add, open(sys.argv[4], 'w'))
s = json.load(open('../cmp/senspair_dbg.json')); o = [q for q in s if q['name'].startswith(sys.argv[6])][0]
json.dump([o[sys.argv[7]]], open(sys.argv[5], 'w')); print('corridor points', len(o[sys.argv[7]]))
