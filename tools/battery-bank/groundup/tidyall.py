"""tidyall.py cu.json out_spec.json [--sweeps=2] [--only=regex] [--log=file.json] [--max=N]
Run tidynet.tidy() over every plain signal net of a copper dump, one after the other on the same copper, short nets
first (local links before long ones). A new route is kept only when it has no more vias, is at most 5 % longer and scores
at least 3 % better on length + 2.5 mm per via + 0.15 mm per segment + 1 mm per extra width. Nets with a track in a
ground plane layer are left for a later pass. Every net gets one width: 0.2 mm, or 0.15 mm for
the whole net when 0.2 does not fit. Left alone: nets with a pour, nets outside the Default net class,
switch-node / gate / bootstrap nets, current-sense pairs, RF and USB data pairs (drawn by hand for a reason).
Writes ONE handadd.py spec for all kept nets (old copper of the net deleted, final copper added)."""
import json, sys, re, math, time, collections, copy
import tidynet as TN
a = [x for x in sys.argv[1:] if not x.startswith('--')]; OPT = dict(x[2:].split('=', 1) for x in sys.argv[1:] if x.startswith('--'))
import os
d = json.load(open(a[0])); d['keep'] = json.load(open(OPT.get('keep', os.path.join(os.path.dirname(a[0]), 'keep.json')))); d0t = copy.deepcopy(d['tracks']); d0v = copy.deepcopy(d['vias'])
SKIP = re.compile(r'(LODRV[12]|LG[12]|SRP(_F)?|SRN(_F)?|ACP(_F)?|ACN(_F)?|RFIO|ANT_IN|D[PN]\d?|D[+-]|USB_D[PMN]|_SNS_[PN])$')
def area(pts): return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))) / 2
za = collections.Counter()
for fl in d['fills']:
    for pts, hs in fl['polys']: za[fl['net']] += area(pts)
npads = collections.Counter(p['net'] for p in d['pads'])
def mst(net):
    pts = list({(round(p['x'], 3), round(p['y'], 3)) for p in d['pads'] if p['net'] == net})
    if len(pts) < 2: return 0.0
    dd = [math.dist(pts[0], p) for p in pts]; used = [False] * len(pts); used[0] = True; tot = 0.0
    for _ in range(len(pts) - 1):
        j = min((i for i in range(len(pts)) if not used[i]), key=lambda i: dd[i]); tot += dd[j]; used[j] = True
        for i in range(len(pts)):
            if not used[i]: dd[i] = min(dd[i], math.dist(pts[j], pts[i]))
    return tot
nets = sorted({t['net'] for t in d['tracks']})
ALLOW = re.compile(r'/(CHG_G|DSG_G)$')        # protection-FET gates: static levels in the GateDrive class
RFN = re.compile(r'(RFIO|ANT_IN)$')                # and whatever hangs on a part of the antenna match (the pi network's middle node)
rfparts = {p['ref'] for p in d['pads'] if RFN.search(p['net'])} - {p['ref'] for p in d['pads'] if RFN.search(p['net']) and sum(1 for q in d['pads'] if q['ref'] == p['ref']) > 4}
rfnets = {p['net'] for p in d['pads'] if p['ref'] in rfparts and p['net'] not in ('GND',)}
cand = [n for n in nets if n and n not in rfnets and npads[n] >= 2 and za[n] < 3.0 and (TN.ncls(n) == 'Default' or ALLOW.search(n)) and not TN.SWN.search(n) and not SKIP.search(n)]
if 'only' in OPT: cand = [n for n in cand if re.search(OPT['only'], n)]
M = {n: mst(n) for n in cand}; cand.sort(key=lambda n: M[n])
if 'max' in OPT: cand = cand[:int(OPT['max'])]
print(len(cand), 'candidate nets of', len(nets), flush=True)
log = []; changed = set(); t00 = time.time()
for sw in range(int(OPT.get('sweeps', 2))):
    nk = 0
    for n in cand:
        t0 = time.time()
        ow = sorted({t['w'] for t in d['tracks'] if t['net'] == n})
        if any(t['l'] not in ('F', 'In2', 'In3', 'B') for t in d['tracks'] if t['net'] == n): print(f's{sw} skip (track in a ground plane)  {n[-30:]}', flush=True); continue
        if not ow or ow[0] > 0.2 + 1e-9: continue                  # drawn wide on purpose: leave alone
        try:
            spec, st, nt, nv = TN.tidy(d, n, W=0.2)
            if not spec: spec, st, nt, nv = TN.tidy(d, n, W=0.15)  # the whole net one step narrower
        except AssertionError as e: continue
        o, w = st['old'], st['new']; nw = sorted({t['w'] for t in nt})
        # one number for "how much there is to look at": length + 2.5 mm per via + 0.15 mm per segment + 1 mm per extra width
        sc = lambda x, nwid: x['length'] + 2.5 * x['vias'] + 0.15 * x['segs'] + 1.0 * (nwid - 1)
        so, sn = sc(o, len(ow)), sc(w, len(nw))
        keep = bool(spec) and w['vias'] <= o['vias'] and w['length'] <= o['length'] * 1.05 and sn <= so * 0.97
        st.update(old_widths=ow, new_widths=nw)
        st.update(sweep=sw, kept=keep, mst=M[n], sec=round(time.time() - t0, 1)); log.append(st)
        if keep:
            d['tracks'] = [t for t in d['tracks'] if t['net'] != n] + nt; d['vias'] = [v for v in d['vias'] if v['net'] != n] + nv; changed.add(n); nk += 1
        print(f"s{sw} {'KEEP' if keep else 'skip' if spec else 'FAIL'} {(st.get('failed_at') or '')[:22]:22s} {n[-30:]:30s} {o['length']:6.1f} -> {w['length']:6.1f} mm  segs {o['segs']:3d} -> {w['segs']:3d}  vias {o['vias']} -> {w['vias']}  {st['sec']} s", flush=True)
        if 'log' in OPT: json.dump(log, open(OPT['log'], 'w'))
    print(f'sweep {sw}: kept {nk}, {time.time() - t00:.0f} s', flush=True)
    if nk == 0: break
spec = []
for n in sorted(changed):
    spec += [dict({'del': [t['x1'], t['y1']]}, net=n, what=t['l']) for t in d0t if t['net'] == n] + [dict({'del': [v['x'], v['y']]}, net=n, what='via') for v in d0v if v['net'] == n]
for n in sorted(changed):
    spec += [dict(net=n, via=[v['x'], v['y']], rul=1) for v in d['vias'] if v['net'] == n]
    spec += [dict(net=n, layer=t['l'], w=t['w'], pts=[[t['x1'], t['y1']], [t['x2'], t['y2']]]) for t in d['tracks'] if t['net'] == n]
json.dump(spec, open(a[1], 'w')); print('changed nets', len(changed), 'spec items', len(spec))
