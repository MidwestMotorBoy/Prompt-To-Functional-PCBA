import sys; sys.path.insert(0, '../tools')      # run from the rooms folder: cd rooms && python3 p2_stage.py
from room import Room
# Port 2 four-switch stage: p1_stage moved DX = -23.1 (same FET/cap geometry, same hot loops), with changes:
#  - R527 turned 90 (BAT pad W, PACK_P pad E at ~x 98.3) so PACK_P lands next to the reserved lane / the In2 PACK_P pour.
#  - C513 / D505 / R546 shift left in the gate row (box ends at x 94.0); C512 and D504 go into the lower-left box.
DX = -23.1
rm = Room('p2_stage')
X1, Y1 = 108.6 + DX, 99.8          # Q501 centre (rot 180)
X2, Y2 = 113.36 + DX, 99.8         # Q502 centre (rot 0)
rm.put('Q501', X1, Y1, 180)
rm.put('Q502', X2, Y2, 0)
rm.put('C530', 108.55 + DX, 102.255, 180)       # Q501 south edge: VIN pad W under D1 paddle, GND pad E
rm.put('C538', X2 + 1.64 - 0.48, 97.35, 0)      # Q502 north edge, BAT pad E over pin 4
CX = (101.6 + 106.29) / 2 + DX                  # input column x 78.5-83.19, VIN pads E
rm.put('C520', CX, 100.195, 90)
rm.put('C523', CX, 96.895, 270)
rm.put('C524', CX, 93.595, 90)
rm.put('C527', CX, 90.295, 270)
OX = (116.8 + 121.49) / 2 + DX                  # output column x 93.7-98.39, BAT pads W
rm.put('C531', OX, 95.6, 90)   # BAT pad corner above the 46 deg ray from the D1 paddle corner: keeps HG2 out of the HL_OUT hull
rm.put('C534', OX, 92.3, 90)
rm.put_court('R527', rot=90, left=94.6, top=99.0)   # BAT W (up to the output caps), PACK_P E at ~(98.3, 100.2)
T = 102.0
rm.put_court('R544', rot=0, left=109.6 + DX, top=T)       # HG1 N, HIDRV1 S
rm.put_court('R545', rot=0,  left=110.68 + DX, top=T)     # LG1 N, LODRV1 S
rm.put_court('R547', rot=0, left=111.76 + DX, top=T)      # LG2 N, LODRV2 S
rm.put_court('D505', rot=0, left=112.84 + DX, top=T - 0.05)   # BTST2 N, DRV_SUP S
rm.put_court('R546', rot=0, left=114.38 + DX, top=T)      # HG2 N (under Q502 pin 1), HIDRV2 S
rm.put_court('C513', rot=180, left=115.46 + DX, top=T)    # BTST2 N, SW2 S
# lower-left box: boot parts of the Q501 half (kept above R525/R526 at y 104.3)
# note: R545's footprint is drawn vertical, so rot 0 here = R445 rot 90 (LG1 N)
rm.put_court('D504', rot=0, left=80.2, top=101.88)       # BTST1 N, DRV_SUP S
rm.put_court('C512', rot=270, left=82.2, top=103.2)       # BTST1 / SW1
rm.done()
