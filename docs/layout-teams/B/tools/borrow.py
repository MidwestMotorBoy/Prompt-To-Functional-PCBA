"""borrow.py <board A.kicad_pcb> <A's plan board (cu.kicad_pcb)> <out hand.json> <net> [<net> ...] [--no-lift]
Team B, phase 2 round 3 (lead). Takes the ROUTED copper of the named nets from board A (every track and via of the net
that is not in A's plan board) and writes it as a tracks.json for tools/handroute.py, with the nets in "lift": on board
B handroute.py then removes B's routed copper of those nets and lays A's instead, after its exact clearance check
(any fault: nothing written). For a connection that one route of a plan made and another did not: same placement and
plan, so the copper of the route that made it often still fits. Check first with handroute.py ... --check."""
import sys, json
sys.path.insert(0, __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '../../../../tools/copper'))
from dc_score import load_copper
A = [a for a in sys.argv[1:] if not a.startswith('--')]; lift = '--no-lift' not in sys.argv
if len(A) < 4: print(__doc__); sys.exit(2)
b, keep, out, nets = A[0], A[1], A[2], A[3:]
Z, T, V = load_copper(b); Zk, Tk, Vk = load_copper(keep)
r = lambda p: (round(p[0], 4), round(p[1], 4))
kt = {(t['net'], t['layer'], r(t['a']), r(t['b'])) for t in Tk}; kv = {(v['net'], r((v['x'], v['y']))) for v in Vk}
J = {'board': b, 'note': 'routed copper of %s borrowed from %s' % (', '.join(nets), b), 'tracks': [], 'vias': []}
if lift: J['lift'] = nets
for t in T:
    if t['net'] in nets and (t['net'], t['layer'], r(t['a']), r(t['b'])) not in kt:
        J['tracks'].append({'net': t['net'], 'layer': t['layer'], 'w': t['w'], 'points': [list(t['a']), list(t['b'])]})
for v in V:
    if v['net'] in nets and (v['net'], r((v['x'], v['y']))) not in kv:
        J['vias'].append({'net': v['net'], 'x': v['x'], 'y': v['y']})
json.dump(J, open(out, 'w'), indent=0)
print('%s: %d tracks, %d vias of %s' % (out, len(J['tracks']), len(J['vias']), nets))
