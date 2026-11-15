"""plan_dbg.py <bare.json> <net>: run tools/copper/plan_copper.py's planner (imported, unchanged) and print why the
detour (B.Cu corridor) of each terminal of <net> fails: via count placed at the pad, corridor path length."""
import sys, os
R = '/home/claude/repo'; sys.path.insert(0, f'{R}/tools/copper')
import plan_copper as pc
NET = sys.argv[2]
orig_det = pc.Planner.detour; orig_pv = pc.Planner.place_vias; orig_path = pc.Planner.path
st = {}
def pv(self, net, near, count, *a, **k):
    out = orig_pv(self, net, near, count, *a, **k)
    if net == NET and st.get('in'): print(f'   place_vias want {count} got {len(out)} near {[round(v,2) for v in near.bounds]} inside={k.get("inside") is not None}')
    return out
def path(self, net, L, *a, **k):
    out = orig_path(self, net, L, *a, **k)
    if net == NET and st.get('in'): print(f'   path on {L}: {"none" if out[0] is None else round(self.plen(out[0]),1)} mm tight={k.get("tight")}')
    return out
def det(self, net, L, gp, w, I, tree):
    st['in'] = net == NET
    if st['in']: print(f' detour {net} pad {[round(v,2) for v in gp.bounds]} w={w:.2f} I={I}')
    r = orig_det(self, net, L, gp, w, I, tree); st['in'] = False
    if net == NET: print('  ->', r)
    return r
pc.Planner.detour = det; pc.Planner.place_vias = pv; pc.Planner.path = path
pl = pc.Planner(sys.argv[1], f'{R}/tools/floorplan/example/monolith/constraints.json', None, escape=0.4, grow=1.5, mirror=3)
spec = pl.run(); print(spec['report']['nets'][NET])
