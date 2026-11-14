import sys; sys.path.insert(0, '../tools')
from room import Room
rm = Room('p1_chg')

# ================= charger controller: 1.0 mm east of the hand spot (frees a 2 mm column on its west side).
#   It cannot go lower: TP113 and J301 sit right under its south edge.
UX, UY = 112.44, 110.44
rm.put('U403', UX, UY, 0)
U = rm.court('U403')

# ================= 5 V buck (west)
# output capacitors: column at the west edge, PP5V pads east toward the lane mouth (100.2, 104.6)
rm.put_court('C443', 0, left=94.0, top=102.62)
rm.put_court('C442', 0, left=94.0, top=105.03)
rm.put_court('C441', 0, left=94.0, top=107.44)
# inductor upright in box 1: PP5V pad north at the lane mouth, SW pad south
rm.put_court('L402', 90, left=101.08, top=102.40)
L = rm.court('L402')
# boot cap right under the SW pad, soft-start cap west of it
rm.beside('C440', 'L402.1', 'S', gap=-0.04, rot=0, shift=-0.9)
rm.beside('C439', 'C440', 'W', gap=0.05, rot=0)
# buck chip: SW pin 5 right under C440's SW pad
rm.beside('U404', 'C440.2', 'S', gap=0.0, rot=0, pad=5)
# first input cap (hot loop): GND pad level with pin 4, PACK_P pad below; pin 3 reaches it under pin 4.
# Free copper under pins 3/4 and C446 for the PACK_P vias (In2 pack rail).
rm.beside('C446', 'U404.4', 'E', gap=0.05, rot=0)
# EN pull-down, flat under pins 1/2 and shifted west: GND pad (W) takes pin 1, EN pad (E) takes pin 2;
# keeps the strip under pin 3 free so the PACK_P copper can reach pin 3 and C446 (hot loop)
p1 = rm.pad('U404.1')
rm.put('R432', p1[0] - 0.5, rm.court('U404')[3] + 0.05 + 0.4, 270)
# FB divider west of U404, away from L402/SW
rm.beside('R434', 'U404.8', 'W', gap=0.45, rot=0)
rm.put_court('R433', 0, right=rm.court('R434')[0] - 0.05, top=rm.court('C441')[3] + 0.03)
# bulk input cap: bottom-left, on the pack rail (vias to In2 and to the bottom bulk caps' PACK_P row at y 111.3)
rm.put_court('C444', 90, left=94.0, bottom=115.92)

# ================= input-current sense filter: NW of U403. ACN (upper pin 29) right, ACP (pin 30) left.
#   Tap resistors 1 mm below the room top: free spots above their tap pads for the inner-layer tap vias.
rm.put_court('R425', 0, left=L[2] + 0.0, top=105.62)                      # ACP tap (PPHV)
rm.put_court('R426', 0, left=rm.court('R425')[2] + 0.02, top=105.62)      # ACN tap (AC_SNS_N)
rm.beside('C414', 'U403.30', 'W', gap=0.0, rot=270)                       # ACP pad at pin 30, ACN pad above (pin 29)
rm.put_court('C416', 180, left=L[2], top=rm.court('R425')[3] + 0.03)       # GND up, ACN down next to C414's ACN pad
rm.put_court('C415', 90, left=rm.court('C440')[2] + 0.25, top=L[3] + 0.02)  # ACP pad east, GND west

# ================= VAC decoupling at pins 32/33 (pins 34/35 escape west under its pads), FSW resistor at pin 36
rm.beside('C409', 'U403.32', 'W', gap=0.0, rot=0, shift=0.25)
rm.beside('R412', 'U403.36', 'W', gap=0.0, rot=0, shift=0.12)

# ================= programming dividers under C409 (ACUV/ACOV), CE_N pair below them
X2 = rm.court('C446')[2] + 0.6
rm.put_court('R409', 180, left=X2, top=rm.court('C409')[3] + 0.06)        # PPHV (W) -> ACUV (E)
rm.put_court('R410', 0, left=X2, top=rm.court('R409')[3] + 0.15)          # ACUV (W) ... ACOV (E)
rm.put_court('R411', 0, left=X2, top=rm.court('R410')[3] + 0.15)          # GND (W) ... ACOV (E)
rm.put_court('R435', 0, left=rm.court('R432')[2] + 0.1, top=rm.court('C446')[3] + 0.75)   # CHG_INH -> CE_N
rm.put_court('R417', 0, left=rm.court('R432')[2] + 0.1, top=rm.court('R435')[3] + 0.05)   # 3V3 pull-up on CE_N

# ================= north strip: REGN / DRV_SUP
# C411 lies across the left gate-drive pins: HIDRV1/BTST1 pass under its body between the pads
rm.put('C411', 110.94, 104.62 + 1.025, 90)
rm.put_court('C410', 90, left=rm.court('C411')[2] + 0.01, bottom=U[1] - 0.02)    # REGN pad south, near pin 24
rm.put_court('D410', 90, left=rm.court('C410')[2] + 0.05, top=104.62)             # flat, top of the strip

# ================= east: battery sense filter and FB divider
rm.put_court('R428', 0, left=U[2] + 0.02, top=107.35)                     # BAT tap: free strip above it to R427
rm.put_court('C417', 0, left=U[2] + 0.02, top=rm.court('R428')[3] + 0.03)
rm.put_court('R419', 0, left=U[2] + 0.02, top=rm.court('C417')[3] + 0.03)
# under J113: two rows; PACK_P pads of R429 and R418 face a via spot between them
rm.put_court('R429', 0, left=rm.court('C417')[2] + 0.05, top=110.64)      # SRN (W) ... PACK_P (E)
rm.put_court('R418', 90, right=121.45, top=110.64)                        # PACK_P (W) ... FB (E)
rm.put_court('C418', 90, left=rm.court('C417')[2] + 0.05, top=rm.court('R429')[3] + 0.05)   # SRP / GND
rm.put_court('C419', 90, left=rm.court('C418')[2] + 0.3, top=rm.court('R429')[3] + 0.05)    # SRN / GND

# ================= south: ICHG / ILIM low at the bottom edge (via row for I2C, CE_N, TS above them)
rm.put_court('R414', 90, right=114.38, bottom=115.52)
rm.put_court('R413', 90, right=rm.court('R414')[0] - 0.05, bottom=115.52)

# ================= TS divider: bottom-left above C444 (TS goes up to TH401 on an inner layer anyway)
rm.put_court('R415', 0, left=94.05, top=rm.court('C441')[3] + 0.05)
rm.put_court('R416', 90, left=rm.court('R415')[2] + 0.05, top=rm.court('C441')[3] + 0.05)

rm.done()
