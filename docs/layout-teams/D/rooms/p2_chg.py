import sys; sys.path.insert(0, '../tools')      # cd rooms && python3 p2_chg.py
from room import Room
rm = Room('p2_chg')

# ---- charger controller: north side faces the stage; 0.6 mm west of the hand spot to give the east side two columns
CX, CY = 87.81, 110.51
rm.put('U503', CX, CY, 0)
W = rm.court('U503')                      # chip courtyard

# ---- north strip: only C510 (REGN), straight above its pin; the gate/boot nets fan out on both sides of it
rm.beside('C510', 'U503.24', 'N', gap=0.25)

# ---- west, top: input-shunt sense filter; taps R525.1 / R526.1 face north (vias above / beside them)
xa = 80.72                                 # ACP column (R525 over C514 pad 1), ACN column 0.96 to the east
rm.put('C514', xa + 0.48, 107.25, 0)       # pad 1 ACP west, pad 2 ACN east
rm.beside('R525', 'C514.1', 'N', gap=0.05)
rm.beside('R526', 'C514.2', 'N', gap=0.05)
rm.beside('C516', 'C514', 'E', gap=0.1, rot=0)          # ACN pad west (next to C514 ACN), GND east
rm.beside('C515', 'C514.1', 'S', gap=0.1)               # ACP pad north, GND south
# ---- west, middle: VAC cap facing the two PPHV pins, ACUV/ACOV divider as rows, FSW under the SW corner
R = W[0] - 0.45
rm.put_court('C509', rot=0, right=R, top=109.95)                                 # PPHV east
rm.put_court('R509', rot=0, right=R, top=rm.court('C509')[3] + 0.1)             # PPHV east, ACUV west
rm.put_court('R510', rot=0, right=R, top=rm.court('R509')[3] + 0.1)             # ACUV west, ACOV east
rm.put_court('R511', rot=0, right=R, top=rm.court('R510')[3] + 0.1)             # ACOV east, GND west
rm.put_court('R512', rot=0, right=R, top=rm.court('R511')[3] + 0.1)            # FSW east, GND west

# ---- east: filter caps and FB divider next to their pins (inner column), C519 / R518 beside them (outer column);
#      the two tap resistors sit in the NE corner, taps east toward the battery shunt R527, SRP/SRN run down the
#      free top of the outer column
xi = W[2] + 0.45
rm.put('C517', xi + 0.51, (rm.pad('U503.14')[1] + rm.pad('U503.13')[1]) / 2, 0)   # SRP N, SRN S
rm.beside('C518', 'C517', 'N', gap=0.1, rot=0)          # GND N, SRP S
rm.beside('R519', 'C517', 'S', gap=0.1, rot=0)          # FB N, FBG S
xo = xi + 1.1
rm.put_court('C519', rot=0, left=xo, top=rm.court('C517')[1] + 0.5)      # SRN N (beside C517 SRN), GND S
rm.put_court('R518', rot=180, left=xo, top=rm.court('C519')[3] + 0.85)   # FB N, PACK_P S (GND via between)
rm.put_court('R528', rot=0, right=93.9, top=104.75)                      # BAT_SNS_P tap E, SRP_F W
rm.put_court('R529', rot=0, right=93.9, top=rm.court('R528')[3] + 0.1)   # PACK_P tap E, SRN_F W

# ---- south: CE_N pair, TS, ICHG, ILIM resistors in one row under the pins; the I2C/INT pins drop to vias under the
#      SW corner; R515 (REGN -> TS) sits below on the REGN path
x0 = 86.62
rm.put_court('R535', rot=270, left=x0, top=W[3] + 0.35)                  # CE_N N, CHG_INH S
rm.beside('R517', 'R535', 'E', gap=0.1, rot=270)                          # CE_N N, 3V3 S
T = W[3] + 0.35
rm.put_court('R516', rot=0, left=rm.court('R517')[2] + 0.1, top=T)       # TS N, GND S
rm.put_court('R513', rot=0, left=rm.court('R516')[2] + 0.08, top=T)      # ICHG N, GND S
rm.put_court('R514', rot=0, left=rm.court('R513')[2] + 0.08, top=T)      # ILIM N, GND S
rm.put_court('R515', rot=180, right=88.0, top=116.0)                     # TS W, REGN E

# ---- DRV_SUP diode-OR and 9 V gate-drive supply: west column C511 / D511 / C558 (DRV_SUP and OUT nodes
#      pad to pad), D510 beside D511; U506 in the lower box with OUT side west, IN/EN east; enable FET east
rm.put_court('C511', rot=0, left=78.6, top=110.05)               # GND N, DRV_SUP S
rm.put_court('D511', rot=270, left=78.6, top=rm.court('C511')[3] + 0.1)    # DRV_SUP N, anode (OUT) S
rm.put_court('D510', rot=180, left=rm.court('D511')[2] + 0.12, top=rm.court('C511')[3] + 0.1)   # DRV_SUP N, REGN S
rm.put_court('C558', rot=0, left=78.6, top=rm.court('D511')[3] + 0.1)      # OUT N, GND S
rm.put_court('R553', rot=0, left=78.6, top=rm.court('C558')[3] + 0.12)     # FB E, GND W
rm.put('U506', 83.97, 119.35, 270)                                # OUT/FB/GND west, IN/EN east
rm.put_court('R552', rot=0, left=80.8, bottom=117.4)             # OUT E, FB W (above U506's OUT/FB pads)
rm.put_court('C557', rot=270, right=85.95, bottom=117.45)   # PACK_P E (above IN), GND W
rm.put_court('Q509', rot=0, right=92.45, top=116.95)             # drain S, gate NE, source NW
rm.put_court('R554', rot=180, left=rm.court('U506')[2] + 0.15, bottom=121.15)    # REGN N, EN/drain S

rm.done()
if '-v' in sys.argv:
    for r in rm.parts:
        if rm.b.fixed(r): continue
        print(r, rm.b.P[r][2], [round(v,2) for v in rm.court(r)], [(p['num'], p['net'].split('/')[-1], round(p['x'],2), round(p['y'],2)) for p in rm.b.pads(r) if p['num']][:4])
