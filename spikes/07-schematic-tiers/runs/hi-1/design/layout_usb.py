"""One USB-C PD port (used twice): connector and protection, PD controller, BQ25756 charger, four-switch stage,
9 V gate-drive LDO and 5 V buck. Reference numbers follow the port: 4xx for port 1, 5xx for port 2."""
from lay import *


def usb_port(s):
    n = 400 if s.name.endswith("1") else 500
    R = lambda k: f"{n + k}"
    r = lambda pre, k: f"{pre}{n + k}"
    nm = lambda t: f"{s.name}/{t}"
    N = lambda ref, pad: s.netof(ref, pad)
    s.rename.update({nm("C_CC1"): "C_CC1", nm("C_CC2"): "C_CC2"})
    s.header(s.name, "USB-C PD port: TPS25751D PD controller, BQ25756 four-switch buck-boost charger into the pack, 5 V buck and 9 V gate-drive supply")
    c1 = g1_connector(s, n, r, nm)
    g2_pd(s, n, r, nm, c1)
    st = g3_stage(s, n, r, nm, 60.96)
    yh = 116.0
    g4_charger(s, n, r, nm, 76.0, 152.0, yh)
    g5_supply(s, n, r, nm, 190.0, 142.0, yh)
    g6_buck5(s, n, r, nm, 312.0, 142.0, yh)


def g1_connector(s, n, r, nm):
    """USB-C receptacle, VBUS protection, CC and DCP wiring, port protection IC."""
    s.heading("USB-C connector and port protection", 0, -52)
    s.text("D+ and D- tied (dedicated charger); CC through TPD6S300", 0, -47.5)
    j = s.ic(r("J", 1), 0, 0, ref_at=(-8, -23, "left"), val_at=(-8, -21.2, "left"))
    P = j.p
    vb = P("A4")
    yr = -34.29
    s.w(vb, (vb[0] + 2.54, vb[1]), (vb[0] + 2.54, yr))
    xs = [34.29, 62.23, 96.52]
    s.w((vb[0] + 2.54, yr), (xs[-1], yr))
    tvs = s.ic(r("D", 1), xs[2], yr + 7.62, ref_at=(xs[2] - 12, yr + 10.0, "right"), val_at=(xs[2] - 12, yr + 11.8, "right"))
    for pad in ("4", "5", "6"): pass
    s.w((xs[2], yr), tvs.p("IN")); s.gnd(*tvs.p("GND"))
    for ref, x in ((r("C", 6), xs[0]), (r("C", 50), xs[1])):
        c = s.two(ref, x, yr, "v", a=nm("VBUS")); s.gnd(*c.b)
    # D+ and D- tied together: dedicated charging port
    dpins = [P("A7"), P("B7"), P("A6"), P("B6")]
    xb = dpins[0][0] + 2.54
    for p in dpins: s.w(p, (xb, p[1]))
    s.w((xb, dpins[0][1]), (xb, dpins[-1][1]))
    for nmn in ("SBU1", "SBU2"): s.nc(*P(nmn))
    s.w(P("GND"), (P("GND")[0], P("GND")[1])); s.gnd(*P("GND")); s.gnd(*P("SHIELD"))
    # CC lines run straight to the protection IC, which sits on the same rows
    u5 = s.ic(r("U", 5), 57.15, 1.27, ref_at=(41, -19.5, "left"), val_at=(41, -17.7, "left"))
    for pin, net in (("CC1", "C_CC1"), ("CC2", "C_CC2")):
        a, b = P(pin), u5.p(net)
        s.w(a, b)
        s.label((a[0] + b[0]) / 2 - 3, a[1], "R", nm(net), above=True)
    for pin, net in (("RPD_G1", "C_CC1"), ("RPD_G2", "C_CC2")):
        s.netlabel(u5.p(pin), "L", net=nm(net), stub=2.54)
    for pin in ("C_SBU1", "C_SBU2", "D1", "D2", "SBU1", "SBU2"): s.nc(*u5.p(pin))
    g, nc_ = u5.p("GND"), u5.p("N.C.")
    s.w(g, nc_); s.w((g[0], g[1]), (g[0], g[1] + 2.54)); s.gnd(g[0], g[1] + 2.54)
    # supply: VPWR from the port's 3V3 LDO, VBIAS with its capacitor to the right of the body
    vp, vbs = u5.p("VPWR"), u5.p("VBIAS")
    ldo = [x for x in s.nets if x.endswith("LDO_3V3") and x.startswith("/P" + ("1" if n == 400 else "2"))][0]
    s.w(vp, (vp[0], vp[1] - 7.62)); s.rail(vp[0], vp[1] - 7.62, ldo)
    yb = vbs[1] - 5.08
    s.w(vbs, (vbs[0], yb))
    chain(s, (vbs[0], yb), "R", nm("VBIAS"), [2.54, ("p", r("C", 51)), 2.54, ("gnd",)], text="D")
    s.netlabel(u5.p("9"), "R", net=nm("SBU_FLT"), stub=2.54)
    return dict(u5=u5, vbus_pt=(xs[-1], yr), ldo=ldo)


def g2_pd(s, n, r, nm, c1):
    u5, ldo = c1["u5"], c1["ldo"]
    s.heading("USB PD controller TPS25751D", 96, -52)
    s.text("Negotiates the contract; PPHV feeds the charger", 96, -47.5)
    u = s.ic(r("U", 1), 140.97, 0, ref_at=(133, -31, "left"), val_at=(133, -29.2, "left"))
    P = u.p
    # ---- CC lines from the protection IC; C401 and C402 sit in a bump of the lower line ----
    cc1, cc2 = u5.p("CC1"), u5.p("CC2")
    t1, t2 = P("CC1"), P("CC2")
    s.w(cc1, t1)
    xa, xb = cc2[0] + 5.08, 106.68
    ylow = cc2[1] + 12.7
    s.w(cc2, (xa, cc2[1]), (xa, ylow), (xb, ylow), (xb, t2[1]), t2)
    c401 = s.two(r("C", 1), xa + 12.7, cc1[1], "v", a=nm("CC1")); s.gnd(*c401.b)
    c402 = s.two(r("C", 2), xa + 25.4, ylow, "v", a=nm("CC2"), text="L"); s.gnd(*c402.b)
    s.label(xa + 12.7 + 8, cc1[1], "R", nm("CC1"), above=True) if False else None
    # ---- VBUS in ----
    xv = 120.65
    vb = c1["vbus_pt"]
    s.w(vb, (xv, vb[1]), (xv, P("VBUS_IN")[1]), P("VBUS_IN"))
    s.w((xv, P("VBUS_IN")[1]), (xv, P("VBUS")[1]), P("VBUS"))
    # ---- 3V3 in with its capacitor ----
    vin = P("VIN_3V3")
    xr3 = 123.19
    s.w(vin, (xr3, vin[1]), (xr3, vin[1] - 12.7)); s.rail(xr3, vin[1] - 12.7, "3V3")
    s.w((xr3, vin[1] - 6.35), (xr3 - 7.62, vin[1] - 6.35))
    c403 = s.two(r("C", 3), xr3 - 7.62, vin[1] - 6.35, "v", a="3V3", text="L"); s.gnd(*c403.b)
    # ---- unused GPIO to ground through a bus at the left ----
    xg = 111.76
    groups = [("GPIO0", "GPIO1", "GPIO2"), ("GPIO4", "GPIO5"), ("GPIO7", "GPIO11")]
    ys = []
    for grp in groups:
        pts = [P(g) for g in grp]
        xb_ = pts[0][0] - 5.08
        for p in pts: s.w(p, (xb_, p[1]))
        s.w((xb_, pts[0][1]), (xb_, pts[-1][1]))
        ym = pts[len(pts) // 2][1] if len(pts) % 2 else (pts[0][1] + pts[-1][1]) / 2
        s.w((xb_, ym), (xg, ym)); ys.append(ym)
    s.w((xg, ys[0]), (xg, ys[-1])); s.gnd(xg, ys[-1])
    for g, net in (("GPIO3", nm("SBU_FLT")), ("GPIO6", nm("DRV9_OFF"))):
        s.netlabel(P(g), "L", net=net, stub=2.54)
    gnd0 = P("11"); s.w(gnd0, (gnd0[0], gnd0[1] + 2.54)); s.gnd(gnd0[0], gnd0[1] + 2.54)
    # ---- right side ----
    px = P("PPHV")[0]
    ends = s.fan([P("PPHV"), P("PP5V"), P("LDO_1V5")], [-48.26, -35.56, -17.78], "R", base=7.62)
    for (x, y), ref1, ref2, net in ((ends[0], r("C", 9), r("C", 49), nm("PPHV")), (ends[1], r("C", 7), None, nm("PP5V"))):
        xe = x + 12.7 + 19.05 * (1 if ref2 else 0) + 10.16
        s.w((x, y), (xe, y))
        for k, ref in enumerate([ref1, ref2]):
            if ref:
                c = s.two(ref, x + 12.7 + 19.05 * k, y, "v", a=net); s.gnd(*c.b)
        s.label(xe, y, "R", net)
    chain(s, ends[2], "R", nm("LDO_1V5"), [5.08, ("p", r("C", 5)), 2.54, ("gnd",)])
    s.w(P("DRAIN"), (px + 2.54, P("DRAIN")[1]), (px + 2.54, P("DRAIN_EP")[1]), P("DRAIN_EP"))
    # port 3V3 rail with its capacitors, pull-ups and the EEPROM supply
    yl = P("LDO_3V3")[1]
    x1, x2, x3, x4, x5 = px + 63.5, px + 88.9, px + 114.3, px + 132.08, px + 147.32
    s.w(P("LDO_3V3"), (x5 + 7.62, yl), (x5 + 7.62, yl - 5.08)); s.rail(x5 + 7.62, yl - 5.08, ldo)
    for k, ref in enumerate([r("C", 4), r("C", 8), r("C", 52)]):
        c = s.two(ref, px + 17.78 + 13.97 * k, yl, "v", a=ldo); s.gnd(*c.b)
    a1 = P("ADCIN1")
    if s.netof(u.ref, "2") == ldo:
        s.w(a1, (px + 5.08, a1[1]), (px + 5.08, yl))
        a2 = P("ADCIN2"); s.w(a2, (px + 6.35, a2[1])); s.gnd(px + 6.35, a2[1])
    else:
        a2 = P("ADCIN2")
        s.w(a1, (px + 5.08, a1[1]), (px + 5.08, a2[1])); s.w(a2, (px + 5.08, a2[1])); s.gnd(px + 5.08, a2[1])
    for pin, xc_, ref, net in (("I2Cc_SCL", x1, r("R", 3), nm("I2CC_SCL")), ("I2Cc_SDA", x2, r("R", 2), nm("I2CC_SDA")),
                               ("~{I2Cc_IRQ}", x3, r("R", 4), nm("CHG_INT"))):
        p = P(pin)
        s.w(p, (xc_ + 2.54, p[1])); s.label(xc_ + 2.54, p[1], "R", net, above=True)
        pu = s.two(ref, xc_, yl, "v", a=ldo); s.w(pu.b, (xc_, p[1]))
    for xc_, ref, net in ((x4, r("R", 41), nm("SBU_FLT")), (x5, r("R", 55), nm("DRV9_OFF"))):
        pu = s.two(ref, xc_, yl, "v", a=ldo); s.label(xc_, pu.b[1], "D", net) if False else s.netlabel(pu.b, "D", net=net, stub=2.54)
    for pin in ("I2Ct_SCL", "I2Ct_SDA", "~{I2Ct_IRQ}"):
        s.netlabel(P(pin), "R", net=s.netof(u.ref, u.byname[pin]), stub=2.54)
    # ---- EEPROM for the PD controller configuration ----
    ex_ = x5 + 30
    s.heading("Configuration EEPROM", ex_ - 14, -30)
    s.text("PD controller configuration, read over I2C", ex_ - 14, -25.5)
    e = s.ic(r("U", 2), ex_, -2.54, ref_at=(ex_ + 3, -14, "left"), val_at=(ex_ + 3, -12.2, "left"))
    s.w(e.p("VCC"), (e.p("VCC")[0], e.p("VCC")[1] - 5.08)); s.rail(e.p("VCC")[0], e.p("VCC")[1] - 5.08, ldo)
    ap = [e.p("A0"), e.p("A1"), e.p("A2")]
    for p in ap: s.w(p, (p[0] - 5.08, p[1]))
    s.w((ap[0][0] - 5.08, ap[0][1]), (ap[-1][0] - 5.08, ap[-1][1])); s.gnd(ap[-1][0] - 5.08, ap[-1][1])
    for pin in ("SDA", "SCL"):
        s.netlabel(e.p(pin), "R", net=s.netof(e.ref, e.byname[pin]), stub=2.54)
    wp = e.p("WP"); s.w(wp, (wp[0] + 2.54, wp[1])); s.gnd(wp[0] + 2.54, wp[1])
    g_ = e.p("GND"); s.w(g_, (g_[0], g_[1] + 2.54)); s.gnd(g_[0], g_[1] + 2.54)


# ---------------------------------------------------------------------------------------------------------------
def other(s, ref, net):
    """The net on the other pad of a two-pad part."""
    pads = sorted({p for (r, p) in s.pinnet if r == ref})
    n = [s.netof(ref, p) for p in pads]
    return n[1] if n[0] == net else n[0]


def kelvin(s, x, y, rs, rt, rb, cd, ct, cb, na, nb):
    """Kelvin-sensed shunt: the sense resistor `rs` lies in the rail at (x, y) (pad A on net na, pad B on nb); a 10 R
    resistor from each side hangs down into a filter (differential cap between, a cap to ground on each side).
    Returns the two filtered nodes (left, right)."""
    xt, xb = x - 5.08, x + 7.62 + 5.08
    s.two(rs, x, y, "h", a=na, text="U")
    s.w((xt, y), (x, y)); s.w((x + 7.62, y), (xb, y))
    t = s.two(rt, xt, y, "v", a=na, text="L")
    b = s.two(rb, xb, y, "v", a=nb, text="R")
    yf = y + 10.16
    f1, f2 = (xt, yf), (xb, yf)
    s.w(t.b, f1); s.w(b.b, f2)
    s.w(f1, (x, yf)); s.w((x + 7.62, yf), f2)
    s.two(cd, x, yf, "h", a=other(s, rt, na), text="U")
    c1 = s.two(ct, xt, yf, "v", a=other(s, rt, na), text="L"); s.gnd(*c1.b)
    c2 = s.two(cb, xb, yf, "v", a=other(s, rb, nb), text="R"); s.gnd(*c2.b)
    return f1, f2


def g3_stage(s, n, r, nm, y_top):
    """Four-switch buck-boost power stage, left to right: input sense and bulk capacitors, the input half-bridge,
    the inductor, the output half-bridge, output bulk capacitors and sense into PACK_P."""
    N = lambda ref, pad: s.netof(ref, pad)
    s.heading("Four-switch buck-boost power stage", 0, y_top - 14)
    s.text("R424 and R427 sense input and output current (Kelvin filtered); gates driven by U%d" % (n + 3), 0, y_top - 9.5)
    yt = y_top
    pph, ac, bat, pack = N(r("R", 24), "1"), N(r("R", 24), "2"), N(r("R", 27), "1"), N(r("R", 27), "2")
    xl = 7.62
    s.label(xl, yt, "L", pph)
    # input sense with its Kelvin filter
    f1, f2 = kelvin(s, 20.32, yt, r("R", 24), r("R", 25), r("R", 26), r("C", 14), r("C", 15), r("C", 16), pph, ac)
    s.netlabel(f1, "L", net=N(r("C", 14), "1"), stub=2.54)
    s.netlabel(f2, "R", net=N(r("C", 14), "2"), stub=2.54)
    s.w((xl, yt), (15.24, yt))
    # input bulk capacitors on the rail
    xa = 150.0
    caps = [r("C", 30), r("C", 20), r("C", 23), r("C", 24), r("C", 27), r("C", 21), r("C", 56)]
    x0 = 45.72
    xd1 = xa + 8.89
    s.w((33.02, yt), (xd1, yt))
    for k, ref in enumerate(caps):
        c = s.two(ref, x0 + 13.97 * k, yt, "v", a=ac); s.gnd(*c.b)
    # the two half-bridges
    y1 = yt + 17.78
    y2 = y1 + 12.7
    q = r("Q", 1)
    a1 = s.ic(q, xa, y1, unit=1, ref_at=(xa - 3.5, y1 - 9.5, "left"), val_at=(xa - 3.5, y1 - 7.8, "left"))
    a2 = s.ic(q, xa, y2, unit=2, hide="val", ref_at=(xa - 3.5, y2 + 5.0, "left"))
    xb = xa + 40.64
    q2 = r("Q", 2)
    b1 = s.ic(q2, xb, y1, unit=1, mirror=True, ref_at=(xb + 3.5, y1 - 9.5, "right"), val_at=(xb + 3.5, y1 - 7.8, "right"))
    b2 = s.ic(q2, xb, y2, unit=2, mirror=True, hide="val", ref_at=(xb + 3.5, y2 + 5.0, "right"))
    d = a1.p("D1")
    s.w(d, (xd1, d[1]), (xd1, yt))
    # gate resistors on the free side of each half
    for part, pin, ref, side in ((a1, "G1", r("R", 44), "L"), (a2, "G2", r("R", 45), "L"), (b1, "G1", r("R", 46), "R"), (b2, "G2", r("R", 47), "R")):
        pt = part.p(pin)
        chain(s, pt, side, N(part.ref, part.byname[pin]), [2.54, ("p", ref), 2.54, ("label",)])
    # switch nodes and the inductor
    ym = a1.p("SW")[1] + 5.08
    xs1, xs2 = xa + 11.43, xa + 29.21
    s.w(a1.p("SW"), (xs1, a1.p("SW")[1]), (xs1, a2.p("SW")[1]), a2.p("SW"))
    s.w(b1.p("SW"), (xs2, b1.p("SW")[1]), (xs2, b2.p("SW")[1]), b2.p("SW"))
    sw1, sw2 = N(q, "9"), N(q2, "9")
    s.w((xs1, ym), (xs1 + 5.08, ym))
    s.two(r("L", 1), xs1 + 5.08, ym, "h", a=sw1, text="D")
    s.w((xs1 + 12.7, ym), (xs2, ym))
    s.label(xs1 + 2.54, ym, "R", sw1, above=True)
    s.label(xs2 - 2.54, ym, "L", sw2, above=True)
    # output side: BAT_SNS_P rail, caps, sense, PACK_P
    xd2 = xb - 8.89
    d2 = b1.p("D1")
    s.w(d2, (xd2, d2[1]), (xd2, yt))
    xr0 = xb + 6.35 + 12.7
    ocaps = [r("C", 31), r("C", 34), r("C", 38)]
    xk = xr0 + 13.97 * 3 + 5.08
    s.w((xd2, yt), (xk, yt))
    for k, ref in enumerate(ocaps):
        c = s.two(ref, xr0 + 13.97 * k, yt, "v", a=bat); s.gnd(*c.b)
    g1, g2 = kelvin(s, xk + 5.08, yt, r("R", 27), r("R", 28), r("R", 29), r("C", 17), r("C", 18), r("C", 19), bat, pack)
    s.netlabel(g1, "L", net=N(r("C", 17), "1"), stub=2.54)
    s.netlabel(g2, "R", net=N(r("C", 17), "2"), stub=2.54)
    xp = xk + 5.08 + 7.62 + 5.08
    xc0 = xp + 13.97
    pc = [r("C", 44), r("C", 46)]
    xe = xc0 + 13.97 * 2
    s.w((xp, yt), (xe, yt), (xe, yt - 5.08)); s.rail(xe, yt - 5.08, pack)
    for k, ref in enumerate(pc):
        c = s.two(ref, xc0 + 13.97 * k, yt, "v", a=pack); s.gnd(*c.b)
    # bootstrap circuits under each half-bridge
    y3 = y2 + 12.7
    boot(s, xa - 48.26, y3, "L", r("C", 12), r("D", 4), N(r("C", 12), "1"), N(r("C", 12), "2"))
    boot(s, xb + 12.7, y3, "R", r("C", 13), r("D", 5), N(r("C", 13), "1"), N(r("C", 13), "2"))
    # grounds of the two low sides, joined, with the test point
    pa, pb = a2.p("S2"), b2.p("S2")
    yg = pa[1] + 5.08
    s.w(pa, (pa[0], yg), (pb[0], yg), pb)
    xm = snap((pa[0] + pb[0]) / 2)
    s.gnd(xm - 5.08, yg)
    tp = s.one(r("TP", 12), xm + 5.08, yg, "D")
    return dict(xa=xa, y1=y1, y2=y2, yg=yg, xe=xe)


def g4_charger(s, n, r, nm, xu, yu, yhead):
    """BQ25756 charge controller. Pins that serve other circuits carry labels; references, sense filters and the
    configuration resistors sit on the left, feedback divider on the right."""
    N = lambda ref, pad: s.netof(ref, pad)
    s.heading("Charge controller BQ25756", xu - 70, yhead)
    s.text("Pins that feed other circuits leave on labels; CE_N pulled up, CHG_INH through R%d" % (n + 35), xu - 70, yhead + 4.5)
    u = s.ic(r("U", 3), xu, yu, ref_at=(xu - 12, yu - 28.5, "left"), val_at=(xu - 12, yu - 26.7, "left"))
    P = u.p
    xl, xr = xu - 12.7, xu + 12.7
    # ---------------- left side ----------------
    for pin in ("VAC", "ACP", "ACN", "ACUV", "ACOV", "SCL", "SDA", "~{INT}"):
        s.netlabel(P(pin), "L", net=N(u.ref, u.byname[pin]), stub=2.54)
    for pin in ("~{STAT1}", "~{STAT2}", "~{PG}"): s.nc(*P(pin))
    # charge enable: pulled up, driven by the MCU through 1 k
    ce = P("~{CE}")
    xc = xl - 20.32
    s.w(ce, (xc, ce[1]))
    s.two(r("R", 17), xc, ce[1] - 7.62, "v", a="3V3", text="R")
    s.rail(xc, ce[1] - 7.62, "3V3")
    chain(s, (xc, ce[1]), "L", N(r("R", 17), "1"), [2.54, ("p", r("R", 35)), 2.54, ("label",)])
    # FSW, ICHG, ILIM, TS
    e2 = s.fan([P("FSW_SYNC"), P("ICHG"), P("ILIM_HIZ"), P("TS")], [yu + 17.78, yu + 27.94, yu + 38.1, yu + 53.34], "L", base=5.08)
    chain(s, e2[0], "L", N(r("R", 12), "1"), [2.54, ("p", r("R", 12), "D"), 2.54, ("gnd",)])
    chain(s, e2[1], "L", N(r("R", 13), "1"), [2.54, ("p", r("R", 13)), 2.54, ("gnd",)])
    chain(s, e2[2], "L", N(r("R", 14), "1"), [2.54, ("p", r("R", 14)), 2.54, ("gnd",)])
    xt = xl - 20.32
    ts = e2[3]
    s.w(ts, (xt, ts[1]))
    rr = s.two(r("R", 15), xt, ts[1] - 7.62, "v", a=N(r("R", 15), "1"), text="L")
    s.netlabel(rr.a, "L", net=N(r("R", 15), "1"), stub=2.54)
    for ref, x, tx in ((r("R", 16), xt, "R"), (r("TH", 1), xt - 15.24, "L")):
        c = s.two(ref, x, ts[1], "v", a=N(ref, "1"), text=tx); s.gnd(*c.b)
    s.w((xt, ts[1]), (xt - 15.24, ts[1]))
    # ACUV / ACOV divider on the input rail, drawn at the left with its taps labelled
    xd = xl - 27.0
    ya = P("ACUV")[1] + 5.08
    d1 = s.two(r("R", 9), xd, ya - 15.24, "v", a=nm("PPHV"), text="L")
    d2 = s.two(r("R", 10), xd, ya - 7.62, "v", a=N(r("R", 10), "1"), text="L")
    d3 = s.two(r("R", 11), xd, ya, "v", a=N(r("R", 11), "1"), text="L"); s.gnd(*d3.b)
    s.netlabel(d1.a, "R", net=nm("PPHV"), stub=2.54)
    s.netlabel(d2.a, "R", net=N(r("R", 10), "1"), stub=2.54)
    s.netlabel(d3.a, "R", net=N(r("R", 11), "1"), stub=2.54)
    # ---------------- right side: every pin leaves on a label ----------------
    names = ["HIDRV1", "BTST1", "SW1", "LODRV1", "HIDRV2", "BTST2", "SW2", "LODRV2", "SRP", "SRN", "FB", "FBG", "REGN", "DRV_SUP"]
    for nme in names:
        s.netlabel(P(nme), "R", net=N(u.ref, u.byname[nme]), stub=2.54)
    s.nc(*P("15"))
    pg = P("PGND"); s.w(pg, (pg[0], pg[1] + 2.54)); s.gnd(pg[0], pg[1] + 2.54)
    # output voltage divider
    xf = xr + 34.29
    yf = P("FB")[1]
    top = s.two(r("R", 18), xf, yf - 7.62, "v", a=N(r("R", 18), "1"), text="R"); s.rail(xf, yf - 7.62, N(r("R", 18), "1"))
    bot = s.two(r("R", 19), xf, yf, "v", a=N(u.ref, u.byname["FB"]), text="R")
    s.text("Output feedback divider", xf - 10, yf + 15)
    s.netlabel(top.b, "L", net=N(u.ref, u.byname["FB"]), stub=2.54)
    s.netlabel(bot.b, "L", net=N(u.ref, u.byname["FBG"]), stub=2.54)
    return u


def boot(s, x, y, side, cb, db, bt, sw):
    """Bootstrap cap and diode of one half-bridge on one row: DRV_SUP - diode - BTST - cap - SW."""
    N = lambda ref, pad: s.netof(ref, pad)
    drv = N(db, "2")
    if side == "L":
        s.label(x, y, "L", drv)
        chain(s, (x, y), "R", drv, [2.54, ("p", db), 2.54])
        xb = x + 2.54 + 7.62 + 2.54
        s.label(xb + 2.54, y, "R", bt, above=True)
        chain(s, (xb, y), "R", bt, [10.16, ("p", cb), 2.54, ("label",)])
    else:
        s.label(x, y, "L", sw)
        chain(s, (x, y), "R", sw, [2.54, ("p", cb), 2.54])
        xb = x + 2.54 + 7.62 + 2.54
        s.label(xb + 2.54, y, "R", bt, above=True)
        chain(s, (xb, y), "R", bt, [10.16, ("p", db), 2.54, ("label",)])


def g5_supply(s, n, r, nm, x9, y9, yhead):
    """Gate-drive supply: 9 V linear regulator off the pack, REGN and the 9 V OR-ed into DRV_SUP through diodes."""
    N = lambda ref, pad: s.netof(ref, pad)
    s.heading("Gate-drive supply: 9 V LDO and DRV_SUP", x9 - 62, yhead)
    s.text("REGN and the 9 V OR-ed into DRV_SUP; DRV9_OFF turns the LDO off", x9 - 62, yhead + 4.5)
    u = s.ic(r("U", 6), x9, y9, ref_at=(x9 - 9, y9 - 12.5, "left"), val_at=(x9 - 9, y9 - 10.7, "left"))
    P = u.p
    pack, v9, v9fb, en = N(u.ref, "8"), N(u.ref, "1"), N(u.ref, "2"), N(u.ref, "5")
    pin_, pen = P("IN"), P("EN")
    xin = x9 - 58.42
    s.w(pin_, (xin, pin_[1]), (xin, pin_[1] - 7.62)); s.rail(xin, pin_[1] - 7.62, pack)
    c = s.two(r("C", 57), xin + 7.62, pin_[1], "v", a=pack, text="R"); s.gnd(*c.b)
    # enable: pulled up from REGN, pulled down by the MCU through a small FET
    xen = x9 - 22.86
    q = s.ic(r("Q", 9), x9 - 38.1, pen[1] + 7.62, ref_at=(x9 - 32, pen[1] + 14.5, "left"), val_at=(x9 - 32, pen[1] + 16.3, "left"))
    s.w(pen, (xen, pen[1]), (q.p("D")[0], pen[1]), q.p("D"))
    ru = s.two(r("R", 54), xen, pen[1], "v", a=en, text="R")
    s.netlabel(ru.b, "D", net=N(r("R", 54), "2"), stub=2.54)
    s.netlabel(q.p("G"), "L", net=N(q.ref, "1"), stub=2.54)
    s.w(q.p("S"), (q.p("S")[0], q.p("S")[1] + 2.54)); s.gnd(q.p("S")[0], q.p("S")[1] + 2.54)
    g = P("4"); s.w(g, (g[0], g[1] + 2.54)); s.gnd(g[0], g[1] + 2.54)
    # output and feedback divider
    po, pf = P("OUT"), P("FB")
    xf = x9 + 22.86
    s.w(po, (xf + 15.24, po[1]))
    s.w(pf, (xf, pf[1]))
    s.two(r("R", 52), xf, po[1], "v", a=v9, text="R")
    d = s.two(r("R", 53), xf, pf[1], "v", a=v9fb, text="R"); s.gnd(*d.b)
    c = s.two(r("C", 58), xf + 15.24, po[1], "v", a=v9, text="R"); s.gnd(*c.b)
    chain(s, (xf + 15.24, po[1]), "R", v9, [20.32, ("p", r("D", 11)), 2.54, ("label",)])
    # REGN into DRV_SUP
    yd = y9 + 27.94
    x0 = x9 - 10.16
    regn = N(r("C", 10), "1")
    s.label(x0, yd, "L", regn)
    s.w((x0, yd), (x0 + 12.7, yd))
    c = s.two(r("C", 10), x0 + 7.62, yd, "v", a=regn, text="L"); s.gnd(*c.b)
    chain(s, (x0 + 12.7, yd), "R", regn, [("p", r("D", 10), "U"), 7.62])
    xc = x0 + 12.7 + 7.62 + 7.62
    drv = N(r("C", 11), "1")
    c = s.two(r("C", 11), xc, yd, "v", a=drv, text="R"); s.gnd(*c.b)
    s.w((xc, yd), (xc + 7.62, yd)); s.label(xc + 7.62, yd, "R", drv)
    return u


def g6_buck5(s, n, r, nm, x5, y5, yhead):
    """5 V buck for the port's 5 V output."""
    N = lambda ref, pad: s.netof(ref, pad)
    s.heading("5 V buck TPS62933", x5 - 40, yhead)
    s.text("5 V rail from the pack; enabled by the MCU", x5 - 40, yhead + 4.5)
    u = s.ic(r("U", 4), x5, y5, ref_at=(x5 - 7, y5 - 14.5, "left"), val_at=(x5 - 7, y5 - 12.7, "left"))
    P = u.p
    pack, en = N(u.ref, "3"), N(u.ref, "2")
    vin, pen = P("VIN"), P("EN")
    xv = x5 - 25.4
    s.w(vin, (xv, vin[1]), (xv, vin[1] - 5.08)); s.rail(xv, vin[1] - 5.08, pack)
    xe = x5 - 22.86 - 5.08
    s.w(pen, (xe, pen[1]))
    s.w((xe, pen[1]), (xe - 5.08, pen[1])); s.label(xe - 5.08, pen[1], "L", en)
    d = s.two(r("R", 32), xe, pen[1], "v", a=en, text="L"); s.gnd(*d.b)
    # soft start and ground
    pss, prt = P("SS"), P("RT")
    xs = x5 - 15.24
    s.w(pss, (xs, pss[1]))
    c = s.two(r("C", 39), xs, pss[1], "v", a=N(r("C", 39), "1"), text="L"); s.gnd(*c.b)
    gp = P("GND")
    yg = gp[1] + 5.08
    s.w(prt, (prt[0] - 2.54, prt[1]), (prt[0] - 2.54, yg), (gp[0], yg), gp)
    s.gnd(gp[0], yg)
    # bootstrap cap, inductor, output
    xcb = x5 + 17.78
    bst, sw = P("BST"), P("SW")
    s.w(bst, (xcb, bst[1])); s.w(sw, (xcb, sw[1]))
    s.two(r("C", 40), xcb, bst[1], "v", a=N(r("C", 40), "1"), text="L")
    xl = xcb + 5.08
    s.w((xcb, sw[1]), (xl, sw[1]))
    s.two(r("L", 2), xl, sw[1], "h", a=N(r("L", 2), "1"), text="U")
    xo = xl + 7.62 + 7.62
    s.w((xl + 7.62, sw[1]), (xo, sw[1]))
    pp5 = N(r("L", 2), "2")
    fb = P("FB")
    s.w(fb, (xo, fb[1]))
    s.two(r("R", 33), xo, sw[1], "v", a=pp5, text="R")
    d = s.two(r("R", 34), xo, fb[1], "v", a=N(r("R", 34), "1"), text="R"); s.gnd(*d.b)
    xcap = xo + 15.24
    xend = xcap + 13.97 * 2 + 12.7
    s.w((xo, sw[1]), (xend, sw[1]))
    for k, ref in enumerate((r("C", 41), r("C", 42), r("C", 43))):
        c = s.two(ref, xcap + 13.97 * k, sw[1], "v", a=pp5, text="R"); s.gnd(*c.b)
    s.label(xend, sw[1], "R", pp5)
    return u
