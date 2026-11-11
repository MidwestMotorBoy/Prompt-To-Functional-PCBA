"""Compact view of one sheet of the truth netlist: parts, then nets as ref.pin(name)."""
import json,sys
t=json.load(open(sys.argv[1]));sh=sys.argv[2]
C=t['comps'];N=t['nets']
refs={r for r in C if C[r]['sheet']==sh}
skip=('Footprint','Datasheet','Description','Notes','Sim.Device','Sim.Pins','Sim.Type')
for r in sorted(refs):
    c=C[r];f={k:v for k,v in c['fields'].items() if k not in skip and v}
    print(f"{r}\t{c['lib']}\t{c['value']}\t{c['footprint'].split(':')[-1]}\t{f}")
print()
for n,nodes in sorted(N.items()):
    own=[f"{a}.{b}" + (f"({f.rsplit('_',1)[0]})" if f and not a[0] in 'CRL' else '') for a,b,f in nodes if a in refs]
    if own: print(f"{n}  [{len(nodes)-len(own)} ext]: {' '.join(own)}")
