"""USB port sheet, section 2: TPS25751D PD controller with its supply, strap, pull-ups and the unused GPIOs."""
from sch import Port, snap
import patterns as P


def pd_controller(S, n, x, y, ldo, vbus):
    """vbus: the VBUS rail end coming from section 1 (its y fixes where the controller sits). Returns the section."""
    R = lambda pre, k: f"{pre}{n + k}"
    sec = S.begin("USB PD controller TPS25751D", x, y, note="Internal 5 A switch VBUS to PPHV; ADCIN1 sets the I2C target address")
    LP = snap(sec.ox + 26)
    ux, uy = snap(LP + 15.24), snap(vbus.y + 15.24)
    u = S.place(R("U", 1), ux, uy)
    RP = u.p("PPHV").x
    # ---- VBUS in, 3V3 in with its capacitor above the VBUS line
    vi, vb = u.p("VBUS_IN"), u.p("VBUS")
    S.wire([vbus, (LP - 2.54, vbus.y)], "VBUS", bridge=True)
    P.tie(S, [vi, vb], "VBUS", reach=2.54)
    v3 = u.p("VIN_3V3")
    y3 = snap(v3.y - 7.62)
    S.wire([v3, (LP - 2.54, v3.y), (LP - 2.54, y3), (LP - 12.7, y3)], "3V3")
    S.rail("3V3", Port(LP - 2.54, y3))
    P.hang(S, R("C", 3), LP - 12.7, y3, "3V3")
    # ---- CC pins to the protector section
    for nm in ("CC1", "CC2"): S.pin_label(u.p(nm), "L", 2.54)
    # ---- unused GPIO grounded on one bus; the two used ones show their nets between pin and bus
    xb = snap(LP - 16.51)
    used = {"GPIO3": None, "GPIO6": None}
    gp = [u.p(f"GPIO{k}") for k in (0, 1, 2, 3, 4, 5, 6, 7, 11)]
    for g in gp:
        if g.pin in used: S.pin_label(g, "L", 2.54)
        else: S.wire([g, (xb, g.y)], "GND")
    ys = [g.y for g in gp]
    S.wire([(xb, ys[0]), (xb, ys[-1])], "GND")
    S.gnd(Port(xb, ys[-1]))
    S.text("Unused GPIOs\ntied to GND", xb - 5.08, ys[-1] + 6.5, 1.27, kind="note")
    g = u.p("GND")
    S.pin_gnd(g, 2.54)
    pads = sorted((n for n, (pt, rec) in u.pins.items() if rec["name"] == "GND"), key=int)
    if len(pads) > 2: S.text("GND pads " + ", ".join(pads), g.x + 2.0, g.y + 0.2, 1.27, kind="note")
    # ---- PPHV rail: riser from the pin, capacitors hang from it, flag at the end
    pp = u.p("PPHV")
    yp = snap(pp.y - 12.7)
    xp = snap(RP + 5.08)
    S.wire([pp, (xp, pp.y), (xp, yp), (xp + 50.8, yp)], "PPHV")
    P.hang(S, R("C", 49), RP + 17.78, yp, "PPHV")
    P.hang(S, R("C", 9), RP + 34.29, yp, "PPHV")
    S.label("PPHV", Port(xp + 50.8, yp), "R")
    # ---- PP5V line with its capacitor
    p5 = u.p("PP5V")
    S.wire([p5, (RP + 38.1, p5.y)], "PP5V")
    P.hang(S, R("C", 7), RP + 22.86, p5.y, "PP5V")
    S.label("PP5V", Port(RP + 38.1, p5.y), "R")
    # ---- DRAIN pins tied together
    dr = u.ps("DRAIN") + u.ps("DRAIN_EP")
    o = P.tie(S, dr, None, reach=2.54)
    S.label(dr[0].net, Port(o[0].x, o[0].y), "R")
    # ---- LDO outputs. LDO_3V3 runs right from its pin as a supply rail: the ADCIN1 strap joins it on port 1, its capacitor
    # hangs from it at the pin and the three I2C pull-ups hang from it above their lines. LDO_1V5 has only its own capacitor,
    # which stands at the end of the line because the rows under the pin belong to the rail.
    l15, l33 = u.p("LDO_1V5"), u.p("LDO_3V3")
    a1, a2 = u.p("ADCIN1"), u.p("ADCIN2")
    pulls = (("I2Cc_SCL", R("R", 3), 25.4), ("I2Cc_SDA", R("R", 2), 43.18), ("~{I2Cc_IRQ}", R("R", 4), 60.96))
    xe = snap(RP + pulls[-1][2])
    S.wire([l33, (xe, l33.y)], ldo)
    S.label(ldo, Port(xe, l33.y), "R", glob=True)                         # the rail's name, where it leaves for the other sections
    P.hang(S, R("C", 4), snap(RP + 10.16), l33.y, ldo)
    if a1.net and S.disp(a1.net) == ldo:
        S.wire([a1, (a1.x + 2.54, a1.y), (a1.x + 2.54, l33.y)], ldo)
        S.pin_gnd(a2, 5.08)
    else:
        o = P.tie(S, [a1, a2], "GND", reach=2.54)
        S.gnd(Port(o[0].x, max(q.y for q in o)))
    for nm, ref, dx in pulls:
        pin = u.p(nm)
        xr = snap(RP + dx)
        r = S.two(ref, xr, pin.y - 3.81, "v", first=ldo)
        S.wire([r.a, (xr, l33.y)], ldo)
        S.wire([pin, (xr + 3.81, pin.y)], pin.net)
        S.label(pin.net, Port(xr + 3.81, pin.y), "R")
    x15 = snap(xe + 17.78)
    S.wire([l15, (x15, l15.y)], "LDO_1V5")
    S.label("LDO_1V5", Port(l15.x + 5.08, l15.y), "R")
    P.hang(S, R("C", 5), x15, l15.y, "LDO_1V5")
    for nm in ("I2Ct_SCL", "I2Ct_SDA", "~{I2Ct_IRQ}"): S.pin_label(u.p(nm), "R", 2.54)
    # ---- configuration EEPROM under the pull-ups
    e = S.place(R("U", 2), snap(RP + 40.64), snap(uy + 35.56), text="TL")
    for nm in ("SDA", "SCL"): S.pin_label(e.p(nm), "R", 2.54)
    S.pin_gnd(e.p("WP"), 2.54)
    o = P.tie(S, [e.p("A0"), e.p("A1"), e.p("A2")], "GND", reach=2.54)
    S.gnd(Port(o[0].x, max(q.y for q in o)))
    S.pin_gnd(e.p("GND"), 2.54)
    vc = e.p("VCC")
    yv = snap(vc.y - 7.62)
    xr = snap(vc.x + 7.62)
    S.wire([vc, (xr, vc.y), (xr, yv), (xr + 8.89, yv)], ldo)
    S.rail(ldo, Port(xr, yv))
    P.hang(S, R("C", 8), xr + 8.89, yv, ldo)
    S.end(sec)
    return sec, u
