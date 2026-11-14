import sys, os, glob, json; sys.path.insert(0, '../tools')
from room import Room
rm = Room('pack_gauge')
# show the neighbours' latest placements in the picture and the checks (read only)
for f in glob.glob('*.json'):
    if f.endswith('.spec.json') or f in ('master.json', 'pack_gauge.json'): continue
    for r, v in json.load(open(f)).items():
        if r not in rm.parts and r in rm.b.P: rm.b.P[r] = [v[0], v[1], int(v[2]) % 360]

# ---------------- FET pair: Q102 turned so its PACK_P sources face north (toward J113 / R527 / R427),
# Q101 with its CELL_P sources facing east, 2.9 mm lower than the hand board: nearer the H103 / J118 neck to F102.
Q102_TOP, Q101_BOT = 116.3, 124.6
rm.put_court('Q101', rot=0, right=109.1, bottom=Q101_BOT)
rm.put_court('Q102', rot=90, right=rm.court('Q101')[0], top=Q102_TOP)

TY = 116.05
# ---------------- top strip above Q101
# row A: PACK_P -> C107 -> CMID -> C108 -> GND (via east of it); row B: PACK_P -> C111 -> mid -> C110 -> CELL_P
rm.put_court('C107', rot=180, left=101.72, top=116.05)
rm.put_court('C108', rot=180, left=103.73, top=116.05)
rm.put_court('C111', rot=0, left=101.72, top=117.16)
rm.put_court('C110', rot=0, left=103.73, top=117.16)
# CHG gate parts right above Q101's gate (pad 4, NE corner); WAKE resistor under TP113
rm.put_court('R110', rot=180, left=106.6, top=116.85)         # CELL_P top (C110), CHG_G bottom (gate)
rm.put_court('R109', rot=180, left=107.73, top=116.85)        # CHG top (via above), CHG_G bottom (gate)
rm.put_court('R118', rot=0, left=109.6, top=116.05)           # WAKE top (TP113), CELL_P bottom -> Q101 pad 3

# ---------------- west column: DSG gate parts, PACK sense, BAT diode; PBI cap in the small box
rm.put_court('D103', rot=270, left=93.5, top=TY)              # DSG_G top (Q102 gate), PACK_P bottom
rm.put_court('R112', rot=0, left=92.42, top=TY)               # PACK_P top, DSG_G bottom
rm.put_court('R111', rot=0, left=92.42, top=TY + 2.05)        # DSG_G top, DSG bottom
rm.put_court('R113', rot=0, left=92.42, top=121.0)            # PACK_P top, PACK bottom
rm.put_court('D101', rot=180, left=93.55, top=121.0)          # CELL_4P top, K bottom
rm.put_court('R105', rot=0, left=94.88, top=121.0)            # K top, BAT bottom
rm.put_court('C105', rot=0, left=88.75, top=121.3)            # PBI east, CELL_1N west

# ---------------- gauge U101 and its cell-input filter column (hand arrangement, 0.5 mm lower)
UX, UY = 99.12, 127.4
rm.put('U101', UX, UY, 0)
CX, RX = 94.95, 93.93
for i, (c, r) in enumerate([('C101', 'R104'), ('C102', 'R103'), ('C103', 'R102'), ('C104', 'R101')]):
    y = 125.2 + 1.96 * i
    rm.put(c, CX, y, 0); rm.put(r, RX, y + 0.05, 0)
rm.put_court('C106', rot=90, left=95.58, top=130.0)            # SRN/SRP cap at U101's SW corner (pins 6, 8)

# ---------------- east of U101: VCC feed from FET_MID, SMBus series resistors, gauge interrupt FET
rm.put_court('R106', rot=0, left=101.7, top=Q101_BOT + 0.1)  # FET_MID top (Q101 drain pad 8), VCC bottom (U101 pin 26)
rm.put_court('R115', rot=90, left=101.82, top=126.75)         # SMBC top (U101 pin 19), SCL bottom
rm.put_court('R116', rot=90, left=101.82, top=128.3)          # SMBD top (U101 pin 18), SDA bottom (vias below)
rm.put_court('Q103', rot=0, left=102.85, bottom=129.68)       # IRQ_N drain up (via room above it), gate/GND down
rm.put_court('R117', rot=0, left=92.45, top=122.97)           # 470k BTP_INT pull-down, parked in the west column
rm.put_court('R314', rot=180, left=103.6, top=Q101_BOT + 0.12)  # IRQ_N pull-up: IRQ_N east (over Q103 drain), 3V3 west

# ---------------- shunt: hand position; pad 2 (GND) keeps x 90.8-93.4 free for its vias
rm.put('RS101', 88.4829, 132.9944, 0)
# R107/R108 west of the shunt, tap pins on top: the taps leave the inner pad edges and run along RS101's north edge;
# SRP/SRN leave through vias below them (x 83.5-85.5 is free down to the board edge) to C106 at U101
rm.put_court('R108', rot=180, left=92.35, top=131.68)         # GND top (pad 2 side, among its vias), SRN bottom
rm.put_court('R107', rot=270, left=83.55, top=131.75)         # CELL_N east (pad 1 side), SRP west

# ---------------- second-level protector U102 below U101 (turned: W = VDD,V4,V3,V2 top->bottom, E = OUT,CD,VSS,V1),
# its six caps in a ring round it, the cell-input resistors in the gaps between the wire pads at the bottom edge
rm.put('U102', 101.3, 132.8, 90)
rm.put_court('C116', rot=0 if False else 90, left=100.4, top=130.4)    # VDD / VSS across the top
rm.put_court('C112', rot=90, left=98.64, top=130.75)          # V4 top, V3 bottom
rm.put_court('C113', rot=90, left=98.64, top=132.7)           # V3 top, V2 bottom
rm.put_court('C117', rot=270, left=102.94, top=130.55)        # VSS top, CD bottom
rm.put_court('C115', rot=0, left=102.94, top=132.52)          # VSS top, V1 bottom
rm.put_court('C114', rot=90, left=100.9, top=134.1)           # V2 / V1 across the bottom
rm.put_court('R121', rot=0, left=101.3, top=135.15)           # V2 top, CELL2 bottom (J110 beside)
rm.put_court('R120', rot=90, left=97.85, top=134.75)          # V3 top, CELL3 bottom (via)
rm.put_court('R122', rot=90, left=104.5, top=133.9)           # V1 west, CELL1 east (via)
rm.put_court('R123', rot=180, left=106.5, top=133.9)          # VDD top, CELL_4P bottom (J116 beside)
rm.put_court('R119', rot=90, left=109.7, top=133.9)           # CELL_4P / V4

# ---------------- fuse corner: F102 with pad 2 (CELL_P) at the exit of the H103 / J118 neck, pad 1 over J112;
# Q104 drain (pad 3) faces the fuse heater pad 3; gate network round Q104
rm.put_court('F102', rot=0, left=111.42, top=128.75)
rm.put_court('Q104', rot=0, left=116.1, top=127.98)
rm.put_court('C118', rot=180, left=115.02, top=126.85)        # CELL_1N west, Q104-G east
rm.put_court('R126', rot=0, left=116.97, top=126.85)          # Q104-G west, GAUGE_FUSE east
# x 119.0-120.4 under U301's GND pads 22/23 is left free for their vias
rm.put_court('R125', rot=0, left=120.47, top=126.85)          # GND top (U301 GND pad 24 above), G bottom
rm.put_court('R124', rot=180, left=120.47, top=128.9)         # G top, OUT bottom (via below)

done = rm.done()
