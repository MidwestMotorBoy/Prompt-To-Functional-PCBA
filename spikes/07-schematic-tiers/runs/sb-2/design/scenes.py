"""Hand layouts, one function per sheet. Each places parts at explicit coordinates with page.Page and wires pin to pin.
Nothing here decides connectivity: make.sh proves the result equals the code's netlist."""
import math
from page import snap, G

X0 = 20.32


def span(pg, r, extra=0.0):
    """Width a vertical part with its two text lines to the right needs, in mm, on the 2.54 grid."""
    n = max(len(pg.c[r]["value"]), len(r) + 1)
    return math.ceil((n * 1.2 + 6.4 + extra) / 2.54) * 2.54


def head(pg, block, title, x, y):
    pg.text(title, x, y, 2.0)
    note = pg.cons.get("notes", {}).get(block + "|" + title)
    if note:
        for i, line in enumerate(note.split("\n")):
            pg.text(line, x, y + 5.08 + 4.0 * i, 1.27)


def hang(pg, x, y, refs, net, step=1, other="GND", gap=None, tail=True):
    """Parts hang from a horizontal bus at height y, one every span(), from x outward (step=+1 right, -1 left).
    Returns (list of x positions, x after the last)."""
    xs = []
    for r in refs:
        w = gap or span(pg, r)
        if step < 0: x = snap(x - w)
        A, B = pg.p2(r, x, y, "v", first=net)
        o = pg.far
        if not tail: pass
        elif o == "GND": pg.gnd(B[0], B[1], "D")
        else: pg.stub(B[0], B[1], "D", o, ld="R")
        xs.append(x)
        if step > 0: x = snap(x + w)
    return xs, x


def bus(pg, y, xs, ends=()):
    """Wire along y across xs (and extra end points) with junctions at the inner taps."""
    pts = sorted(list(xs) + list(ends))
    pg.w((pts[0], y), (pts[-1], y))
    for x in xs:
        if x not in (pts[0], pts[-1]) or x in ends: pg.j(x, y)
    return pts[0], pts[-1]


def gnd_bar(pg, ref, keys, d=3.81, net=None):
    """Several ground pins on one edge of a part: wire each out, join them, one ground symbol."""
    ps = [(pg.P(ref, k), pg.side(ref, k)) for k in keys]
    side = ps[0][1]
    for k in keys: pg.use(ref, k)
    if len(ps) == 1: return pg.tag(ref, keys[0])
    if side in "UD":
        sg = 1 if side == "D" else -1
        yb = ps[0][0][1] + sg * d
        xs = sorted(p[0][0] for p in ps)
        for p in ps: pg.w(p[0], (p[0][0], yb))
        pg.w((xs[0], yb), (xs[-1], yb))
        xm = xs[len(xs) // 2] if len(xs) % 2 else snap((xs[0] + xs[-1]) / 2)
        for x in xs[1:-1]: pg.j(x, yb)
        if net is False: pass
        elif net: pg.j(xm, yb); pg.stub(xm, yb, "D" if sg > 0 else "U", net, 2.54, ld="R")
        else: pg.j(xm, yb); pg.gnd(xm, yb, "D" if sg > 0 else "U")
    else:
        sg = 1 if side == "R" else -1
        xb = ps[0][0][0] + sg * d
        ys = sorted(p[0][1] for p in ps)
        for p in ps: pg.w(p[0], (xb, p[0][1]))
        pg.w((xb, ys[0]), (xb, ys[-1]))
        for y in ys[1:-1]: pg.j(xb, y)
        if net is False: return
        ym = snap((ys[0] + ys[-1]) / 2)
        if ym not in ys: pg.j(xb, ym)
        else: pg.j(xb, ym) if len(ys) > 2 else None
        pg.stub(xb, ym, "R" if sg > 0 else "L", net or "GND", 2.54)


def rail_3v3(pg, block):
    sh = pg.S
    sh.paper = (297, 150)
    head(pg, block, "TPS62177 3.3 V always-on buck", X0, 33)
    yv = snap(70)
    ic = "U204"
    vin = (snap(150), yv)                      # VIN pin tip
    pg.ic(ic, vin[0] + 10.16, yv + 7.62)
    pg.w(("U204", "VIN"), (vin[0] - 5.08, yv))
    # EN tied to VIN: it is always on
    en = pg.P(ic, "EN"); pg.use(ic, "EN"); pg.use(ic, "VIN")
    pg.w(en, (vin[0] - 5.08, en[1]), (vin[0] - 5.08, yv)); pg.j(vin[0] - 5.08, yv)
    # input capacitors: the 2.2 u at the pin, the bulk further out
    cin = ["C206"] + [f"C{208 + i}" for i in range(6)]
    xs, xe = hang(pg, vin[0] - 12.7, yv, cin, "PACK_P", -1)
    xl = snap(xe - 5.08)
    bus(pg, yv, xs, ends=(vin[0] - 5.08, xl))
    pg.lab("PACK_P", xl, yv, "L")
    # sleep input
    pg.tag(ic, "~{SLEEP}", 5.08)
    pg.tag(ic, "PG")
    gnd_bar(pg, ic, ["NC", "PAD", "PGND", "AGND"])
    # inductor and output
    sw = pg.P(ic, "SW"); pg.use(ic, "SW")
    xl_ = snap(sw[0] + 17.78)
    A, B = pg.p2("L201", xl_, sw[1], "h", first="SW_3V3")
    pg.w(sw, A)
    pg.lab("SW_3V3", snap(sw[0] + 2.54), sw[1], "R")
    xo = snap(B[0] + 7.62)
    pg.w(B, (xo + 10.16, B[1]))
    xs2, _ = hang(pg, xo, B[1], ["C207"], "3V3", 1)
    pg.j(xo, B[1])
    vos = pg.P(ic, "VOS"); pg.use(ic, "VOS")
    pg.w(vos, (xo, vos[1]), (xo, B[1]))
    pg.tag(ic, "FB")
    pg.lab("3V3", xo + 10.16, B[1], "R")
    pg.text("Fixed 3.3 V version: VOS senses the output, FB is grounded.", X0, 120, 1.27)




def pull(pg, ref, x, row_y, net, up, other="3V3"):
    """A pull-up resistor tapped onto the wire on row_y at x: up (supply label above) or down (label below)."""
    if up:
        A, B = pg.p2(ref, x, snap(row_y - 7.62), "v", first=other)
        pg.stub(A[0], A[1], "U", other, ld="R")
    else:
        A, B = pg.p2(ref, x, row_y, "v", first=net)
        pg.stub(B[0], B[1], "D", other, ld="R")
    pg.j(x, row_y)


def mcu(pg, block):
    sh = pg.S
    sh.paper = (297, 175)
    ox, oy = snap(150), snap(88)
    pg.ic("U301", ox, oy)
    xp, xr = pg.P("U301", "RSTN")[0], pg.P("U301", "DIO6_A1")[0]
    head(pg, block, "CC2340R5MODA module", X0, 33)
    # supply: pin up to a 3V3 bus, decoupling hangs from it
    yb = snap(oy - 15.24 - 12.7)
    vd = pg.P("U301", "VDDS"); pg.use("U301", "VDDS")
    pg.w(vd, (xp - 5.08, vd[1]), (xp - 5.08, yb))
    # RSTN: pull-up from the bus, reset capacitor to ground
    yr = pg.P("U301", "RSTN")[1]; pg.use("U301", "RSTN")
    xs, xe = hang(pg, xp - 12.7, yb, ["R302"], "3V3", -1, gap=12.7, tail=False)
    xr302 = xs[0]
    xs2, xe2 = hang(pg, xr302 - 12.7, yb, ["C302", "C303", "C301"], "3V3", -1)
    # fix the reset net: R302 bottom is at yb+7.62
    pg.w((xr302, yb + 7.62), (xr302, yr), (xp, yr))
    xc = xr302 - 12.7
    xs3, _ = hang(pg, xc, yr, ["C304"], "NRST", 1, gap=12.7)
    pg.j(xs3[0], yr); pg.j(xr302, yr)
    pg.w((xc, yr), (xr302, yr)); pg.lab("NRST", snap(xp - 7.62), yr, "R")
    pg.lab("NRST", xr302 - 7.62, yr, "L") if False else None
    xl = snap(xe2 - 22.86)
    bus(pg, yb, [xp - 5.08] + xs + xs2, ends=(xl,))
    pg.lab("3V3", xl, yb, "L")
    # test point on the bus
    pg.p1("TP301", snap(xe2 - 7.62), yb)
    pg.j(snap(xe2 - 7.62), yb)
    pg.use("TP301", "1")
    # pins with only a label
    for k in ("ANT_IN", "RFIO", "DIO16/SWDIO", "DIO17/SWDCK"): pg.tag("U301", k)
    gnd_bar(pg, "U301", ["GND"] if False else ["1"], 3.81) if False else pg.tag("U301", "GND")
    # right side
    xl_ = snap(xr + 43.18)
    for k in ("DIO6_A1", "DIO8", "DIO21_A10", "DIO11"): pg.use("U301", k)
    p = pg.P("U301", "DIO6_A1"); pg.w(p, (xl_, p[1])); pull(pg, "R304", snap(xr + 7.62), p[1], "SCL", True); pg.lab("SCL", xl_, p[1], "R")
    p = pg.P("U301", "DIO8"); pg.w(p, (xl_, p[1])); pull(pg, "R305", snap(xr + 15.24), p[1], "SDA", False); pg.lab("SDA", xl_, p[1], "R")
    p = pg.P("U301", "DIO21_A10"); pg.w(p, (xl_, p[1])); pull(pg, "R313", snap(xr + 25.4), p[1], "3V3_SLEEP", True); pg.lab("3V3_SLEEP", xl_, p[1], "R")
    p = pg.P("U301", "DIO11"); pg.w(p, (xl_, p[1])); pull(pg, "R314", snap(xr + 7.62), p[1], "IRQ_N", False); pg.lab("IRQ_N", xl_, p[1], "R")
    for k in ("DIO18", "DIO20_A11", "DIO12", "DIO24_A7", "DIO3_X32P", "DIO4_X32N"): pg.tag("U301", k)
    # antenna match
    ya = snap(oy + 40)
    head(pg, block, "Antenna match", X0, snap(ya - 12.7))
    x = snap(X0 + 20)
    pg.lab("RFIO", x, ya, "L")
    A, B = pg.p2("C313", x, ya, "h", first="RFIO")
    pg.w((x, ya), A)
    A2, B2 = pg.p2("R321", snap(B[0] + 12.7), ya, "h", first="Net-(C313-Pad2)")
    pg.w(B, A2); xm = snap(B[0] + 6.35); pg.j(xm, ya)
    xm = snap(B[0] + 5.08); xm = snap(B[0] + 6.35)
    pg.w(B2, (snap(B2[0] + 7.62), ya)); pg.j(snap(B2[0] + 5.08), ya) if False else None
    xe_ = snap(B2[0] + 5.08)
    pg.lab("ANT_IN", snap(B2[0] + 7.62), ya, "R")
    # shunt caps
    xm = snap(B[0] + 6.35)
    pg.j(xm, ya); a, b = pg.p2("C314", xm, ya, "v", first="Net-(C313-Pad2)"); pg.gnd(b[0], b[1], "D")
    pg.j(xe_, ya); a, b = pg.p2("C315", xe_, ya, "v", first="ANT_IN"); pg.gnd(b[0], b[1], "D")
    # connectors
    xj = snap(xl_ + 40)
    head(pg, block, "Debug and gauge-training connectors", snap(xj - 22), 33)
    pg.ic("J301", xj, snap(oy - 22))
    for k in ("VCC", "GND", "~{RESET}", "SWCLK", "SWDIO", "SWO"): pg.tag("J301", k)
    pg.ic("J302", xj, snap(oy + 28))
    for k in ("SDA", "CHG_INH", "NRST", "NC", "GND", "SCL"): pg.tag("J302", k)




def stair(pg, ref, keys, lanes, side="L"):
    """Fan pins out to lanes: pin, short run, vertical to the lane. The pin nearest the outside turns first so nothing crosses."""
    out = []
    for i, (k, ly) in enumerate(zip(keys, lanes)):
        x, y = pg.P(ref, k); pg.use(ref, k)
        cx = snap(x + (-1 if side == "L" else 1) * 2.54 * (i + 1))
        pg.w((x, y), (cx, y), (cx, ly))
        out.append((cx, ly))
    return out


def hpart(pg, ref, xr, y, first, tpos="above"):
    """Horizontal part whose right tip is at xr. Returns (left tip, right tip)."""
    return pg.p2(ref, xr - 7.62, y, "h", first=first, tpos=tpos)


def cells(pg, block):
    sh = pg.S
    sh.paper = (345, 320)
    L = 7.62
    # ---------------------------------------------------------------- pack power path
    head(pg, block, "Pack power path", X0, 33)
    yp = snap(62)
    pg.p1("J112", 40, yp, tl=True)
    xf = snap(75)
    pg.ic("F102", xf, yp)
    pg.w(("J112", "1"), ("F102", "1"))
    xq1, xq2 = snap(125), snap(155)
    pg.ic("Q101", xq1, yp + 2.54, ref_at=(xq1 - 3.81, yp - 9.8), val_at=(xq1 - 3.81, yp - 7.8))
    pg.ic("Q102", xq2, yp + 2.54, mirror=True, ref_at=(xq2 - 3.81, yp - 9.8), val_at=(xq2 - 3.81, yp - 7.8))
    pg.w(("F102", "2"), ("Q101", "S"))
    pg.w(("Q101", "D"), ("Q102", "D"))
    xm = snap((pg.P("Q101", "D")[0] + pg.P("Q102", "D")[0]) / 2)
    pg.j(xm, yp); pg.stub(xm, yp, "U", "FET_MID", 2.54, ld="R")
    xpe = snap(pg.P("Q102", "S")[0] + 95)
    pg.w(("Q102", "S"), (xpe, yp)); pg.lab("PACK_P", xpe, yp, "R")
    yg = yp + L
    # charge FET gate network
    pg.use("Q101", "G"); pg.use("Q102", "G")
    g1 = pg.P("Q101", "G"); g2 = pg.P("Q102", "G")
    x110 = snap(xq1 - 17.78)
    pg.p2("R110", x110, yp, "v", first="CELL_P"); pg.j(x110, yp)
    pg.w((x110, yg), g1)
    x109 = snap(xq1 - 7.62)
    pg.p2("R109", x109, yg, "v", first="CHG_G"); pg.stub(x109, yg + L, "D", "CHG", ld="R"); pg.j(x109, yg)
    # discharge FET gate network
    x111 = snap(xq2 - 11.43)
    pg.p2("R111", x111, yg, "v", first="DSG_G"); pg.stub(x111, yg + L, "D", "DSG", ld="R")
    x112, xd = snap(xq2 + 12.7), snap(xq2 + 31.75)
    pg.w((x111, yg), g2, (xd, yg)); pg.j(x111, yg)
    pg.p2("R112", x112, yp, "v", first="PACK_P"); pg.j(x112, yp); pg.j(x112, yg)
    pg.p2("D103", xd, yp, "v", first="PACK_P"); pg.j(xd, yp)
    # ESD capacitors across both FETs, two in series so one shorted cap cannot bypass them
    ye = snap(yp - 12.7)
    xe1, xe2 = snap(xf + 24.13), snap(xq2 + 7.62)
    pg.w((xe1, yp), (xe1, ye)); pg.j(xe1, yp)
    A, B = pg.p2("C110", xe1, ye, "h", first="CELL_P")
    A2, B2 = pg.p2("C111", snap(B[0] + 5.08), ye, "h", first="ESD_MID")
    pg.w(B, A2); pg.w(B2, (xe2 + 2 * 0, ye), (xe2, yp)); pg.j(xe2, yp)
    pg.text("ESD across the FET pair", xe1, ye - 7.5, 1.0)
    # WAKE pull-up
    xw = snap(xf + 10.16)
    pg.p2("R118", xw, yp, "v", first="CELL_P"); pg.j(xw, yp)
    pg.w((xw, yp + L), (xw, yp + L + 3.81))
    pg.p1("TP113", xw, yp + L + 3.81, flip=True)
    # load side pads
    pg.p1("J113", xd + 15.24, yp); pg.j(xd + 15.24, yp)
    pg.p1("TP106", xd + 40.64, yp); pg.j(xd + 40.64, yp)
    pg.stub(xf, yp + 5.08, "D", "F102_HTR", 2.54, ld="R"); pg.use("F102", "HTR")
    # PACK_P to ground pair
    xc7 = snap(xd + 60.96)
    pg.p2("C107", xc7, yp, "v", first="PACK_P"); pg.j(xc7, yp)
    pg.p2("C108", xc7, yp + L, "v", first="PACK_CMID"); pg.gnd(xc7, yp + 2 * L, "D")
    pg.text("PACK_P to ground through two caps", xc7 - 8, yp + 2 * L + 8, 1.0)
    # ---------------------------------------------------------------- gauge
    head(pg, block, "BQ40Z50 gauge", X0, 101)
    xi, yi = snap(200.66), snap(152.4)
    pg.ic("U101", xi, yi)
    xp = pg.P("U101", "BAT")[0]; xr = pg.P("U101", "CHG")[0]
    lanes = [yi - 39.37, yi - 31.75, yi - 24.13]
    st = stair(pg, "U101", ["BAT", "VCC", "PBI"], [snap(v) for v in lanes])
    (cx, ly) = st[0]
    pg.w((cx, ly), (cx - 5.08, ly))
    A, B = hpart(pg, "R105", cx - 5.08, ly, "BAT_D")
    D1, D2 = pg.p2("D101", snap(A[0] - 5.08 - 7.62), ly, "h", first="CELL_4P")
    pg.w(D2, A); pg.stub(D1[0], ly, "L", "CELL_4P")
    (cx, ly) = st[1]
    pg.w((cx, ly), (cx - 5.08, ly))
    A, B = hpart(pg, "R106", cx - 5.08, ly, "FET_MID"); pg.stub(A[0], ly, "L", "FET_MID")
    (cx, ly) = st[2]
    xc5 = snap(xp - 25.4)
    pg.w((cx, ly), (xc5, ly))
    pg.p2("C105", xc5, ly, "v", first="PBI_C"); pg.stub(xc5, ly + L, "D", "CELL_1N", ld="R")
    # PACK sense: 10k from PACK_P
    pk = pg.P("U101", "PACK"); pg.use("U101", "PACK")
    A, B = hpart(pg, "R113", pk[0] - 12.7, pk[1], "PACK_P")
    pg.w(pk, B); pg.stub(A[0], pk[1], "L", "PACK_P")
    # SMBus series resistors
    for key, ref, net, dx, tp in (("SMBC", "R115", "SCL", 22.86, "above"), ("SMBD", "R116", "SDA", 30.48, "below")):
        p = pg.P("U101", key); pg.use("U101", key)
        A, B = pg.p2(ref, xr + dx, p[1], "h", first=pg.net("U101", key), tpos=tp)
        pg.w(p, A); pg.stub(B[0], p[1], "R", net)
    for k in ("CHG", "DSG", "FUSE", "BTP_INT"): pg.tag("U101", k)
    for k in ("PTCEN", "VC4", "VC3", "VC2", "VC1", "SRP", "SRN", "TS1", "TS2", "TS3", "TS4", "PTC"): pg.tag("U101", k)
    # ---- cell sense filters: 100R in series, 0.1u ladder between the pins' nets
    pg.text("Cell sense filters: 100R and 0.1u per cell", X0, 124, 1.27)
    yl = snap(131)
    xpad, xrl, xcl = 44, 58, snap(86)
    nets = ["CELL_4P", "CELL3", "CELL2", "CELL1"]; vn = ["VC4", "VC3", "VC2", "VC1"]
    rr = ["R104", "R103", "R102", "R101"]; pads = ["J116", "J111", "J110", "J109"]
    cc = ["C101", "C102", "C103", "C104"]
    xout = snap(xcl + 15.24)
    for k in range(4):
        y = snap(yl + k * L)
        pg.p1(pads[k], xpad, y, tl=True)
        A, B = pg.p2(rr[k], xrl, y, "h", first=nets[k])
        pg.w((xpad, y), A); pg.w(B, (xout, y)); pg.lab(nets[k], xpad + 1.27, y, "R")
        pg.j(xcl, y); pg.lab(vn[k], xout, y, "R")
        pg.p2(cc[k], xcl, y, "v", first=vn[k])
    pg.w((xcl, snap(yl + 3 * L + L)), (xcl, snap(yl + 3 * L + L + 3.81)))
    pg.p1("J115", xcl, snap(yl + 4 * L + 3.81), flip=True)
    pg.lab("CELL_1N", xcl, snap(yl + 4 * L + 1.27), "R")
    # ---- current sense, Kelvin
    ys = snap(178)
    pg.text("Current sense: 1 mOhm shunt, Kelvin taps through 100R", X0, ys - 2.54, 1.27)
    yP = snap(ys + 12.7); yN = yP + L
    xrs = 60
    A, B = pg.p2("RS101", xrs, yP, "v", first="CELL_N")
    pg.p1("J108", xrs, yP - 5.08, tl=True); pg.w((xrs, yP - 5.08), (xrs, yP)); pg.j(xrs, yP)
    xr7 = snap(xrs + 10.16); xc2 = snap(xr7 + 25.4)
    A, B = hpart(pg, "R107", xr7 + 7.62, yP, "CELL_N", "above"); pg.w((xrs, yP), A); pg.w(B, (xc2 + 15.24, yP))
    A, B = hpart(pg, "R108", xr7 + 7.62, yN, "GND", "below"); pg.w((xrs, yN), A); pg.w(B, (xc2 + 15.24, yN)); pg.j(xrs, yN)
    pg.j(xc2, yP); pg.j(xc2, yN); pg.p2("C106", xc2, yP, "v", first="SRP")
    pg.lab("SRP", xc2 + 15.24, yP, "R"); pg.lab("SRN", xc2 + 15.24, yN, "R")
    yb = snap(yN + 7.62)
    pg.w((xrs, yN), (xrs, yb)); pg.w((xrs - 15.24, yb), (xrs + 15.24, yb)); pg.gnd(xrs, yb, "D"); pg.j(xrs, yb)
    pg.p1("J114", xrs - 15.24, yb, flip=True); pg.p1("TP109", xrs + 15.24, yb, flip=True)
    # ---- thermistors
    yt = snap(232)
    pg.text("Cell temperature sensing: NTCs to the gauge, Kelvin return on CELL_1N", X0, yt - 8, 1.27)
    for i, (th, net) in enumerate((("TH101", "TS1"), ("TH104", "TS4"))):
        y = snap(yt + i * 12.7)
        pg.lab(net, 55, y, "L"); A, B = pg.p2(th, 58, y, "h", first=net, tpos="above")
        pg.w((55, y), A); pg.stub(B[0], y, "R", "CELL_1N")
    for i, (a, b, net) in enumerate((("J117", "J118", "TS2"), ("J119", "J120", "TS3"))):
        y = snap(yt + 2 * 12.7 + 2.54 + i * 17.78)
        pg.p1(a, 70, y); pg.lab(net, 55, y, "L"); pg.w((55, y), (70, y))
        pg.p1(b, 70, y + 7.62); pg.lab("CELL_1N", 55, y + 7.62, "L"); pg.w((55, y + 7.62), (70, y + 7.62))
    # ---- gauge interrupt
    xq3, yq3 = snap(292), snap(146)
    head(pg, block, "Gauge interrupt onto the shared IRQ line", snap(xq3 - 40), snap(101))
    pg.ic("Q103", xq3, yq3)
    g = pg.P("Q103", "G"); pg.use("Q103", "G")
    pg.lab("BTP_INT", g[0] - 10.16, g[1], "L"); pg.w((g[0] - 10.16, g[1]), g)
    pg.p2("R117", g[0] - 5.08, g[1], "v", first="BTP_INT"); pg.j(g[0] - 5.08, g[1]); pg.stub(g[0] - 5.08, g[1] + L, "D", "CELL_1N", ld="R")
    pg.stub(*pg.P("Q103", "D"), "U", "IRQ_N", 5.08, ld="R"); pg.use("Q103", "D"); pg.tag("Q103", "S")
    # ---------------------------------------------------------------- protector
    yu = snap(250)
    head(pg, block, "Second-level protector and fuse", snap(X0 + 130), snap(yu - 30))
    xu = snap(200)
    pg.ic("U102", xu, yu)
    xpl = pg.P("U102", "V4")[0]; xrr = pg.P("U102", "VDD")[0]
    xcc = snap(xpl - 7.62)
    rn = [("R119", "CELL_4P", "PV4", "V4"), ("R120", "CELL3", "PV3", "V3"), ("R121", "CELL2", "PV2", "V2"), ("R122", "CELL1", "PV1", "V1")]
    for k, (r, cn, vn_, pin) in enumerate(rn):
        p = pg.P("U102", pin); pg.use("U102", pin)
        A, B = hpart(pg, r, xcc - 7.62, p[1], cn); pg.stub(A[0], p[1], "L", cn)
        pg.w(B, p); pg.j(xcc, p[1])
    pcs = ["C112", "C113", "C114"]
    ys_ = [pg.P("U102", p)[1] for p in ("V4", "V3", "V2", "V1")]
    for k, c in enumerate(pcs): pg.p2(c, xcc, ys_[k], "v", first=rn[k][2])
    pg.w((xcc, ys_[3]), (xcc, ys_[3] + 3.81)); pg.p2("C115", xcc, ys_[3], "v", first="PV1"); pg.stub(xcc, ys_[3] + L, "D", "CELL_1N", ld="R")
    # right side
    vd = pg.P("U102", "VDD"); pg.use("U102", "VDD")
    xn = snap(xrr + 7.62)
    pg.w(vd, (xn, vd[1])); pg.j(xn, vd[1])
    pg.p2("C116", xn, vd[1] - L, "v", first="CELL_1N"); pg.stub(xn, vd[1] - L, "U", "CELL_1N", ld="R")
    A, B = pg.p2("R123", xn + 5.08, vd[1], "h", first="PVDD", tpos="below"); pg.w((xn, vd[1]), A); pg.stub(B[0], vd[1], "R", "CELL_4P")
    pg.tag("U102", "VSS")
    cd = pg.P("U102", "CD"); pg.use("U102", "CD")
    A, B = pg.p2("C117", xrr + 15.24, cd[1], "h", first="CD", tpos="above"); pg.w(cd, A); pg.stub(B[0], cd[1], "R", "CELL_1N")
    ot = pg.P("U102", "OUT"); pg.use("U102", "OUT")
    A, B = hpart(pg, "R124", xrr + 5.08 + 7.62, ot[1], "OVP_OUT"); pg.w(ot, A)
    x1 = snap(B[0] + 7.62); x2 = snap(x1 + 17.78); x3 = snap(x2 + 15.24); xq4 = snap(x3 + 15.24)
    pg.ic("Q104", xq4, ot[1])
    pg.w(B, ("Q104", "G")); pg.use("Q104", "G")
    pg.p2("R126", x1, ot[1], "v", first="FUSE_G"); pg.stub(x1, ot[1] + L, "D", "GAUGE_FUSE", ld="R"); pg.j(x1, ot[1])
    pg.p2("R125", x2, ot[1], "v", first="FUSE_G"); pg.gnd(x2, ot[1] + L, "D"); pg.j(x2, ot[1])
    pg.p2("C118", x3, ot[1], "v", first="FUSE_G"); pg.stub(x3, ot[1] + L, "D", "CELL_1N", ld="R"); pg.j(x3, ot[1])
    pg.stub(*pg.P("Q104", "D"), "U", "F102_HTR", 5.08, ld="R"); pg.use("Q104", "D")
    pg.tag("Q104", "S")
    pg.text("Fuse heater F102 fired by the protector (OUT) or by the gauge (FUSE)", xq4 - 60, yu + 24, 1.0)





def usb_pd(pg, block, title):
    n = port_n(block); pn = int(block[-1])
    R = lambda p, k: f"{p}{n + k}"
    U, E = R("U", 1), R("U", 2)
    ldo = f"P{pn}_LDO_3V3"
    xu, yu = snap(70), snap(44)
    pg.ic(U, xu, yu)
    P = lambda k: pg.P(U, k)
    # supply from the 3V3 rail
    v = P("VIN_3V3"); pg.use(U, "VIN_3V3")
    yv = snap(v[1] - 10.16)
    pg.w(v, (v[0] - 5.08, v[1]), (v[0] - 5.08, yv), (v[0] - 33.02, yv))
    pg.p2(R("C", 3), v[0] - 15.24, yv, "v", first="3V3"); pg.gnd(v[0] - 15.24, yv + 7.62, "D"); pg.j(v[0] - 15.24, yv)
    pg.lab("3V3", v[0] - 33.02, yv, "L")
    gnd_bar(pg, U, ["VBUS_IN", "VBUS"], 3.81, net="VBUS")
    pg.tag(U, "CC1"); pg.tag(U, "CC2")
    gnd_bar(pg, U, ["GPIO0", "GPIO1", "GPIO2"]); gnd_bar(pg, U, ["GPIO4", "GPIO5"]); gnd_bar(pg, U, ["GPIO7", "GPIO11"])
    # SBU_FLT and DRV9_OFF: the fault pull-up sits on the line
    g3 = P("GPIO3"); pg.use(U, "GPIO3")
    x41 = snap(g3[0] - 12.7)
    pg.w(g3, (x41, g3[1])); pg.p2(R("R", 41), x41, snap(g3[1] - 7.62), "v", first=ldo, tleft=True)
    pg.stub(x41, snap(g3[1] - 7.62), "U", ldo, 2.54, ld="L"); pg.j(x41, g3[1])
    pg.stub(x41, g3[1], "L", "SBU_FLT")
    pg.tag(U, "GPIO6")
    # right side: PPHV with its capacitors, PP5V, drains
    pp = P("PPHV"); pg.use(U, "PPHV")
    pg.tag(U, "PPHV")
    p5 = P("PP5V"); pg.use(U, "PP5V")
    x5 = snap(p5[0] + 7.62)
    pg.w(p5, (x5 + 5.08, p5[1])); pg.p2(R("C", 7), x5, p5[1], "v", first="PP5V"); pg.gnd(x5, p5[1] + 7.62, "D"); pg.j(x5, p5[1])
    pg.lab("PP5V", x5 + 5.08, p5[1], "R")
    gnd_bar(pg, U, ["15", "40"], 3.81, net=False)
    l1 = P("LDO_1V5"); pg.use(U, "LDO_1V5")
    x1 = snap(l1[0] + 40.64)
    pg.w(l1, (x1 + 5.08, l1[1])); pg.p2(R("C", 5), x1, l1[1], "v", first="LDO_1V5"); pg.gnd(x1, l1[1] + 7.62, "D"); pg.j(x1, l1[1])
    pg.lab("LDO_1V5", x1 + 5.08, l1[1], "R")
    l3 = P("LDO_3V3"); pg.use(U, "LDO_3V3")
    x3 = snap(l3[0] + 10.16)
    pg.w(l3, (x3 + 10.16, l3[1])); pg.p2(R("C", 4), x3, l3[1], "v", first=ldo); pg.gnd(x3, l3[1] + 7.62, "D"); pg.j(x3, l3[1])
    pg.lab(ldo, x3 + 10.16, l3[1], "R")
    if pg.net(U, "ADCIN1") == pg.net(U, "LDO_3V3"):
        a1 = P("ADCIN1"); pg.use(U, "ADCIN1")
        pg.w(a1, (a1[0] + 3.81, a1[1]), (a1[0] + 3.81, l3[1])); pg.w((l3[0], l3[1]), (l3[0] + 3.81, l3[1]))
    else: pg.tag(U, "ADCIN1")
    pg.tag(U, "ADCIN2")
    gnd_bar(pg, U, ["11", "12", "14", "31", "39"] if False else ["11"], 3.81)
    # I2Cc bus: the interrupt and bus pins carry labels; their pull-ups hang from one 3V3 bus beside them
    for pin in ("I2Cc_SCL", "I2Cc_SDA", "~{I2Cc_IRQ}"): pg.tag(U, pin, 2.54)
    xb0, yb0 = snap(xu + 62), snap(yu + 6)
    pg.lab(ldo, xb0, yb0, "L")
    xs_ = []
    for k, (pin, rr) in enumerate((("I2Cc_SCL", R("R", 3)), ("I2Cc_SDA", R("R", 2)), ("~{I2Cc_IRQ}", R("R", 4)))):
        x = snap(xb0 + 8.89 + 15.24 * k)
        net = pg.net(U, pin)
        pg.p2(rr, x, yb0, "v", first=ldo); pg.stub(x, yb0 + 7.62, "D", net, 2.54, ld="R"); xs_.append(x)
    bus(pg, yb0, xs_, ends=(xb0,))
    pg.text("I2Cc bus pull-ups", xb0 - 2, yb0 - 5, 1.0)
    for k in ("I2Ct_SCL", "I2Ct_SDA", "~{I2Ct_IRQ}"): pg.tag(U, k)
    # EEPROM with its own supply capacitor
    xe, ye = snap(xu + 85), snap(yu + 38)
    pg.ic(E, xe, ye)
    vt = pg.P(E, "VCC"); pg.use(E, "VCC")
    pg.w(vt, (vt[0], vt[1] - 5.08), (vt[0] + 30.48, vt[1] - 5.08))
    pg.p2(R("C", 8), snap(vt[0] + 25.4), snap(vt[1] - 5.08), "v", first=ldo); pg.gnd(snap(vt[0] + 25.4), snap(vt[1] - 5.08 + 7.62), "D")
    pg.j(snap(vt[0] + 25.4), snap(vt[1] - 5.08))
    pg.lab(ldo, snap(vt[0] + 30.48), snap(vt[1] - 5.08), "R")
    gnd_bar(pg, E, ["A0", "A1", "A2"]); gnd_bar(pg, E, ["WP"] if False else ["7"])
    for k in ("SDA", "SCL"): pg.tag(E, k)
    pg.tag(E, "GND")




def sense_filter(pg, x0, y1, ra, rb, cx, ca, cb, na_in, nb_in, na_f, nb_f):
    """Kelvin current-sense filter: a series resistor in each line, one capacitor across, one from each line to ground."""
    y2 = snap(y1 + 12.7)
    xc = snap(x0 + 33.02)
    for y, r, nin, nf in ((y1, ra, na_in, na_f), (y2, rb, nb_in, nb_f)):
        pg.lab(nin, x0, y, "L")
        A, B = pg.p2(r, x0 + 5.08, y, "h", first=nin)
        pg.w((x0, y), A)
        pg.w(B, (xc, y))
    pg.j(xc, y1); pg.j(xc, y2)
    pg.w((xc, y1), (xc, snap(y1 + 2.54))); pg.w((xc, snap(y2 - 2.54)), (xc, y2))
    pg.p2(cx, xc, snap(y1 + 2.54), "v", first=na_f, tleft=True)
    xb = snap(x0 + 20.32)
    pg.j(xb, y2); pg.p2(cb, xb, y2, "v", first=nb_f, tleft=True); pg.gnd(xb, y2 + 7.62, "D")
    xa = snap(xc + 20.32)
    pg.w((xc, y1), (xa + 10.16, y1)); pg.j(xa, y1)
    pg.p2(ca, xa, y1, "v", first=na_f); pg.gnd(xa, y1 + 7.62, "D")
    pg.lab(na_f, xa + 10.16, y1, "R")
    pg.w((xc, y2), (xc + 5.08, y2)); pg.lab(nb_f, xc + 5.08, y2, "R")


def usb_charger(pg, block, title):
    n = port_n(block)
    R = lambda p, k: f"{p}{n + k}"
    U = R("U", 3)
    xu, yu = snap(185), snap(30)
    pg.ic(U, xu, yu)
    P = lambda k: pg.P(U, k)
    y0 = P("VAC")[1]
    xp = P("VAC")[0]; xr = P("HIDRV1")[0]
    # --- VAC bus with its capacitors, and the input-window divider standing on it
    xch = snap(xp - 27.94)
    xl = snap(xp - 96)
    pg.w((U, "VAC"), (xl, y0)); pg.lab("PPHV", xl, y0, "L")
    for r, x in ((R("C", 9), xp - 64.77), (R("C", 49), xp - 80.01)):
        x = snap(x); pg.p2(r, x, y0, "v", first="PPHV"); pg.gnd(x, y0 + 7.62, "D"); pg.j(x, y0)
    pg.p2(R("R", 9), xch, y0, "v", first="PPHV", tleft=True); pg.j(xch, y0)
    pg.p2(R("R", 10), xch, y0 + 7.62, "v", first="ACUV", tleft=True)
    pg.p2(R("R", 11), xch, y0 + 15.24, "v", first="ACOV", tleft=True); pg.gnd(xch, y0 + 22.86, "D")
    pg.w((U, "ACUV"), (xch, y0 + 7.62)); pg.j(xch, y0 + 7.62)
    ao = P("ACOV"); pg.use(U, "ACOV")
    xs = snap(xch + 5.08)
    pg.w(ao, (xs, ao[1]), (xs, y0 + 15.24), (xch, y0 + 15.24)); pg.j(xch, y0 + 15.24)
    for k in ("ACP", "ACN", "SCL", "SDA", "~{INT}", "~{STAT1}", "~{STAT2}", "~{PG}"): pg.tag(U, k)
    # --- CE: pull-up to 3V3, and the MCU inhibit through 1k
    ce = P("~{CE}"); pg.use(U, "~{CE}")
    xn = snap(ce[0] - 22.86)
    pg.w(ce, (xn, ce[1]))
    pg.p2(R("R", 17), xn, snap(ce[1] - 7.62), "v", first="3V3"); pg.stub(xn, snap(ce[1] - 7.62), "U", "3V3", 2.54, ld="R"); pg.j(xn, ce[1])
    A, B = pg.p2(R("R", 35), xn - 12.7, ce[1], "h", first="CHG_INH"); pg.w(B, (xn, ce[1])); pg.stub(A[0], ce[1], "L", "CHG_INH")
    # --- FSW, ICHG, ILIM, TS down a staircase of lanes
    yf = P("FSW_SYNC")[1]
    lanes = [snap(yf + 5.08 + 10.16 * k) for k in range(4)]
    st = stair(pg, U, ["TS", "ILIM_HIZ", "ICHG", "FSW_SYNC"], lanes[::-1])
    xrt = snap(xp - 22.86)
    for (cx, ly), r in zip(st[::-1], (R("R", 12), R("R", 13), R("R", 14))):
        A, B = pg.p2(r, xrt - 7.62, ly, "h", first="GND")
        pg.w((cx, ly), B); pg.stub(A[0], ly, "L", "GND")
    cx, ly = st[0]                                   # TS lane
    xa, xb_ = snap(xp - 15.24), snap(xp - 30.48)
    pg.w((cx, ly), (xb_, ly))
    pg.p2(R("R", 16), xa, ly, "v", first="TS"); pg.gnd(xa, ly + 7.62, "D"); pg.j(xa, ly)
    pg.p2("TH" + str(n + 1), xb_, ly, "v", first="TS"); pg.gnd(xb_, ly + 7.62, "D"); pg.j(xb_, ly)
    A, B = pg.p2(R("R", 15), xb_ - 5.08 - 7.62, ly, "h", first="REGN"); pg.w((xb_, ly), B); pg.stub(A[0], ly, "L", "REGN")
    # --- gate drive: 0R in series with each driver output
    for pin, r, net in (("HIDRV1", R("R", 44), "HG1"), ("LODRV1", R("R", 45), "LG1"), ("HIDRV2", R("R", 46), "HG2"), ("LODRV2", R("R", 47), "LG2")):
        p = P(pin); pg.use(U, pin)
        dx = 30.48 if pin == "HIDRV2" else 15.24
        A, B = pg.p2(r, p[0] + dx, p[1], "h", first=pg.net(U, pin))
        pg.w(p, A); pg.stub(B[0], p[1], "R", net)
    for k in ("BTST1", "SW1", "BTST2", "SW2", "SRP", "SRN"): pg.tag(U, k)
    # --- battery feedback divider
    fb, fg = P("FB"), P("FBG"); pg.use(U, "FB"); pg.use(U, "FBG")
    xc = snap(xr + 53.34); xs2 = snap(xr + 46.99)
    pg.w(fb, (xc, fb[1])); pg.j(xc, fb[1])
    pg.p2(R("R", 18), xc, fb[1] - 7.62, "v", first="PACK_P"); pg.stub(xc, fb[1] - 7.62, "U", "PACK_P", 2.54, ld="R")
    pg.p2(R("R", 19), xc, fb[1], "v", first="FB")
    pg.w(fg, (xs2, fg[1]), (xs2, fb[1] + 7.62), (xc, fb[1] + 7.62))
    # --- REGN and DRV_SUP
    rg, ds = P("REGN"), P("DRV_SUP"); pg.use(U, "REGN"); pg.use(U, "DRV_SUP")
    xg = snap(xr + 30.48); xd_ = snap(xr + 15.24)
    pg.w(rg, (xg + 5.08, rg[1])); pg.lab("REGN", snap(rg[0] + 2.54), rg[1], "R")
    pg.p2(R("C", 10), xg, rg[1], "v", first="REGN"); pg.gnd(xg, rg[1] + 7.62, "D"); pg.j(xg, rg[1])
    pg.w(ds, (xd_ + 5.08, ds[1])); pg.lab("DRV_SUP", snap(ds[0] + 2.54), ds[1], "R")
    pg.p2(R("C", 11), xd_, ds[1], "v", first="DRV_SUP"); pg.gnd(xd_, ds[1] + 7.62, "D"); pg.j(xd_, ds[1])
    pg.tag_all(U, "NC"); pg.tag(U, "PGND")
    # --- bootstrap: DRV_SUP, diode, BTST, capacitor, SW
    xb0 = snap(xr + 84)
    for k, (d, c, bt, sw, y) in enumerate(((R("D", 4), R("C", 12), "BTST1", "SW1", y0 + 5.08), (R("D", 5), R("C", 13), "BTST2", "SW2", y0 + 20.32))):
        y = snap(y)
        pg.lab("DRV_SUP", xb0, y, "L")
        A, B = pg.p2(d, xb0 + 5.08, y, "h", first="DRV_SUP"); pg.w((xb0, y), A)
        A2, B2 = pg.p2(c, snap(B[0] + 15.24), y, "h", first=bt)
        pg.w(B, A2); pg.lab(bt, snap(B[0] + 2.54), y, "R")
        pg.w(B2, (B2[0] + 5.08, y)); pg.lab(sw, B2[0] + 5.08, y, "R")
    # --- Kelvin current-sense filters, input side then pack side
    ysf = snap(y0 + 88)
    sense_filter(pg, snap(xp - 110), ysf, R("R", 25), R("R", 26), R("C", 14), R("C", 15), R("C", 16), "PPHV", "AC_SNS_N", "ACP_F", "ACN_F")
    sense_filter(pg, snap(xr + 20), ysf, R("R", 28), R("R", 29), R("C", 17), R("C", 18), R("C", 19), "BAT_SNS_P", "PACK_P", "SRP_F", "SRN_F")
    pg.text("Input sense (RAC)", snap(xp - 110), ysf - 8, 1.0); pg.text("Pack side sense (RBAT)", snap(xr + 20), ysf - 8, 1.0)



def usb_9v(pg, block, title):
    n = port_n(block); pn = int(block[-1])
    R = lambda p, k: f"{p}{n + k}"
    U = R("U", 6); ldo = f"P{pn}_LDO_3V3"
    xu, yu = snap(72), snap(26)
    pg.ic(U, xu, yu)
    P = lambda k: pg.P(U, k)
    # input: pack rail with its 1u at the pin
    i = P("IN"); pg.use(U, "IN")
    xci = snap(i[0] - 45.72)
    pg.w(i, (snap(xci - 10.16), i[1])); pg.lab("PACK_P", snap(xci - 10.16), i[1], "L")
    pg.p2(R("C", 57), xci, i[1], "v", first="PACK_P"); pg.gnd(xci, i[1] + 7.62, "D"); pg.j(xci, i[1])
    # enable: pulled up to REGN, pulled down by Q409 when the PD controller asks for 9 V off
    e = P("EN"); pg.use(U, "EN")
    xe = snap(e[0] - 7.62)
    pg.w(e, (xe, e[1]))
    A, B = pg.p2(R("R", 54), xe - 15.24, e[1], "h", first="REGN"); pg.w(B, (xe, e[1])); pg.stub(A[0], e[1], "L", "REGN")
    pg.j(xe, e[1])
    q = R("Q", 9)
    pg.ic(q, xe - 2.54, snap(e[1] + 22.86))
    pg.w((xe, e[1]), (q, "D")); pg.use(q, "D")
    pg.tag(q, "S")
    g = pg.P(q, "G"); pg.use(q, "G")
    xg = snap(g[0] - 12.7)
    pg.w(g, (xg - 7.62, g[1])); pg.stub(xg - 7.62, g[1], "L", "DRV9_OFF")
    pg.p2(R("R", 55), xg, snap(g[1] - 7.62), "v", first=ldo); pg.stub(xg, snap(g[1] - 7.62), "U", ldo, 2.54, ld="R"); pg.j(xg, g[1])
    pg.tag(U, "GND"); pg.tag_all(U, "NC")
    # output: divider, capacitor, then the diode that ORs it onto DRV_SUP
    o = P("OUT"); pg.use(U, "OUT"); fb = P("FB"); pg.use(U, "FB")
    xc = snap(o[0] + 10.16)
    pg.w(o, (xc, o[1])); pg.j(xc, o[1])
    pg.p2(R("R", 52), xc, o[1], "v", first="V9_DRV"); pg.p2(R("R", 53), xc, o[1] + 7.62, "v", first="V9_FB"); pg.gnd(xc, o[1] + 15.24, "D")
    pg.w(fb, (xc, fb[1])); pg.j(xc, fb[1])
    x1 = snap(xc + 22.86)
    pg.w((xc, o[1]), (snap(x1 + 12.7), o[1])); pg.j(x1, o[1])
    pg.p2(R("C", 58), x1, o[1], "v", first="V9_DRV"); pg.gnd(x1, o[1] + 7.62, "D")
    A, B = pg.p2(R("D", 11), snap(x1 + 12.7), o[1], "h", first="V9_DRV")
    pg.w((x1, o[1]), A)
    xn = snap(B[0] + 7.62)
    pg.w(B, (xn, o[1])); pg.lab("DRV_SUP", xn + 2.54, o[1], "R") if False else None
    y2 = snap(o[1] + 15.24)
    A2, B2 = pg.p2(R("D", 10), snap(B[0] - 7.62 - 2.54), y2, "h", first="REGN")
    pg.lab("REGN", snap(A2[0] - 5.08), y2, "L"); pg.w((snap(A2[0] - 5.08), y2), A2)
    pg.w(B2, (xn, y2), (xn, o[1])); pg.j(xn, o[1])
    pg.w((xn, o[1]), (xn + 5.08, o[1])); pg.lab("DRV_SUP", xn + 5.08, o[1], "R")


def usb_5v(pg, block, title):
    n = port_n(block)
    R = lambda p, k: f"{p}{n + k}"
    U = R("U", 4)
    xu, yu = snap(75), snap(28)
    pg.ic(U, xu, yu)
    P = lambda k: pg.P(U, k)
    vi = P("VIN"); pg.use(U, "VIN")
    xs = [snap(vi[0] - 50.8), snap(vi[0] - 66.04)]
    xl = snap(xs[-1] - 12.7)
    pg.w(vi, (xl, vi[1])); pg.lab("PACK_P", xl, vi[1], "L")
    for r, x in ((R("C", 46), xs[0]), (R("C", 44), xs[1])):
        pg.p2(r, x, vi[1], "v", first="PACK_P"); pg.gnd(x, vi[1] + 7.62, "D"); pg.j(x, vi[1])
    en = P("EN"); pg.use(U, "EN")
    xe = snap(en[0] - 20.32)
    pg.w(en, (xe - 5.08, en[1])); pg.lab(pg.net(U, "EN"), xe - 5.08, en[1], "L")
    pg.p2(R("R", 32), xe, en[1], "v", first=pg.net(U, "EN")); pg.gnd(xe, en[1] + 7.62, "D"); pg.j(xe, en[1])
    ss = P("SS"); pg.use(U, "SS"); xss = snap(ss[0] - 5.08)
    pg.w(ss, (xss, ss[1])); pg.p2(R("C", 39), snap(ss[0] - 5.08) if False else xss, ss[1], "v", first="SS_5V", tleft=True); pg.gnd(xss, ss[1] + 7.62, "D")
    pg.tag(U, "RT")
    gb = P("GND"); pg.use(U, "GND")
    pg.w(gb, (gb[0], gb[1] + 2.54)); pg.j(gb[0], gb[1] + 2.54)
    pg.w((gb[0], gb[1] + 2.54), (gb[0] + 12.7, gb[1] + 2.54)); pg.gnd(gb[0], gb[1] + 2.54, "D")
    pg.p1(R("TP", 12), gb[0] + 12.7, gb[1] + 2.54, flip=True)
    # boot capacitor between BST and SW
    bs, sw, fb = P("BST"), P("SW"), P("FB")
    for k in ("BST", "SW", "FB"): pg.use(U, k)
    xb = snap(bs[0] + 10.16)
    pg.w(bs, (xb, bs[1])); pg.p2(R("C", 40), xb, bs[1], "v", first="BST_5V", tdx=2.54)
    pg.w(sw, (xb, sw[1])); pg.j(xb, sw[1])
    pg.lab("SW_5V", snap(sw[0] + 2.54), sw[1], "R")
    A, B = pg.p2(R("L", 2), snap(xb + 17.78), sw[1], "h", first="SW_5V")
    pg.w((xb, sw[1]), A)
    xo = snap(B[0] + 7.62)
    pg.w(B, (xo, sw[1])); pg.j(xo, sw[1])
    pg.p2(R("R", 33), xo, sw[1], "v", first="PP5V"); pg.p2(R("R", 34), xo, sw[1] + 7.62, "v", first="FB_5V"); pg.gnd(xo, sw[1] + 15.24, "D")
    pg.w(fb, (xo, fb[1])); pg.j(xo, fb[1])
    xs2 = [snap(xo + 22.86 + 15.24 * k) for k in range(3)]
    pg.w((xo, sw[1]), (snap(xs2[-1] + 15.24), sw[1]))
    for r, x in zip((R("C", 41), R("C", 42), R("C", 43)), xs2):
        pg.p2(r, x, sw[1], "v", first="PP5V"); pg.gnd(x, sw[1] + 7.62, "D"); pg.j(x, sw[1])
    pg.lab("PP5V", snap(xs2[-1] + 15.24), sw[1], "R")


PAGE_W = {"USB Port 1": 430.0, "USB Port 2": 430.0}
SECTIONS = {}


def port_n(block):
    return 300 + 100 * int(block[-1])


def usb_connector(pg, block, title):
    n = port_n(block)
    R = lambda p, k: f"{p}{n + k}"
    J, D, U5 = R("J", 1), R("D", 1), R("U", 5)
    yj = snap(66)
    pg.ic(J, 30, yj)
    yb = 22.86
    vb = pg.P(J, "VBUS"); pg.use(J, "VBUS")
    pg.w(vb, (vb[0] + 5.08, vb[1]), (vb[0] + 5.08, yb))
    xs = [snap(66), snap(80), snap(110)]
    pg.p2(R("C", 6), xs[0], yb, "v", first="VBUS"); pg.gnd(xs[0], yb + 7.62, "D")
    pg.p2(R("C", 50), xs[1], yb, "v", first="VBUS"); pg.gnd(xs[1], yb + 7.62, "D")
    pg.ic(D, xs[2], yb + 7.62, ref_at=(xs[2] + 3.81, yb + 5.5), val_at=(xs[2] + 3.81, yb + 7.7))
    pg.w((xs[2], yb), pg.P(D, "IN")); pg.use(D, "IN"); pg.gnd(*pg.P(D, "GND"), "D"); pg.use(D, "GND")
    xe = snap(xs[2] + 20)
    bus(pg, yb, [vb[0] + 5.08] + xs, ends=(xe,))
    pg.lab("VBUS", xe, yb, "R")
    pg.j(vb[0] + 5.08, yb) if False else None
    gnd_bar(pg, J, ["SH", "A1"])
    gnd_bar(pg, J, ["A7", "B7", "A6", "B6"], 3.81, net="DPDN_DCP")
    for k in ("SBU1", "SBU2"): pg.tag(J, k)
    # TPD6S300: CC lines straight across
    yu = snap(yj + 1.27)
    pg.ic(U5, 85, yu)
    pg.w((J, "CC1"), (U5, "C_CC1")); pg.w((J, "CC2"), (U5, "C_CC2"))
    xlab = snap(pg.P(J, "CC1")[0] + 5.08)
    pg.lab("C_CC1", xlab, pg.P(J, "CC1")[1], "R"); pg.lab("C_CC2", xlab, pg.P(J, "CC2")[1], "R")
    for k in ("RPD_G1", "RPD_G2", "C_SBU1", "C_SBU2", "D1", "D2", "SBU1", "SBU2", "9"): pg.tag(U5, k)
    gnd_bar(pg, U5, ["GND", "N.C."])
    # outputs with the 220 p CC capacitors
    p2_ = pg.P(U5, "CC2"); pg.use(U5, "CC2"); p1_ = pg.P(U5, "CC1"); pg.use(U5, "CC1")
    x2 = snap(p2_[0] + 7.62); x1 = snap(x2 + 17.78)
    pg.w(p2_, (x2, p2_[1])); pg.p2(R("C", 2), x2, p2_[1], "v", first="CC2"); pg.gnd(x2, p2_[1] + 7.62, "D"); pg.j(x2, p2_[1])
    pg.w((x2, p2_[1]), (x2 + 5.08, p2_[1])); pg.lab("CC2", x2 + 5.08, p2_[1], "R")
    pg.w(p1_, (x1, p1_[1])); pg.p2(R("C", 1), x1, p1_[1], "v", first="CC1"); pg.gnd(x1, p1_[1] + 7.62, "D"); pg.j(x1, p1_[1])
    pg.w((x1, p1_[1]), (x1 + 5.08, p1_[1])); pg.lab("CC1", x1 + 5.08, p1_[1], "R")
    # supply pins on top
    ty = snap(yu - 16.51)
    vp, vbs = pg.P(U5, "VPWR"), pg.P(U5, "VBIAS"); pg.use(U5, "VPWR"); pg.use(U5, "VBIAS")
    yv = snap(ty - 7.62)
    xc = snap(vp[0] - 12.7)
    pg.w(vp, (vp[0], yv), (xc - 5.08, yv)); pg.p2(R("C", 52), xc, yv, "v", first="P%d_LDO_3V3" % int(block[-1])); pg.gnd(xc, yv + 7.62, "D"); pg.j(xc, yv)
    pg.lab("P%d_LDO_3V3" % int(block[-1]), xc - 5.08, yv, "L")
    xc2 = snap(vbs[0] + 10.16)
    pg.w(vbs, (vbs[0], yv), (xc2, yv)); pg.p2(R("C", 51), xc2, yv, "v", first="VBIAS"); pg.gnd(xc2, yv + 7.62, "D")


SECTIONS_USB = {"USB-C connector and port protection": (usb_connector, []),
                "USB PD controller TPS25751D, EEPROM and I2C pull-ups": (usb_pd, []),
                "BQ25756 charger controller": (usb_charger, ["Charger programming"]),
                "9 V gate-drive supply": (usb_9v, []),
                "5 V buck for PP5V": (usb_5v, [])}
SECTIONS["USB Port 1"] = SECTIONS_USB
SECTIONS["USB Port 2"] = SECTIONS_USB

SCENES = {"3V3 Rail": rail_3v3, "MCU": mcu, "Cells and Gauge": cells}


ROOT_HEAD = [("Monolith: two-port USB-C PD charger with battery pack", 3.0),
             ("Power flows: USB port -> charger -> pack (Cells and Gauge) -> PACK_P rail -> 3V3 rail and 5 V / 9 V supplies.", 1.27)]
ROOT_NOTES = {
    "3V3 Rail": ["p2  TPS62177 always-on 3.3 V buck", "In: PACK_P   Out: 3V3"],
    "Cells and Gauge": ["p3  Pack power path, BQ40Z50 gauge,", "cell sense, BQ294700 protector + fuse"],
    "MCU": ["p4  CC2340 BLE module, pull-ups,", "antenna match, debug connectors"],
    "USB Port 1": ["p5  USB-C, PD controller, BQ25756 charger,", "four-switch stage, 9 V and 5 V supplies"],
    "USB Port 2": ["p6  Same as port 1 (parts 5xx)"],
}
