"""Where to put the front-cell NTCs, and the derate retuned for the chosen spot (2026-10-24).
1. probes: record the can temperature at a grid of spots on the front cells (angle round from the board-facing line,
   height z) in the main cases, and compare each with the hottest point of that cell's can.
2. policy: rerun the cases with the front NTCs at the chosen spot and a set of derate / charge thresholds.
Run: python ntc.py probes | policy [pol=p40,p42] | extra | table     -> results/ntc_*.npz, renders/ntc.json"""
import os, sys, json, time, itertools
import multiprocessing as mp
os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pack3d as P

ANGLES = (-30, -15, 0, 7, 15, 25, 35, 50)                 # degrees from the board-facing line, + toward the board edge
ZS = (40.0, 50.0, 54.5, 56.0, 57.5, 59.0, 61.0, 64.0, 68.0, 72.0)
PROBES = [(k, a, z) for k in P.FRONT for a in ANGLES for z in ZS]
PROBE_CASES = {'dis100': 1.0, 'dis60': 1.5, 'chg1': None, 'pass': None}   # case: hours (None = the case's own)

SPOT = (7, 48.0)          # chosen front-NTC spot: 7 degrees out from the board-facing line (|y| = 12.9 mm), z = 48 mm,
                          # on the hot stripe inside the gap-filler zone (z 27-53); above the filler (z 56) it reads 5-6 K low
POLICIES = {              # name: (DERATE, DERATE_HOT, CHG_HOT), all on the hottest NTC reading
    'old':   ((33.0, 39.0, 40.0), (45.0, 55.0), (40.0, 45.0)),
    'p40':   ((40.0, 44.0, 40.0), (50.0, 58.0), (40.0, 44.5)),
    'p42':   ((42.0, 46.0, 40.0), (50.0, 58.0), (40.0, 44.5)),
    'p44':   ((44.0, 48.0, 40.0), (50.0, 58.0), (40.0, 44.5)),
    'p46':   ((46.0, 50.0, 40.0), (52.0, 58.0), (40.0, 44.5)),
    'p42c':  ((42.0, 46.0, 40.0), (50.0, 58.0), (42.0, 44.5)),   # p42 with the charge ramp starting at 42 °C
}
EXTRA = [('chg1', 'p42c', 'board', 25.0), ('pass', 'p42c', 'board', 25.0),     # (case, policy, NTC, ambient)
         ('dis100', 'p42', 'board', 35.0), ('dis100', 'old', 'centre', 35.0)]
POLICY_CASES = ('dis100', 'chg1', 'pass')

def probe_job(case):
    g = P.get_grid()
    pts = [P.can_point(k, a, z) for k, a, z in PROBES]
    P.run_case(g, case, verbose=False, tag='_ntcprobe', probes=pts, hours=PROBE_CASES[case])
    return case

def tag(pol, ntc, amb=25.0): return f'_ntc_{pol}_{ntc}' + ('' if amb == 25.0 else f'_amb{amb:.0f}')

def policy_job(spec):
    case, pol, ntc, amb = (spec + (25.0,))[:4]
    P.DERATE, P.DERATE_HOT, P.CHG_HOT = POLICIES[pol]
    g = P.get_grid()
    P.run_case(g, case, verbose=False, tag=tag(pol, ntc, amb), amb=amb, ntc_front=SPOT if ntc == 'board' else None)
    return spec

def load(name): return np.load(os.path.join(P.OUT_DIR, name + '.npz'))

def probe_table():
    out = {}
    for case in PROBE_CASES:
        z = load(case + '_ntcprobe'); pr = z['rec_probe']; sm = z['rec_surf_max']; ntc = z['rec_ntc']; t = z['rec_t']
        hot = int(np.argmax(sm.max(1)))                    # the moment the hottest can point peaks
        rows = []
        for j, (k, a, zz) in enumerate(PROBES):
            under = sm[:, k] - pr[:, j]
            rows.append(dict(cell=P.CELLS[k][0], ang=a, z=zz, max_under=float(under.max()), under_at_peak=float(under[hot]),
                             min_under=float(under.min())))
        cen = [dict(cell=P.CELLS[k][0], max_under=float((sm[:, k] - ntc[:, k]).max()),
                    under_at_peak=float(sm[hot, k] - ntc[hot, k])) for k in P.FRONT]
        out[case] = dict(t_peak=float(t[hot]), surf_peak=float(sm[hot].max()), probes=rows, centre=cen)
    return out

def policy_row(case, pol, ntc, amb=25.0):
    z = load(case + tag(pol, ntc, amb)); t = z['rec_t']; dt = t[1] - t[0]
    p = z['rec_p_out']; pin = z['rec_p_in']; m40 = t <= 40
    full = np.nonzero(p < 99)[0]
    r = dict(case=case, policy=pol, ntc=ntc, amb=amb, t_end=float(t[-1]), surf_max=float(z['rec_surf_max'].max()),
             ntc_max=float(z['rec_ntc'].max()), part_max=float(z['rec_part_max'].max()), skin_max=float(z['rec_skin_max'].max()),
             cell_max=float(z['rec_cell_max'].max()))
    if case.startswith('dis'):
        r.update(min_full=float(t[full[0]]) if len(full) else float(t[-1]), wh_40=float(p[m40].sum()*dt/60),
                 wh_total=float(p.sum()*dt/60))
    if case in ('chg1', 'pass'):
        soc = z['rec_soc']; r.update(soc_end=float(soc[-1]))
        if case == 'chg1':
            hit = np.nonzero(soc >= 0.95 - 1e-6)[0]; r.update(min_to_95=float(t[hit[0]]) if len(hit) else None)
        trim = np.nonzero((z['rec_i_chg'] < 4.5) & (t > 1))[0]; r.update(min_trim=float(t[trim[0]]) if len(trim) else None)
    return r

def pool_run(fn, specs):
    with mp.get_context('spawn').Pool(4, maxtasksperchild=1) as pool:
        for r in pool.imap_unordered(fn, specs): print(r, 'done', time.strftime('%H:%M:%S'), flush=True)

if __name__ == '__main__':
    what = sys.argv[1:] or ['table']
    P.get_grid()
    if 'probes' in what: pool_run(probe_job, list(PROBE_CASES))
    if 'policy' in what:
        pols = [a.split('=')[1].split(',') for a in what if a.startswith('pol=')]
        pols = pols[0] if pols else list(POLICIES)
        specs = [(c, p, 'board') for p in pols for c in POLICY_CASES]
        if 'old' in pols: specs += [(c, 'old', 'centre') for c in POLICY_CASES]
        pool_run(policy_job, specs)
    if 'extra' in what: pool_run(policy_job, EXTRA)
    if 'table' in what:
        res = dict(probes=probe_table() if all(os.path.exists(os.path.join(P.OUT_DIR, c + '_ntcprobe.npz')) for c in PROBE_CASES) else None,
                   policy=[policy_row(c, p, n, a) for c, p, n, a in
                           dict.fromkeys([(c, p, n, 25.0) for p in POLICIES for n in ('board', 'centre') for c in POLICY_CASES] + EXTRA)
                           if os.path.exists(os.path.join(P.OUT_DIR, c + tag(p, n, a) + '.npz'))])
        json.dump(res, open(os.path.join(P.HERE, 'renders', 'ntc.json'), 'w'), indent=1)
        for r in res['policy']: print(json.dumps({k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()}))
