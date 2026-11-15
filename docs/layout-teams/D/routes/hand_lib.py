import sys, time; sys.path.insert(0, '../tools')
from mroute import MR
t=time.time(); m = MR('/home/claude/runs/r2_route', 'r2'); print('load %.0f s' % (time.time()-t))
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
