# A2 = merged + the A1 moves that helped, without the horizontal PP5V caps (they walled CC1/CC2 pins 28/29 and VBUS pin 32):
#  R455/R555 rot 270, DRV9_OFF pad 2 0.5 mm in front of pin 37 (A1: port 1 DRV9_OFF 2 edges freed).
#  U505 0.35 mm south (A1: port 2 VBIAS freed: the J501 VBUS pad pour stops at its 1.5 mm grow limit above the pins).
#  Port 2 NW: C503 (3V3) up to R555's old spot, C504 (LDO_3V3) vertical at the board lip, to make room for R555.
import sys; sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/pdfix/tools'); import pf
P = pf.load()
def mv(r, x, y, rot): P[r] = [x, y, rot]
mv('R455', 103.0, 77.75, 270)
mv('U505', 95.75, 73.65, -90)
mv('R555', 82.0, 77.75, 270); mv('C504', 80.2, 76.9, 270); mv('C503', 81.0, 74.6, 0)
name = sys.argv[1] if len(sys.argv) > 1 else 'a2'
print(pf.check(P)); g, s, ov = pf.save(P, name); print(g, s, len(ov), 'changed')
