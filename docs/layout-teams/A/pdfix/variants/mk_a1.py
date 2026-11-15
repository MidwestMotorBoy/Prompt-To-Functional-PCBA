# A1: lanes above the port protectors' C_CC pins, DRV9_OFF pull-up in front of pin 37, PP5V cap horizontal.
#  U405/U505 0.5 mm south: the VBUS pour round J's VBUS pads then stops at its 1.5 mm grow limit (y 71.25), not at the
#    pins' 0.55 mm escape ring, so a 0.8 mm lane opens above pins 3..5 (C_CC2, C_CC1, VBIAS).
#  C407/C507 rot 0, 0.6 mm above the north row: PP5V pad 1 over pin 34, GND pad 2 over pin 31 (GND pin joins it straight).
#  (U505 only 0.35 mm: C541 below; C403 0.28 mm west to clear U405)
#  R455/R555 rot 270: DRV9_OFF pad 2 0.5 mm in front of pin 37 (escape ring keeps PP5V off the pin's exit).
import sys; sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/pdfix/tools'); import pf
P = pf.load()
def mv(r, x, y, rot): P[r] = [x, y, rot]
mv('U405', 104.3, 73.8, -90); mv('C407', 104.9, 77.7, 0); mv('R455', 103.0, 77.75, 270)
mv('U505', 95.75, 73.65, -90); mv('C403', 100.72, 76.2, 0); mv('C507', 83.9, 77.7, 0); mv('R555', 82.0, 77.75, 270)
mv('C504', 80.2, 76.9, 270); mv('C503', 81.0, 74.6, 0)
name = sys.argv[1] if len(sys.argv) > 1 else 'a1'
print(pf.check(P)); g, s, ov = pf.save(P, name); print(g, s, len(ov), 'changed')
for r in ('C407', 'R455', 'C507', 'R555', 'C504', 'C503'): print(r, {k: (v[0], v[1], v[2].split('/')[-1]) for k, v in pf.pads(P, r).items() if k})
