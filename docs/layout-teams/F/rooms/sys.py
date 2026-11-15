import sys; sys.path.insert(0, '../tools')      # run from the rooms folder: python3 sys.py
from room import Room
rm = Room('sys')

# ---------------- 3.3 V buck (lower-left corner of the room) ----------------
# U204: west column 1=PGND 2,3=VIN(PACK_P) 4,5=GND; east column 10=3V3(VOS) 9=SW 8=3V3_SLEEP 7=nc 6=GND
UX, UY = 82.36, 128.50
rm.put('U204', UX, UY, 0)
# hot loop: C206 upright west of U204, PACK_P pad (south) level with pins 2/3, GND pad (north) just above pin 1.
rm.put('C206', 79.60, UY - 1.05, 180)
# SW: pad 9 straight east into L201 pad 1; L201 pad 2 sits under the fixed 3V3 test pad TP301.
rm.put('L201', 87.19, 129.24, 0)        # 1.4 mm gap to U204's east pins: via spot for 3V3_SLEEP (pad 8) at (84.45,129.3)
# output capacitor directly behind L201 pad 2, 3V3 pad west, GND pad east (free space east/south for GND vias)
rm.put('C207', 91.34, 130.45, 0)
# SLEEP pull-up R313 moved here from the MCU: 3V3 pad east, next to TP301 (top-layer 3V3), SLEEP pad west with a via spot
rm.put('R313', 86.50, 125.60, 180)

# ---------------- MCU: antenna match (hand arrangement kept) ----------------
rm.put('C314', 114.89, 117.96, 0)
rm.put('C313', 116.76, 117.96, 0)
rm.put('R321', 118.62, 117.96, 0)
rm.put('C315', 120.52, 117.96, 0)

# ---------------- MCU: decoupling + SCL pull-up, north-west of the module ----------------
rm.put('R304', 112.72, 117.68, 0)       # SCL pad south, straight above U301 pad 9; 3V3 pad north
rm.put('C302', 113.52, 117.68, 270)     # GND pad south above U301 pad 8 (GND); 3V3 pad north
rm.put('C301', 113.30, 116.42, 180)     # 3V3 pad west (joins R304/C302/C303 3V3), GND pad east
rm.put('C303', 111.62, 116.50, 0)       # 3V3 pad east, GND pad west

# ---------------- MCU: west strip ----------------
# The 10 A CELL_P top copper of pack_gauge fills this strip up to 0.25 mm from our pads and 0.57 mm from U301's pads
# (runs sys_f1, sys_f2), so a pad that faces west can never get a via. Parts stand upright, 0.8 mm from U301's pads:
# too narrow for the pour to enter, wide enough for a 0.45 mm via.
rm.put('R305', 110.30, 119.30, 90)      # NW corner: SDA pad south, 0.5 mm from U301 pad 10; 3V3 pad north (via NE of it)
rm.put('C304', 110.00, 124.40, 270)     # NRST pad north, level with U301 pad 14; GND pad south, via east of it
# NRST pull-up R302 moved to the 3V3 cluster north of the module (its 3V3 pad had no path in the strip, run sys_f2):
rm.put('R302', 111.55, 117.35, 180)     # 3V3 pad east facing R304's 3V3 pad; NRST pad west, via spot south at (111.2,118.15)
rm.done()
