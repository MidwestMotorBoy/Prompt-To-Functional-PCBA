"""Board-mounted SMD NTCs for TS1 / TS4 instead of the wired beads on the can (2026-10-28).
1. probes: run the main cases with today's policy (p42c, wired NTC on the stripe) and record the board's B.Cu temperature
   at candidate SMD spots over each front cell, next to the stripe spot and the hottest can point.
2. seq: 100 W to empty, then straight onto one 100 W charger (the cool-down case a board sensor could get wrong).
3. policy: rerun the cases with the front NTCs on the board at the best spot and shifted thresholds.
Run: python smd.py probes | seq | policy [pol=s46,s50] | table     -> results/smd_*.npz, renders/smd.json"""
import os, sys, json, time
os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pack3d as P
import ntc as N

# SMD_LAYOUT=p0: the port-1 stage where it sits on the Production board today (2026-10-28, KiCad x = 100 + y, y = 141.47 - z):
# Q401 / Q402 SiZ240DT at (10.4, 50.3) / (10.3, 44.0), L401 at (4.3, 47.1), U403 BQ25756 at (17.4, 45.8), R424 (AC sense) at
# (11.2, 60.8). The battery-side sense resistor and port 2 aren't placed yet: RBAT is put beside the FETs, port 2 mirrored onto C1.
LAYOUT = os.environ.get('SMD_LAYOUT', '')
def p0_src_boxes():
    b = _orig_src_boxes()
    for p in (1, 2):
        s = 1 if p == 1 else -1
        def bx(y, z, hy, hz, x1=27.8): y = s*y; return (26.9, x1, y - hy, y + hy, z - hz, z + hz)
        b[f'fet{p}'] = [bx(10.4, 50.26, 1.65, 1.65), bx(10.32, 44.01, 1.65, 1.65)]
        b[f'ind{p}'] = [bx(4.27, 47.12, 3.5, 3.5, 30.0)]
        b[f'ic{p}'] = [bx(17.36, 45.83, 2.5, 3.0, 27.7)]
        b[f'sense{p}'] = [bx(11.23, 60.83, 2.5, 1.3, 27.5), bx(14.3, 54.5, 1.6, 0.8, 27.5)]
    return b
# SMD_LAYOUT=p0b: the same after Logan's 10-27 "Layout in progress" commit (ed56285): Q401 / Q402 at (9.6, 41.7) / (14.1, 41.6),
# L401 at (11.8, 48.9), U403 at (11.4, 31.0) turned 90 deg, RBAT R427 at (18.2, 36.5). R424 (AC sense) is still off the board:
# put beside L401 at (9.0, 54.5). Port 2 is still off the board and stays mirrored onto C1.
def p0b_src_boxes():
    b = _orig_src_boxes()
    for p in (1, 2):
        s = 1 if p == 1 else -1
        def bx(y, z, hy, hz, x1=27.8): y = s*y; return (26.9, x1, y - hy, y + hy, z - hz, z + hz)
        b[f'fet{p}'] = [bx(9.56, 41.66, 1.65, 1.65), bx(14.08, 41.62, 1.65, 1.65)]
        b[f'ind{p}'] = [bx(11.81, 48.86, 3.5, 3.5, 30.0)]
        b[f'ic{p}'] = [bx(11.44, 30.97, 3.0, 2.5, 27.7)]
        b[f'sense{p}'] = [bx(18.17, 36.48, 0.8, 1.6, 27.5), bx(9.0, 54.5, 1.0, 0.65, 27.5)]
    return b
# SMD_LAYOUT=p0f: every heat source where it sits on the board at ca78123 "Footprint Layout Done" (2026-10-29), read from
# Monolith.kicad_pcb (KiCad x = 100 + y, y = 141.47 - z). Port 2 is a translated copy of port 1 (x - 23.03), not a mirror,
# so over C1 the outboard FET is leg A (Q501) and over C4 it is leg B (Q402). The FET loss is split by leg: conduction
# half and half, the switching terms (edges, Coss, dead time) on the leg at the higher voltage (leg A, USB side, when
# V_USB > V_BUS; leg B when V_USB < V_BUS; shared within 5 %). Sources off the gap-filler zone (RBAT R527 / RAC R524 of
# port 2, both RAC, the TPS62933s, Q101 / Q102, F102, RS101) sit where they are, on board without the via array.
#   port 1: Q401 (A) (9.56, 41.66), Q402 (B) (14.08, 41.62), L401 (11.81, 48.86), U403 (11.44, 30.97), R427 RBAT (18.17, 36.48),
#           R424 RAC (11.28, 60.83), U401 TPS25751 (5.09, 61.53), U404 TPS62933 (2.90, 30.37)
#   port 2: Q501 (A) (-13.47, 41.66), Q502 (B) (-8.95, 41.62), L501 (-11.22, 48.86), U503 (-11.59, 30.96), R527 RBAT (-1.96, 41.33),
#           R524 RAC (-2.21, 48.66), U501 TPS25751 (-14.69, 61.50), U504 TPS62933 (-12.60, 23.19)
#   pack:   Q101 (4.74, 22.64), Q102 (-2.72, 22.64), F102 (13.79, 9.64), RS101 (-11.52, 8.48)
FETSPLIT = os.environ.get('SMD_FETSPLIT', '')
BUCK5_W = 0.10                             # TPS62933 (PP5V / VCONN) loss while its port sources: assumed
def p0f_src_boxes():
    b = _orig_src_boxes()
    def bx(y, z, hy, hz, x1=27.8): return (26.9, x1, y - hy, y + hy, z - hz, z + hz)
    st = {1: dict(fetA=(9.56, 41.66), fetB=(14.08, 41.62), ind=(11.81, 48.86), ic=(11.44, 30.97), rbat=(18.17, 36.48, 0.8, 1.6),
                  rac=(11.28, 60.83, 1.0, 0.65), pphv=(5.09, 61.53), buck5=(2.90, 30.37)),
          2: dict(fetA=(-13.47, 41.66), fetB=(-8.95, 41.62), ind=(-11.22, 48.86), ic=(-11.59, 30.96), rbat=(-1.96, 41.33, 0.8, 1.6),
                  rac=(-8.41, 60.75, 1.0, 0.65), pphv=(-14.69, 61.50), buck5=(-12.60, 23.19))}
    for p, s in st.items():
        b.pop(f'fet{p}'); b.pop(f'sense{p}')
        b[f'fetA{p}'] = [bx(*s['fetA'], 1.65, 1.65)]
        b[f'fetB{p}'] = [bx(*s['fetB'], 1.65, 1.65)]
        b[f'ind{p}'] = [bx(*s['ind'], 3.5, 3.5, 30.0)]
        b[f'ic{p}'] = [bx(*s['ic'], 3.0, 2.5, 27.7)]
        b[f'rbat{p}'] = [bx(*s['rbat'], 27.5)]
        b[f'rac{p}'] = [bx(*s['rac'], 27.5)]
        b[f'pphv{p}'] = [bx(*s['pphv'], 3.0, 2.0)]
        b[f'buck5{p}'] = [bx(*s['buck5'], 1.0, 0.8, 27.6)]
    b['prot'] = [bx(4.74, 22.64, 3.0, 2.6, 27.9), bx(-2.72, 22.64, 3.0, 2.6, 27.9)]
    b['fuse'] = [bx(13.79, 9.64, 2.0, 1.5, 27.9)]
    b['shunt'] = [bx(-11.52, 8.48, 1.6, 0.8, 27.5)]
    return b
_orig_port_loss = P.port_loss
def p0f_port_loss(p_usb, v_usb, v_bus, sink, prm=P.P0):
    """as pack3d.port_loss, with the FET loss split into leg A (USB side) and leg B (battery side), the sense loss into
    RBAT and RAC, and the TPS62933 on a sourcing port"""
    L, i_b = _orig_port_loss(p_usb, v_usb, v_bus, sink, prm)
    L = dict(L); fet = L.pop('fet'); sense = L.pop('sense')
    if p_usb <= 0:
        L.update(fetA=0, fetB=0, rbat=0, rac=0, buck5=0); return L, i_b
    v_hi = max(v_usb, v_bus)
    il2 = max(0.0, (L['ind'] - prm['core']*min(1.0, v_hi/20.0)) / prm['ind'])
    cond = prm['fet']*il2*2; sw = fet - cond
    r = v_usb / v_bus
    fa = 1.0 if r > 1.05 else 0.0 if r < 1/1.05 else 0.5           # share of the switching loss on leg A
    rac = prm['rac']*(p_usb / v_usb)**2
    if FETSPLIT == 'even': fa = 0.5                                  # SMD_FETSPLIT=even: as p0b, both legs alike
    L.update(fetA=cond/2 + fa*sw, fetB=cond/2 + (1 - fa)*sw, rbat=sense - rac, rac=rac,
             buck5=0.0 if sink else BUCK5_W)
    return L, i_b
P.CASES.update({   # port 2 and swapped-port versions of the smd-ntc.md cases
    'dis100u2': dict(title='100 W asked, USB2 only (20 V 5 A)', ports={2: ('src', 100, 20.0)}, soc0=1.0, hours=2.5, dt=10),
    'chg1u2':   dict(title='Charging, USB2 only (100 W charger)', ports={2: ('snk', 100, 20.0)}, soc0=0.05, hours=3.0, dt=20),
    'pass21':   dict(title='Pass-through: 100 W charger on USB2, 30 W out of USB1', ports={2: ('snk', 100, 20.0), 1: ('src', 30, 15.0)},
                     soc0=0.20, hours=2.0, dt=20),
})
_orig_src_boxes = P.src_boxes
if LAYOUT in ('p0', 'p0b'):
    P.src_boxes = p0_src_boxes if LAYOUT == 'p0' else p0b_src_boxes
    P.OUT_DIR = os.path.join(P.HERE, 'results', 'p0layout' if LAYOUT == 'p0' else 'p0b')
if LAYOUT == 'p0f':
    P.src_boxes, P.port_loss = p0f_src_boxes, p0f_port_loss
    P.OUT_DIR = os.path.join(P.HERE, 'results', 'p0f' + ('_' + FETSPLIT if FETSPLIT else ''))

X_BCU, X_FCU = 25.8, 26.4                 # board voxels: the B.Cu half (board is x 25.3-26.9) and the F.Cu half
SPOTS = {                                  # name: (x, |y|, z) on the board, mirrored onto C1 (-y) and C4 (+y)
    'stripe':  (X_BCU, 12.9, 48.0),        # B.Cu straight over the wired bead's spot (under the stage FETs)
    'tangent': (X_BCU, 11.6, 44.0),        # B.Cu on the board-facing line, closest to the can
    'zone_lo': (X_BCU, 13.5, 30.0),        # B.Cu at the bottom of the filler zone, under the BQ25756
    'edge':    (X_BCU, 15.5, 40.0),        # B.Cu at the outer edge of the filler zone
    'below':   (X_BCU, 13.5, 24.0),        # B.Cu just below the filler zone (air gap to the can)
    'above':   (X_BCU, 12.9, 57.0),        # B.Cu just above the filler zone
    'pads':    (X_BCU, 14.7, 66.0),        # B.Cu where J102 / J107 are today
    'low28':   (X_BCU, 12.9, 28.5),        # B.Cu at the bottom end of the filler zone, on the stripe line
    'low33':   (X_BCU, 12.9, 33.0),
    'low38':   (X_BCU, 12.9, 38.0),
    'out29':   (X_BCU, 15.5, 29.0),        # filler zone bottom, outboard of U403 in the p0b layout
    'in29':    (X_BCU, 7.5, 29.0),         # filler zone bottom, inboard of U403
    'z26':     (X_BCU, 12.9, 26.0),        # just below the filler zone
    'z20':     (X_BCU, 13.5, 20.0),
    'out27':   (X_BCU, 15.5, 27.5),        # p0f alternatives round TH101 / TH104 (15.5, 29)
    'out33':   (X_BCU, 15.5, 33.0),
    'mid29':   (X_BCU, 11.5, 29.0),
    'stripe_f': (X_FCU, 12.9, 48.0),       # F.Cu side of the stripe spot
}
def spot_points():
    pts = []
    for k in P.FRONT:
        s = np.sign(P.CELLS[k][2])
        pts += [(x, s*y, z) for x, y, z in SPOTS.values()]
        pts.append(P.can_point(k, *N.SPOT))                       # the wired bead's spot (today's design)
    return pts
NAMES = list(SPOTS) + ['wired']
CASES = {'dis100': None, 'dis60': None, 'dis30': None, 'chg1': None, 'pass': None, 'dis100x2': None,
         'dis100u2': None, 'chg1u2': None, 'pass21': None}

POLICIES = {    # name: (DERATE, DERATE_HOT, CHG_HOT) on the hottest TS reading, as ntc.POLICIES
    'p42c': N.POLICIES['p42c'],
    's46':  ((46.0, 50.0, 40.0), (54.0, 62.0), (46.0, 48.5)),   # +4 K
    's48':  ((48.0, 52.0, 40.0), (56.0, 62.0), (48.0, 50.5)),   # +6 K
    's50':  ((50.0, 54.0, 40.0), (58.0, 62.0), (50.0, 52.5)),   # +8 K
    's43':  ((43.0, 47.0, 40.0), (51.0, 59.0), (43.0, 45.5)),   # +1 K
    'd44':  ((44.0, 48.0, 40.0), (52.0, 59.0), (42.0, 44.5)),   # discharge ramp +2 K, charge ramp as p42c
}

def probe_job(case):
    P.DERATE, P.DERATE_HOT, P.CHG_HOT = N.POLICIES['p42c']
    g = P.get_grid()
    P.run_case(g, case, verbose=False, tag='_smdprobe', probes=spot_points(), ntc_front=N.SPOT)
    return case

def seq_job(spec):
    """100 W to empty, then one 100 W charger at once, with policy `pol` and the front NTCs `ntc` ('wired' or a spot)"""
    pol, ntc = spec
    P.DERATE, P.DERATE_HOT, P.CHG_HOT = POLICIES[pol]
    g = P.get_grid(); use_spot(ntc)
    a = f'_smdseq_{pol}_{ntc}'
    P.run_case(g, 'dis100', verbose=False, tag=a + '_a', probes=spot_points(), ntc_front=N.SPOT)
    z = np.load(os.path.join(P.OUT_DIR, 'dis100' + a + '_a.npz'))
    P.run_case(g, 'chg1', verbose=False, tag=a + '_b', probes=spot_points(), ntc_front=N.SPOT, hours=3.0,
               th0=z['snap_end'][...], soc0=float(z['rec_soc'][-1]))
    return spec

_orig_ntc_points = P.ntc_points
def use_spot(ntc):
    """front NTCs on the board at SPOTS[ntc] (or the wired spot for 'wired')"""
    if ntc == 'wired': P.ntc_points = _orig_ntc_points; return
    def pts(g, ntc_front=None):
        p, alt = _orig_ntc_points(g, ntc_front)
        for k in P.FRONT:
            x, y, z = SPOTS[ntc]; p[k] = P.vox(g, (x, np.sign(P.CELLS[k][2])*y, z))
        return p, alt
    P.ntc_points = pts

def policy_job(spec):
    case, pol, ntc, amb = spec
    P.DERATE, P.DERATE_HOT, P.CHG_HOT = POLICIES[pol]
    g = P.get_grid(); use_spot(ntc)
    P.run_case(g, case, verbose=False, tag=f'_smd_{pol}_{ntc}' + ('' if amb == 25 else f'_amb{amb:.0f}'), amb=amb,
               probes=spot_points(), ntc_front=N.SPOT)
    return spec

def lambda_free_job(spec):
    kind, a = spec
    return (policy_job if kind == 'policy' else seq_job)(a)

def load(name): return np.load(os.path.join(P.OUT_DIR, name + '.npz'))

def bias(z):
    """per spot: reading minus the hottest can point of the same front cell, (max, min, at the can peak), worst cell"""
    pr, sm, t = z['rec_probe'], z['rec_surf_max'], z['rec_t']
    hot = int(np.argmax(sm.max(1))); out = {}
    for j, n in enumerate(NAMES):
        d = np.stack([pr[:, i*len(NAMES) + j] - sm[:, k] for i, k in enumerate(P.FRONT)], 1)   # (t, 2)
        late = t > 3                                                    # skip the first minutes from a cold start
        out[n] = dict(max=float(d[late].max()), min=float(d[late].min()), at_peak=float(d[hot].max()),
                      c4_at_peak=float(d[hot, 1]), c1_at_peak=float(d[hot, 0]),
                      c1_max=float(d[late, 0].max()), c1_min=float(d[late, 0].min()),
                      c4_max=float(d[late, 1].max()), c4_min=float(d[late, 1].min()))
    return out

def run_row(z, case):
    t = z['rec_t']; dt = t[1] - t[0]; p = z['rec_p_out']; m40 = t <= 40; full = np.nonzero(p < 99)[0]
    r = dict(t_end=float(t[-1]), surf_max=float(z['rec_surf_max'].max()), ntc_max=float(z['rec_ntc'].max()),
             part_max=float(z['rec_part_max'].max()), skin_max=float(z['rec_skin_max'].max()))
    if case.startswith('dis'):
        r.update(min_full=float(t[full[0]]) if len(full) else float(t[-1]), wh_40=float(p[m40].sum()*dt/60), wh_total=float(p.sum()*dt/60))
    else:
        soc = z['rec_soc']; r.update(soc_end=float(soc[-1]))
        hit = np.nonzero(soc >= 0.95 - 1e-6)[0]; r.update(min_to_95=float(t[hit[0]]) if len(hit) else None)
        chg = z['rec_i_chg'] > 0.1                                       # hottest can while current flows
        r.update(surf_max_charging=float(z['rec_surf_max'][chg].max()) if chg.any() else None)
    return r

if __name__ == '__main__':
    what = sys.argv[1:] or ['table']
    P.get_grid()
    if 'probes' in what: N.pool_run(probe_job, list(CASES))
    if 'seq' in what:
        sq = [a.split('=')[1].split(':') for a in what if a.startswith('seq=')]
        N.pool_run(seq_job, [tuple(sq[0])] if sq else [('p42c', 'wired'), ('s48', 'stripe')])
    if 'policy' in what:
        pols = [a.split('=')[1].split(',') for a in what if a.startswith('pol=')]
        pols = pols[0] if pols else ['s46', 's48', 's50']
        spot = [a.split('=')[1] for a in what if a.startswith('spot=')] or ['stripe']
        N.pool_run(policy_job, [(c, p, spot[0], 25.0) for p in pols for c in ('dis100', 'chg1', 'pass')])
    if 'amb' in what:
        N.pool_run(policy_job, [('dis100', 'p42c', 'wired', 35.0), ('dis100', 's48', 'stripe', 35.0),
                                ('chg1', 'p42c', 'wired', 35.0), ('chg1', 's48', 'stripe', 35.0)])
    if 'p0' in what:          # SMD_LAYOUT=p0 python smd.py p0
        N.pool_run(probe_job, ['dis100', 'chg1', 'pass', 'dis30'])
        N.pool_run(policy_job, [(c, p, 'low28', 25.0) for p in ('p42c', 's43') for c in ('dis100', 'chg1', 'pass')])
        N.pool_run(seq_job, [('s43', 'low28')])
    if 'p0c' in what:         # the p0b layout's best spot, today's thresholds
        N.pool_run(lambda_free_job, [('policy', ('dis100', 'p42c', 'out29', 25.0)), ('policy', ('chg1', 'p42c', 'out29', 25.0)),
                                     ('policy', ('pass', 'p42c', 'out29', 25.0)), ('seq', ('p42c', 'out29'))])
    if 'p0d' in what:
        N.pool_run(lambda_free_job, [('policy', ('dis100', 'd44', 'out29', 25.0)), ('seq', ('d44', 'out29')),
                                     ('policy', ('dis60', 'd44', 'out29', 25.0)), ('policy', ('dis60', 'p42c', 'wired', 25.0))])
    if 'probes4' in what: N.pool_run(probe_job, ['dis100', 'chg1', 'pass', 'dis30'])
    if 'probesf' in what:     # SMD_LAYOUT=p0f: both ports' cases
        N.pool_run(probe_job, ['dis100', 'dis100u2', 'chg1', 'chg1u2', 'pass', 'pass21', 'dis30'])
    if 'p0b' in what:         # the recommended spot (z 33) with today's thresholds
        N.pool_run(lambda_free_job, [('policy', ('dis100', 'p42c', 'low33', 25.0)), ('policy', ('chg1', 'p42c', 'low33', 25.0)),
                                     ('policy', ('pass', 'p42c', 'low33', 25.0)), ('seq', ('p42c', 'low33'))])
    if 'table' in what:
        res = dict(probes={}, policy=[], seq={})
        for c in CASES:
            f = c + '_smdprobe'
            if os.path.exists(os.path.join(P.OUT_DIR, f + '.npz')):
                z = load(f); res['probes'][c] = dict(bias=bias(z), **run_row(z, c))
        for fn in sorted(os.listdir(P.OUT_DIR)):
            if fn.endswith('.npz') and '_smd_' in fn:
                name = fn[:-4]; case = name.split('_smd_')[0]; z = load(name)
                res['policy'].append(dict(run=name, case=case, bias=bias(z)['stripe'], wired_bias=bias(z)['wired'], **run_row(z, case)))
            if fn.endswith('_b.npz') and '_smdseq_' in fn:
                name = fn[:-4]; z = load(name); a = load('dis100' + name[4:-2] + '_a')
                t = z['rec_t']; i = z['rec_i_chg']; sm = z['rec_surf_max'].max(1); nt = z['rec_ntc'].max(1)
                on = np.nonzero(i > 0.1)[0]
                res['seq'][name] = dict(dis=run_row(a, 'dis100'), chg=run_row(z, 'chg1'), bias=bias(z),
                                        t_first_current=float(t[on[0]]) if len(on) else None,
                                        can_at_first_current=float(sm[on[0]]) if len(on) else None,
                                        ntc_at_first_current=float(nt[on[0]]) if len(on) else None,
                                        can_max_while_charging=float(sm[i > 0.1].max()) if len(on) else None,
                                        can_max_at_full_current=float(sm[i > 4.4].max()) if (i > 4.4).any() else None)
        os.makedirs(os.path.join(P.HERE, 'renders'), exist_ok=True)
        json.dump(res, open(os.path.join(P.HERE, 'renders', f'smd{"_" + LAYOUT if LAYOUT else ""}{"_" + FETSPLIT if LAYOUT == "p0f" and FETSPLIT else ""}.json'), 'w'), indent=1)
        for c, r in res['probes'].items():
            print(c, {k: round(v, 1) for k, v in r.items() if isinstance(v, float)})
            for n, b in r['bias'].items(): print(f'   {n:9s}', {k: round(v, 1) for k, v in b.items()})
        for r in res['policy']: print(json.dumps({k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items() if k not in ('bias', 'wired_bias')}),
                                      'bias', {k: round(v, 1) for k, v in r['bias'].items()})
        for n, r in res['seq'].items(): print(n, json.dumps({k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items() if k != 'bias'}))
