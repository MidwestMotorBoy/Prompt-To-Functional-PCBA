"""runwidth.py cu.json out_spec.json [--only=regex] [--neck=1.5] [--share=0.6]
One width per run. A run is a chain of track segments on one layer between pads, vias and junctions. A width pass
that lowers single segments where a rule objects (widen.py) leaves runs that step 0.25 / 0.4 / 0.3 / 0.6 for no
visible reason. This pass only ever narrows, so every result is legal if the input was:
  - signal, gate-drive and Kelvin nets: the whole run takes its narrowest width; a narrower escape at a pad
    (within --neck mm of the pad along the run) stays as it is;
  - power, high-current and ground tracks: the run takes the widest width that at least --share of its length
    already has; narrower stretches stay as necks, all at the narrowest neck width of the run, and a wide
    stretch under 1 mm between two necks becomes neck too.
With --palette=0.8,0.5,0.3,0.2,0.15 every width of a net that uses more than one width is then rounded down to the
palette, so a net shows a few widths that mean something (trunk, branch, signal, escape) and not seven.
Writes a handadd.py spec of {"setw": [x1, y1, x2, y2], "layer", "net", "w"} items and prints a summary per net."""
import json, sys, math, re, collections
import tidynet as TN
a = [x for x in sys.argv[1:] if not x.startswith('--')]; OPT = dict(x[2:].split('=', 1) for x in sys.argv[1:] if x.startswith('--'))
PAL0 = sorted(float(v) for v in OPT['palette'].split(',')) if 'palette' in OPT else None
d = json.load(open(a[0])); NECK = float(OPT.get('neck', 1.5)); SHARE = float(OPT.get('share', 0.6))
K = lambda x, y: (round(x, 3), round(y, 3)); ln = lambda t: math.hypot(t['x2'] - t['x1'], t['y2'] - t['y1'])
def inpoly(x, y, poly):
    c = False; n = len(poly)
    for i in range(n):
        (xa, ya), (xb, yb) = poly[i], poly[(i + 1) % n]
        if (ya > y) != (yb > y) and x < xa + (y - ya) * (xb - xa) / (yb - ya): c = not c
    return c
by = collections.defaultdict(list)
for t in d['tracks']: by[(t['net'], t['l'])].append(t)
vias = collections.defaultdict(set)
for v in d['vias']: vias[v['net']].add(K(v['x'], v['y']))
pads = collections.defaultdict(list)
for p in d['pads']: pads[p['net']].append(p)
spec = []; rep = collections.defaultdict(lambda: [0, 0, 0.0])
for (net, L), tt in sorted(by.items()):
    if not net or ('only' in OPT and not re.search(OPT['only'], net)): continue
    if len({t['w'] for t in tt}) < 2: continue
    strict = TN.ncls(net) in ('Default', 'Kelvin', 'GateDrive')
    PAL = PAL0 if TN.ncls(net) in ('Default', 'Kelvin', 'GateDrive', 'Power') else None      # ground and high-current stubs keep their drawn widths
    adj = collections.defaultdict(list)
    for t in tt: adj[K(t['x1'], t['y1'])].append(t); adj[K(t['x2'], t['y2'])].append(t)
    onpad = lambda q: any(p['L'].get(L) and inpoly(q[0], q[1], p['L'][L]) for p in pads[net])
    brk = {q for q, ts in adj.items() if len(ts) != 2 or q in vias[net] or onpad(q)}
    seen = set()
    for q0 in sorted(brk):
        for t0 in adj[q0]:
            if id(t0) in seen: continue
            run = []; q = q0; t = t0
            while True:                                   # walk to the next break node
                seen.add(id(t)); run.append(t); q = K(t['x2'], t['y2']) if K(t['x1'], t['y1']) == q else K(t['x1'], t['y1'])
                if q in brk: break
                nx = [u for u in adj[q] if id(u) not in seen]
                if not nx: break
                t = nx[0]
            ws = [u['w'] for u in run]
            if len(set(ws)) < 2:                          # a run in one width: only the palette applies
                if PAL:
                    w1 = max([p for p in PAL if p <= ws[0] + 1e-9] or [ws[0]])
                    if w1 < ws[0] - 1e-9:
                        for u in run: spec.append(dict(setw=[u['x1'], u['y1'], u['x2'], u['y2']], layer=L, net=net, w=w1)); rep[net][0] += 1; rep[net][2] += ln(u)
                continue
            Ls = [ln(u) for u in run]; tot = sum(Ls); new = list(ws)
            if strict:
                # escapes: narrow segments within NECK of a run end that sits on a pad
                keepn = set(); 
                for ends, order in ((q0, range(len(run))), (q, range(len(run) - 1, -1, -1))):
                    if not onpad(ends): continue
                    s = 0.0
                    for i in order:
                        if s + Ls[i] > NECK: break
                        keepn.add(i); s += Ls[i]
                body = [ws[i] for i in range(len(run)) if i not in keepn]
                if not body: continue
                wm = min(body); new = [min(ws[i], wm) if i in keepn else wm for i in range(len(run))]
                # an escape is one stretch of one width from the pad: trim it to its narrow part
                for order in (range(len(run)), range(len(run) - 1, -1, -1)):
                    wn = None
                    for i in order:
                        if i not in keepn: break
                        if new[i] < wm - 1e-9: wn = new[i] if wn is None else min(wn, new[i])
                    hit = False
                    for i in reversed(list(order)):
                        if i in keepn and wn is not None:
                            if new[i] < wm - 1e-9: hit = True
                            if hit: new[i] = wn
            else:
                wm = max(w for w in set(ws) if sum(l for l, x in zip(Ls, ws) if x >= w - 1e-9) >= SHARE * tot - 1e-9)
                neck = [x for x in ws if x < wm - 1e-9]; wn = min(neck) if neck else wm
                new = [wm if x >= wm - 1e-9 else wn for x in ws]
                i = 0
                while i < len(run):                       # a short wide stretch between two necks reads as noise
                    if new[i] == wm:
                        j = i; s = 0.0
                        while j < len(run) and new[j] == wm: s += Ls[j]; j += 1
                        if s < 1.0 and i > 0 and j < len(run):
                            for k in range(i, j): new[k] = wn
                        i = j
                    else: i += 1
            if PAL: new = [max([p for p in PAL if p <= w + 1e-9] or [w]) for w in new]
            for u, w0, w1, l in zip(run, ws, new, Ls):
                assert w1 <= w0 + 1e-9
                if w1 < w0 - 1e-9:
                    spec.append(dict(setw=[u['x1'], u['y1'], u['x2'], u['y2']], layer=L, net=net, w=w1)); r = rep[net]; r[0] += 1; r[2] += l
            rep[net][1] += 1
json.dump(spec, open(a[1], 'w'))
for n, (k, runs, l) in sorted(rep.items()):
    if k: print(f'{TN.ncls(n)[:9]:10s}{n[-30:]:30s} runs with mixed widths {runs:2d}   segments narrowed {k:3d} ({l:.1f} mm)')
print('segments narrowed', len(spec), 'in', sum(1 for v in rep.values() if v[0]), 'nets')
