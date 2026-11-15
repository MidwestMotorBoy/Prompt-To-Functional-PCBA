"""blocked.py <scorecard outdir> [...]: blocked edges (GHOSTFAIL lines of ghost.log) counted by area.
stage = charger power stage (port 1/2 Q, TH, gate drive, U403/U503 power-side pins, R4xx/R5xx at the sense resistors);
p1 / p2 = port top blocks (PD chip U401/U501, port protector U405/U505, EEPROM, pull-ups, connector); other = rest."""
import sys, re, os, collections
STAGE_NETS = re.compile(r'/(HG\d|LG\d|SW\d|FSW|AC_SNS_N|BAT_SNS_P|HIDRV\d|LODRV\d|BTST\d|REGN)$|ACOV|PACK_P')
def area(line):
    refs = re.findall(r'of (\S+) on', line); net = re.match(r'GHOSTFAIL (.*?) (Pad|Via|Zone) ', line).group(1)
    if STAGE_NETS.search(net) or re.match(r'GND$', net) and any(re.match(r'(Q[45]0\d|TH[45]0\d)$', r) for r in refs): return 'stage'
    for r in refs:
        m = re.match(r'[A-Z]+([45])\d\d$', r)
        if m and not r.startswith(('Q', 'TH')): return 'p1' if m.group(1) == '4' else 'p2'
    if 'Port 1' in net: return 'p1'
    if 'Port 2' in net: return 'p2'
    return 'other'
for d in sys.argv[1:]:
    L = [l.strip() for l in open(os.path.join(d, 'ghost.log')) if l.startswith('GHOSTFAIL')]
    m = re.search(r'GHOST noway (\d+) of (\d+)', open(os.path.join(d, 'ghost.log')).read())
    c = collections.Counter(area(l) for l in L)
    print(f'{d}: {m.group(1) if m else "?"} of {m.group(2) if m else "?"}  ' + '  '.join(f'{k} {c[k]}' for k in ('stage', 'p1', 'p2', 'other')))
    if '-v' in os.environ.get('V', ''):
        for l in sorted(L, key=area): print('  ', area(l), l[10:])
