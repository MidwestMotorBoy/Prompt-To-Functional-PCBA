"""gp.py cu.json jobs.json out_spec.json [png]: single-layer tracks on a ground-plane layer between existing vias.
jobs: [{"net":..,"layer":"In4","w":0.2,"src":[[x,y],..],"dst":[[x,y],..]}, ...] routed in order; each laid track blocks the next.
Legal area = the plane's own fill shrunk by w/2 + CLR, minus every same-net (GND) via and hole. Soft cost keeps the track
away from switching copper on the neighbouring layers and out of the listed boxes. Run with the venv python."""
import json, sys, heapq, re, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
G = 0.05; X0, Y0, X1, Y1 = 77.5, 61.5, 122.5, 138.5; NX, NY = int((X1 - X0) / G), int((Y1 - Y0) / G); CLR = 0.15
d = json.load(open(sys.argv[1])); jobs = json.load(open(sys.argv[2]))
AVOID = re.compile(r'/SW[12]$|SW_5V$|SW_3V3$|BTST[12]$|HIDRV[12]$|/HG[12]$')
SENSE = re.compile(r'(SRP|SRN|ACP|ACN)(_F)?$')
px = lambda x, y: ((x - X0) / G, (y - Y0) / G)
def ras(draw_fn):
    im = Image.new('L', (NX, NY), 0); draw_fn(ImageDraw.Draw(im)); return np.array(im) > 0
def dil(m, r):
    im = Image.fromarray((m * 255).astype(np.uint8)); r = int(round(r / G))
    while r > 0:
        k = min(r, 7); im = im.filter(ImageFilter.MaxFilter(2 * k + 1)); r -= k
    return np.array(im) > 0
def layer_copper(L, rx):
    def f(dr):
        for fl in d['fills']:
            if fl['l'] == L and rx.search(fl['net']):
                for pts, hs in fl['polys']: dr.polygon([px(*p) for p in pts], fill=255)
        for t in d['tracks']:
            if t['l'] == L and rx.search(t['net']): dr.line([px(t['x1'], t['y1']), px(t['x2'], t['y2'])], fill=255, width=max(1, int(t['w'] / G)))
        for p in d['pads']:
            if p['L'].get(L) and rx.search(p['net']): dr.polygon([px(*q) for q in p['L'][L]], fill=255)
    return ras(f)
spec = []; laid = []
def legal(L, w, clr=CLR, own=None):
    def f(dr):
        for fl in d['fills']:
            if fl['l'] == L and fl['net'] == 'GND':
                for pts, hs in fl['polys']: dr.polygon([px(*p) for p in pts], fill=255)
        for fl in d['fills']:
            if fl['l'] == L and fl['net'] == 'GND':
                for pts, hs in fl['polys']:
                    for h in hs: dr.polygon([px(*p) for p in h], fill=0)
    m = ras(f)
    m = ~dil(~m, w / 2 + CLR)
    def g(dr):
        for v in d['vias']:
            r = (v['d'] / 2 + CLR + w / 2 + 0.03) / G; x, y = px(v['x'], v['y']); dr.ellipse([x - r, y - r, x + r, y + r], fill=255)
        for p in d['pads']:
            if p['L'].get(L): dr.polygon([px(*q) for q in p['L'][L]], fill=255)
        for t in d['tracks'] + laid:
            if t['l'] == L and t['net'] != own: dr.line([px(t['x1'], t['y1']), px(t['x2'], t['y2'])], fill=255, width=int(round((t['w'] + 2 * max(clr, t.get('clr', CLR)) + w + 0.1) / G)))
    blk = ras(g)
    def g2(dr):
        for p in d['pads']:
            if p['L'].get(L): dr.polygon([px(*q) for q in p['L'][L]], fill=255)
    blk |= dil(ras(g2), w / 2 + CLR + 0.05)
    return m & ~blk
ADJ = {'In4': ('In3', 'B'), 'In1': ('F', 'In2')}
for jb in jobs:
    L, w, net = jb['layer'], jb.get('w', 0.2), jb['net']
    ok = legal(L, w, jb.get('clr', CLR), net)
    cost = np.ones((NY, NX), np.float32)
    for A in ADJ[L]:
        cost += 300 * dil(layer_copper(A, AVOID), 0.8) + 6 * dil(layer_copper(A, SENSE), 0.4)
    for bx in jb.get('boxes', []):
        c0, r0 = [int(v) for v in px(bx[0], bx[1])]; c1, r1 = [int(v) for v in px(bx[2], bx[3])]; cost[r0:r1, c0:c1] += bx[4]
    def cells(pts, rad=0.35):          # start / goal cells: legal cells within rad of a via of the net (the via itself is not legal area)
        out = []
        for x, y in pts:
            cx, cy = [int(round(v)) for v in px(x, y)]; r = int(rad / G)
            for yy in range(cy - r, cy + r + 1):
                for xx in range(cx - r, cx + r + 1):
                    if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r: out.append((yy, xx, x, y))
        return out
    # the net's own vias must not block: free a disc round each src / dst via
    for x, y in jb['src'] + jb['dst']:
        cx, cy = [int(round(v)) for v in px(x, y)]; r = int(0.85 / G)
        yy, xx = np.ogrid[cy - r:cy + r + 1, cx - r:cx + r + 1]; near = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
        # only free cells that are blocked by this via alone: re-check against other vias
        sub = ok[cy - r:cy + r + 1, cx - r:cx + r + 1]
        oth = np.zeros_like(sub)
        for v in d['vias']:
            if abs(v['x'] - x) < 0.01 and abs(v['y'] - y) < 0.01: continue
            if abs(v['x'] - x) < 1.5 and abs(v['y'] - y) < 1.5:
                rr = (v['d'] / 2 + CLR + w / 2 + 0.03) / G; vx, vy = px(v['x'], v['y'])
                oth |= ((xx - vx) ** 2 + (yy - vy) ** 2 <= rr * rr)
        sub |= near & ~oth
    dist = np.full((NY, NX), np.inf, np.float32); prev = {}; hq = []
    goal = {}; goal_src = {}
    for x, y in jb['dst']:
        cx, cy = [int(round(v)) for v in px(x, y)]; goal[(cy, cx)] = (x, y)
    if jb.get('join'):
        for t in d['tracks'] + laid:
            if t['l'] == L and t['net'] == net:
                n_ = max(1, int(math.dist((t['x1'], t['y1']), (t['x2'], t['y2'])) / G))
                for i_ in range(n_ + 1):
                    x_, y_ = t['x1'] + (t['x2'] - t['x1']) * i_ / n_, t['y1'] + (t['y2'] - t['y1']) * i_ / n_
                    cx, cy = [int(round(v)) for v in px(x_, y_)]; goal[(cy, cx)] = (round(X0 + cx * G, 3), round(Y0 + cy * G, 3)); ok[cy, cx] = True
    for x, y in jb['src']:
        cx, cy = [int(round(v)) for v in px(x, y)]; goal_src[(cy, cx)] = (x, y); dist[cy, cx] = 0; heapq.heappush(hq, (0.0, cy, cx)); prev[(cy, cx)] = None
    NB = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)]
    end = None
    while hq:
        dd, y, x = heapq.heappop(hq)
        if dd > dist[y, x]: continue
        if (y, x) in goal: end = (y, x); break
        for dy, dx, c in NB:
            yy, xx = y + dy, x + dx
            if not (0 <= yy < NY and 0 <= xx < NX) or not ok[yy, xx]: continue
            pd = prev.get((y, x)); turn = 0.0
            if pd is not None and (y - pd[0], x - pd[1]) != (dy, dx): turn = 3.0
            nd = dd + c * cost[yy, xx] + turn
            if nd < dist[yy, xx]: dist[yy, xx] = nd; prev[(yy, xx)] = (y, x); heapq.heappush(hq, (nd, yy, xx))
    if end is None: print('FAILED', net, 'reached', int(np.isfinite(dist).sum()), 'cells'); continue
    path = []; c = end
    while c is not None: path.append(c); c = prev[c]
    path.reverse()
    pts = [path[0]]
    for i in range(1, len(path) - 1):
        a, b, c2 = path[i - 1], path[i], path[i + 1]
        if (b[0] - a[0], b[1] - a[1]) != (c2[0] - b[0], c2[1] - b[1]): pts.append(b)
    pts.append(path[-1])
    mm = [[round(X0 + x * G, 3), round(Y0 + y * G, 3)] for y, x in pts]
    mm[0] = list(goal_src[path[0]]); mm[-1] = list(goal[path[-1]])
    ln = sum(math.dist(mm[i], mm[i + 1]) for i in range(len(mm) - 1))
    hot = sum(1 for y, x in path if cost[y, x] > 20) * G
    hc = [(round(X0 + x * G, 1), round(Y0 + y * G, 1)) for y, x in path if cost[y, x] > 20]
    if hc: print('   keep-away cells from', hc[0], 'to', hc[-1])
    print('routed', net, L, 'length %.1f mm, %d corners, %.1f mm inside keep-away' % (ln, len(mm) - 2, hot), mm[0], mm[-1])
    spec.append(dict(net=net, layer=L, w=w, pts=mm))
    for i in range(len(mm) - 1): laid.append(dict(clr=jb.get('clr', CLR), l=L, w=w, x1=mm[i][0], y1=mm[i][1], x2=mm[i + 1][0], y2=mm[i + 1][1], net=net))
json.dump(spec, open(sys.argv[3], 'w'))
if len(sys.argv) > 4:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    L = jobs[0]['layer']; VIEW = [float(v) for v in sys.argv[5].split(',')] if len(sys.argv) > 5 else [78, 122, 62, 138]
    fig, ax = plt.subplots(figsize=(13, 13 * (VIEW[3] - VIEW[2]) / (VIEW[1] - VIEW[0])))
    for v in d['vias']:
        if VIEW[0] <= v['x'] <= VIEW[1] and VIEW[2] <= v['y'] <= VIEW[3]: ax.text(v['x'], v['y'], v['net'].split('/')[-1][:6], fontsize=7, ha='center', va='center', clip_on=True)
    ax.imshow(legal(L, 0.2), extent=(X0, X1, Y1, Y0), cmap='Greys', alpha=0.35, interpolation='nearest')
    av = np.zeros((NY, NX), bool)
    for A in ADJ[L]: av |= dil(layer_copper(A, AVOID), 0.8)
    ax.imshow(np.ma.masked_equal(av, 0), extent=(X0, X1, Y1, Y0), cmap='autumn', alpha=0.35, interpolation='nearest')
    for k, s in enumerate(spec):
        xs, ys = zip(*s['pts']); ax.plot(xs, ys, lw=1.6, label=s['net'].split('/')[-1] + (' P' + s['net'].split('Port ')[1][0] if 'Port' in s['net'] else ''))
    ax.legend(); ax.set_xlim(*VIEW[:2]); ax.set_ylim(VIEW[3], VIEW[2]); ax.set_aspect('equal'); ax.grid(lw=0.2)
    fig.savefig(sys.argv[4], dpi=110)
