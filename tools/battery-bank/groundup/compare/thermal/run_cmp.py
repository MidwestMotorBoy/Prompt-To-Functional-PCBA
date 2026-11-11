"""Thermal comparison: current board (master) vs ground-up board.  Same p0f loss model, d44 policy, TH101/TH104 at out29.
Per board: heat-source positions read from the .kicad_pcb, routed-copper loss tiles (cu_<board>.json, DC grid solver),
board in-plane conductivity and filler-zone through conductivity scaled by the measured copper cover and via count.
python run_cmp.py <board,..> <case,..> [hours]  -> results/<board>/<case>_cmp.npz"""
import os, sys, time, json
os.environ.setdefault('OMP_NUM_THREADS', '1'); os.environ['SMD_LAYOUT'] = 'p0f'
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ['CU_JSON'] = os.path.join(HERE, 'cu_base.json')
import numpy as np
import cu as C
P, S, N = C.P, C.S, C.N
BOARDS = {
 'base': dict(k_in=38.0, k_vias=8.0, ts={1: (11.82, 44.16), 2: (-11.20, 44.16)},
    st={1: dict(fetA=(9.56, 41.66), fetB=(14.08, 41.62), ind=(11.81, 48.86), ic=(11.44, 31.03, 3.0, 2.5), rbat=(18.17, 36.48, 0.8, 1.6),
                rac=(11.28, 60.83, 1.0, 0.65), pphv=(5.09, 61.53, 3.0, 2.0), buck5=(2.90, 30.37)),
        2: dict(fetA=(-13.46, 41.66), fetB=(-8.95, 41.62), ind=(-11.21, 48.86), ic=(-11.59, 30.96, 3.0, 2.5), rbat=(-1.96, 41.33, 0.8, 1.6),
                rac=(-8.41, 60.75, 1.0, 0.65), pphv=(-14.69, 61.50, 3.0, 2.0), buck5=(-12.60, 23.19))},
    prot=[(4.74, 22.64, 3.0, 2.6), (-2.72, 22.64, 3.0, 2.6)], fuse=(13.79, 9.64), shunt=(-11.52, 8.48)),
 'new': dict(k_in=38.0 * 1.20, k_vias=0.45 + 7.55 * 0.58, ts={1: (9.55, 38.69), 2: (-13.48, 38.69)},
    st={1: dict(fetA=(9.55, 41.67), fetB=(14.05, 41.67), ind=(11.81, 48.86), ic=(10.84, 30.23, 3.0, 2.5), rbat=(18.45, 37.37, 0.8, 1.6),
                rac=(5.60, 55.17, 0.65, 1.0), pphv=(6.10, 60.47, 2.0, 3.0), buck5=(15.00, 57.47)),
        2: dict(fetA=(-13.48, 41.67), fetB=(-8.98, 41.67), ind=(-11.21, 48.86), ic=(-12.19, 30.23, 3.0, 2.5), rbat=(-4.58, 37.37, 0.8, 1.6),
                rac=(-15.90, 55.17, 0.65, 1.0), pphv=(-15.40, 60.47, 2.0, 3.0), buck5=(-6.10, 54.87))},
    prot=[(3.40, 15.47, 2.6, 3.0), (3.40, 22.97, 2.6, 3.0)], fuse=(13.79, 9.64), shunt=(-11.40, 8.47)),
}
BOARDS['new_k38'] = dict(BOARDS['new'], k_in=38.0, cu='new')          # bracket: no credit for the extra copper cover
# ground-up board after the fix pass: same part positions (four 0402 capacitors moved), its own loss tiles, 134 + 125 vias
# in the filler zones against 141 + 139 (0.925), stage copper cover 41.6 against 32.65 W/mK by area (1.27)
BOARDS['fix'] = dict(BOARDS['new'], k_in=38.0 * 1.27, k_vias=0.45 + 7.55 * 0.925, cu='fix')
BOARDS['fix_k38'] = dict(BOARDS['fix'], k_in=38.0)
CFG = [None]
def src_boxes():
    cfg = CFG[0]; b = S._orig_src_boxes()
    def bx(y, z, hy, hz, x1=27.8): return (26.9, x1, y - hy, y + hy, z - hz, z + hz)
    for p, s in cfg['st'].items():
        b.pop(f'fet{p}'); b.pop(f'sense{p}')
        b[f'fetA{p}'] = [bx(*s['fetA'], 1.65, 1.65)]; b[f'fetB{p}'] = [bx(*s['fetB'], 1.65, 1.65)]
        b[f'ind{p}'] = [bx(*s['ind'], 3.5, 3.5, 30.0)]; b[f'ic{p}'] = [bx(*s['ic'], 27.7)]
        b[f'rbat{p}'] = [bx(*s['rbat'], 27.5)]; b[f'rac{p}'] = [bx(*s['rac'], 27.5)]
        b[f'pphv{p}'] = [bx(*s['pphv'])]; b[f'buck5{p}'] = [bx(*s['buck5'], 1.0, 0.8, 27.6)]
    b['prot'] = [bx(*q, 27.9) for q in cfg['prot']]
    b['fuse'] = [bx(*cfg['fuse'], 2.0, 1.5, 27.9)]; b['shunt'] = [bx(*cfg['shunt'], 1.6, 0.8, 27.5)]
    return b
C._ob = src_boxes

def setup(board):
    cfg = BOARDS[board]; CFG[0] = cfg
    C.CU = json.load(open(os.path.join(HERE, f"cu_{cfg.get('cu', board)}.json")))
    C.RB = 0.5 * (C.CU['cub1']['R'] + C.CU['cub2']['R']); C.RU = 0.5 * (C.CU['cuu1']['R'] + C.CU['cuu2']['R'])
    P.K_BOARD_IN = cfg['k_in']; P.K_VIAS_THRU = cfg['k_vias']; P.GRID_TAG = ''
    P.TS_PT = {p: (26.6, y, z) for p, (y, z) in cfg['ts'].items()}
    P.OUT_DIR = os.path.join(HERE, 'results', board)

def job(spec):
    board, case, hours = spec
    setup(board); C.ON[0] = True
    P.DERATE, P.DERATE_HOT, P.CHG_HOT = S.POLICIES['d44']
    g = P.get_grid(); S.use_spot('out29')
    P.run_case(g, case, verbose=False, tag='_cmp', amb=25.0, hours=hours, probes=S.spot_points(), ntc_front=N.SPOT)
    return spec

if __name__ == '__main__':
    boards = sys.argv[1].split(','); cases = sys.argv[2].split(',')
    hours = float(sys.argv[3]) if len(sys.argv) > 3 else None
    for b in boards:
        setup(b); t0 = time.time(); P.get_grid(); print(f'grid {b} ready {time.time()-t0:.0f} s', flush=True)
    specs = [(b, c, hours) for b in boards for c in cases]
    import multiprocessing as mp
    with mp.get_context('spawn').Pool(int(os.environ.get('NPROC', '2')), maxtasksperchild=1) as pl:
        for r in pl.imap_unordered(job, specs): print(r, 'done', time.strftime('%H:%M:%S'), flush=True)
