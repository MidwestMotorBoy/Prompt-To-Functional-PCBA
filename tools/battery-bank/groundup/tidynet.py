"""tidynet.py cu.json NET out_spec.json [--w=0.2] [--viacost=2.5] [--layers=F,In2,In3,B] [--marg=2.5] [--stats=file.json]
Rip up one signal net and route it again as ONE tree, the way a person would redraw it:
  - pads are joined in shortest-tree order; every further pad is routed to the nearest point of the tree already drawn,
    so two links of one net share a trunk instead of running side by side;
  - the search knows its direction: a 45 degree bend costs 0.1 mm, a 90 degree bend 0.4 mm, sharper bends are not allowed,
    a via costs --viacost mm, so the result has few bends and no staircase;
  - ONE width for the whole net (--w, 0.2 mm for plain signals). Only old segments that are kept verbatim (pin escapes,
    gaps too tight for the grid) keep their old width;
  - all other copper is fixed and kept at exact clearance (0.05 mm grid; exact distance to tracks and vias);
  - the board edge, unplated holes and rule areas come from dumpkeep.py (keep.json beside the copper dump);
  - a route that would raise the number of pieces of a power pour or inner plane is refused, and so is one that
    leaves a GND pad on a piece of outer-layer GND fill with no via (the fill after refill is estimated);
  - a pad the grid cannot reach is left along its old escape (from any old track end inside the pad) to the first
    grid node; old copper that runs straight into another pad of the net is kept as a link;
  - power pours (3V3, PACK_P) are NOT free space: a track through one costs three times its length and no new via may
    land in one. GND fill on the signal layers is free. Old via sites of the net may be reused;
  - switching copper is expensive to be near (same layer within 1 mm, next layer within 0.6 mm) and no new via may
    land within 1 mm of it on any layer: coupling hot spots are vias.
Writes a handadd.py spec that deletes the net's old tracks and vias and adds the new ones. Run with the venv python,
then step.sh / finish.sh (DRC, plane islands) and the solver loop: a rip-up is an edit like any other.
tidyall.py calls tidy() for many nets in a row on one copper dump."""
import json, sys, heapq, re, math, os, fnmatch
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage
G = 0.05; MARG = 0.03; VR = 0.225; T45, T90 = 0.1, 0.4; POURX = 3.0; SWX_SAME, SWX_ADJ = 2.5, 2.0; OLDP = 0.3
ALL = ['F', 'In1', 'In2', 'In3', 'In4', 'B']
PLANE = re.compile(r'^(GND|3V3|/?PACK_P)$'); POUR = re.compile(r'^(3V3|/?PACK_P)$')
SWN = re.compile(r'/(SW[12]|BTST[12]|HIDRV[12]|HG[12]|SW_5V|BST_5V|SW_3V3)$')
_here = os.path.dirname(os.path.abspath(__file__))      # net classes from the project file: $PRO, the scratch copy, or the repo's
_pro = next(p for p in (os.environ.get('PRO', ''), os.path.join(_here, 'base/Monolith.kicad_pro'), os.path.join(_here, '../Monolith.kicad_pro')) if p and os.path.exists(p))
_pp = json.load(open(_pro))['net_settings']['netclass_patterns']
def ncls(net):
    for p_ in _pp:
        if fnmatch.fnmatchcase(net, p_['pattern']): return p_['netclass']
    return 'Default'
DIRS = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]; DC = [1.0, 1.4142] * 4
def turn(d0, d1):
    if d0 == 8: return 0.0
    k = abs(d0 - d1); k = min(k, 8 - k)
    return (0.0, T45, T90)[k] if k <= 2 else None

def pulltight(segs, env_segs, fixed_pts, W, box, R=0.01):
    """Straighten chains of segments without leaving copper that is known to be legal.
    segs: the net's new tracks (dicts x1 y1 x2 y2 w l). env_segs: copper known legal (the net's old tracks at their old
    width, and the new grid-routed tracks). A run of vertices is replaced by one or two 45/90 degree segments of width W
    when the replacement lies wholly inside that copper (drawn at R mm and shrunk by one pixel), so clearance to
    everything else holds by construction. Vias, pad ends, stubs and T-junctions stay where they are."""
    X0, Y0, X1, Y1 = box; NXf, NYf = int((X1 - X0) / R) + 1, int((Y1 - Y0) / R) + 1
    k2 = lambda x, y: (round(x, 4), round(y, 4)); P = lambda x, y: ((x - X0) / R, (y - Y0) / R)
    def draw(dr, x1, y1, x2, y2, w):
        r = w / 2 / R; a, b = P(x1, y1), P(x2, y2); dr.line([a, b], fill=255, width=max(1, int(round(w / R))))
        for c in (a, b): dr.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=255)
    out = [t for t in segs if t.get('stub')]
    for L in sorted({t['l'] for t in segs}):
        S = [t for t in segs if t['l'] == L and not t.get('stub')]
        if not any(t.get('kept') for t in S): out += S; continue
        im = Image.new('L', (NXf, NYf), 0); dr = ImageDraw.Draw(im)
        for t in env_segs:
            if t['l'] == L: draw(dr, t['x1'], t['y1'], t['x2'], t['y2'], t['w'])
        env = np.array(im.filter(ImageFilter.MinFilter(3))) > 0
        def inside(a, b):
            x0 = max(int((min(a[0], b[0]) - X0 - W) / R), 0); y0 = max(int((min(a[1], b[1]) - Y0 - W) / R), 0)
            x1 = min(int((max(a[0], b[0]) - X0 + W) / R) + 2, NXf); y1 = min(int((max(a[1], b[1]) - Y0 + W) / R) + 2, NYf)
            c = Image.new('L', (x1 - x0, y1 - y0), 0); d2 = ImageDraw.Draw(c); r = W / 2 / R
            pa = ((a[0] - X0) / R - x0, (a[1] - Y0) / R - y0); pb = ((b[0] - X0) / R - x0, (b[1] - Y0) / R - y0)
            d2.line([pa, pb], fill=255, width=max(1, int(round(W / R))))
            for q in (pa, pb): d2.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=255)
            m = np.array(c) > 0
            return bool(np.all(env[y0:y1, x0:x1][m]))
        def connect(a, b):
            dx, dy = b[0] - a[0], b[1] - a[1]; ax, ay = abs(dx), abs(dy); sx = 1 if dx > 0 else -1; sy = 1 if dy > 0 else -1
            if ax < 1e-4 or ay < 1e-4 or abs(ax - ay) < 1e-4: return [a, b] if inside(a, b) else None
            m = min(ax, ay)
            for c in ((a[0] + sx * m, a[1] + sy * m), (b[0] - sx * m, b[1] - sy * m)):      # diagonal first, or straight first
                c = (round(c[0], 4), round(c[1], 4))
                if inside(a, c) and inside(c, b): return [a, c, b]
            return None
        deg = {}; fixed = {k2(*q) for q in fixed_pts}
        for t in S:
            for q in ((t['x1'], t['y1']), (t['x2'], t['y2'])): deg.setdefault(k2(*q), []).append(t)
        def onseg(q, t):
            ax, ay, bx, by = t['x1'], t['y1'], t['x2'], t['y2']; l2 = (bx - ax) ** 2 + (by - ay) ** 2
            if l2 < 1e-9: return False
            u = ((q[0] - ax) * (bx - ax) + (q[1] - ay) * (by - ay)) / l2
            return 0.0 < u < 1.0 and math.hypot(ax + u * (bx - ax) - q[0], ay + u * (by - ay) - q[1]) < 0.006 and min(math.dist(q, (ax, ay)), math.dist(q, (bx, by))) > 0.006
        ends = list(deg) + list(fixed)
        for t in S:
            if any(onseg(q, t) for q in ends): fixed.add(k2(t['x1'], t['y1'])); fixed.add(k2(t['x2'], t['y2']))
        for q, tt in deg.items():
            if len(tt) != 2: fixed.add(q)
        used = set()
        for t0 in S:
            if id(t0) in used: continue
            for q0 in (k2(t0['x1'], t0['y1']), k2(t0['x2'], t0['y2'])):
                if q0 not in fixed or id(t0) in used: continue
                chain = [q0]; t = t0; ts = []
                while True:
                    used.add(id(t)); ts.append(t); a, b = k2(t['x1'], t['y1']), k2(t['x2'], t['y2']); nx = b if a == chain[-1] else a; chain.append(nx)
                    if nx in fixed: break
                    t = [u for u in deg[nx] if id(u) != id(t)][0]
                    if id(t) in used: break
                if not any(u.get('kept') for u in ts) or len(chain) < 3:
                    out += ts; continue
                new = [chain[0]]; i = 0
                while i < len(chain) - 1:
                    best = None
                    for j in range(len(chain) - 1, i + 1, -1):
                        c = connect(chain[i], chain[j])
                        if c: best = (j, c); break
                    if best: new += best[1][1:]; i = best[0]
                    else: new.append(chain[i + 1]); i += 1
                # keep the old width on pieces that were not replaced
                wmap = {(k2(u['x1'], u['y1']), k2(u['x2'], u['y2'])): u for u in ts}; wmap.update({(b_, a_): u for (a_, b_), u in list(wmap.items())})
                for a_, b_ in zip(new, new[1:]):
                    u = wmap.get((a_, b_))
                    out.append(dict(x1=a_[0], y1=a_[1], x2=b_[0], y2=b_[1], w=u['w'] if u else W, l=L, net=ts[0]['net'], **({'kept': 1} if u is not None and u.get('kept') else {})))
        out += [t for t in S if id(t) not in used]
    return merge(out, fixed_pts)

def merge(segs, fixed_pts):
    """join collinear neighbours of equal width and layer at plain two-segment vertices"""
    k2 = lambda x, y: (round(x, 4), round(y, 4)); fixed = {k2(*q) for q in fixed_pts}; segs = list(segs); again = True
    while again:
        again = False; deg = {}
        for t in segs:
            if t.get('stub'):
                for q in ((t['x1'], t['y1']), (t['x2'], t['y2'])): fixed.add(k2(*q))
                continue
            for q in ((t['x1'], t['y1']), (t['x2'], t['y2'])): deg.setdefault((t['l'], k2(*q)), []).append(t)
        for (L, q), tt in deg.items():
            if len(tt) != 2 or q in fixed or tt[0] is tt[1] or abs(tt[0]['w'] - tt[1]['w']) > 1e-6: continue
            a, b = tt; fa = k2(a['x2'], a['y2']) if k2(a['x1'], a['y1']) == q else k2(a['x1'], a['y1']); fb = k2(b['x2'], b['y2']) if k2(b['x1'], b['y1']) == q else k2(b['x1'], b['y1'])
            cr = (q[0] - fa[0]) * (fb[1] - q[1]) - (q[1] - fa[1]) * (fb[0] - q[0]); dt = (q[0] - fa[0]) * (fb[0] - q[0]) + (q[1] - fa[1]) * (fb[1] - q[1])
            if abs(cr) < 1e-6 and dt > 0:
                n = dict(a, x1=fa[0], y1=fa[1], x2=fb[0], y2=fb[1])
                if not (a.get('kept') and b.get('kept')): n.pop('kept', None)
                segs = [t for t in segs if t is not a and t is not b] + [n]; again = True; break
    return segs

def tidy(d, NET, W=0.2, RL=('F', 'In2', 'In3', 'B'), VIAC=2.5, MG=2.5, verbose=False):
    """returns (spec, stats, new_tracks, new_vias); spec is None when a pad could not be joined"""
    RL = list(RL); mypads = [p for p in d['pads'] if p['net'] == NET]; oldt = [t for t in d['tracks'] if t['net'] == NET]; oldv = [v for v in d['vias'] if v['net'] == NET]
    assert len(mypads) >= 2 and oldt, 'net has fewer than two pads or no tracks'
    xs = [p['x'] for p in mypads] + [t[k] for t in oldt for k in ('x1', 'x2')]; ys = [p['y'] for p in mypads] + [t[k] for t in oldt for k in ('y1', 'y2')]
    # grid through the old router's nodes (x on 0.025 + k*0.05, y on 0.0245 + k*0.05), so old via sites are grid points
    X0 = math.floor((min(xs) - MG) / G) * G + 0.025; Y0 = math.floor((min(ys) - MG) / G) * G + 0.0245
    NX = int(round((max(xs) + MG - X0) / G)); NY = int(round((max(ys) + MG - Y0) / G)); X1 = X0 + NX * G; Y1 = Y0 + NY * G
    px = lambda x, y: ((x - X0) / G, (y - Y0) / G)
    inb = lambda x, y, m=2.0: X0 - m <= x <= X1 + m and Y0 - m <= y <= Y1 + m
    def ras(fn):
        im = Image.new('L', (NX, NY), 0); fn(ImageDraw.Draw(im)); return np.array(im) > 0
    def disc(dr, x, y, r, fill=255):
        cx, cy = px(x, y); r /= G; dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
    def seg(dr, t, grow):
        wd = (t['w'] + 2 * grow) / G; dr.line([px(t['x1'], t['y1']), px(t['x2'], t['y2'])], fill=255, width=max(1, int(math.ceil(wd))))
        disc(dr, t['x1'], t['y1'], t['w'] / 2 + grow); disc(dr, t['x2'], t['y2'], t['w'] / 2 + grow)
    def dil(m, r):
        im = Image.fromarray((m * 255).astype(np.uint8)); r = int(math.ceil(r / G))
        while r > 0:
            k = min(r, 7); im = im.filter(ImageFilter.MaxFilter(2 * k + 1)); r -= k
        return np.array(im) > 0
    EPS = 0.005
    def mark(m, x1, y1, x2, y2, r):
        """cells whose centre is closer than r to the segment: exact distance, no raster error"""
        c0 = max(int((min(x1, x2) - r - X0) / G), 0); c1 = min(int((max(x1, x2) + r - X0) / G) + 2, NX)
        r0 = max(int((min(y1, y2) - r - Y0) / G), 0); r1 = min(int((max(y1, y2) + r - Y0) / G) + 2, NY)
        if c0 >= c1 or r0 >= r1: return
        gx = X0 + np.arange(c0, c1) * G; gy = (Y0 + np.arange(r0, r1) * G)[:, None]; dx, dy = x2 - x1, y2 - y1; l2 = dx * dx + dy * dy
        if l2 < 1e-12: d2 = (gx - x1) ** 2 + (gy - y1) ** 2
        else:
            u = np.clip(((gx - x1) * dx + (gy - y1) * dy) / l2, 0.0, 1.0); d2 = (gx - x1 - u * dx) ** 2 + (gy - y1 - u * dy) ** 2
        m[r0:r1, c0:c1] |= d2 < r * r
    KEEP = d.get('keep') or dict(edge=[], npth=[], keepouts=[])
    def _edge(dr):
        for pts, hs in KEEP['edge']:
            dr.polygon([px(*q) for q in pts], fill=255)
            for h in hs: dr.polygon([px(*q) for q in h], fill=0)
    outside = ~ras(_edge) if KEEP['edge'] else np.zeros((NY, NX), bool)
    def kzone(L, what):
        def g(dr):
            for z in KEEP['keepouts']:
                if z.get(what) and L in z['layers']:
                    for pts, hs in z['polys']: dr.polygon([px(*q) for q in pts], fill=255)
        return ras(g)
    me = ncls(NET)
    def clr(net):
        o = ncls(net)
        return 0.25 if (me == 'HighCurrent' and o == 'Default') or (o == 'HighCurrent' and me == 'Default') else 0.15
    T = [t for t in d['tracks'] if t['net'] != NET and (inb(t['x1'], t['y1']) or inb(t['x2'], t['y2']))]
    V = [v for v in d['vias'] if v['net'] != NET and inb(v['x'], v['y'])]
    Pd = [p for p in d['pads'] if p['net'] != NET and inb(p['x'], p['y'], 6)]
    F = [(fl, [(pts, hs) for pts, hs in fl['polys'] if any(inb(x, y) for x, y in pts[::3])]) for fl in d['fills'] if fl['net'] != NET]
    F = [(fl, pl) for fl, pl in F if pl]
    def hard(L):
        base = {}
        for c in (0.15, 0.25):
            def g(dr):
                if c == 0.15:
                    for p in Pd:
                        if p['L'].get(L): dr.polygon([px(*q) for q in p['L'][L]], fill=255)
                for fl, pl in F:
                    if fl['l'] == L and not PLANE.search(fl['net']) and clr(fl['net']) == c:
                        for pts, hs in pl: dr.polygon([px(*q) for q in pts], fill=255)
            base[c] = ras(g)
        kz = kzone(L, 'notracks')
        def blocked(half):
            m = np.zeros((NY, NX), bool)
            for t in T:
                if t['l'] == L: mark(m, t['x1'], t['y1'], t['x2'], t['y2'], t['w'] / 2 + clr(t['net']) + half + EPS)
            for v in V: mark(m, v['x'], v['y'], v['x'], v['y'], v['d'] / 2 + clr(v['net']) + half + EPS)
            for c in (0.15, 0.25):
                if base[c].any(): m |= dil(base[c], c + half + MARG)
            if outside.any(): m |= dil(outside, 0.25 + half + MARG)                      # rule 'Edge margin'
            for h in KEEP['npth']: mark(m, h['x1'], h['y1'], h['x2'], h['y2'], h['w'] / 2 + 0.25 + half + EPS)
            if kz.any(): m |= dil(kz, half + MARG)                                       # rule areas that forbid tracks
            return m
        return blocked
    def pour(L, half):
        def g(dr):
            for fl, pl in F:
                if fl['l'] == L and POUR.search(fl['net']):
                    for pts, hs in pl:
                        dr.polygon([px(*q) for q in pts], fill=255)
                        for h in hs: dr.polygon([px(*q) for q in h], fill=0)
        m = ras(g)
        return dil(m, 0.15 + half) if m.any() else m
    def swcu(L):
        def g(dr):
            for t in T:
                if t['l'] == L and SWN.search(t['net']): seg(dr, t, 0.0)
            for v in V:
                if SWN.search(v['net']): disc(dr, v['x'], v['y'], v['d'] / 2)
            for p in Pd:
                if p['L'].get(L) and SWN.search(p['net']): dr.polygon([px(*q) for q in p['L'][L]], fill=255)
            for fl, pl in F:
                if fl['l'] == L and SWN.search(fl['net']):
                    for pts, hs in pl: dr.polygon([px(*q) for q in pts], fill=255)
        return ras(g)
    def ownpads(L):
        def f(dr):
            for p in mypads:
                if p['L'].get(L): dr.polygon([px(*q) for q in p['L'][L]], fill=255)
        return ras(f)
    blk = {L: hard(L) for L in ALL}; op = {L: ownpads(L) for L in RL}
    ok = {L: ~blk[L](W / 2) for L in RL}
    sw = {L: swcu(L) for L in ALL}; anysw = any(m.any() for m in sw.values())
    cf = {}
    for L in RL:
        c = np.where(pour(L, W / 2), POURX, 1.0)
        if anysw:
            i = ALL.index(L)
            if sw[L].any(): c = c * np.where(dil(sw[L], 1.0), SWX_SAME, 1.0)
            for j in (i - 1, i + 1):
                if 0 <= j < 6 and sw[ALL[j]].any(): c = c * np.where(dil(sw[ALL[j]], 0.6), SWX_ADJ, 1.0)
        cf[L] = c.astype(np.float32)
    viaok = np.ones((NY, NX), bool)
    for L in ALL: viaok &= ~blk[L](VR)
    hm = np.zeros((NY, NX), bool)                             # hole to hole: 0.2 mm to via holes, 0.45 mm to pad holes of 0.5 mm and more
    for v in V: mark(hm, v['x'], v['y'], v['x'], v['y'], v['drill'] / 2 + 0.2 + 0.15 + EPS)
    for p in d['pads']:
        if p.get('hole', 0) > 0 and inb(p['x'], p['y'], 6): mark(hm, p['x'], p['y'], p['x'], p['y'], p['hole'] / 2 + (0.45 if p['hole'] >= 0.5 else 0.2) + 0.15 + 0.2)
    for h in KEEP['npth']: mark(hm, h['x1'], h['y1'], h['x2'], h['y2'], h['w'] / 2 + 0.45 + 0.15 + EPS)
    viaok &= ~hm
    for L in ALL:
        kv = kzone(L, 'novias')
        if kv.any(): viaok &= ~dil(kv, VR + MARG)
    for L in ALL:
        viaok &= ~pour(L, VR)                                 # no new via in a power pour, on any layer
        if sw[L].any(): viaok &= ~dil(sw[L], 1.0 + VR)        # and none within 1 mm of switching copper
    oldsite = np.zeros((NY, NX), bool)
    for v in oldv:
        r, c = int(round((v['y'] - Y0) / G)), int(round((v['x'] - X0) / G))
        if 0 <= r < NY and 0 <= c < NX and abs(X0 + c * G - v['x']) < 0.003 and abs(Y0 + r * G - v['y']) < 0.003: oldsite[r, c] = True
    # An old via site is already drilled, so the hole is legal. Its pads are not legal on every layer: the router's vias
    # have their unused inner pads removed. A pad is allowed where the old via had one (F, B and every layer on which an
    # old track of the net ended at it) or where a pad is legal anyway.
    padok = [~blk[L](VR) for L in RL]
    for v in oldv:
        r, c = int(round((v['y'] - Y0) / G)), int(round((v['x'] - X0) / G))
        if not (0 <= r < NY and 0 <= c < NX and oldsite[r, c]): continue
        for i, L in enumerate(RL):
            if L in ('F', 'B') or any(t['l'] == L and (math.hypot(t['x1'] - v['x'], t['y1'] - v['y']) < 0.01 or math.hypot(t['x2'] - v['x'], t['y2'] - v['y']) < 0.01) for t in oldt): padok[i][r, c] = True
    exact = {}
    p_on = lambda c, e: any(p['L'].get(RL[c[0]]) and abs(p['x'] - e[0]) < 1e-6 and abs(p['y'] - e[1]) < 1e-6 for p in mypads)
    def padcells(p):
        """the grid points next to the pad centre (it is rarely on the grid); the search takes whichever suits the route"""
        r0 = int(math.floor((p['y'] - Y0) / G)); c0 = int(math.floor((p['x'] - X0) / G)); out = []
        for r in (r0, r0 + 1):
            for c in (c0, c0 + 1):
                if 0 <= r < NY and 0 <= c < NX and math.hypot(X0 + c * G - p['x'], Y0 + r * G - p['y']) < 0.045:
                    # only where a track of width W is really legal: beside a fine-pitch neighbour it is not, and the old escape is used
                    cs = [(RL.index(L), r, c) for L in RL if p['L'].get(L) and ok[L][r, c]]
                    if cs: exact[(r, c)] = (p['x'], p['y']); out += cs
        return out
    # Old copper of the net as exact moves. Where the legal corridor is narrower than the grid error (fine-pitch pins,
    # tight gaps) the grid search cannot pass although the old track does. So every old segment between two grid nodes
    # may be reused as it is (it costs its length plus OLDP), and a pad may be left along its old track up to the
    # first grid node. Such segments are kept verbatim, at their old width.
    def gcell(x, y):
        r, c = int(round((y - Y0) / G)), int(round((x - X0) / G))
        return (r, c) if 0 <= r < NY and 0 <= c < NX and abs(X0 + c * G - x) < 0.003 and abs(Y0 + r * G - y) < 0.003 else None
    oe = {}
    for t in oldt:
        if t['l'] not in RL: continue
        a_, b_ = gcell(t['x1'], t['y1']), gcell(t['x2'], t['y2'])
        if a_ and b_ and a_ != b_:
            li = RL.index(t['l']); ln = math.hypot(t['x2'] - t['x1'], t['y2'] - t['y1'])
            oe.setdefault((li,) + a_, []).append((b_[0], b_[1], ln, t)); oe.setdefault((li,) + b_, []).append((a_[0], a_[1], ln, t))
    key = lambda x, y: (round(x, 2), round(y, 2)); adj = {}
    for t in oldt:
        for A, B in (((t['x1'], t['y1']), (t['x2'], t['y2'])), ((t['x2'], t['y2']), (t['x1'], t['y1']))): adj.setdefault((t['l'], key(*A)), []).append((B, t))
    startinfo = {}; links = {}
    def inpoly(x, y, poly):
        c = False; n = len(poly)
        for i in range(n):
            (xa, ya), (xb, yb) = poly[i], poly[(i + 1) % n]
            if (ya > y) != (yb > y) and x < xa + (y - ya) * (xb - xa) / (yb - ya): c = not c
        return c
    def starts(p):
        """grid nodes from which pad p can be left: next to its centre where the new width is legal, and along its old
        escape (from the centre or from any old track end inside the pad: the old router ended tracks anywhere in a pad)
        up to the first grid node. Old copper that runs straight into another pad of the net is noted in links."""
        out = list(padcells(p)); me_ = id(p); links[me_] = []
        for L in RL:
            if not p['L'].get(L): continue
            li = RL.index(L); poly = p['L'][L]; seen = set(); q = []
            for sx_, sy_ in [(p['x'], p['y'])] + [e for t in oldt if t['l'] == L for e in ((t['x1'], t['y1']), (t['x2'], t['y2'])) if inpoly(e[0], e[1], poly)]:
                if key(sx_, sy_) in seen: continue
                seen.add(key(sx_, sy_)); g_ = gcell(sx_, sy_)
                if g_ and ok[L][g_[0], g_[1]] and (sx_, sy_) != (p['x'], p['y']):
                    startinfo.setdefault((li,) + g_, []).append([]); out.append((li,) + g_)
                else: q.append(((sx_, sy_), []))
            while q:
                (x, y), pth = q.pop(0)
                for (bx, by), t in adj.get((L, key(x, y)), []):
                    if key(bx, by) in seen: continue
                    seen.add(key(bx, by)); g_ = gcell(bx, by)
                    for k_, p2 in enumerate(mypads):
                        if p2 is not p and p2['L'].get(L) and not inpoly(bx, by, poly) and inpoly(bx, by, p2['L'][L]): links[me_].append((k_, pth + [t]))
                    if g_: startinfo.setdefault((li,) + g_, []).append(pth + [t]); out.append((li,) + g_)
                    elif len(pth) < 6: q.append(((bx, by), pth + [t]))
        return out
    order = [0]; rest = list(range(1, len(mypads)))           # pads in shortest-tree order
    while rest:
        j = min(rest, key=lambda j: min(math.hypot(mypads[j]['x'] - mypads[i]['x'], mypads[j]['y'] - mypads[i]['y']) for i in order)); order.append(j); rest.remove(j)
    nl = len(RL); tree = np.zeros((nl, NY, NX), bool)
    for li, r, c in starts(mypads[order[0]]): tree[li, r, c] = True
    okA = [ok[L] for L in RL]; cfA = [cf[L] for L in RL]
    def route(src):
        h = (ndimage.distance_transform_edt(~tree.any(axis=0)) * G).astype(np.float32)
        dist = {}; prev = {}; tag = {}; hq = []
        for s in src: st = s + (8,); dist[st] = 0.0; prev[st] = None; heapq.heappush(hq, (float(h[s[1], s[2]]), 0.0, st))
        while hq:
            f_, dd, st = heapq.heappop(hq)
            if dd > dist.get(st, 1e9): continue
            li, y, x, d0 = st
            if tree[li, y, x]: return st, prev, tag
            okL = okA[li]; cfL = cfA[li]
            for d1 in range(8):
                tc = turn(d0, d1)
                if tc is None: continue
                y2, x2 = y + DIRS[d1][0], x + DIRS[d1][1]
                if not (0 <= y2 < NY and 0 <= x2 < NX) or not okL[y2, x2]: continue
                nd = dd + DC[d1] * G * float(cfL[y2, x2]) + tc; s2 = (li, y2, x2, d1)
                if nd < dist.get(s2, 1e9): dist[s2] = nd; prev[s2] = st; tag[s2] = None; heapq.heappush(hq, (nd + float(h[y2, x2]), nd, s2))
            for y2, x2, ln, t in oe.get((li, y, x), ()):
                nd = dd + ln * max(float(cfL[y, x]), float(cfL[y2, x2])) + OLDP; s2 = (li, y2, x2, 8)
                if nd < dist.get(s2, 1e9): dist[s2] = nd; prev[s2] = st; tag[s2] = t; heapq.heappush(hq, (nd + float(h[y2, x2]), nd, s2))
            if viaok[y, x] or (oldsite[y, x] and padok[li][y, x]):
                for l2 in range(nl):
                    if l2 != li and (okA[l2][y, x] if viaok[y, x] else padok[l2][y, x]):
                        nd = dd + (VIAC * 0.6 if oldsite[y, x] else VIAC); s2 = (l2, y, x, 8)
                        if nd < dist.get(s2, 1e9): dist[s2] = nd; prev[s2] = st; tag[s2] = None; heapq.heappush(hq, (nd + float(h[y, x]), nd, s2))
        return None, prev, tag
    mm = lambda r, c: (round(X0 + c * G, 4), round(Y0 + r * G, 4))
    add = []; newv = []; newt = []; stubbed = set(); keptids = set()
    def keep(t):
        if id(t) not in keptids: keptids.add(id(t)); newt.append(dict(t, w=min(t['w'], W), kept=1)); add.append(dict(net=NET, layer=t['l'], w=min(t['w'], W), pts=[[t['x1'], t['y1']], [t['x2'], t['y2']]], kept=1))
    def emit(L, P):
        add.append(dict(net=NET, layer=L, w=W, pts=[list(q) for q in P]))
        for k in range(len(P) - 1): newt.append(dict(x1=P[k][0], y1=P[k][1], x2=P[k + 1][0], y2=P[k + 1][1], w=W, l=L, net=NET))
    fail = None
    joined = {order[0]}
    for j in order[1:]:
        p = mypads[j]; src = starts(p)
        lk = [pth for k_, pth in links[id(p)] if k_ in joined]
        if lk:                                                    # old copper runs straight into a pad that is already joined: keep it
            for t in min(lk, key=len): keep(t)
            for c in src: tree[c[0], c[1], c[2]] = True
            joined.add(j)
            if verbose: print('  pad %s.%s joined by its old direct link' % (p['ref'], p['n']))
            continue
        end, prev, tag = route(src)
        if end is None:
            fail = p['ref'] + '.' + p['n']
            if verbose: print('  FAIL at', fail, 'starts', len(src), 'states explored', len(prev), 'tree cells', int(tree.sum()), 'start cells', src[:6], 'old escape', [(round(t['x1'], 3), round(t['y1'], 3), round(t['x2'], 3), round(t['y2'], 3), t['l']) for n_ in src[:1] for pth_ in startinfo.get(n_, []) for t in pth_])
            break
        path = []; c = end
        while c is not None: path.append(c); c = prev[c]
        path.reverse()
        for node in (path[0][:3], path[-1][:3]):                 # left or reached a pad along its old escape
            for pth_ in startinfo.get(node, ()):                 # every old escape that ends here (two pads may share the node)
                for t in pth_: keep(t)
        cur = [path[0]]
        def flush():
            if len(cur) > 1:
                pts = [cur[0]]
                for k in range(1, len(cur)):
                    if k == len(cur) - 1 or (cur[k][1] - cur[k - 1][1], cur[k][2] - cur[k - 1][2]) != (cur[k + 1][1] - cur[k][1], cur[k + 1][2] - cur[k][2]): pts.append(cur[k])
                emit(RL[cur[0][0]], [mm(c[1], c[2]) for c in pts])
        for a_, b_ in zip(path, path[1:]):
            tree[a_[0], a_[1], a_[2]] = True; tree[b_[0], b_[1], b_[2]] = True
            if b_[0] != a_[0]:                                    # via
                flush(); cur = [b_]; v = mm(b_[1], b_[2]); add.append(dict(net=NET, via=list(v))); newv.append(dict(x=v[0], y=v[1], d=0.45, drill=0.3, net=NET))
                for l_ in range(nl):
                    if viaok[b_[1], b_[2]] or padok[l_][b_[1], b_[2]]: tree[l_, b_[1], b_[2]] = True
            elif tag.get(b_) is not None: flush(); cur = [b_]; keep(tag[b_])
            else: cur.append(b_)
        flush()
        for c in (path[0], path[-1]):                            # a pad centre is not on the grid: tiny stub inside the pad copper
            e = exact.get((c[1], c[2])); L = RL[c[0]]
            if e and c[:3] not in startinfo and p_on(c, e) and c[:3] not in stubbed and math.dist(e, mm(c[1], c[2])) > 0.002:
                q = mm(c[1], c[2]); add.append(dict(net=NET, layer=L, w=0.15, pts=[list(q), list(e)], stub=1)); stubbed.add(c[:3])
                newt.append(dict(x1=q[0], y1=q[1], x2=e[0], y2=e[1], w=0.15, l=L, net=NET, stub=1))
        for c in src: tree[c[0], c[1], c[2]] = True
        if verbose: print('  pad %s.%s joined' % (p['ref'], p['n']))
        joined.add(j)
    # No pour may fall apart. The fill after a refill is estimated: today's fill, plus the cuts of this net's old copper
    # where nothing else blocks them (they heal), minus the new copper with its clearance.
    #  - power pours and inner planes: the number of pieces (40 cells and more) must not go up;
    #  - the GND fill on the outer layers is a patchwork tied down by vias, there a cut is normal. What must not happen:
    #    a piece that holds a GND pad and has no GND via or plated hole of its own (the pad would be unconnected).
    split = None
    if fail is None:
        for L in ALL:
            cor = np.zeros((NY, NX), bool)
            for t in newt:
                if t['l'] == L and not t.get('kept'): mark(cor, t['x1'], t['y1'], t['x2'], t['y2'], t['w'] / 2 + 0.2 + G)
            for v in newv:
                if not oldsite[int(round((v['y'] - Y0) / G)), int(round((v['x'] - X0) / G))]: mark(cor, v['x'], v['y'], v['x'], v['y'], VR + 0.2 + G)
            if not cor.any(): continue
            heal = np.zeros((NY, NX), bool)
            for t in oldt:
                if t['l'] == L: mark(heal, t['x1'], t['y1'], t['x2'], t['y2'], t['w'] / 2 + 0.25 + G)
            for v in oldv: mark(heal, v['x'], v['y'], v['x'], v['y'], v['d'] / 2 + 0.25 + G)
            if heal.any(): heal &= ~blk[L](0.05)
            for pn in sorted({fl['net'] for fl, pl in F if fl['l'] == L and PLANE.search(fl['net'])}):
                def g(dr):
                    for fl, pl in F:
                        if fl['l'] == L and fl['net'] == pn:
                            for pts, hs in pl:
                                dr.polygon([px(*q) for q in pts], fill=255)
                                for h in hs: dr.polygon([px(*q) for q in h], fill=0)
                m = ras(g)
                if not m.any(): continue
                m2 = (m | (heal & dil(m, 2 * G))) & ~cor if heal.any() else m & ~cor
                if pn == 'GND' and L in ('F', 'B'):
                    def gp_(dr):
                        for p_ in Pd:
                            if p_['net'] == pn and p_['L'].get(L): dr.polygon([px(*q) for q in p_['L'][L]], fill=255)
                    gp = ras(gp_); cu_ = np.zeros((NY, NX), bool)
                    for t in T:
                        if t['net'] == pn and t['l'] == L: mark(cu_, t['x1'], t['y1'], t['x2'], t['y2'], t['w'] / 2)
                    anc = np.zeros((NY, NX), bool)
                    for v in V:
                        if v['net'] == pn: mark(anc, v['x'], v['y'], v['x'], v['y'], v['d'] / 2)
                    for p_ in Pd:
                        if p_['net'] == pn and p_.get('hole', 0) > 0 and p_['L'].get(L): mark(anc, p_['x'], p_['y'], p_['x'], p_['y'], p_['hole'] / 2 + 0.1)
                    def orphans(mm_):
                        lab, n = ndimage.label(mm_ | gp | cu_ | anc, structure=np.ones((3, 3)))
                        if not n: return 0
                        has = lambda msk: np.bincount(lab[msk], minlength=n + 1) > 0
                        edge_ = np.zeros((NY, NX), bool); edge_[0, :] = edge_[-1, :] = edge_[:, 0] = edge_[:, -1] = True
                        bad = has(gp) & ~has(anc) & ~has(edge_); bad[0] = False
                        return int(bad.sum())
                    if orphans(m2) > orphans(m): split = L + ' ' + pn + ' (a GND pad would lose its fill)'; break
                else:
                    def pieces(mm_):
                        lab, n = ndimage.label(mm_)
                        return int((np.bincount(lab.ravel())[1:] >= 40).sum()) if n else 0
                    if pieces(m2) > pieces(m): split = L + ' ' + pn; break
            if split: break
        if split: fail = 'splits pour ' + split
    nk0 = sum(1 for t in newt if t.get('kept'))
    if fail is None and nk0:
        fixed_pts = [(v['x'], v['y']) for v in newv] + [(p['x'], p['y']) for p in mypads] + [q for t in newt if t.get('stub') for q in ((t['x1'], t['y1']), (t['x2'], t['y2']))]
        fixed_pts += [(v['x'], v['y']) for v in oldv]
        newt = pulltight(newt, oldt + [t for t in newt if not t.get('kept') and not t.get('stub')], fixed_pts, W, [X0, Y0, X1, Y1])
    spec = [dict({'del': [t['x1'], t['y1']]}, net=NET, what=t['l']) for t in oldt] + [dict({'del': [v['x'], v['y']]}, net=NET, what='via') for v in oldv]
    spec += [dict(net=NET, via=[v['x'], v['y']], rul=1) for v in newv]
    spec += [dict(net=NET, layer=t['l'], w=t['w'], pts=[[t['x1'], t['y1']], [t['x2'], t['y2']]], **{k: 1 for k in ('kept', 'stub') if t.get(k)}) for t in newt]
    tot = sum(math.hypot(t['x2'] - t['x1'], t['y2'] - t['y1']) for t in newt)
    old_len = sum(math.hypot(t['x2'] - t['x1'], t['y2'] - t['y1']) for t in oldt)
    st = dict(net=NET, ok=fail is None, failed_at=fail, w=W, old=dict(length=old_len, segs=len(oldt), vias=len(oldv)),
              new=dict(length=tot, segs=sum(1 for t in newt if not t.get('stub')), vias=len(newv), kept=sum(1 for t in newt if t.get('kept')), kept_before_pull=nk0), box=[X0, Y0, X1, Y1])
    return (None if fail else spec), st, newt, newv

if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]; OPT = dict(x[2:].split('=', 1) for x in sys.argv[1:] if x.startswith('--'))
    d = json.load(open(a[0])); kf = OPT.get('keep', os.path.join(os.path.dirname(a[0]), 'keep.json'))
    if os.path.exists(kf): d['keep'] = json.load(open(kf))
    else: print('NO keep.json: board edge, unplated holes and keep-outs are NOT respected')
    spec, st, nt, nv = tidy(d, a[1], W=float(OPT.get('w', 0.2)), RL=OPT.get('layers', 'F,In2,In3,B').split(','), VIAC=float(OPT.get('viacost', 2.5)), MG=float(OPT.get('marg', 2.5)), verbose=True)
    print(json.dumps(st))
    if spec: json.dump(spec, open(a[2], 'w'))
    if 'stats' in OPT: json.dump(st, open(OPT['stats'], 'w'))
    sys.exit(0 if spec else 1)
