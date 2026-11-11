"""ml.py cu.json net x0,y0,x1,y1 sx0,sy0,sx1,sy1 out_spec.json [w=0.15] [--png=out.png] [--layers=F,In2,In3,B] [--viacost=2] [--block=x0,y0,x1,y1,...]
Exact-clearance search for one short link on the signal layers, all existing copper fixed, vias allowed wherever a
0.45/0.3 via is legal on all six layers (also inside a pad of the same net). Source = the net's copper inside the s-box,
goal = the net's copper outside it. Grid 0.05 mm. Writes a handadd spec. Run with the venv python."""
import json, sys, heapq, re, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
a = [x for x in sys.argv[1:] if not x.startswith('--')]; OPT = dict(x[2:].split('=', 1) for x in sys.argv[1:] if x.startswith('--'))
d = json.load(open(a[0])); NET = a[1]; X0, Y0, X1, Y1 = [float(v) for v in a[2].split(',')]; SB = [float(v) for v in a[3].split(',')]
W = float(a[5]) if len(a) > 5 else 0.15
G = 0.05; NX, NY = int(round((X1 - X0) / G)), int(round((Y1 - Y0) / G)); MARG = float(OPT.get('marg', 0.03))
ALL = ['F', 'In1', 'In2', 'In3', 'In4', 'B']; RL = OPT.get('layers', 'F,In2,In3,B').split(','); VIAC = float(OPT.get('viacost', 2)); VR = 0.225
HC = re.compile(r'PACK_P$|CELL_N$|/CELL|FET_MID|VBAT_SYS$|PPHV$|VBUS$|/SW[12]$|AC_SNS_N$|BAT_SNS_P$')
PLANE = re.compile(r'^(GND|3V3|/?PACK_P)$')
px = lambda x, y: ((x - X0) / G, (y - Y0) / G)
inb = lambda x, y, m=2.0: X0 - m <= x <= X1 + m and Y0 - m <= y <= Y1 + m
def ras(fn):
    im = Image.new('L', (NX, NY), 0); fn(ImageDraw.Draw(im)); return np.array(im) > 0
def disc(dr, x, y, r):
    cx, cy = px(x, y); r /= G; dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
def seg(dr, t, grow):
    wd = (t['w'] + 2 * grow) / G; dr.line([px(t['x1'], t['y1']), px(t['x2'], t['y2'])], fill=255, width=max(1, int(math.ceil(wd))))
    disc(dr, t['x1'], t['y1'], t['w'] / 2 + grow); disc(dr, t['x2'], t['y2'], t['w'] / 2 + grow)
def dil(m, r):
    im = Image.fromarray((m * 255).astype(np.uint8)); r = int(math.ceil(r / G))
    while r > 0:
        k = min(r, 7); im = im.filter(ImageFilter.MaxFilter(2 * k + 1)); r -= k
    return np.array(im) > 0
import fnmatch, os
_pp = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'base/Monolith.kicad_pro')))['net_settings']['netclass_patterns']
def ncls(net):
    for p_ in _pp:
        if fnmatch.fnmatchcase(net, p_['pattern']): return p_['netclass']
    return 'Default'
_me = ncls(NET)
def clr(net, pad=False):        # custom rule: HighCurrent copper to Default-class copper 0.25 mm, pads excepted
    if pad: return 0.15
    o = ncls(net)
    return 0.25 if (_me == 'HighCurrent' and o == 'Default') or (o == 'HighCurrent' and _me == 'Default') else 0.15
def blocked(L, half):
    """cells where the centre of a round thing of radius `half` of our net may not be on layer L"""
    def f(dr):
        for t in d['tracks']:
            if t['l'] == L and t['net'] != NET and (inb(t['x1'], t['y1']) or inb(t['x2'], t['y2'])): seg(dr, t, clr(t['net']) + half + MARG)
        for v in d['vias']:
            if v['net'] != NET and inb(v['x'], v['y']): disc(dr, v['x'], v['y'], v['d'] / 2 + clr(v['net']) + half + MARG)
    m = ras(f)
    for c in (0.15, 0.25):
        def g(dr):
            for p in d['pads']:
                if p['L'].get(L) and p['net'] != NET and inb(p['x'], p['y'], 6) and c == 0.15: dr.polygon([px(*q) for q in p['L'][L]], fill=255)
            for fl in d['fills']:
                if fl['l'] == L and fl['net'] != NET and not PLANE.search(fl['net']) and clr(fl['net']) == c:
                    for pts, hs in fl['polys']:
                        if any(inb(x, y) for x, y in pts[::3]): dr.polygon([px(*q) for q in pts], fill=255)
        m |= dil(ras(g), c + half + MARG)
    return m
def own(L):
    def f(dr):
        for t in d['tracks']:
            if t['l'] == L and t['net'] == NET: seg(dr, t, -0.03)
        for p in d['pads']:
            if p['L'].get(L) and p['net'] == NET: dr.polygon([px(*q) for q in p['L'][L]], fill=255)
        for v in d['vias']:
            if v['net'] == NET: disc(dr, v['x'], v['y'], 0.15)
    return ras(f)
# boxes the caller wants kept free, all layers
XB = [float(v) for v in OPT['block'].split(',')] if 'block' in OPT else []
def xblock(m):
    for i in range(0, len(XB), 4):
        c0, r0 = [int(v) for v in px(XB[i], XB[i + 1])]; c1, r1 = [int(v) for v in px(XB[i + 2], XB[i + 3])]; m[max(r0, 0):max(r1, 0), max(c0, 0):max(c1, 0)] = True
    return m
ok = {L: ~xblock(blocked(L, W / 2)) for L in RL}
CORR = None
if 'corridor' in OPT:       # --corridor=file.json:r  only cells within r mm of the polylines in the file may be used (follow a partner net)
    _f, _r = OPT['corridor'].rsplit(':', 1); _pl = json.load(open(_f))
    def _c(dr):
        for pl in _pl: dr.line([px(*q) for q in pl], fill=255, width=1)
    CORR = dil(ras(_c), float(_r))
    for L in RL: ok[L] &= CORR
viaok = np.ones((NY, NX), bool)
for L in ALL: viaok &= ~blocked(L, VR)
def holes(dr):
    for v in d['vias']:
        if inb(v['x'], v['y']): disc(dr, v['x'], v['y'], v['drill'] / 2 + 0.2 + 0.15 + MARG)   # hole to hole 0.2, our drill 0.3
    for p in d['pads']:
        if p.get('hole', 0) > 0 and inb(p['x'], p['y'], 6): disc(dr, p['x'], p['y'], p['hole'] / 2 + 0.25 + 0.15 + MARG)
viaok &= ~ras(holes); viaok = ~xblock(~viaok)
if CORR is not None: viaok &= CORR
ownm = {L: own(L) for L in RL}
yy, xx = np.mgrid[0:NY, 0:NX]; gx = X0 + xx * G; gy = Y0 + yy * G
insb = (gx >= SB[0]) & (gx <= SB[2]) & (gy >= SB[1]) & (gy <= SB[3])
src = {L: ownm[L] & insb for L in RL}; goal = {L: ownm[L] & ~insb for L in RL}
for L in RL: ok[L] |= ownm[L]
if 'pieces' in OPT:      # link a cut-off group of a plane net (isl.py pieces file): source = group --group, goal = everything in group 0
    PCS = json.load(open(OPT['pieces'])); key = [k for k in PCS if k.split('/')[-1] == NET.split('/')[-1] and '@' not in k][0]; GRP = int(OPT.get('group', 1))
    LN = lambda l: l.replace('.C', '')
    def pr(g, L):
        def f(dr):
            for e in PCS[key]:
                if e[0] == g and LN(e[1]) == L: dr.polygon([px(*q) for q in e[6]], fill=255)
        return ~dil(~ras(f), 0.1)
    def iso(L):
        def f(dr):
            for e in PCS[key + '@iso']:
                if e[0] == 'P': dr.rectangle([px(e[2], e[3]), px(e[4], e[5])], fill=255)
                elif e[0] == 'V': disc(dr, e[2], e[3], 0.12)
                elif LN(e[1]) == L: seg(dr, dict(x1=e[2], y1=e[3], x2=e[4], y2=e[5], w=2 * e[6]), -0.03)
        return ras(f)
    for L in RL:
        im_ = iso(L); mainp = pr(0, L); srcp = pr(GRP, L)
        goal[L] = (ownm[L] & ~dil(im_, 0.15) & ~dil(srcp, 0.2)) | mainp
        src[L] = (im_ & ownm[L] & insb) | srcp
        ok[L] |= mainp | srcp
    print('group', GRP, 'of', key)
if 'goalbox' in OPT:
    gb = [float(v) for v in OPT['goalbox'].split(',')]; ing = (gx >= gb[0]) & (gx <= gb[2]) & (gy >= gb[1]) & (gy <= gb[3])
    for L in RL: goal[L] &= ing
FV = [float(v) for v in OPT['via'].split(',')] if 'via' in OPT else None      # a via site checked by hand (vsite.py): start there on every layer
if FV:
    fc = [int(round(v)) for v in px(*FV)]
    for L in RL: src[L][:] = False; src[L][fc[1], fc[0]] = True; ok[L][fc[1], fc[0]] = True
print('source cells', {L: int(src[L].sum()) for L in RL}, 'goal cells', {L: int(goal[L].sum()) for L in RL})
nl = len(RL); dist = np.full((nl, NY, NX), np.inf, np.float32); prev = {}; hq = []
for li, L in enumerate(RL):
    for y, x in zip(*np.nonzero(src[L])): dist[li, y, x] = 0; heapq.heappush(hq, (0.0, li, int(y), int(x))); prev[(li, int(y), int(x))] = None
NB = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)]
end = None
while hq:
    dd, li, y, x = heapq.heappop(hq)
    if dd > dist[li, y, x]: continue
    if goal[RL[li]][y, x]: end = (li, y, x); break
    pd = prev.get((li, y, x))
    for dy, dx, c in NB:
        y2, x2 = y + dy, x + dx
        if not (0 <= y2 < NY and 0 <= x2 < NX) or not ok[RL[li]][y2, x2]: continue
        turn = 0.3 if pd is not None and pd[0] == li and (y - pd[1], x - pd[2]) != (dy, dx) else 0.0
        nd = dd + c * G + turn
        if nd < dist[li, y2, x2]: dist[li, y2, x2] = nd; prev[(li, y2, x2)] = (li, y, x); heapq.heappush(hq, (nd, li, y2, x2))
    if viaok[y, x]:
        for l2 in range(nl):
            if l2 != li and ok[RL[l2]][y, x]:
                nd = dd + VIAC
                if nd < dist[l2, y, x]: dist[l2, y, x] = nd; prev[(l2, y, x)] = (li, y, x); heapq.heappush(hq, (nd, l2, y, x))
reach = {L: int(np.isfinite(dist[i]).sum()) for i, L in enumerate(RL)}
spec = []
if end is None: print('FAILED; reached cells', reach)
else:
    path = []; c = end
    while c is not None: path.append(c); c = prev[c]
    path.reverse()
    mm = lambda c: [round(X0 + c[2] * G, 3), round(Y0 + c[1] * G, 3)]
    runs = []; cur = [path[0]]
    for c in path[1:]:
        if c[0] != cur[-1][0]: runs.append(cur); cur = [c]
        else: cur.append(c)
    runs.append(cur); tot = 0
    if FV: spec.append(dict(net=NET, via=FV))
    for i, r in enumerate(runs):
        if i > 0: spec.append(dict(net=NET, via=mm(r[0])))
        pts = [r[0]]
        for j in range(1, len(r) - 1):
            if (r[j][1] - r[j - 1][1], r[j][2] - r[j - 1][2]) != (r[j + 1][1] - r[j][1], r[j + 1][2] - r[j][2]): pts.append(r[j])
        if len(r) > 1:
            pts.append(r[-1]); p = [mm(c) for c in pts]
            if FV and i == 0: p[0] = FV
            ln = sum(math.dist(p[k], p[k + 1]) for k in range(len(p) - 1)); tot += ln
            spec.append(dict(net=NET, layer=RL[r[0][0]], w=W, pts=p)); print('  %s %.2f mm' % (RL[r[0][0]], ln), p)
    print('routed', NET, 'length %.1f mm,' % tot, len(runs) - 1, 'vias at', [s['via'] for s in spec if 'via' in s])
json.dump(spec, open(a[4], 'w'))
if 'png' in OPT:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    PV = OPT.get('panels', ','.join(RL)).split(',')
    fig, axs = plt.subplots(1, len(PV), figsize=(11 * len(PV), 11 * (Y1 - Y0) / (X1 - X0) + 0.5), squeeze=False)
    for ax, L in zip(axs[0], PV):
        i = RL.index(L); m = ok[L]
        img = np.zeros((NY, NX, 3)); img[:] = 0.3; img[m] = 0.8; img[np.isfinite(dist[i]) & m] = 1.0
        img[viaok & m] *= [1.0, 0.85, 0.6]; img[ownm[L]] = [0.75, 0.75, 0.95]; img[src[L]] = [0.4, 0.5, 1.0]; img[goal[L]] = [0.5, 0.9, 0.5]
        ax.imshow(img, extent=[X0, X1, Y1, Y0]); ax.set_title(L + ': white reached, grey free, dark blocked, blue source, green goal, orange tint via site'); ax.grid(lw=0.2)
        for s_ in spec:
            if 'pts' in s_ and s_['layer'] == L: ax.plot([p[0] for p in s_['pts']], [p[1] for p in s_['pts']], 'r-', lw=1.5)
            if 'via' in s_: ax.plot(*s_['via'], 'ro', ms=5)
        for v in d['vias']:
            if X0 < v['x'] < X1 and Y0 < v['y'] < Y1: ax.text(v['x'], v['y'], v['net'].split('/')[-1][:7], fontsize=6, ha='center', va='center', color='k', clip_on=True)
        for p in d['pads']:
            if p['L'].get(L) and X0 < p['x'] < X1 and Y0 < p['y'] < Y1: ax.text(p['x'], p['y'], p['ref'] + '.' + p['n'], fontsize=5, ha='center', va='center', color='#aa0000', clip_on=True)
    fig.savefig(OPT['png'], dpi=75)
