"""Room p2_chg: Port 2 charger controller U503, its filters/programming, and the 9 V gate-drive supply.
Run from the rooms folder:  cd rooms && python3 p2_chg.py > /tmp/p2_chg.log
U503 sits 0.8 mm west / 0.6 mm south of the hand position so that the east side has room for two columns of
sense-filter parts and the north strip holds D510 + C510 with via room above them."""
import sys; sys.path.insert(0, '../tools')
from room import Room
rm = Room('p2_chg')

# ---- controller ------------------------------------------------------------------------------------------------
UX, UY = 87.6, 111.1
rm.put('U503', UX, UY, 0)            # N pins y 108.7 (x 85.35..89.85), S pins y 113.5, W pins x 84.7, E pins x 90.5

# ---- north strip: only the REGN / DRV_SUP parts, in the middle column above pins 24/23/22 ----------------------
# left group (SW1 HIDRV1 BTST1 LODRV1) passes west of x 86.45, right group (LODRV2 BTST2 HIDRV2, SW2) east of x 89.05
rm.put('D510', 87.90, 107.15, 270)   # W pad REGN above pin 24, E pad DRV_SUP above pin 23/22
rm.put('C510', 87.68, 105.86, 180)   # W pad REGN straight above D510's REGN pad, E pad GND; vias at y 105.05
rm.put('C511', 92.40, 106.40, 0)     # DRV_SUP reservoir, NE: S pad DRV_SUP (via west of it), N pad GND; SW2 + right group pass west of x 91

# ---- west side: column A at x 83.05 (0.48 mm channel-side gap to U503), rows to its west -------------------------
AX = 83.05
rm.put('R526', AX, 107.17, 0)        # N = AC_SNS_N tap (via north of it), S = ACN_F
rm.put('C514', AX, 109.10, 270)      # N = ACN_F, S = ACP_F (pins 29/30 come up the channel)
rm.put('R509', AX, 111.60, 270)      # N = PPHV at pins 32/33, S = ACUV at pin 34
rm.put('R510', AX, 113.60, 90)       # N = ACUV, S = ACOV (pin 35 down the channel)
rm.put('R511', AX, 115.58, 270)      # N = ACOV, S = GND
rm.put('R512', 84.20, 114.95, 270)   # N = FSW (pin 36 down the channel), S = GND
BX = 81.53
rm.put('C516', BX, 108.10, 180)      # E = ACN_F next to C514 N pad, W = GND
rm.put('C515', BX, 109.10, 0)        # E = ACP_F next to C514 S pad, W = GND
rm.put('R525', 81.50, 110.10, 270)   # E = ACP_F under C515's pad, W = PPHV sense tap (via west of it)
rm.put('C509', 80.95, 111.40, 0)     # E = PPHV next to R509 N pad, W = GND

# ---- east side: column A x 92.05, column B x 93.1 ---------------------------------------------------------------
EA, EB = 92.05, 93.10
rm.put('C518', EA, 109.67, 0)        # N = GND (via shared with C511), S = SRP_F
rm.put('C517', EA, 111.60, 0)        # N = SRP_F at pin 14, S = SRN_F at pin 13
rm.put('R529', EA, 113.55, 90)       # N = SRN_F, S = PACK_P
rm.put('R528', EB, 110.11, 270)      # N = BAT_SNS_P tap (via north of it), S = SRP_F
rm.put('C519', EB, 112.10, 0)        # N = SRN_F, S = GND
rm.put('R518', EB, 114.60, 0)        # N = PACK_P (beside R529's PACK_P pad), S = FB

# ---- south side, row a (straight under the pins) ----------------------------------------------------------------
rm.put('R517', 87.10, 115.30, 270)   # N = CE_N, S = 3V3
rm.put('R535', 87.90, 115.30, 270)   # N = CE_N (pin 7), S = CHG_INH
rm.put('R513', 89.35, 115.53, 0)     # N = ICHG under pin 9
rm.put('R514', 90.40, 115.53, 0)     # N = ILIM (pin 10)
rm.put('R519', 91.75, 115.53, 0)     # N = FB (beside R518's FB pad), S = FBG
# row b: thermistor divider with a via spot between the two TS pads
rm.put('R515', 86.85, 117.10, 0)     # W = REGN, E = TS
rm.put('R516', 89.50, 117.10, 270)   # W = TS, E = GND          (TS via at 88.15, 117.1)

# ---- 9 V gate-drive supply along the bottom ---------------------------------------------------------------------
rm.put('Q509', 80.30, 115.53, 0)     # gate NE, GND NW, drain S -> U506 EN straight below
rm.put('R554', 82.85, 117.10, 270)   # W = Q509 drain / EN, E = REGN
rm.put('U506', 83.37, 119.40, 90)    # W pins: EN (upper), IN (lower); E pins: GND, nc, FB, OUT (lower)
rm.put('C557', 79.38, 119.60, 0)     # S = PACK_P level with IN, N = GND
rm.put('C558', 87.63, 119.40, 180)   # S = OUT at pin 1, N = GND at pin 4; FB passes between its pads
rm.put('R552', 89.20, 119.92, 90)    # N = FB, S = OUT
rm.put('R553', 89.68, 118.35, 180)   # W = FB, E = GND
rm.put('D511', 91.40, 119.90, 270)   # S = anode (OUT), N = DRV_SUP facing U503

# ---- via spots reserved for nets that leave the room or go to a plane (checked against every pad, both sides) ----
VIAS = [('REGN', 87.20, 105.05, 'C510/D510/U503.24 -> R515, R554'), ('GND', 88.05, 105.05, 'C510'), ('DRV_SUP', 88.90, 105.05, 'D510/U503.23 -> C511, boot diodes'),
        ('DRV_SUP', 91.25, 107.35, 'C511'), ('GND', 91.25, 105.45, 'C511'),
        ('AC_SNS_N', 83.05, 105.80, 'R526.1 tap'), ('GND', 80.30, 108.10, 'C516'), ('GND', 80.30, 109.10, 'C515'), ('PPHV', 80.20, 110.10, 'R525.1 tap'), ('PPHV', 81.90, 112.70, 'C509.1/R509.1 feed'),
        ('GND', 79.20, 111.40, 'C509'), ('DRV9_OFF', 81.25, 113.30, 'Q509.1'), ('GND', 79.35, 113.15, 'Q509.2'), ('GND', 82.20, 116.15, 'R511'),
        ('GND', 84.20, 116.05, 'R512'), ('I2CC_SCL', 85.00, 114.70, 'U503.1'), ('I2CC_SDA', 85.70, 115.35, 'U503.2'), ('CHG_INT', 86.35, 114.75, 'U503.3'),
        ('3V3', 87.10, 116.20, 'R517.2'), ('CHG_INH', 87.90, 116.20, 'R535.1'), ('TS', 88.15, 117.10, 'R515.2/R516.1 -> TH501'), ('REGN', 84.00, 117.10, 'R554.2, R515.1'),
        ('GND', 90.75, 117.10, 'R513/R514/R516'), ('GND', 92.05, 108.45, 'C518'), ('BAT_SNS_P', 93.10, 108.75, 'R528.1 tap'), ('GND', 93.10, 113.34, 'C519'),
        ('PACK_P', 92.575, 114.07, 'R529.1 + R518.1 (touches both pads)'), ('GND', 79.20, 117.80, 'C557'), ('PACK_P', 80.17, 120.40, 'U506.8 + C557.1'),
        ('GND', 90.16, 117.73, 'R553/R516'), ('DRV_SUP', 91.40, 118.25, 'D511.1'), ('SW2', 91.05, 108.60, 'U503.18 (if not routed on top)')]
def check_vias(r=0.225, need=0.2):
    b = rm.b; bad = 0
    pads = [p for ref in b.fp for p in b.pads(ref)]
    for i, (net, x, y, why) in enumerate(VIAS):
        worst = (9, '')
        for p in pads:
            if not p['net'] or p['net'].split('/')[-1] == net: continue
            B = p['box']; dx = max(B[0]-x, 0, x-B[2]); dy = max(B[1]-y, 0, y-B[3]); d = (dx*dx+dy*dy)**.5 - r
            if d < worst[0]: worst = (d, p['ref']+'.'+p['num'])
        for (n2, x2, y2, w2) in VIAS[i+1:]:
            d = ((x-x2)**2+(y-y2)**2)**.5 - 2*r
            if n2 != net and d < worst[0]: worst = (d, 'via '+n2)
        flag = '' if worst[0] >= need else '   <-- TOO CLOSE'; bad += worst[0] < need
        print(f'   via {net:9s} ({x:6.2f},{y:6.2f}) clearance {worst[0]:.2f} to {worst[1]:10s} {why}{flag}')
    print('via spots too close:', bad)
rm.done()
check_vias()
