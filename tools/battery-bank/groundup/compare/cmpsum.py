"""cmpsum.py tagA tagB: the check-loop numbers of two boards side by side, from the result files that runfix.sh
(and gmerge.py) leave: path resistance, Kelvin taps, hot loops per capacitor, gate loops, coupling, via current, sense pairs.
A line that moved and should not have is the finding."""
import json, sys, re, os
A, B = sys.argv[1:3]
def J(f, t): 
    p = f.format(t); return json.load(open(p)) if os.path.exists(p) else None
print('== path resistance, mOhm (0.1 mm grid)')
la, lb = J('k/cu_{}.json', A)['paths'], J('k/cu_{}.json', B)['paths']
for k in la: print(f"  {k:34s} {la[k]['R']*1e3:6.2f} {lb[k]['R']*1e3:6.2f}" + ('   <-- moved' if abs(la[k]['R'] - lb[k]['R']) > 3e-5 else ''))
print('== Kelvin tap error, %, 0.05 mm grid')
ka, kb = J('k/r05_{0}/kelvin_{0}.json', A), J('k/r05_{0}/kelvin_{0}.json', B)
for k in ka:
    if isinstance(ka[k], dict) and 'err_pct' in ka[k]: print(f"  {k:44s} {ka[k]['err_pct']:+6.2f} {kb[k]['err_pct']:+6.2f}")
print('== hot loops, nH (and per capacitor)')
ha, hb = J('hot_{}.json', A), J('hot_{}.json', B)
for k in ha:
    if hb and k in hb: print(f"  {k:22s} {ha[k]['eff_all']*1e9:.3f} {hb[k]['eff_all']*1e9:.3f}   " + ', '.join(f"{c} {ha[k]['caps'][c]*1e9:.2f}/{hb[k]['caps'].get(c, float('nan'))*1e9:.2f}" for c in ha[k]['caps']))
print('== gate loops, nH')
ga, gb = J('gate3_{}.json', A), J('gate3_{}.json', B)
if ga and gb:
    for k in ga:
        if k in gb: print(f"  {k:28s} {ga[k]['L']*1e9:6.2f} {gb[k]['L']*1e9:6.2f}  h {ga[k].get('h')} {gb[k].get('h')}")
    print('  sum', round(sum(v['L'] for v in ga.values()) * 1e9, 1), round(sum(gb[k]['L'] for k in ga if k in gb) * 1e9, 1), len([k for k in ga if k in gb]), 'loops')
print('== coupling: victims over 3 mV per edge')
ca, cb = J('coup_sum_{}.json', A), J('coup_sum_{}.json', B)
va = {v['label']: v['worst_mV'] for v in ca['victims'].values()}; vb = {v['label']: v['worst_mV'] for v in cb['victims'].values()}
for k in sorted(set(va) | set(vb), key=lambda k: -max(va.get(k, 0), vb.get(k, 0))):
    if max(va.get(k, 0), vb.get(k, 0)) > 3: print(f'  {k:18s} {va.get(k, 0):8.1f} {vb.get(k, 0):8.1f}')
print('  over 10 mV:', sum(1 for v in va.values() if v > 10), sum(1 for v in vb.values() if v > 10))
print('  to signals, pF:', round(sum(g['to_signals_fF'] for g in ca['groups'].values()) / 1000, 2), round(sum(g['to_signals_fF'] for g in cb['groups'].values()) / 1000, 2))
print('== vias')
xa, xb = J('k/via_{}.json', A), J('k/via_{}.json', B)
print('  highest via current, A:', round(max(t['i'] for p in xa.values() for t in p['top']), 2), round(max(t['i'] for p in xb.values() for t in p['top']), 2))
sa, sb = J('custats_{}.json', A), J('custats_{}.json', B)
print('  vias on the board:', sa['board']['vias'], sb['board']['vias'], ' keys', [k for k in sa['board'] if 'via' in k or 'gnd' in k.lower()])
print('  ', {k: (sa[k].get('vias'), sb[k].get('vias')) for k in ('fill1', 'fill2')})
pa, pb = J('senspair_{}.json', A), J('senspair_{}.json', B)
print('== sense pairs, enclosed area mm2:', round(sum(p['area'] for p in pa), 1), round(sum(p['area'] for p in pb), 1))
