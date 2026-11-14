"""Per-block drawings. Each function draws one sheet with the lay.Sch API, the way a careful person would:
power flows left to right, supplies up and ground down, decoupling at its pin, a block per titled group.
A new board gets a new function here (or falls back to draw.py's generic drawing)."""
from lay import *

LAYOUTS = {}
import layout_usb
def layout(block):
    def deco(fn):
        LAYOUTS[block] = fn
        return fn
    return deco


@layout("3V3 Rail")
def rail_3v3(s):
    s.header("3V3 Rail", "TPS62177 always-on buck: pack rail in (12 to 16.8 V), 3.3 V out at 0.5 A for the MCU and both PD controllers")
    s.heading("Buck converter", -52, -22)
    u = s.ic("U204", 0, 0, ref_at=(-9, -13.5, "left"), val_at=(-9, -11.7, "left"))
    vin, en, sl, pg = u.p("VIN"), u.p("EN"), u.p("~{SLEEP}"), u.p("PG")
    # input: pack rail at the left, the small ceramic at VIN
    xc = vin[0] - 25.4
    s.w((xc - 10.16, vin[1]), vin)
    s.rail(xc - 10.16, vin[1], "PACK_P")
    c = s.two("C206", xc, vin[1], "v", a="PACK_P"); s.gnd(*c.b)
    # EN tied to VIN: always on
    s.w(en, (vin[0] - 2.54, en[1]), (vin[0] - 2.54, vin[1]))
    s.netlabel(sl, "L", ref="U204", pad="8", stub=2.54)
    s.nc(*pg)
    # ground pins joined and grounded once
    bot = [u.p(n) for n in ("NC", "PAD", "PGND", "AGND")]
    gy = bot[0][1]
    s.w((bot[0][0], gy), (bot[-1][0], gy))
    gx = u.p("PGND")[0]
    s.w((gx, gy), (gx, gy + 2.54)); s.gnd(gx, gy + 2.54)
    # switch node, inductor, output
    sw, vos, fb = u.p("SW"), u.p("VOS"), u.p("FB")
    s.w(sw, (sw[0] + 5.08, sw[1]))
    s.label(sw[0] + 2.54, sw[1] - 0.0, "R", "SW_3V3") if False else None
    l = s.two("L201", sw[0] + 5.08, sw[1], "h", a="SW_3V3", text="U")
    xo = l.b[0] + 7.62
    s.w(l.b, (xo + 12.7, sw[1]))
    s.w(vos, (xo, vos[1]), (xo, sw[1]))
    c = s.two("C207", xo + 5.08, sw[1], "v", a="3V3"); s.gnd(*c.b)
    s.label(xo + 12.7, sw[1], "R", "3V3")
    s.w(fb, (fb[0] + 2.54, fb[1]), (fb[0] + 2.54, fb[1] + 2.54)); s.gnd(fb[0] + 2.54, fb[1] + 2.54)
    # pack-rail bulk, its own group below
    y0 = 44
    s.heading("Pack-rail bulk capacitance", -52, y0 - 16)
    s.text("Shared by this buck, both chargers and both 5 V bucks", -52, y0 - 11.5)
    xs = [-35.56 + 13.97 * i for i in range(6)]
    s.w((xs[0] - 10.16, y0), (xs[-1], y0))
    s.rail(xs[0] - 10.16, y0, "PACK_P")
    for i, r in enumerate(["C208", "C209", "C210", "C211", "C212", "C213"]):
        c = s.two(r, xs[i], y0, "v", a="PACK_P"); s.gnd(*c.b)
    # notes
    s.heading("Notes", 72, -22)
    s.note(["EN is tied to VIN: the rail is always on.",
            "SLEEP low puts the buck in sleep mode. The MCU drives it,",
            "and a pull-up on the MCU sheet keeps it high until then.",
            "VOS senses the output (fixed 3.3 V part); FB is grounded.",
            "PG is not used. NC, PAD, PGND and AGND go to ground.",
            "C206 sits at VIN and closes the hot loop with PGND."], 72, -16)


@layout("MCU")
def mcu(s):
    s.header("MCU", "CC2340R5 Bluetooth LE module: 3V3 supply, reset, I2C and control lines, debug and gauge-training connectors")
    u = s.ic("U301", 0, 0, ref_at=(-14, -21.5, "left"), val_at=(-14, -19.7, "left"))
    P = u.p
    # ---- supply: 3V3 rail along the top, decoupling at VDDS ----
    vdd = P("6")
    ry = -33.02
    dx = vdd[0] - 7.62                                   # VDDS drop
    s.w(vdd, (dx, vdd[1]), (dx, ry))
    xs = [dx - 12.7 - 15.24 * i for i in range(3)]
    s.w((dx, ry), (xs[-1] - 10.16, ry))
    s.rail(xs[-1] - 10.16, ry, "3V3")
    for r, x in zip(["C303", "C302", "C301"], xs):
        c = s.two(r, x, ry, "v", a="3V3"); s.gnd(*c.b)
    tp = s.one("TP301", xs[-1] - 10.16 - 10.16, ry, "D")
    s.w((xs[-1] - 10.16 - 10.16, ry), (xs[-1] - 10.16, ry))
    # ---- reset: pull-up and cap, label NRST ----
    rst = P("RSTN")
    xr = vdd[0] - 22.86
    xc = xr - 15.24
    s.w(rst, (xc - 7.62, rst[1]))
    r302 = s.two("R302", xr, rst[1] - 7.62, "v", a="3V3", text="L"); s.rail(*r302.a, "3V3") if False else None
    s.rail(xr, rst[1] - 7.62, "3V3")
    s.w(r302.b, (xr, rst[1]))
    c304 = s.two("C304", xc, rst[1], "v", a="NRST"); s.gnd(*c304.b)
    s.label(xc - 7.62, rst[1], "L", "NRST")
    # ---- antenna and SWD pins: labels (the pi network and the connectors are drawn below) ----
    for nm, net in (("ANT_IN", "ANT_IN"), ("RFIO", "RFIO"), ("DIO16/SWDIO", "SWDIO"), ("DIO17/SWDCK", "SWCLK")):
        s.netlabel(P(nm), "L", net=net if net in s.glob else s.netof("U301", u.byname[nm]), stub=2.54)
    g = P("GND")
    s.w(g, (g[0] - 2.54, g[1])); s.gnd(g[0] - 2.54, g[1])
    # ---- right side ----
    R_ = 16.51
    def pull(pin, rref, xcol):
        """Signal row with its pull-up standing above it at xcol: R to a 3V3 symbol, label at the end of the row."""
        p = P(pin)
        net = s.netof("U301", u.byname[pin])
        s.w(p, (xcol, p[1]))
        r = s.two(rref, xcol, p[1] - 7.62, "v", a="3V3")
        s.rail(xcol, p[1] - 7.62, "3V3")
        s.w((xcol, p[1] - 0.0), (xcol, p[1]))
        s.netlabel((xcol, p[1]), "R", net=net, stub=2.54)
    pull("DIO6_A1", "R304", R_ + 10.16)
    pull("DIO8", "R305", R_ + 27.94)
    pull("DIO21_A10", "R313", R_ + 20.32)
    pull("DIO11", "R314", R_ + 45.72)
    for nm in ("DIO18", "DIO24_A7", "DIO3_X32P", "DIO4_X32N"):
        s.netlabel(P(nm), "R", net=s.netof("U301", u.byname[nm]), stub=2.54)
    s.nc(*P("DIO20_A11")); s.nc(*P("DIO12"))
    # ---- antenna match: a pi network between RFIO and ANT_IN ----
    x0, y0 = -62.0, 40.0
    s.heading("Antenna match", x0 - 5.08, y0 - 14)
    s.text("Pi network: series C313 and R321, shunt C314 and C315 (retune on this board)", x0 - 5.08, y0 - 9.5)
    s.w((x0, y0), (x0 + 5.08, y0))
    s.label(x0, y0, "L", "RFIO")
    c313 = s.two("C313", x0 + 5.08, y0, "h", a="RFIO", text="U")
    xm = c313.b[0] + 5.08
    s.w(c313.b, (xm, y0))
    s.w((xm, y0), (xm + 5.08, y0))
    r321 = s.two("R321", xm + 5.08, y0, "h", a=s.netof("C313", c313.pb), text="U")
    c314 = s.two("C314", xm, y0, "v", a=s.netof("C313", c313.pb)); s.gnd(*c314.b)
    xa = r321.b[0] + 5.08
    s.w(r321.b, (xa + 5.08, y0))
    c315 = s.two("C315", xa, y0, "v", a="ANT_IN"); s.gnd(*c315.b)
    s.label(xa + 5.08, y0, "R", "ANT_IN")
    # ---- connectors ----
    s.heading("Debug and gauge-training connectors", 22, y0 - 14)
    s.text("Tag-Connect pads, no part fitted", 22, y0 - 9.5)
    j2 = s.ic("J302", 30, 56, ref_at=(25, 35.5, "left"), val_at=(25, 37.3, "left"))
    for nm in ("SDA", "CHG_INH", "NRST", "SCL"):
        s.netlabel(j2.p(nm), "L", net=s.netof("J302", j2.byname[nm]), stub=2.54)
    s.nc(*j2.p("NC"))
    g2 = j2.p("GND"); s.w(g2, (g2[0] - 2.54, g2[1])); s.gnd(g2[0] - 2.54, g2[1])
    j1 = s.ic("J301", 75, 56, ref_at=(66, 50, "right"), val_at=(66, 51.8, "right"))
    for nm in ("~{RESET}", "SWCLK", "SWDIO", "SWO"):
        s.netlabel(j1.p(nm), "R", net=s.netof("J301", j1.byname[nm]), stub=2.54)
    s.rail(*j1.p("VCC"), "3V3")
    gp = j1.p("GND"); s.w(gp, (gp[0], gp[1] + 2.54)); s.gnd(gp[0], gp[1] + 2.54)


@layout("Cells and Gauge")
def cells(s):
    s.rename.update({"Net-(F102-HTR)": "F102_HTR", "Net-(Q104-G)": "Q104_G", "GAUGE_FUSE": "FUSE", "Net-(U101-PACK)": "PACK_S"})
    s.header("Cells and Gauge", "4S pack connections, BQ40Z50 gauge, charge and discharge FETs, BQ294700 second-level protector with chemical fuse")
    u = s.ic("U101", 0, 0, ref_at=(-12, -31, "left"), val_at=(-12, -29.2, "left"))
    P = u.p
    N = lambda pin: s.netof("U101", u.byname[pin] if pin in u.byname else pin)
    s.heading("BQ40Z50 gauge", -108, -80)
    # ---------------- left: supply, cell inputs, current sense, pack sense, thermistors ----------------
    names = ["BAT", "VCC", "PBI", "VC4", "VC3", "VC2", "VC1"]
    tg = [-68.58, -58.42, -48.26, -38.1, -27.94, -17.78, -7.62]
    ends = s.fan([P(n) for n in names], tg, "L", base=10.16)
    E = dict(zip(names, ends))
    x, y, _ = chain(s, E["BAT"], "L", N("BAT"), [5.08, ("p", "R105"), 2.54, ("p", "D101"), 5.08, ("label",)])
    chain(s, E["VCC"], "L", N("VCC"), [5.08, ("p", "R106"), 5.08, ("label",)])
    chain(s, E["PBI"], "L", N("PBI"), [5.08, ("p", "C105"), 5.08, ("gndx", "CELL_1N")])
    # PTCEN and PTC are tied to the Kelvin ground
    for nm in ("PTCEN", "PTC"):
        s.netlabel(P(nm), "L", ref="U101", pad=u.byname[nm] if nm in u.byname else nm, stub=2.54)
    # cell input filters: R in series, caps between the sense nodes
    xc = -53.34
    vc = ["VC4", "VC3", "VC2", "VC1"]
    rr = {"VC4": "R104", "VC3": "R103", "VC2": "R102", "VC1": "R101"}
    cc = {"VC4": "C101", "VC3": "C102", "VC2": "C103", "VC1": "C104"}
    pads = {"VC4": "J116", "VC3": "J111", "VC2": "J110", "VC1": "J109"}
    for i, v in enumerate(vc):
        ex, ey = E[v]
        s.w((ex, ey), (xc, ey))
        px_, py_, nn_ = chain(s, (xc, ey), "L", N(v), [5.08, ("p", rr[v]), 20.32, ("pad", pads[v], "D")])
        s.label(px_ + 7.62, py_, "R", nn_, above=True)
        c = s.two(cc[v], xc, ey, "v", a=N(v))
        if i < 3: s.w(c.b, (xc, ey + 10.16))
        else:
            s.gndx(*c.b, "CELL_1N")
            s.w(c.b, (xc - 33.02, c.b[1])); s.one("J115", xc - 33.02, c.b[1], "D")
    # SRP, SRN, PACK and TS1..TS4 leave on labels; their circuits are drawn as wired groups under the gauge
    names2 = ["SRP", "SRN", "PACK", "TS1", "TS2", "TS3", "TS4"]
    for nm in names2:
        s.netlabel(P(nm), "L", ref="U101", pad=u.byname[nm] if nm in u.byname else nm, stub=2.54)
    # ---- current sense (Kelvin) ----
    ya = 64.0
    s.heading("Pack current sense", -108, ya - 4)
    s.text("RS101 in the pack-negative path; R107, R108, C106 filter", -108, ya + 0.5)
    ys = ya + 16.0
    xr = -84.0
    xt_, xb_ = xr - 5.08, xr + 7.62 + 5.08
    s.w((xt_ - 5.08, ys), (xt_, ys)); s.one("J108", xt_ - 5.08, ys, "L")
    s.w((xt_, ys), (xr, ys)); s.w((xr + 7.62, ys), (xb_, ys))
    s.two("RS101", xr, ys, "h", a="CELL_N", text="U")
    rt = s.two("R107", xt_, ys, "v", a="CELL_N", text="L")
    gn = layout_usb.other(s, "R108", N("SRN"))
    rb = s.two("R108", xb_, ys, "v", a=gn, text="R")
    yf = ys + 10.16
    s.w(rt.b, (xt_, yf)); s.w(rb.b, (xb_, yf))
    s.w((xt_, yf), (xr, yf)); s.w((xr + 7.62, yf), (xb_, yf))
    s.two("C106", xr, yf, "h", a=N("SRP"), text="D")
    s.netlabel((xt_, yf), "L", net=N("SRP"), stub=2.54)
    s.netlabel((xb_, yf), "R", net=N("SRN"), stub=2.54)
    # ground side of the shunt: load-ground pad and test point hang on the wire
    s.w((xb_, ys), (xb_ + 40.64, ys))
    s.one("J114", xb_ + 10.16, ys, "D"); s.one("TP109", xb_ + 27.94, ys, "D")
    s.gnd(xb_ + 40.64, ys)
    # ---- pack voltage sense and thermistors ----
    xg0 = -12.0
    s.heading("Pack sense and thermistors", xg0 - 6, ya - 4)
    s.text("R113 senses PACK_P; TH101, TH104 on board; TS2, TS3 NTCs on wires", xg0 - 6, ya + 0.5)
    yv = ya + 14.0
    pk = N("PACK")
    s.rail(xg0, yv, "PACK_P")
    rp = s.two("R113", xg0, yv, "v", a="PACK_P", text="R")
    s.netlabel(rp.b, "D", net=pk, stub=2.54)
    for k, (ref, net) in enumerate((("TH101", "TS1"), ("TH104", "TS4"))):
        x = xg0 + 17.78 + 15.24 * k
        t = s.two(ref, x, yv, "v", a=N(net), text="R")
        s.netlabel((x, yv), "U", net=N(net), stub=2.54)
        s.gndx(*t.b, "CELL_1N")
    for k, (ref, net) in enumerate((("J117", "TS2"), ("J118", "CELL_1N"), ("J119", "TS3"), ("J120", "CELL_1N"))):
        x = xg0 + 17.78 + 15.24 * 2 + 27.94 * k + 5.08
        s.netlabel((x, yv), "U", net=N(net) if net != "CELL_1N" else "CELL_1N", stub=2.54)
        s.one(ref, x, yv, "D")
    # ---------------- right: gate drives, SMBus, interrupt ----------------
    for nm in ("CHG", "DSG", "FUSE"):
        s.netlabel(P(nm), "R", ref="U101", pad=u.byname[nm], stub=2.54)
    s.nc(*P("PCHG"))
    ends3 = s.fan([P("SMBC"), P("SMBD")], [-30.48, -20.32], "R", base=10.16)
    chain(s, ends3[0], "R", N("SMBC"), [5.08, ("p", "R115"), 5.08, ("label",)])
    chain(s, ends3[1], "R", N("SMBD"), [5.08, ("p", "R116"), 5.08, ("label",)])
    # BTP_INT: pull-down and level shifter onto the shared IRQ line
    bt = P("BTP_INT")
    q103 = s.ic("Q103", 43.18, bt[1], ref_at=(48, bt[1] + 2, "left"), val_at=(48, bt[1] + 3.8, "left"))
    s.w(bt, q103.p("G"))
    r117 = s.two("R117", 27.94, bt[1], "v", a=N("BTP_INT")); s.gndx(*r117.b, "CELL_1N")
    s.w(q103.p("D"), (q103.p("D")[0], q103.p("D")[1] - 2.54)); s.label(q103.p("D")[0], q103.p("D")[1] - 2.54, "R", "IRQ_N")
    s.gnd(*q103.p("S"))
    pr, ds = P("PRES/SHUTDN"), P("DISP")
    s.w(pr, (pr[0] + 2.54, pr[1]), (pr[0] + 2.54, ds[1]), ds)
    s.label(pr[0] + 2.54, (pr[1] + ds[1]) / 2, "R", "CELL_1N")
    for nm in ("LEDCNTLA", "LEDCNTLB", "LEDCNTLC", "NC"): s.nc(*P(nm))
    vs = P("VSS"); s.w(vs, (vs[0] + 2.54, vs[1])); s.gndx(vs[0] + 2.54, vs[1], "CELL_1N")
    ps = Shift(s, 138.0, -192.0)
    # ---------------- power path: wire, fuse, back-to-back FETs, load ----------------
    Yp = 140.0
    ps.heading("Charge and discharge path", -82, Yp - 38)
    ps.text("PACK+ wire, fuse, charge FET Q101 and discharge FET Q102 back to back, then the load", -82, Yp - 33)
    f = ps.ic("F102", -40, Yp, ref_at=(-46, Yp - 5.5, "left"), val_at=(-46, Yp - 3.8, "left"))
    ps.w((-64, Yp), f.p("1")); ps.one("J112", -64, Yp, "D")
    ps.netlabel(f.p("HTR"), "D", net="Net-(F102-HTR)", stub=2.54)
    qx, qx2 = 0.0, 45.72
    q1 = ps.ic("Q101", qx, Yp - 6.35, angle=270, ref_at=(qx + 4, Yp - 9.5, "left"), val_at=(qx + 4, Yp - 7.7, "left"))
    q2 = ps.ic("Q102", qx2, Yp - 6.35, angle=270, mirror=True, ref_at=(qx2 - 7.5, Yp - 9.5, "left"), val_at=(qx2 - 7.5, Yp - 7.7, "left"))
    ps.w(f.p("2"), q1.p("S"))
    ps.w(q1.p("D"), q2.p("D")); ps.label((q1.p("D")[0] + q2.p("D")[0]) / 2 - 3.2, Yp, "R", "FET_MID", above=True)
    # CHG gate: R109 from CHG, R110 holds it to CELL_P
    yg = Yp - 25.4
    g1 = q1.p("G")
    ps.w(g1, (g1[0], yg), (-10.16, yg))
    r110 = ps.two("R110", -10.16, yg, "v", a="CHG_G", text="L"); ps.w(r110.b, (-10.16, Yp))
    chain(ps, (-10.16, yg), "L", "CHG_G", [5.08, ("p", "R109", "U"), 2.54, ("label",)])
    # DSG gate: R111 from DSG, R112 and the zener D103 to PACK_P
    g2 = q2.p("G")
    ps.w(g2, (g2[0], yg), (qx2 + 12.7, yg))
    r112 = ps.two("R112", qx2 + 12.7, yg, "v", a="DSG_G"); ps.w(r112.b, (qx2 + 12.7, Yp))
    ps.w((qx2 + 12.7, yg), (qx2 + 30.48, yg))
    d103 = ps.two("D103", qx2 + 30.48, yg, "v", a="DSG_G"); ps.w(d103.b, (qx2 + 30.48, Yp))
    chain(ps, (qx2 + 30.48, yg), "R", "DSG_G", [5.08, ("p", "R111", "U"), 2.54, ("label",)])
    # load side
    xl = 120.0
    ps.w(q2.p("S"), (xl, Yp)); ps.label(xl, Yp, "R", "PACK_P")
    # ESD pair across the FETs
    ye = Yp + 17.78
    ps.w((-6.35, Yp), (-6.35, ye))
    ex, ey, _ = chain(ps, (-6.35, ye), "R", "CELL_P", [5.08, ("p", "C110", "U"), 2.54, ("p", "C111", "U")])
    ps.w((ex, ey), (58.42, ey), (58.42, Yp))
    # WAKE test point
    ps.w((-27.94, Yp), (-27.94, Yp)); r118 = ps.two("R118", -27.94, Yp, "v", a="CELL_P"); ps.one("TP113", *r118.b, "D")
    # PACK_P: mid-point cap pair to ground, load pad, test point
    c107 = ps.two("C107", 76.2, Yp, "v", a="PACK_P"); c108 = ps.two("C108", 76.2, c107.b[1], "v", a="PACK_CMID"); ps.gnd(*c108.b)
    ps.w((90.17, Yp), (90.17, Yp)); ps.one("J113", 90.17, Yp, "D"); ps.one("TP106", 112.0, Yp, "D")
    ps = Shift(s, 138.0, -176.0)
    # ---------------- second-level protector ----------------
    Yu = 215.0
    ps.heading("Second-level protector and chemical fuse", -82, Yu - 30)
    ps.text("BQ294700 trips Q104 through R124 if a cell goes over 4.35 V; Q104 heats the fuse F102", -82, Yu - 25)
    u2 = ps.ic("U102", 0, Yu, ref_at=(-8, Yu - 19, "left"), val_at=(-8, Yu - 17.2, "left"))
    xc2 = -22.86
    rows = (("V4", "R119", "C112"), ("V3", "R120", "C113"), ("V2", "R121", "C114"), ("V1", "R122", "C115"))
    for i, (pin, rr_, cc_) in enumerate(rows):
        p = u2.p(pin)
        ps.w(p, (xc2, p[1]))
        chain(ps, (xc2, p[1]), "L", ps.netof("U102", u2.byname[pin]), [5.08, ("p", rr_, "U"), 5.08, ("label",)])
        c = ps.two(cc_, xc2, p[1], "v", a=ps.netof("U102", u2.byname[pin]))
        if i < 3: pass
        else: ps.gndx(*c.b, "CELL_1N")
    # right side: VDD with R123 and C116, VSS, CD with C117, OUT to the fuse FET
    vdd, vss, cd, out = u2.p("VDD"), u2.p("VSS"), u2.p("CD"), u2.p("OUT")
    xa, xb = 24.13, 40.64
    ps.w(vdd, (xa, vdd[1]))
    c116 = ps.two("C116", xa, vdd[1], "v", a=ps.netof("U102", u2.byname["VDD"]))
    chain(ps, (xa, vdd[1]), "R", ps.netof("U102", u2.byname["VDD"]), [12.7, ("p", "R123", "U"), 5.08, ("label",)])
    ps.w(vss, (xb, vss[1])); ps.w((14.0, vss[1]), (14.0, vss[1])); ps.gndx(14.0, vss[1], "CELL_1N")
    c117 = ps.two("C117", xb, vss[1], "v", a="CELL_1N")
    ps.w(cd, (xb, cd[1]))
    gy = out[1]
    ps.w(out, (14.0, gy))
    r124 = ps.two("R124", 14.0, gy, "h", a=ps.netof("U102", "8"), text="S")
    q104 = ps.ic("Q104", 71.12, gy, ref_at=(76, gy + 2, "left"), val_at=(76, gy + 3.8, "left"))
    gq = q104.p("G")
    ps.w(r124.b, gq)
    r125 = ps.two("R125", 30.48, gy, "v", a="Net-(Q104-G)"); ps.gnd(*r125.b)
    c118 = ps.two("C118", 46.99, gy, "v", a="Net-(Q104-G)"); ps.gndx(*c118.b, "CELL_1N")
    r126 = ps.two("R126", 58.42, gy - 7.62, "v", a="GAUGE_FUSE", text="L")
    ps.w(r126.b, (58.42, gy)); ps.label(58.42, gy - 7.62, "U", "GAUGE_FUSE") if False else ps.netlabel((58.42, gy - 7.62), "U", net="GAUGE_FUSE", stub=2.54)
    ps.netlabel(q104.p("D"), "U", net="Net-(F102-HTR)", stub=2.54)
    ps.gnd(*q104.p("S"))


LAYOUTS["USB Port 1"] = layout_usb.usb_port
LAYOUTS["USB Port 2"] = layout_usb.usb_port
