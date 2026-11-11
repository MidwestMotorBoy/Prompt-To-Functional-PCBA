import json, sys, xml.etree.ElementTree as ET
truth = json.load(open("truth.json"))["nets"]
T = {frozenset((r, p) for r, p in v) for v in truth.values()}
t = ET.parse(sys.argv[1]).getroot()
K = {frozenset((x.get('ref'), x.get('pin')) for x in n.iter('node')) for n in t.iter('net')}
print("truth nets", len(T), "kicad nets", len(K), "identical partition:", T == K)
for s in T - K: print("  only in truth:", sorted(s))
for s in K - T: print("  only in kicad:", sorted(s))
