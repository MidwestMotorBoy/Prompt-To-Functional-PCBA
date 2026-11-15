# A3 = A2 + port 2 south row (pins 16..19 walled by the PPHV pour that grows 1.5 mm west from pad 20 -> R524):
#  R541 (SBU_FLT pull-up) rot 270 straight under pin 19, its SBU_FLT pad 0.5 mm below the pin: its escape ring and the
#    pin's keep PPHV out of the strip; R504 (CHG_INT pull-up) under it, reached by pin 18 down the lane west of R541;
#  U502 (EEPROM) 0.7 mm west so the lane under pins 17/18 is free; C508 0.6 mm west to clear U502, R502/R503 0.6 mm west.
import sys; sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/pdfix/tools'); import pf
P = pf.load()
def mv(r, x, y, rot): P[r] = [x, y, rot]
# A2
mv('R455', 103.0, 77.75, 270); mv('U505', 95.75, 73.65, -90)
mv('R555', 82.0, 77.75, 270); mv('C504', 80.2, 76.9, 270); mv('C503', 81.0, 74.6, 0)
# port 2 south
mv('U502', 84.5, 86.5, 90); mv('C508', 82.4, 84.7, 0)
mv('R541', 86.5, 84.25, 90); mv('R504', 86.4, 85.9, 90)
mv('R502', 81.6, 86.8, 90); mv('R503', 82.5, 86.8, 90)      # I2CC pull-ups 0.6 mm west with the EEPROM
name = sys.argv[1] if len(sys.argv) > 1 else 'a3'
print(pf.check(P)); g, s, ov = pf.save(P, name); print(g, s, len(ov), 'changed')
for r in ('R541', 'R504', 'U502'): print(r, {k: (v[0], v[1], v[2].split('/')[-1]) for k, v in pf.pads(P, r).items() if k})
