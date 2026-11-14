"""USB-C PD port sheet (used for both ports): hand layout written with the kit in scene.py."""
from scene import snap


def usb_port(S):
    S.sh.paper = (594, 420)
    n = int(next(r for r in S.refs if r.startswith("J"))[1:]) - 1
    port = n // 100 - 3
    S.alias = {"LDO_3V3": f"/P{port}_LDO_3V3", "EN_5V": f"EN_5V{port}"}
    R = lambda k: f"R{n + k}"; C = lambda k: f"C{n + k}"; U = lambda k: f"U{n + k}"
    Q = lambda k: f"Q{n + k}"; D = lambda k: f"D{n + k}"; L = lambda k: f"L{n + k}"; J = lambda k: f"J{n + k}"
    gnda = lambda pt, show=False: S.gnda(pt[0], pt[1], show)
    S.title(f"USB Port {port}", 15, 18)

    def hang(ref, x, y, first, show_gnd=True, text="r"):
        p = S.two(ref, x, y, "v", first=first, text=text)
        if show_gnd: S.gnd(*p.b)
        return p

    # ================= A: connector and protection =================
    S.text("USB-C connector and port protection", 15, 30, 1.6)
    S.box(12, 34, 192, 130)
    j = S.ic(J(1), 45.72, 86.36)
    vb = j("VBUS"); ry = vb[1] - 17.78
    xr = vb[0] + 7.62
    S.w(vb, (xr, vb[1]), (xr, ry)); S.w((xr - 6.35, ry), (xr + 24.0, ry)); S.label("VBUS", xr - 6.35, ry, "L")
    hang(C(6), xr + 7.62, ry, "VBUS"); hang(C(50), xr + 24.0, ry, "VBUS")
    d401 = S.ic(D(1), 32.0, ry + 7.62, ref_at=(40.0, ry + 3.5), val_at=(40.0, ry + 5.8))
    S.gnd(*d401("GND"))
    S.w(d401("IN"), (xr - 6.35, ry))
    cc1, cc2 = j("CC1"), j("CC2")
    for p in (j("SBU1"), j("SBU2")): S.nc(p)
    xb = vb[0] + 5.08
    # D+ and D- shorted: dedicated charging port
    dpins = [j("D-"), j("D+")]
    S.w((dpins[0][0], dpins[0][1]), (xb, dpins[0][1]))
    y_dm = [pt for pt in (j("A7"), j("B7"), j("A6"), j("B6"))]
    for pt in y_dm: S.w(pt, (xb, pt[1]))
    S.w((xb, min(p[1] for p in y_dm)), (xb, max(p[1] for p in y_dm)))
    S.text("D+ and D- shorted: dedicated charging port", xb + 2.54, y_dm[1][1] + 6.5)
    g = j("GND"); S.gnd(*g); sh = j("SHIELD"); S.gnd(*sh)
    # CC lines to the protection IC, rows aligned
    u5 = S.ic(U(5), 134.62, cc1[1] + 11.43, ref_at=(113.0, cc1[1] - 9.0), val_at=(113.0, cc1[1] - 7.0))
    S.w(cc1, u5("C_CC1")); S.w(cc2, u5("C_CC2"))
    S.label("C_CC1", cc1[0] + 15.24, cc1[1], "R"); S.label("C_CC2", cc2[0] + 15.24, cc2[1], "R")
    S.stub(u5("RPD_G1"), "L", "C_CC1", 5.08); S.stub(u5("RPD_G2"), "L", "C_CC2", 5.08)
    for p in ("C_SBU1", "C_SBU2", "D1", "D2", "SBU1", "SBU2"): S.nc(u5(p))
    p1, p2 = u5("CC1"), u5("CC2")
    x1 = p1[0] + 7.62; x2 = p1[0] + 22.86
    S.w(p2, (x1 + 2.54, p2[1])); S.label("CC2", x1 + 2.54, p2[1], "R"); hang(C(2), x1, p2[1], "CC2")
    S.w(p1, (x2 + 2.54, p1[1])); S.label("CC1", x2 + 2.54, p1[1], "R"); hang(C(1), x2, p1[1], "CC1")
    S.stub(u5("~{FLT}"), "R", "SBU_FLT", 5.08)
    vp = u5("VPWR"); ytop = vp[1] - 15.24
    S.w(vp, (vp[0], ytop), (vp[0] - 17.78, ytop)); S.label("LDO_3V3", vp[0] - 17.78, ytop, "L")
    hang(C(52), vp[0] - 10.16, ytop, "LDO_3V3")
    vi = u5("VBIAS")
    S.w(vi, (vi[0], ytop), (vi[0] + 10.16, ytop)); hang(C(51), vi[0] + 10.16, ytop, "VBIAS")
    S.label("VBIAS", vi[0] + 3.81, ytop, "R")
    a, b = u5("GND"), u5("N.C.")
    S.w(a, (a[0], a[1] + 2.54), (b[0], a[1] + 2.54), b); S.gnd(a[0] + 2.54, a[1] + 2.54)

    S.note(["D401 clamps VBUS surges. U405 protects CC1 and CC2 from VBUS shorts and gives the",
            "dead-battery Rd (RPD_G pins). The SBU pins are not used."], 16, 118)

    # ================= B: PD controller =================
    S.text("USB PD controller TPS25751D, EEPROM and pull-ups", 198, 30, 1.6)
    S.box(196, 34, 470, 130)
    u = S.ic(U(1), 267.97, 86.36)
    lx = u("VBUS")[0]; rx = u("PPHV")[0]
    # left: 3V3 supply with its capacitor, VBUS, CC, strap and GPIO
    v3 = u("VIN_3V3"); yt = v3[1] - 12.7
    S.w(v3, (v3[0] - 5.08, v3[1]), (v3[0] - 5.08, yt), (v3[0] - 33.0, yt)); S.pwr("3V3", v3[0] - 33.0, yt)
    hang(C(3), v3[0] - 22.86, yt, "3V3")
    S.w(u("VBUS_IN"), (lx - 5.08, u("VBUS_IN")[1]), (lx - 5.08, u("VBUS")[1]), u("VBUS"))
    S.w((lx - 5.08, u("VBUS")[1]), (lx - 10.16, u("VBUS")[1])); S.label("VBUS", lx - 10.16, u("VBUS")[1], "L")
    S.stub(u("CC1"), "L", "CC1", 5.08); S.stub(u("CC2"), "L", "CC2", 5.08)
    S.gbus([u("GPIO0"), u("GPIO1"), u("GPIO2")], "L")
    S.stub(u("GPIO3"), "L", "SBU_FLT", 5.08)
    S.gbus([u("GPIO4"), u("GPIO5")], "L", at=(u("GPIO4")[1] + u("GPIO5")[1]) / 2)
    S.stub(u("GPIO6"), "L", "DRV9_OFF", 5.08)
    S.gbus([u("GPIO7"), u("GPIO11")], "L", at=(u("GPIO7")[1] + u("GPIO11")[1]) / 2)
    gp = u("GND"); S.w(gp, (gp[0], gp[1] + 2.54)); S.gnd(gp[0], gp[1] + 2.54)
    # right: PPHV and PP5V outputs with their capacitors (staircase: the upper row reaches farther)
    xf, xn = 36.83, 22.86
    pp, p5 = u("PPHV"), u("PP5V")
    S.w(pp, (pp[0] + xf + 2.54, pp[1])); S.label("PPHV", pp[0] + xf + 2.54, pp[1], "R"); hang(C(49), pp[0] + xf, pp[1], "PPHV")
    S.w(p5, (p5[0] + xn + 2.54, p5[1])); S.label("PP5V", p5[0] + xn + 2.54, p5[1], "R"); hang(C(7), p5[0] + xn, p5[1], "PP5V")
    # the C409 1u is the charger's VAC bulk: drawn with the charger
    d1, d2 = u("DRAIN"), u("DRAIN_EP")
    S.w(d1, (d1[0] + 5.08, d1[1]), (d1[0] + 5.08, d2[1]), d2); S.text("PD_DRAIN", d1[0] + 7, (d1[1] + d2[1]) / 2 + 1.0)
    l15, l33 = u("LDO_1V5"), u("LDO_3V3")
    S.w(l15, (l15[0] + 32.5, l15[1])); S.label("LDO_1V5", l15[0] + 17, l15[1], "R"); hang(C(5), l15[0] + 30.48, l15[1], "LDO_1V5")
    S.w(l33, (l33[0] + 8.89 + 2.54, l33[1])); S.label("LDO_3V3", l33[0] + 11.43, l33[1], "R"); hang(C(4), l33[0] + 8.89, l33[1], "LDO_3V3")
    a1, a2 = u("ADCIN1"), u("ADCIN2")
    if port == 1: S.w(l33, (l33[0] + 5.08, l33[1]), (l33[0] + 5.08, a1[1]), a1)
    else: S.w(a1, (a1[0] + 2.54, a1[1])); S.gside(a1[0] + 2.54, a1[1], "R")
    S.w(a2, (a2[0] + 2.54, a2[1])); S.gside(a2[0] + 2.54, a2[1], "R")
    for pin, net in (("I2Cc_SCL", "I2CC_SCL"), ("I2Cc_SDA", "I2CC_SDA"), ("~{I2Cc_IRQ}", "CHG_INT"), ("I2Ct_SCL", "SCL"), ("I2Ct_SDA", "SDA"), ("~{I2Ct_IRQ}", "IRQ_N")):
        S.stub(u(pin), "R", net, 5.08)
    # pull-ups and EEPROM
    S.text("Pull-ups on the PD controller 3.3 V", 345, 50, 1.27)
    yb = 58.42
    S.w((347.66, yb), (421.64, yb)); S.label("LDO_3V3", 347.66, yb, "L")
    for k, (rr, net) in enumerate(((R(2), "I2CC_SDA"), (R(3), "I2CC_SCL"), (R(4), "CHG_INT"), (R(41), "SBU_FLT"), (R(55), "DRV9_OFF"))):
        x = 360.68 + k * 15.24
        p = S.two(rr, x, yb, "v", first="LDO_3V3")
        S.w(p.b, (x, p.b[1] + 5.08)); S.label(net, x, p.b[1] + 5.08, "R")
    ee = S.ic(U(2), 440.0, 100.33, ref_at=(421.0, 89.0), val_at=(421.0, 91.2))
    S.stub(ee("SDA"), "R", "I2CC_SDA", 5.08); S.stub(ee("SCL"), "R", "I2CC_SCL", 5.08)
    S.gbus([ee("A0"), ee("A1"), ee("A2")], "L")
    w = ee("WP"); S.w(w, (w[0] + 2.54, w[1])); S.gside(w[0] + 2.54, w[1], "R")
    g = ee("GND"); S.w(g, (g[0], g[1] + 2.54)); S.gnd(g[0], g[1] + 2.54)
    vc = ee("VCC"); yv = vc[1] - 15.24
    S.w(vc, (vc[0], yv), (vc[0] - 10.16, yv), (vc[0] + 10.16, yv)); S.label("LDO_3V3", vc[0] - 10.16, yv, "L")
    hang(C(8), vc[0] + 10.16, yv, "LDO_3V3")
    S.text("EEPROM for the PD configuration", 420, 124)
    S.note(["ADCIN1 is a strap: it sets the I2C target address, so the two ports differ.",
            "PP5V and PPHV are the controller's 5 V and 20 V power paths."], 200, 118)

    # ================= C: four-switch power stage =================
    S.text("Four-switch buck-boost power stage: VBUS side half bridge, inductor, pack side half bridge", 15, 136, 1.6)
    S.box(12, 140, 372, 224)
    yr = 160.02
    S.w((22.86, yr), (36.83, yr)); S.label("PPHV", 22.86, yr, "L")
    r424 = S.two(R(24), 36.83, yr, "h", first="PPHV", text="a")
    xn_ = 52.07
    S.w(r424.b, (xn_, yr)); S.label("AC_SNS_N", 53.34, yr, "R")
    cin = [C(30), C(20), C(23), C(24), C(27), C(21), C(56)]
    xs_ = [64.77 + 15.24 * i for i in range(len(cin))]
    for ref, x in zip(cin, xs_): hang(ref, x, yr, "AC_SNS_N")
    S.w((xn_, yr), (xs_[-1], yr))
    qx, ya = 203.2, 175.26
    yb = ya + 15.24
    qa = S.ic(Q(1), qx, ya, unit=1, ref_at=(qx - 6.35, ya - 8), val_at=(qx - 6.35, ya - 5.8))
    qb = S.ic(Q(1), qx, yb, unit=2, ref_at=(qx - 6.35, yb + 7), val_at=(qx - 6.35, yb + 9.2))
    xd, xs = qx + 8.89, qx + 11.43
    S.w((xs_[-1], yr), (xd, yr), (xd, qa("D1")[1]), qa("D1"))
    S.w(qa("SW"), (xs, qa("SW")[1]), (xs, qb("SW")[1]), qb("SW"))
    S.w(qb("S2"), (xd, qb("S2")[1])); S.gnd(xd, qb("S2")[1])
    ysw = 182.88
    r444 = S.two(R(44), 172.72, qa("G1")[1], "h", first="HIDRV1", text="a")
    S.w(r444.b, qa("G1")); S.w(r444.a, (r444.a[0] - 5.08, r444.a[1])); S.label("HIDRV1", r444.a[0] - 5.08, r444.a[1], "L")
    r445 = S.two(R(45), 172.72, qb("G2")[1], "h", first="LODRV1", text="b")
    S.w(r445.b, qb("G2")); S.w(r445.a, (r445.a[0] - 5.08, r445.a[1])); S.label("LODRV1", r445.a[0] - 5.08, r445.a[1], "L")
    l401 = S.two(L(1), xs + 7.62, ysw, "h", first="SW1", text="a")
    S.w((xs, ysw), l401.a)
    S.label("SW1", xs + 1.27, ysw, "R")
    xs2 = xs + 22.86; qx2 = xs2 + 11.43; xd2 = qx2 - 8.89
    S.label("SW2", xs2 - 1.27, ysw, "L")
    S.w(l401.b, (xs2, ysw))
    qa2 = S.ic(Q(2), qx2, ya, unit=1, mirror=True, ref_at=(qx2 - 6.35, ya - 8), val_at=(qx2 - 6.35, ya - 5.8))
    qb2 = S.ic(Q(2), qx2, yb, unit=2, mirror=True, ref_at=(qx2 - 6.35, yb + 7), val_at=(qx2 - 6.35, yb + 9.2))
    S.w(qa2("SW"), (xs2, qa2("SW")[1]), (xs2, qb2("SW")[1]), qb2("SW"))
    S.w(qb2("S2"), (xd2, qb2("S2")[1])); S.gnd(xd2, qb2("S2")[1])
    S.w(qa2("D1"), (xd2, qa2("D1")[1]), (xd2, yr))
    r446 = S.two(R(46), qa2("G1")[0] + 5.08, qa2("G1")[1], "h", first="HG2", text="a")
    S.w(qa2("G1"), r446.a); S.w(r446.b, (r446.b[0] + 5.08, r446.b[1])); S.label("HIDRV2", r446.b[0] + 5.08, r446.b[1], "R")
    r447 = S.two(R(47), qb2("G2")[0] + 5.08, qb2("G2")[1], "h", first="LG2", text="b")
    S.w(qb2("G2"), r447.a); S.w(r447.b, (r447.b[0] + 5.08, r447.b[1])); S.label("LODRV2", r447.b[0] + 5.08, r447.b[1], "R")
    xo = 292.1
    S.w((xd2, yr), (xo + 15.24 * 2, yr)); S.label("BAT_SNS_P", xd2 + 2.54, yr, "R")
    for k, ref in enumerate((C(38), C(31), C(34))): hang(ref, xo + 15.24 * k, yr, "BAT_SNS_P")
    r427 = S.two(R(27), xo + 15.24 * 2 + 12.7, yr, "h", first="BAT_SNS_P", text="a")
    S.w((xo + 30.48, yr), r427.a); S.w(r427.b, (r427.b[0] + 7.62, yr)); S.pwr("PACK_P", r427.b[0] + 7.62, yr)
    S.text("Q401: input half bridge", 190, 207); S.text("Q402: pack half bridge", 236, 207)
    S.text("0R gate resistors are tuning positions", 150, 217)
    S.text("Input bulk: 4 x 22u + 100n + 2 x 68u polymer", 62, 190)
    S.text("R424 (input) and R427 (battery) are the 5 mR sense resistors", 262, 217)

    # ================= F: 9 V gate-drive supply =================
    S.text("9 V gate-drive supply, diode-ORed with REGN", 378, 136, 1.6)
    S.box(376, 140, 582, 224)
    u6 = S.ic(U(6), 450.0, 168.0)
    vin6, en6, out6, fb6, gn6 = u6("IN"), u6("EN"), u6("OUT"), u6("FB"), u6("GND")
    xi, yrail = vin6[0] - 5.08, 152.4
    S.pwr("PACK_P", 396.0, yrail)
    S.w(vin6, (xi, vin6[1]), (xi, yrail), (396.0, yrail))
    hang(C(57), 408.0, yrail, "PACK_P")
    xe = 426.0
    S.w(en6, (xe, en6[1]))
    r454 = S.two(R(54), xe, en6[1] - 7.62, "v", first="REGN")
    S.w(r454.a, (xe, r454.a[1] - 2.54)); S.label("REGN", xe, r454.a[1] - 2.54, "R")
    q9 = S.ic(Q(9), xe - 2.54, en6[1] + 12.7, ref_at=(xe + 3.5, en6[1] + 11.3), val_at=(xe + 3.5, en6[1] + 13.9))
    S.w((xe, en6[1]), q9("D"))
    S.stub(q9("G"), "L", "DRV9_OFF", 5.08)
    S.w(q9("S"), (q9("S")[0], q9("S")[1] + 2.54)); S.gnd(q9("S")[0], q9("S")[1] + 2.54)
    S.text("GPIO6 of the PD controller", 436, 190); S.text("high pulls EN low: 9 V off", 436, 192.5)
    S.w(gn6, (gn6[0], gn6[1] + 2.54)); S.gnd(gn6[0], gn6[1] + 2.54)
    xd6 = out6[0] + 10.16
    r452 = S.two(R(52), xd6, out6[1], "v", first="V9_DRV")
    S.w(out6, (xd6 + 30.0, out6[1])); S.w(fb6, (xd6, fb6[1]))
    hang(R(53), xd6, fb6[1], "V9_FB")
    hang(C(58), xd6 + 20.0, out6[1], "V9_DRV")
    S.label("V9_DRV", xd6 + 30.0, out6[1], "R")
    # diode OR into DRV_SUP
    yo2 = 206.0
    S.w((401.0, yo2), (408.0, yo2)); S.label("REGN", 401.0, yo2, "L")
    d410 = S.two(D(10), 408.0, yo2, "h", first="REGN", text="a")
    xn6 = d410.b[0] + 14.0
    S.w(d410.b, (xn6, yo2))
    d411 = S.two(D(11), xn6, yo2, "h", first="DRV_SUP", text="a")
    S.w(d411.b, (d411.b[0] + 5.08, yo2)); S.label("V9_DRV", d411.b[0] + 5.08, yo2, "R")
    S.w((xn6, yo2), (xn6, yo2 + 5.08)); S.label("DRV_SUP", xn6, yo2 + 5.08, "R")
    S.text("DRV_SUP takes the higher of REGN and 9 V", 401, 216)

    # ================= D: BQ25756 charge controller =================
    S.text("BQ25756 charge controller: input sensing, programming, feedback and bias", 15, 230, 1.6)
    S.box(12, 234, 372, 374)
    cx, cy = 190.0, 316.0
    u3 = S.ic(U(3), cx, cy)
    px, px2 = u3("SCL")[0], u3("SRP")[0]
    rowL = lambda pin: u3(pin)[1]

    # --- left stubs: the pins whose circuits are drawn apart, linked by the net names
    for pin, net in (("ACUV", "ACUV"), ("ACOV", "ACOV"), ("SCL", "I2CC_SCL"), ("SDA", "I2CC_SDA"),
                     ("~{INT}", "CHG_INT"), ("~{CE}", "CE_N")):
        S.stub(u3(pin), "L", net, 5.08)
    for pin in ("~{STAT1}", "~{STAT2}", "~{PG}"): S.nc(u3(pin))

    # --- input window: divider hanging from the PPHV rail (taps by label)
    S.text("Input window: under 4.1 V, over 22.5 V", 58, 243)
    yp = 250.0
    xv, xp, xn = px - 7.62, px - 17.78, px - 27.94
    vac, acp, acn = u3("VAC"), u3("ACP"), u3("ACN")
    S.w((24.0, yp), (xv, yp)); S.label("PPHV", 24.0, yp, "L")
    S.w(vac, (xv, vac[1]), (xv, yp))                                  # VAC rises to the rail
    hang(C(9), 100.0, yp, "PPHV")
    r409 = S.two(R(9), 70.0, yp, "v", first="PPHV")
    r410 = S.two(R(10), 70.0, r409.b[1], "v", first="ACUV")
    r411 = S.two(R(11), 70.0, r410.b[1], "v", first="ACOV")
    S.gnd(*r411.b)
    S.stub(r409.b, "L", "ACUV", 5.08); S.stub(r410.b, "L", "ACOV", 5.08)
    # --- input current sense: Kelvin RC filter wired straight up from ACP and ACN
    S.text("Input current sense across R424", 112, 243)
    r425 = S.two(R(25), xp, yp, "v", first="PPHV")
    yf = r425.b[1]; yf2 = yf + 17.78
    S.w(acp, (xp, acp[1]), (xp, yf))
    xcc = 132.08
    S.w((xp, yf), (xcc, yf))
    hang(C(15), 154.94, yf, "ACP_F", text="l")
    c414 = S.two(C(14), xcc, yf, "v", first="ACP_F", text="l")
    S.w(c414.b, (xcc, yf2))
    S.w(acn, (xn, acn[1]), (xn, yf2), (115.0, yf2))
    hang(C(16), 124.46, yf2, "ACN_F")
    r426 = S.two(R(26), 105.0, yf2, "h", first="AC_SNS_N", text="a")
    S.w((r426.a[0] - 5.08, yf2), r426.a); S.label("AC_SNS_N", r426.a[0] - 5.08, yf2, "L")
    S.w(r426.b, (115.0, yf2))

    # --- charge enable
    S.text("Charge enable, active low: pulled up by R417, driven by CHG_INH", 88, 322)
    S.pwr("3V3", 100.0, 302.0)
    r417 = S.two(R(17), 100.0, 302.0, "v", first="3V3")
    S.stub(r417.b, "L", "CE_N", 5.08)
    S.w(r417.b, (112.0, r417.b[1]))
    r435 = S.two(R(35), 112.0, r417.b[1], "h", first="CE_N", text="b")
    S.stub(r435.b, "R", "CHG_INH", 5.08)

    # --- programming resistors on the lower left pins (staircase: the upper pin reaches farthest)
    S.text("Set points: 500 kHz, 4.2 A charge, 5.5 A input limit, 16.8 V battery", 100, 368)
    for pin, ref, xo_ in (("FSW_SYNC", R(12), -43.18), ("ICHG", R(13), -27.94), ("ILIM_HIZ", R(14), -12.7)):
        pt = u3(pin)
        net = {"FSW_SYNC": "FSW", "ICHG": "ICHG", "ILIM_HIZ": "ILIM"}[pin]
        x = px + xo_
        S.w(pt, (x, pt[1]))
        p = S.two(ref, x, pt[1], "v", first=net, text="l")
        S.gnd(*p.b)
    # --- thermistor network: its own row below the stair, REGN on the left
    ts = u3("TS"); yts = 352.0; xts = px - 5.08
    S.w(ts, (xts, ts[1]), (xts, yts), (px - 62.0 + 7.62, yts))
    r416 = S.two(R(16), px - 12.0, yts, "v", first="TS")
    S.gnd(*r416.b)
    th = S.two(f"TH{n + 1}", px - 32.0, yts, "v", first="TS", text="l")
    S.gnd(*th.b)
    r415 = S.two(R(15), px - 62.0, yts, "h", first="REGN", text="a")
    S.w((r415.a[0] - 5.08, yts), r415.a); S.label("REGN", r415.a[0] - 5.08, yts, "L")

    # --- right stubs: gate drive, bootstrap and sense pins
    for pin, net in (("HIDRV1", "HIDRV1"), ("LODRV1", "LODRV1"), ("HIDRV2", "HIDRV2"), ("LODRV2", "LODRV2"),
                     ("SRP", "SRP_F"), ("SRN", "SRN_F"), ("FB", "FB"), ("FBG", "FBG")):
        S.stub(u3(pin), "R", net, 5.08)
    S.nc(u3("NC"))
    pg = u3("PGND"); S.w(pg, (pg[0] + 2.54, pg[1])); S.gside(pg[0] + 2.54, pg[1], "R")
    # REGN and DRV_SUP bypass: the upper pin reaches farther
    rg, ds_ = u3("REGN"), u3("DRV_SUP")
    xr_, xd_ = px2 + 27.94, px2 + 7.62
    S.w(rg, (xr_ + 2.54, rg[1])); S.label("REGN", xr_ + 2.54, rg[1], "R")
    hang(C(10), xr_, rg[1], "REGN")
    S.w(ds_, (xd_ + 2.54, ds_[1])); S.label("DRV_SUP", xd_ + 2.54, ds_[1], "R")
    hang(C(11), xd_, ds_[1], "DRV_SUP")

    # --- bootstrap supplies, wired straight up from BTST and SW: cap across, diode from DRV_SUP above
    S.text("Bootstrap: Q401 high side", 205, 245); S.text("Bootstrap: Q402 high side", 245, 245)
    ycb = 272.0
    for dref, cref, bt, sw, xb in ((D(4), C(12), "BTST1", "SW1", px2 + 17.78), (D(5), C(13), "BTST2", "SW2", px2 + 50.8)):
        pb, ps = u3(bt), u3(sw)
        xs_b = xb + 7.62
        c_ = S.two(cref, xb, ycb, "h", first=bt, ra_=(xs_b + 2.5, ycb + 1.2), va_=(xs_b + 2.5, ycb + 3.4))
        S.w(pb, (xb, pb[1]), (xb, ycb))
        S.w(ps, (xs_b, ps[1]), c_.b)
        S.w(c_.b, (xs_b, ycb - 5.08)); S.label(sw, xs_b, ycb - 5.08, "R")
        d_ = S.two(dref, xb, ycb - 7.62, "v", first="DRV_SUP", text="l")
        S.w(d_.a, (xb, d_.a[1] - 5.08)); S.label("DRV_SUP", xb, d_.a[1] - 5.08, "R")

    # --- battery current-sense filter (mirror of the input one) and feedback divider
    S.text("Battery current sense across R427", 272, 281)
    ys = 290.0
    S.w((279.0, ys), (294.0, ys)); S.label("BAT_SNS_P", 279.0, ys, "L")
    r428 = S.two(R(28), 294.0, ys, "v", first="BAT_SNS_P")
    hang(C(18), 294.0, r428.b[1], "SRP_F")
    S.stub(r428.b, "L", "SRP_F", 5.08)
    c417 = S.two(C(17), 308.0, r428.b[1], "h", first="SRP_F", text="a")
    S.w(r428.b, c417.a)
    S.pwr("PACK_P", 330.0, ys)
    r429 = S.two(R(29), 330.0, ys, "v", first="PACK_P")
    S.w(c417.b, r429.b)
    hang(C(19), 330.0, r429.b[1], "SRN_F")
    S.stub(r429.b, "R", "SRN_F", 5.08)
    S.text("Battery feedback 16.8 V", 342, 281)
    S.pwr("PACK_P", 358.0, ys)
    r418 = S.two(R(18), 358.0, ys, "v", first="PACK_P")
    r419 = S.two(R(19), 358.0, r418.b[1], "v", first="FB")
    S.stub(r418.b, "L", "FB", 5.08); S.stub(r419.b, "L", "FBG", 5.08)

    # ================= E: 5 V buck =================
    S.text("5 V buck for PP5V (TPS62933)", 378, 230, 1.6)
    S.box(376, 234, 582, 374)
    u4 = S.ic(U(4), 440.0, 300.0)
    vin, en, ss, rt, gn = u4("VIN"), u4("EN"), u4("SS"), u4("RT"), u4("GND")
    bst, sw, fb = u4("BST"), u4("SW"), u4("FB")
    xv, yrl = vin[0] - 7.62, 277.14
    S.pwr("PACK_P", 384.0, yrl)
    S.w(vin, (xv, vin[1]), (xv, yrl), (384.0, yrl))
    hang(C(46), 393.0, yrl, "PACK_P"); hang(C(44), 408.24, yrl, "PACK_P")
    S.w(en, (390.0, en[1])); S.label("EN_5V", 390.0, en[1], "L")
    r432 = hang(R(32), 400.0, en[1], "EN_5V")
    xs5 = ss[0] - 12.0
    S.w(ss, (xs5, ss[1]))
    c439 = S.two(C(39), xs5, ss[1], "v", first="SS_5V", text="l"); S.gnd(*c439.b)
    S.w(rt, (rt[0] - 2.54, rt[1])); S.gside(rt[0] - 2.54, rt[1], "L")
    S.w(gn, (gn[0], gn[1] + 2.54)); S.gnd(gn[0], gn[1] + 2.54)
    xc = bst[0] + 7.62
    S.w(bst, (xc, bst[1]))
    c440 = S.two(C(40), xc, bst[1], "v", first="BST_5V")
    S.w(c440.b, (c440.b[0], sw[1]))
    l402 = S.two(L(2), xc + 16.0, sw[1], "h", first="SW_5V", text="a")
    S.w(sw, l402.a)
    S.w(l402.b, (l402.b[0] + 5.08, sw[1]))
    xo5 = l402.b[0] + 5.08
    r433 = S.two(R(33), xo5 + 8.0, sw[1], "v", first="PP5V")
    r434 = S.two(R(34), xo5 + 8.0, r433.b[1], "v", first="FB_5V")
    S.gnd(*r434.b)
    S.w(fb, (xo5 + 8.0, fb[1]))
    xcap = [xo5 + 30.0 + 15.24 * i for i in range(3)]
    for ref, x in zip((C(41), C(42), C(43)), xcap): hang(ref, x, sw[1], "PP5V")
    S.w((xo5, sw[1]), (xcap[-1] + 12.0, sw[1])); S.label("PP5V", xcap[-1] + 12.0, sw[1], "R")
    S.text("PP5V 5.15 V: 120k / 22k feedback", 480, 322)
    S.pad(f"TP{n + 12}", 30.0, 360.0); S.gnd(30.0, 360.0)
