import sys, time; sys.path.insert(0, '../tools')
from mroute import MR
t=time.time(); import os; m = MR(os.environ.get('HD', '/home/claude/runs/r2_route'), os.environ.get('HB', 'r2')); print('load %.0f s' % (time.time()-t))
nets = sorted({n for L in m.items for _, n, kind, _ in m.items[L] if n and n not in ("GND", "<keepout>")})
def why(net, w=0.15, margin=6.0):
    cs = m.clusters(net)
    for small in cs[1:]:
        r = m.join(net, small, cs[0], w=w, margin=margin, quiet=True, ghost=set(nets) - {net}); print('  why', net, '->', r[2] if r else 'WALLED')
def st(net): print('  %s: %d pieces' % (net, len(m.clusters(net))))
def joinall(net, w=0.15, margin=6.0, **kw):
    for k in range(10):
        cs = m.clusters(net)
        if len(cs) < 2: break
        if not any(m.join(net, c, cs[0], w=w, margin=margin, **kw) is not None for c in reversed(cs[1:])): break
    st(net)

import copy
from shapely.strtree import STRtree
def snap(): return ({L: list(v) for L, v in m.items.items()}, list(m.vias), copy.deepcopy(m.J))
def restore(s):
    m.items = {L: list(v) for L, v in s[0].items()}; m.vias = list(s[1]); m.J = copy.deepcopy(s[2])
    for L in m.items: m.tree[L] = STRtree([i[0] for i in m.items[L]])
def one(net): return len(m.clusters(net)) < 2
import math
from shapely.geometry import box as sbox, Point
def rip_box(net, box, layers=('F.Cu', 'In2.Cu', 'In3.Cu', 'B.Cu'), vias=True):
    """pull the board's tracks of a net whose two ends lie inside the box, and its vias there (same test as hr2's drop)"""
    for L in layers:
        keep = []
        for it in m.items[L]:
            geo, n, kind, name = it
            if n == net and kind == 'track':
                P, A = geo.length, geo.area; w = (P / 2 - math.sqrt(max(P * P / 4 - math.pi * A, 0))) / (math.pi / 2)
                if geo.within(sbox(box[0] - w / 2 - 0.01, box[1] - w / 2 - 0.01, box[2] + w / 2 + 0.01, box[3] + w / 2 + 0.01)): continue
            if vias and n == net and kind == 'via' and sbox(*box).contains(geo.centroid): continue
            keep.append(it)
        m.items[L] = keep; m.tree[L] = STRtree([i[0] for i in keep])
        m.J['drop'].append({'net': net, 'layer': L, 'box': list(box), 'tracks_only': True})
    if vias:
        m.vias = [v for v in m.vias if not (v[3] == net and box[0] <= v[0] <= box[2] and box[1] <= v[1] <= box[3])]
        m.J['drop'].append({'net': net, 'layer': 'none', 'box': list(box)})          # no segment is on layer 'none': vias only
def swap(stuck, victims, box, layers=('F.Cu', 'In2.Cu', 'In3.Cu', 'B.Cu'), margin=9.0):
    """pull the victims' tracks inside the box, lay the stuck net first, re-lay the victims; undone if anything stays open"""
    s = snap(); print('swap', stuck, 'past', victims)
    for v in victims: rip_box(v, box, layers)
    joinall(stuck, margin=margin)
    for v in victims: joinall(v, margin=margin)
    if one(stuck) and all(one(v) for v in victims): return True
    why(stuck, margin=margin)
    for v in victims: why(v, margin=margin)
    restore(s); print('  undone'); return False

import itertools
def group(netlist, box, margin=9.0, maxtry=24, boxes={}):
    """pull every listed net's tracks and vias inside the box and lay them again, trying orders until all are whole"""
    s = snap(); print('group', netlist)
    for k, order in enumerate(itertools.permutations(netlist)):
        if k >= maxtry: break
        restore(s)
        for v in netlist: rip_box(v, boxes.get(v, box))
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            for v in order: joinall(v, margin=margin)
        bad = [v for v in order if not one(v)]
        print('  order', [v.split('/')[-1] for v in order], 'open:', [v.split('/')[-1] for v in bad], flush=True)
        if not bad: return True
    restore(s); print('  undone'); return False
from shapely.geometry import LineString
from obst import SIG
def viol(net, geom, L, via=False):
    out = []
    for i in m.tree[L].query(geom.buffer(0.3)):
        g, n, kind, name = m.items[L][int(i)]
        if n == net or kind == 'keepout' or (kind == 'pour' and m.soft_pour(n, L)): continue
        d = geom.distance(g); c = m.clr(net, n, kind)
        if d < c - 1e-6: out.append((round(d, 3), kind, n.split('/')[-1], name, L[:-3]))
    return out
def stub(net, pts, w=0.15, L='F.Cu', via=True):
    """a hand-drawn escape: track along pts on one layer, a via at the last point; checked against the real rules"""
    bad = viol(net, LineString(pts).buffer(w / 2), L)
    if via:
        x, y = pts[-1]
        for l in SIG: bad += viol(net, Point(x, y).buffer(0.225), l)
        bad += [(round(math.hypot(v[0] - x, v[1] - y), 3), 'via spacing', v[3]) for v in m.vias if 1e-6 < math.hypot(v[0] - x, v[1] - y) < 0.6]
    if bad: print('  stub %s PROBLEM %s' % (net, bad[:5]))
    m.J['routes'].append({'net': net, 'w': w, 'path': [[L, round(p[0], 3), round(p[1], 3)] for p in pts]}); m._add(L, LineString(pts).buffer(w / 2), net, 'track')
    if via:
        m.J['vias'].append({'net': net, 'x': x, 'y': y}); m.vias.append((x, y, 0.45, net))
        for l in SIG: m._add(l, Point(x, y).buffer(0.225), net, 'via')
    return not bad
def via_sites(net, box, step=0.05):
    """legal via centres for a net inside a box (real rules, all four signal layers, 0.6 mm via spacing)"""
    out = []; x = box[0]
    while x <= box[2] + 1e-9:
        y = box[1]
        while y <= box[3] + 1e-9:
            g = Point(x, y).buffer(0.225)
            if not any(viol(net, g, l) for l in SIG) and not any(1e-6 < math.hypot(v[0] - x, v[1] - y) < 0.6 for v in m.vias) and not any(k.buffer(0.225).contains(Point(x, y)) for k in m.ko_v): out.append((round(x, 2), round(y, 2)))
            y += step
        x += step
    return out
def escape_try(net, pad, victims, box, sites_box, margin=9.0, maxtry=40, first=(0, 0.25)):
    """pull the victims inside the box; try each legal via site near a walled pad: hand stub pad -> (pad + first) -> site,
    then lay the net and the victims again; keep the first site where everything ends whole"""
    import io, contextlib
    s0 = snap()
    for v in victims: rip_box(v, box)
    s1 = snap(); sites = sorted(via_sites(net, sites_box), key=lambda p: math.hypot(p[0] - pad[0], p[1] - pad[1]))
    print('escape', net, 'at', pad, ':', len(sites), 'via sites')
    for k, sx in enumerate(sites[:maxtry]):
        restore(s1); pts = [pad, (pad[0] + first[0], pad[1] + first[1]), sx]
        if viol(net, LineString(pts).buffer(0.075), 'F.Cu'): continue
        with contextlib.redirect_stdout(io.StringIO()):
            stub(net, pts); joinall(net, margin=margin)
            for v in victims: joinall(v, margin=margin)
        bad = [v.split('/')[-1] for v in [net] + victims if not one(v)]
        print('  site', sx, 'open:', bad, flush=True)
        if not bad: return True
    restore(s0); print('  undone'); return False
def rip_hit(net, geom, layers=('In2.Cu',), clr=0.3):
    """pull the board tracks of a net on the given layers that come within clr of a shape, and its vias there"""
    z = geom.buffer(clr); n_t = n_v = 0
    for L in SIG:
        keep = []
        for it in m.items[L]:
            geo, n, kind, name = it
            if n == net and kind == 'track' and L in layers and geo.intersects(z):
                P, A = geo.length, geo.area; w = (P / 2 - math.sqrt(max(P * P / 4 - math.pi * A, 0))) / (math.pi / 2); b = geo.bounds
                m.J['drop'].append({'net': net, 'layer': L, 'box': [b[0] + w / 2 - 0.01, b[1] + w / 2 - 0.01, b[2] - w / 2 + 0.01, b[3] - w / 2 + 0.01], 'tracks_only': True}); n_t += 1; continue
            if n == net and kind == 'via' and geo.intersects(z):
                c = geo.centroid
                if L == SIG[0]: m.J['drop'].append({'net': net, 'layer': 'none', 'box': [c.x - 0.01, c.y - 0.01, c.x + 0.01, c.y + 0.01]}); n_v += 1
                continue
            keep.append(it)
        m.items[L] = keep; m.tree[L] = STRtree([i[0] for i in keep])
    m.vias = [v for v in m.vias if not (v[3] == net and Point(v[0], v[1]).buffer(0.225).intersects(z))]
    print('  pulled %d tracks, %d vias of %s' % (n_t, n_v, net))
ELIG = {n for n in nets if m.cls(n) in ('Default', 'Kelvin', 'GateDrive')}
def cross(stuck, margin=12.0, r=1.0, extra=(), w=0.15):
    """local rip-up: ask which lines the cheapest path of a stuck net crosses and where, pull each only round its crossing
    point (radius r), lay the stuck net, re-lay the pulled lines; everything undone if a line stays open"""
    s = snap(); cs = m.clusters(stuck)
    if len(cs) < 2: return True
    wh = {}
    for small in cs[1:]:
        g = m.join(stuck, small, cs[0], w=w, margin=margin, quiet=True, ghost=(ELIG | set(extra)) - {stuck})
        if g and len(g) > 2: wh.update(g[2])
    print('cross', stuck, wh, flush=True)
    for v, (L, x, y) in wh.items(): rip_hit(v, Point(x, y).buffer(r), layers=SIG, clr=0.0)
    joinall(stuck, margin=margin)
    for v in wh: joinall(v, margin=margin)
    bad = [v for v in [stuck] + list(wh) if not one(v)]
    if not bad: return True
    for v in bad: why(v, margin=margin)
    restore(s); print('  undone'); return False
def cross2(stuck, depth=2, chain=frozenset(), margin=12.0, r=1.0, w=0.15, ind=''):
    """cross() with depth: a pulled line that cannot be re-laid may itself pull others locally (never a line of its own chain)"""
    import io, contextlib
    s = snap()
    with contextlib.redirect_stdout(io.StringIO()): joinall(stuck, margin=margin, w=w)
    if one(stuck): return True
    restore(s); cs = m.clusters(stuck); wh = {}
    for small in cs[1:]:
        g = m.join(stuck, small, cs[0], w=w, margin=margin, quiet=True, ghost=ELIG - chain - {stuck})
        if g and len(g) > 2: wh.update(g[2])
    print('%scross %s %s' % (ind, stuck.split('/')[-1], {k.split('/')[-1]: v for k, v in wh.items()}), flush=True)
    if not wh: return False
    with contextlib.redirect_stdout(io.StringIO()):
        for v, (L, x, y) in wh.items(): rip_hit(v, Point(x, y).buffer(r), layers=SIG, clr=0.0)
        joinall(stuck, margin=margin, w=w)
    if not one(stuck): restore(s); print('%s  %s still open, undone' % (ind, stuck.split('/')[-1])); return False
    for v in wh:
        if not cross2(v, depth - 1, chain | {stuck} | set(wh), margin, r, w, ind + '    ') if depth > 0 else not _j(v, margin, w):
            restore(s); print('%s  could not re-lay %s, undone' % (ind, v.split('/')[-1])); return False
    print('%s  %s closed' % (ind, stuck.split('/')[-1])); return True
def _j(v, margin, w):
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()): joinall(v, margin=margin, w=w)
    return one(v)

from shapely.ops import unary_union
import io, contextlib
def piecewise(net, w=0.2, margin=9.0, r=1.0):
    """close a net piece by piece; each piece on its own may pull lines locally, undone per piece if they do not come back"""
    done = set()
    for k in range(8):
        cs = m.clusters(net); todo = [c for c in cs[1:] if tuple(round(v, 1) for v in unary_union([g for gs in c.values() for g in gs]).bounds) not in done]
        if not todo: break
        c = todo[-1]; key = tuple(round(v, 1) for v in unary_union([g for gs in c.values() for g in gs]).bounds); done.add(key); s0 = snap(); n0 = len(cs)
        if m.join(net, c, cs[0], w=w, margin=margin, quiet=True) is not None and len(m.clusters(net)) < n0: print('  piece', key, 'joined'); continue
        restore(s0); g = m.join(net, c, cs[0], w=w, margin=margin, quiet=True, ghost=ELIG - {net})
        if not g or len(g) < 3 or not g[2]: print('  piece', key, 'walled'); continue
        with contextlib.redirect_stdout(io.StringIO()):
            for v, (L, x, y) in g[2].items(): rip_hit(v, Point(x, y).buffer(r), layers=SIG, clr=0.0)
            cs2 = m.clusters(net); c2 = min(cs2[1:], key=lambda q: unary_union([g_ for gs in q.values() for g_ in gs]).distance(unary_union([g_ for gs in c.values() for g_ in gs])))
            ok = m.join(net, c2, cs2[0], w=w, margin=margin, quiet=True) is not None and len(m.clusters(net)) < n0
            if ok:
                for v in g[2]: joinall(v, margin=margin)
        if ok and all(one(v) for v in g[2]): print('  piece', key, 'joined after re-laying', list(g[2])); continue
        restore(s0); print('  piece', key, 'not joined; in the way:', g[2])
