"""Cells and Gauge: the BQ40Z50 gauge with its cell filters and current sense, the pack power path with the two
protection FETs, the BQ294700 second-level protector with its fuse driver, and the interrupt level shifter."""
import symlib

GAUGE = ("MonolithDev", "BQ40Z50-R2")
PROT = ("MonolithDev", "BQ294700")
sn = lambda v: round(v / 1.27) * 1.27


def draw(h):
    h.text(20.32, 21, "Cells and Gauge", 3.0)
    with h.group("BQ40Z50 gauge: cell inputs, current sense, SMBus"):
        gauge(h, 127.0, 100.33)
    with h.group("Pack power path: fuse, charge FET, discharge FET"):
        path(h, 224.0, 63.5)
    with h.group("Second-level protector BQ294700 and fuse driver"):
        protector(h, 250.0, 142.24)


def cell_ladder(h, u, pins, rs, caps, xn, gap, lastcap):
    """Cell sense inputs on a pin column: a resistor in series on each lane, a capacitor between neighbouring nodes
    and one from the last node to CELL_1N, drawn as a ladder. pins: the pin names top to bottom."""
    rows = {}
    for pin, r in zip(pins, rs):
        h.lane(u.p(pin), "L", [r], u.net(pin), gap=gap, end="none")
        rows[pin] = u.p(pin)[1]
    for (a, b), c in zip(zip(pins, pins[1:]), caps):
        s = h.two(c, xn, (rows[a] + rows[b]) / 2, "v", first=u.net(a))
        h.w(s.a, (xn, rows[a])); h.w(s.b, (xn, rows[b]))
    s = h.two(lastcap, xn, rows[pins[-1]] + 3.81, "v", first=u.net(pins[-1]))
    h.w(s.a, (xn, rows[pins[-1]]))
    return rows, s.b


def gauge(h, ox, oy):
    symlib.respace(*GAUGE, {"BAT": 55.88, "VCC": 48.26, "PBI": 38.1, "PTCEN": 33.02,
                            "VC4": 27.94, "VC3": 20.32, "VC2": 12.7, "VC1": 5.08, "SRP": -12.7, "SRN": -20.32,
                            "PACK": -30.48, "TS1": -40.64, "TS2": -50.8, "TS3": -60.96, "TS4": -71.12, "PTC": -81.28,
                            "CHG": 48.26, "DSG": 40.64, "PCHG": 35.56, "FUSE": 30.48, "SMBC": 20.32, "SMBD": 10.16,
                            "BTP_INT": 0, "PRES/SHUTDN": -10.16, "DISP": -12.7, "LEDCNTLA": -17.78, "LEDCNTLB": -20.32,
                            "LEDCNTLC": -22.86, "NC": -27.94, "VSS": -33.02})
    u = h.ic("U101", ox, oy, fields="above")
    P = u.p
    xp = P("VC4")[0]
    # ---- left lanes
    h.lane(P("BAT"), "L", ["R105", "D101"], "GAUGE_BAT")
    h.lane(P("VCC"), "L", ["R106"], "GAUGE_VCC")
    e, _, _ = h.lane(P("PBI"), "L", ["C105"], "PBI", end="none")
    ypt = P("PTCEN")[1]
    h.w(P("PTCEN"), (e[0], ypt), e)                # PBI cap and PTCEN return to the same node
    h.w(e, (e[0] - 2.54, e[1])); h.lab(e[0] - 2.54, e[1], "CELL_1N", "L")
    xn = sn(xp - 16.51)
    xend = sn(xp - 29.21)                       # where the series resistors end
    xpad = sn(xp - 48.26)                       # the wire pads for the cells
    rows, c4b = cell_ladder(h, u, ["VC4", "VC3", "VC2", "VC1"], ["R104", "R103", "R102", "R101"],
                            ["C101", "C102", "C103"], xn, 21.59, "C104")
    for (pin, pad, net) in (("VC4", "J116", "CELL_4P"), ("VC3", "J111", "CELL3"), ("VC2", "J110", "CELL2"), ("VC1", "J109", "CELL1")):
        y = rows[pin]
        h.w((xend, y), (xpad, y)); h.lab(xend - 2.54, y, net, "L")
        h.one(pad, xpad, y, "R", txt="l")
    # 1N Kelvin wire at the bottom of the ladder
    yk = c4b[1] + 2.54
    h.w(c4b, (xn, yk), (xpad, yk)); h.lab(xn - 2.54, yk, "CELL_1N", "L")
    h.one("J115", xpad, yk, "R", txt="l")
    # current sense: the sense resistor stands between the two lanes, in line with them
    for pin, r in (("SRP", "R107"), ("SRN", "R108")):
        h.lane(P(pin), "L", [r], u.net(pin), gap=21.59, end="none", txt="a" if pin == "SRP" else "b")
    s = h.two("C106", xn, (P("SRP")[1] + P("SRN")[1]) / 2, "v", first="SRP")
    h.w(s.a, (xn, P("SRP")[1])); h.w(s.b, (xn, P("SRN")[1]))
    xr = sn(xp - 48.26)
    ysp, ysn = P("SRP")[1], P("SRN")[1]
    rs = h.two("RS101", xr, (ysp + ysn) / 2, "v", first="CELL_N", txt="r")
    h.w((xend, ysp), (xr, ysp)); h.w((xend, ysn), (xr, ysn))
    h.w(rs.a, (xr - 15.24, rs.a[1])); h.one("J108", xr - 15.24, rs.a[1], "R", txt="l")
    yg = rs.b[1] + 2.54
    h.w(rs.b, (xr, yg)); h.gnd(xr, yg)
    h.w((xr, yg), (xr - 15.24, yg)); h.one("J114", xr - 15.24, yg, "R", txt="l")
    h.w((xr - 7.62, yg), (xr - 7.62, yg + 2.54)); h.one("TP109", xr - 7.62, yg + 2.54, "U", txt="r")
    h.lane(P("PACK"), "L", ["R113"], "GAUGE_PACK")
    # thermistors: two on the board, two on wires
    h.lane(P("TS1"), "L", ["TH101"], "TS1", txt="b")
    e4, _, _ = h.lane(P("TS4"), "L", ["TH104"], "TS4", txt="b", end="none")
    ypc = P("PTC")[1]
    xv4 = e4[0] - 7.62
    h.w(e4, (xv4, e4[1]), (xv4, ypc)); h.w(P("PTC"), (xv4, ypc)); h.lab(xv4, ypc, "CELL_1N", "L")
    for pin, j, jr in (("TS2", "J117", "J118"), ("TS3", "J119", "J120")):
        pos = P(pin)
        xj = pos[0] - 33.02
        h.w(pos, (xj, pos[1])); h.lab(pos[0] - 5.08, pos[1], pin, "L")
        a = h.ic(j, xj - 5.08, pos[1], mirror=True, fields="left")
        h.w(h.syms[jr].p("Pin_1") if jr in h.syms else (0, 0), (0, 0)) if False else None
        b = h.ic(jr, xj - 5.08, pos[1] + 5.08, mirror=True, fields="left")
        h.stub(b.p("Pin_1"), "R", "CELL_1N", 5.08)
    # ---- right lanes
    h.stub(P("CHG"), "R", "CHG", 5.08)
    h.stub(P("DSG"), "R", "DSG", 5.08)
    h.stub(P("FUSE"), "R", "GAUGE_FUSE", 5.08)
    h.lane(P("SMBC"), "R", ["R115"], "SMBC")
    h.lane(P("SMBD"), "R", ["R116"], "SMBD")
    pe, pf = P("PRES/SHUTDN"), P("DISP")
    # interrupt: BTP_INT drives Q103, which pulls the shared IRQ_N line low
    pb = P("BTP_INT")
    q = h.ic("Q103", pb[0] + 26.67, pb[1], fields="right")
    h.w(pb, q.p("G"))
    r117 = h.two("R117", pb[0] + 5.08, pb[1] + 3.81, "v", first="BTP_INT", txt="r")
    h.w(r117.a, (r117.a[0], pb[1]))
    # one CELL_1N bus down the right side: R117, PRES/SHUTDN and DISP (joined), VSS
    xb = r117.b[0]; yv = P("VSS")[1]
    h.w(r117.b, (xb, yv)); h.w(pe, (xb, pe[1])); h.w(pf, (xb, pf[1])); h.w(P("VSS"), (xb, yv))
    h.lab(xb, yv, "CELL_1N", "R")
    h.w(q.p("D"), (q.p("D")[0], q.p("D")[1] - 2.54)); h.lab(q.p("D")[0], q.p("D")[1] - 2.54, "IRQ_N", "R")
    h.gnd(*q.p("S"))
    h.note(sn(ox - 82), oy + 100, ["Cell sense: every tap has 100R and 0.1u (R101-R104, C101-C104).",
                                  "J115 and J116 are the Kelvin wires to the 1N and 4P cell taps.",
                                  "RS101 (1 mOhm) is sensed on SRP/SRN through R107/R108 with C106.",
                                  "TH101, TH104 and the TS2/TS3 pads give four temperature inputs."], 1.27)
    return u


def path(h, x0, y0):
    """The pack current, left to right along one rail: cells, fuse, charge FET, discharge FET, pack output.
    The two FETs are drawn back to back with their drains joined; their sources dip down to the rail."""
    yq = sn(y0)                               # FET centre
    yr = sn(yq + 6.35)                        # the rail
    xj = sn(x0)
    xf = sn(xj + 20.32)
    h.one("J112", xj, yr, "R", txt="l")
    f = h.ic("F102", xf, yr, fields="above")
    h.w((xj, yr), f.p("1"))
    ht = f.p("HTR"); h.w(ht, (ht[0], ht[1] + 2.54)); h.lab(ht[0], ht[1] + 2.54, "FUSE_HTR", "R")
    # charge FET Q101 (gate on the left), discharge FET Q102 mirrored (gate on the right)
    xq1 = sn(xf + 58.42)
    xq2 = sn(xq1 + 30.48)
    q1 = h.ic("Q101", xq1, yq, fields="above")
    q2 = h.ic("Q102", xq2, yq, mirror=True, fields="above")
    d1, d2 = q1.p("D"), q2.p("D")
    h.w(d1, d2)
    xm = sn((d1[0] + d2[0]) / 2)
    h.w((xm, d1[1]), (xm, d1[1] - 5.08)); h.lab(xm, d1[1] - 5.08, "FET_MID", "R")
    s1, s2 = q1.p("S"), q2.p("S")
    h.w((xj, yr), f.p("1")); h.w(f.p("2"), (s1[0], yr), s1)
    h.w(s2, (s2[0], yr), (sn(xq2 + 70), yr))
    # gate networks, each with its 10M gate-source resistor standing between the gate line and the rail
    g1 = q1.p("G"); n1 = (g1[0] - 5.08, g1[1])
    h.w(g1, n1)
    r110 = h.two("R110", n1[0], g1[1] + 3.81, "v", first="CHG_G", txt="l")
    h.w(n1, r110.a)
    h.lane(n1, "L", ["R109"], "CHG_G", end="label", gap=2.54, endgap=5.08)
    g2 = q2.p("G"); n2 = (g2[0] + 5.08, g2[1]); n3 = (n2[0] + 12.7, g2[1])
    h.w(g2, n3)
    r112 = h.two("R112", n2[0], g2[1] + 3.81, "v", first="DSG_G", txt="r")
    d103 = h.two("D103", n3[0], g2[1] + 3.81, "v", first="DSG_G", txt="r")
    h.lane(n3, "R", ["R111"], "DSG_G", end="label", gap=2.54, endgap=5.08)
    # ESD caps in series across both FETs, from the cell side to the pack side
    ye = sn(yr + 11.43)
    xe1, xe2 = sn(xq1 - 25.4), sn(xq2 + 10.16)
    h.w((xe1, yr), (xe1, ye))
    c110 = h.two("C110", sn(xe1 + 17.78), ye, "h", first="CELL_P")
    h.w((xe1, ye), c110.a)
    c111 = h.two("C111", sn(xe2 - 17.78), ye, "h", first="ESD_MID")
    h.w(c110.b, c111.a); h.lab(sn((c110.b[0] + c111.a[0]) / 2) - 2.54, ye, "ESD_MID", "R")
    h.w(c111.b, (xe2, ye), (xe2, yr))
    # wake test point
    xw = sn(xf + 25.4)
    r118 = h.two("R118", xw, yr + 6.35, "v", first="CELL_P", txt="r")
    h.w((xw, yr), r118.a)
    h.w(r118.b, (xw, r118.b[1] + 2.54)); h.one("TP113", xw, r118.b[1] + 2.54, "U", txt="r")
    # pack output: bypass, test points, load wire, label
    xc = sn(xe2 + 20.32)
    c107 = h.two("C107", xc, yr + 6.35, "v", first="PACK_P", txt="r")
    c108 = h.two("C108", xc, c107.b[1] + 6.35, "v", first="PACK_CMID", txt="r")
    h.w((xc, yr), c107.a)
    h.w(c107.b, c108.a); h.gnd(*c108.b)
    xt = sn(xc + 20.32)
    h.w((xt, yr), (xt, yr + 2.54)); h.one("TP106", xt, yr + 2.54, "U", txt="r")
    xl = sn(xt + 17.78)
    h.w((xl, yr), (xl, yr + 2.54)); h.one("J113", xl, yr + 2.54, "U", txt="r")
    xo = sn(xl + 22.86)
    h.w((xc, yr), (xo, yr)); h.lab(xo, yr, "PACK_P", "R")
    h.note(xj, yr + 26, ["Charge FET Q101 and discharge FET Q102 sit back to back, drains joined at FET_MID.",
                         "C110 and C111 in series across both FETs are the ESD path.",
                         "R118 and TP113 are the wake test point; J113 is the load wire."], 1.27)


def protector(h, ox, oy):
    """Second-level protector BQ294700: cell inputs in on the left, the OUT line that fires the fuse heater on the right."""
    symlib.respace(*PROT, {"VDD": 19.05, "OUT": -19.05})
    u = h.ic("U102", ox, oy, fields="above")
    P = u.p
    xp = P("V4")[0]
    xn = sn(xp - 16.51); xend = sn(xp - 29.21)
    rows, c_b = cell_ladder(h, u, ["V4", "V3", "V2", "V1"], ["R119", "R120", "R121", "R122"], ["C112", "C113", "C114"], xn, 21.59, "C115")
    for pin, net in (("V4", "CELL_4P"), ("V3", "CELL3"), ("V2", "CELL2"), ("V1", "CELL1")):
        h.stub((xend, rows[pin]), "L", net, 5.08)
    h.drop(c_b, "CELL_1N", "L")
    # supply: filtered from the top cell, bypassed to CELL_1N
    pv = P("VDD"); xv = sn(pv[0] + 7.62)
    h.w(pv, (xv, pv[1]))
    c116 = h.two("C116", xv, pv[1] + 3.81, "v", first="PROT_VDD", txt="r")
    h.w((xv, pv[1]), c116.a); h.drop(c116.b, "CELL_1N", "R")
    h.lane((xv, pv[1]), "R", ["R123"], "PROT_VDD", gap=12.7, step=2.54, endgap=5.08)
    h.tie(P("VSS"), "CELL_1N", "R")
    # delay capacitor
    pc = P("CD")
    c117 = h.two("C117", xv, pc[1] + 3.81, "v", first="PROT_CD", txt="r")
    h.w(pc, (xv, pc[1])); h.w((xv, pc[1]), c117.a); h.drop(c117.b, "CELL_1N", "R")
    # OUT drives the fuse-ignition FET through a divider
    po = P("OUT")
    e, _, _ = h.lane(po, "R", ["R124"], "PROT_OUT", end="none")
    xa = sn(e[0] + 22.86); xb = sn(xa + 12.7); xc = sn(xb + 12.7)
    h.w(e, (xc, po[1]))
    r126 = h.two("R126", xa, po[1] - 3.81, "v", first="GAUGE_FUSE", txt="r")
    h.w(r126.b, (xa, po[1]))
    h.w(r126.a, (xa, r126.a[1] - 2.54)); h.lab(xa, r126.a[1] - 2.54, "GAUGE_FUSE", "R")
    r125 = h.two("R125", xb, po[1] + 3.81, "v", first="FUSE_G", txt="r")
    h.w((xb, po[1]), r125.a); h.gnd(*r125.b)
    c118 = h.two("C118", xc, po[1] + 3.81, "v", first="FUSE_G", txt="r")
    h.w((xc, po[1]), c118.a); h.drop(c118.b, "CELL_1N", "R")
    q = h.ic("Q104", xc + 15.24, po[1], fields="right")
    h.w((xc, po[1]), q.p("G"))
    d = q.p("D"); h.w(d, (d[0], d[1] - 2.54)); h.lab(d[0], d[1] - 2.54, "FUSE_HTR", "R")
    h.gnd(*q.p("S"))
    h.note(sn(ox - 50), oy + 42, ["BQ294700: a second, independent overvoltage check on the four cells.",
                                  "When OUT goes high Q104 heats the chemical fuse F102 through FUSE_HTR;",
                                  "the gauge can fire the same fuse through GAUGE_FUSE."], 1.27)
