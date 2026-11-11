# Design review packet

215 parts, 124 nets. Everything below is generated from the build; nothing here is a judgement.

## 1. What the gate did not check

Parts with no limits file (their pins were not checked against anything):

- none

Limits files that are waivers (declared not to need limits, or open):

- TC2030: bare pads for a pogo-pin cable, no part fitted; pin names are the KiCad symbol's, no electrical limits
- USB_C_Receptacle: standard connector; pin functions are the USB Type-C names in the KiCad symbol; only the voltage rating is used

Nets with no declared voltage (2); ratings on them are unchecked:

`USB Port 1/PD_DRAIN`, `USB Port 2/PD_DRAIN`

Connected IC pins with no absolute-maximum row in their limits file:

- Q401 (SiZ240DT): G1
- Q402 (SiZ240DT): G1
- Q501 (SiZ240DT): G1
- Q502 (SiZ240DT): G1
- U204 (TPS62177): EN, SW
- U301 (CC2340R5MODA): ANT_IN, RFIO
- U401 (TPS25751D): PPHV
- U403 (BQ25756): BTST1, BTST2, DRV_SUP, HIDRV1, HIDRV2, LODRV1, LODRV2
- U404 (TPS62933): BST
- U501 (TPS25751D): PPHV
- U503 (BQ25756): BTST1, BTST2, DRV_SUP, HIDRV1, HIDRV2, LODRV1, LODRV2
- U504 (TPS62933): BST

## 2. Thinnest voltage margins (20 lowest)

| Pin | Net | Net voltage, V | Limit, V | Kind | Source | Margin |
|---|---|---|---|---|---|---|
| J401.VBUS | USB Port 1/VBUS | 25.2 | 20 | recommended | p.1 | -26 % |
| J501.VBUS | USB Port 2/VBUS | 25.2 | 20 | recommended | p.1 | -26 % |
| U401.VBUS | USB Port 1/VBUS | 25.2 | 22 | recommended | p.8 | -15 % |
| U501.VBUS | USB Port 2/VBUS | 25.2 | 22 | recommended | p.8 | -15 % |
| U301.VDDS | 3V3 | 3.6 | 3.8 | recommended | p.12 | 5 % |
| U401.VBUS | USB Port 1/VBUS | 26.5 | 28 | abs max | p.7 | 5 % |
| U401.VBUS_IN | USB Port 1/VBUS | 26.5 | 28 | abs max | p.7 | 5 % |
| U405.C_CC1 | USB Port 1/C_CC1 | 26.5 | 28 | abs max | p.5 | 5 % |
| U405.C_CC2 | USB Port 1/C_CC2 | 26.5 | 28 | abs max | p.5 | 5 % |
| U405.RPD_G1 | USB Port 1/C_CC1 | 26.5 | 28 | abs max | p.5 | 5 % |
| U405.RPD_G2 | USB Port 1/C_CC2 | 26.5 | 28 | abs max | p.5 | 5 % |
| U405.VBIAS | USB Port 1/VBIAS | 26.5 | 28 | abs max | p.5 | 5 % |
| U501.VBUS | USB Port 2/VBUS | 26.5 | 28 | abs max | p.7 | 5 % |
| U501.VBUS_IN | USB Port 2/VBUS | 26.5 | 28 | abs max | p.7 | 5 % |
| U505.C_CC1 | USB Port 2/C_CC1 | 26.5 | 28 | abs max | p.5 | 5 % |
| U505.C_CC2 | USB Port 2/C_CC2 | 26.5 | 28 | abs max | p.5 | 5 % |
| U505.RPD_G1 | USB Port 2/C_CC1 | 26.5 | 28 | abs max | p.5 | 5 % |
| U505.RPD_G2 | USB Port 2/C_CC2 | 26.5 | 28 | abs max | p.5 | 5 % |
| U505.VBIAS | USB Port 2/VBIAS | 26.5 | 28 | abs max | p.5 | 5 % |
| U401.PP5V | USB Port 1/PP5V | 5.5 | 6 | abs max | p.7 | 8 % |

Capacitors with the least voltage headroom (10 lowest; ceramic capacitance also falls with DC bias):

| Part | Value | Sees, V | Headroom |
|---|---|---|---|
| C420 | 22u 35V | 26.5 | 24 % |
| C421 | 68u 35V | 26.5 | 24 % |
| C423 | 22u 35V | 26.5 | 24 % |
| C424 | 22u 35V | 26.5 | 24 % |
| C427 | 22u 35V | 26.5 | 24 % |
| C456 | 68u 35V | 26.5 | 24 % |
| C520 | 22u 35V | 26.5 | 24 % |
| C521 | 68u 35V | 26.5 | 24 % |
| C523 | 22u 35V | 26.5 | 24 % |
| C524 | 22u 35V | 26.5 | 24 % |

## 3. Set points the design declares

| Name | Formula | Parts and constants | Target | Tolerance |
|---|---|---|---|---|
| USB Port 1/PP5V | `VREF * (1 + Rtop / Rbot)` | Rbot=R434 (22k), Rtop=R433 (120k), VREF=TPS62933.VREF | 5.15 V | 0.03 |
| USB Port 1/battery regulation | `VFB * (1 + Rtop / (Rbot + RFBG))` | RFBG=BQ25756.RFBG, Rbot=R419 (10.0k 0.1%), Rtop=R418 (100k 0.1%), VFB=BQ25756.VFB_NOM | 16.8 V | 0.01 |
| USB Port 1/charge current limit | `K * 0.005 / Rsns / (Rset / 1e3)` | K=BQ25756.KICHG, Rset=R413 (11.8k 1%), Rsns=R427 (5m 1W (RBAT)) | 4.2 A | 0.05 |
| USB Port 1/gate-drive supply | `VREF * (1 + Rtop / Rbot)` | Rbot=R453 (5.6k 1%), Rtop=R452 (40.2k 1%), VREF=TPS7A4101.VREF | 9.6 V | 0.03 |
| USB Port 1/input current limit | `K * 0.002 / Rsns / (Rset / 1e3)` | K=BQ25756.KILIM, Rset=R414 (3.6k 1%), Rsns=R424 (5m 0.5W) | 5.5 A | 0.05 |
| USB Port 1/input overvoltage | `VREF * (R1 + R2 + R3) / R3` | R1=R409 (162k 1%), R2=R410 (49.9k 1%), R3=R411 (10k 1%), VREF=BQ25756.VREF_ACOV | 26.5 V | 0.04 |
| USB Port 1/input undervoltage | `VREF * (R1 + R2 + R3) / (R2 + R3)` | R1=R409 (162k 1%), R2=R410 (49.9k 1%), R3=R411 (10k 1%), VREF=BQ25756.VREF_ACUV | 4.1 V | 0.05 |
| USB Port 1/switching frequency | `(1 / Rset + 5e-6) / 5e-11 / 1e3` | Rset=R412 (49.9k 1%) | 500 kHz | 0.05 |
| USB Port 2/PP5V | `VREF * (1 + Rtop / Rbot)` | Rbot=R534 (22k), Rtop=R533 (120k), VREF=TPS62933.VREF | 5.15 V | 0.03 |
| USB Port 2/battery regulation | `VFB * (1 + Rtop / (Rbot + RFBG))` | RFBG=BQ25756.RFBG, Rbot=R519 (10.0k 0.1%), Rtop=R518 (100k 0.1%), VFB=BQ25756.VFB_NOM | 16.8 V | 0.01 |
| USB Port 2/charge current limit | `K * 0.005 / Rsns / (Rset / 1e3)` | K=BQ25756.KICHG, Rset=R513 (11.8k 1%), Rsns=R527 (5m 1W (RBAT)) | 4.2 A | 0.05 |
| USB Port 2/gate-drive supply | `VREF * (1 + Rtop / Rbot)` | Rbot=R553 (5.6k 1%), Rtop=R552 (40.2k 1%), VREF=TPS7A4101.VREF | 9.6 V | 0.03 |
| USB Port 2/input current limit | `K * 0.002 / Rsns / (Rset / 1e3)` | K=BQ25756.KILIM, Rset=R514 (3.6k 1%), Rsns=R524 (5m 0.5W) | 5.5 A | 0.05 |
| USB Port 2/input overvoltage | `VREF * (R1 + R2 + R3) / R3` | R1=R509 (162k 1%), R2=R510 (49.9k 1%), R3=R511 (10k 1%), VREF=BQ25756.VREF_ACOV | 26.5 V | 0.04 |
| USB Port 2/input undervoltage | `VREF * (R1 + R2 + R3) / (R2 + R3)` | R1=R509 (162k 1%), R2=R510 (49.9k 1%), R3=R511 (10k 1%), VREF=BQ25756.VREF_ACUV | 4.1 V | 0.05 |
| USB Port 2/switching frequency | `(1 / Rset + 5e-6) / 5e-11 / 1e3` | Rset=R512 (49.9k 1%) | 500 kHz | 0.05 |

A set point that is not in this table is not checked by anything.

## 4. Gate findings waived in the design code

- none

## 5. Questions the reviewer answers, with a datasheet page for each answer

Answer each for every IC and protection part, starting with the parts in sections 1 and 2.

1. Does any table other than absolute maximum and recommended conditions limit a pin here? Look for tested tolerance, hot-plug, short-circuit, surge and ESD rows, and for footnotes under the tables.
2. Does a fault put more on a pin than the declared net voltage: a neighbouring pin shorted in a connector, a clamp's let-through voltage, an inductive kick, a reversed or hot-plugged input?
3. For each set point in section 3: is the formula the datasheet's, with every internal resistance and offset, and does the worst case over part tolerance stay inside what the load can take?
4. Which behaviour is set by firmware or a configuration memory and not by parts? What does the circuit do with that memory blank or wrong?
5. When one set point moves, which others move with it because they share a divider or a pin?
6. Is every part still sensible in its normal running state, not only safe at the maximum: capacitor bias, regulator dropout, minimum load, start-up order, enable pins and their defaults?
7. Is anything that the application notes require missing: a capacitor value range, a pull resistor, a required diode, a layout-critical part?
8. Does each declared net voltage in the code match what the circuit can really produce?

Write findings to `findings.json` (see `review_check.py`). A finding without a datasheet page and quote is an opinion and is rejected by the check.
