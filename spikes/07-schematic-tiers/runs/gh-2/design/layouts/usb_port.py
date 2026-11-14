"""One USB-C PD port: connector and protection, the TPS25751D PD controller, the BQ25756 charger with its sense and
programming parts, the four-switch power stage, the 9 V gate-drive supply and the 5 V buck. Used for both ports."""
import symlib

PD = ("MonolithDev", "TPS25751D")
ESD = ("MonolithDev", "TPD6S300")
EE = ("Memory_EEPROM", "24LC512")
sn = lambda v: round(v / 1.27) * 1.27


def draw(h, n):
    port = 1 if n == 400 else 2
    R = lambda p, k: f"{p}{n + k}"
    h.text(20.32, 21, f"USB Port {port}", 3.0)
    with h.group("USB-C connector, port protection and PD controller"):
        front(h, R, port)
    with h.group("Sheet interface"):
        h.note(345, 48, ["Nets that leave this sheet:", "",
                         "PACK_P: pack rail, charger", "   output and buck input",
                         "3V3: always-on supply", "   for the PD controller",
                         f"P{port}_LDO_3V3: the PD controller's", "   own 3.3 V LDO",
                         "SCL, SDA, IRQ_N: I2C target", "   side to the MCU",
                         "CHG_INH: high stops charging", f"EN_5V{port}: MCU enables the 5 V buck",
                         "", "Power flow:", "VBUS -> U401 -> PPHV -> RAC ->", "four-switch stage -> RBAT ->", "PACK_P"], 1.27)
    with h.group("Four-switch buck-boost power stage: PPHV to the pack rail"):
        stage(h, R, 20.32, 220.0)
    with h.group("BQ25756 charge controller: current sense, input window, programming"):
        charger(h, R, 110.0, 386.0)
    with h.group("9 V gate-drive supply"):
        ldo9(h, R, 226.0, 337.0)
    with h.group("5 V buck for PP5V"):
        buck5(h, R, 240.0, 413.0)


def front(h, R, port):
    ldo = f"P{port}_LDO_3V3"
    yv = 58.42                                                  # the VBUS rail
    # ---------------------------------------------------------------- connector
    j = h.ic(R("J", 1), 45.72, 104.14, fields="above")
    jp = j.p
    vb = jp("A4")
    xv = vb[0] + 2.54
    h.w(vb, (xv, vb[1]), (xv, yv), (sn(xv + 96.52), yv))
    # D+ and D- tied together: dedicated charging port, no data
    h.w(jp("A7"), jp("B7"), jp("A6"), jp("B6"))
    h.w(jp("B7"), (jp("B7")[0] + 5.08, jp("B7")[1])); h.lab(jp("B7")[0] + 5.08, jp("B7")[1], "DPDN_DCP", "R")
    h.w(jp("A1"), jp("SH")); h.gnd(jp("A1")[0], jp("A1")[1])

    h.note(28, 40, ["USB-C receptacle J401: D+ and D- tied together (dedicated charging port, no data).",
                    "CC lines run through the TPD6S300 protector U405 to the TPS25751D PD controller U401."], 1.27)
    # ---------------------------------------------------------------- VBUS bypass and surge protection on the rail
    d = h.ic(R("D", 1), sn(xv + 17.78), yv + 7.62, fields="right")
    h.w((d.x, yv), d.p("IN"))
    h.gnd(*d.p("GND"))
    h.hang(yv, sn(xv + 38.1), R("C", 6), f"VBUS")
    h.hang(yv, sn(xv + 53.34), R("C", 50), f"VBUS")
    # ---------------------------------------------------------------- port protection
    symlib.respace(*ESD, {"RPD_G1": 16.51, "RPD_G2": 3.81, "C_SBU1": -5.08, "C_SBU2": -10.16, "D1": -15.24, "D2": -20.32, "SBU1": -5.08, "SBU2": -10.16, "~{FLT}": -13.97})
    u5 = h.ic(R("U", 5), 105.41, 105.41, fields="below")
    h.w(jp("CC1"), u5.p("C_CC1")); h.w(jp("CC2"), u5.p("C_CC2"))
    # the dead-battery Rd pins sit just outside the CC pair and join their CC line directly
    for pin, cc in (("RPD_G1", "C_CC1"), ("RPD_G2", "C_CC2")):
        pr, pc = u5.p(pin), u5.p(cc)
        xj = sn(pr[0] - 5.08)
        h.w(pr, (xj, pr[1]), (xj, pc[1]))
    h.w(u5.p("GND"), u5.p("N.C.")); h.gnd(u5.p("GND")[0], u5.p("GND")[1])
    vp = u5.p("VPWR"); vi = u5.p("VBIAS")
    h.w(vp, (vp[0] - 5.08, vp[1])); h.lab(vp[0] - 5.08, vp[1], ldo, "L")
    h.hang(vp[1], vp[0], R("C", 52), ldo, up=True, txt="l")
    h.w(vi, (vi[0] + 5.08, vi[1])); h.hang(vi[1], vi[0] + 5.08, R("C", 51), "VBIAS", up=True, txt="r")
    # ---------------------------------------------------------------- PD controller
    symlib.respace(*PD, {"VIN_3V3": 55.88, "VBUS_IN": 50.8, "VBUS": 48.26, "CC1": 33.02, "CC2": 17.78,
                         "GPIO0": 5.08, "GPIO1": 2.54, "GPIO2": 0, "GPIO3": -10.16, "GPIO4": -20.32, "GPIO5": -22.86,
                         "GPIO6": -33.02, "GPIO7": -43.18, "GPIO11": -45.72,
                         "PPHV": 63.5, "PP5V": 50.8, "DRAIN": 43.18, "DRAIN_EP": 40.64, "LDO_1V5": 30.48, "LDO_3V3": 12.7,
                         "ADCIN1": -5.08, "ADCIN2": -7.62, "I2Cc_SCL": -25.4, "I2Cc_SDA": -38.1, "~{I2Cc_IRQ}": -50.8,
                         "I2Ct_SCL": -58.42, "I2Ct_SDA": -63.5, "~{I2Ct_IRQ}": -68.58})
    u1 = h.ic(R("U", 1), 175.26, 109.22, fields="above")
    P = u1.p
    xp = P("VBUS_IN")[0]
    h.w(P("VBUS"), (xp - 2.54, P("VBUS")[1]), (xp - 2.54, P("VBUS_IN")[1]))
    h.w((sn(xv + 96.52), yv), (xp - 2.54, yv)); h.w((xp - 2.54, yv), P("VBUS_IN"))
    # CC lines from the protector, fanned out to the controller's pins
    for pin, a, xe in (("CC1", "CC1", 129.54), ("CC2", "CC2", 134.62)):
        pa, pb = u5.p(a), P(pin)
        h.w(pa, (xe, pa[1]), (xe, pb[1]), pb)
    h.hang(P("CC1")[1], sn(xp - 17.78), R("C", 1), "CC1")
    h.hang(P("CC2")[1], sn(xp - 17.78), R("C", 2), "CC2")
    # 3.3 V in
    pv = P("VIN_3V3")
    h.w(pv, (xp - 12.7, pv[1])); h.lab(xp - 12.7, pv[1], "3V3", "L")
    h.hang(pv[1], sn(xp - 7.62), R("C", 3), "3V3", up=True, txt="l")
    # unused GPIO to ground, bussed
    for a, b in (("GPIO0", "GPIO2"), ("GPIO4", "GPIO5"), ("GPIO7", "GPIO11")):
        pa, pb = P(a), P(b)
        h.w(pa, (pa[0] - 2.54, pa[1]), (pb[0] - 2.54, pb[1]), pb)
        h.gnd(pb[0] - 2.54, pb[1])
    h.w(P("GPIO1"), (P("GPIO1")[0] - 2.54, P("GPIO1")[1]))
    # SBU_FLT and the drive-off line
    pf = P("GPIO3"); h.w(u5.p("~{FLT}"), pf)
    h.hang(pf[1], sn(xp - 15.24), R("R", 41), "SBU_FLT", up=True, txt="r")
    pg = P("GPIO6"); h.w(pg, (xp - 20.32, pg[1])); h.lab(xp - 20.32, pg[1], "DRV9_OFF", "L")
    h.hang(pg[1], sn(xp - 15.24), R("R", 55), "DRV9_OFF", up=True, txt="r")
    h.tie(P("GND"), "GND", "D")
    # ---- right side of the controller
    xr = P("PPHV")[0]
    h.w(P("PPHV"), (xr + 25.4, P("PPHV")[1])); h.lab(xr + 25.4, P("PPHV")[1], "PPHV", "R")
    h.hang(P("PPHV")[1], sn(xr + 10.16), R("C", 49), "PPHV", up=True)
    h.w(P("PP5V"), (xr + 25.4, P("PP5V")[1])); h.lab(xr + 25.4, P("PP5V")[1], "PP5V", "R")
    h.hang(P("PP5V")[1], sn(xr + 10.16), R("C", 7), "PP5V")
    h.w(P("DRAIN"), (xr + 2.54, P("DRAIN")[1]), (xr + 2.54, P("DRAIN_EP")[1]), P("DRAIN_EP"))
    h.w(P("LDO_1V5"), (xr + 12.7, P("LDO_1V5")[1]))
    h.hang(P("LDO_1V5")[1], sn(xr + 7.62), R("C", 5), "LDO_1V5")
    y3 = P("LDO_3V3")[1]
    h.w(P("LDO_3V3"), (xr + 25.4, y3)); h.lab(xr + 25.4, y3, ldo, "R")
    h.hang(y3, sn(xr + 10.16), R("C", 4), ldo)
    h.tie(P("ADCIN1"), u1.net("ADCIN1"), "R", 5.08)
    h.tie(P("ADCIN2"), "GND", "R", 2.54)
    # I2C to the charger and the EEPROM, pulled up to the controller's own 3.3 V
    symlib.respace(*EE, {"SCL": 6.35, "SDA": -6.35, "WP": -12.7, "A0": 2.54, "A1": 0, "A2": -2.54})
    ee = h.ic(R("U", 2), sn(xr + 63.5), P("I2Cc_SCL")[1] + 6.35, mirror=True, fields="above", lift=5.0)
    for pin, x in (("I2Cc_SCL", 10.16), ("I2Cc_SDA", 22.86), ("~{I2Cc_IRQ}", 10.16)):
        pa = P(pin)
        if pin != "~{I2Cc_IRQ}":
            pe = ee.p("SCL" if pin == "I2Cc_SCL" else "SDA")
            h.w(pa, pe)
            xt = pe[0] - 7.62
            h.w((xt, pa[1]), (xt, pa[1] + 5.08)); h.lab(xt, pa[1] + 5.08, u1.net(pin), "L")
        else:
            h.w(pa, (xr + 35.56, pa[1])); h.lab(xr + 35.56, pa[1], "CHG_INT", "R")
        rr = {"I2Cc_SCL": R("R", 3), "I2Cc_SDA": R("R", 2), "~{I2Cc_IRQ}": R("R", 4)}[pin]
        r = h.two(rr, sn(xr + x), pa[1] - 3.81, "v", first=ldo, txt="r")
        h.w(r.b, (r.b[0], pa[1])); h.w(r.a, (r.a[0], r.a[1] - 2.54)); h.lab(r.a[0], r.a[1] - 2.54, ldo, "R")
    for pin, net in (("I2Ct_SCL", "SCL"), ("I2Ct_SDA", "SDA"), ("~{I2Ct_IRQ}", "IRQ_N")):
        h.stub(P(pin), "R", net, 5.08)
    h.tie(ee.p("WP"), "GND", "L", 2.54)
    a0, a2 = ee.p("A0"), ee.p("A2")
    h.w(a0, (a0[0] + 2.54, a0[1]), (a2[0] + 2.54, a2[1]), a2); h.w(ee.p("A1"), (a0[0] + 2.54, ee.p("A1")[1]))
    h.gnd(a2[0] + 2.54, a2[1])
    h.tie(ee.p("GND"), "GND", "D", 2.54)
    vcc = ee.p("VCC")
    yr = vcc[1] - 5.08
    h.w(vcc, (vcc[0], yr), (vcc[0] + 17.78, yr)); h.lab(vcc[0] + 17.78, yr, ldo, "R")
    h.hang(yr, vcc[0] + 17.78, R("C", 8), ldo)
    h.note(sn(vcc[0] - 30), ee.p("GND")[1] + 14, ["U402: configuration EEPROM for the PD controller; I2C pull-ups go to its own 3.3 V LDO."], 1.27)


def stage(h, R, x0, y0):
    """The power path as one rail, left to right: sense resistor and input caps, input half bridge, inductor, output half
    bridge, output caps, battery sense resistor. Gate drive and bootstrap come in on labels from the controller."""
    symlib.widen("MonolithDev", "SiZ240DT", 2.54)
    yr = sn(y0)
    xl = sn(x0 + 10)
    h.lab(xl, yr, "PPHV", "L")
    r24 = h.two(R("R", 24), sn(xl + 15.24), yr, "h", first="PPHV", txt="a")
    h.w((xl, yr), r24.a)
    ins = [R("C", k) for k in (30, 20, 23, 24, 27, 21, 56)]
    xs = [sn(r24.b[0] + 10.16 + 13.97 * i) for i in range(len(ins))]
    xq = sn(xs[-1] + 30.48)
    xdv = sn(xq + 11.43)
    h.w(r24.b, (xdv, yr))
    for c, xc in zip(ins, xs): h.hang(yr, xc, c, "AC_SNS_N")
    xa = sn(xs[0] - 5.08)
    h.w((xa, yr), (xa, yr - 3.81)); h.lab(xa, yr - 3.81, "AC_SNS_N", "R")
    h.note(xl, yr - 14, ["Four-switch buck-boost stage between PPHV (from the PD controller) and the pack rail: the BQ25756 drives the two half bridges",
                         "through the HIDRV/LODRV and BTST/SW labels and picks buck, boost or buck-boost. AC_SNS_N is the input rail after the RAC sense resistor."], 1.27)
    # ---- input half bridge: high side above, low side below, switch node on the right
    ya = sn(yr + 25.4); yb = sn(ya + 17.78)
    qa = h.ic(R("Q", 1), xq, ya, unit=1, fields="above")
    qb = h.ic(R("Q", 1), xq, yb, unit=2, fields="above")
    d1, sw1, s2 = qa.p("D1"), qa.p("SW"), qb.p("S2")
    h.w(d1, (xdv, d1[1]), (xdv, yr))
    xsw = sn(xq + 13.97)
    ysw = sn((sw1[1] + qb.p("SW")[1]) / 2)
    h.w(sw1, (xsw, sw1[1]), (xsw, ysw)); h.w(qb.p("SW"), (xsw, qb.p("SW")[1]), (xsw, ysw))
    h.w(s2, (xdv, s2[1])); h.gnd(xdv, s2[1], "D")
    for q, pin, rk in ((qa, "G1", 44), (qb, "G2", 45)):
        h.lane(q.p(pin), "L", [R("R", rk)], q.net(pin), gap=5.08, end="label")
    # ---- bootstrap: capacitor from the switch node, diode from DRV_SUP, both standing on the switch node
    def boot(xsw_, side, ck, dk, btst):
        s_ = 1 if side == "R" else -1
        xc = sn(xsw_ + s_ * 7.62)
        t = h.hang(ysw, xc, R("C", ck), "SW1" if side == "R" else "SW2", up=True, other="none", txt="r" if side == "R" else "l")
        yt = t.a[1]
        dd = h.two(R("D", dk), xc, sn(yt - 6.35), "v", first="DRV_SUP", txt="r" if side == "R" else "l")
        h.w((xc, yt), dd.b)
        h.w((xc, yt), (xc + s_ * 5.08, yt)); h.lab(xc + s_ * 5.08, yt, btst, side)
        h.w(dd.a, (xc, dd.a[1] - 2.54)); h.lab(xc, dd.a[1] - 2.54, "DRV_SUP", side)
        return xc
    xc1 = boot(xsw, "R", 12, 4, "BTST1")
    h.w((xsw + 3.81, ysw), (xsw + 3.81, ysw + 3.81)); h.lab(xsw + 3.81, ysw + 3.81, "SW1", "R")
    # ---- inductor and the output half bridge, mirrored
    xsw2 = sn(xsw + 66.04)
    xi = sn((xsw + xsw2) / 2)
    l = h.two(R("L", 1), xi, ysw, "h", first="SW1", txt="a")
    h.w((xsw, ysw), l.a); h.w(l.b, (xsw2, ysw))
    xc2 = boot(xsw2, "L", 13, 5, "BTST2")
    h.w((xsw2 - 3.81, ysw), (xsw2 - 3.81, ysw + 3.81)); h.lab(xsw2 - 3.81, ysw + 3.81, "SW2", "L")
    xq2 = sn(xsw2 + 13.97)
    xdv2 = sn(xq2 - 11.43)
    qc = h.ic(R("Q", 2), xq2, ya, unit=1, mirror=True, fields="above")
    qd = h.ic(R("Q", 2), xq2, yb, unit=2, mirror=True, fields="above")
    d1b, sw1b, s2b = qc.p("D1"), qc.p("SW"), qd.p("S2")
    h.w(d1b, (xdv2, d1b[1]), (xdv2, yr))
    h.w(sw1b, (xsw2, sw1b[1]), (xsw2, ysw)); h.w(qd.p("SW"), (xsw2, qd.p("SW")[1]), (xsw2, ysw))
    h.w(s2b, (xdv2, s2b[1])); h.gnd(xdv2, s2b[1], "D")
    for q, pin, rk in ((qc, "G1", 46), (qd, "G2", 47)):
        h.lane(q.p(pin), "R", [R("R", rk)], q.net(pin), gap=5.08, end="label")
    # ---- output rail: caps, sense resistor, pack
    xe_ = sn(xdv2 + 10.16 + 13.97 * 3)
    h.w((xdv2, yr), (xe_, yr))
    outs = [R("C", k) for k in (38, 31, 34)]
    for i, c in enumerate(outs): h.hang(yr, sn(xdv2 + 10.16 + 13.97 * i), c, "BAT_SNS_P")
    xr = sn(xe_ + 15.24)
    r27 = h.two(R("R", 27), xr, yr, "h", first="BAT_SNS_P", txt="a")
    h.w((xe_, yr), r27.a)
    h.w(r27.b, (xr + 12.7, yr)); h.lab(xr + 12.7, yr, "PACK_P", "R")
    xb = sn(xe_ + 3.81)
    h.w((xb, yr), (xb, yr - 3.81)); h.lab(xb, yr - 3.81, "BAT_SNS_P", "L")
    h.note(xdv + 8, yr - 8, ["The first 22u ceramics sit on the D1 pins", "of Q401 and Q402: they close the hot loops.",
                             "R427 (RBAT) is the pack-side current sense."], 1.27)
    h.note(xsw + 14, ysw + 20, ["SW1 and SW2 are the two switch nodes, L401 between them.", "0R gate resistors are tuning positions."], 1.27)
    # test point on the power ground
    h.w((xdv, s2[1]), (xdv + 7.62, s2[1]))
    h.one(R("TP", 12), xdv + 7.62, s2[1], "L", txt="b")


def charger(h, R, ox, oy):
    symlib.respace("MonolithDev", "BQ25756", {
        "VAC": 78.74, "ACP": 58.42, "ACN": 50.8, "ACUV": 33.02, "ACOV": 25.4,
        "SCL": 15.24, "SDA": 12.7, "~{INT}": 10.16, "~{STAT1}": 7.62, "~{STAT2}": 5.08, "~{PG}": 2.54,
        "~{CE}": -15.24, "FSW_SYNC": -27.94, "ICHG": -40.64, "ILIM_HIZ": -53.34, "TS": -71.12,
        "HIDRV1": 76.2, "BTST1": 73.66, "SW1": 71.12, "LODRV1": 68.58, "HIDRV2": 63.5, "BTST2": 60.96, "SW2": 58.42,
        "LODRV2": 55.88, "SRP": 35.56, "SRN": 27.94, "FB": 5.08, "FBG": -2.54, "REGN": -25.4, "DRV_SUP": -38.1,
        "NC": -48.26, "PGND": -53.34})
    u = h.ic(R("U", 3), ox, oy, fields="above")
    P = u.p
    xp = P("VAC")[0]; xq = P("HIDRV1")[0]
    pr = lambda p: P(p)
    # ---------------------------------------------------------------- left: input sense, window, control, programming
    h.w(P("VAC"), (xp - 25.4, P("VAC")[1])); h.lab(xp - 25.4, P("VAC")[1], "PPHV", "L")
    h.hang(P("VAC")[1], sn(xp - 10.16), R("C", 9), "PPHV", up=True, txt="l")
    # Kelvin pair: ACP and ACN, filter capacitor between them, each with a series resistor out to the sense resistor
    xn = sn(xp - 7.62)
    ya_, yn_ = P("ACP")[1], P("ACN")[1]
    h.w(P("ACP"), (xn, ya_)); h.w(P("ACN"), (xn, yn_))
    c14 = h.two(R("C", 14), xn, sn((ya_ + yn_) / 2), "v", first="ACP_F", txt="l")
    h.hang(ya_, xn, R("C", 15), "ACP_F", up=True, txt="l")
    h.hang(yn_, xn, R("C", 16), "ACN_F", txt="l")
    h.lane((xn, ya_), "L", [R("R", 25)], "ACP_F", gap=14.0, end="label", txt="a")
    h.lane((xn, yn_), "L", [R("R", 26)], "ACN_F", gap=14.0, end="label", txt="b")
    # input window divider R409 R410 R411 as one vertical chain, taps at ACUV and ACOV
    xc = sn(xp - 33.02)
    yu, yo = P("ACUV")[1], P("ACOV")[1]
    h.w(P("ACUV"), (xc, yu)); h.w(P("ACOV"), (xc, yo))
    r9 = h.two(R("R", 9), xc, yu - 3.81, "v", first="PPHV", txt="l")
    r10 = h.two(R("R", 10), xc, yu + 3.81, "v", first="ACUV", txt="l")
    r11 = h.two(R("R", 11), xc, yo + 3.81, "v", first="ACOV", txt="l")
    h.w(r9.a, (xc, r9.a[1] - 2.54)); h.lab(xc, r9.a[1] - 2.54, "PPHV", "R")
    h.gnd(*r11.b)
    # bus and status
    h.stub(P("SCL"), "L", u.net("SCL"), 7.62)
    h.stub(P("SDA"), "L", u.net("SDA"), 7.62)
    h.stub(P("~{INT}"), "L", u.net("~{INT}"), 7.62)
    for pin in ("~{STAT1}", "~{STAT2}", "~{PG}"): h.nc(*P(pin))
    # charge enable: pulled up, MCU can force it high through R435
    yce = P("~{CE}")[1]
    xce = sn(xp - 7.62)
    h.w(P("~{CE}"), (xce, yce))
    h.hang(yce, xce, R("R", 17), "CE_N", up=True, txt="l")
    h.lane((xce, yce), "L", [R("R", 35)], "CE_N", gap=12.7, end="label", txt="a")
    # frequency and current programming resistors, one per pin
    for pin, rk in (("FSW_SYNC", 12), ("ICHG", 13), ("ILIM_HIZ", 14)):
        h.lane(P(pin), "L", [R("R", rk)], u.net(pin), gap=7.62, end="gnd", txt="a")
    # thermistor: REGN bias on top, 5.6k and the NTC down to ground
    yts = P("TS")[1]
    xts = sn(xp - 25.4)
    h.w(P("TS"), (xts - 12.7, yts))
    h.hang(yts, xts, R("R", 15), "TS", up=True, txt="r")
    h.hang(yts, xts, R("R", 16), "TS", txt="r")
    h.hang(yts, xts - 12.7, R("TH", 1), "TS", txt="l")
    # ---------------------------------------------------------------- right: gate drive on labels, battery sense, feedback
    for pin in ("HIDRV1", "BTST1", "SW1", "LODRV1", "HIDRV2", "BTST2", "SW2", "LODRV2"):
        h.stub(P(pin), "R", u.net(pin), 5.08)
    xn3 = sn(xq + 7.62)
    ys_, yn3 = P("SRP")[1], P("SRN")[1]
    h.w(P("SRP"), (xn3, ys_)); h.w(P("SRN"), (xn3, yn3))
    h.two(R("C", 17), xn3, sn((ys_ + yn3) / 2), "v", first="SRP_F", txt="r")
    h.hang(ys_, xn3, R("C", 18), "SRP_F", up=True, txt="r")
    h.hang(yn3, xn3, R("C", 19), "SRN_F", txt="r")
    h.lane((xn3, ys_), "R", [R("R", 28)], "SRP_F", gap=16.0, end="label", txt="a")
    h.lane((xn3, yn3), "R", [R("R", 29)], "SRN_F", gap=16.0, end="label", txt="b")
    # battery feedback divider R418 R419, vertical, tap at FB; the bottom end is FBG
    yf, yg = P("FB")[1], P("FBG")[1]
    xf = sn(xq + 27.94)
    h.w(P("FB"), (xf, yf)); h.w(P("FBG"), (xf, yg))
    r18 = h.two(R("R", 18), xf, yf - 3.81, "v", first="PACK_P", txt="r")
    h.two(R("R", 19), xf, yf + 3.81, "v", first="FB", txt="r")
    h.w(r18.a, (xf, r18.a[1] - 2.54)); h.lab(xf, r18.a[1] - 2.54, "PACK_P", "R")
    # regulator outputs
    yr_ = P("REGN")[1]; xr = sn(xq + 7.62)
    h.w(P("REGN"), (xr, yr_), (xr + 12.7, yr_)); h.lab(xr + 12.7, yr_, "REGN", "R")
    h.hang(yr_, xr, R("C", 10), "REGN", up=True, txt="r")
    yd = P("DRV_SUP")[1]
    h.w(P("DRV_SUP"), (xr, yd), (xr + 12.7, yd)); h.lab(xr + 12.7, yd, "DRV_SUP", "R")
    h.hang(yd, xr, R("C", 11), "DRV_SUP", txt="r")
    h.nc(*P("NC"))
    h.tie(P("PGND"), "GND", "R", 2.54)
    h.note(xp - 62, P("VAC")[1] - 14, ["Kelvin sense: ACP/ACN across RAC, SRP/SRN across RBAT, each pair filtered at the pin."], 1.27)
    h.note(xp - 10, P("TS")[1] + 8, ["Programming (expected values in the block):", "ACUV/ACOV window 4.1 V to 22.5 V, FB divider for 16.8 V,", "ICHG 4.2 A, ILIM 5.5 A, FSW 500 kHz, TS divider with NTC."], 1.27)


def ldo9(h, R, ox, oy):
    symlib.respace("MonolithDev", "TPS7A4101", {"IN": 22.86, "EN": -2.54})
    u = h.ic(R("U", 6), ox, oy, fields="above")
    P = u.p
    xp = P("IN")[0]
    yi = P("IN")[1]
    h.w(P("IN"), (xp - 20.32, yi)); h.lab(xp - 20.32, yi, "PACK_P", "L")
    h.hang(yi, sn(xp - 12.7), R("C", 57), "PACK_P", up=True, txt="l")
    # enable pulled up to REGN, pulled low by Q409 when the PD controller drives DRV9_OFF
    ye = P("EN")[1]
    xe = sn(xp - 7.62)
    h.w(P("EN"), (xe, ye))
    h.hang(ye, xe, R("R", 54), "V9_EN", up=True, txt="l", ld="L")
    q = h.ic(R("Q", 9), xe - 2.54, ye + 5.08, fields="right")
    h.w(q.p("D"), (xe, ye))
    h.tie(q.p("S"), "GND", "D", 2.54)
    h.stub(q.p("G"), "L", "DRV9_OFF", 5.08)
    # output, feedback divider as a vertical chain between the OUT row and the FB row, gate-drive diodes
    xo = P("OUT")[0]
    yo, yf = P("OUT")[1], P("FB")[1]
    xc = sn(xo + 22.86)
    h.w(P("OUT"), (xc, yo)); h.w(P("FB"), (xc, yf))
    h.hang(yo, sn(xc + 10.16), R("C", 58), "V9_DRV", txt="r")
    h.two(R("R", 52), xc, yo + 3.81, "v", first="V9_DRV", txt="l")
    r53 = h.two(R("R", 53), xc, yf + 3.81, "v", first="V9_FB", txt="l")
    h.gnd(*r53.b)
    h.lane((xc, yo), "R", [R("D", 11)], "V9_DRV", gap=30.0, end="label", txt="a")
    yd = yo - 12.7
    h.lab(xc + 12.7, yd, "REGN", "L"); h.w((xc + 12.7, yd), (xc + 12.7, yd))
    h.lane((xc + 12.7, yd), "R", [R("D", 10)], "REGN", gap=10.0, end="label", txt="a")
    h.tie(P("GND"), "GND", "D", 2.54)
    h.note(xp - 30, P("GND")[1] + 14, ["TPS7A4101 makes 9.6 V (R452/R453) for the gate drivers; D410 and D411 OR it with REGN onto DRV_SUP.",
                                        "The PD controller (DRV9_OFF) turns it off through Q409."], 1.27)


def buck5(h, R, ox, oy):
    symlib.respace("Regulator_Switching", "TPS62933", {"VIN": 22.86, "EN": 10.16, "SS": -15.24, "RT": -22.86})
    u = h.ic(R("U", 4), ox, oy, fields="above")
    P = u.p
    xp = P("VIN")[0]; yi = P("VIN")[1]
    h.w(P("VIN"), (xp - 38.1, yi)); h.lab(xp - 38.1, yi, "PACK_P", "L")
    h.hang(yi, sn(xp - 12.7), R("C", 46), "PACK_P", up=True, txt="r")
    h.hang(yi, sn(xp - 25.4), R("C", 44), "PACK_P", up=True, txt="l")
    ye = P("EN")[1]; xe = sn(xp - 7.62)
    h.w(P("EN"), (xe, ye), (xp - 38.1, ye)); h.lab(xp - 38.1, ye, u.net("EN"), "L")
    h.hang(ye, xe, R("R", 32), u.net("EN"), txt="r")
    ys = P("SS")[1]; xs = sn(xp - 7.62)
    h.w(P("SS"), (xs, ys)); h.hang(ys, xs, R("C", 39), "SS_5V", txt="l")
    h.tie(P("RT"), "GND", "L", 2.54)
    h.tie(P("GND"), "GND", "D", 2.54)
    xb = P("BST")[0]
    yb, ysw, yf = P("BST")[1], P("SW")[1], P("FB")[1]
    xk = sn(xb + 10.16)
    h.w(P("BST"), (xk, yb)); h.w(P("SW"), (xk, ysw))
    h.two(R("C", 40), xk, sn((yb + ysw) / 2), "v", first="BST_5V", txt="r")
    xl = sn(xk + 22.86)
    l = h.two(R("L", 2), xl, ysw, "h", first="SW_5V", txt="a")
    h.w((xk, ysw), l.a)
    xo = sn(l.b[0] + 10.16)
    xe_ = sn(xo + 15.24 * 5)
    h.w(l.b, (xe_, ysw)); h.lab(xe_, ysw, "PP5V", "R")
    # feedback divider: R433 from the output down to the FB row, R434 to ground
    h.w(P("FB"), (xo, yf))
    h.two(R("R", 33), xo, ysw + 3.81, "v", first="PP5V", txt="l")
    r34 = h.two(R("R", 34), xo, yf + 3.81, "v", first="FB_5V", txt="l")
    h.gnd(*r34.b)
    for i, k in enumerate((41, 42, 43)):
        h.hang(ysw, sn(xo + 15.24 * (i + 1)), R("C", k), "PP5V")
    h.note(xp - 38, P("GND")[1] + 9, ["TPS62933 makes PP5V (set by R433/R434) for the PD controller", "from the pack rail; the MCU enables it on EN_5V."], 1.27)
