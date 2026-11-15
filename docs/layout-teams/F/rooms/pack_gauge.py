import sys; sys.path.insert(0, '../tools')
from room import Room
rm = Room('pack_gauge')
DY = 1.68                      # gauge block sits this much lower than on the hand board (FETs are upright now)

# ---- 10 A path: FET pair upright. Q102 PACK_P pads north (towards J113), Q101 CELL_P pads south (towards F102)
rm.put_court('Q102', rot=90, left=97.7, top=116.0)
rm.put_court('Q101', rot=90, right=109.1, top=116.0)        # 0.55 up: 1.2 mm of CELL_P copper fits between R110's gate pad and H103
rm.put('F102', 114.19, 131.83, 0)                           # 0.2 east: 1.2 mm pocket between J302's east guide holes and pad 2 (SCL via spot 111.45,131.8)
rm.put('RS101', 88.48, 132.99, 0)

# ---- shunt sense resistors right at the shunt (taps leave the inner pad edges, go south under the body)
rm.put('R107', 88.95, 135.25, 180)     # N = CELL_N tap, S = SRP
rm.put('R108', 89.95, 135.25, 180)     # N = GND tap,   S = SRN

# ---- west block: gate parts of Q102, PACK_P clamp, Q103
rm.beside('R112', 'Q102.4', 'W', gap=0.15)                  # DSG_G pad at the gate, PACK_P pad west
rm.put('C111', 94.65, 116.55, 180)                          # E = PACK_P beside R112/R113's PACK_P pads, W = mid (via spot 93.3,116.55)
rm.put('C107', 92.95, 118.1, 270)                           # N = PACK_P, S = CMID
rm.put('C108', 92.95, 120.05, 270)                          # N = CMID, S = GND
rm.put('C105', 95.19, 123.0, 0)
rm.put_court('Q103', rot=0, left=94.0, top=118.0)
rm.put('R113', 94.65, 117.52, 90)                           # E = PACK_P next to R112's PACK_P pad, W = to U101 PACK

# ---- gauge
UX, UY = 99.57, 126.87 + DY
rm.put('U101', UX, UY, 0)
for r, x in (('R105', 97.54), ('R109', 98.55), ('R111', 99.57), ('R106', 101.60)):
    rm.put(r, x, 122.81 + DY + 0.36, 0)
rm.put('D101', 96.35, 124.9, 0)
for i, (r, c) in enumerate((('R104', 'C101'), ('R103', 'C102'), ('R102', 'C103'), ('R101', 'C104'))):
    y = 125.02 + 1.94 * i
    rm.put(r, 94.0, y, 0); rm.put(c, 95.02, y, 0)
rm.put('C106', 96.55, UY + 1.0, 90)
rm.put('D103', 103.35, 126.45, 270)                          # upright at the corridor edge: N = DSG_G, S = PACK_P (pulls the PACK_P inner pour south-east)
rm.put('R115', 103.06, UY + 0.75, 0)
rm.put('R116', 103.06, UY + 1.61, 0)
rm.put('R118', 109.65, 117.1, 0)                             # N = WAKE next to TP113, S = CELL_P
rm.put('C110', 105.14, 125.2, 270)                           # west edge of the CELL_P strip under Q101 pad 1: N = CELL_P, S = mid (via spot under D103's body 103.5,126.0); 11 mm from C111

# ---- gate of Q101
rm.beside('R110', 'Q101.4', 'S', gap=0.05, rot=90)          # E = CHG_G under the gate, W = CELL_P in the CELL_P copper

# ---- second-level protector (pins face west and east)
rm.put_court('U102', rot=90, left=101.25, top=132.6)
rm.put('R117', 100.9, 131.6, 0)                             # W = BTP_INT under pin 15, E = CELL_1N under pin 16
rm.put('C117', 103.2, 131.6, 180)                           # W = CELL_1N next to R117's, E = CD above pins 7/8
rm.put('C116', 99.8, 132.65, 270)                            # W = CELL_1N, E = VDD at pin 1
rm.put('C112', 99.8, 133.83, 180)                           # 0.56 mm channel above (V4 from R119) and 0.61 mm below (V3 from pin 3)                            # E = V4 at pin 2, W = V3
rm.put('C113', 98.08, 133.55, 270)                           # N = V2, S = V3 next to C112
rm.put('R121', 98.08, 135.55, 0)                             # N = V2, S = CELL2 next to J110
rm.put('R119', 97.0, 131.6, 180)                             # E = V4, W = CELL_4P
rm.put('C114', 101.83, 135.76, 90)                           # W = V2 under pin 4, E = V1
rm.put('C115', 105.4, 134.4, 270)                            # W = CELL_1N, E = V1
rm.put('R122', 106.95, 134.9, 180)                           # N = V1, S = CELL1
rm.put('R123', 110.5, 135.0, 0)                              # N = CELL_4P next to J116, S = VDD
rm.put('R120', 92.85, 132.75, 90)                            # CELL3 series resistor

# ---- fuse corner
rm.put_court('Q104', rot=0, left=116.6, top=127.7)
rm.put('R314', 117.4, 127.25, 180)
rm.put('R124', 121.0, 127.85, 0)
rm.put('R125', 121.0, 129.8, 0)
rm.put('R126', 120.1, 131.72, 0)
rm.put('C118', 118.1, 131.72, 0)
rm.done()
