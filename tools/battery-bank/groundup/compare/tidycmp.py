"""tidycmp.py tag1 tag2 [tag3 ...]   Table of the tidiness numbers (tidy_<tag>.json from tidy.py) of several boards,
on the nets that are routed as tracks on all of them, and the per-net width count on every net."""
import json, sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); tags = sys.argv[1:]
D = {t: {r['net']: r for r in json.load(open(os.path.join(HERE, f'tidy_{t}.json')))['nets']} for t in tags}
common = set.intersection(*[set(d) for d in D.values()])
def tot(rows):
    L = sum(r['length'] for r in rows); M = sum(r['mst'] for r in rows)
    return [('nets', len(rows)), ('track length, mm', round(L)), ('length / shortest tree', round(L / M, 2)), ('segments', sum(r['segs'] for r in rows)),
            ('segments under 0.2 mm', sum(r['short'] for r in rows)), ('bends', sum(r['bends'] for r in rows)), ('vias', sum(r['vias'] for r in rows)),
            ('nets over 1.5x', sum(1 for r in rows if r['detour'] > 1.5 and r['mst'] > 2)), ('nets over 2x', sum(1 for r in rows if r['detour'] > 2 and r['mst'] > 2)),
            ('nets in one width', sum(1 for r in rows if r['widths'] == 1)), ('nets in two widths', sum(1 for r in rows if r['widths'] == 2)),
            ('nets in three or more widths', sum(1 for r in rows if r['widths'] > 2)), ('width changes, all', sum(r['wsteps'] for r in rows)), ('width changes away from a pad', sum(r['wsteps_mid'] for r in rows)),
            ('segments off the 45 degree grid', sum(r['offangle'] for r in rows))]
out = {}
for name, pick in (('common nets', lambda d: [d[n] for n in common]), ('all track nets', lambda d: list(d.values()))):
    T = {t: tot(pick(D[t])) for t in tags}; out[name] = {t: dict(T[t]) for t in tags}
    print(f'\n{name}\n' + ' ' * 34 + ''.join(f'{t:>10s}' for t in tags))
    for i, (k, _) in enumerate(T[tags[0]]): print(f'{k:34s}' + ''.join(f'{T[t][i][1]:>10}' for t in tags))
json.dump(out, open(os.path.join(HERE, 'tidycmp_' + '_'.join(tags) + '.json'), 'w'), indent=1)
