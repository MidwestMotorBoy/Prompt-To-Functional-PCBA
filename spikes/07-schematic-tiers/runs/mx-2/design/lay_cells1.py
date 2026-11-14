"""Cells and Gauge sheet, section 1: the pack power path with its fuse, protection FETs and sense resistor."""
from sch import Port, snap
import patterns as P


def kelvin(S, xr, y, rs, rp, rn, cdiff, net_l, net_r, fl, fr):
    """Sense resistor `rs` in line at (xr, y) with its Kelvin filter hanging below: rp from a tap on the left wire,
    rn from a tap on the right wire, cdiff across the two filtered nodes, which leave as labels. Returns the resistor."""
    r = S.two(rs, xr, y, "h", first=net_l)
    xa, xb = snap(r.l.x - 7.62), snap(r.r.x + 7.62)
    S.wire([r.l, (xa, y)], net_l); S.wire([r.r, (xb, y)], net_r)
    S.two(rp, xa, y + 3.81, "v", first=net_l, text="L")
    S.two(rn, xb, y + 3.81, "v", first=net_r, text="R")
    yn = y + 7.62
    S.two(cdiff, xr, yn, "h", first=fl)
    S.wire([(xa, yn), (xr - 3.81, yn)], fl); S.wire([(xr + 3.81, yn), (xb, yn)], fr)
    S.wire([(xa, yn), (xa - 2.54, yn)], fl); S.label(fl, Port(xa - 2.54, yn), "L")
    S.wire([(xb, yn), (xb + 2.54, yn)], fr); S.label(fr, Port(xb + 2.54, yn), "R")
    return r


def power_path(S, x, y):
    sec = S.begin("Pack power path: fuse, protection FETs and sense resistor", x, y,
                  note="Cells at the left, load at the right. The gauge drives CHG and DSG; the fuse heater is fired through FUSE_HTR")
    ox, oy = sec.ox, sec.oy
    yG = snap(oy + 14)                 # gate row, also the FETs' drain row
    yH = snap(yG + 7.62)               # PACK+ line
    xJ = snap(ox + 3)
    xf = snap(xJ + 27)
    xa = snap(xf + 43)                 # Q101 (charge FET)
    xb = snap(xa + 30.48)              # Q102 (discharge FET), mirrored, drains facing Q101's
    # ---- PACK+ : wire pad, fuse, then the back-to-back FETs with their drains joined
    j112 = S.place("J112", xJ, yH)
    f = S.place("F102", xf, yH)
    S.wire([j112.p("1"), f.p("1")], "CELL_P_RAW")
    q1 = S.place("Q101", xa, yG + 1.27)
    q2 = S.place("Q102", xb, yG + 1.27, mirror=True)
    g1, d1, s1 = q1.p("4"), q1.p("5"), q1.p("1")
    g2, d2, s2 = q2.p("4"), q2.p("5"), q2.p("1")
    S.wire([f.p("2"), (s1.x, yH), s1], "CELL_P")
    S.label("CELL_P", Port(f.p("2").x + 5.08, yH), "R")
    S.wire([d1, d2], "FET_MID")
    S.label("FET_MID", Port(d1.x + 4.0, yG), "R")
    # ESD capacitors in series, in the gap below the FETs: they bridge CELL_P and PACK_P
    c110 = S.two("C110", s1.x + 3.81, yH, "h", first="CELL_P")
    c111 = S.two("C111", s1.x + 3.81 + 10.16, yH, "h", first="ESD_MID")
    S.wire([c110.r, c111.l], "ESD_MID")
    S.wire([s2, (s2.x, yH)], "PACK_P")
    S.wire([c111.r, (s2.x, yH)], "PACK_P")
    # ---- gate of Q101: CHG through R109, 10 M to the source (CELL_P)
    xn1 = snap(g1.x - 5.08)
    S.wire([g1, (xn1, yG)], "CHG_G")
    P.hang(S, "R110", xn1, yG, "CHG_G", to=None)
    r109 = S.two("R109", snap(xn1 - 11.43), yG, "h", first="CHG")
    S.wire([r109.r, (xn1, yG)], "CHG_G")
    S.wire([r109.l, r109.l.to(-2.54, 0)], "CHG"); S.label("CHG", r109.l.to(-2.54, 0), "L")
    # ---- gate of Q102: DSG through R111, 10 M and a zener to the source (PACK_P)
    xn2 = snap(g2.x + 5.08)
    xn3 = snap(xn2 + 11.43)
    S.wire([g2, (xn3, yG)], "DSG_G")
    P.hang(S, "R112", xn2, yG, "DSG_G", to=None)
    P.hang(S, "D103", xn3, yG, "DSG_G", to=None)
    r111 = S.two("R111", snap(xn3 + 8.89), yG, "h", first="DSG_G")
    S.wire([(xn3, yG), r111.l], "DSG_G")
    S.wire([r111.r, r111.r.to(2.54, 0)], "DSG"); S.label("DSG", r111.r.to(2.54, 0), "R")
    # ---- PACK_P line to the load: series capacitors to ground, test point, wire pad, supply arrow
    xc = snap(r111.r.x + 15.24)
    xt = snap(xc + 11.43)
    xl = snap(xt + 13.0)
    xe = snap(xl + 17.0)
    S.wire([(s2.x, yH), (xe, yH)], "PACK_P")
    c107 = P.hang(S, "C107", xc, yH, "PACK_P", to=None)
    S.wire([c107.bt, c107.bt.to(0, 2.54)], "PACK_CMID")
    c108 = S.two("C108", xc, c107.bt.y + 2.54 + 3.81, "v", first="PACK_CMID"); S.gnd(c108.bt)
    S.place("TP106", xt, yH)
    S.place("J113", xl, yH)
    S.rail("PACK_P", Port(xe, yH))
    # ---- WAKE: pulled up to CELL_P, test point on it; fuse heater leaves as a label
    xw = snap(xf + 19.05)
    r118 = P.hang(S, "R118", xw, yH, "CELL_P", to=None)
    S.place("TP113", xw, r118.bt.y, angle=180)
    hp = f.p("3")
    S.wire([hp, hp.to(0, 2.54)], "FUSE_HTR"); S.label("FUSE_HTR", hp.to(0, 2.54), "R")
    # ---- PACK- : wire pad, sense resistor with its Kelvin filter, load ground
    yL = snap(yH + 27.94)
    xrs = snap(xa + 16)
    j108 = S.place("J108", xJ, yL)
    r = kelvin(S, xrs, yL, "RS101", "R107", "R108", "C106", "CELL_N", "GND", "SRP", "SRN")
    S.wire([j108.p("1"), (r.l.x - 7.62, yL)], "CELL_N")
    S.wire([(r.r.x + 7.62, yL), (xe, yL)], "GND")
    S.place("TP109", xt, yL)
    S.place("J114", xl, yL)
    S.gnd(Port(xe, yL))
    S.end(sec)
    return sec
