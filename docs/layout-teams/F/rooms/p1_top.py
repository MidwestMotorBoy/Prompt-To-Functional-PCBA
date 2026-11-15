import sys; sys.path.insert(0, '../tools')
from room import Room
rm = Room('p1_top')

def pp(ref, pad, x, y, rot):
    """place ref so that pad `pad` sits at x, y with rotation rot"""
    rm.put(ref, 0, 0, rot); px, py = rm.pad(f'{ref}.{pad}'); rm.put(ref, x - px, y - py, rot)

# ---- PD controller: 2.1 east and 1.2 south of the hand spot (room for the west caps beside the PP5V lane and for the
#      PP5V run between U405 and the cap row north of U401)
rm.put('U401', 107.19, 81.14, 0)

# ---- north cap row (courtyards touch U401's top edge): C403 | R455 | C407
rm.put_court('C407', rot=180, left=105.33, bottom=78.64)      # PP5V pad (west) over pad 34, GND pad east over pad 31; pad 32 under the body gap
rm.put_court('R455', rot=0, right=105.33, bottom=78.64)       # DRV9_OFF pad just above pad 37 (its via site)
rm.put_court('C403', rot=270, right=104.54, bottom=78.64)     # 3V3 pad (east) next to corner pad 38
rm.put_court('C401', rot=0, left=108.6, bottom=78.64)         # CC1 pad above pin 28
rm.put_court('C402', rot=0, left=107.42, bottom=77.05)        # CC2 pad one row up, pin 29's track passes C407's end
rm.put_court('C450', rot=0, left=106.38, bottom=77.05)        # VBUS pad above pad 32 (track under C407's body)

# ---- west caps
pp('C404', 1, 101.88, 80.34, 0)                                # LDO_3V3 pad level with pins 1/2
pp('C405', 1, 103.2, 81.34, 0)                                 # LDO_1V5 pad level with pin 4

# ---- pull-ups under pins 16, 17 and 19 (their pads are the via sites and keep power copper off the pins); pin 18
#      (CHG_INT) gets the free slot between R403 and R441 for its via. Row 1.15 mm below the pins for the fan-out.
for r, x in (('R402', 107.6), ('R403', 108.79), ('R441', 110.1)):   # 0.9 mm slots R402|R403 and R403|R441: signal pads on both sides keep the power copper out, a via fits in each
    rm.put_court(r, rot=0, left=x - 0.395, top=83.6)     # tight under the pins: with R424 pad 2 below, a wall no power strip can pass

# ---- EEPROM south-west of the chip, signal pads east; free block x 105..107.3, y 83.8..86 for the vias of
#      SDA / SCL / IRQ_N (pins 8..10); C408 under the GND pins 11..14
rm.put_court('U402', rot=180, left=101.1, top=83.7)
pp('C408', 1, 106.2, 84.3, 0)

# ---- PPHV: pad 20 -> C449 -> strip down the east side of the chip -> shunt lying on the bottom edge, pad 1 (PPHV)
#      west under the strip, pad 2 (AC_SNS_N) east, leaving straight south. West of pad 1 the strip y 86.2..87.7 is
#      kept free: the planner takes PPHV on to the charger's VAC capacitor (C409) through it.
rm.beside('C449', 'U401.20', 'E', gap=0.15)
rm.put_court('R424', rot=180, left=107.3, top=85.05)     # pad 2 (AC_SNS_N) west over the stage's input column, pad 1 (PPHV) east under C449

# ---- connector protection. U405 a quarter turn: connector-side CC pads at its NE corner under J401, system-side CC
#      pads west (via field west of it), only GND / unused pads on the south side where the PP5V run passes
# Run p1_top_x2 tried C452 right under J401 A12 / B4 as a fence with U405 at y 73.4: the planner then took VBUS round the
# west and south of U405 as a ring and walled 9 of its pads. Do not repeat; this is the placement of run c again.
rm.put('U405', 103.8, 72.62, 90)
pp('C451', 1, 106.34, 72.9, 90)                                # VBIAS pad beside pad 3; closes the gap U405 - H104 to VBUS copper
pp('C452', 1, 101.3, 70.5, 0)                                  # LDO_3V3 pad west of pad 10
rm.put('R404', 107.75, 70.7, 90)                               # CHG_INT pull-up as a fence under A5 / B8: keeps VBUS copper off the CC1 escape
rm.put_court('C406', rot=0, left=110.7, top=70.45)             # bulk cap next to the connector: VBUS pad in the strip
rm.put_court('D401', rot=180, left=113.35, top=73.0)           # TVS on the east edge of the VBUS strip

# ---- 9 V supply: Q409 above the shunt's east end, U406 | C457 east of it, divider and output cap north of U406
rm.put_court('Q409', rot=180, left=112.8, bottom=85.6)
rm.put_court('U406', rot=0, left=116.3, bottom=85.85)          # clear of TP106
rm.put_court('C457', rot=0, right=121.5, bottom=85.85)         # PACK_P pad between U406 pad 8 and TP106
rm.put_court('R453', rot=0, left=115.85, bottom=79.47)
rm.put_court('R452', rot=0, left=117.85, bottom=79.47)
rm.put_court('C458', rot=180, left=118.0, bottom=78.35)        # output pad just above R452's output pad
rm.put_court('D411', rot=270, right=121.5, bottom=79.47)
pp('R454', 1, 114.55, 81.215, 180)                             # above Q409's drain pad (same node as U406 EN), REGN pad north with a free via spot above it; the bottom strip under Q409 / U406 stays free for AC_SNS_N
rm.done()
if '--pads' in sys.argv:
    for r in sys.argv[sys.argv.index('--pads')+1:]:
        print(r, [round(v,2) for v in rm.court(r)])
        for p in rm.b.pads(r):
            if p['num']: print('   ', p['num'], p['net'].split('/')[-1], [round(v,2) for v in p['box']])
