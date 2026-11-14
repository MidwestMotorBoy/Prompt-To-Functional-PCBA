"""Cells and Gauge sheet: BQ40Z50 gauge with its cell inputs and gate drive, the protection FETs in the power path,
current sense, the BQ294700 second-level protector and the fuse heater driver."""
from lay import *

DISP = {"Net-(Q104-G)": "FUSE_G"}


def scene(L):
    L.disp.update(DISP)
    L.title("Cells and Gauge", 20.32, 22.86, 3.0)
    L.pack([("BQ40Z50 gauge: cell inputs, supply, temperature, gate drive, SMBus, interrupt", gauge),
            ("Pack path: fuse and back-to-back protection FETs (charge and discharge)", lambda L, x, y: power_path(L, x, y + 30.48)),
            ("Second-level protector: independent overvoltage cut that heats the fuse", protector),
            ("Current sense: 1 mOhm shunt in the negative leg", lambda L, x, y: sense_and_protector(L, x, y))])


def gauge(L, X0, Y0):
    s = L.s
    gl = {"VCC": 10.16, "PBI": 10.16, "PTCEN": 17.78, "VC4": 12.7, "VC3": 12.7, "VC2": 12.7, "VC1": 12.7, "SRP": 20.32, "SRN": 5.08,
          "PACK": 12.7, "TS1": 12.7, "TS2": 15.24, "TS3": 22.86, "TS4": 17.78, "PTC": 12.7}
    gr = {"DSG": 7.62, "PCHG": 5.08, "FUSE": 5.08, "SMBC": 10.16, "SMBD": 10.16, "BTP_INT": 12.7, "PRES/SHUTDN": 20.32, "DISP": 2.54,
          "LEDCNTLA": 12.7, "LEDCNTLB": 5.08, "LEDCNTLC": 5.08, "NC": 7.62, "VSS": 7.62}
    u = L.ic("U101", X0 + 97.79, Y0 + 34.29, gaps={"L": gl, "R": gr}, text="above")
    P = u.pin
    xp = P("VC4")[0]
    # ---- cell inputs: pad, tap label, series resistor, node with the cap chain
    xn = snap(xp - 17.78)
    rows = [("VC4", "R104", "J116", "CELL_4P"), ("VC3", "R103", "J111", "CELL3"), ("VC2", "R102", "J110", "CELL2"), ("VC1", "R101", "J109", "CELL1")]
    ys = {}
    for pin, rr, jj, tap in rows:
        y = P(pin)[1]; ys[pin] = y
        r = L.h(rr, snap(xn - 8.89), y, left=tap, txt="ab")
        s.wire(r.r[0], y, xp, y)
        xpad = snap(xn - 8.89 - 3.81 - 20.32)
        L.pad(jj, xpad, y, "L")
        s.wire(xpad, y, r.l[0], y)
        s.label(L.short(tap), snap(xpad + 3.81), y, 0, False)
        L.use(u, pin)
    for k, (a, b, cc) in enumerate((("VC4", "VC3", "C101"), ("VC3", "VC2", "C102"), ("VC2", "VC1", "C103"))):
        c = L.v(cc, xn, snap((ys[a] + ys[b]) / 2), top=L.netat(u, a))
        s.wire(xn, ys[a], xn, c.t[1]); s.wire(xn, c.b[1], xn, ys[b])
    c104 = L.v("C104", xn, snap(ys["VC1"] + 3.81 + 2.54 + 1.27), top=L.netat(u, "VC1"))
    s.wire(xn, ys["VC1"], xn, c104.t[1])
    yk = snap(c104.b[1] + 2.54)
    s.wire(xn, c104.b[1], xn, yk)
    xpad = snap(xn - 8.89 - 3.81 - 20.32)
    s.wire(xn, yk, xpad, yk); L.pad("J115", xpad, yk, "L")
    L.term("CELL_1N", xn, yk + 2.54, "D") if False else None
    s.wire(xn, yk, xn, snap(yk + 2.54)); L.term("CELL_1N", xn, snap(yk + 2.54), "D")
    # ---- cell-top bus up to the supply row: CELL_4P also feeds BAT through D101 and R105
    yb = P("BAT")[1]
    r104 = L.placed["R104"]
    xt = snap(xn - 8.89 - 3.81 - 2.54)
    xr5 = snap(xp - 10.16)
    r105 = L.h("R105", xr5, yb, left="Net-(D101-K)", txt="ab")
    d101 = L.h("D101", snap(xp - 25.4), yb, left="CELL_4P", txt="ab")
    s.wire(xt, ys["VC4"], xt, yb); s.wire(xt, yb, d101.l[0], yb)
    s.wire(d101.r[0], yb, r105.l[0], yb); s.wire(r105.r[0], yb, xp, yb)
    L.note("BAT is fed from the cell top ahead of the fuse, so\nthe gauge stays powered if F102 opens\n(TI fig. 9-12).", xt - 24, yb - 9.5)
    L.use(u, "BAT")
    # ---- VCC from the FET midpoint, PBI capacitor, tied pins
    yv = P("VCC")[1]
    r106 = L.h("R106", snap(xp - 12.7), yv, left="FET_MID", txt="ab")
    s.wire(r106.r[0], yv, xp, yv)
    s.wire(r106.l[0], yv, snap(r106.l[0] - 5.08), yv)
    s.label("FET_MID", snap(r106.l[0] - 5.08), yv, 180, False)
    L.use(u, "VCC")
    yp = P("PBI")[1]; xc = snap(xp - 8.89)
    s.wire(xp, yp, xc, yp)
    L.drop("C105", xc, yp, "Net-(U101-PBI)", side="L")
    L.use(u, "PBI")
    L.gdrop(u, "PTCEN"); L.gdrop(u, "PTC")
    # ---- sense inputs by label (the current-sense network sits elsewhere), PACK through R113 from the pack rail
    L.stub(u, "SRP", n=5.08); L.stub(u, "SRN", n=5.08); L.use(u, "SRP", "SRN")
    yk = P("PACK")[1]
    r113 = L.h("R113", snap(xp - 12.7), yk, left="PACK_P", txt="ab")
    s.wire(r113.r[0], yk, xp, yk)
    s.path((r113.l[0], yk), (snap(r113.l[0] - 2.54), yk), (snap(r113.l[0] - 2.54), yk - 5.08))
    L.term("PACK_P", snap(r113.l[0] - 2.54), yk - 5.08, "U")
    L.use(u, "PACK")
    # ---- thermistors
    for pin, th in (("TS1", "TH101"), ("TS4", "TH104")):
        y = P(pin)[1]; xx = snap(xp - 12.7)
        s.wire(xp, y, xx, y)
        L.drop(th, xx, y, L.netat(u, pin), side="L")
        L.use(u, pin)
    for pin, jw, jr in (("TS2", "J117", "J118"), ("TS3", "J119", "J120")):
        y = P(pin)[1]; xx = snap(xp - 17.78)
        s.wire(xp, y, xx, y); L.pad(jw, xx, y, "L")
        L.pad(jr, xx, y + 7.62, "L")
        s.path((xx, y + 7.62), (xx + 3.81, y + 7.62), (xx + 3.81, y + 11.43)); L.term("CELL_1N", xx + 3.81, y + 11.43, "D")
        L.use(u, pin)
    L.note("External cell thermistors (TS2, TS3) are wired in at the pads;\nTS1 and TS4 are on-board NTCs. Returns go to CELL_1N.", xp - 62, P("TS1")[1] - 7)
    # ---- right side: gate-drive outputs, fuse, SMBus through 100 ohm, interrupt inverter
    xo = P("CHG")[0]
    L.stub(u, "CHG", n=6.35); L.stub(u, "DSG", n=6.35); L.use(u, "CHG", "DSG")
    for pin, rr in (("FUSE", "R126"), ("SMBC", "R115"), ("SMBD", "R116")):
        y = P(pin)[1]; net = L.netat(u, pin)
        r = L.h(rr, snap(xo + 10.16), y, left=net, txt="ab")
        s.wire(xo, y, r.l[0], y)
        other = r.nr
        s.wire(r.r[0], y, snap(r.r[0] + 5.08), y); L.lab(other, snap(r.r[0] + 5.08), y, "R")
        L.use(u, pin)
    yq = P("BTP_INT")[1]; net = L.netat(u, "BTP_INT")
    q103 = L._sym("Q103", snap(xo + 25.4 + 5.08), yq, 0, ref_at=(snap(xo + 25.4 + 10.0), yq - 3.0, "l"), val_at=(snap(xo + 25.4 + 10.0), yq - 1.0, "l"))
    xg = snap(xo + 25.4)
    s.wire(xo, yq, xg, yq)
    L.drop("R117", snap(xo + 12.7), yq, net, side="L")
    s.wire(q103.pin("S")[0], q103.pin("S")[1], q103.pin("S")[0], q103.pin("S")[1] + 2.54); s.gnd(q103.pin("S")[0], q103.pin("S")[1] + 2.54)
    dx, dy = q103.pin("D")
    s.wire(dx, dy, dx, dy - 2.54); L.term("IRQ_N", dx, dy - 2.54, "U")
    L.use(u, "BTP_INT")
    L.note("Q103 inverts the gauge interrupt\nonto the shared IRQ_N line.", xo + 19.0, yq + 14)
    # PRES/SHUTDN, DISP and VSS are tied to the Kelvin ground
    xj = snap(xo + 3.81); yd1, yd2 = P("PRES/SHUTDN")[1], P("DISP")[1]
    s.wire(xo, yd1, xj, yd1); s.wire(xo, yd2, xj, yd2); s.path((xj, yd1), (xj, yd2 + 3.81)); L.term("CELL_1N", xj, yd2 + 3.81, "D")
    L.use(u, "PRES/SHUTDN", "DISP")
    L.gdrop(u, "VSS")
    L.finish(u)
    return u


def power_path(L, x0, yp):
    """Pack+ wire, fuse, back-to-back charge and discharge FETs, load. Left to right, with the gate networks below,
    the ESD capacitors across the FET pair above, and the fuse heater FET under the fuse."""
    s = L.s
    # the path
    L.pad("J112", x0, yp, "L")
    f102 = L._sym("F102", snap(x0 + 20.32), yp, 0, ref_at=(snap(x0 + 20.32), yp - 5.2, "c"), val_at=(snap(x0 + 20.32), yp - 3.4, "c"))
    s.wire(x0, yp, f102.pin("1")[0], yp)
    q1 = L.fet("Q101", snap(x0 + 78.74), yp)
    s.wire(f102.pin("2")[0], yp, q1.pin("S")[0], yp)
    q2 = L.fet("Q102", snap(x0 + 105.41), yp, drain_left=True)
    s.wire(q1.pin("D")[0], yp, q2.pin("D")[0], yp)
    xmid = snap((q1.pin("D")[0] + q2.pin("D")[0]) / 2)
    s.label("FET_MID", snap(xmid - 2.54), yp, 0, False)
    xl = snap(q2.pin("S")[0] + 68.0)
    s.wire(q2.pin("S")[0], yp, xl, yp)
    L.pad("J113", xl, yp, "R")
    # WAKE tap on CELL_P
    xw = snap(x0 + 30.48)
    r118 = L.v("R118", xw, yp + 3.81, top="CELL_P")
    L.pad("TP113", r118.b[0], r118.b[1], "D")
    s.label("CELL_P", snap(xw + 6.35), yp, 0, False) if False else None
    # Q101 gate network: CHG through R109, pull-down R110 to CELL_P
    yg1 = snap(yp + 17.78)
    xr110 = snap(q1.pin("S")[0] - 7.62)
    r110 = L.v("R110", xr110, snap(yp + 3.81), top="CELL_P")
    s.wire(xr110, r110.b[1], xr110, yg1)
    gx, gy = q1.pin("G")
    s.path((gx, gy), (gx, yg1)); s.wire(xr110, yg1, gx, yg1)
    r109 = L.h("R109", snap(xr110 - 8.89), yg1, left="CHG", txt="ab")
    s.wire(r109.r[0], yg1, xr110, yg1)
    s.wire(r109.l[0], yg1, snap(r109.l[0] - 3.81), yg1); L.lab("CHG", snap(r109.l[0] - 3.81), yg1, "L")
    # Q102 gate network: DSG through R111, R112 and the zener D103 to the pack side
    yg2 = snap(yp + 30.48)
    gx2, gy2 = q2.pin("G")
    s.path((gx2, gy2), (gx2, yg2))
    r111 = L.h("R111", snap(gx2 - 10.16), yg2, left="DSG", txt="ab")
    s.wire(r111.r[0], yg2, gx2, yg2)
    s.wire(r111.l[0], yg2, snap(r111.l[0] - 5.08), yg2); L.lab("DSG", snap(r111.l[0] - 5.08), yg2, "L")
    xs2 = q2.pin("S")[0]
    xd = snap(xs2 + 10.16); xz = snap(xd + 12.7)
    r112 = L.v("R112", xd, snap(yp + 3.81), top="PACK_P")
    d103 = L.v("D103", xz, snap(yp + 3.81), top="PACK_P")
    s.wire(xd, r112.b[1], xd, yg2); s.wire(xz, d103.b[1], xz, yg2); s.wire(gx2, yg2, xz, yg2)
    # ESD capacitors across the FET pair
    ye = snap(yp - 17.78)
    xa = snap(q1.pin("S")[0] - 2.54); xb = snap(xs2 + 5.08)
    c110 = L.h("C110", snap(xa + 12.7), ye, left="CELL_P", txt="ab")
    c111 = L.h("C111", snap(xb - 12.7), ye, left="Net-(C110-Pad2)", txt="ab")
    s.wire(xa, yp, xa, ye); s.wire(xa, ye, c110.l[0], ye); s.wire(c110.r[0], ye, c111.l[0], ye)
    s.wire(c111.r[0], ye, xb, ye); s.wire(xb, ye, xb, yp)
    L.note("C110 and C111 in series across the FETs: ESD protection\nthat one shorted capacitor cannot bypass.", xa, ye - 8)
    # split bulk capacitor to ground and the test point
    xc = snap(xd + 31.0)
    c107 = L.v("C107", xc, snap(yp + 3.81), top="PACK_P")
    c108 = L.v("C108", xc, snap(yp + 3.81 + 7.62 + 2.54), top="PACK_CMID")
    s.wire(xc, c107.b[1], xc, c108.t[1]); L.term("GND", c108.b[0], c108.b[1], "D")
    xt = snap(xc + 8.89)
    s.wire(xt, yp, xt, yp - 5.08); L.term("PACK_P", xt, yp - 5.08, "U")
    xtp = snap(xt + 9.0)
    L.pad("TP106", xtp, yp, "U")
    # fuse heater FET under the fuse
    hx, hy = f102.pin("HTR")
    q104 = L._sym("Q104", snap(hx - 2.54), snap(hy + 5.08 + 5.08), 0, ref_at=(snap(hx + 4.0), hy + 9.0, "l"), val_at=(snap(hx + 4.0), hy + 11.0, "l"))
    s.wire(hx, hy, hx, q104.pin("D")[1])
    sx, sy = q104.pin("S"); s.wire(sx, sy, sx, sy + 2.54); s.gnd(sx, sy + 2.54)
    gx4, gy4 = q104.pin("G")
    xg4 = snap(gx4 - 17.78)
    s.wire(gx4, gy4, xg4, gy4)
    L.drop("R125", snap(gx4 - 6.35), gy4, "Net-(Q104-G)", side="L")
    L.drop("C118", xg4, gy4, "Net-(Q104-G)", side="L")
    s.wire(xg4, gy4, snap(xg4 - 6.35), gy4); L.lab("Net-(Q104-G)", snap(xg4 - 6.35), gy4, "L")
    return q1


def sense_and_protector(L, x0, y0):
    s = L.s
    # ---- current sense: pack minus wire, shunt, load ground; Kelvin taps with an RC filter to the gauge
    yn = snap(y0 + 8.0)
    L.pad("J108", x0, yn, "L")
    rs = L.h("RS101", snap(x0 + 30.48), yn, left="CELL_N", txt="aa")
    s.wire(x0, yn, rs.l[0], yn)
    xa = snap(rs.l[0] - 7.62); xb = snap(rs.r[0] + 7.62)
    xg = snap(xb + 7.62)
    s.wire(rs.r[0], yn, snap(xg + 12.7), yn)
    L.pad("J114", snap(xg + 12.7), yn, "R")
    L.term("GND", xg, yn + 5.08, "D") if False else None
    s.path((xg, yn), (xg, yn + 5.08)); s.gnd(xg, yn + 5.08)
    L.pad("TP109", snap(xg + 6.35), yn, "U")
    ysn = snap(yn + 15.24)
    r107 = L.v("R107", xa, snap(yn + 3.81), top="CELL_N")
    r108 = L.v("R108", xb, snap(yn + 3.81), top="GND")
    s.wire(xa, yn, xa, yn)
    s.wire(xa, r107.b[1], xa, ysn); s.wire(xb, r108.b[1], xb, ysn)
    c106 = L.h("C106", snap((xa + xb) / 2), ysn, left="SRP", txt="bb")
    s.wire(xa, ysn, c106.l[0], ysn); s.wire(c106.r[0], ysn, xb, ysn)
    s.label("SRP", snap(xa - 2.54), ysn, 180, False); s.wire(xa, ysn, snap(xa - 2.54), ysn)
    s.label("SRN", snap(xb + 2.54), ysn, 0, False); s.wire(xb, ysn, snap(xb + 2.54), ysn)
    L.note("R107, R108 and C106 form the Kelvin filter;\nSRP and SRN go to the gauge.", x0, ysn + 12)


def protector(L, x0, y0):
    """BQ294700 second-level protector: cell inputs on the left like the gauge, supply and outputs on the right."""
    s = L.s
    gl = {"V3": 12.7, "V2": 12.7, "V1": 12.7}
    gr = {"VSS": 17.78, "CD": 17.78, "OUT": 17.78}
    u = L.ic("U102", x0, y0, gaps={"L": gl, "R": gr}, text="above")
    P = u.pin; xp = P("V4")[0]
    xn = snap(xp - 12.7)
    rows = [("V4", "R119", "CELL_4P"), ("V3", "R120", "CELL3"), ("V2", "R121", "CELL2"), ("V1", "R122", "CELL1")]
    ys = {}
    for pin, rr, tap in rows:
        y = P(pin)[1]; ys[pin] = y
        r = L.h(rr, snap(xn - 8.89), y, left=tap, txt="ab")
        s.wire(r.r[0], y, xp, y)
        s.wire(r.l[0], y, snap(r.l[0] - 5.08), y); L.lab(tap, snap(r.l[0] - 5.08), y, "L")
        L.use(u, pin)
    for a, b, cc in (("V4", "V3", "C112"), ("V3", "V2", "C113"), ("V2", "V1", "C114")):
        c_ = L.v(cc, xn, snap((ys[a] + ys[b]) / 2), top=L.netat(u, a))
        s.wire(xn, ys[a], xn, c_.t[1]); s.wire(xn, c_.b[1], xn, ys[b])
    c115 = L.v("C115", xn, snap(ys["V1"] + 3.81 + 2.54 + 1.27), top=L.netat(u, "V1"))
    s.wire(xn, ys["V1"], xn, c115.t[1]); L.term("CELL_1N", c115.b[0], c115.b[1], "D")
    # right side
    xo = P("VDD")[0]; yv = P("VDD")[1]
    xc = snap(xo + 8.89)
    s.wire(xo, yv, xc, yv)
    L.drop("C116", xc, yv, L.netat(u, "VDD"))
    r123 = L.h("R123", snap(xc + 17.78), yv, left=L.netat(u, "VDD"), txt="ab")
    s.wire(xc, yv, r123.l[0], yv)
    s.wire(r123.r[0], yv, snap(r123.r[0] + 5.08), yv); L.lab("CELL_4P", snap(r123.r[0] + 5.08), yv, "R")
    L.use(u, "VDD")
    L.gdrop(u, "VSS")
    yc = P("CD")[1]; xcd = snap(xo + 8.89)
    s.wire(xo, yc, xcd, yc)
    L.drop("C117", xcd, yc, L.netat(u, "CD"))
    L.use(u, "CD")
    yo = P("OUT")[1]
    r124 = L.h("R124", snap(xo + 12.7), yo, left=L.netat(u, "OUT"), txt="ab")
    s.wire(xo, yo, r124.l[0], yo)
    s.wire(r124.r[0], yo, snap(r124.r[0] + 5.08), yo); L.lab("Net-(Q104-G)", snap(r124.r[0] + 5.08), yo, "R")
    L.use(u, "OUT")
    L.note("Independent of the gauge: 4.35 V per cell overvoltage, delay set by C117\n(about 1 to 2 s). OUT drives Q104, which heats the fuse.", xo - 10, P("OUT")[1] + 12)
    L.finish(u)
    return u
