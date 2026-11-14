"""USB port sheet, section 4: the four-switch power stage drawn as a path, with its current sense and bootstrap parts."""
from sch import Port, snap
import patterns as P


def sense(S, xr, y, rs, rp, rn, cdiff, cp, cn, net_l, net_r, fl, fr):
    """Sense resistor `rs` in line at (xr, y) (net_l on its left, net_r on its right) with the Kelvin filter hanging below:
    rp from a tap on the left wire, rn from a tap on the right wire, cdiff across the two filtered nodes, cp / cn from each to ground."""
    r = S.two(rs, xr, y, "h", first=net_l)
    xa, xb = snap(r.l.x - 7.62), snap(r.r.x + 7.62)
    S.wire([r.l, (xa, y)], net_l); S.wire([r.r, (xb, y)], net_r)
    S.two(rp, xa, y + 3.81, "v", first=net_l)
    S.two(rn, xb, y + 3.81, "v", first=net_r)
    yn = y + 7.62
    yc = yn + 2.54
    S.wire([(xa, yn), (xa, yc)], fl); S.wire([(xb, yn), (xb, yc)], fr)
    S.two(cdiff, xr, yn, "h", first=fl)
    S.wire([(xa, yn), (xr - 3.81, yn)], fl); S.wire([(xr + 3.81, yn), (xb, yn)], fr)
    P.hang(S, cp, xa, yc, fl)
    P.hang(S, cn, xb, yc, fr)
    S.wire([(xa, yn), (xa - 2.54, yn)], fl)
    S.label(fl, Port(xa - 2.54, yn), "L")
    S.wire([(xb, yn), (xb + 2.54, yn)], fr)
    S.label(fr, Port(xb + 2.54, yn), "R")
    return r


def half_bridge(S, ref, x, y, mirror, hi_ref, lo_ref, hi_net, lo_net, drain_net, d_ref, c_ref, bt_net, sw_net, y_rail, dsup="DRV_SUP"):
    """Dual FET `ref` as a half bridge at (x, y): high-side unit above, low-side unit below, gates through hi_ref / lo_ref
    to flags, drain up to the rail, switch node out, source to ground. mirror=True flips left to right.
    Returns dict of useful points."""
    k = -1 if mirror else 1
    yh, yl = y, y + 10.16
    u1 = S.place(ref, x, yh, mirror=mirror, unit=1)
    u2 = S.place(ref, x, yl, mirror=mirror, unit=2)
    g1, d1, sw1 = u1.p("G1"), u1.p("D1"), u1.p("SW")
    g2, sw2, s2 = u2.p("G2"), u2.p("SW"), u2.p("S2")
    # gates: flag - 0R - gate
    for g, ref_r, net in ((g1, hi_ref, hi_net), (g2, lo_ref, lo_net)):
        r = S.two(ref_r, g.x - k * 12.7, g.y, "h", first=(g.net if mirror else net), text="auto" if mirror else "B")
        near, far = (r.l, r.r) if mirror else (r.r, r.l)
        S.wire([g, near], g.net)
        S.pin_label(far, "R" if mirror else "L", 2.54)
    # drain to the rail, switch node, source to ground
    xd = snap(d1.x + k * 2.54)
    S.wire([d1, (xd, d1.y), (xd, y_rail)], drain_net)
    xs = snap(sw1.x + k * 5.08)
    S.wire([sw1, (xs, sw1.y), (xs, sw2.y), (sw2.x, sw2.y)], sw_net)
    ysw = snap((sw1.y + sw2.y) / 2)
    S.wire([s2, (xs, s2.y)], "GND"); S.gnd(Port(xs, s2.y))
    return dict(xd=xd, xs=xs, ysw=ysw, d1=d1, s2=s2, u1=u1, u2=u2)


def power_stage(S, n, x, y, ldo):
    R = lambda pre, k: f"{pre}{n + k}"
    sec = S.begin("Four-switch power stage with current sense", x, y,
                  note="Q401/Q402 are dual FETs, each drawn as two half bridges. 0R gate resistors are tuning positions")
    yP = snap(sec.oy + 14)
    xr = snap(sec.ox + 22)
    # ---- input: PPHV - R424 - AC_SNS_N rail, input capacitors hang from the rail
    r424 = sense(S, xr, yP, R("R", 24), R("R", 25), R("R", 26), R("C", 14), R("C", 15), R("C", 16), "PPHV", "AC_SNS_N", "ACP_F", "ACN_F")
    S.wire([r424.l, r424.l.to(-12.7, 0)], "PPHV")
    S.label("PPHV", r424.l.to(-12.7, 0), "L")
    caps = [R("C", 21), R("C", 56), R("C", 24), R("C", 27), R("C", 23), R("C", 20), R("C", 30)]
    xc = snap(r424.r.x + 24.0)
    pitch = 13.97
    for i, c in enumerate(caps):
        P.hang(S, c, xc + i * pitch, yP, "AC_SNS_N")
    xh1 = snap(xc + (len(caps) - 1) * pitch + 5.08)                # centre of the first half bridge: its drain riser stands 14 mm after the last capacitor
    # ---- half bridges and inductor
    h1 = half_bridge(S, R("Q", 1), xh1, snap(yP + 15.24), False, R("R", 44), R("R", 45), "HIDRV1", "LODRV1", "AC_SNS_N", R("D", 4), R("C", 12), "BTST1", "SW1", yP)
    S.wire([r424.r, (h1["xd"], yP)], "AC_SNS_N")
    S.label("AC_SNS_N", Port(r424.r.x + 10.16, yP), "R")
    xl = snap(xh1 + 62.23)
    xh2 = snap(xh1 + 124.46)
    h2 = half_bridge(S, R("Q", 2), xh2, snap(yP + 15.24), True, R("R", 46), R("R", 47), "HIDRV2", "LODRV2", "BAT_SNS_P", R("D", 5), R("C", 13), "BTST2", "SW2", yP)
    l = S.two(R("L", 1), xl, h1["ysw"], "h", first="SW1")
    S.wire([(h1["xs"], h1["ysw"]), l.l], "SW1")
    S.wire([l.r, (h2["xs"], h2["ysw"])], "SW2")
    S.label("SW1", Port(h1["xs"] + 5.08, h1["ysw"]), "R")
    S.label("SW2", Port(h2["xs"] - 5.08, h2["ysw"]), "L")
    # ---- bootstrap: DRV_SUP - diode - BTST - capacitor - SW, standing on the switch-node wire
    for h, k, d_ref, c_ref, bt, sw, xcap in ((h1, 1, R("D", 4), R("C", 12), "BTST1", "SW1", xh1 + 41.91),
                                              (h2, -1, R("D", 5), R("C", 13), "BTST2", "SW2", xh2 - 41.91)):
        xcap = snap(xcap)
        cb = S.two(c_ref, xcap, h["ysw"] - 3.81, "v", first=bt)
        S.wire([Port(xcap, h["ysw"]), cb.bt], sw)
        dd = S.two(d_ref, xcap - k * 10.16, cb.a.y, "h", first="DRV_SUP" if k == 1 else bt)
        near = dd.r if k == 1 else dd.l
        far = dd.l if k == 1 else dd.r
        S.wire([near, cb.a], bt)
        S.wire([cb.a, cb.a.to(2.54 * k, 0)], bt)
        S.label(bt, cb.a.to(2.54 * k, 0), "R" if k == 1 else "L")
        S.pin_label(far, "L" if k == 1 else "R", 5.08)
    # ---- output: BAT_SNS_P rail with its capacitors, R427 in line, PACK_P
    xo = snap(h2["xd"] + 17.78)
    ocaps = [R("C", 38), R("C", 31), R("C", 34)]
    for i, c in enumerate(ocaps):
        P.hang(S, c, xo + i * pitch, yP, "BAT_SNS_P")
    xr2 = snap(xo + len(ocaps) * pitch + 12.0)
    r427 = sense(S, xr2, yP, R("R", 27), R("R", 28), R("R", 29), R("C", 17), R("C", 18), R("C", 19), "BAT_SNS_P", "PACK_P", "SRP_F", "SRN_F")
    S.wire([(h2["xd"], yP), r427.l], "BAT_SNS_P")
    S.label("BAT_SNS_P", Port(h2["xd"] + 2.54, yP), "R")
    xe = snap(r427.r.x + 17.78)
    S.wire([r427.r, (xe, yP)], "PACK_P")
    S.rail("PACK_P", Port(xe, yP))
    tp = S.place(R("TP", 12), h1["xs"] + 15.24, h1["s2"].y)
    S.wire([Port(h1["xs"], h1["s2"].y), tp.p("1")], "GND")
    S.end(sec)
    return sec
