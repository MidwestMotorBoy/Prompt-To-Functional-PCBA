"""Cells and Gauge page, drawn by hand-placed coordinates.

Top: the pack current path left to right (PACK+ wire, fuse, CHG FET, DSG FET, load), ESD caps across the FETs.
Left below: BQ40Z50 with every input fanned out to its own lane: sense wires on the far left, the RC filters,
the cell-voltage ladder, the Kelvin shunt, the thermistors.  Right of it: the SMBus / IRQ outputs.
Right below: BQ294700 second level protector with its fuse ignition FET."""


def layout(c):
    S = c.sheet
    comps, pinnet, sn, sh = c.comps, c.pinnet, c.snap, c.short
    G = 1.27

    def N(r, p): return pinnet[(r, str(p))]

    def lab(net, x, y, ang=0): S.label(sh(net), x, y, ang, net in c.glob)

    def put(r, x, y, ang=0, mirror=False, ref_at=None, val_at=None):
        l, n = comps[r]["lib"].split(":")
        S.symbol(l, n, r, comps[r]["value"], x, y, ang, footprint=comps[r]["footprint"], fields=comps[r]["fields"],
                 ref_at=ref_at, val_at=val_at, mirror=mirror)

    def hpart(r, xc, y, left_net, above=True, dy=0.0):
        if above:
            return c.horiz(r, xc, y, left_net, ref_at=(xc - 3.81, y - 5.0 - dy), val_at=(xc - 3.81, y - 3.0 - dy))
        return c.horiz(r, xc, y, left_net, ref_at=(xc - 3.81, y + 3.0), val_at=(xc - 3.81, y + 5.0))

    def flag(x, y, net, down=True):
        """short stub with a label: used for CELL_1N (the gauge ground) and other far-away nets"""
        if net == "GND":
            S.gnd(x, y); return
        S.wire(x, y, x, y + 2.54); S.wire(x, y + 2.54, x + 1.27, y + 2.54); lab(net, x + 1.27, y + 2.54, 0)

    def vhang(r, x, y0, up, gap=2.54):
        yc = sn(y0 + gap + 3.81)
        t, b = c.small(r, x, yc, up)
        S.wire(x, y0, x, t)
        return b

    def term(r, x, y, side):
        """wire terminal with its pin at (x, y); body to the left (side=L) or to the right (side=R)"""
        l, n = comps[r]["lib"].split(":")
        tp = (n == "TestPoint")
        if side == "L":
            ang = 90 if tp else 180
            xc = x if tp else x - 5.08
            d_ = 2.54 if tp else -0.5
            ra, va = (x - d_, y - 1.5), (x - d_, y + 1.5)
            put(r, xc, y, ang, ref_at=ra, val_at=va)
        else:
            ang = 270 if tp else 0
            xc = x if tp else x + 5.08
            put(r, xc, y, ang, ref_at=(x + 5.08, y - 1.5), val_at=(x + 5.08, y + 1.5))

    def fan(px, sg, pins, base=0.0):
        """pins: [(pin_y, lane_y)] top to bottom, pin end at px.  Returns x where all lanes start."""
        n = len(pins)
        up = [k for k in range(n) if pins[k][1] < pins[k][0] - 0.01]
        dn = [k for k in range(n) if pins[k][1] > pins[k][0] + 0.01]
        col = {}
        for i, k in enumerate(up): col[k] = i + 1
        for i, k in enumerate(reversed(dn)): col[k] = i + 1
        xs = px + sg * (base + 2.54 * (max([0] + list(col.values())) + 1))
        for k, (py, ly) in enumerate(pins):
            if k in col:
                xc = px + sg * (base + 2.54 * col[k])
                S.wire(px, py, xc, py); S.wire(xc, py, xc, ly); S.wire(xc, ly, xs, ly)
            else:
                S.wire(px, py, xs, ly) if abs(py - ly) < 0.01 else None
        return xs

    S.text(S.title, 20.32, 21, 3.0)

    # ================================================================== A: pack current path
    S.text("Pack current path: cells (PACK+ wire), fuse, charge and discharge FETs, load", 20.32, 30, 2.0)
    Y1 = 66.04
    yq = Y1 - 12.7
    xF, xq1, xq2 = 88.9, 127.0, 152.4
    J = "J112"
    term(J, 50.8, Y1, "L"); S.wire(50.8, Y1, xF - 6.35, Y1); lab(N(J, 1), 55.88, Y1, 0)
    put("F102", xF, Y1, ref_at=(xF - 3.8, Y1 - 7.6), val_at=(xF - 3.8, Y1 - 5.6))
    S.wire(xF + 6.35, Y1, xq1 + 6.35, Y1)
    lab(N("F102", 2), 97.79, Y1, 0)
    S.wire(xF, Y1 + 5.08, xF, Y1 + 7.62); lab(N("F102", 3), xF, Y1 + 7.62, 180)
    # CHG FET
    put("Q101", xq1, yq, ref_at=(xq1 - 6.35, yq - 9), val_at=(xq1 - 6.35, yq - 7))
    S.text("Charge FET", xq1 - 6.35, yq - 11.5)
    S.wire(xq1 + 6.35, yq + G, xq1 + 6.35, Y1)                      # source to CELL_P
    gy_ = yq - G
    xn1 = xq1 - 15.24
    S.junction(xn1, gy_)
    # R109: gate side on the right
    xl, xrr = hpart("R109", xn1 - 8.89, gy_, N("R109", 1))
    # R109 pin 1 is CHG (left), pin 2 is CHG_G (right)
    S.wire(xl, gy_, xl - 2.54, gy_); lab(N("R109", 1), xl - 2.54, gy_, 180)
    S.wire(xrr, gy_, xq1 - 6.35, gy_)
    yc = sn(gy_ + 7.62 + 3.81 - 5.08 + 1.27)
    t, b = c.small("R110", xn1, 57.15, N("R110", 1))
    S.wire(xn1, gy_, xn1, t); S.wire(xn1, b, xn1, Y1); S.junction(xn1, Y1)
    # DSG FET, mirrored so its drain faces the CHG FET's drain
    put("Q102", xq2, yq, mirror=True, ref_at=(xq2 + 6.35, yq - 9), val_at=(xq2 + 6.35, yq - 7))
    S.text("Discharge FET", xq2 + 6.35 - 15, yq - 11.5)
    S.wire(xq1 + 6.35, gy_, xq2 - 6.35, gy_)                        # FET_MID between the two drains
    lab(N("Q101", 5), xq1 + 7.62, gy_, 0)
    S.wire(xq2 - 6.35, yq + G, xq2 - 6.35, Y1)                      # source to PACK_P
    S.wire(xq2 + 6.35, gy_, xq2 + 33.02, gy_)
    xn2, xn3 = xq2 + 15.24, xq2 + 27.94
    S.junction(xn2, gy_); S.junction(xn3, gy_)
    t, b = c.small("R112", xn2, 57.15, N("R112", 1))
    S.wire(xn2, gy_, xn2, t); S.wire(xn2, b, xn2, Y1)
    t, b = c.small("D103", xn3, 57.15, N("D103", 1))
    S.wire(xn3, gy_, xn3, t); S.wire(xn3, b, xn3, Y1)
    xl, xrr = hpart("R111", xq2 + 33.02 + 6.35, gy_, N("R111", 2))
    S.wire(xq2 + 33.02, gy_, xl, gy_)
    S.wire(xrr, gy_, xrr + 2.54, gy_); lab(N("R111", 1), xrr + 2.54, gy_, 0)
    # load side
    xP = xq2 + 60.96
    S.wire(xq2 - 6.35, Y1, xP, Y1)
    S.junction(xn2, Y1); S.junction(xn3, Y1)
    term("J113", xP, Y1, "R")
    xg_ = xP - 25.4
    S.junction(xg_, Y1); S.wire(xg_, Y1, xg_, Y1 - 5.08); lab(N("J113", 1), xg_, Y1 - 5.08, 0)
    # ESD caps in series across both FETs
    xa, xb, ym = 124.46, 154.94, Y1 + 15.24
    for r, x in (("C110", xa), ("C111", xb)):
        b = vhang(r, x, Y1, N(r, 1) if r == "C110" else N("C111", 2))
        S.wire(x, b, x, ym)
    S.wire(xa, ym, xb, ym); S.junction(xa, Y1); S.junction(xb, Y1)
    S.text("ESD caps in series across both FETs (CELL_P to PACK_P)", xa - 2.54, ym + 5.08)
    # WAKE pull-up
    b = vhang("R118", 104.14, Y1, N("R118", 1))
    S.junction(104.14, Y1)
    S.wire(104.14, b, 104.14, b + 5.08)
    put("TP113", 104.14, b + 5.08, 180)
    # PACK_P test point, bypass chain to ground, test point
    xt = xP - 16.51
    S.junction(xt, Y1)
    b = vhang("C107", xt, Y1, N("C107", 1))
    S.wire(xt, b, xt, b + 2.54)
    t, b2 = c.small("C108", xt, sn(b + 2.54 + 3.81), N("C108", 1))
    S.gnd(xt, b2)
    S.junction(173.99, Y1)
    put("TP106", 173.99, Y1, 180, ref_at=(176.5, Y1 + 3.8), val_at=(176.5, Y1 + 6.0))

    # ================================================================== B: BQ40Z50 gauge
    gx, gy = 142.24, 167.64
    S.text("BQ40Z50 gauge: supply, cell inputs, current sense, thermistors, SMBus", 20.32, 93, 2.0)
    pb = {}
    for p in c.pins_of["U101"]: pb.setdefault(p["num"], p)
    put("U101", gx, gy, ref_at=(gx - 11.43, gy - 34), val_at=(gx - 11.43, gy - 32))
    PXL, PXR = gx - 12.7, gx + 12.7
    py = lambda num: sn(gy - pb[str(num)]["y"])
    lanes = [("32", -58.42), ("26", -48.26), ("1", -38.1), ("24", -30.48), ("2", -22.86), ("3", -10.16),
             ("4", 2.54), ("5", 15.24), ("8", 38.1), ("6", 48.26), ("27", 60.96), ("10", 73.66), ("11", 83.82),
             ("12", 93.98), ("13", 104.14), ("23", 114.3)]
    ly = {n: sn(gy + d) for n, d in lanes}
    xs = fan(PXL, -1, [(py(n), ly[n]) for n, _ in lanes])
    xs_ = xs

    def series(y, x, parts, dy=0.0):
        """parts: [(ref, left_net)] going left from x on lane y; returns left end"""
        for r, ln in parts:
            xc = x - 2.54 - 3.81
            xl, xrr = hpart(r, xc, y, ln, dy=dy)
            S.wire(x, y, xrr, y)
            x = xl
        return x

    # top lanes
    XT = xs - 60
    # BAT: R105 - D101 - 4P
    x = series(ly["32"], xs, [("R105", N("D101", 1)), ("D101", N("D101", 2))])
    xR = xs - 42.0
    S.wire(x, ly["32"], XT, ly["32"]); lab(N("D101", 2), XT + 3.81, ly["32"], 0)
    term("J116", XT, ly["32"], "L")
    # VCC: R106 - FET_MID
    x = series(ly["26"], xs, [("R106", N("R106", 1))])
    S.wire(x, ly["26"], x - 2.54, ly["26"]); lab(N("R106", 1), x - 2.54, ly["26"], 180)
    # PBI: C105 to the gauge ground
    x = series(ly["1"], xs, [("C105", N("C105", 2))])
    S.wire(x, ly["1"], x - 2.54, ly["1"]); lab(N("C105", 2), x - 2.54, ly["1"], 180)
    # PTCEN: gauge ground
    S.wire(xs, ly["24"], xs - 5.08, ly["24"]); lab("CELL_1N", xs - 5.08, ly["24"], 180)
    # cell ladder: VC4..VC1
    capx = xs - 17.78
    vc = [("2", "R104", "J116"), ("3", "R103", "J111"), ("4", "R102", "J110"), ("5", "R101", "J109")]
    for i, (pin, rr, jj) in enumerate(vc):
        y = ly[pin]
        S.wire(xs, y, capx, y); S.junction(capx, y)
        x = series(y, capx, [(rr, N(rr, 1))])
        if jj != "J116":
            S.wire(x, y, XT, y); lab(N(rr, 1), XT + 3.81, y, 0)
            term(jj, XT, y, "L")
        else:
            S.wire(x, y, xR, y)
    capn = {"2": ("C101", "3"), "3": ("C102", "4"), "4": ("C103", "5")}
    for pin, (cr, nxt) in capn.items():
        y0, y1 = ly[pin], ly[nxt]
        yc = sn((y0 + y1) / 2)
        t, b = c.small(cr, capx, yc, N("U101", pin))
        S.wire(capx, y0, capx, t); S.wire(capx, b, capx, y1)
    b = vhang("C104", capx, ly["5"], N("U101", 5))
    flag(capx, b, N("C104", 2))
    S.wire(xR, ly["32"], xR, ly["2"]); S.junction(xR, ly["32"]); S.junction(xR, ly["2"])
    # Kelvin shunt: C106 near the pins, R107 / R108, RS101 at the left
    ys, yn = ly["8"], ly["6"]
    S.wire(xs, ys, capx, ys); S.wire(xs, yn, capx, yn)
    yc = sn((ys + yn) / 2)
    t, b = c.small("C106", capx, yc, N("U101", 8))
    S.wire(capx, ys, capx, t); S.wire(capx, b, capx, yn)
    S.junction(capx, ys); S.junction(capx, yn)
    xl1, _ = hpart("R107", capx - 6.35, ys, N("R107", 1))
    S.wire(capx, ys, capx - 2.54, ys)
    xl2, _ = hpart("R108", capx - 6.35, yn, N("R108", 1), above=False)
    S.wire(capx, yn, capx - 2.54, yn)
    xsn = xl1 - 6.35
    S.wire(xl1, ys, xsn, ys); S.wire(xl2, yn, xsn, yn)
    t, b = c.small("RS101", xsn, yc, N("RS101", 1))
    S.wire(xsn, ys, xsn, t); S.wire(xsn, b, xsn, yn)
    S.junction(xsn, ys); S.junction(xsn, yn)
    S.wire(xsn, ys, XT, ys); lab("CELL_N", XT + 3.81, ys, 0)
    term("J108", XT, ys, "L")
    S.wire(xsn, yn, XT, yn)
    term("J114", XT, yn, "L")
    xg = xsn - 6.35
    S.junction(xg, yn); S.gnd(xg, yn)
    xtp = xsn - 14.0
    S.junction(xtp, yn); S.wire(xtp, yn, xtp, yn + 2.54)
    put("TP109", xtp, yn + 2.54, 180, ref_at=(xtp - 2.54, yn + 2.0), val_at=(xtp - 2.54, yn + 4.5))
    S.text("1 mOhm shunt, Kelvin sense", xsn - 24, yn + 10.5)
    # PACK sense
    x = series(ly["27"], xs, [("R113", N("R113", 1))])
    S.wire(x, ly["27"], x - 2.54, ly["27"]); lab(N("R113", 1), x - 2.54, ly["27"], 180)
    # thermistors
    x = series(ly["10"], xs, [("TH101", N("TH101", 2))], dy=2.0)
    S.wire(x, ly["10"], x - 2.54, ly["10"]); lab(N("TH101", 2), x - 2.54, ly["10"], 180)
    x = series(ly["13"], xs, [("TH104", N("TH104", 2))], dy=2.0)
    S.wire(x, ly["13"], x - 2.54, ly["13"]); lab(N("TH104", 2), x - 2.54, ly["13"], 180)
    for pin, jt, jr in (("11", "J117", "J118"), ("12", "J119", "J120")):
        y = ly[pin]
        S.wire(xs, y, XT, y); lab(N(jt, 1), XT + 6.35, y, 0)
        term(jt, XT, y, "L")
        S.wire(XT, y + 5.08, XT + 6.35, y + 5.08); lab(N(jr, 1), XT + 6.35, y + 5.08, 0)
        term(jr, XT, y + 5.08, "L")
    y = ly["23"]
    S.wire(xs, y, XT, y); lab(N("J115", 1), XT + 6.35, y, 0)
    term("J115", XT, y, "L")

    # right side of the gauge
    ry = {"31": -58.42, "28": -48.26, "25": -38.1, "19": -27.94, "18": -17.78, "15": -7.62}
    ry = {n: sn(gy + d) for n, d in ry.items()}
    xe = fan(PXR, 1, [(py(n), ry[n]) for n in ("31", "28", "25", "19", "18", "15")])
    for n in ("31", "28", "25"):
        S.wire(xe, ry[n], xe + 2.54, ry[n]); lab(N("U101", n), xe + 2.54, ry[n], 0)
    for n, rr in (("19", "R115"), ("18", "R116")):
        xl, xrr = hpart(rr, xe + 3.81 + 2.54, ry[n], N("U101", n))
        S.wire(xe, ry[n], xl, ry[n])
        S.wire(xrr, ry[n], xrr + 2.54, ry[n]); lab(N(rr, 2), xrr + 2.54, ry[n], 0)
    # BTP_INT: R117 to ground, Q103 level shifter
    yb = ry["15"]
    xq3 = xe + 30.48
    S.wire(xe, yb, xq3 - 5.08, yb)
    xh = xe + 12.7
    S.junction(xh, yb)
    b = vhang("R117", xh, yb, N("R117", 1))
    flag(xh, b, N("R117", 2))
    put("Q103", xq3, yb, ref_at=(xq3 + 4, yb - 2.5), val_at=(xq3 + 4, yb - 0.5))
    S.wire(xq3 + 2.54, yb - 5.08, xq3 + 2.54, yb - 7.62); lab(N("Q103", 3), xq3 + 2.54, yb - 7.62, 0)
    S.gnd(xq3 + 2.54, yb + 5.08)
    S.text("Gauge interrupt onto the shared IRQ_N line", xe + 5.08, yb + 20)
    # grounds and no-connects on the right
    for n in ("16", "17"):
        yy = py(n)
        S.wire(PXR, yy, PXR + 2.54, yy); lab("CELL_1N", PXR + 2.54, yy, 0)
    for p in c.pins_of["U101"]:
        if p["angle"] == 180 and (("U101", p["num"]) in c.ncset or p["num"] in ("30",)):
            S.nc(sn(gx + p["x"]), sn(gy - p["y"]))
        if p["angle"] == 180 and p["num"] in ("9", "33"):
            pass
    yy = py("9"); S.wire(PXR, yy, PXR + 2.54, yy); lab("CELL_1N", PXR + 2.54, yy, 0)

    # ================================================================== C: BQ294700 + fuse
    ux, uy = 292.0, 185.42
    S.text("BQ294700 second-level protector and fuse ignition", ux - 70, uy - 42, 2.0)
    ub = {}
    for p in c.pins_of["U102"]: ub.setdefault(p["num"], p)
    put("U102", ux, uy, ref_at=(ux - 8, uy - 17), val_at=(ux - 8, uy - 15))
    UXL, UXR = ux - 8.89, ux + 8.89
    upy = lambda n: sn(uy - ub[str(n)]["y"])
    ul = {"2": -19.05, "3": -6.35, "4": 6.35, "5": 19.05}
    ul = {n: sn(uy + d) for n, d in ul.items()}
    xs2 = fan(UXL, -1, [(upy(n), ul[n]) for n in ("2", "3", "4", "5")])
    cx2 = xs2 - 17.78
    rs = {"2": ("R119", "J116"), "3": ("R120", None), "4": ("R121", None), "5": ("R122", None)}
    for pin, (rr, _) in rs.items():
        y = ul[pin]
        S.wire(xs2, y, cx2, y); S.junction(cx2, y)
        x = series(y, cx2, [(rr, N(rr, 1))])
        S.wire(x, y, x - 2.54, y); lab(N(rr, 1), x - 2.54, y, 180)
    for pin, cr, nxt in (("2", "C112", "3"), ("3", "C113", "4"), ("4", "C114", "5")):
        y0, y1 = ul[pin], ul[nxt]
        t, b = c.small(cr, cx2, sn((y0 + y1) / 2), N("U102", pin))
        S.wire(cx2, y0, cx2, t); S.wire(cx2, b, cx2, y1)
    b = vhang("C115", cx2, ul["5"], N("U102", 5))
    flag(cx2, b, N("C115", 2))
    # VDD, VSS, CD, OUT on the right
    vy = {"1": -19.05, "7": 6.35, "8": 25.4}
    vy = {n: sn(uy + d) for n, d in vy.items()}
    xe2 = fan(UXR, 1, [(upy("1"), vy["1"]), (upy("7"), vy["7"]), (upy("8"), vy["8"])])
    y = vy["1"]
    xh = xe2 + 5.08
    S.junction(xh, y)
    b = vhang("C116", xh, y, N("C116", 1))
    flag(xh, b, N("C116", 2))
    xl, xrr = hpart("R123", xe2 + 22.86, y, N("U102", 1))
    S.wire(xe2, y, xl, y); S.wire(xrr, y, xrr + 2.54, y); lab(N("R123", 2), xrr + 2.54, y, 0)
    yy = upy("6"); S.wire(UXR, yy, UXR + 2.54, yy); lab("CELL_1N", UXR + 2.54, yy, 0)
    y = vy["7"]
    xh = xe2 + 5.08
    S.wire(xe2, y, xh, y); S.junction(xh, y)
    b = vhang("C117", xh, y, N("U102", 7))
    flag(xh, b, N("C117", 1))
    # OUT -> R124 -> Q104 gate
    y = vy["8"]
    xl, xrr = hpart("R124", xe2 + 12.7, y, N("U102", 8))
    S.wire(xe2, y, xl, y)
    xB = xrr + 12.7
    S.wire(xrr, y, xB + 12.7, y)
    S.junction(xB, y)
    b = vhang("C118", xB, y, N("C118", 1))
    flag(xB, b, N("C118", 2))
    xA = xB + 12.7
    S.junction(xA, y)
    b = vhang("R125", xA, y, N("R125", 1)); S.gnd(xA, b)
    # R126 up to the GAUGE_FUSE label
    t, b2 = c.small("R126", xA, sn(y - 2.54 - 3.81), N("R126", 1) if False else N("R126", 2))
    S.wire(xA, y, xA, b2)
    S.wire(xA, t, xA, t - 2.54); lab(N("R126", 2), xA, t - 2.54, 0)
    xq4 = xA + 5.08 + 12.7
    S.wire(xA, y, xq4 - 5.08, y)
    put("Q104", xq4, y, ref_at=(xq4 + 5, y - 3), val_at=(xq4 + 5, y - 1))
    S.wire(xq4 + 2.54, y - 5.08, xq4 + 2.54, y - 7.62); lab(N("Q104", 3), xq4 + 2.54, y - 7.62, 0)
    S.gnd(xq4 + 2.54, y + 5.08)
    S.text("Fuse heater FET", xq4 - 5, y + 12)
    notes = ["How the protection works",
             "U101 (BQ40Z50) measures the four cell voltages, the pack current across RS101 and four NTCs,",
             "and drives the CHG and DSG gates (Q101, Q102) through R109 / R111.",
             "R110 / R112 hold the gates off; D103 clamps the DSG gate in a short.",
             "U102 (BQ294700) is an independent 4.35 V per cell overvoltage detector. After its CD delay",
             "OUT turns on Q104, which heats the fuse F102 open. U101 FUSE can fire Q104 as well.",
             "U101 and U102 take CELL_1N, the 1N Kelvin tab, as their ground."]
    for i, t_ in enumerate(notes):
        S.text(t_, 254.0, 41 + 5.0 * i, 1.8 if i == 0 else 1.27)
    S.maxy = max(S.maxy, gy + 130)
    return True
