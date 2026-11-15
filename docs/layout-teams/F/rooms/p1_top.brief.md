# Room p1_top: Port 1 connector protection, PD controller, input shunt, 9 V supply

Room area (black boxes in the pictures): x 99.9-121.5 for y 67.8-79.3; x 95.6-121.5 for y 79.3-87.7; the corner x 113.2-121.5, y 63.9-67.8.
Fixed inside: J401 (USB-C, pads at y 69.2: VBUS at x 104.1 and 108.9, CC1 A5 at 107.75, CC2 B5 at 104.75), hole H104, J111 (a cell wire pad), TP109 (GND), TP106 (PACK_P).
Reserved lane, keep every part out: x 99.4-101.0, y 79.3-87.7 (PP5V comes up here).

## Power flow you must make work (top-layer copper, straight and wide)
1. VBUS, 5 A: J401 VBUS pads -> D401 (TVS), C406 (bulk), C450 -> U401 pad 23 (the large pad on U401's east side, upper).
2. PPHV, 5 A: U401 pad 20 (large pad, east side, lower) -> R424 pad 1. C449 sits at pad 20.
3. AC_SNS_N, 5 A: R424 pad 2 -> leaves the room through the bottom edge at about x 104-108, y 87.7. Directly below, the
   stage room puts its input capacitor column (x about 104-107.3, from y 87.9). Put R424 so pad 2 is within about 2 mm of
   that crossing point with a clear strip at least 2.5 mm wide; pad 1 as close to U401 pad 20 as that allows. On the hand
   board this path wound round the inductor and cost 0.23 W; it must be short and straight now.
   R424 is a current shunt: its two sense taps (thin tracks from the inner pad edges) run a long way down to the charger
   chip, so leave room for two vias beside R424.
4. PP5V, 1.5 A: comes from the 5 V buck in the room below, up the reserved lane, entering at (100.2, 87.7). It must reach
   U401 pad 34 (north side) and C407 on the TOP layer through a clear strip at least 1.2 mm wide. On the hand board this
   was the one open power path of the whole board (no top-layer path to pad 34). Note pad 34 sits between pad 36/37 on
   its left and VBUS pad 32 on its right, so PP5V has to arrive from the north-west of U401; C407 goes right there.
   You may shift U401 a little (keep its north side facing the connector) to make this work.
5. 9 V supply (U406, Q409, C457, C458, D411, R452-R455): compact group in the right-hand part of the room. PACK_P reaches
   U406 pad 8 and C457 through an inner-layer pour: leave room for a via within 1.5 mm of each. Its output DRV_SUP (D411
   pad 1) leaves on an inner layer to the charger far below: via room at D411. DRV9_OFF (Q409 pad 1, R455 pad 2) comes
   from U401 pad 37.

## Signals
- CC: J401 A5/B5 -> U405 (pads 4/7 are both C_CC1, 5/6 both C_CC2) -> U405 pads 12/11 -> U401 pads 28/29; C401, C402 at the
  CC lines; C451 at U405 pad 3, C452 at U405 pad 10; SBU_FLT U405 pad 9 -> U401 pad 19 (R441 pull-up).
- U401 south side: SDA 8, SCL 9, IRQ_N 10 go to the far end of the board (inner layers; leave via room below the pins);
  I2CC SDA/SCL 16/17 and CHG_INT 18 go to U402 (EEPROM), the pull-ups R402-R404 and on to the charger chip far below.
- LDO capacitors: C403 at pad 38, C404 at pads 1/2, C405 at pad 4, C408 at U402 pad 8.

## What failed here on the hand board (connections with no path)
PP5V at U401 pad 34 and C407; C_CC1 J401-U405 and U405 pad 7 to pad 4; SBU_FLT U401-U405; I2CC_SDA R402-U401; IRQ_N,
SDA, SCL leaving U401; GND at a U401 pad, at C449 and at Q409. Aim for none of these.

## Numbers to report
VBUS, PPHV, AC_SNS_N (R424 part) resistances from dc.log, whether PP5V is joined at U401, blocked connections in your room.
