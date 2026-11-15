"""assemble.py <out.json>  - master.json overlaid by each room's placement; refuses if the whole board has overlaps."""
import json, sys, os, glob
from dlib import Board
from room import ROOMS, MASTER
b = Board(); b.set(json.load(open(MASTER))); owner = {}
for f in sorted(glob.glob(os.path.join(ROOMS, '*.json'))):
    if f.endswith('.spec.json') or f.endswith('master.json'): continue
    P = json.load(open(f)); b.set(P)
    for r in P:
        if r in owner: print(f'WARNING {r} placed by both {owner[r]} and {os.path.basename(f)}')
        owner[r] = os.path.basename(f)
pr = [p for p in b.check() if not (p.startswith('OVERLAP') and float(p.split()[-2]) < 0.1)]
print('\n'.join(pr) if pr else 'whole board: no overlaps'); print('signal tree length %.0f mm' % b.wirelength()[0])
json.dump({r: v for r, v in b.P.items() if not b.fixed(r)}, open(sys.argv[1], 'w'), indent=0)
if len(sys.argv) > 2: b.render(sys.argv[2])
