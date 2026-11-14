"""USB port sheet (both ports): hand-composed picture, parameterised by the reference base (400 or 500)."""
from lay import CHW


def layout_usb(c, b):
    R = lambda l, k: f"{l}{b + k}"
    N = lambda ref, pin: c.net(ref, pin)
    c.s.paper = (420, 400)
    ldo = N(R("U", 1), 1)
    c.RAILS = {ldo}
    GND = "GND"
    PN = lambda n: f"P{b // 100 - 3}_{n}"

    def hang(ref, x, y, net, side="R"):
        """Cap or resistor hanging from a wire at (x, y), its far pad to ground by a symbol."""
        p = c.vp(ref, x, y + 6.35, net, side=side)
        c.w((x, y), p.top); c.w(p.bot, (x, p.bot[1] + 2.54)); c.end(x, p.bot[1] + 2.54, GND)
        return p

    def gbus(pl, keys, xb, d="L", skip=()):
        """Tie ground pins on one side of an IC together with a vertical bus and one sideways ground."""
        ys = [pl(k)[1] for k in keys]
        for k in keys:
            c.w(pl(k), (xb, pl(k)[1])); pl.__dict__.setdefault("handled", set()).add(pl(k))
        c.w((xb, min(ys)), (xb, max(ys)))
        ym = ys[len(ys) // 2]
        sg = -1 if d == "L" else 1
        c.w((xb, ym), (xb + sg * 2.54, ym)); c.gnd_side(xb + sg * 2.54, ym, d)

    # ======================= row 1 left: connector and port protection =======================
    c.frame(12.7, 12.7, 408, 120, "USB-C port: connector and protection (TPD6S300), PD controller TPS25751D, EEPROM, I2C pull-ups")
    j = c.place(R("J", 1), 38.1, 50.8, ref_at=(22, 25.5), val_at=(22, 27.5), just="left")
    jt = j("A4")[0]; yv = j("A4")[1]
    xd = jt + 3.81
    ys = [j(k)[1] for k in ("A7", "B7", "A6", "B6")]
    for k in ("A7", "B7", "A6", "B6"): c.w(j(k), (xd, j(k)[1]))
    c.w((xd, min(ys)), (xd, max(ys)))
    for k in ("A8", "B8"): c.nc(*j(k))
    pg = j("A1"); psh = j("SH"); yg = pg[1] + 2.54
    c.w(pg, (pg[0], yg)); c.w(psh, (psh[0], yg)); c.w((psh[0], yg), (pg[0], yg)); c.end(pg[0], yg, GND)
    u5x, u5y = 140.97, 83.82
    u5 = c.place(R("U", 5), u5x, u5y, ref_at=(u5x + 19, u5y + 17.5), val_at=(u5x + 19, u5y + 19.5), just="left")
    cc1y, cc2y = u5("C_CC1")[1], u5("C_CC2")[1]
    c.w(j("A5"), (66.04, j("A5")[1]), (66.04, cc1y), u5("C_CC1"))
    c.w(j("B5"), (60.96, j("B5")[1]), (60.96, cc2y), u5("C_CC2"))
    c.lab(63.5, 71.0, "C_CC1", "R") if False else None
    c.lab(78.0, cc1y, "C_CC1", "R"); c.lab(78.0, cc2y, "C_CC2", "R")
    c.pin_end(u5, "RPD_G1", 2.54); c.pin_end(u5, "RPD_G2", 2.54)
    for k in ("C_SBU1", "C_SBU2", "D1", "D2", "SBU1", "SBU2"): c.pin_end(u5, k)
    # supply and bias of the protection chip, decoupled above it
    pv = u5("VPWR"); pb = u5("VBIAS")
    c.w(pv, (pv[0], 50.8)); c.pwr(pv[0], 50.8, ldo)
    p2 = hang(R("C", 52), pv[0] - 6.35, 50.8, ldo, side="L")
    c.w((pv[0], 50.8), (pv[0] - 6.35, 50.8))
    c.w(pb, (pb[0], 54.61), (pb[0] + 7.0, 54.61))
    hang(R("C", 51), pb[0] + 7.0, 54.61, N(R("C", 51), 1), side="R")
    c.pin_end(u5, "9", 2.54)
    u5.__dict__.setdefault("handled", set()).update({pv, pb})
    gp = [k for k in ("8", "13", "18", "21")]
    yb = u5("8")[1] + 2.54
    for k in ("8", "13", "18", "21", "16", "17"):
        c.w(u5(k), (u5(k)[0], yb))
    c.w((u5("8")[0], yb), (u5("16")[0], yb)); c.end(u5("8")[0], yb, GND)
    u5.__dict__.setdefault("handled", set()).update({u5(k) for k in ("8", "13", "18", "21", "16", "17")})
    c.rest(u5)

    # VBUS rail: connector, TVS and caps, on to the PD controller
    xU, yU = 232.0, 82.55
    u1 = c.place(R("U", 1), xU, yU, ref_at=(xU - 14, 53.2), val_at=(xU - 14, 55.0), just="left")
    xdrop = u1("32")[0] - 5.08
    c.w(j("A4"), (xdrop, yv), (xdrop, u1("32")[1]))
    d1x = 80.01
    d1 = c.place(R("D", 1), d1x, yv + 7.62, ref_at=(d1x - 5, 58.6), val_at=(d1x - 5, 60.6), just="left")
    c.w(d1("4"), (d1("4")[0], yv)); c.end(*d1("1"), GND)
    xe, ybank, xn = c.bank([R("C", 6), R("C", 50)], 92.71, yv, N(R("C", 6), 1), GND)
    c.w((xdrop, u1("23")[1]), (xdrop, u1("32")[1]))
    for k in ("23", "32"): c.w(u1(k), (xdrop, u1(k)[1])); u1.__dict__.setdefault("handled", set()).add(u1(k))
    c.lab(jt + 3.81, yv, "VBUS", "R") if False else None
    c.text("VBUS", jt + 4.0, yv - 0.8, 1.27)

    # ======================= row 1 right: PD controller =======================
    H = u1.__dict__.setdefault("handled", set())
    # CC lines from the protection chip, shunt caps on them
    x5 = u5("CC1")[0]
    c.w(u5("CC1"), (u5x + 22.86, u5("CC1")[1]), (u5x + 22.86, 50.8), (204.0, 50.8), (204.0, u1("CC1")[1]), u1("CC1"))
    c.w(u5("CC2"), u1("CC2"))
    H.update({u1("CC1"), u1("CC2")})
    hang(R("C", 1), 172.0, 50.8, N(R("C", 1), 1))
    hang(R("C", 2), 165.1, u1("CC2")[1] - 0.0, N(R("C", 2), 1))
    # 3V3 supply with its decoupling above
    p3 = u1("VIN_3V3"); H.add(p3)
    xs3 = p3[0] - 2.54
    c.w(p3, (xs3, p3[1]), (xs3, 44.45)); c.pwr(xs3, 44.45, "3V3")
    c.w((xs3, 47.0), (xs3, 47.0))
    hcap(c, R("C", 3), xs3, 47.0, "R", below=True)
    # grounds, pull-ups and flags on the left side
    gbus(u1, ["5", "6", "7"], u1("5")[0] - 3.81)
    gbus(u1, ["26", "27"], u1("26")[0] - 3.81)
    gbus(u1, ["36", "13"], u1("36")[0] - 3.81)
    # SBU_FLT with its pull-up
    ps = u1("19"); H.add(ps)
    xr = 204.0
    c.w(ps, (xr, ps[1]), (xr - 2.54, ps[1]))
    r441 = c.vp(R("R", 41), xr, ps[1] - 3.81, ldo, side="L")
    c.w(r441.bot, (xr, ps[1])); c.w(r441.top, (xr, r441.top[1] - 2.54)); c.lab(xr, r441.top[1] - 2.54, ldo, "R")
    c.lab(xr - 2.54, ps[1], N(R("U", 1), 19), "L")
    pd = u1("37"); H.add(pd)
    xr2 = 188.0
    c.w(pd, (xr2 - 2.54, pd[1]))
    r455 = c.vp(R("R", 55), xr2, pd[1] - 3.81, ldo, side="L")
    c.w(r455.bot, (xr2, pd[1])); c.w(r455.top, (xr2, r455.top[1] - 2.54)); c.lab(xr2, r455.top[1] - 2.54, ldo, "L")
    c.lab(xr2 - 2.54, pd[1], N(R("U", 1), 37), "L")
    # right side: PPHV rail with caps, PP5V, drain strap, LDO outputs
    pp = u1("PPHV"); H.add(pp)
    xp = pp[0] + 3.81
    c.w(pp, (xp, pp[1]), (xp, 47.0)); c.pwr(xp, 47.0, N(R("U", 1), 20), PN("PPHV"))
    xe2, yb2, _ = c.bank([R("C", 9), R("C", 49)], 280.0, 47.0, N(R("C", 9), 1), GND)
    c.w((xp, 47.0), (280.0, 47.0))
    p5 = u1("PP5V"); H.add(p5)
    x5v = p5[0] + 9.0
    c.w(p5, (x5v, p5[1]), (x5v, 56.5)); c.pwr(x5v, 56.5, N(R("U", 1), 34), PN("PP5V"))
    hcap(c, R("C", 7), x5v, p5[1], "R")
    pdn = u1("15"); H.update({u1("15"), u1("40")})
    c.w(u1("15"), (xp, u1("15")[1])); c.w(u1("40"), (xp, u1("40")[1])); c.w((xp, u1("15")[1]), (xp, u1("40")[1]))
    c.lab(xp, (u1("15")[1] + u1("40")[1]) / 2, N(R("U", 1), 15), "R") if False else None
    c.text("PD_DRAIN", xp + 1.5, u1("15")[1] + 1.8, 1.27)
    pl1 = u1("LDO_1V5"); H.add(pl1)
    hcap(c, R("C", 5), pl1[0] + 2.54, pl1[1], "R"); c.w(pl1, (pl1[0] + 2.54, pl1[1]))
    pl3 = u1("1"); H.add(pl3)
    yr = pl3[1]
    xend = 350.0
    c.w(pl3, (xend, yr))
    c.pwr(292.1, yr, ldo)
    pa = u1("ADCIN1"); H.add(pa)
    if N(R("U", 1), 2) == ldo:
        c.w(pa, (pa[0] + 5.08, pa[1]), (pa[0] + 5.08, yr))
    else:
        c.pin_end(u1, "ADCIN1")
    pa2 = u1("ADCIN2"); H.add(pa2); c.w(pa2, (pa2[0] + 2.54, pa2[1])); c.gnd_side(pa2[0] + 2.54, pa2[1], "R")
    # I2C pull-ups on the controller-side bus, each straight onto its signal line
    for ref, key, xi in ((R("R", 3), "17", 266.0), (R("R", 2), "16", 280.0), (R("R", 4), "18", 294.0)):
        pin = u1(key); H.add(pin); y = pin[1]
        rp = c.vp(ref, xi, yr + 2.54 + 3.81, ldo)
        c.w((xi, yr), rp.top); c.w(rp.bot, (xi, y)); c.w(pin, (xi, y))
        c.lab(xi - 1.27, y, N(R("U", 1), key), "L")
        c.juncs.add((xi, yr))
    hang(R("C", 4), 306.0, yr, ldo); hang(R("C", 8), 318.0, yr, ldo)
    # EEPROM
    u2 = c.place(R("U", 2), 350.0, yr + 7.62, ref_at=(358, 70), val_at=(358, 72), just="left")
    H2 = u2.__dict__.setdefault("handled", set())
    gbus(u2, ["1", "2", "3"], u2("1")[0] - 3.81)
    c.pin_end(u2, "7"); c.pin_end(u2, "5"); c.pin_end(u2, "6"); c.pin_end(u2, "4")
    H2.add(u2("8"))
    c.rest(u2)
    # tool-side I2C, interrupt: leave by global label
    c.rest(u1)
    power_stage(c, b, R, N, hang, GND)
    charger(c, b, R, N, hang, GND)
    buck5(c, b, R, N, hang, GND)
    ldo9(c, b, R, N, hang, GND)


def hcap(c, ref, x, y, d="R", below=False):
    """Shunt cap lying along a wire: the signal pad on the line at (x, y), the far pad ending in a sideways ground."""
    sg = 1 if d == "R" else -1
    nums, ns = c.ends(ref)
    gn = nums[ns.index("GND")]; sig = [n for n in nums if n != gn][0]
    a = c.orient2(ref, (sig, "L" if d == "R" else "R"))
    xc = x + sg * 3.81
    xt = xc + (2.5 if d == "R" else -2.5)
    pl = c.place(ref, xc, y, a, ref_at=(xt, y + (2.8 if below else -4.6)), val_at=(xt, y + (4.6 if below else -2.8)), just="center")
    near, far = pl.pos[sig], pl.pos[gn]
    c.w((x, y), near); c.w(far, (far[0] + sg * 2.54, y)); c.gnd_side(far[0] + sg * 2.54, y, d)
    return pl



def power_stage(c, b, R, N, hang, GND):
    PN = lambda n: f"P{b // 100 - 3}_{n}"
    Y0 = 126.0
    c.frame(12.7, Y0, 408, Y0 + 70, "Four-switch power stage: PPHV -> Q401/L401/Q402 -> PACK_P (0R gate resistors are tuning positions)")
    yp = 144.78
    pphv = N(R("U", 1), 20)
    c.pwr(22.86, yp, pphv, PN("PPHV"))
    r424 = c.hp(R("R", 24), 38.1, yp, pphv, txt="mid")
    c.w((22.86, yp), r424.lft)
    xs0 = 58.42
    refs = [R("C", k) for k in (20, 21, 23, 24, 27, 30, 56)]
    xe, ybank, xn = c.bank(refs, xs0, yp, N(R("C", 20), 1), GND, pitch=12.7)
    c.w(r424.rgt, (xs0, yp))
    c.lab(r424.rgt[0] + 3.0, yp, N(R("C", 20), 1), "R")
    xq = 170.18
    cy1 = yp + 15.24; cy2 = cy1 + 12.7
    q1 = c.place(R("Q", 1), xq, cy1, unit=1, ref_at=(xq - 6, cy1 - 8.6), val_at=(xq - 6, cy1 - 6.7), just="left")
    q2 = c.place(R("Q", 1), xq, cy2, unit=2, ref_at=(xq - 6, cy2 + 5.2), val_at=(xq - 6, cy2 + 7.1), just="left")
    xd = q1("D1")[0] + 3.81
    c.w((xe, yp), (xd, yp), (xd, q1("D1")[1])); c.w(q1("D1"), (xd, q1("D1")[1]))
    xsw = q1("SW")[0] + 7.62
    ysw1 = q1("SW")[1]; ysw2 = q2("SW")[1]
    c.w(q1("SW"), (xsw, ysw1), (xsw, ysw2)); c.w(q2("SW"), (xsw, ysw2))
    ps2 = q2("S2"); c.w(ps2, (ps2[0] + 2.54, ps2[1])); c.gdown(ps2[0] + 2.54, ps2[1])
    for k, ref in ((q1("G1"), R("R", 44)), (q2("G2"), R("R", 45))):
        net = N(ref, 1) if N(ref, 1) and "HG" not in N(ref, 1) and "LG" not in N(ref, 1) else N(ref, 2)
        xl, nn = c.chain(k[0], k[1], [ref], N(R("Q", 1), "1" if ref == R("R", 44) else "8"))
        c.lab(xl - 2.54, k[1], nn, "L"); c.w((xl, k[1]), (xl - 2.54, k[1]))
    # inductor between the two half bridges
    ymid = (ysw1 + ysw2) / 2
    ind = c.hp(R("L", 1), xsw + 18.0, ymid, N(R("L", 1), 1), txt="mid")
    c.w((xsw, ymid), ind.lft)
    c.lab(xsw, ymid, N(R("Q", 1), "9"), "R") if False else None
    c.lab(xsw, ysw1 + 2.0, N(R("Q", 1), "9"), "R")
    xsw2 = xsw + 36.0
    c.w(ind.rgt, (xsw2, ymid))
    c.lab(xsw2, ysw1 + 2.0, N(R("Q", 2), "9"), "L")
    xq2 = xsw2 + 14.0 - 0.0
    m1 = c.place(R("Q", 2), xq2, cy1, unit=1, mirror=True, ref_at=(xq2 - 6, cy1 - 8.6), val_at=(xq2 - 6, cy1 - 6.7), just="left")
    m2 = c.place(R("Q", 2), xq2, cy2, unit=2, mirror=True, ref_at=(xq2 - 6, cy2 + 5.2), val_at=(xq2 - 6, cy2 + 7.1), just="left")
    c.w(m1("SW"), (xsw2, m1("SW")[1]), (xsw2, m2("SW")[1])); c.w(m2("SW"), (xsw2, m2("SW")[1]))
    xd2 = m1("D1")[0] - 3.81
    c.w(m1("D1"), (xd2, m1("D1")[1]), (xd2, yp))
    pS = m2("S2"); c.w(pS, (pS[0] - 2.54, pS[1])); c.gdown(pS[0] - 2.54, pS[1])
    for k, ref, pn in ((m1("G1"), R("R", 46), "1"), (m2("G2"), R("R", 47), "8")):
        gnet = N(R("Q", 2), pn)
        r = c.hp(ref, k[0] + 14.0, k[1], gnet, txt="line")
        c.w(k, r.lft)
        # r.lft here is the pad on the gate net; the other pad leaves by label
        c.w(r.rgt, (r.rgt[0] + 2.54, k[1])); c.lab(r.rgt[0] + 2.54, k[1], N(ref, 1) if N(ref, 1) != gnet else N(ref, 2), "R")
    # BAT_SNS_P rail: caps, sense resistor, PACK_P
    bat = N(R("Q", 2), "2")
    xb0 = m1("G1")[0] + 36.0
    xe2, yb2, xn2 = c.bank([R("C", 31), R("C", 34), R("C", 38)], xb0, yp, bat, GND, pitch=12.7)
    c.w((xd2, yp), (xb0, yp))
    c.lab(xd2 + 3.0, yp, bat, "R")
    r427 = c.hp(R("R", 27), xn2 + 8.0, yp, bat, txt="mid")
    c.w((xe2, yp), r427.lft)
    xo = xn2 + 22.0
    c.note(20.0, Y0 + 62.0, ["Buck-boost: Q401 is the input half bridge, Q402 the output half bridge, L401 between the SW1 and SW2 nodes. R424 (input) and R427 (output) are the 5 mR current-sense shunts read by the controller."], size=1.27)
    xe3, yb3, xn3 = c.bank([R("C", 44), R("C", 46)], xo, yp, "PACK_P", GND, pitch=12.7)
    c.w(r427.rgt, (xo, yp))
    c.w((xe3, yp), (xe3 + 10.0, yp)); c.lab(xe3 + 10.0, yp, "PACK_P", "R")


def charger(c, b, R, N, hang, GND):
    PN = lambda n: f"P{b // 100 - 3}_{n}"
    Y0 = 214.0
    c.frame(12.7, Y0, 252, 382, "BQ25756 buck-boost charger: controller and current sense")
    ux, uy = 140.0, 276.86
    u = c.place(R("U", 3), ux, uy, ref_at=(ux - 10, uy - 28.5), val_at=(ux - 10, uy - 26.5), just="left")
    H = u.__dict__.setdefault("handled", set())
    # ---------------- right side: lanes out to the power stage, boot parts, sense filter, feedback ----------------
    keys = ["27", "26", "28", "25", "19", "20", "18", "21", "14", "13", "12", "11", "24", "23"]
    ys = [224.0, 231.62, 239.24, 246.86, 256.0, 263.62, 271.24, 278.86, 290.0, 310.32, 330.0, 337.62, 350.0, 357.62]
    ln = c.lanes(u, keys, "R", ys)
    L = dict(zip(keys, ln))
    X = ln[0][0]
    def lend(k, x, net=None, stub=2.54):
        xs, y = L[k]; c.w((xs, y), (x, y)); c.w((x, y), (x + stub, y)); c.lab(x + stub, y, net or N(R("U", 3), k), "R")
    lend("27", X + 4.0); lend("25", X + 4.0); lend("19", X + 4.0); lend("21", X + 4.0)
    for kb, ks, kh, di, ca in (("26", "28", "27", R("D", 4), R("C", 12)), ("20", "18", "19", R("D", 5), R("C", 13))):
        yb_, ysw = L[kb][1], L[ks][1]
        c.w(L[kb], (X + 22.0, yb_))
        d = c.vp(di, X + 22.0, yb_ - 3.81, N(di, 1) if N(di, 1) == N(R("U", 3), "23") else N(di, 2), side="R")
        c.w(d.bot, (X + 22.0, yb_)); c.w(d.top, (X + 22.0, d.top[1] - 2.54)); c.lab(X + 22.0, d.top[1] - 2.54, N(R("U", 3), "23"), "R")
        c.w(L[kb], (X + 34.0, yb_))
        cp = c.vp(ca, X + 34.0, yb_ + 3.81, N(R("U", 3), kb), side="R")
        c.w(L[ks], (X + 34.0, ysw)); c.juncs.add((X + 34.0, ysw))
        c.w(cp.bot, (X + 34.0, ysw))
        c.w((X + 34.0, ysw), (X + 40.0, ysw)); c.lab(X + 40.0, ysw, N(R("U", 3), ks), "R")
    # SRP/SRN sense filter
    ysp, ysn = L["14"][1], L["13"][1]
    pf = N(R("U", 3), "14"); nf = N(R("U", 3), "13")
    xc = X + 22.0
    c.w(L["14"], (X + 30.0, ysp)); c.w(L["13"], (X + 30.0, ysn))
    c417 = c.vp(R("C", 17), xc, (ysp + ysn) / 2, pf, side="R")
    c.w((xc, ysp), c417.top); c.w((xc, ysn), c417.bot)
    c.juncs.add((xc, ysp)); c.juncs.add((xc, ysn))
    xg = X + 10.0
    hang(R("C", 18), xg, ysp, pf, side="L"); hang(R("C", 19), xg, ysn, nf, side="L")
    r428 = c.hp(R("R", 28), X + 42.0, ysp, pf, txt="line"); c.w((X + 30.0, ysp), r428.lft)
    c.w(r428.rgt, (r428.rgt[0] + 2.54, ysp)); c.lab(r428.rgt[0] + 2.54, ysp, N(R("R", 28), 1) if N(R("R", 28), 1) != pf else N(R("R", 28), 2), "R")
    r429 = c.hp(R("R", 29), X + 42.0, ysn, nf, txt="line"); c.w((X + 30.0, ysn), r429.lft)
    c.w(r429.rgt, (r429.rgt[0] + 2.54, ysn)); c.lab(r429.rgt[0] + 2.54, ysn, N(R("R", 29), 1) if N(R("R", 29), 1) != nf else N(R("R", 29), 2), "R")
    # feedback divider: R418 to PACK_P, R419 down to FBG
    yfb, yfg = L["12"][1], L["11"][1]
    fb = N(R("U", 3), "12")
    xr = X + 14.0
    c.w(L["12"], (xr + 14.0, yfb)); c.w(L["11"], (xr, yfg))
    r419 = c.vp(R("R", 19), xr, (yfb + yfg) / 2, fb, side="R")
    c.w((xr, yfb), r419.top); c.w(r419.bot, (xr, yfg)); c.juncs.add((xr, yfb))
    r418 = c.hp(R("R", 18), xr + 24.0, yfb, fb, txt="line"); c.w((xr + 14.0, yfb), r418.lft)
    c.w(r418.rgt, (r418.rgt[0] + 2.54, yfb)); c.lab(r418.rgt[0] + 2.54, yfb, "PACK_P", "R")
    # REGN / DRV_SUP
    yr_, yd_ = L["24"][1], L["23"][1]
    regn = N(R("U", 3), "24"); drv = N(R("U", 3), "23")
    xdd = X + 10.0
    c.w(L["24"], (xdd, yr_)); c.w(L["23"], (X + 24.0, yd_))
    c.lab(X + 0.5, yr_, regn, "R"); c.lab(X + 0.5, yd_, drv, "R")
    d410 = c.vp(R("D", 10), xdd, (yr_ + yd_) / 2, regn, side="R")
    c.w((xdd, yr_), d410.top); c.w(d410.bot, (xdd, yd_)); c.juncs.add((xdd, yd_))
    c.w((xdd, yr_), (X + 38.0, yr_))
    hcap(c, R("C", 10), X + 38.0, yr_, "R")
    hang(R("C", 11), X + 22.0, yd_, drv, side="L")
    d411 = c.hp(R("D", 11), X + 50.0, yd_, drv, txt="line")
    c.w((X + 22.0, yd_), d411.lft); c.w(d411.rgt, (d411.rgt[0] + 2.54, yd_)); c.lab(d411.rgt[0] + 2.54, yd_, N(R("D", 11), 2), "R")
    pg = u("17"); H.add(pg); c.w(pg, (pg[0] + 2.54, pg[1])); c.gdown(pg[0] + 2.54, pg[1])
    for k in ("15", "16", "31"): c.pin_end(u, k)
    hang(R("C", 10), X + 16.0, yr_, regn, side="R") if False else None
    # ---------------- left side ----------------
    pv = u("32"); H.add(pv)
    xv = pv[0] - 3.81
    c.w(pv, (xv, pv[1]), (xv, pv[1] - 5.08)); c.pwr(xv, pv[1] - 5.08, N(R("U", 3), "32"), PN("PPHV"))
    lk = ["30", "29", "34", "35", "1", "2", "3", "7", "36", "9", "10", "8"]
    ly = [236.0, 256.32, 266.0, 272.0, 280.0, 285.0, 290.0, 298.0, 306.0, 313.0, 320.0, 328.0]
    ll = c.lanes(u, lk, "L", ly, gap=12.7)
    LL = dict(zip(lk, ll)); XL = ll[0][0]
    for k in ("5", "4", "6"): c.nc(*u(k)); H.add(u(k))
    # input filter: C414 between the lanes, C415 / C416 to ground, R425 / R426 to PPHV and AC_SNS_N
    ya, yn = LL["30"][1], LL["29"][1]
    pa_, pn_ = N(R("U", 3), "30"), N(R("U", 3), "29")
    c414 = c.vp(R("C", 14), XL - 12.0, (ya + yn) / 2, pa_, side="L")
    c.w((XL - 12.0, ya), c414.top); c.w(c414.bot, (XL - 12.0, yn)); c.juncs.add((XL - 12.0, ya)); c.juncs.add((XL - 12.0, yn))
    hang(R("C", 15), XL - 26.0, ya, pa_, side="L"); hang(R("C", 16), XL - 26.0, yn, pn_, side="L")
    for ref, y, lanek in ((R("R", 25), ya, "30"), (R("R", 26), yn, "29")):
        near = N(R("U", 3), lanek)
        far = N(ref, 1) if N(ref, 1) != near else N(ref, 2)
        r = c.hp(ref, XL - 48.0, y, far, txt="line")
        c.w((XL, y), r.rgt)
        if far == N(R("U", 3), "32"):
            c.w(r.lft, (r.lft[0] - 2.54, y), (r.lft[0] - 2.54, y - 2.54)); c.pwr(r.lft[0] - 2.54, y - 2.54, far, PN("PPHV"))
        else:
            c.w(r.lft, (r.lft[0] - 2.54, y)); c.lab(r.lft[0] - 2.54, y, far, "L")
    # window divider, ACUV / ACOV by label
    for k in ("34", "35", "1", "2", "3"):
        xs, y = LL[k]; c.w((xs, y), (xs - 2.54, y)); c.lab(xs - 2.54, y, N(R("U", 3), k), "L")
    xdv = 24.0
    r409 = c.vp(R("R", 9), xdv, 270.0, N(R("R", 9), 1) if "PPHV" in N(R("R", 9), 1) else N(R("R", 9), 2), side="R")
    r410 = c.vp(R("R", 10), xdv, r409.bot[1] + 7.62, N(R("U", 3), "34"), side="R")
    c.w(r409.bot, r410.top)
    r411 = c.vp(R("R", 11), xdv, r410.bot[1] + 7.62, N(R("U", 3), "35"), side="R")
    c.w(r410.bot, r411.top)
    c.w(r411.bot, (xdv, r411.bot[1] + 2.54)); c.end(xdv, r411.bot[1] + 2.54, GND)
    c.w(r409.top, (xdv, r409.top[1] - 2.54)); c.pwr(xdv, r409.top[1] - 2.54, N(R("U", 3), "32"), PN("PPHV"))
    c.w(r409.bot, (xdv + 5.08, r409.bot[1])); c.lab(xdv + 5.08, r409.bot[1], N(R("U", 3), "34"), "R")
    c.w(r410.bot, (xdv + 5.08, r410.bot[1])); c.lab(xdv + 5.08, r410.bot[1], N(R("U", 3), "35"), "R")
    # chip enable: pull-up and inhibit resistor
    yce = LL["7"][1]; xce = XL - 20.0
    c.w((XL, yce), (xce, yce))
    r417 = c.vp(R("R", 17), xce, yce - 3.81, "3V3", side="L")
    c.w((xce, yce), r417.bot); c.w(r417.top, (xce, r417.top[1] - 2.54)); c.pwr(xce, r417.top[1] - 2.54, "3V3")
    r435 = c.hp(R("R", 35), xce - 18.0, yce, "CHG_INH", txt="line")
    c.w((xce, yce), r435.rgt)
    c.w(r435.lft, (r435.lft[0] - 2.54, yce)); c.lab(r435.lft[0] - 2.54, yce, "CHG_INH", "L")
    # programming resistors to ground, sideways
    for k, ref in (("36", R("R", 12)), ("9", R("R", 13)), ("10", R("R", 14))):
        xs, y = LL[k]
        r = c.hp(ref, xs - 14.0, y, GND, txt="line")
        c.w((xs, y), r.rgt)
        c.w(r.lft, (r.lft[0] - 2.54, y)); c.gnd_side(r.lft[0] - 2.54, y, "L")
    # thermistor network on TS
    xs, y = LL["8"]; ts = N(R("U", 3), "8")
    c.w((xs, y), (xs - 44.0, y))
    for ref, x in ((R("R", 16), xs - 10.0), (R("TH", 1), xs - 34.0)):
        p = c.vp(ref, x, y + 6.35, ts, side="R")
        c.w((x, y), p.top); c.w(p.bot, (x, p.bot[1] + 2.54)); c.end(x, p.bot[1] + 2.54, GND)
    r415 = c.hp(R("R", 15), xs - 56.0, y, N(R("R", 15), 1) if N(R("R", 15), 1) != ts else N(R("R", 15), 2), txt="line")
    c.w((xs - 44.0, y), r415.rgt)
    c.w(r415.lft, (r415.lft[0] - 2.54, y)); c.lab(r415.lft[0] - 2.54, y, N(R("R", 15), 1) if N(R("R", 15), 1) != ts else N(R("R", 15), 2), "L")
    c.rest(u)


def buck5(c, b, R, N, hang, GND):
    PN = lambda n: f"P{b // 100 - 3}_{n}"
    X0, Y0 = 258.0, 214.0
    c.frame(X0, Y0, 408, 284, "5 V buck for PP5V (TPS62933), input from PACK_P")
    ux, uy = 308.0, 256.54
    u = c.place(R("U", 4), ux, uy, ref_at=(ux - 7, uy - 17.5), val_at=(ux - 7, uy - 15.5), just="left")
    H = u.__dict__.setdefault("handled", set())
    tl = u("3")[0]
    pin = u("3"); H.add(pin)
    c.w(pin, (tl - 32.0, pin[1])); c.lab(tl - 32.0, pin[1], "PACK_P", "L")
    pe = u("2"); H.add(pe)
    c.w(pe, (tl - 32.0, pe[1])); c.lab(tl - 32.0, pe[1], N(R("U", 4), 2), "L")
    r432 = hang(R("R", 32), tl - 22.0, pe[1], N(R("U", 4), 2), side="L")
    ps = u("7"); H.add(ps)
    c.w(ps, (tl - 8.0, ps[1]))
    hang(R("C", 39), tl - 8.0, ps[1], N(R("U", 4), 7), side="L")
    c.pin_end(u, "1")
    pg = u("4"); H.add(pg)
    c.w(pg, (pg[0], pg[1] + 2.54)); c.end(pg[0], pg[1] + 2.54, GND)
    c.w((pg[0], pg[1] + 2.54), (pg[0] + 10.0, pg[1] + 2.54))
    c.one(R("TP", 12), pg[0] + 10.0, pg[1] + 2.54, "U", txt="R")
    # boot cap between BST and SW, inductor to PP5V
    tr = u("5")[0]
    ysw, ybs = u("5")[1], u("6")[1]
    H.update({u("5"), u("6")})
    xb = tr + 8.0
    c.w(u("6"), (xb, ybs)); c.w(u("5"), (xb + 8.0, ysw))
    cb = c.vp(R("C", 40), xb, (ysw + ybs) / 2, N(R("U", 4), 6), side="R")
    c.w((xb, ybs), cb.top); c.w(cb.bot, (xb, ysw)); c.juncs.add((xb, ysw))
    l402 = c.hp(R("L", 2), xb + 21.0, ysw, N(R("L", 2), 1), txt="mid")
    c.w((xb + 8.0, ysw), l402.lft) if False else None
    c.w((xb, ysw), l402.lft)
    xo = l402.rgt[0] + 8.0
    c.w(l402.rgt, (xo, ysw))
    pp5 = N(R("L", 2), 2)
    # feedback divider: R433 from the output down to FB, R434 to ground
    pf = u("8"); H.add(pf)
    c.w(pf, (xo, pf[1]))
    r433 = c.vp(R("R", 33), xo, (ysw + pf[1]) / 2, pp5, side="R")
    c.w((xo, ysw), r433.top); c.w(r433.bot, (xo, pf[1]))
    hang(R("R", 34), xo - 14.0, pf[1], N(R("U", 4), 8), side="L")
    xe, yb_, xn = c.bank([R("C", 41), R("C", 42), R("C", 43)], xo + 8.0, ysw, pp5, GND, pitch=13.0)
    c.w((xo, ysw), (xo + 8.0, ysw))
    c.w((xe, ysw), (xe + 8.0, ysw)); c.pwr(xe + 8.0, ysw, pp5, PN("PP5V"))
    c.rest(u)


def ldo9(c, b, R, N, hang, GND):
    PN = lambda n: f"P{b // 100 - 3}_{n}"
    X0, Y0 = 258.0, 290.0
    c.frame(X0, Y0, 408, 356, "9 V gate-drive supply (TPS7A41), diode-ORed with REGN at DRV_SUP")
    ux, uy = 350.52, 326.14
    u = c.place(R("U", 6), ux, uy, ref_at=(ux - 10, uy - 15.5), val_at=(ux - 10, uy - 13.5), just="left")
    H = u.__dict__.setdefault("handled", set())
    tl = u("8")[0]
    pi = u("8"); H.add(pi)
    c.w(pi, (tl - 50.0, pi[1])); c.lab(tl - 50.0, pi[1], "PACK_P", "L")
    hang(R("C", 57), tl - 44.0, pi[1], "PACK_P", side="L")
    pe = u("5"); H.add(pe)
    xn = tl - 10.0
    c.w(pe, (tl - 36.0 + 0.0, pe[1])) if False else None
    r454 = c.hp(R("R", 54), tl - 28.0, pe[1], N(R("R", 54), 2) if N(R("R", 54), 1) == N(R("U", 6), 5) else N(R("R", 54), 1), txt="line")
    c.w(pe, (xn, pe[1])); c.w((xn, pe[1]), r454.rgt)
    c.w(r454.lft, (r454.lft[0] - 2.54, pe[1])); c.lab(r454.lft[0] - 2.54, pe[1], N(R("R", 54), 1) if N(R("R", 54), 1) != N(R("U", 6), 5) else N(R("R", 54), 2), "L")
    q = c.place(R("Q", 9), xn - 2.54, pe[1] + 5.08, ref_at=(xn + 5.0, pe[1] + 3.5), val_at=(xn + 5.0, pe[1] + 5.5), just="left")
    c.w(q("D"), (q("D")[0], pe[1])) if False else None
    c.w(q("S"), (q("S")[0], q("S")[1] + 2.54)); c.end(q("S")[0], q("S")[1] + 2.54, GND)
    pgate = q("G"); c.w(pgate, (pgate[0] - 6.0, pgate[1])); c.lab(pgate[0] - 6.0, pgate[1], N(R("Q", 9), 1), "L")
    for k in ("3", "6", "7"): c.nc(*u(k)); H.add(u(k))
    pg = u("4"); yb = pg[1] + 2.54
    c.w(pg, (pg[0], yb)); c.w(u("9"), (u("9")[0], yb)); c.end(pg[0], yb, GND)
    H.update({u("4"), u("9")})
    po = u("1"); H.add(po)
    pf = u("2"); H.add(pf)
    tr = po[0]
    xr2 = tr + 14.0
    v9 = N(R("U", 6), 1)
    c.w(po, (xr2 + 12.0, po[1])); c.w(pf, (xr2, pf[1]))
    r452 = c.vp(R("R", 52), xr2, (po[1] + pf[1]) / 2, v9, side="R")
    c.w((xr2, po[1]), r452.top); c.w(r452.bot, (xr2, pf[1]))
    hang(R("R", 53), xr2 - 6.0, pf[1], N(R("U", 6), 2), side="L")
    hang(R("C", 58), xr2 + 12.0, po[1], v9, side="R")
    c.w((xr2 + 12.0, po[1]), (xr2 + 20.0, po[1])); c.lab(xr2 + 20.0, po[1], v9, "R")
    c.rest(u)
