import sys; sys.path.insert(0, '../tools')      # run from the rooms folder: cd rooms && python3 p1_stage.py
from room import Room
# Port 1 four-switch stage.
#  Q401 turned 180: D1 (AC_SNS_N) faces the input capacitor column on the west, S2 (GND) faces Q402's S2 across a
#  shared ground gap, SW1 paddle exits north straight into L401 pad 1. Gates HG1/LG1 are on Q401's north corners.
#  Q402 at 0: D1 (BAT_SNS_P) faces the output capacitors on the east, SW2 exits north into L401 pad 2, gates south.
#  Input caps: horizontal column west, AC pads on the east end (one AC strip down to Q401's D1 pins).
#  Output caps: horizontal column east, BAT pads on the west end, kept ABOVE Q402's HG2 pin so the hot-loop pour
#  does not wall HG2 in; BAT copper runs straight down to R427, R427 pad 2 sits on J113.
rm = Room('p1_stage')
X1, Y1 = 108.6, 99.8          # Q401 centre (rot 180)
X2, Y2 = 113.36, 99.8         # Q402 centre (rot 0)
rm.put('Q401', X1, Y1, 180)
rm.put('Q402', X2, Y2, 0)
# HF caps: C430 across Q401's south edge (AC pad under the D1 paddle, GND pad under the SW paddle -> pin 5),
#          C438 on Q402's north edge, BAT pad over pin 4.
rm.put('C430', 108.55, 102.255, 180)
rm.put('C438', X2 + 1.64 - 0.48, 97.35, 0)
# input column (west), AC pads east: C420 next to Q401's D1 pins, then C423, C424, C427 upward
CX = (101.6 + 106.29) / 2
rm.put('C420', CX, 100.195, 90)
rm.put('C423', CX, 96.895, 270)
rm.put('C424', CX, 93.595, 90)
rm.put('C427', CX, 90.295, 270)
# output column (east), BAT pads west
OX = (116.8 + 121.49) / 2
rm.put('C431', OX, 95.6, 90)   # BAT pad corner above the 46 deg ray from the D1 paddle corner: keeps HG2 out of the HL_OUT hull
rm.put('C434', OX, 92.3, 90)
# battery shunt: pad 1 (BAT_SNS_P) north, pad 2 (PACK_P) on J113
rm.put('R427', 119.575, 104.775, 0)
# gate zone under the FETs (y 102.0-104.5), parts in driver-pin order; gate resistors sit under their gate pins,
# their gate pad north, driver pad south (U403's north pins at y 108). A 0.5 mm strip is left under the FETs so the
# north pads of the boot parts can be reached.
T = 102.0
# row shifted 0.32 mm east (and R427 0.3 mm) because R426 (neighbour) now reaches x 107.957 inside this room
rm.put_court('C412', rot=270, left=107.96, top=103.45)            # BTST1 east, SW1 west (driver SW1/BTST1)
rm.put_court('R444', rot=0, left=109.92, top=T)                   # HG1 north, HIDRV1 south
rm.put_court('R445', rot=90, left=111.0, top=T)                 # LG1 north (down the FET gap), LODRV1 south
rm.put_court('R447', rot=0, left=112.08, top=T)                  # LG2 north (under Q402 pin 8), LODRV2 south
rm.put_court('D404', rot=0, left=113.16, top=T - 0.05)           # BTST1 north, DRV_SUP south
rm.put_court('R446', rot=0, left=114.7, top=T)                  # HG2 north (under Q402 pin 1), HIDRV2 south
rm.put_court('D405', rot=0, left=115.78, top=T - 0.05)           # BTST2 north, DRV_SUP south
rm.put_court('C413', rot=180, left=117.32, top=T)                 # BTST2 north, SW2 south
rm.done()
