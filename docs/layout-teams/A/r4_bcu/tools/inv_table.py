#!/usr/bin/env python3
"""inv_table.py <outdir> [<outdir> ...]: markdown table of B.Cu non-GND copper per net (mm2, zones + tracks) for each outdir."""
import sys, os, json, subprocess
here = os.path.dirname(os.path.abspath(__file__))
cols = []; rows = {}
for d in sys.argv[1:]:
    out = subprocess.run([sys.executable, f'{here}/bcu_area.py', d], capture_output=True, text=True).stdout
    j = json.loads([l for l in out.splitlines() if l.startswith('BCU_JSON')][0][9:])
    name = os.path.basename(os.path.normpath(d)); cols.append(name)
    for n, a in j['bcu_by_net'].items(): rows.setdefault(n, {})[name] = a
    rows.setdefault('**total B.Cu non-GND**', {})[name] = j['bcu_nongnd']
    rows.setdefault('**switch-node B.Cu (SW1+SW2, both ports)**', {})[name] = j['swnode_bcu']
    rows.setdefault('switch-node F.Cu', {})[name] = j['swnode'].get('F.Cu', 0)
print('| net (B.Cu) | ' + ' | '.join(cols) + ' |'); print('|---' * (len(cols) + 1) + '|')
for n in sorted(rows, key=lambda n: (n.startswith('**') or n.startswith('switch'), n)):
    print(f'| {n} | ' + ' | '.join(str(rows[n].get(c, '-')) for c in cols) + ' |')
