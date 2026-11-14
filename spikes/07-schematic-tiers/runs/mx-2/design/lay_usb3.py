"""USB port sheet, section 3: BQ25756 charger controller with its programming networks."""
from sch import Port, snap
import patterns as P


def chain(S, x, y, refs, nets, top, bottom, taps):
    """Vertical resistor chain standing at x with its top pin at y. refs: resistors top to bottom.
    top / bottom: ('label', net) | ('rail', net) | ('gnd',) | ('label_only', net) for the two ends.
    taps: {index: net} gives a label stub on the node after resistor `index`. Returns the nodes' y values."""
    ys = [y]
    parts = []
    for i, r in enumerate(refs):
        t = S.two(r, x, ys[-1] + 3.81, "v", first=nets[i])
        parts.append(t); ys.append(ys[-1] + 7.62)
    end_top, end_bot = top, bottom
    if end_top[0] == "rail": S.rail(end_top[1], parts[0].a)
    elif end_top[0] == "label":
        a = parts[0].a
        S.wire([a, a.to(2.54, 0, "R")], end_top[1]); S.label(end_top[1], a.to(2.54, 0, "R"), "R")
    if end_bot[0] == "gnd": S.gnd(parts[-1].bt)
    elif end_bot[0] == "label":
        b = parts[-1].bt
        S.wire([b, b.to(2.54, 0, "R")], end_bot[1]); S.label(end_bot[1], b.to(2.54, 0, "R"), "R")
    for i, net in taps.items():
        nd = parts[i].bt
        S.wire([nd, nd.to(2.54, 0, "R")], net)
        S.label(net, nd.to(2.54, 0, "R"), "R")
    return parts


def charger(S, n, x, y, ldo):
    R = lambda pre, k: f"{pre}{n + k}"
    sec = S.begin("BQ25756 buck-boost charger: controller and programming", x, y,
                  note="I2C-programmed charger. Input window, frequency and current limits are set by the resistors at the pins")
    LP = snap(sec.ox + 82)
    ux, uy = snap(LP + 12.7), snap(sec.oy + 29)
    u = S.place(R("U", 3), ux, uy)
    RP = u.p("HIDRV1").x
    # ------------------------------------------------------------------------------------- left side flags
    for nm in ("ACP", "ACN", "SCL", "SDA", "~{INT}"): S.pin_label(u.p(nm), "L", 2.54)
    for nm in ("~{STAT1}", "~{STAT2}", "~{PG}"): S.nc(u.p(nm))
    # input window divider hangs from the PPHV wire at the VAC pin: PPHV - R409 - ACUV - R410 - ACOV - R411 - GND.
    # The first tap is level with the ACUV pin and runs straight in; the second jogs up into ACOV.
    vac, acuv, acov = u.p("VAC"), u.p("ACUV"), u.p("ACOV")
    xd = snap(LP - 36.83)
    S.wire([vac, (xd - 5.08, vac.y)], "PPHV")
    S.label("PPHV", Port(xd - 5.08, vac.y), "L")
    dv = chain(S, xd, vac.y, [R("R", 9), R("R", 10), R("R", 11)], ["PPHV", "ACUV", "ACOV"], ("wire",), ("gnd",), {})
    S.wire([dv[0].bt, acuv], "ACUV")
    xj = snap(LP - 20.32)
    S.wire([dv[1].bt, (xj, dv[1].bt.y), (xj, acov.y), acov], "ACOV")
    # charge enable: CE_N pulled up, MCU can force it high through R435
    ce = u.p("~{CE}")
    xn = snap(LP - 25.4)
    S.wire([ce, (xn, ce.y)], "CE_N")
    P.pullup(S, R("R", 17), xn, ce.y, "3V3")
    r435 = S.two(R("R", 35), xn - 12.7, ce.y, "h", first="CHG_INH")
    S.wire([(xn, ce.y), r435.r], "CE_N")
    S.pin_label(r435.l, "L", 2.54)
    # programming resistors fan out to rows 7.62 mm apart: FSW, ICHG, ILIM to ground, TS to its divider
    rows = {"FSW_SYNC": 12.7, "ICHG": 20.32, "ILIM_HIZ": 27.94, "TS": 35.56}
    turn = {"FSW_SYNC": None, "ICHG": 15.24, "ILIM_HIZ": 10.16, "TS": 5.08}
    ends = {}
    for nm, dy in rows.items():
        p = u.p(nm)
        yr = snap(uy + dy)
        if turn[nm]:
            S.wire([p, (LP - turn[nm], p.y), (LP - turn[nm], yr)], p.net)
        ends[nm] = Port(LP - (turn[nm] or 0), yr, "L", p.net)
    for nm, ref in (("FSW_SYNC", R("R", 12)), ("ICHG", R("R", 13)), ("ILIM_HIZ", R("R", 14))):
        e = ends[nm]
        r = S.two(ref, LP - 31.75, e.y, "h", first="GND")
        S.wire([e, r.r], e.net)
        S.gnd(r.l.out(2.54)); S.wire([r.l, r.l.out(2.54)], "GND")
    # thermistor divider on TS: REGN - R415 - TS - (R416 || TH401) - GND
    e = ends["TS"]
    xt = snap(LP - 57.15)
    S.wire([e, (xt, e.y)], e.net)
    r415 = S.two(R("R", 15), xt, e.y - 3.81, "v", first="REGN")
    S.label("REGN", r415.a, "R")
    r416 = S.two(R("R", 16), xt, e.y + 3.81, "v", first="TS"); S.gnd(r416.bt)
    th = S.two(R("TH", 1), xt - 12.7, e.y + 3.81, "v", first="TS"); S.gnd(th.bt)
    S.wire([(xt, e.y), (xt - 12.7, e.y)], "TS")
    # ------------------------------------------------------------------------------------ right side
    for nm in ("HIDRV1", "BTST1", "SW1", "LODRV1", "HIDRV2", "BTST2", "SW2", "LODRV2", "SRP", "SRN"):
        S.pin_label(u.p(nm), "R", 2.54)
    # battery voltage divider beside the FB and FBG pins: PACK_P - R418 - FB - R419 - FBG. Its foot is level with FBG;
    # the FB tap jogs down into its pin, right of the SRP/SRN flags.
    fb, fbg = u.p("FB"), u.p("FBG")
    xf = snap(RP + 27.94)
    dvb = chain(S, xf, snap(fbg.y - 15.24), [R("R", 18), R("R", 19)], ["PACK_P", "FB"], ("rail", "PACK_P"), ("none",), {})
    xk = snap(RP + 16.51)
    S.wire([dvb[0].bt, (xk, dvb[0].bt.y), (xk, fb.y), fb], "FB")
    S.wire([dvb[1].bt, fbg], "FBG")
    # REGN and DRV_SUP supplies, staggered so that each capacitor hangs clear of the line below it
    rg, dv = u.p("REGN"), u.p("DRV_SUP")
    S.wire([rg, (RP + 30.48, rg.y)], "REGN")
    P.hang(S, R("C", 10), RP + 22.86, rg.y, "REGN")
    S.label("REGN", Port(RP + 30.48, rg.y), "R")
    S.wire([dv, (RP + 7.62, dv.y)], "DRV_SUP")
    P.hang(S, R("C", 11), RP + 7.62, dv.y, "DRV_SUP")
    S.label("DRV_SUP", Port(RP + 7.62, dv.y), "R")
    S.nc(u.p("NC"))
    S.pin_gnd(u.p("PGND"), 2.54)
    S.end(sec)
    return sec, u
