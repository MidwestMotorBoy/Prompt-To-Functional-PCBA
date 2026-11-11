"""Mechanical fit of the new placement against the unchanged cup model.
The repo's board mesh (hardware/mechanical/board/monolith_board.npz, one mesh per footprint from the KiCad STEP of the
current board) is re-posed: every footprint's mesh is moved rigidly from its old position/rotation to the new one, then
monolith_cup.board_checks() runs on it.   mechcheck.py <repo> <base.json> <placement.json> [--baseline]"""
import sys, os, json, math, numpy as np
repo, basej, placej = sys.argv[1:4]
sys.path.insert(0, os.path.join(repo, 'hardware', 'mechanical'))
import monolith_shell as S, monolith_parts as P
d = np.load(P.BOARD_NPZ)
base = {f['ref']: (f['x'], f['y'], f['rot']) for f in json.load(open(basej))['fps']}
new = {k: tuple(v) for k, v in json.load(open(placej)).items()}
out, moved, dev = {}, 0, []
for k in d.files:
    if k.startswith('_') or k == 'PCB' or k not in new or '--baseline' in sys.argv:
        out[k] = d[k]; continue
    V = d[k].astype(float)
    kx, ky = V[..., 1] + 100.0, S.sb_z_mid + 100.0 - V[..., 2]
    (x0, y0, r0), (x1, y1, r1) = base[k], new[k]
    if abs(x0 - x1) < 1e-6 and abs(y0 - y1) < 1e-6 and abs((r0 - r1) % 360) < 1e-6:
        out[k] = d[k]; continue
    a = math.radians(r1 - r0); c, s = math.cos(a), math.sin(a)
    dx, dy = kx - x0, ky - y0
    nx, ny = x1 + dx * c + dy * s, y1 - dx * s + dy * c
    out[k] = np.stack([V[..., 0], nx - 100.0, S.sb_z_mid + 100.0 - ny], -1)
    moved += 1
    if k[0] in 'RC' and len(V):
        dev.append((abs(nx.mean() - x1) + abs(ny.mean() - y1), k))
tmp = os.path.join(os.path.dirname(os.path.abspath(placej)), 'board_reposed.npz')
np.savez(tmp, **out)
print('footprint meshes moved:', moved, ' worst R/C centroid offset from its new position: %.3f mm (%s)' % max(dev) if dev else '')
P.BOARD_NPZ = tmp
import monolith_cup as C
res = C.board_checks()
bad = 0
for k, v in res.items():
    print('%s %8.3f  %s' % ('ok  ' if v >= 0 else 'FAIL', v, k)); bad += v < 0
print('failed checks:', bad)
