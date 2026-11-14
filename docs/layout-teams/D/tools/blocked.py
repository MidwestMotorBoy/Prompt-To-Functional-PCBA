"""blocked.py <run dir> [room]  - (with a room name, only the edges that touch that room's parts) the blocked-edge screen (ghost.log) and power opens of a scorecard run, grouped by part."""
import sys, re, json, collections, os
d = sys.argv[1]; room = sys.argv[2] if len(sys.argv) > 2 else None
mine = set(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rooms', room + '.spec.json')))['parts']) if room else None
g = open(os.path.join(d, 'ghost.log')).read(); c = collections.Counter(); rows = []
for l in g.splitlines():
    if not l.startswith('GHOSTFAIL'): continue
    net = l[10:].split(' Pad')[0]; refs = re.findall(r'Pad (\S+) \[[^\]]*\] of (\w+) on', l); rows.append((net, refs))
    for r in set(x[1] for x in refs): c[r] += 1
m = re.search(r'GHOST noway (\d+) of (\d+)', g); print('BLOCKED', m.group(0) if m else 'not finished')
if os.path.exists(os.path.join(d, 'score.json')): print('SCORE', json.dumps(json.load(open(os.path.join(d, 'score.json')))))
if os.path.exists(os.path.join(d, 'plan.log')):
    for l in open(os.path.join(d, 'plan.log')):
        if 'left to router [' in l and not l.rstrip().endswith('[]'): print('COPPER', l.strip()[:230])
print('by part:', ', '.join(f'{r} {n}' for r, n in c.most_common()))
for n, r in sorted(rows):
    if mine is not None and not any(a in mine for p, a in r): continue
    print('  ', n, ' -> '.join(f'{a}.{p}' for p, a in r))
