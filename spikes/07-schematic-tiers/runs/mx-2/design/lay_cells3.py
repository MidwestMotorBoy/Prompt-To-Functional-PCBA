"""Cells and Gauge sheet, sections 3 and 4: the cell thermistors, and the second-level protector with the fuse driver."""
from sch import Port, snap
import patterns as P


def thermistors(S, x, y):
    sec = S.begin("Cell temperature inputs", x, y,
                  note="TS1 and TS4: NTCs on the board.\nTS2 and TS3: NTCs on wires")
    ox, oy = sec.ox, sec.oy
    xl = snap(ox + 10)
    yy = snap(oy + 4)
    for k, (ts, th, jt, jr) in enumerate((("TS1", "TH101", None, None), ("TS2", None, "J117", "J118"),
                                          ("TS3", None, "J119", "J120"), ("TS4", "TH104", None, None))):
        y0 = yy + k * 20.32
        xe = xl + 12.7
        S.wire([(xl, y0), (xe, y0)], ts); S.label(ts, Port(xl, y0), "L")
        if th:                                  # NTC on the board: from the TS line to the Kelvin ground
            t = P.hang(S, th, xe, y0, ts, to=None)
            S.gnd(t.bt, "D", "CELL_1N")
        else:                                   # NTC on wires: one pad for the NTC, one for its return
            S.place(jt, xe + 5.08, y0)
            yr = y0 + 8.89
            S.place(jr, xe + 5.08, yr)
            S.wire([(xe, yr), (xe - 7.62, yr)], "CELL_1N")
            S.gnd(Port(xe - 7.62, yr), "D", "CELL_1N")
    S.end(sec)
    return sec


def protector(S, x, y):
    sec = S.begin("Second-level protector and fuse driver", x, y,
                  note="BQ294700 trips at 4.35 V per cell after the delay set by C117. Its OUT or the gauge's FUSE pin turns on Q104, which heats the fuse")
    ox, oy = sec.ox, sec.oy
    ux, uy = snap(ox + 58), snap(oy + 30)
    u = S.place("U102", ux, uy)
    pl, rp = ux - 8.89, ux + 8.89
    # ---- cell inputs: 1k from each cell tap, 0.1u between adjacent inputs; the pins are already 7.62 mm apart
    xcap = snap(pl - 15.24)
    xr = snap(xcap - 12.7)
    ys, nets = [], []
    for pn, rref, cell in (("V4", "R119", "CELL_4P"), ("V3", "R120", "CELL3"), ("V2", "R121", "CELL2"), ("V1", "R122", "CELL1")):
        pt = u.p(pn)
        r = S.two(rref, xr, pt.y, "h", first=cell)
        S.wire([pt, r.r], pt.net)
        S.wire([r.l, r.l.to(-2.54, 0)], cell); S.label(cell, r.l.to(-2.54, 0), "L")
        ys.append(pt.y); nets.append(pt.net)
    for i, cref in enumerate(("C112", "C113", "C114")):
        S.two(cref, xcap, (ys[i] + ys[i + 1]) / 2, "v", first=nets[i])
    c115 = P.hang(S, "C115", xcap, ys[3], nets[3], to=None)
    S.gnd(c115.bt, "D", "CELL_1N")
    # ---- supply: VDD through 100R from CELL_4P, 0.1u between VDD and VSS
    vdd, vss, cd, out = u.p("VDD"), u.p("VSS"), u.p("CD"), u.p("OUT")
    xc = snap(rp + 7.62)
    r123 = S.two("R123", snap(rp + 20.32), vdd.y, "h", first="U102_VDD")
    S.wire([vdd, r123.l], "U102_VDD")
    S.wire([r123.r, r123.r.to(2.54, 0)], "CELL_4P"); S.label("CELL_4P", r123.r.to(2.54, 0), "R")
    S.two("C116", xc, (vdd.y + vss.y) / 2, "v", first="U102_VDD")
    S.wire([vss, (xc + 7.62, vss.y)], "CELL_1N")
    S.gnd(Port(xc + 7.62, vss.y), "D", "CELL_1N")
    # ---- delay capacitor
    S.wire([cd, (xc, cd.y)], "CD")
    c117 = P.hang(S, "C117", xc, cd.y, "CD", to=None)
    S.gnd(c117.bt, "D", "CELL_1N")
    # ---- OUT down to the gate row of Q104: 5.1k in line, 51k and 0.1u to ground, 5.1k from the gauge's FUSE pin
    yo = snap(out.y + 7.62)
    xo = snap(rp + 2.54)
    S.wire([out, (xo, out.y), (xo, yo)], "OV_OUT")
    r124 = S.two("R124", snap(rp + 12.7), yo, "h", first="OV_OUT")
    S.wire([(xo, yo), r124.l], "OV_OUT")
    xq = snap(rp + 60.96)
    q4 = S.place("Q104", xq, yo)
    S.wire([r124.r, q4.p("G")], "FUSE_G")
    r125 = P.hang(S, "R125", snap(rp + 24.13), yo, "FUSE_G", to=None); S.gnd(r125.bt)
    c118 = P.hang(S, "C118", snap(rp + 34.29), yo, "FUSE_G", to=None); S.gnd(c118.bt, "D", "CELL_1N")
    r126 = S.two("R126", snap(rp + 44.45), yo - 3.81, "v", first="GAUGE_FUSE")
    S.pin_label(r126.t, "R", 2.54)
    S.pin_label(q4.p("D"), "R", 2.54)
    S.gnd(q4.p("S"))
    S.end(sec)
    return sec
