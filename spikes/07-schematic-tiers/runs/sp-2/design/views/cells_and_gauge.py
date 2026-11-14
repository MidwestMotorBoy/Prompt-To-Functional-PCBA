"""Hand-composed page for Cells and Gauge, read left to right: the gauge (U101) with its cell-tap filters and current
sense on the left and its outputs on the right; the second-level protector (U102) with the fuse ignition FET; and
below, the pack power path (fuse, back-to-back protection FETs, load).  Hints only: the circuit is unchanged."""


def layout(ctx):
    S = ctx.sheet
    comps, short, glob, pinnet, ends, snap = ctx.comps, ctx.short, ctx.glob, ctx.pinnet, ctx.ends, ctx.snap
    pins_of, horiz, small = ctx.pins_of, ctx.horiz, ctx.small
    W, J = S.wire, S.junction

    # ------------------------------------------------------------------ helpers
    def pin(ref, num, cx, cy, mirror=False):
        p = next(p for p in pins_of[ref] if p["num"] == num)
        return snap(cx + (-p["x"] if mirror else p["x"])), snap(cy - p["y"])

    def net(ref, num):
        return pinnet.get((ref, num))

    def lab(n, x, y, ang):
        """Net label (or ground symbol) at a wire end; ang is the direction the text runs (0 right, 180 left, 90 up, 270 down)."""
        if n == "GND":
            return S.gnd(x, y, {0: 90, 180: 270, 90: 180, 270: 0}[ang])
        S.label(short(n), x, y, ang, n in glob)

    def gl(n, x, y, ang):
        S.label(short(n), x, y, ang, n in glob)

    def stub(n, x, y, side, ln=2.54):
        dx, dy = {"R": (ln, 0), "L": (-ln, 0), "U": (0, -ln), "D": (0, ln)}[side]
        ang = {"R": 0, "L": 180, "U": 90, "D": 270}[side]
        W(x, y, x + dx, y + dy)
        lab(n, x + dx, y + dy, ang)

    def put(r, x, y, a=0, mirror=False, ref_at=None, val_at=None):
        lib, name = comps[r]["lib"].split(":")
        S.symbol(lib, name, r, comps[r]["value"], x, y, a, footprint=comps[r]["footprint"], fields=comps[r]["fields"],
                 ref_at=ref_at, val_at=val_at, mirror=mirror)

    def hpart(r, xr, y, left_net, txt="above"):
        """Two-pad part lying flat with its RIGHT pad at xr. Returns (left pad x, right pad x)."""
        xc = xr - 3.81
        ya, yb = (y - 5.0, y - 3.0) if txt == "above" else (y + 3.0, y + 5.0)
        return horiz(r, xc, y, left_net, ref_at=(xc - 3.81, ya), val_at=(xc - 3.81, yb))

    def hchain(y, xb, parts, gap=5.08):
        """Parts in a row running LEFT from (xb, y); parts = [(ref, net on its left pad)], nearest the IC first. Returns left end."""
        x = xb
        for r, ln in parts:
            xl, xr_ = hpart(r, snap(x - gap), y, ln)
            W(x, y, xr_, y)
            x = xl
        return x

    def hright(r, xl_, y, left_net, txt="above"):
        """Part lying flat with its LEFT pad at xl_. Returns (left pad, right pad)."""
        xc = xl_ + 3.81
        ya, yb = (y - 5.0, y - 3.0) if txt == "above" else (y + 3.0, y + 5.0)
        return horiz(r, xc, y, left_net, ref_at=(xc - 3.81, ya), val_at=(xc - 3.81, yb))

    def vhang(r, x, y, up_net, end="stub"):
        """Part hanging below a wire point (x, y), top pad on up_net. Returns bottom pad y."""
        t, b = small(r, x, snap(y + 3.81), up_net)
        W(x, y, x, t)
        dn = [n for n in ends(r) if n != up_net][0]
        if end == "stub": stub(dn, x, b, "D")
        return b

    def vup(r, x, y, dn_net):
        """Part standing on a wire point (x, y) with its bottom pad on dn_net; the top ends in a label or ground."""
        up = [n for n in ends(r) if n != dn_net][0]
        t, b = small(r, x, snap(y - 3.81), up)
        W(x, b, x, y)
        stub(up, x, t, "U")

    def title(s, x, y): S.text(s, x, y, 2.0)
    def note(s, x, y): S.text(s, x, y, 1.27)

    def conn(jj, x, y, side, txt_dx=None):
        """Wire-end connector at (x, y): body on the side given ('L' body left of the wire end, 'R' right)."""
        a = 90 if side == "L" else 270
        put(jj, x, y, a, ref_at=(txt_dx[0], y - 4.5), val_at=(txt_dx[0], y - 2.5)) if False else None

    S.text(S.title, ctx.X0, 21, 3.0)
    U1, U2 = "U101", "U102"
    OX, OY = 139.7, 99.06

    # ================================================================ gauge
    title("BQ40Z50 gauge: cell inputs, supply, current sense, SMBus", 20.32, 31)
    put(U1, OX, OY, ref_at=(OX - 12.7, OY - 31.0), val_at=(OX - 12.7, OY - 29.0))
    XL, XR = OX - 12.7, OX + 12.7
    PY = lambda num: pin(U1, num, OX, OY)[1]
    bend = lambda k: snap(XL - 2.54 * k)

    # upper-left pins climb to rows above the IC (nearest bend = highest row, so nothing crosses)
    rows_up = {"32": (1, OY - 57.15), "26": (2, OY - 48.26), "1": (3, OY - 39.37), "24": (4, OY - 30.48)}
    for num, (k, ry) in rows_up.items():
        W(XL, PY(num), bend(k), PY(num)); W(bend(k), PY(num), bend(k), ry)
    ry = OY - 57.15                                   # BAT <- R105 <- D101 <- CELL_4P (BAT feed from the cell top)
    x = hchain(ry, bend(1), [("R105", "Net-(D101-K)"), ("D101", "CELL_4P")])
    stub("CELL_4P", x, ry, "L")
    ry = OY - 48.26                                   # VCC <- R106 <- FET_MID
    x = hchain(ry, bend(2), [("R106", "FET_MID")])
    stub("FET_MID", x, ry, "L")
    ry = OY - 39.37                                    # PBI <- C105 <- CELL_1N
    x = hchain(ry, bend(3), [("C105", "CELL_1N")])
    stub("CELL_1N", x, ry, "L")
    ry = OY - 30.48                                   # PTCEN tied to CELL_1N
    W(bend(4), ry, bend(4) - 5.08, ry); lab("CELL_1N", bend(4) - 5.08, ry, 180)
    note("D101 feeds BAT from the cell top ahead of fuse F102 (TI fig. 9-12)", XL + 4, OY - 50)

    # cell-tap filters: the four taps fan out to lanes 7.62 apart so the capacitors between taps fit
    lanes = {"2": (5, OY - 17.78, "R104", "J116"), "3": (6, OY - 10.16, "R103", "J111"),
             "4": (10, OY - 2.54, "R102", "J110"), "5": (9, OY + 5.08, "R101", "J109")}
    xL = snap(bend(10) - 22.86)                        # ladder column
    lane_y = {}
    for num, (k, ly, rr, jj) in lanes.items():
        py = PY(num); lane_y[num] = ly
        W(XL, py, bend(k), py); W(bend(k), py, bend(k), ly); W(bend(k), ly, xL, ly)
        xl, xr_ = hpart(rr, snap(xL - 5.08 - 3.81), ly, ends(rr)[0])
        W(xL, ly, xr_, ly)
        jx = snap(xl - 10.16)
        W(xl, ly, jx, ly)
        gl(ends(rr)[0], xl - 1.27, ly, 180)
        tw = (len(jj) + 1 + len(comps[jj]["value"])) * 1.1 + 5
        put(jj, jx, ly, 90, ref_at=(jx - tw, ly - 2.5), val_at=(jx - tw + (len(jj) + 1) * 1.1, ly - 2.5))
    for cr, a, b in [("C101", "2", "3"), ("C102", "3", "4"), ("C103", "4", "5")]:
        small(cr, xL, snap((lane_y[a] + lane_y[b]) / 2), net(U1, a))
        J(xL, lane_y[a]); J(xL, lane_y[b])
    t, bt = small("C104", xL, snap(lane_y["5"] + 3.81), net(U1, "5"))
    W(xL, bt, xL, bt + 2.54); gl("CELL_1N", xL, bt + 2.54, 0)
    note("RC filter per cell tap (TI fig. 9-2): 100 R in series, 0.1 uF between taps", 24, OY - 27)

    # lower-left pins: sense, pack, thermistors (lowest pin = nearest bend = lowest row)
    ry_ = {"8": (8, OY + 25.4), "6": (7, OY + 33.02), "27": (6, OY + 40.64), "10": (5, OY + 48.26), "11": (4, OY + 55.88),
           "12": (3, OY + 63.5), "13": (2, OY + 71.12), "23": (1, OY + 78.74)}
    for num, (k, ry) in ry_.items():
        W(XL, PY(num), bend(k), PY(num)); W(bend(k), PY(num), bend(k), ry)
    # current sense: RS101 between the SRP and SRN rows, 100 R in each leg and 0.1 uF across at the IC end
    ysp, ysn = ry_["8"][1], ry_["6"][1]
    xrs = snap(xL - 17.78)
    for rr, y, nn in (("R107", ysp, "8"), ("R108", ysn, "6")):
        xl, xr_ = hpart(rr, snap(xL - 5.08), y, ends(rr)[0], txt="above" if rr == "R107" else "below")
        W(xL, y, xr_, y); W(bend(ry_[nn][0]), y, xL, y)
        W(xl, y, xrs, y)
    small("C106", xL, snap((ysp + ysn) / 2), net(U1, "8")); J(xL, ysp); J(xL, ysn)
    t, b = small("RS101", xrs, snap((ysp + ysn) / 2), "CELL_N")
    W(xrs, b, xrs, b + 2.54); S.gnd(xrs, b + 2.54, 0)
    J(xrs, ysp); J(xrs, ysn)
    jx = snap(xrs - 7.62)
    W(xrs, ysp, jx, ysp)
    put("J108", jx, ysp, 90, ref_at=(jx - 28, ysp - 2.5), val_at=(jx - 28 + 5.5, ysp - 2.5))
    note("1 mohm shunt, Kelvin sense", xrs - 40, ysn + 6)
    # PACK <- R113 <- PACK_P
    y = ry_["27"][1]
    x = hchain(y, bend(6), [("R113", "PACK_P")])
    stub("PACK_P", x, y, "L")
    # thermistors on the board: TS1, TS4
    for num, rr in (("10", "TH101"), ("13", "TH104")):
        k, y = ry_[num]
        x = hchain(y, bend(k), [(rr, "CELL_1N")])
        stub("CELL_1N", x, y, "L")
    # off-board thermistor wires on TS2 and TS3: wire pair with a gap where the NTC is soldered
    for num, ja, jb in (("11", "J117", "J118"), ("12", "J119", "J120")):
        k, y = ry_[num]
        xa = snap(bend(k) - 26.0)
        W(bend(k), y, xa, y)
        put(ja, snap(xa - 5.08), y, 180, ref_at=(xa + 1.27, y - 1.8), val_at=(xa + 1.27 + 5.5, y - 1.8))
        xb_ = snap(xa - 40.64)
        put(jb, snap(xb_ + 5.08), y, 0, ref_at=(xb_ + 1.27, y - 2.5), val_at=(xb_ + 1.27 + 5.5, y - 2.5))
        W(xb_, y, xb_ - 3.81, y); lab("CELL_1N", xb_ - 3.81, y, 180)
        note("off-board NTC", snap(xa - 24), y + 3.5)
    # PTC tied to CELL_1N
    k, y = ry_["23"]
    xj = snap(bend(k) - 20.32)
    W(bend(k), y, xj, y); gl("CELL_1N", xj + 12.7, y, 180)
    put("J115", xj, y, 90, ref_at=(xj - 26, y - 2.5), val_at=(xj - 26 + 5.5, y - 2.5))

    # right side: gate drive and fuse stubs, SMBus, interrupt
    for num in ("31", "28", "25"):
        y = PY(num); n = net(U1, num)
        stub(n, XR, y, "R", 5.08)
    for num in ("30", "20", "21", "22", "7", "14", "29"):
        S.nc(XR, PY(num))
    for num in ("16", "17", "9"):
        stub("CELL_1N", XR, PY(num), "R", 5.08)
    for num, rr, dx in (("19", "R115", 25.4), ("18", "R116", 50.8)):
        y = PY(num)
        xc = snap(XR + dx) + 3.81
        xl, xr_ = horiz(rr, xc, y, net(U1, num), ref_at=(xc - 3.81, y - 5.0), val_at=(xc - 3.81, y - 3.0))
        W(XR, y, xl, y)
        stub(ends(rr)[1], xr_, y, "R")
    yb = PY("15"); n = net(U1, "15")
    xq3 = snap(XR + 88.9)
    W(XR, yb, xq3 - 5.08, yb)
    put("Q103", xq3, yb, 0, ref_at=(xq3 + 5.08, yb - 1.27), val_at=(xq3 + 5.08, yb + 1.27))
    stub("IRQ_N", xq3 + 2.54, yb - 5.08, "U")
    W(xq3 + 2.54, yb + 5.08, xq3 + 2.54, yb + 7.62); S.gnd(xq3 + 2.54, yb + 7.62, 0)
    xr117 = snap(XR + 30.48)
    J(xr117, yb)
    vhang("R117", xr117, yb, n)
    note("BTP_INT drives the shared open-drain IRQ_N through Q103 (inverting)", xq3 - 24, yb + 16)
    note("CHG / DSG: gate drive to the protection FETs (power path, below)", XR + 4, PY("31") - 6)

    # ================================================================ second-level protector + ignition
    OX2, OY2 = 312.4, 73.66
    title("BQ294700 second-level protector, fuse ignition", 258, 31)
    put(U2, OX2, OY2, ref_at=(OX2 - 8.89, OY2 - 17), val_at=(OX2 - 8.89, OY2 - 15))
    XL2, XR2 = OX2 - 8.89, OX2 + 8.89
    xl2 = snap(XL2 - 19.05)
    lane2 = {}
    for num, rr in (("2", "R119"), ("3", "R120"), ("4", "R121"), ("5", "R122")):
        y = pin(U2, num, OX2, OY2)[1]; lane2[num] = y
        W(XL2, y, xl2, y)
        xl, xr_ = hpart(rr, snap(xl2 - 5.08), y, ends(rr)[0])
        W(xl2, y, xr_, y)
        stub(ends(rr)[0], xl, y, "L")
    for cr, a, b in [("C112", "2", "3"), ("C113", "3", "4"), ("C114", "4", "5")]:
        small(cr, xl2, snap((lane2[a] + lane2[b]) / 2), net(U2, a))
        J(xl2, lane2[a]); J(xl2, lane2[b])
    t, bt = small("C115", xl2, snap(lane2["5"] + 3.81), net(U2, "5"))
    W(xl2, bt, xl2, bt + 2.54); gl("CELL_1N", xl2, bt + 2.54, 0)
    # VDD: 100 R from the cell top, 0.1 uF to VSS
    yv = pin(U2, "1", OX2, OY2)[1]
    xv = snap(XR2 + 5.08)
    W(XR2, yv, xv + 22.86, yv); J(xv, yv)
    vup("C116", xv, yv, net(U2, "1"))
    xl, xr_ = hright("R123", snap(xv + 22.86), yv, net(U2, "1"))
    W(xv + 22.86, yv, xl, yv)
    stub("CELL_4P", xr_, yv, "R")
    stub("CELL_1N", XR2, pin(U2, "6", OX2, OY2)[1], "R", 5.08)         # VSS (pins 6 and 9)
    yc = pin(U2, "7", OX2, OY2)[1]                                      # CD: 0.1 uF to VSS sets the delay
    W(XR2, yc, snap(XR2 + 5.08), yc)
    xl, xr_ = hright("C117", snap(XR2 + 5.08), yc, net(U2, "7"))
    stub("CELL_1N", xr_, yc, "R")
    yo = pin(U2, "8", OX2, OY2)[1]                                      # OUT -> R124 -> ignition FET gate
    W(XR2, yo, snap(XR2 + 5.08), yo)
    xl, xr_ = hright("R124", snap(XR2 + 5.08), yo, net(U2, "8"), txt="below")
    xg = snap(xr_ + 5.08)
    nq = ends("R126")[0]                                                 # Net-(Q104-G)
    xq4 = snap(xg + 30.48 + 12.7)
    W(xr_, yo, xq4 - 5.08, yo)
    J(xg, yo)
    vhang("R126", xg, yo, nq)                                            # gauge FUSE pin through 5.1k
    xr125 = snap(xg + 15.24); J(xr125, yo)
    vhang("R125", xr125, yo, nq)                                         # 51k to ground
    xc118 = snap(xg + 30.48); J(xc118, yo)
    vhang("C118", xc118, yo, nq)
    put("Q104", xq4, yo, 0, ref_at=(xq4 + 5.08, yo - 1.27), val_at=(xq4 + 5.08, yo + 1.27))
    stub("Net-(F102-HTR)", xq4 + 2.54, yo - 5.08, "U", 3.81)
    W(xq4 + 2.54, yo + 5.08, xq4 + 2.54, yo + 7.62); S.gnd(xq4 + 2.54, yo + 7.62, 0)
    note("OUT (about 7 V) after the CD delay fires the fuse heater", xl2 - 20, OY2 + 31)

    # ================================================================ power path
    P0 = 192.0
    title("Pack power path: fuse, back-to-back protection FETs, load", 20.32, P0)
    yd = snap(P0 + 22)
    ycp = snap(yd + 7.62); ycp_ = ycp
    xf = snap(70)
    put("F102", xf, yd, ref_at=(xf - 6.35, yd - 8), val_at=(xf - 6.35, yd - 6))
    jx = snap(xf - 6.35 - 20.32)
    W(jx, yd, xf - 6.35, yd)
    put("J112", jx, yd, 90, ref_at=(jx - 22, yd - 2.5), val_at=(jx - 22 + 5.5, yd - 2.5))
    gl("CELL_P_RAW", jx + 2.54, yd, 0)
    xdrop = snap(xf + 6.35 + 5.08)
    W(xf + 6.35, yd, xdrop, yd); W(xdrop, yd, xdrop, ycp)
    htr = pin("F102", "3", xf, yd)
    stub("Net-(F102-HTR)", htr[0], htr[1], "D", 3.81)
    # gate row of the charge FET: CHG -> R109 -> gate, R110 gate-to-source
    xlab = snap(xdrop + 12.7)
    xl, xr_ = hright("R109", snap(xlab + 2.54), yd, "CHG")
    W(xlab, yd, xl, yd); lab("CHG", xlab, yd, 180)
    xg1 = snap(xr_ + 5.08)
    xq1 = snap(xg1 + 24.13)
    W(xr_, yd, xq1 - 6.35, yd); J(xg1, yd)
    yq = snap(yd + 1.27)
    put("Q101", xq1, yq, 0, ref_at=(xq1 - 6.35, yq - 8.5), val_at=(xq1 - 6.35, yq - 6.5))
    vhang("R110", xg1, yd, "CHG_G", end="none"); J(xg1, ycp_)                         # to the CELL_P wire
    xq2 = snap(xq1 + 25.4)
    put("Q102", xq2, yq, 0, mirror=True, ref_at=(xq2 + 6.35, yq - 8.5), val_at=(xq2 + 6.35, yq - 6.5))
    W(xq1 + 6.35, yd, xq2 - 6.35, yd)
    gl("FET_MID", xq1 + 8.89, yd, 0)
    # CELL_P under Q101, PACK_P under Q102
    s1 = pin("Q101", "1", xq1, yq); s2 = pin("Q102", "1", xq2, yq, True)
    W(xdrop, ycp, s1[0], ycp); W(s1[0], ycp, s1[0], s1[1]); 
    gl("CELL_P", xdrop + 1.27, ycp, 0)
    xp_end = snap(xq2 + 6.35 + 5.08 + 17.78 + 12.7 + 15.24 + 20 + 44)
    W(s2[0], s2[1], s2[0], ycp); W(s2[0], ycp, xp_end, ycp)
    # Q102 gate row: DSG -> R111 -> gate, R112 and D103 gate-to-PACK_P
    xg2 = snap(xq2 + 6.35 + 5.08)
    W(xq2 + 6.35, yd, xg2, yd); J(xg2, yd)
    vhang("R112", xg2, yd, "DSG_G", end="none")
    xd3 = snap(xg2 + 17.78); J(xd3, yd)
    vhang("D103", xd3, yd, "DSG_G", end="none")
    xl, xr_ = hright("R111", snap(xd3 + 12.7), yd, "DSG_G")
    W(xg2, yd, xl, yd)
    stub("DSG", xr_, yd, "R")
    J(xg2, ycp); J(xd3, ycp)
    gl("PACK_P", xd3 + 20, ycp, 0)
    # wake line off CELL_P, ESD caps across the FETs
    xw = snap(xdrop + 7.62); J(xw, ycp)
    b = vhang("R118", xw, ycp, "CELL_P", end="none")
    W(xw, b, xw, b + 2.54)
    put("TP113", xw, b + 2.54, 180, ref_at=(xw + 2.54, b + 3.0), val_at=(xw + 2.54, b + 5.0))
    xa = snap(xq1 - 6.35); yc2 = snap(ycp + 12.7)
    J(xa, ycp); W(xa, ycp, xa, yc2)
    xl, xr_ = hright("C110", snap(xa + 5.08), yc2, "CELL_P")
    W(xa, yc2, xl, yc2)
    xl2_, xr2_ = hright("C111", snap(xr_ + 5.08), yc2, ends("C111")[0], txt="above")
    W(xr_, yc2, xl2_, yc2)
    xb2 = snap(xq2 + 6.35 + 3.81); J(xb2, ycp)
    W(xr2_, yc2, xb2, yc2); W(xb2, yc2, xb2, ycp)
    note("ESD caps across the FETs, two in series (TI fig. 9-2)", xa + 5.08, yc2 + 5)
    note("CHG FET", xq1 - 6.35, yq + 12.5 + 14) if False else None
    # load end: PACK_P, mid-point caps, test points
    xm = snap(xq2 + 6.35 + 5.08 + 17.78 + 12.7 + 15.24 + 20)
    J(xm, ycp)
    b = vhang("C107", xm, ycp, "PACK_P", end="none")
    t, b2 = small("C108", xm, snap(b + 3.81), "PACK_CMID")
    gl("PACK_CMID", xm - 1.27, b, 180)
    W(xm, b2, xm, b2 + 2.54); S.gnd(xm, b2 + 2.54, 0)
    xt = snap(xm + 26.67); J(xt, ycp)
    put("TP106", xt, ycp, 0, ref_at=(xt + 2.54, ycp - 4.5), val_at=(xt + 2.54, ycp - 2.5))
    J(xp_end, ycp)
    put("J113", xp_end, ycp, 0, ref_at=(xp_end + 2.54, ycp - 4.5), val_at=(xp_end + 2.54, ycp - 2.5))
    yg = snap(ycp + 22)
    W(xt, yg, xp_end, yg)
    put("TP109", xt, yg, 0, ref_at=(xt + 2.54, yg - 4.5), val_at=(xt + 2.54, yg - 2.5))
    put("J114", xp_end, yg, 0, ref_at=(xp_end + 2.54, yg - 4.5), val_at=(xp_end + 2.54, yg - 2.5))
    W(xt, yg, xt, yg + 2.54); S.gnd(xt, yg + 2.54, 0)
    return True
