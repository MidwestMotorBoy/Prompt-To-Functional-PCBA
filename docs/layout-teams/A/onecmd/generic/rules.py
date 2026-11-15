"""rules.py - placement rules that replace typed coordinates (team A onecmd, round 2).

Every rule reads only the footprint geometry (glib.DB), the netlist (pad nets), constraints.json and the poses of
parts already placed (fixed parts, anchors). Nothing here names a reference designator of the Monolith board.

  stage_poses()     charger-stage template (stage_template.json, poses relative to the switch FET) hung from the
                    FIXED inductor of each port: no absolute coordinate.
  pd_rotation()     PD chip rotation: its big power pads (>= 3x median pad area, on constraints power nets) face the
                    connector's VBUS pins and the charger inductor that the PPHV path feeds, so no pin row lies between.
  sense_targets()   the sense resistor of a big power pad sits beside that pad, one shunt-cap length out, running along
                    the chip side toward the consumer: the shunt cap fits between pad and resistor.
  tvs_targets()     a TVS (diode with pads on a connector's VBUS and GND) sits at the connector VBUS pin nearest the
                    PD chip's VBUS pad.
  pincap_shift()    a power pin's own decoupling cap is aimed one pin pitch off the pin, toward the side of the row
                    with fewer signal pins, so the signal neighbours keep their exit.
  walled_pullups()  a 2-pad part on a signal pin that lies within WALL_MM (pad edge to pad edge) of a power pad of the
                    same IC (that pin gets no escape room from the power pour) sits straight out in front of the pin,
                    its axis along the row normal, its signal pad PULL_MM from the pin centre.
"""
import json, math, re
import numpy as np
from glib import rotv

WALL_MM = 0.75     # pad-edge distance from a signal pin to a power pad of the same IC below which the pin is walled
PULL_MM = 0.9      # centre distance pin -> pull-up signal pad (merged3: R541 0.82, R455 1.0)


def mp(ref, m):
    return re.sub(m[0], m[1], ref) if m else ref


def stage_poses(T, P):
    """T = stage template dict; P = placed poses (must hold the template's anchor_from inductor and its port maps).
    Returns {ref: (x, y, rot)} for every template part of every port, and the keep boxes in world coordinates."""
    out = {}; keeps = []
    f = T['anchor_from']
    for port, pd in T['ports'].items():
        m = pd.get('map'); L = mp(f['ref'], m)
        if L not in P: raise RuntimeError(f'stage template: inductor {L} not placed')
        fx, fy, fr = P[L]; dx, dy = rotv(f['dx'], f['dy'], fr)
        ax, ay, ar = fx + dx, fy + dy, (fr + f['drot']) % 360
        for ref, q in T['parts'].items():
            r = mp(ref, m); ddx, ddy = rotv(q['dx'], q['dy'], ar)
            out[r] = (round(ax + ddx, 3), round(ay + ddy, 3), round((ar + q['drot'] + 180) % 360 - 180, 1))
        for k in T.get('keep', []):
            cs = [rotv(u, v, ar) for u, v in ((k[0], k[1]), (k[2], k[1]), (k[2], k[3]), (k[0], k[3]))]
            keeps.append((ax + min(c[0] for c in cs), ay + min(c[1] for c in cs), ax + max(c[0] for c in cs), ay + max(c[1] for c in cs)))
    return out, keeps


def _area(p): return p['sx'] * p['sy']


def big_power_pads(db, r, cnets, norm):
    """numbered pads of IC r with area >= 3x the median pad and on a constraints power net"""
    ps = [p for p in db.fp[r]['pads'] if p['n'] and p['net']]
    med = float(np.median([_area(p) for p in ps]))
    return [p for p in ps if _area(p) >= 3 * med and cnets.get(norm(p['net']), {}).get('kind') == 'power']


def _axis(v):
    """unit vector along the dominant axis of v"""
    return (math.copysign(1.0, v[0]), 0.0) if abs(v[0]) >= abs(v[1]) else (0.0, math.copysign(1.0, v[1]))


def pd_rotation(db, r, at, P, C, cnets, norm):
    """rotation of PD chip r placed at (x, y): big power pads toward mean(connector VBUS pins, charger inductor).
    The connector = J part with pads on a big-pad net; the inductor = constraints draw entry whose rin resistor has a pad
    on a big-pad net. Returns (rot, why)."""
    big = big_power_pads(db, r, cnets, norm)
    nets = {p['net'] for p in big}
    goal = []
    for q, (x, y, rot) in P.items():
        if not q.startswith('J'): continue
        pts = [db.pad(P, q, p['n']) for p in db.fp[q]['pads'] if p['net'] in nets]
        if pts: goal.append(np.mean(pts, 0)); con = q
    for st in C.get('draw', {}).values():
        rin = st.get('rin')
        if rin and any(p['net'] in nets for p in db.fp[rin]['pads']) and st.get('inductor') in P:
            goal.append(np.array(P[st['inductor']][:2])); ind = st['inductor']
    v = np.mean(goal, 0) - np.array(at)
    v = v / (np.linalg.norm(v) + 1e-9)
    cen = np.mean([[p['lx'], p['ly']] for p in big], 0)
    best = None
    for rot in (0, 90, 180, 270):
        n = np.array(rotv(cen[0], cen[1], rot)); n = n / (np.linalg.norm(n) + 1e-9)
        s = float(n @ v)
        if best is None or s > best[0]: best = (s, rot)
    return best[1], f'pd chip: big pads {sorted(p["n"] for p in big)} toward connector {con} VBUS + inductor {ind} (dot {best[0]:.2f})'


def pad_world(db, P, r, n):
    return np.array(db.pad(P, r, n))


def sense_targets(db, P, rs, chip, C, cnets, norm, serves):
    """targets for sense resistor rs beside chip's big pad on its net. Returns (targets, why) or None."""
    big = {p['net']: p for p in big_power_pads(db, chip, cnets, norm)}
    mine = [p for p in db.fp[rs]['pads'] if p['net'] in big]
    if not mine: return None
    pr = mine[0]; other = [p for p in db.fp[rs]['pads'] if p['n'] != pr['n']][0]
    bp = big[pr['net']]; p = pad_world(db, P, chip, bp['n'])
    n = np.array(_axis(p - np.array(P[chip][:2])))
    t = np.array([-n[1], n[0]])
    # consumer side along the chip edge: the draw entry that names rs as rin -> its inductor
    for st in C.get('draw', {}).values():
        if st.get('rin') == rs and st.get('inductor') in P:
            if float((np.array(P[st['inductor']][:2]) - p) @ t) < 0: t = -t
    # the shunt cap that serves that pin sets the gap
    caps = [c for c, s in serves.items() if s.split('.')[0] == chip and any(q['net'] == pr['net'] for q in db.fp[c]['pads'])]
    if caps:
        b = db.fp[caps[0]]['box']; clen = b[2] - b[0]; cwid = b[3] - b[1]
    else: clen, cwid = 1.0, 0.5
    rb = db.fp[rs]['box']; rlen = rb[2] - rb[0]
    d1 = clen + 0.5; d2 = cwid + rlen / 2 - 0.15
    q1 = p + n * d1 + t * d2
    sep = math.hypot(pr['lx'] - other['lx'], pr['ly'] - other['ly'])
    q2 = q1 + t * sep
    return [(pr['n'], np.array([q1]), 1.0), (other['n'], np.array([q2]), 1.0)], \
        f'sense beside {chip}.{bp["n"]}: +{d1:.2f} out, +{d2:.2f} along toward the consumer (cap {caps[0] if caps else "-"})'


def tvs_targets(db, P, d, chip, cnets, norm):
    """targets for TVS d: its pads on the connector VBUS net -> connector VBUS pad nearest chip's VBUS big pad"""
    big = {p['net']: p for p in big_power_pads(db, chip, cnets, norm)}
    vb = [p for p in db.fp[d]['pads'] if p['net'] in big and p['n']]
    if not vb: return None
    net = vb[0]['net']
    bigv = max((p for p in db.fp[chip]['pads'] if p['n'] and p['net'] == net), key=_area)   # the chip's largest pad on that net
    cp = pad_world(db, P, chip, bigv['n'])
    best = None
    for q in P:
        if not q.startswith('J'): continue
        for p in db.fp[q]['pads']:
            if p['net'] == net:
                w = pad_world(db, P, q, p['n']); dd = float(np.hypot(*(w - cp)))
                if best is None or dd < best[0]: best = (dd, q, p['n'], w)
    if best is None: return None
    T = [(p['n'], np.array([best[3]]), 1.0) for p in vb]
    return T, f'tvs at {best[1]}.{best[2]} (connector VBUS pin nearest {chip}.{bigv["n"]}, its largest VBUS pad)'


def _row(db, r, n):
    """small pads in the same row as pad n of IC r: returns (axis index along the row, pitch, list of pads)"""
    ps = [p for p in db.fp[r]['pads'] if p['n'] and p['net'] is not None]
    me = [p for p in ps if p['n'] == n][0]
    a0 = _area(me)
    for ax in (0, 1):     # row along x: same ly
        k = 'ly' if ax == 0 else 'lx'
        row = [p for p in ps if abs(p[k] - me[k]) < 0.05 and _area(p) <= 4 * a0]
        if len(row) >= 4:
            kk = 'lx' if ax == 0 else 'ly'
            xs = sorted(p[kk] for p in row); pitch = float(np.median(np.diff(xs)))
            return ax, pitch, row, me
    return None


def is_signal(net, plane, cnets, norm):
    return bool(net) and net not in plane and cnets.get(norm(net), {}).get('kind') not in ('power',) and not net.startswith('unconnected')


def pincap_shift(db, P, chip, n, plane, cnets, norm, reach=1.3):
    """world shift for the target of a power pin's decoupling cap: one pitch toward the row side with fewer signal pins"""
    rr = _row(db, chip, n)
    if not rr: return np.zeros(2), 'no row'
    ax, pitch, row, me = rr
    kk = 'lx' if ax == 0 else 'ly'
    lo = sum(1 for p in row if -reach < p[kk] - me[kk] < -0.01 and is_signal(p['net'], plane, cnets, norm))
    hi = sum(1 for p in row if 0.01 < p[kk] - me[kk] < reach and is_signal(p['net'], plane, cnets, norm))
    if lo == hi: return np.zeros(2), f'row signals {lo}/{hi}: centred'
    s = pitch if lo > hi else -pitch
    loc = (s, 0.0) if ax == 0 else (0.0, s)
    w = np.array(rotv(loc[0], loc[1], P[chip][2]))
    return w, f'row signals {lo}/{hi}: shifted {s:+.2f} along the row'


def _edge_gap(a, ax_, ay_, b, bx_, by_):
    dx = max(abs(ax_ - bx_) - (a['sx'] + b['sx']) / 2, 0); dy = max(abs(ay_ - by_) - (a['sy'] + b['sy']) / 2, 0)
    return math.hypot(dx, dy)


def walled_pins(db, r, plane, cnets, norm):
    """signal pins of IC r within WALL_MM (pad edge) of a pad of r on a power net (big pad or power-kind pin), in local frame"""
    ps = [p for p in db.fp[r]['pads'] if p['n'] and p['net']]
    pw = [p for p in ps if cnets.get(norm(p['net']), {}).get('kind') == 'power' and p['net'] not in plane]
    out = []
    for p in ps:
        if not is_signal(p['net'], plane, cnets, norm) or _area(p) > 0.2: continue
        g = min((_edge_gap(p, p['lx'], p['ly'], q, q['lx'], q['ly']) for q in pw), default=9)
        if g < WALL_MM: out.append((p, g))
    return out


def pullup_targets(db, P, part, chip, pin, plane, cnets, norm):
    """targets + allowed rotations for a 2-pad part straight out in front of a walled pin"""
    pads = [p for p in db.fp[part]['pads'] if p['n']]
    if len(pads) != 2: return None
    sig = [p for p in pads if p['net'] == pin['net']]
    if not sig: return None
    sig = sig[0]; oth = [p for p in pads if p is not sig][0]
    pw = pad_world(db, P, chip, pin['n'])
    # outward normal of the pin's row (local frame: a row along x has its normal along y, away from the body centre)
    rr = _row(db, chip, pin['n'])
    if not rr: return None
    ax, pitch, row, me = rr
    nl = (0.0, math.copysign(1.0, me['ly'])) if ax == 0 else (math.copysign(1.0, me['lx']), 0.0)
    n = np.array(rotv(nl[0], nl[1], P[chip][2]))
    sep = math.hypot(sig['lx'] - oth['lx'], sig['ly'] - oth['ly'])
    q1 = pw + n * PULL_MM; q2 = q1 + n * sep
    # rotations with the part's axis along n
    ax_local = (oth['lx'] - sig['lx'], oth['ly'] - sig['ly'])
    rots = []
    for rot in (0, 90, 180, 270):
        v = np.array(rotv(ax_local[0], ax_local[1], rot)); v = v / (np.linalg.norm(v) + 1e-9)
        if float(v @ n) > 0.9: rots.append(rot)
    return [(sig['n'], np.array([q1]), 1.0), (oth['n'], np.array([q2]), 1.0)], tuple(rots or (0, 90, 180, 270)), \
        f'pull-up in front of walled pin {chip}.{pin["n"]} ({pin["net"].split("/")[-1]})'


def cap_rots(db, P, cap, chip, pin_n):
    """rotations that put a decoupling cap's pad axis along the outward normal of the served pin's row (so its pad
    faces the pin head-on and its width, not its length, covers the row)"""
    rr = _row(db, chip, pin_n)
    if not rr: return (0, 90, 180, 270)
    ax, pitch, row, me = rr
    nl = (0.0, 1.0) if ax == 0 else (1.0, 0.0)
    n = np.array(rotv(nl[0], nl[1], P[chip][2]))
    ps = [p for p in db.fp[cap]['pads'] if p['n']]
    v0 = (ps[1]['lx'] - ps[0]['lx'], ps[1]['ly'] - ps[0]['ly'])
    out = []
    for rot in (0, 90, 180, 270):
        v = np.array(rotv(v0[0], v0[1], rot)); v = v / (np.linalg.norm(v) + 1e-9)
        if abs(float(v @ n)) > 0.9: out.append(rot)
    return tuple(out) or (0, 90, 180, 270)


def biggest_pad_on(db, chip, net):
    ps = [p for p in db.fp[chip]['pads'] if p['n'] and p['net'] == net]
    return max(ps, key=_area) if ps else None


def exit_corridor(db, P, rs, chip, cnets, norm, length=3.0, width=1.5):
    """box on the sense resistor's far (consumer-side) pad, extended `length` mm along the resistor axis away from the
    chip side: the power path toward the consumer starts there (support parts of other nets stay out)"""
    big = {p['net'] for p in big_power_pads(db, chip, cnets, norm)}
    ps = [p for p in db.fp[rs]['pads'] if p['n']]
    a = [p for p in ps if p['net'] in big][0]; b = [p for p in ps if p is not a][0]
    pa = pad_world(db, P, rs, a['n']); pb = pad_world(db, P, rs, b['n'])
    u = (pb - pa) / (np.linalg.norm(pb - pa) + 1e-9); e = pb + u * length; h = width / 2
    return b['net'], (min(pb[0], e[0]) - h, min(pb[1], e[1]) - h, max(pb[0], e[0]) + h, max(pb[1], e[1]) + h)


def exit_band(db, P, rs, chip, cnets, norm, width=1.5, maxlen=9.0):
    """straight band of boxes from the sense resistor's consumer-side pad to the nearest placed pad of the same net
    (the stage's first bulk cap): the power path toward the consumer, kept free of other nets' support parts"""
    big = {p['net'] for p in big_power_pads(db, chip, cnets, norm)}
    ps = [p for p in db.fp[rs]['pads'] if p['n']]
    a = [p for p in ps if p['net'] in big][0]; b = [p for p in ps if p is not a][0]
    pb = pad_world(db, P, rs, b['n']); best = None
    for q in P:
        if q == rs: continue
        for p in db.fp[q]['pads']:
            if p['net'] == b['net']:
                w = pad_world(db, P, q, p['n']); d = float(np.hypot(*(w - pb)))
                if best is None or d < best[0]: best = (d, q, w)
    if best is None or best[0] > maxlen: return b['net'], [], None
    h = width / 2; n = max(1, int(best[0] / 0.4)); out = []
    for t in np.linspace(0, 1, n + 1):
        c = pb + (best[2] - pb) * t; out.append((c[0] - h, c[1] - h, c[0] + h, c[1] + h))
    return b['net'], out, best[1]


def bigpad_rots(db, P, cap, chip, padn):
    """rotations that put a cap's pad axis along the outward normal of a big chip pad (served pad faces the chip pad,
    the other pad points away from the chip, so neither covers the neighbouring pin rows)"""
    pw = pad_world(db, P, chip, padn); n = np.array(_axis(pw - np.array(P[chip][:2])))
    ps = [p for p in db.fp[cap]['pads'] if p['n']]
    v0 = (ps[1]['lx'] - ps[0]['lx'], ps[1]['ly'] - ps[0]['ly'])
    out = []
    for rot in (0, 90, 180, 270):
        v = np.array(rotv(v0[0], v0[1], rot)); v = v / (np.linalg.norm(v) + 1e-9)
        if abs(float(v @ n)) > 0.9: out.append(rot)
    return tuple(out) or (0, 90, 180, 270)
