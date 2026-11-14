"""Hand-composed drawings for sections where the textbook picture is a specific arrangement that a generic placer does not
find. A sketch gets the drawing API `d` (see draw.py, class D) and an origin, draws its parts with exact wires and returns
(width, height) in mm. SKETCHES maps the section title to (function, the parts it draws); BLOCKS names the sheet."""

def pack_path(d, X, Y):
    # ---- fuse with its heater driver on the left, then the back-to-back FETs ----
    yr = Y + 12.7
    xF = X + 56.0
    d.sym("J112", X + 3.81, yr, ref_at=(X + 2.54, yr - 9.0), val_at=(X + 2.54, yr - 7.2))
    d.wire((X + 3.81, yr), (xF - 6.35, yr))
    d.lab("CELL_P_RAW", X + 7.62, yr, "R")
    F = d.sym("F102", xF, yr, ref_at=(xF - 6.35, yr - 5.0), val_at=(xF - 6.35, yr - 3.2))
    # fuse heater: Q104 under the fuse heater pin, its gate network to the left
    yq4 = yr + 20.32
    Q = d.sym("Q104", xF - 2.54, yq4, ref_at=(xF + 5.0, yq4 - 2.0), val_at=(xF + 5.0, yq4))
    d.wire(F["3"], (F["3"][0], Q["3"][1]))
    d.lab("FUSE_HTR", F["3"][0] + 1.27, yr + 8.89, "R")
    d.wire(Q["2"], (Q["2"][0], Q["2"][1] + 2.54)); d.gnd(Q["2"][0], Q["2"][1] + 2.54, "D")
    xn = xF - 24.13
    d.wire(Q["1"], (xn, Q["1"][1])); d.dot(xn, Q["1"][1])
    d.lab("FUSE_FET_G", xn + 2.54, yq4, "R")
    # R126 in from the gauge on the left, R125 to ground below, C118 up to CELL_1N
    l_, r_ = d.hor("R126", xn - 10.16, yq4, "GAUGE_FUSE", above=True)
    d.wire((r_, yq4), (xn, yq4)); d.wire((l_, yq4), (l_ - 2.54, yq4)); d.lab("GAUGE_FUSE", l_ - 2.54, yq4, "L")
    t, b = d.vert("R125", xn, yq4 + 7.62, "FUSE_FET_G", "R")
    d.wire((xn, yq4), (xn, t)); d.gnd(xn, b, "D")
    t, b = d.vert("C118", xn, yq4 - 9.0, "CELL_1N", "R")
    d.wire((xn, yq4), (xn, b)); d.wire((xn, t), (xn, t - 2.54)); d.lab("CELL_1N", xn, t - 2.54, "L")

    # ---- charge FET Q101 and discharge FET Q102, drains joined in the middle ----
    ycp = yr + 40.64                       # CELL_P and PACK_P run along here, under the FETs
    yq = ycp - 12.7
    yg = yq - 1.27
    xg1 = xF + 33.02                      # CHG_G node
    xq1 = xg1 + 17.78
    xq2 = xq1 + 60.96
    xg2 = xq2 + 16.51
    A = d.sym("Q101", xq1, yq, ref_at=(xq1 - 6.35, yq - 8.0), val_at=(xq1 - 6.35, yq - 6.0))
    B = d.sym("Q102", xq2, yq, mirror=True, ref_at=(xq2 - 6.35, yq - 8.0), val_at=(xq2 - 6.35, yq - 6.0))
    # CELL_P: from the fuse down the left side, along under Q101 to its source drop
    xcl = xg1 - 12.7
    d.wire(F["2"], (xcl, yr), (xcl, ycp), (A["1"][0] + 2.54, ycp))
    d.lab("CELL_P", F["2"][0] + 1.27, yr, "R")
    d.wire(A["1"], (A["1"][0] + 2.54, A["1"][1]), (A["1"][0] + 2.54, ycp))
    # drains: FET_MID joins them
    d.wire(A["5"], B["5"]); d.lab("FET_MID", (A["5"][0] + B["5"][0]) / 2 - 5.0, A["5"][1], "R")
    # PACK_P: out to the right
    xs2 = B["1"][0] - 2.54
    d.wire(B["1"], (xs2, B["1"][1]), (xs2, ycp), (xg2 + 25.4, ycp))
    # CHG gate network
    d.wire(A["4"], (xg1, A["4"][1])); d.dot(xg1, A["4"][1])
    t, b = d.vert("R109", xg1, yg - 6.35, "CHG", "L")
    d.wire((xg1, b), (xg1, yg)); d.wire((xg1, t), (xg1, t - 2.54)); d.lab("CHG", xg1, t - 2.54, "L")
    t, b = d.vert("R110", xg1, yg + 7.62, "CHG_G", "L")
    d.wire((xg1, yg), (xg1, t)); d.wire((xg1, b), (xg1, ycp)); d.dot(xg1, ycp)
    d.lab("CHG_G", xg1 + 2.54, yg, "R")
    # DSG gate network, with the zener across R112
    d.wire(B["4"], (xg2, B["4"][1])); d.dot(xg2, B["4"][1])
    t, b = d.vert("R111", xg2, yg - 6.35, "DSG", "R")
    d.wire((xg2, b), (xg2, yg)); d.wire((xg2, t), (xg2, t - 2.54)); d.lab("DSG", xg2, t - 2.54, "R")
    t, b = d.vert("R112", xg2, yg + 7.62, "DSG_G", "L")
    d.wire((xg2, yg), (xg2, t)); d.wire((xg2, b), (xg2, ycp)); d.dot(xg2, ycp)
    d.lab("DSG_G", xq2 + 7.62, yg, "R")
    xz = xg2 + 7.62
    d.wire((xg2, yg), (xz, yg)); d.dot(xg2, yg)
    t, b = d.vert("D103", xz, yg + 7.62, "DSG_G", "R")
    d.wire((xz, yg), (xz, t)); d.wire((xz, b), (xz, ycp)); d.dot(xz, ycp)
    # ESD capacitors across both FETs, in series
    xa, xb = A["1"][0] + 2.54, xs2
    ye = ycp + 10.16
    xm = (xa + xb) / 2
    d.wire((xa, ycp), (xa, ye)); d.dot(xa, ycp)
    l_, r_ = d.hor("C110", xa + 10.16, ye, "CELL_P", above=False)
    d.wire((xa, ye), (l_, ye))
    l2, r2 = d.hor("C111", xb - 10.16, ye, "ESD_MID", above=False)
    d.wire((r_, ye), (l2, ye)); d.lab("ESD_MID", r_ + 1.27, ye, "R")
    d.wire((r2, ye), (xb, ye), (xb, ycp)); d.dot(xb, ycp)
    # wake-up pull from CELL_P to its test point
    xw = xcl + 10.16
    t, b = d.vert("R118", xw, ycp + 7.62, "CELL_P", "R")
    d.wire((xw, ycp), (xw, t)); d.dot(xw, ycp)
    d.wire((xw, b), (xw, b + 3.81)); d.lab("WAKE", xw, b + 3.81, "L")
    d.sym("TP113", xw + 12.7, b + 3.81, ref_at=(xw + 14.5, b + 1.0), val_at=(xw + 14.5, b + 3.0))
    d.wire((xw, b + 3.81), (xw + 12.7, b + 3.81))
    # PACK_P rail: a coupling divider and the label
    xp = xz + 12.7
    t, b = d.vert("C107", xp, ycp + 7.62, "PACK_P", "R")
    d.wire((xp, ycp), (xp, t)); d.dot(xp, ycp)
    t2, b2 = d.vert("C108", xp, b + 5.08 + 3.81, "PACK_CMID", "R")
    d.wire((xp, b), (xp, t2)); d.lab("PACK_CMID", xp, (b + t2) / 2, "L"); d.dot(xp, (b + t2) / 2)
    d.gnd(xp, b2, "D")
    xe = xp + 10.16
    d.wire((xp, ycp), (xe, ycp)); d.lab("PACK_P", xe, ycp, "R")
    return xe + 20, ycp + 32 - Y

SKETCHES = {
    "Pack path: fuse, back-to-back protection FETs, fuse heater driver":
        (pack_path, ["J112", "F102", "Q104", "R125", "R126", "C118", "Q101", "Q102", "R109", "R110", "R111", "R112", "D103",
                     "C110", "C111", "C107", "C108", "R118", "TP113"]),
}
BLOCKS = {"Pack path: fuse, back-to-back protection FETs, fuse heater driver": "Cells and Gauge"}

def applies(title, block):
    b = BLOCKS[title]
    return block in b if isinstance(b, (tuple, list)) else block == b

def refs_of(title, block):
    r = SKETCHES[title][1]
    return r(block) if callable(r) else r

def current_sense(d, X, Y):
    """RS101 in the return path with its Kelvin filter: R107 and R108 from the two ends, C106 across SRP and SRN."""
    yt, yb = Y + 6.35, Y + 30.48
    xr = X + 6.35
    t, b = d.vert("RS101", xr, (yt + yb) / 2, "CELL_N", "L")
    d.wire((xr, yt), (xr, t)); d.wire((xr, b), (xr, yb))
    d.wire((xr, yt), (xr - 5.08, yt)); d.lab("CELL_N", xr - 5.08, yt, "L")
    d.dot(xr, yt)
    d.gnd(xr, yb, "D"); d.dot(xr, yb)
    l_, r_ = d.hor("R107", xr + 14.0, yt, "CELL_N", above=True)
    d.wire((xr, yt), (l_, yt))
    xs = r_ + 10.16
    d.wire((r_, yt), (xs, yt)); d.dot(xs, yt); d.lab("SRP", xs + 2.54, yt, "R"); d.wire((xs, yt), (xs + 2.54, yt))
    t2, b2 = d.vert("C106", xs, (yt + yb) / 2, "SRP", "R")
    d.wire((xs, yt), (xs, t2)); d.wire((xs, b2), (xs, yb)); d.dot(xs, yb)
    l2, r2 = d.hor("R108", xr + 14.0, yb, "GND", above=False)
    d.wire((xr, yb), (l2, yb)); d.wire((r2, yb), (xs, yb)); d.wire((xs, yb), (xs + 2.54, yb)); d.lab("SRN", xs + 2.54, yb, "R")
    d.text("Kelvin sense: SRP/SRN are taken at the two ends of RS101", X, Y + 38.0, 1.0)
    return xs + 20, 42

SKETCHES["Current sense"] = (current_sense, ["RS101", "R107", "R108", "C106"])
BLOCKS["Current sense"] = "Cells and Gauge"

def antenna_pi(d, X, Y):
    """Pi match as in the application note: series C313, R321 in line, a shunt to ground at each of the three nodes."""
    y = Y + 12.7
    x = X + 12.7
    d.wire((x, y), (x + 5.08, y)); d.lab("RFIO", x, y, "L")
    l1, r1 = d.hor("C313", x + 5.08 + 3.81, y, "RFIO", above=True)
    xm = r1 + 12.7
    d.wire((r1, y), (xm, y)); d.dot(xm, y); d.lab("RF_MID", r1 + 1.27, y, "R")
    t, b = d.vert("C314", xm, y + 7.62, "RF_MID", "R")
    d.wire((xm, y), (xm, t)); d.gnd(xm, b, "D")
    l2, r2 = d.hor("R321", xm + 5.08 + 3.81, y, "RF_MID", above=True)
    d.wire((xm, y), (l2, y))
    xa = r2 + 12.7
    d.wire((r2, y), (xa + 5.08, y)); d.dot(xa, y); d.lab("ANT_IN", xa + 5.08, y, "R")
    t, b = d.vert("C315", xa, y + 7.62, "ANT_IN", "R")
    d.wire((xa, y), (xa, t)); d.gnd(xa, b, "D")
    d.text("C314 is the DNP shunt of TI's pi match; retune all three on this board", X, Y + 30.0, 1.0)
    return xa + 22 - X, 32

SKETCHES["Antenna match (pi network between RFIO and ANT_IN)"] = (antenna_pi, ["C313", "C314", "R321", "C315"])
BLOCKS["Antenna match (pi network between RFIO and ANT_IN)"] = "MCU"


def usb_front(d, X, Y):
    """USB-C receptacle on the left, port protector U405 to its right, CC lines wired straight across; VBUS runs along the
    top with its bulk caps and TVS hanging from it; the protector's supply caps hang from buses above it."""
    base = 400 if d.block.endswith("1") else 500
    J, D_, CB, CS, U, C51, C52, C1, C2 = (f"J{base + 1}", f"D{base + 1}", f"C{base + 6}", f"C{base + 50}", f"U{base + 5}",
                                          f"C{base + 51}", f"C{base + 52}", f"C{base + 1}", f"C{base + 2}")
    xJ, yJ = X + 24.0, Y + 52.0
    pj = d.sym(J, xJ, yJ, ref_at=(xJ - 15.0, yJ - 21.0), val_at=(xJ - 15.0, yJ - 19.0))
    # VBUS leaves upward, then along the top: bulk caps and the TVS hang from it, clear of the CC lines
    yv0 = pj["A4"][1]
    xv0 = pj["A4"][0]
    yv = yv0 - 22.86
    vb = d.net(J, "A4")
    d.wire(pj["A4"], (xv0 + 5.08, yv0), (xv0 + 5.08, yv), (xv0 + 82.0, yv))
    for r, dx in ((CB, 12.7), (CS, 31.0)):
        t, b = d.vert(r, xv0 + dx, yv + 8.0, vb, "R")
        d.wire((xv0 + dx, yv), (xv0 + dx, t)); d.gnd(xv0 + dx, b, "D"); d.dot(xv0 + dx, yv)
    pd_ = d.sym(D_, xv0 + 58.0, yv + 9.0, ref_at=(xv0 + 65.0, yv + 6.0), val_at=(xv0 + 65.0, yv + 8.0))
    d.wire((xv0 + 58.0, yv), pd_["4"]); d.dot(xv0 + 58.0, yv); d.gnd(pd_["1"][0], pd_["1"][1], "D")
    d.lab(vb, xv0 + 82.0, yv, "R")
    # grounds and unused pins of the receptacle
    d.wire(pj["A1"], (pj["A1"][0], pj["A1"][1] + 2.54)); d.gnd(pj["A1"][0], pj["A1"][1] + 2.54, "D")
    d.wire(pj["SH"], (pj["SH"][0], pj["SH"][1] + 2.54)); d.gnd(pj["SH"][0], pj["SH"][1] + 2.54, "D")
    d.sheet_nc(*pj["A8"]); d.sheet_nc(*pj["B8"])
    # D+ and D- tied together: dedicated charging port
    xd = pj["A7"][0] + 2.54
    d.wire((xd, pj["A7"][1]), (xd, pj["B6"][1]))
    for k in ("A7", "B7", "A6", "B6"): d.wire(pj[k], (xd, pj[k][1]))
    d.dot(xd, pj["B7"][1]); d.dot(xd, pj["A6"][1])
    d.wire((xd, pj["B6"][1]), (xd + 2.54, pj["B6"][1])); d.lab(d.net(J, "A7"), xd + 2.54, pj["B6"][1], "R")
    # protector
    xU = xJ + 15.24 + 128.0
    yU = pj["A5"][1] + 11.43
    pu = d.sym(U, xU, yU, ref_at=(xU - 16.0, yU + 20.0), val_at=(xU - 16.0, yU + 22.0))
    d.wire(pj["A5"], pu["4"]); d.lab(d.net(J, "A5"), pj["A5"][0] + 4.0, pj["A5"][1], "R")
    d.wire(pj["B5"], pu["5"]); d.lab(d.net(J, "B5"), pj["B5"][0] + 4.0, pj["B5"][1], "R")
    for pin, src in (("7", "A5"), ("6", "B5")):
        d.wire(pu[pin], (pu[pin][0] - 2.54, pu[pin][1])); d.lab(d.net(U, pin), pu[pin][0] - 2.54, pu[pin][1], "L")
    for pin in ("1", "2", "20", "19", "15", "14"): d.sheet_nc(*pu[pin])
    # CC1 / CC2 leave to the right, bent apart so each shunt cap hangs in clear space
    bx = pu["12"][0] + 5.08
    y1, y2 = pu["12"][1], pu["11"][1]
    d.wire(pu["12"], (bx, y1), (bx, y1 - 10.16), (bx + 40.0, y1 - 10.16))
    d.wire(pu["11"], (bx, y2), (bx, y2 + 10.16), (bx + 40.0, y2 + 10.16))
    t, b = d.vert(C1, bx + 14.0, y1 - 10.16 + 8.0, d.net(U, "12"), "R")
    d.wire((bx + 14.0, y1 - 10.16), (bx + 14.0, t)); d.gnd(bx + 14.0, b, "D"); d.dot(bx + 14.0, y1 - 10.16)
    t, b = d.vert(C2, bx + 14.0, y2 + 10.16 + 8.0, d.net(U, "11"), "R")
    d.wire((bx + 14.0, y2 + 10.16), (bx + 14.0, t)); d.gnd(bx + 14.0, b, "D"); d.dot(bx + 14.0, y2 + 10.16)
    d.lab(d.net(U, "12"), bx + 40.0, y1 - 10.16, "R"); d.lab(d.net(U, "11"), bx + 40.0, y2 + 10.16, "R")
    d.wire(pu["9"], (pu["9"][0] + 2.54, pu["9"][1])); d.lab(d.net(U, "9"), pu["9"][0] + 2.54, pu["9"][1], "R")
    # protector ground pins joined to one symbol
    yg = pu["8"][1] + 2.54
    xm_ = (pu["8"][0] + pu["16"][0]) / 2
    d.wire(pu["8"], (pu["8"][0], yg), (xm_, yg)); d.wire(pu["16"], (pu["16"][0], yg), (xm_, yg)); d.gnd(xm_, yg, "D")
    # supply buses above the protector: VPWR to the left, VBIAS to the right, bypass caps hanging from them
    yb = pu["10"][1] - 30.48
    d.wire(pu["10"], (pu["10"][0], yb), (pu["10"][0] - 22.0, yb)); d.lab(d.net(U, "10"), pu["10"][0] - 22.0, yb, "L")
    t, b = d.vert(C52, pu["10"][0] - 10.0, yb + 8.0, d.net(U, "10"), "L")
    d.wire((pu["10"][0] - 10.0, yb), (pu["10"][0] - 10.0, t)); d.gnd(pu["10"][0] - 10.0, b, "D"); d.dot(pu["10"][0] - 10.0, yb)
    d.wire(pu["3"], (pu["3"][0], yb), (pu["3"][0] + 10.0, yb))
    t, b = d.vert(C51, pu["3"][0] + 10.0, yb + 8.0, d.net(U, "3"), "R")
    d.wire((pu["3"][0] + 10.0, yb), (pu["3"][0] + 10.0, t)); d.gnd(pu["3"][0] + 10.0, b, "D")
    return xU + 16.51 + 50.0 - X, 100.0

SKETCHES["USB-C connector and port protection"] = (usb_front, lambda b: [f"J{(400 if b.endswith('1') else 500) + 1}", f"D{(400 if b.endswith('1') else 500) + 1}",
    *[f"C{(400 if b.endswith('1') else 500) + k}" for k in (6, 50, 51, 52, 1, 2)], f"U{(400 if b.endswith('1') else 500) + 5}"])
BLOCKS["USB-C connector and port protection"] = ("USB Port 1", "USB Port 2")
