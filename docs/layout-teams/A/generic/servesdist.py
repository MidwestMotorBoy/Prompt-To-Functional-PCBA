#!/usr/bin/env python3
"""servesdist.py <base.json> <placement_gu.json> <constraints.json> : distance from each 'serves' cap pad to its pin (mm)"""
import sys, json, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glib
db = glib.DB(sys.argv[1]); P = {r: tuple(v) for r, v in json.load(open(sys.argv[2])).items()}; C = json.load(open(sys.argv[3]))
D = {}
for c, spec in C['serves'].items():
    q, name = spec.split('.', 1)
    ns = C['pin_pads'].get(spec) or [p['n'] for p in db.fp[q]['pads'] if p['pinfn'] == name] or [name]
    net = [p['net'] for p in db.fp[q]['pads'] if p['n'] == ns[0]][0]
    A = np.array([db.pad(P, c, p['n']) for p in db.fp[c]['pads'] if p['net'] == net]); B = np.array([db.pad(P, q, n) for n in ns])
    if len(A): D[c] = round(float(np.min(np.hypot(A[:, None, 0] - B[None, :, 0], A[:, None, 1] - B[None, :, 1]))), 2)
v = np.array(list(D.values()))
print(f'serves caps {len(D)}: max {v.max():.2f} mean {v.mean():.2f} median {np.median(v):.2f} over 3 mm {int((v>3).sum())} over 5 mm {int((v>5).sum())}')
if len(sys.argv) > 4: print(sorted(D.items(), key=lambda x: -x[1])[:25])
