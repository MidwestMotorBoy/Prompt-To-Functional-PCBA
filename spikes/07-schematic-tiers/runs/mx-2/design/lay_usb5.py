"""USB port sheet, sections 5 and 6: the 9 V gate-drive supply and the 5 V buck for PP5V."""
from sch import Port, snap
import patterns as P


def ldo9(S, n, x, y, ldo):
    R = lambda pre, k: f"{pre}{n + k}"
    sec = S.begin("9 V gate-drive supply", x, y, note="TPS7A4101, diode-ORed with REGN. The PD controller switches it off through Q409")
    ux, uy = snap(sec.ox + 70), snap(sec.oy + 20)
    u = S.place(R("U", 6), ux, uy)
    vin, en, out, fb, gnd = u.p("IN"), u.p("EN"), u.p("OUT"), u.p("FB"), u.p("GND")
    # input: PACK_P rail above the enable line, capacitor hangs from it
    yr = snap(vin.y - 10.16)
    S.wire([vin, (vin.x - 2.54, vin.y), (vin.x - 2.54, yr), (vin.x - 17.78, yr)], "PACK_P")
    S.rail("PACK_P", Port(vin.x - 17.78, yr))
    P.hang(S, R("C", 57), vin.x - 10.16, yr, "PACK_P")
    # enable: pulled up to REGN, pulled down by Q409 whose gate is the PD controller's DRV9_OFF
    xn = snap(en.x - 25.4)
    S.wire([en, (xn, en.y)], "V9_EN")
    r454 = S.two(R("R", 54), xn, en.y - 3.81, "v", first="REGN")
    S.wire([r454.a, r454.a.to(2.54, 0)], "REGN"); S.label("REGN", r454.a.to(2.54, 0), "R")
    q = S.place(R("Q", 9), xn - 2.54, en.y + 5.08)
    S.wire([q.p("D"), Port(xn, en.y)], "V9_EN")
    S.gnd(q.p("S"))
    gq = q.p("G")
    xg = snap(gq.x - 20.32)
    S.wire([gq, (xg - 7.62, gq.y)], gq.net)
    P.pullup(S, R("R", 55), xg, gq.y, ldo)
    S.label(gq.net, Port(xg - 7.62, gq.y), "L")
    # output: capacitor, feedback divider between OUT and FB, diode-OR into DRV_SUP
    xd = snap(out.x + 10.16)
    xc = snap(out.x + 27.94)
    xo = snap(out.x + 52.07)
    S.wire([out, (xo, out.y)], "V9_DRV")
    S.wire([fb, (xd, fb.y)], "V9_FB")
    S.two(R("R", 52), xd, out.y + 3.81, "v", first="V9_DRV")
    r453 = S.two(R("R", 53), xd, fb.y + 3.81, "v", first="V9_FB"); S.gnd(r453.bt)
    P.hang(S, R("C", 58), xc, out.y, "V9_DRV")
    d11 = S.two(R("D", 11), xo + 8.89, out.y, "h", first="V9_DRV")
    S.wire([(xo, out.y), d11.l], "V9_DRV")
    yb = snap(out.y + 10.16)
    d10 = S.two(R("D", 10), xo + 8.89, yb, "h", first="REGN")
    S.pin_label(d10.l, "L", 5.08)
    xb = snap(d11.r.x + 5.08)
    S.wire([d11.r, (xb, out.y), (xb, yb), d10.r], "DRV_SUP")
    S.wire([(xb, out.y), (xb + 5.08, out.y)], "DRV_SUP")
    S.label("DRV_SUP", Port(xb + 5.08, out.y), "R")
    S.pin_gnd(gnd, 2.54)
    S.end(sec)
    return sec


def buck5(S, n, x, y, ldo):
    R = lambda pre, k: f"{pre}{n + k}"
    sec = S.begin("5 V buck for PP5V (TPS62933)", x, y, note="Powers the PD controller's PP5V. Enabled by the MCU")
    ux, uy = snap(sec.ox + 62), snap(sec.oy + 22)
    u = S.place(R("U", 4), ux, uy)
    vin, en, ss, rt = u.p("VIN"), u.p("EN"), u.p("SS"), u.p("RT")
    bst, sw, fb, gnd = u.p("BST"), u.p("SW"), u.p("FB"), u.p("GND")
    # input rail above the enable line with the two input capacitors
    yr = snap(vin.y - 10.16)
    S.wire([vin, (vin.x - 2.54, vin.y), (vin.x - 2.54, yr), (vin.x - 33.02, yr)], "PACK_P")
    S.rail("PACK_P", Port(vin.x - 33.02, yr))
    P.hang(S, R("C", 46), vin.x - 25.4, yr, "PACK_P")
    P.hang(S, R("C", 44), vin.x - 11.43, yr, "PACK_P")
    # enable from the MCU, pulled down; soft start; RT to ground
    xe = snap(en.x - 25.4)
    S.wire([en, (xe - 10.16, en.y)], en.net)
    P.hang(S, R("R", 32), xe, en.y, en.net, to="gnd")
    S.pin_label(Port(xe - 10.16, en.y, "L", en.net), "L", 0.0)
    xs = snap(ss.x - 7.62)
    S.wire([ss, (xs, ss.y)], ss.net)
    P.hang(S, R("C", 39), xs, ss.y, ss.net)
    S.pin_gnd(rt, 2.54)
    # switch node: bootstrap capacitor straight between BST and SW, inductor to PP5V, divider from PP5V to FB
    xb = snap(sw.x + 10.16)
    S.wire([bst, (xb, bst.y)], bst.net)
    cb = S.two(R("C", 40), xb, bst.y + 3.81, "v", first=bst.net)
    xl = snap(xb + 17.78)
    l = S.two(R("L", 2), xl, sw.y, "h", first=sw.net)
    S.wire([sw, l.l], sw.net)
    xf = snap(l.r.x + 7.62)
    S.wire([l.r, (xf + 62.0, sw.y)], "PP5V")
    S.two(R("R", 33), xf, sw.y + 3.81, "v", first="PP5V")
    S.wire([fb, (xf, fb.y)], fb.net)
    r34 = S.two(R("R", 34), xf, fb.y + 3.81, "v", first=fb.net); S.gnd(r34.bt)
    for i, c in enumerate((R("C", 41), R("C", 42), R("C", 43))):
        P.hang(S, c, xf + 17.78 + i * 15.24, sw.y, "PP5V")
    S.label("PP5V", Port(xf + 62.0, sw.y), "R")
    S.pin_gnd(gnd, 2.54)
    S.end(sec)
    return sec
