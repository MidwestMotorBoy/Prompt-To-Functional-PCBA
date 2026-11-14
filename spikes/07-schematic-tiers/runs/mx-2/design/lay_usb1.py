"""USB port sheet, section 1: USB-C receptacle, VBUS protection and the TPD6S300 CC protector."""
from sch import Port, snap
import patterns as P


def connector(S, n, x, y, ldo):
    """ldo: name of the PD controller's own 3.3 V rail (a power symbol, unique per port). Returns (section, VBUS port)."""
    R = lambda pre, k: f"{pre}{n + k}"
    sec = S.begin("USB-C connector and port protection", x, y,
                  note="TPD6S300 presents Rd (RPD_G) on both CC pins until the PD controller has booted")
    jx, jy = snap(sec.ox + 12), snap(sec.oy + 63.5)
    yV = snap(jy - 38.1)
    j = S.place(R("J", 1), jx, jy)
    # ---- VBUS: up and over to a rail, protection hangs from the rail
    v = j.p("VBUS")
    xr = snap(v.x + 5.08)
    d = S.place(R("D", 1), jx + 38.1, yV + 7.62)
    xe = snap(jx + 126)
    S.wire([v, (xr, v.y), (xr, yV), (xe, yV)], "VBUS")
    P.hang(S, R("C", 6), jx + 57, yV, "VBUS")
    P.hang(S, R("C", 50), jx + 74, yV, "VBUS")
    S.gnd(Port(d.x, d.y + 7.62))
    S.label("VBUS", Port(xr + 8.89, yV), "R")
    vbus_out = Port(xe, yV, "R", "VBUS")
    # ---- D+ and D- are tied together (dedicated charging port), no data
    ds = j.ps("D-") + j.ps("D+")
    o = P.tie(S, ds, "DPDN_DCP", reach=2.54)
    S.label("DPDN_DCP", Port(o[0].x, max(q.y for q in o)), "R")
    for nm in ("SBU1", "SBU2"): S.nc(j.p(nm))
    sh, gd = j.p("SHIELD"), j.p("GND")
    S.wire([sh, gd], "GND"); S.gnd(gd)
    # ---- TPD6S300
    ux, uy = snap(jx + 100), snap(jy + 1.27)
    u = S.place(R("U", 5), ux, uy)
    S.wire([j.p("CC1"), u.p("C_CC1")], "C_CC1")
    S.wire([j.p("CC2"), u.p("C_CC2")], "C_CC2")
    S.label("C_CC1", Port(j.p("CC1").x + 30.48, j.p("CC1").y), "R")
    S.label("C_CC2", Port(j.p("CC2").x + 30.48, j.p("CC2").y + 0.0), "R")
    # the dead-battery Rd pins are strapped to their own CC line: RPD_G1 to C_CC1, RPD_G2 to C_CC2 (one plain crossing)
    c1, c2, g1p, g2p = u.p("C_CC1"), u.p("C_CC2"), u.p("RPD_G1"), u.p("RPD_G2")
    xs1, xs2 = snap(c1.x - 7.62), snap(c1.x - 12.7)
    S.wire([g1p, (xs1, g1p.y), (xs1, c1.y)], "C_CC1")
    S.wire([g2p, (xs2, g2p.y), (xs2, c2.y)], "C_CC2")
    for nm in ("C_SBU1", "C_SBU2", "D1", "D2", "SBU1", "SBU2"): S.nc(u.p(nm))
    g1, g2 = u.p("GND"), u.p("N.C.")
    S.wire([g1, g1.out(2.54), g2.out(2.54), g2], "GND")
    S.gnd(Port(ux, g1.y + 2.54))
    # supply and bias on top, risers to a small rail each
    yt = snap(uy - 29.21)
    vp, vb = u.p("VPWR"), u.p("VBIAS")
    S.wire([vp, (vp.x, yt), (vp.x - 8.89, yt)], ldo)
    S.rail(ldo, Port(vp.x, yt))
    P.hang(S, R("C", 52), vp.x - 8.89, yt, ldo)
    S.wire([vb, (vb.x, yt), (vb.x + 7.62, yt)], "VBIAS")
    P.hang(S, R("C", 51), vb.x + 7.62, yt, "VBIAS")
    # ---- CC lines out: CC1 steps up so that each cap can hang from its own line
    px = u.p("CC1").x
    cc1, cc2 = u.p("CC1"), u.p("CC2")
    y1u = snap(cc1.y - 15.24)
    S.wire([cc1, (px + 7.62, cc1.y), (px + 7.62, y1u), (px + 30.48, y1u)], "CC1")
    P.hang(S, R("C", 1), px + 16.51, y1u, "CC1")
    S.label("CC1", Port(px + 30.48, y1u), "R")
    S.wire([cc2, (px + 30.48, cc2.y)], "CC2")
    P.hang(S, R("C", 2), px + 16.51, cc2.y, "CC2")
    S.label("CC2", Port(px + 30.48, cc2.y), "R")
    # ---- fault flag, open drain
    fl = u.p("~{FLT}")
    xp = px + 40.64
    S.wire([fl, (xp + 3.81, fl.y)], fl.net)
    P.pullup(S, R("R", 41), xp, fl.y, ldo)
    S.label(fl.net, Port(xp + 3.81, fl.y), "R")
    S.end(sec)
    return sec, vbus_out
