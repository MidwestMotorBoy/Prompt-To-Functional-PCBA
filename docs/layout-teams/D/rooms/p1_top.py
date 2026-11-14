import sys; sys.path.insert(0, '../tools')      # run from the rooms folder: cd rooms && python3 p1_top.py
from room import Room
rm = Room('p1_top')
P = rm.pad
DX, DY = 2.3, 2.45
# ================================================================ PD controller U401
# Moved east and south of the hand spot so that
#  * PP5V comes up the lane (x 99.9-101.1), turns east in a band at y ~77-78.3 and drops onto C407's PP5V pad,
#    which sits right above pad 34; under the band a pocket keeps pins 38/37 free (C403 + a via for DRV9_OFF);
#  * VBUS (strip east of H104) lands on pad 23 from the north-east;
#  * PPHV leaves pad 20 straight into R424 (vertical, east of the signal pins 15-19), AC_SNS_N leaves R424 pad 2.
rm.put('U401', 105.0924 + DX, 79.9392 + DY, 0)
UC = rm.court('U401')
p34, p38, p37 = P('U401.34'), P('U401.38'), P('U401.37')

# C407 (PP5V, 0805): PP5V pad just north-west of pad 34, GND pad east above pins 32/31; it must end west of
# pin 29 so CC2/CC1 (pins 29/28) leave straight north to C402/C401
rm.put_court('C407', rot=180, right=P('U401.29')[0] - 0.65, bottom=UC[1] - 0.1)
rm.put_court('C403', rot=270, right=rm.court('C407')[0] - 0.3, bottom=UC[1] - 0.1)
# C403 (3V3, pin 38) north-west of the pin row, 3V3 pad east; C404 (LDO_3V3, pins 1/2) and C405 (LDO_1V5, pin 4)
# in a column on the west side, LDO pad up
rm.put_court('C404', rot=0, right=UC[0] - 0.12, top=UC[1] + 0.25)
rm.put_court('C405', rot=0, right=UC[0] - 0.12, top=rm.court('C404')[3] + 0.1)

# CC capacitors above pins 29/28 east of C407 (CC pad south)
rm.beside('C402', 'U401.29', 'N', gap=0.45, rot=0)
rm.put_court('C401', rot=0, left=rm.court('C402')[2] + 0.1, bottom=rm.court('C402')[3])

# ================================================================ port protection U405 under the connector
rm.put('U405', 103.45, 73.9, 0)            # west, so the gap to H104 holds C451 and the C_CC1 track A5->pin 4 passes north of it
rm.beside('C451', 'U405.3', 'E', gap=0.12, rot=90, shift=-0.2)   # VBIAS pad north, GND pad south
rm.put_court('C452', rot=270, left=99.95, top=rm.court('U405')[1] + 2.3)   # LDO_3V3 (pin 10) cap west of U405

# ================================================================ VBUS strip east of H104, PPHV, shunt
# D401 (TVS) sits at the east VBUS pad on the strip; C406, C450 follow on the strip's east edge
rm.put_court('D401', rot=180, left=112.25, top=70.4)
rm.put_court('C406', rot=0, left=111.9, top=rm.court('D401')[3] + 0.12)
rm.put_court('C450', rot=90, left=112.3, top=rm.court('C406')[3] + 0.12)
rm.put_court('C449', rot=270, left=UC[2] + 0.1, top=P('U401.20')[1] - 0.5)   # PPHV pad facing pad 20
rm.put_court('R424', rot=90, left=UC[2] + 0.1, bottom=87.65)

# ================================================================ pull-ups under U401's south-east pins, EEPROM west of the lane
# The pull-ups (signal pad up, facing pins 16-19) form a row 1.2 mm below the pins: a band for the escape vias of
# pins 8-10 and 15-19 stays free, and the 5 A copper (AC_SNS_N to the stage, PPHV to C409) is kept south of the row.
# spread from C405 to R424 so that no 2.5 mm wide corridor passes between them
x0, x1 = rm.court('C405')[2] + 0.9, rm.court('R424')[0] - 0.12
w = rm.size('R402', rot=0)[0]; step = (x1 - x0 - w) / 3
for i, r in enumerate(('R402', 'R403', 'R404', 'R441')):
    rm.put_court(r, rot=0, left=x0 + i * step, bottom=87.65)
rm.put_court('U402', rot=90, left=96.3, top=79.6)
rm.put_court('C408', rot=90, left=rm.court('U402')[0], top=rm.court('U402')[3] + 0.15)

# ================================================================ 9 V gate-drive supply, east
rm.put_court('U406', rot=0, right=121.45, bottom=85.8)
rm.put_court('C458', rot=180, right=121.45, bottom=79.3)
rm.put_court('R452', rot=270, right=rm.court('C458')[0] - 0.12, bottom=79.3)
rm.put_court('R453', rot=0, right=rm.court('R452')[0] - 0.08, bottom=79.3)
rm.put_court('D411', rot=180, right=rm.court('C458')[0] - 0.12, bottom=rm.court('R452')[1] - 0.1)
rm.put_court('Q409', rot=270, right=rm.court('U406')[0] - 0.1, top=82.7)
rm.put_court('R455', rot=0, left=rm.court('Q409')[0] + 0.6, bottom=rm.court('Q409')[1] - 0.1)
rm.put_court('R454', rot=90, left=rm.court('Q409')[0] + 0.6, top=rm.court('Q409')[3] + 0.15)
rm.put_court('C457', rot=270, right=119.45, bottom=87.7)

rm.done()
