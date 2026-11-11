"""Electric-field coupling from switching copper to every other net: 3-D finite-difference Laplace solve on the real
copper of a box round the aggressor nets.  Aggressor group = 1 V, every other conductor = 0 V; the charge induced on a
net is its coupling capacitance to the group.  xy grid H (0.05 mm), graded z through the 6-layer stack + air.
PCB=<board> TAG=<tag> python coup.py [group indices]  ->  coup_<tag>.json"""
import numpy as np, os, json, sys, time
import scipy.sparse as sp, pyamg
from PIL import Image, ImageDraw
from peec import Model, LAYERS, REF, FP, SEG, VIA, ZON

E0 = 8.854e-15            # F/mm
H = float(os.environ.get('H', '0.05'))
MARGIN = float(os.environ.get('MARGIN', '1.5'))
TAG = os.environ['TAG']
allnets = sorted(set([p['net'] for fp in FP for p in fp['pads'] if p['net']] + [s['net'] for s in SEG if s['net']]
                     + [z['net'] for z in ZON if z['net']] + [v['net'] for v in VIA if v['net']]))
P1, P2 = '/USB Port 1/', '/USB Port 2/'
GROUPS = [
    ('P1 SW1 (VBUS leg)', [P1+'SW1', P1+'BTST1', P1+'HIDRV1', P1+'HG1'], 20.0),
    ('P1 SW2 (pack leg)', [P1+'SW2', P1+'BTST2', P1+'HIDRV2', P1+'HG2'], 16.8),
    ('P2 SW1 (VBUS leg)', [P2+'SW1', P2+'BTST1', P2+'HIDRV1', P2+'HG1'], 20.0),
    ('P2 SW2 (pack leg)', [P2+'SW2', P2+'BTST2', P2+'HIDRV2', P2+'HG2'], 16.8),
    ('P1 5 V buck SW', [P1+'SW_5V', P1+'BST_5V'], 16.8),
    ('P2 5 V buck SW', [P2+'SW_5V', P2+'BST_5V'], 16.8),
    ('3V3 buck SW', ['/3V3 Rail/SW_3V3'], 16.8),
]
# z levels (mm, 0 = top of F.Cu, positive down) and what sits on them
ZF = [0.0, 0.035, 0.07]; ZI = {'In1.Cu': 0.27, 'In2.Cu': 0.5875, 'In3.Cu': 0.995, 'In4.Cu': 1.3125}; ZB = [1.53, 1.565, 1.60]
def between(a, b):
    g = b - a; n = max(2, int(round(g / 0.055)))
    return [a + g * i / n for i in range(1, n)]
levels = [(-z, None) for z in (1.6, 1.0, 0.6, 0.35, 0.2, 0.1, 0.05)]
levels += [(z, 'F.Cu') for z in ZF]
prev = 0.07
for L in ('In1.Cu', 'In2.Cu', 'In3.Cu', 'In4.Cu'):
    levels += [(z, 'via') for z in between(prev, ZI[L])]; levels.append((ZI[L], L)); prev = ZI[L]
levels += [(z, 'via') for z in between(prev, 1.53)]
levels += [(z, 'B.Cu') for z in ZB]
levels += [(1.6 + z, None) for z in (0.05, 0.1, 0.2, 0.35, 0.6, 1.0, 1.6)]
ZS = np.array([z for z, _ in levels]); NZ = len(ZS); DZ = np.diff(ZS)
def eps_between(za, zb):
    zm = 0.5 * (za + zb)
    if zm < 0 or zm > 1.60: return 1.0
    if zm < 0.07 or zm > 1.53: return 3.5      # solder mask between outer-layer copper
    return 4.4


def bbox(nets):
    xs = []; ys = []
    for s in SEG:
        if s['net'] in nets: xs += [s['x1'], s['x2']]; ys += [s['y1'], s['y2']]
    for fp in FP:
        for p in fp['pads']:
            if p['net'] in nets: r = max(p['w'], p['h']) / 2; xs += [p['x'] - r, p['x'] + r]; ys += [p['y'] - r, p['y'] + r]
    for v in VIA:
        if v['net'] in nets: xs.append(v['x']); ys.append(v['y'])
    for z in ZON:
        if z['net'] in nets:
            for L, pts in z['fills']: xs += [q[0] for q in pts]; ys += [q[1] for q in pts]
    return (min(xs) - MARGIN, max(xs) + MARGIN, min(ys) - MARGIN, max(ys) + MARGIN)


def run(name, nets, vsw):
    t0 = time.time()
    box = bbox(set(nets)); m = Model(box, allnets, h=H); Hh, W = m.H, m.W
    # via / plated-hole barrels between the copper layers
    im = Image.new('I', (W, Hh), 0); d = ImageDraw.Draw(im)
    for v in VIA:
        if v['net'] in m.nid:
            c = m.P(v['x'], v['y']); r = max(v['drill'] / 2 / H, 0.5); d.ellipse([c[0]-r, c[1]-r, c[0]+r, c[1]+r], fill=m.nid[v['net']])
    for fp in FP:
        for p in fp['pads']:
            if p['net'] in m.nid and p['drill'] is not None and '*.Cu' in p['layers']:
                try: dr = float(p['drill'][1])
                except Exception: dr = 0.8
                c = m.P(p['x'], p['y']); r = dr / 2 / H; d.ellipse([c[0]-r, c[1]-r, c[0]+r, c[1]+r], fill=m.nid[p['net']])
    vial = np.array(im, dtype=np.int32)
    lab = np.zeros((NZ, Hh, W), dtype=np.int32)
    for k, (z, what) in enumerate(levels):
        if what is None: continue
        lab[k] = vial if what == 'via' else np.asarray(m.lab[what], dtype=np.int32)
    agg = np.zeros(len(m.nets) + 1, dtype=bool)
    for n in nets: agg[m.nid[n]] = True
    free = lab == 0
    idx = -np.ones(lab.shape, dtype=np.int64); nf = int(free.sum()); idx[free] = np.arange(nf)
    diag = np.zeros(nf); rhs = np.zeros(nf)
    rows = []; cols = []; vals = []
    cq_a = []; cq_n = []; cq_w = []            # free node a next to conductor net n with weight w
    direct = np.zeros(len(m.nets) + 1)
    # per-level lateral weight eps*dz (half of the interval above + half below)
    wl = np.zeros(NZ)
    for k in range(NZ):
        if k > 0: wl[k] += 0.5 * eps_between(ZS[k-1], ZS[k]) * DZ[k-1]
        if k < NZ - 1: wl[k] += 0.5 * eps_between(ZS[k], ZS[k+1]) * DZ[k]
    def links(ia, ib, la, lb, w):
        ia = ia.ravel(); ib = ib.ravel(); la = la.ravel(); lb = lb.ravel(); w = np.broadcast_to(w, la.shape) if np.ndim(w) else np.full(la.shape, w)
        w = np.asarray(w).ravel()
        ff = (ia >= 0) & (ib >= 0)
        rows.append(ia[ff].astype(np.int32)); cols.append(ib[ff].astype(np.int32)); vals.append(w[ff])
        np.add.at(diag, ia[ff], w[ff]); np.add.at(diag, ib[ff], w[ff])
        for a, b_lab in ((ia, lb), (ib, la)):
            other = ib if a is ia else ia
            fc = (a >= 0) & (other < 0)
            np.add.at(diag, a[fc], w[fc]); np.add.at(rhs, a[fc], w[fc] * agg[b_lab[fc]])
            cq_a.append(a[fc].astype(np.int32)); cq_n.append(b_lab[fc]); cq_w.append(w[fc])
        cc = (ia < 0) & (ib < 0) & (agg[la] != agg[lb])
        if cc.any():
            vict = np.where(agg[la[cc]], lb[cc], la[cc]); np.add.at(direct, vict, w[cc])
    for k in range(NZ):
        w = wl[k]
        links(idx[k][:, :-1], idx[k][:, 1:], lab[k][:, :-1], lab[k][:, 1:], w)
        links(idx[k][:-1, :], idx[k][1:, :], lab[k][:-1, :], lab[k][1:, :], w)
        if k < NZ - 1:
            links(idx[k], idx[k+1], lab[k], lab[k+1], eps_between(ZS[k], ZS[k+1]) * H * H / DZ[k])
    r = np.concatenate(rows); c = np.concatenate(cols); v = np.concatenate(vals); del rows, cols, vals
    A = sp.coo_matrix((np.concatenate([-v, -v, diag]), (np.concatenate([r, c, np.arange(nf, dtype=np.int32)]),
                                                         np.concatenate([c, r, np.arange(nf, dtype=np.int32)]))), shape=(nf, nf)).tocsr()
    del r, c, v
    t1 = time.time()
    ml = pyamg.smoothed_aggregation_solver(A, max_coarse=2000)
    res = []
    x = ml.solve(rhs, tol=1e-8, accel='cg', maxiter=200, residuals=res)
    a = np.concatenate(cq_a); n = np.concatenate(cq_n); w = np.concatenate(cq_w)
    q = np.bincount(n, weights=w * x[a], minlength=len(m.nets) + 1) + direct          # victims: induced charge per volt
    qself = float((w * (1 - x[a]))[agg[n]].sum())
    C = {m.nets[i-1]: float(q[i] * E0) for i in range(1, len(m.nets) + 1) if not agg[i] and q[i] * E0 > 0.2e-15}
    if os.environ.get('WHERE'):                 # where on each listed victim the charge sits: 0.5 mm bins, top few
        kk, ii, jj = np.nonzero(free); B5 = int(round(0.5 / H))
        for vn in os.environ['WHERE'].split(','):
            ids = [i for i in range(1, len(m.nets) + 1) if m.nets[i-1].endswith(vn)]
            for vi in ids:
                sel = n == vi
                if not sel.any(): continue
                qq = w[sel] * x[a[sel]] * E0 * 1e15; ka = kk[a[sel]]; ia = ii[a[sel]] // B5; ja = jj[a[sel]] // B5
                tot = {}; lay = {}
                for q1, k1, i1, j1 in zip(qq, ka, ia, ja):
                    tot[(i1, j1)] = tot.get((i1, j1), 0) + q1; z = ZS[k1]
                    L = 'F' if z < 0.17 else 'In1' if z < 0.43 else 'In2' if z < 0.79 else 'In3' if z < 1.15 else 'In4' if z < 1.42 else 'B'
                    lay[(i1, j1, L)] = lay.get((i1, j1, L), 0) + q1
                print(f"   WHERE {m.nets[vi-1]} from {name}: {qq.sum():.1f} fF", flush=True)
                for (i1, j1), q1 in sorted(tot.items(), key=lambda kv: -kv[1])[:10]:
                    ls = ', '.join(f"{L} {v:.1f}" for (i2, j2, L), v in sorted(lay.items(), key=lambda kv: -kv[1]) if (i2, j2) == (i1, j1) and v > 0.05 * q1)
                    print(f"      x {box[0] + (j1 + 0.5) * 0.5:.2f} y {box[2] + (i1 + 0.5) * 0.5:.2f}: {q1:5.1f} fF  ({ls})", flush=True)
    out = dict(name=name, nets=nets, vsw=vsw, box=box, h=H, unknowns=nf, iters=len(res), C_self_pF=qself * E0 * 1e12, C=C,
               t=time.time() - t0)
    top = sorted(C.items(), key=lambda kv: -kv[1])
    print(f"{name}: box {tuple(round(b,1) for b in box)} N={nf/1e6:.1f}M it={len(res)} build {t1-t0:.0f}s total {time.time()-t0:.0f}s  C_self {qself*E0*1e12:.1f} pF", flush=True)
    print('   ' + ', '.join(f"{k.split('/')[-1]} {v*1e15:.0f}" for k, v in top[:28]) + ' fF', flush=True)
    return out


if __name__ == '__main__':
    only = sys.argv[1:]
    fn = f'coup_{TAG}.json'
    res = json.load(open(fn)) if os.path.exists(fn) else {}
    for k, (name, nets, vsw) in enumerate(GROUPS):
        if only and str(k) not in only: continue
        res[name] = run(name, nets, vsw)
        json.dump(res, open(fn, 'w'), indent=1)
