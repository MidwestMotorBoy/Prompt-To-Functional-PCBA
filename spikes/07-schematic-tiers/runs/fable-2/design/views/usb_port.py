"""Sheet layout of one USB-C port. Used for both ports: d.r(k) gives the reference number (401 / 501 ...)."""


def view(d):
    r = d.r
    d.page = (430.0, 297.0)
    d.alias[next(n for n in d.nets if n.endswith("_LDO_3V3") and n[2] == str(d.base // 100 - 3))] = "LDO_3V3"
    connector_and_pd(d, 5.5, 5.5)
    power_stage(d, 5.5, 43)
    buck_5v(d, 5.5, 63.5)
    ldo_9v(d, 5.5, 88.5)
    controller(d, 78.5, 63.5)
    notes(d)


def connector_and_pd(d, x0, y0):
    r = d.r
    d.section("USB-C CONNECTOR, VBUS CLAMP, CC PROTECTION (TPD6S300) AND PD CONTROLLER (TPS25751D)", x0, y0, 131.5, 36)
    RY = 12                                                   # the VBUS rail
    j = d.ic("J" + r(1), 7, RY + 12.5, text=(-3.6, -11.4))
    d.tie([j.p(n) for n in ("A6", "A7", "B6", "B7")], dx=1.5, end=None)
    g = [d.go(j.p(n), dy=0.5) for n in ("SH", "A1")]
    d.wire(g[0], g[1]); d.gnd(g[1], "D")
    # VBUS: up to the rail, bulk capacitor and clamp, then straight into the PD controller
    v = d.go(d.go(j.p("A4"), dx=2), to_y=RY)
    d.label(d.pt(d.ux(v) + 0.5, RY, "VBUS"), "R")
    c = d.go(v, dx=5); d.shunt("C" + r(6), c, "D")
    # CC lines through the protection IC; RPD_Gx strapped to its CC pin (dead-battery Rd)
    e = d.ic("U" + r(5), 30, RY + 13, text=(2.2, 7.4))
    for a, b, k, dx in (("A5", "C_CC1", "RPD_G1", 1), ("B5", "C_CC2", "RPD_G2", 2)):
        d.wire(j.p(a), e.p(b))
        d.label(d.go(j.p(a), dx=1.5), "R")
        t = d.go(e.p(k), dx=-dx)
        d.wire(t, d.pt(d.ux(t), d.uy(e.p(b)), e.p(b).net))
    n = d.go(e.p("VPWR"), dy=-1.5)
    d.gnd(d.go(d.two("C" + r(52), n, "L", gap=0.5), dx=-1), "D")
    d.label(d.go(n, dy=-3), "R")
    n = d.go(e.p("VBIAS"), dy=-1.5)
    d.gnd(d.go(d.two("C" + r(51), n, "R", gap=0.5), dx=1), "D")
    g = [d.go(e.p(n), dy=1) for n in ("GND", "N.C.")]
    d.wire(g[0], g[1]); d.gnd(d.go(g[0], dy=1), "D")
    for pin, cap, dx in (("CC2", "C" + r(2), 7), ("CC1", "C" + r(1), 13)):
        d.label(d.go(e.p(pin), dx=0.5), "R")
        d.shunt(cap, d.go(e.p(pin), dx=dx), "D")
    f = d.go(e.p("~{FLT}"), dx=2)
    d.label(d.go(d.two("R" + r(41), f, "U", gap=0.5), dy=-0.5), "R")
    d.label(d.go(f, dx=1), "R")
    tv = d.ic("D" + r(1), 59, RY + 4, text=(3.4, -0.4))
    top = d.pt(59, RY, "VBUS")
    d.wire(c, top); d.wire(top, tv.p("IN")); d.gnd(tv.p("GND"), "D")

    # PD controller: VBUS in on the left, supplies and I2C on the right
    u = d.ic("U" + r(1), 83, RY + 6)
    d.wire(top, u.p("VBUS"))
    d.shunt("C" + r(50), d.go(u.p("VBUS"), dx=-5), "D", text="L")
    t = d.go(u.p("VBUS_IN"), dx=-1.5); d.wire(t, d.pt(d.ux(t), RY, "VBUS"))
    v = d.go(d.go(u.p("VIN_3V3"), dx=-2), dy=-4)
    d.pwr(d.go(v, dy=-1))
    d.shunt("C" + r(3), d.go(v, dx=-4), "D", text="L")
    d.tie([u.p(f"GPIO{k}") for k in (0, 1, 2, 4, 5, 7, 11)], dx=1)
    for k in (3, 6): d.label(d.go(u.p(f"GPIO{k}"), dx=-2), "L")
    d.gnd(u.p("GND"), "D")
    d.tie([u.p("DRAIN"), u.p("DRAIN_EP")], dx=1, end=None)
    d.gnd(d.two("C" + r(5), u.p("LDO_1V5"), "R", gap=2), "R")
    rail = u.p("LDO_3V3")
    R = lambda x: d.pt(d.ux(rail) + x, d.uy(rail), rail.net)
    d.shunt("C" + r(4), d.go(rail, dx=7), "D", gap=0, text="L")
    if u.p("ADCIN1").net == rail.net:
        t = d.go(u.p("ADCIN1"), dx=1.5); d.wire(t, R(1.5))
    for pin, ref, x in (("I2Cc_SCL", "R" + r(3), 9), ("I2Cc_SDA", "R" + r(2), 13.5), ("~{I2Cc_IRQ}", "R" + r(4), 18)):
        p = u.p(pin)
        d.wire(d.two(ref, R(x), "D"), d.go(p, dx=x), "vh")
        d.label(d.go(p, dx=0.5), "R")
    ee = d.ic("U" + r(2), d.ux(rail) + 28, d.uy(u.p("I2Cc_SCL")), mirror=True, text=(1, 3.7))
    d.wire(u.p("I2Cc_SCL"), ee.p("SCL"))
    k = d.go(u.p("I2Cc_SDA"), dx=22); d.wire(k, ee.p("SDA"), "vh")
    d.label(R(19.5), "R")
    v = R(d.ux(ee.p("VCC")) - d.ux(rail))
    d.wire(rail, v); d.wire(v, ee.p("VCC"))
    d.shunt("C" + r(8), d.go(v, dx=8.5), "D")
    d.tie([ee.p(n) for n in ("A0", "A1", "A2")], dx=1)
    d.gnd(ee.p("GND"), "D")


def power_stage(d, x0, y0):
    r = d.r
    d.section("BQ25756 FOUR-SWITCH BUCK-BOOST POWER STAGE: PPHV (5-20 V from the port) <-> PACK_P (12-16.8 V), 5 A", x0, y0, 157.5, 19)
    Y = 6.5
    p = d.pt(4, Y, "PPHV"); d.label(p, "L")
    p = d.bank(["C" + r(49), "C" + r(9)], p, "R", first=5, pitch=8.5, text="L")
    a = d.go(p, dx=4)
    b = d.go(d.two("R" + r(24), a, "R", gap=2), dx=2)
    d.label(d.pt(d.ux(b) + 0.5, Y, b.net), "R")
    fa, fb = d.kelvin(a, b, "R" + r(25), "R" + r(26), "C" + r(14), "C" + r(15), "C" + r(16))
    d.label(fa, "L"); d.label(fb, "R")
    p = d.bank(["C" + r(k) for k in (30, 20, 23, 24, 27, 21, 56)], b, "R", first=5.5)
    # input half bridge
    qx = d.ux(p) + 15; ya, yb = Y + 4, Y + 9
    qa = d.ic("Q" + r(1), qx, ya, unit=1, text=(-1.5, -2.8)); qb = d.ic("Q" + r(1), qx, yb, unit=2, text=(-1.5, 2.2))
    top = d.pt(qx + 4, Y, b.net)
    d.wire(p, top); d.wire(top, qa.p("D1"), "vh")
    s1 = d.pt(qx + 6, Y + 6.5, qa.p("SW").net)
    d.wire(qa.p("SW"), d.pt(qx + 6, d.uy(qa.p("SW")), s1.net)); d.wire(qb.p("SW"), d.pt(qx + 6, d.uy(qb.p("SW")), s1.net))
    d.wire(d.pt(qx + 6, d.uy(qa.p("SW")), s1.net), d.pt(qx + 6, d.uy(qb.p("SW")), s1.net))
    d.gnd(d.go(qb.p("S2"), dx=1, dy=1), "D")
    for q, pin, ref in ((qa, "G1", "R" + r(44)), (qb, "G2", "R" + r(45))):
        d.label(d.go(d.two(ref, q.p(pin), "L", gap=1), dx=-1), "L")
    # bootstrap 1, inductor, bootstrap 2
    bs = d.go(s1, dx=1.5)
    bt = d.go(d.two("C" + r(12), bs, "U", gap=0.5), dy=-0.5); d.label(bt, "L")
    d.label(d.go(d.two("D" + r(4), bt, "U", gap=0.5), dy=-0.5), "L")
    d.label(d.pt(d.ux(bs) + 0.5, d.uy(bs), s1.net), "R")
    lo = d.two("L" + r(1), bs, "R", gap=6)
    s2 = d.go(lo, dx=8)
    d.label(d.pt(d.ux(lo) + 0.5, d.uy(lo), lo.net), "R")
    bs2 = d.pt(d.ux(s2) - 1.5, d.uy(s2), s2.net)
    bt = d.go(d.two("C" + r(13), bs2, "U", gap=0.5, text="L"), dy=-0.5); d.label(bt, "R")
    d.label(d.go(d.two("D" + r(5), bt, "U", gap=0.5, text="L"), dy=-0.5), "R")
    # output half bridge, mirrored
    qx2 = d.ux(s2) + 6
    qc = d.ic("Q" + r(2), qx2, ya, unit=1, mirror=True, text=(-1.5, -2.8)); qd = d.ic("Q" + r(2), qx2, yb, unit=2, mirror=True, text=(-1.5, 2.2))
    d.wire(qc.p("SW"), d.pt(d.ux(s2), d.uy(qc.p("SW")), s2.net)); d.wire(qd.p("SW"), d.pt(d.ux(s2), d.uy(qd.p("SW")), s2.net))
    d.wire(d.pt(d.ux(s2), d.uy(qc.p("SW")), s2.net), d.pt(d.ux(s2), d.uy(qd.p("SW")), s2.net))
    d.gnd(d.go(qd.p("S2"), dx=-1, dy=1), "D")
    for q, pin, ref in ((qc, "G1", "R" + r(46)), (qd, "G2", "R" + r(47))):
        d.label(d.go(d.two(ref, q.p(pin), "R", gap=1), dx=1), "R")
    top2 = d.pt(qx2 - 4, Y, qc.p("D1").net)
    d.wire(qc.p("D1"), top2, "hv")
    d.label(d.pt(qx2 - 3.5, Y, top2.net), "R")
    p = d.bank(["C" + r(k) for k in (38, 31, 34)], top2, "R", first=16)
    c = d.go(p, dx=8)
    e = d.go(d.two("R" + r(27), c, "R", gap=2), dx=2)
    fa, fb = d.kelvin(c, e, "R" + r(28), "R" + r(29), "C" + r(17), "C" + r(18), "C" + r(19))
    d.label(fa, "L"); d.label(fb, "R")
    d.pwr(d.go(e, dx=4, dy=-1))


def controller(d, x0, y0):
    r = d.r
    d.section("BQ25756 CHARGE CONTROLLER: input window, switching frequency, current limits, battery feedback", x0, y0, 71, 29)
    u = d.ic("U" + r(3), 29, 16)
    P = u.p
    # input voltage window: one divider from PPHV, two taps
    top = d.go(P("VAC"), dx=-19)
    d.label(d.go(top, dx=-1), "L")
    t1 = d.go(d.two("R" + r(9), top, "D", text="L"), dy=1)
    t2 = d.go(d.two("R" + r(10), t1, "D", text="L"), dy=1)
    d.shunt("R" + r(11), t2, "D", text="L")
    d.wire(d.go(P("ACUV"), dx=-9), t1, "vh")
    d.wire(d.go(P("ACOV"), dx=-7), t2, "vh")
    # charge enable: pulled up to 3V3 (charging off), the MCU pulls CHG_INH low through R435 to allow charging
    n = d.go(P("~{CE}"), dx=-4)
    d.label(d.two("R" + r(17), n, "U", gap=0), "L")
    d.label(d.go(d.two("R" + r(35), n, "L", gap=2, text="S"), dx=-1), "L")
    for pin, ref, x in (("FSW_SYNC", "R" + r(12), 13), ("ICHG", "R" + r(13), 8), ("ILIM_HIZ", "R" + r(14), 3)):
        d.shunt(ref, d.go(P(pin), dx=-x), "D", text="L")
    # battery feedback divider: PACK_P - R418 - FB - R419 - FBG (FBG is switched to ground only while charging)
    t = d.go(P("FB"), dx=17)
    d.end(d.two("R" + r(18), t, "U"))
    f = d.go(d.two("R" + r(19), t, "D"), dy=1)
    d.wire(f, d.go(P("FBG"), dx=14), "hv")
    d.shunt("C" + r(10), d.go(P("REGN"), dx=9.5), "D")
    d.label(d.go(P("REGN"), dx=1), "R")
    d.shunt("C" + r(11), d.go(P("DRV_SUP"), dx=3.5), "D")
    d.label(d.go(P("DRV_SUP"), dx=0.3), "R")
    d.gnd(d.go(P("PGND"), dx=1, dy=1), "D")
    # battery thermistor window
    k = d.pt(d.ux(t) + 9, d.uy(P("REGN")), "TS")
    d.label(d.go(d.two("R" + r(15), k, "U"), dy=-0.5), "R")
    d.label(k, "L")
    d.shunt("R" + r(16), k, "D", text="L")
    d.shunt("TH" + r(1), d.go(k, dx=4), "D")
    # what the programming resistors set
    d.note(0.8, 22.6, "input window\n4.1 V to 22.5 V")
    d.note(9.0, 26.6, "500 kHz")
    d.note(13.2, 27.4, "4.2 A charge")
    d.note(21.8, 27.6, "5.5 A input")
    d.note(51.8, 19.1, "16.8 V")


def buck_5v(d, x0, y0):
    r = d.r
    d.section("5 V BUCK FOR PP5V (TPS62933): PACK_P in, 5.15 V out for the port's 5 V source and VCONN", x0, y0, 71, 23.5)
    u = d.ic("U" + r(4), 22, 13)
    v = d.go(d.go(u.p("VIN"), dx=-2), dy=-5)
    d.pwr(d.go(v, dy=-1))
    d.bank(["C" + r(46), "C" + r(44)], v, "L", first=4, text="L")
    e = d.go(u.p("EN"), dx=-7)
    d.shunt("R" + r(32), e, "D", text="L")
    d.label(d.go(e, dx=-3.5), "L")
    d.shunt("C" + r(39), d.go(u.p("SS"), dx=-3.5), "D")
    b = d.go(u.p("BST"), dx=2)
    s = d.two("C" + r(40), b, "D", gap=0)
    d.wire(u.p("SW"), s)
    o = d.go(d.two("L" + r(2), s, "R", gap=5), dx=3)
    t = d.go(d.two("R" + r(33), o, "D"), dy=1)
    d.shunt("R" + r(34), t, "D")
    d.wire(d.go(u.p("FB"), dx=2), t, "vh")
    p = d.bank(["C" + r(k) for k in (41, 42, 43, 7)], o, "R", first=5)
    d.label(d.go(p, dx=3), "R")
    d.gnd(u.p("GND"), "D")


def ldo_9v(d, x0, y0):
    r = d.r
    d.section("9.6 V GATE-DRIVE SUPPLY (TPS7A4101), DIODE-ORed WITH REGN INTO DRV_SUP; PD GPIO6 high turns it off", x0, y0, 71, 22.5)
    u = d.ic("U" + r(6), 32, 13.5)
    v = d.go(d.go(u.p("IN"), dx=-1.5), dy=-6)
    d.pwr(d.go(v, dy=-1))
    d.shunt("C" + r(57), d.go(v, dx=-3.5), "D", text="L")
    q = d.ic("Q" + r(9), d.ux(u.p("EN")) - 12, d.uy(u.p("EN")) + 3, text=(2.3, -0.5))
    e = d.go(q.p("D"), dy=-1)
    d.wire(e, u.p("EN"))
    d.label(d.go(d.two("R" + r(54), e, "U"), dy=-0.5), "L")
    g = d.go(q.p("G"), dx=-3)
    d.label(d.go(d.two("R" + r(55), g, "U", gap=0.5), dy=-0.5), "L")
    d.label(d.go(g, dx=-1.5), "L")
    d.gnd(q.p("S"), "D")
    o = d.go(u.p("OUT"), dx=4)
    t = d.go(d.two("R" + r(52), o, "D"), dy=1)
    d.shunt("R" + r(53), t, "D")
    d.wire(d.go(u.p("FB"), dx=2), t, "vh")
    d.label(d.go(u.p("OUT"), dx=0.5), "R")
    c = d.go(o, dx=6); d.shunt("C" + r(58), c, "D")
    n = d.go(d.two("D" + r(11), c, "R", gap=5), dx=2)
    d.label(d.go(d.two("D" + r(10), n, "D"), dy=0.5, dx=1), "R") if False else d.label(d.go(d.go(d.two("D" + r(10), n, "D"), dy=1), dx=1), "R")
    d.label(d.go(n, dx=2), "R")
    d.gnd(u.p("GND"), "D")


def notes(d):
    r = d.r
    d.ox, d.oy = 0, 0
    tp = d.pt(155.5, 70.5, "GND")
    d.tp("TP" + r(12), tp, "U"); d.gnd(tp, "D")
    q = lambda k: "Q" + r(k)
    d.note(138.5, 6, "NOTES\n"
           "1. This sheet is used twice (4xx = port 1, 5xx = port 2).\n"
           "   The only difference is the ADCIN1 strap of the PD\n"
           "   controller: LDO_3V3 on port 1, GND on port 2.\n"
           "2. Power path: VBUS - 5 A switch in the TPS25751D -\n"
           "   PPHV - RAC - four-switch bridge - RBAT - PACK_P.\n"
           "   Charging and sourcing use the same path.\n"
           "3. D+ is shorted to D- at the connector (dedicated\n"
           "   charging port, no data). SBU pins are not used.\n"
           "4. TPD6S300: RPD_G1/G2 strapped to C_CC1/C_CC2 give the\n"
           "   dead-battery Rd, so a flat pack still gets 5 V.\n"
           "5. Unused PD GPIO are grounded. GPIO3 reads the TPD6S300\n"
           "   fault flag, GPIO6 (DRV9_OFF) turns the 9.6 V LDO off.\n"
           "6. The PD controller is I2C master of the BQ25756 and\n"
           "   the EEPROM (I2CC_*), and a target of the MCU (SCL, SDA).\n"
           "7. RAC and RBAT are sensed Kelvin: 10R + 10R with 0.47u\n"
           "   across and 0.1u to ground on each side, at the IC.\n"
           "8. Hot loops: the first ceramic on each side of the\n"
           "   bridge (input side and pack side) sits at the FET\n"
           "   pair. Gate resistors are 0R places for tuning.\n"
           "9. Bootstrap diodes and the gate driver run from\n"
           "   DRV_SUP = REGN (5 V) or 9.6 V from the LDO, whichever\n"
           "   is higher (diode-OR).\n"
           "10. Set points (resistors): charge to 16.8 V, 4.2 A;\n"
           "   input 4.1 V to 22.5 V, 5.5 A limit; 500 kHz.\n"
           "11. /CE is pulled up to 3V3 (47k): the charger is off\n"
           "   until the MCU pulls CHG_INH low (1k). High or floating\n"
           "   stops charging.\n"
           "12. TH401/TH501: board NTC read by the BQ25756 TS pin\n"
           "   (charging is held off when too hot or too cold).", 1.27)
