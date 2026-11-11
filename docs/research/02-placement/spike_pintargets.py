"""Spike A: how many of the pin targets that were typed by hand into place_*.py can be derived from the netlist alone?
Usage: spike_pintargets.py <groundup dir>
Rule tried (no LLM, no schematic fields): for a pad of a two-pad part, on a net that is not a plane net, the target is
the pad on that net that belongs to the part with the most pads (the 'parent'); ties broken by fewest pads on net."""
import sys, re, json, glob, os, collections
g = sys.argv[1]; d = json.load(open(os.path.join(g, 'base.json')))
fp = {f['ref']: f for f in d['fps']}
PLANE = {'GND', 'PACK_P', '3V3'}
net = collections.defaultdict(list)
for f in d['fps']:
    for p in f['pads']:
        if p['net']: net[p['net']].append((f['ref'], p['n']))
padnet = {(f['ref'], p['n']): p['net'] for f in d['fps'] for p in f['pads']}
typed = []
for path in sorted(glob.glob(os.path.join(g, 'place*.py'))):
    src = open(path).read()
    # literal calls only; loops with f-strings are skipped and counted separately
    for m in re.finditer(r"A\('(\w+)',pins=\{([^}]*)\}", src):
        for n, t in re.findall(r"'(\w+)':'(\w+)\.(\w+)'", m.group(2)) and [(a, (b, c)) for a, b, c in re.findall(r"'(\w+)':'(\w+)\.(\w+)'", m.group(2))]:
            typed.append((m.group(1), n, t))
same_net = ident = parent_ok = plane = 0; miss = []
for ref, n, (tr, tn) in typed:
    nn = padnet.get((ref, n)); tnet = padnet.get((tr, tn))
    if nn != tnet: miss.append((ref, n, nn, tr, tn, tnet, 'typed target is on another net')); continue
    same_net += 1
    if nn in PLANE: plane += 1; continue
    cands = [(r, k) for r, k in net[nn] if r != ref]
    best = max(cands, key=lambda c: (len(fp[c[0]]['pads']), c[0] == tr))
    if best[0] == tr: parent_ok += 1
    else: miss.append((ref, n, nn, tr, tn, best, 'rule picked another part'))
    if best == (tr, tn): ident += 1
print('typed pad targets parsed:', len(typed))
print('  target on the same net as the pad:', same_net, ' (of those on a plane net:', plane, ')')
print('  rule picks the same parent part:', parent_ok, '  the same pad:', ident)
for m in miss: print('   ', m)
two = [f for f in d['fps'] if len(f['pads']) == 2]
print('two-pad parts on board:', len(two), ' with at least one non-plane pad whose net has <=4 pads:',
      sum(1 for f in two if any(p['net'] and p['net'] not in PLANE and len(net[p['net']]) <= 4 for p in f['pads'])))
