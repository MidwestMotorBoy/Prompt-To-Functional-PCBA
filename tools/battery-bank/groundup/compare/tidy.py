"""Track tidiness per net: what a person sees at a glance and no solver scores.

For every net that is routed with tracks (nets with a zone fill are left out, their tracks are only stubs):
  length   total track length, mm
  mst      length of the shortest tree over the net's pads (straight lines), mm
  detour   length / mst          1.0 to about 1.4 is a direct route with 45 degree corners
  segs     track segments, and how many are shorter than 0.2 mm (staircase steps of a grid router)
  bends    direction changes along the tracks
  vias, layers
  widths   how many track widths the net uses; wsteps: places where two widths meet; wsteps_mid: those further than
           1.6 mm from every pad of the net (a step at a pad is a pin-escape neck, one out in the run reads as random)
  offangle segments over 0.3 mm that are not at a multiple of 45 degrees

PCB=<board> TAG=<tag> python tidy.py [N]     prints the N worst nets (default 25) and writes tidy_<TAG>.json
"""
import os, sys, math, json, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '../../../../docs/reviews/2026-10-30-routed-board/tools'))
import board as B
TAG = os.environ.get('TAG', 'x'); NW = int(sys.argv[1]) if len(sys.argv) > 1 else 25
def _area(pts): return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))) / 2
_za = collections.Counter()
for z in B.ZON:
    if z['net']: _za[z['net']] += sum(_area(p) for _, p in z['fills'])
zoned = {n for n, a in _za.items() if a > 3.0}       # a real pour; teardrops are zones too and stay far below this
pads = collections.defaultdict(list); segs = collections.defaultdict(list); vias = collections.Counter()
for fp in B.FP:
    for p in fp['pads']:
        if p['net']: pads[p['net']].append((p['x'], p['y'], fp['ref'] or '?', p['num']))
for s in B.SEG: segs[s['net']].append(s)
for v in B.VIA: vias[v['net']] += 1
def mst(pts):
    pts = list({(round(x, 3), round(y, 3)) for x, y in pts})
    if len(pts) < 2: return 0.0
    d = [math.hypot(pts[0][0] - p[0], pts[0][1] - p[1]) for p in pts]; used = [False] * len(pts); used[0] = True; tot = 0.0
    for _ in range(len(pts) - 1):
        j = min((i for i in range(len(pts)) if not used[i]), key=lambda i: d[i]); tot += d[j]; used[j] = True
        for i in range(len(pts)):
            if not used[i]: d[i] = min(d[i], math.hypot(pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]))
    return tot
def offangle(ss):
    n = 0
    for s in ss:
        if B.seglen(s) > 0.3:
            a = math.degrees(math.atan2(s['y2'] - s['y1'], s['x2'] - s['x1'])) % 45
            if min(a, 45 - a) > 1.0: n += 1
    return n
def wsteps(ss, pp=()):
    """places where two widths meet on one layer: (all, those further than 1.6 mm from every pad of the net).
    A step next to a pad is a neck at a pin escape; one out in the run is the kind that reads as random."""
    e = collections.defaultdict(set)
    for s in ss:
        e[(s['layer'], round(s['x1'], 3), round(s['y1'], 3))].add(s['w']); e[(s['layer'], round(s['x2'], 3), round(s['y2'], 3))].add(s['w'])
    st = [k for k, v in e.items() if len(v) > 1]
    return len(st), sum(1 for l, x, y in st if all(math.hypot(p[0] - x, p[1] - y) > 1.6 for p in pp))
def bends(ss):
    ends = collections.defaultdict(list)
    for s in ss:
        a = math.atan2(s['y2'] - s['y1'], s['x2'] - s['x1'])
        ends[(s['layer'], round(s['x1'], 3), round(s['y1'], 3))].append(a); ends[(s['layer'], round(s['x2'], 3), round(s['y2'], 3))].append(a + math.pi)
    n = 0
    for k, aa in ends.items():
        if len(aa) == 2:
            d = abs((aa[0] - aa[1] + math.pi) % (2 * math.pi) - math.pi)      # 0 = straight through
            d = abs(math.pi - d)
            if d > 0.05: n += 1
    return n
rows = []
for net, ss in segs.items():
    if not net or net in zoned or len(pads[net]) < 2: continue
    L = sum(B.seglen(s) for s in ss); M = mst([(p[0], p[1]) for p in pads[net]])
    rows.append(dict(net=net, pads=len(pads[net]), length=L, mst=M, detour=L / M if M > 0.5 else 0.0, segs=len(ss),
                     short=sum(1 for s in ss if B.seglen(s) < 0.2), bends=bends(ss), vias=vias[net], layers=len({s['layer'] for s in ss}), widths=len({s['w'] for s in ss}), wsteps=wsteps(ss, pads[net])[0], wsteps_mid=wsteps(ss, pads[net])[1], offangle=offangle(ss),
                     excess=max(L - 1.2 * M, 0.0)))
tot = dict(nets=len(rows), length=sum(r['length'] for r in rows), mst=sum(r['mst'] for r in rows), segs=sum(r['segs'] for r in rows),
           short=sum(r['short'] for r in rows), bends=sum(r['bends'] for r in rows), vias=sum(r['vias'] for r in rows),
           over15=sum(1 for r in rows if r['detour'] > 1.5 and r['mst'] > 2), over2=sum(1 for r in rows if r['detour'] > 2.0 and r['mst'] > 2),
           excess=sum(r['excess'] for r in rows), one_width=sum(1 for r in rows if r['widths'] == 1), wsteps=sum(r['wsteps'] for r in rows), wsteps_mid=sum(r['wsteps_mid'] for r in rows), offangle=sum(r['offangle'] for r in rows))
tot['detour'] = tot['length'] / tot['mst']; tot['bends_per_mm'] = tot['bends'] / tot['length']
json.dump(dict(total=tot, nets=rows), open(os.path.join(HERE, f'tidy_{TAG}.json'), 'w'), indent=0)
print(TAG, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in tot.items()})
for r in sorted(rows, key=lambda r: -r['excess'])[:NW]:
    print(f"  {r['net'][-28:]:28s} pads {r['pads']:2d}  {r['length']:6.1f} mm / mst {r['mst']:5.1f} = {r['detour']:4.2f}  segs {r['segs']:3d} ({r['short']} short)  bends {r['bends']:3d}  vias {r['vias']}  layers {r['layers']}")
