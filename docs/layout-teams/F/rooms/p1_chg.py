"""Room p1_chg: Port 1 charger controller U403 with its filters and programming, and the Port 1 5 V buck.
Run from the rooms folder:  cd rooms && python3 p1_chg.py > /tmp/p1_chg.out

Plan (x right, y down):
- 5 V buck on the west: output caps C442 (box 0), C441, C443 in a column west of the PP5V lane (x 99.4-101.0), inductor L402 upright under the lane (PP5V pad north, SW pad south), U404 directly under the SW pad, boot cap
  C440 and first input cap C446 in one column east of U404, bulk input cap C444 in the south-west corner over the
  bottom-side PACK_P capacitor pads.
- U403 stays at the hand position. West of it: sense filter (R425/R426, C416, C415/C414 with C414 on pins 29/30), then
  a stack C409, R409, R410, R411, R412 in pin order. North strip: only C410 and C411, on their pins. D410 sits in the
  east end of box 1 (REGN/DRV_SUP both leave north anyway). The column east of L402 (x 104.5-105.85, y 104.9-110.1) is
  kept empty as via land. R415/R416 (thermistor divider) sit in box 3 under J113; REGN, TS and GND reach them by via.
- East: C417 on pins 13/14, C418 above, R419 on pins 11/12, then a second column R428, R429, C419; R418 under J113.
"""
import sys; sys.path.insert(0, '../tools')
from room import Room
rm = Room('p1_chg')

# ---------------- charger controller (hand position) ----------------
rm.put('U403', 111.4358, 110.4432, 0)

# ---------------- 5 V buck ----------------
rm.put_court('C442', rot=0,   right=99.3, top=102.5)     # PP5V pad east, at the lane
rm.put_court('C443', rot=0,   left=94.0,  top=107.4)     # PP5V pad east, under C441 (box 1 stays free: PPHV copper comes down there)
rm.put_court('C441', rot=0,   left=94.0,  top=104.95)    # PP5V pad east, faces L402 pad 2
rm.put_court('L402', rot=90,  left=98.7,  top=104.95)    # PP5V pad north (under the lane), SW pad south
rm.put('U404', 102.0, 113.015, 0)                        # N row FB SS BST SW, S row GND EN VIN GND
rm.put_court('C440', rot=270, left=103.4, top=111.55)    # SW pad north (to L402 pad), BST pad south
rm.put_court('C446', rot=0,   left=103.4, top=113.75)    # GND pad north at pin 4, PACK_P pad south
rm.put_court('C439', rot=270, left=99.58, top=112.7)     # SS pad north (SS runs under U404 between the pin rows), GND south to TP412
rm.put_court('C444', rot=270, left=94.0,  top=110.3)     # PACK_P pad north over the bottom-side PACK_P pads
rm.put_court('R433', rot=0,   left=97.5,  top=109.85)     # PP5V north, FB south
rm.put_court('R434', rot=90,  left=98.55, top=111.65)    # FB east (to pin 8), GND west (to TP412)
rm.put_court('R432', rot=90,  left=99.55, top=114.65)    # GND east (pin 1), EN west

# ---------------- west of U403: sense filter, VAC bypass, input window divider ----------------
# The stack C409..R412 keeps 1 mm free in front of pins 32-36 (x 107.25-108.24): the router's pin stubs leave straight
# west and need that strip to fan south (ACUV had no path when a pad sat 0.7 mm in front of pin 34).
rm.put_court('D410', rot=180, left=105.85, top=102.45)     # DRV_SUP north, REGN south
rm.put_court('R425', rot=0, left=105.85, top=105.05)
rm.put_court('R426', rot=0, left=106.87, top=105.05)
rm.put_court('C416', rot=90, left=105.92, top=107.03)     # ACN_F east under R426, GND west
rm.put('C414', 107.375, 109.03, 270)                     # ACN_F north on pin 29, ACP_F south on pin 30
rm.put('C415', 106.355, 109.03, 180)                     # ACP_F south beside C414, GND north
# (The thermistor divider R415/R416 used to stand here, x 104.55-105.58, y 104.9-108.85, squeezed between the PPHV
#  power copper on its west and the sense filter on its east: TS had no via spot at all. It now sits in box 3 under
#  J113, see below; this column is left free as via land: ACP_F runs down it, REGN / PPHV-tap vias go here.)
rm.put_court('C409', rot=180, right=107.55, top=110.15)   # PPHV WEST (power copper lands from the west, clear of pins 34-36), thin link to pins 32/33 along y 110.05
rm.put_court('R409', rot=180, right=107.3,  top=111.75)   # ACUV east (pin 34), PPHV west
rm.put_court('R410', rot=0,   right=107.4,  top=112.8)  # ACOV east, ACUV west
rm.put_court('R411', rot=0,   right=107.39, top=113.85)   # ACOV east, GND west
rm.put_court('R412', rot=0,   right=107.39, top=114.9)  # FSW east, GND west

# ---------------- north strip ----------------
rm.put('C410', 111.19, 106.4, 90)                        # REGN south on pin 24 (untested option: C410 x 111.34 and C411 left 111.86 give LODRV1 a straight run north)
rm.put_court('C411', rot=90, left=111.71, top=104.65)    # DRV_SUP west above pin 23, GND east; 1.0 mm lane between its pads and pins 22-19 so LODRV2/BTST2/HIDRV2 can turn east/north

# ---------------- south ----------------
# Slot x 111.6-112.6 between the CE_N pads and R413 is for TS (pin 8): track south, via at about (112.12, 114.55),
# GND via of R413/R414 under it at (112.12, 115.35). West of R435/R417 (x 108.3-110.4) is via land for SCL, SDA, CHG_INT,
# CHG_INH and 3V3.
rm.put('R413', 112.91, 114.66, 0)                        # (cannot go lower: C301 of the sys room sits at y 115.57 under them)
rm.put('R414', 113.93, 114.66, 0)
rm.put_court('R435', rot=0, right=111.81, top=113.87)    # CE_N east, south-west of pin 7
rm.put_court('R417', rot=0, right=111.81, top=114.70)

# ---------------- east ----------------
rm.put('C417', 115.55, 110.5, 0)                         # SRP_F north / SRN_F south on pins 14/13
rm.put('C418', 115.55, 108.6, 0)                         # GND north, SRP_F south
rm.put('R419', 115.55, 112.47, 0)                        # FB north / FBG south on pins 12/11
rm.put('R428', 116.62, 108.33, 0)                        # BAT_SNS_P tap north, SRP_F south
rm.put('R429', 116.62, 110.33, 270)                      # PACK_P tap north, SRN_F south
rm.put('C419', 117.72, 111.65, 0)                        # SRN_F north (beside R429 pad 2), GND south
rm.put('R418', 116.62, 112.3, 180)                       # FB north beside R419 pad 1, PACK_P south
# thermistor divider, in the free strip under J113 (below the PACK_P copper): all three nets arrive by via
rm.put_court('R415', rot=270, left=118.9, top=111.3)     # TS north, REGN south
rm.put_court('R416', rot=0,  left=119.93, top=111.3)     # TS north, GND south

if '--pads' in sys.argv:
    for r in rm.parts:
        if rm.b.fixed(r) and r not in ('TP412',): continue
        c = rm.court(r)
        print(r, 'court %.2f-%.2f x %.2f-%.2f' % (c[0], c[2], c[1], c[3]),
              ' | '.join('%s %s (%.2f,%.2f)' % (p['num'], p['net'].split('/')[-1], p['x'], p['y']) for p in rm.pads_of(r)) if hasattr(rm, 'pads_of') else
              ' | '.join('%s %s (%.2f,%.2f)' % (p['num'], p['net'].split('/')[-1], p['x'], p['y']) for p in rm.b.pads(r) if p['num'] and r not in ('U403',)))
rm.done()
