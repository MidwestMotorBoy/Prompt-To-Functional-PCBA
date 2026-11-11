"""python analyze_cmp.py  -> one 'RESULT {json}' line per finished run in results/<board>/<case>_cmp.npz, plus summary.json"""
import os, sys, json, glob
import numpy as np
import run_cmp as R
HERE = os.path.dirname(os.path.abspath(__file__)); out = {}
for board in R.BOARDS:
    R.setup(board)
    names = [n for n in R.C.boxes() if n.startswith(('fet', 'ind', 'ic', 'rbat', 'rac', 'pphv', 'buck5', 'prot', 'fuse', 'shunt', 'conn'))]
    for f in sorted(glob.glob(os.path.join(HERE, 'results', board, '*_cmp.npz'))):
        case = os.path.basename(f)[:-8]; z = np.load(f); t = z['rec_t']; p = z['rec_p_out']; dt = t[1] - t[0]
        full = t[p >= 0.99 * p.max()] if p.max() > 0 else []
        k = t <= 40; parts = z['rec_parts']; loss = z['rec_loss']
        sel = np.unique(np.concatenate([np.flatnonzero(np.isclose((t / 0.5) % 1, 0, atol=1e-6) & (t <= 20)),
                                        np.flatnonzero(np.isclose((t / 2.0) % 1, 0, atol=1e-6) & (t <= 60)),
                                        np.flatnonzero(np.isclose((t / 10.0) % 1, 0, atol=1e-6))]))
        r = dict(board=board, case=case, burst_min=float(full.max() + dt) if len(full) else 0.0,
                 Wh40=float(np.trapezoid(p[k], t[k]) / 60), can_max=float(z['rec_cell_max'].max()), part_max=float(z['rec_part_max'].max()),
                 board_max=float(z['rec_board_max'].max()), skin_max=float(z['rec_skin_max'].max()), t_end=float(t[-1]),
                 q_board_4min=float(z['rec_q_board'][t <= 4].mean()), q_cells_4min=float(z['rec_q_cells'][t <= 4].mean()),
                 i_bat_4min=float(np.abs(z['rec_i_bat'][t <= 4]).mean()),
                 part_peak={n: round(float(parts[:, i].max()), 1) for i, n in enumerate(names) if parts[:, i].max() > 30},
                 loss_4min={n: round(float(loss[t <= 4][:, i].mean()), 3) for i, n in enumerate(names) if loss[:, i].max() > 0.002},
                 s_t=[round(float(v), 2) for v in t[sel]], s_p=[round(float(v), 1) for v in (p if p.max() > 0 else z['rec_p_in'])[sel]],
                 s_part=[round(float(v), 1) for v in z['rec_part_max'][sel]], s_can=[round(float(v), 1) for v in z['rec_cell_max'].max(1)[sel]],
                 s_soc=[round(float(v), 3) for v in z['rec_soc'][sel]])
        out[f'{board}/{case}'] = r
        print('RESULT ' + json.dumps(r, separators=(',', ':')), flush=True)
json.dump(out, open(os.path.join(HERE, 'results', 'summary.json'), 'w'), indent=1)
