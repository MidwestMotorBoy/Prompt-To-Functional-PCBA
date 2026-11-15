#!/usr/bin/env python3
"""gu_to_score.py <groundup placement.json {ref:[x,y,abs_rot_deg]}> <out.json> [base.json]
Convert a groundup-style placement (absolute KiCad orientation) to the scorecard / apply_placement.py format
{ref:[x,y,ang]} where ang is a multiple of 90 RELATIVE to the template board: new_orientation = template_rot - ang.
Only parts that differ from the template (base.json = dump of tools/score/template/board.kicad_pcb) are written."""
import json, sys, os
here = os.path.dirname(os.path.abspath(__file__))
base = sys.argv[3]
B = {f['ref']: f for f in json.load(open(base))['fps']}
P = json.load(open(sys.argv[1])); out = {}
for r, (x, y, rot) in P.items():
    f = B[r]; ang = round((f['rot'] - rot) % 360)
    if ang % 90: sys.exit(f'{r}: rotation {rot} is not a quarter turn from the template ({f["rot"]})')
    if abs(f['x'] - x) < 1e-4 and abs(f['y'] - y) < 1e-4 and ang == 0: continue
    out[r] = [x, y, ang]
json.dump(out, open(sys.argv[2], 'w'), indent=0)
print(f'{len(out)} parts differ from the template, of {len(P)}')
