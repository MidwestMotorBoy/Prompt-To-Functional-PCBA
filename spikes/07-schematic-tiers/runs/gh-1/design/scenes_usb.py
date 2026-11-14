"""USB port sheet (used for both ports): USB-C front end and PD controller, BQ25756 charger, four-switch power stage,
9 V gate-drive supply and 5 V buck. Refs are built from the port's base number so one scene draws both sheets."""
from lay import *

EXTRA = ("VBUS", "PPHV", "PP5V", "SW1", "SW2", "REGN", "DRV_SUP", "FB", "FBG", "TS", "CE_N", "ACUV", "ACOV", "FSW", "ILIM", "ICHG",
         "HG1", "HG2", "LG1", "LG2", "HIDRV1", "HIDRV2", "LODRV1", "LODRV2", "BTST1", "BTST2", "SRP_F", "SRN_F", "ACP_F", "ACN_F",
         "AC_SNS_N", "BAT_SNS_P", "CHG_INT", "I2CC_SDA", "I2CC_SCL", "SBU_FLT", "DRV9_OFF", "V9_DRV", "V9_FB", "V9_EN",
         "SW_5V", "BST_5V", "SS_5V", "FB_5V", "LDO_1V5", "VBIAS", "C_CC1", "C_CC2", "CC1", "CC2", "PD_DRAIN")


class Ctx:
    def __init__(self, L):
        self.L = L
        self.s = L.s
        name = L.s.name
        self.n = 400 if name.endswith("1") else 500
        self.name = name
        L.disp.update({f"{name}/{k}": k for k in EXTRA})
        self.net = lambda s_: f"{name}/{s_}"

    def r(self, p, k): return f"{p}{self.n + k}"


def scene(L):
    X = Ctx(L)
    s = L.s
    X0, Y0 = 20.32, 22.86
    L.title(L.s.name, X0, Y0, 3.0)
    L.note("Power path: J%d USB-C VBUS -> PD controller (PPHV) -> input shunt R%d -> four-switch stage -> shunt R%d -> PACK_P.\n"
           "Gate drive: 9 V LDO or REGN through D%d / D%d.  PD controller power: 5 V buck from PACK_P." % (X.n + 1, X.n + 24, X.n + 27, X.n + 10, X.n + 11), X0, Y0 + 6.0)
    L.pack([("USB-C input, port protection and PD controller", lambda S, x, y: pd_group(S, Ctx(S), x, y)),
            ("BQ25756 charger: input window, programming, drivers, current sense, battery feedback", lambda S, x, y: charger_group(S, Ctx(S), x, y)),
            ("Four-switch buck-boost power stage (VBUS side left, pack side right)", lambda S, x, y: power_group(S, Ctx(S), x, y)),
            ("5 V buck for PP5V (TPS62933)", lambda S, x, y: buck_group(S, Ctx(S), x, y)),
            ("9 V gate-drive supply, diode-ORed with REGN", lambda S, x, y: v9_group(S, Ctx(S), x, y)),
            ("Configuration EEPROM (PD I2C bus 2)", lambda S, x, y: eeprom_group(S, Ctx(S), x + 22.86, y + 20.32))], top=40.0, fixed=True)
    return X


def pd_group(L, X, x0, y0):
    s, r, N = L.s, X.r, X.net
    yCC = y0 + 36.0
    xJ = snap(x0 + 30.0)
    # ---------------------------------------------------------------- connector
    j = L.ic(r("J", 1), xJ, yCC, at_pin="CC1", gaps={"R": {"CC1": 27.94}}, text="above")
    yV = j.pin("VBUS")[1]
    # D+ and D- shorted: dedicated charging port, no data
    dp = [(p["sx"], p["sy"]) for p in j.pins if p["name"] in ("D+", "D-")]
    ys = sorted({y for _, y in dp})
    xb = snap(xJ + 5.08)
    for y in ys: s.wire(xJ, y, xb, y)
    s.wire(xb, ys[0], xb, ys[-1])
    L.use(j, "D+", "D-")
    L.note("D+ and D- tied:\ndedicated charging\nport, no data", xb + 2.5, ys[0] + 2.0)
    # ---------------------------------------------------------------- port protection (U405) between connector and PD controller
    gm = {"_custom": {"pins": {"RPD_G1": (-16.51, 13.97, 0), "RPD_G2": (-16.51, 6.35, 0), "VPWR": (-10.16, -16.51, 90), "VBIAS": (10.16, -16.51, 90)},
                      "rect": (-13.97, -13.97, 13.97, 16.51)},
          "R": {"CC2": 20.32, "SBU2": 5.08}}
    xM = snap(xJ + 33.02 + 25.4)
    esd = L.ic(r("U", 5), xM, yCC, at_pin="CC1", gaps=gm, text="above")
    # CC lines from the connector into the protector, dead-battery pull-downs tied on
    for a, b in (("CC1", "C_CC1"), ("CC2", "C_CC2")):
        pa, pb = j.pin(a), esd.pin(b)
        s.wire(pa[0], pa[1], pb[0], pb[1])
    rp1, rp2 = esd.pin("RPD_G1"), esd.pin("RPD_G2")
    yc1, yc2 = esd.pin("C_CC1")[1], esd.pin("C_CC2")[1]
    s.path(rp1, (rp1[0] - 3.81, rp1[1]), (rp1[0] - 3.81, yc1))
    s.path(rp2, (rp2[0] - 3.81, rp2[1]), (rp2[0] - 3.81, yc2))
    L.use(esd, "C_CC1", "C_CC2", "RPD_G1", "RPD_G2")
    L.use(j, "CC1", "CC2")
    # VPWR and VBIAS at the bottom: capacitors hang from them
    for pin, ref, side in (("VPWR", r("C", 52), "L"), ("VBIAS", r("C", 51), "R")):
        px, py = esd.pin(pin)
        net = L.netat(esd, pin)
        s.wire(px, py, px, py + 2.54)
        p = L.drop(ref, px, py + 2.54, net, side=side)
        if pin == "VPWR":
            s.wire(px, py + 2.54, px - 6.35, py + 2.54); L.lab(net, px - 6.35, py + 2.54, "L")
        L.use(esd, pin)
    L.finish(esd, n=2.54)
    # ---------------------------------------------------------------- PD controller
    xU = snap(xM + 50.8)
    gu = {"L": {"VBUS_IN": 20.32, "CC1": 27.94, "CC2": 20.32, "GPIO3": 10.16, "GPIO6": 10.16, "GPIO7": 10.16},
          "R": {"PP5V": 20.32, "DRAIN": 20.32, "LDO_3V3": 20.32, "~{I2Cc_SCL}": 15.24, "I2Cc_SCL": 15.24, "I2Cc_SDA": 5.08, "~{I2Cc_IRQ}": 5.08,
                "I2Ct_SCL": 10.16, "I2Ct_SDA": 5.08, "~{I2Ct_IRQ}": 5.08}}
    u = L.ic(r("U", 1), xU, yCC, at_pin="CC1", gaps=gu, text="above")
    P = u.pin
    # CC1 / CC2 straight across, one 220p capacitor each
    for pin, ref in (("CC1", r("C", 1)), ("CC2", r("C", 2))):
        pa, pb = esd.pin(pin), u.pin(pin)
        s.wire(pa[0], pa[1], pb[0], pb[1])
        L.drop(ref, snap(pa[0] + 12.7), pa[1], L.netat(u, pin))
        L.use(u, pin); L.use(esd, pin)
    # VBUS rail from the connector with TVS and capacitors, down to the controller
    xs0 = snap(xJ + 17.78)
    s.wire(xJ, yV, snap(xs0 + 21.0), yV)
    tvs = L.ic(r("D", 1), xs0, yV, at_pin="IN", text=((xs0 + 4.5, yV + 6.3, "l"), (xs0 + 4.5, yV + 8.9, "l")))
    L.stub(tvs, "GND", n=2.54)
    L.use(j, "VBUS")
    xs, xe = L.hang_row([r("C", 6), r("C", 50)], xs0 + 21.0, yV, N("VBUS"))
    s.wire(xs[-1], yV, P("VBUS")[0], yV)
    vi = P("VBUS_IN")
    s.path(vi, (vi[0] - 5.08, vi[1]), (vi[0] - 5.08, yV))
    L.use(u, "VBUS", "VBUS_IN")
    # 3V3 supply
    yv3 = P("VIN_3V3")[1]
    xa = snap(P("VIN_3V3")[0] - 19.05)
    s.rail("3V3", xa, yv3, "+3V3")
    s.wire(xa, yv3, P("VIN_3V3")[0], yv3)
    L.drop(r("C", 3), snap(P("VIN_3V3")[0] - 10.16), yv3, "3V3", side="L")
    L.use(u, "VIN_3V3")
    # GPIO: unused ones grounded in groups, GPIO3 and GPIO6 are signals
    xl = P("GPIO0")[0]
    def gbar(pins):
        pts = [P(p) for p in pins]
        for (px, py) in pts: s.wire(px, py, px - 5.08, py)
        s.wire(pts[0][0] - 5.08, pts[0][1], pts[-1][0] - 5.08, pts[-1][1] + 2.54)
        s.gnd(pts[0][0] - 5.08, pts[-1][1] + 2.54)
        L.use(u, *pins)
    gbar(["GPIO0", "GPIO1", "GPIO2"]); gbar(["GPIO4", "GPIO5"]); gbar(["GPIO7", "GPIO11"])
    # GPIO3: SBU fault with its pull-up; GPIO6: gate-drive supply off command
    px, py = P("GPIO3"); net = L.netat(u, "GPIO3")
    xn = snap(px - 10.16)
    s.wire(px, py, snap(xn - 7.62), py); L.lab(net, snap(xn - 7.62), py, "L")
    r441 = L.pull(r("R", 41), xn, py, "P1_LDO_3V3" if False else L.netat(u, "LDO_3V3"), side="L")
    L.use(u, "GPIO3")
    px, py = P("GPIO6"); net = L.netat(u, "GPIO6")
    s.wire(px, py, px - 10.16, py); L.lab(net, px - 10.16, py, "L")
    L.use(u, "GPIO6")
    # ------------------------------------------------------------ right side
    xR = P("PPHV")[0]
    def line(pin, hangs=(), end=None, lab=True):
        px, py = P(pin); net = L.netat(u, pin)
        xe_ = snap(px + (end or 10.16 * (len(hangs) + 1)))
        s.wire(px, py, xe_, py)
        for k, ref in enumerate(hangs):
            L.drop(ref, snap(px + 10.16 + 17.78 * k), py, net)
        if lab: L.lab(net, xe_, py, "R")
        L.use(u, pin)
        return xe_
    line("PPHV", [r("C", 49)], end=22.86)
    line("PP5V", [r("C", 7)], end=22.86)
    # drain pins tied
    d1, d2 = P("DRAIN"), P("DRAIN_EP")
    s.path(d1, (d1[0] + 5.08, d1[1]), (d1[0] + 5.08, d2[1]), d2)
    ym = snap((d1[1] + d2[1]) / 2)
    s.wire(d1[0] + 5.08, ym, d1[0] + 10.16, ym); L.lab(L.netat(u, "DRAIN"), d1[0] + 10.16, ym, "R")
    L.use(u, "DRAIN", "DRAIN_EP")
    px, py = P("LDO_1V5"); s.wire(px, py, px + 10.16, py)
    L.drop(r("C", 5), px + 10.16, py, L.netat(u, "LDO_1V5"))
    L.use(u, "LDO_1V5")
    # LDO_3V3 with ADCIN1 strapped to it and ADCIN2 grounded
    xe3 = line("LDO_3V3", [r("C", 4)], end=22.86)
    l3 = P("LDO_3V3")
    gp = []
    for pin in ("ADCIN1", "ADCIN2"):
        if L.netat(u, pin) == L.netat(u, "LDO_3V3"):
            a = P(pin); s.path(a, (a[0] + 5.08, a[1]), (a[0] + 5.08, l3[1])); L.use(u, pin)
        else:
            gp.append(pin)
    if gp:                                      # the strap that is low: pins joined, one ground symbol
        pts = [P(p_) for p_ in gp]
        for px, py in pts: s.wire(px, py, px + 2.54, py)
        s.wire(pts[0][0] + 2.54, pts[0][1], pts[0][0] + 2.54, pts[-1][1] + 2.54)
        s.gnd(pts[0][0] + 2.54, pts[-1][1] + 2.54); L.use(u, *gp)
    # I2C to the charger and EEPROM with its pull-ups on one rail: SCL leaves first, SDA continues past its pull-up
    ys_, yd_, yi_ = P("I2Cc_SCL")[1], P("I2Cc_SDA")[1], P("~{I2Cc_IRQ}")[1]
    x1 = snap(xR + 30.48); x2 = snap(x1 + 15.24); x3 = snap(x2 + 15.24)
    yrail = snap(ys_ - 11.43)
    rails = L.netat(u, "LDO_3V3")
    for pin, ref, xx in (("I2Cc_SCL", r("R", 3), x1), ("I2Cc_SDA", r("R", 2), x2), ("~{I2Cc_IRQ}", r("R", 4), x3)):
        px, py = P(pin)
        s.wire(px, py, snap(xx + 5.08), py); L.lab(L.netat(u, pin), snap(xx + 5.08), py, "R")
        p = L.v(ref, xx, snap(yrail + 3.81), top=rails)
        s.wire(xx, p.b[1], xx, py)
        L.use(u, pin)
    s.wire(x1, yrail, x3, yrail)
    s.wire(x1, yrail, snap(x1 - 3.81), yrail); L.lab(rails, snap(x1 - 3.81), yrail, "L")
    for pin in ("I2Ct_SCL", "I2Ct_SDA", "~{I2Ct_IRQ}"):
        L.stub(u, pin, n=10.16)
    L.use(u, "I2Ct_SCL", "I2Ct_SDA", "~{I2Ct_IRQ}")
    L.finish(u, n=2.54)
    L.finish(j, n=2.54)
    L.note("C%d and the TVS D%d sit at the connector; C%d at the PD controller's VBUS pins.\n"
           "ADCIN1 is strapped to LDO_3V3 or ground: it sets this port's I2C target\naddress, so the two ports differ.\n"
           "R%d and R%d pull up the PD controller's own I2C bus (EEPROM, charger);\nthe MCU side (SCL, SDA, IRQ_N) leaves by labels." % (X.n + 6, X.n + 1, X.n + 50, X.n + 2, X.n + 3), x0, snap(esd.pin("VPWR")[1] + 20.0))
    return u


# ====================================================================================================== EEPROM
def eeprom_group(L, X, x0, y0):
    """24LC512 holding the PD controller's configuration, on the controller's second I2C bus."""
    s, r, N = L.s, X.r, X.net
    gm = {"_custom": {"pins": {"SCL": (-10.16, 2.54, 0), "SDA": (-10.16, 0, 0), "A0": (10.16, 2.54, 180), "A1": (10.16, 0, 180),
                               "A2": (10.16, -2.54, 180), "WP": (10.16, -5.08, 180), "GND": (0, -10.16, 90)},
                      "rect": (-7.62, -7.62, 7.62, 5.08)}}
    u = L.ic(r("U", 2), x0, y0, gaps=gm, text=((x0 + 4.0, y0 - 4.5, "r"), (x0 + 4.0, y0 - 2.4, "r")))
    for pin in ("SCL", "SDA"):
        px, py = u.pin(pin)
        s.wire(px, py, px - 6.35, py); L.lab(L.netat(u, pin), px - 6.35, py, "L")
        L.use(u, pin)
    pts = [u.pin(p) for p in ("A0", "A1", "A2", "WP")]
    xb = pts[0][0] + 5.08
    for px, py in pts: s.wire(px, py, xb, py)
    s.wire(xb, pts[0][1], xb, pts[-1][1] + 2.54); s.gnd(xb, pts[-1][1] + 2.54)
    L.use(u, "A0", "A1", "A2", "WP")
    L.stub(u, "GND", n=2.54); L.use(u, "GND")
    vx, vy = u.pin("VCC"); net = L.netat(u, "VCC")
    xc = snap(xb + 10.16)
    s.path((vx, vy), (vx, vy - 5.08), (xc, vy - 5.08))
    L.lab(net, vx, vy - 5.08, "L") if False else None
    L.drop(r("C", 8), xc, vy - 5.08, net)
    s.label(L.short(net), vx - 2.54, vy - 5.08, 180, net in L.glob)
    s.wire(vx - 2.54, vy - 5.08, vx, vy - 5.08)
    L.use(u, "VCC")
    return u


# ====================================================================================================== charger
def charger_group(L, X, x0, y0):
    s, r, N = L.s, X.r, X.net
    gaps = {"L": {"ACP": 20.32, "ACN": 22.86, "ACUV": 22.86, "ACOV": 15.24, "SCL": 17.78, "SDA": 5.08, "~{INT}": 5.08,
                  "~{CE}": 12.7, "FSW_SYNC": 15.24, "ICHG": 5.08, "ILIM_HIZ": 5.08, "TS": 20.32},
            "R": {"BTST1": 5.08, "SW1": 12.7, "LODRV1": 5.08, "HIDRV2": 20.32, "BTST2": 5.08, "SW2": 12.7, "LODRV2": 5.08,
                  "SRP": 15.24, "SRN": 25.4, "FB": 20.32, "FBG": 15.24, "REGN": 12.7, "DRV_SUP": 20.32, "NC": 10.16, "PGND": 5.08}}
    xl0 = snap(x0 + 70.0)
    u = L.ic(r("U", 3), xl0, y0, at_pin="VAC", gaps=gaps, text="above")
    P = u.pin
    xl = P("VAC")[0]; xr = P("HIDRV1")[0]
    net = lambda pin: L.netat(u, pin)

    # ---------------------------------------------------------------- left: input side
    yv = P("VAC")[1]
    s.wire(xl, yv, xl - 25.4, yv); L.lab(net("VAC"), xl - 25.4, yv, "L")
    L.drop(r("C", 9), snap(xl - 10.16), yv, net("VAC"), side="L")
    L.use(u, "VAC")
    # input current sense filter: ACP and ACN, each through 10R from the shunt, caps to ground and across
    ya, yn = P("ACP")[1], P("ACN")[1]
    xc, xh, xrr = snap(xl - 8.89), snap(xl - 24.13), snap(xl - 38.1)
    for y, ref_r, cap_g, lab in ((ya, r("R", 25), r("C", 15), N("PPHV")), (yn, r("R", 26), r("C", 16), N("AC_SNS_N"))):
        pin = "ACP" if y == ya else "ACN"
        rr = L.h(ref_r, xrr, y, left=lab, txt="ab")
        s.wire(xl, y, rr.r[0], y)
        s.wire(rr.l[0], y, snap(rr.l[0] - 3.81), y); L.lab(lab, snap(rr.l[0] - 3.81), y, "L")
        L.drop(cap_g, xh, y, L.netat(u, pin))
        L.use(u, pin)
    c414 = L.v(r("C", 14), xc, snap((ya + yn) / 2), top=net("ACP"), side="L")
    s.wire(xc, ya, xc, c414.t[1]); s.wire(xc, c414.b[1], xc, yn)
    # input window divider on ACUV / ACOV: PPHV - R409 - ACUV - R410 - ACOV - R411 - GND
    yu, yo = P("ACUV")[1], P("ACOV")[1]
    xch = snap(xl - 24.13)
    s.wire(xl, yu, xch, yu); s.wire(xl, yo, xch, yo)
    r409 = L.v(r("R", 9), xch, snap(yu - 3.81), top=N("PPHV"))
    s.label(L.short(N("PPHV")), xch, r409.t[1], 180, False)
    r410 = L.v(r("R", 10), xch, snap((yu + yo) / 2), top=net("ACUV"))
    s.wire(xch, yu, xch, r410.t[1]); s.wire(xch, r410.b[1], xch, yo)
    L.drop(r("R", 11), xch, yo, net("ACOV"))
    L.use(u, "ACUV", "ACOV")
    # I2C and interrupt by label
    for pin in ("SCL", "SDA", "~{INT}"):
        px, py = P(pin)
        s.wire(px, py, px - 7.62, py); L.lab(net(pin), px - 7.62, py, "L")
        L.use(u, pin)
    for pin in ("~{STAT1}", "~{STAT2}", "~{PG}"):
        s.nc(*P(pin)); L.use(u, pin)
    # charge enable: pulled up by R417, MCU can force it high through R435
    yc = P("~{CE}")[1]
    xce = snap(xl - 12.7)
    r435 = L.h(r("R", 35), snap(xl - 26.67), yc, left=N("CHG_INH") if False else L.netat(L.placed[r("R", 35)] if r("R", 35) in L.placed else u, "") if False else None, txt="bb") if False else None
    e35 = L.ends(r("R", 35))
    inh = [n for n in e35 if n != net("~{CE}")][0]
    r435 = L.h(r("R", 35), snap(xl - 26.67), yc, left=inh, txt="bb")
    s.wire(xl, yc, r435.r[0], yc)
    s.wire(r435.l[0], yc, snap(r435.l[0] - 3.81), yc); L.lab(inh, snap(r435.l[0] - 3.81), yc, "L")
    L.pull(r("R", 17), xce, yc, "3V3", side="L")
    L.use(u, "~{CE}")
    # frequency, charge current and input current limit programming resistors: a staircase of three hangs
    for pin, ref, dx in (("FSW_SYNC", r("R", 12), 48.26), ("ICHG", r("R", 13), 33.02), ("ILIM_HIZ", r("R", 14), 17.78)):
        px, py = P(pin)
        s.wire(px, py, snap(px - dx), py)
        L.drop(ref, snap(px - dx), py, net(pin))
        L.use(u, pin)
    # thermistor network on TS
    yt = P("TS")[1]
    xr416, xth, xr415 = snap(xl - 12.7), snap(xl - 36.83), snap(xl - 58.42)
    ts = net("TS")
    reg = [n for n in L.ends(r("R", 15)) if n != ts][0]
    r415 = L.h(r("R", 15), xr415, yt, left=reg, txt="ab")
    s.wire(xl, yt, r415.r[0], yt)
    s.wire(r415.l[0], yt, snap(r415.l[0] - 3.81), yt); L.lab(reg, snap(r415.l[0] - 3.81), yt, "L")
    L.drop(r("R", 16), xr416, yt, ts, side="L")
    L.drop(r("TH", 1), xth, yt, ts, side="L")
    L.use(u, "TS")

    # ---------------------------------------------------------------- right: switch drivers
    def drive(hi, lo_ref, gate_net_name, rref):
        px, py = P(hi); dn = net(hi)
        g = [n for n in L.ends(rref) if n != dn][0]
        rr = L.h(rref, snap(px + 10.16), py, left=dn, txt="ab")
        s.wire(px, py, rr.l[0], py)
        s.wire(rr.r[0], py, snap(px + 22.86), py); L.lab(g, snap(px + 22.86), py, "R")
        L.use(u, hi)
    for k, (hi, bt, sw, lo, rh, rl) in enumerate((("HIDRV1", "BTST1", "SW1", "LODRV1", 44, 45), ("HIDRV2", "BTST2", "SW2", "LODRV2", 46, 47))):
        drive(hi, None, None, r("R", rh))
        drive(lo, None, None, r("R", rl))
        yb, ysw = P(bt)[1], P(sw)[1]
        xcb, xd = snap(xr + 10.16), snap(xr + 38.1)
        s.wire(xr, yb, xd, yb)
        capref, dref = (r("C", 12), r("D", 4)) if k == 0 else (r("C", 13), r("D", 5))
        cb = L.v(capref, xcb, snap((yb + ysw) / 2), top=net(bt))
        s.wire(xcb, yb, xcb, cb.t[1]); s.wire(xcb, cb.b[1], xcb, ysw)
        s.wire(xr, ysw, snap(xr + 22.86), ysw); L.lab(net(sw), snap(xr + 22.86), ysw, "R")
        ds = net("REGN") if False else N("DRV_SUP")
        dd = L.v(dref, xd, snap(yb - 3.81), top=ds)
        s.wire(xd, dd.b[1], xd, yb)
        s.label(L.short(ds), xd, dd.t[1], 0, False)
        L.use(u, bt, sw)
    # output current sense filter: SRP and SRN
    ya, yn = P("SRP")[1], P("SRN")[1]
    xc, xh, xrr = snap(xr + 10.16), snap(xr + 26.67), snap(xr + 41.91)
    for y, ref_r, cap_g, pin in ((ya, r("R", 28), r("C", 18), "SRP"), (yn, r("R", 29), r("C", 19), "SRN")):
        far = [n for n in L.ends(ref_r) if n != net(pin)][0]
        rr = L.h(ref_r, xrr, y, left=net(pin), txt="ab")
        s.wire(xr, y, rr.l[0], y)
        s.wire(rr.r[0], y, snap(rr.r[0] + 3.81), y); L.lab(far, snap(rr.r[0] + 3.81), y, "R")
        L.drop(cap_g, xh, y, net(pin))
        L.use(u, pin)
    c417 = L.v(r("C", 17), xc, snap((ya + yn) / 2), top=net("SRP"))
    s.wire(xc, ya, xc, c417.t[1]); s.wire(xc, c417.b[1], xc, yn)
    # battery voltage divider FB / FBG
    yf, yg = P("FB")[1], P("FBG")[1]
    xd = snap(xr + 10.16)
    s.wire(xr, yf, xd, yf)
    L.pull(r("R", 18), xd, yf, "PACK_P")
    r419 = L.v(r("R", 19), xd, snap((yf + yg) / 2), top=net("FB"))
    s.wire(xd, yf, xd, r419.t[1]); s.path(P("FBG"), (xd, yg), (xd, r419.b[1]))
    L.use(u, "FB", "FBG")
    # REGN and DRV_SUP: capacitor each, REGN feeds DRV_SUP through D410, the 9 V rail through D411
    yr, ydv = P("REGN")[1], P("DRV_SUP")[1]
    s.wire(xr, yr, snap(xr + 5.08), yr)
    s.path((snap(xr + 5.08), yr), (snap(xr + 5.08), yr - 3.81)); L.lab(net("REGN"), snap(xr + 5.08), yr - 3.81, "R")
    xcr = snap(xr + 12.7)
    s.wire(xr, yr, xcr, yr)
    L.drop(r("C", 10), xcr, yr, net("REGN"))
    d410 = L.h(r("D", 10), snap(xr + 36.83), yr, left=net("REGN"), txt="ab")
    s.wire(xcr, yr, d410.l[0], yr)
    xv = snap(xr + 46.99)
    s.path(d410.r, (xv, yr), (xv, ydv))
    s.wire(xr, ydv, xv, ydv)
    L.drop(r("C", 11), xcr, ydv, net("DRV_SUP"))
    n9 = [n for n in L.ends(r("D", 11)) if n != net("DRV_SUP")][0]
    d411 = L.h(r("D", 11), snap(xr + 58.42), ydv, left=net("DRV_SUP"), txt="ab")
    s.wire(xv, ydv, d411.l[0], ydv)
    s.wire(d411.r[0], ydv, snap(d411.r[0] + 3.81), ydv); L.lab(n9, snap(d411.r[0] + 3.81), ydv, "R")
    s.path((snap(xr + 5.08), ydv), (snap(xr + 5.08), ydv - 3.81)); L.lab(net("DRV_SUP"), snap(xr + 5.08), ydv - 3.81, "R")
    L.use(u, "REGN", "DRV_SUP")
    s.nc(*P("NC")); L.use(u, "NC")
    L.gdrop(u, "PGND")
    L.finish(u)
    L.note("Set by the parts here: input window about 4.1 to 22.5 V (R%d, R%d, R%d on ACUV/ACOV);\n"
           "input current limit 5.5 A (R%d on ILIM_HIZ, shunt R%d); charge current 4.2 A (R%d on ICHG, shunt R%d);\n"
           "switching frequency 500 kHz (R%d); battery regulation 16.8 V (R%d / R%d on FB).\n"
           "R%d to R%d are 0R gate resistors, tuning positions. Each sense input is a Kelvin pair with a 10R + 0.47u filter."
           % (X.n + 9, X.n + 10, X.n + 11, X.n + 14, X.n + 24, X.n + 13, X.n + 27, X.n + 12, X.n + 18, X.n + 19, X.n + 44, X.n + 47),
           xl - 66.0, P("PGND")[1] + 12.0)
    return u


# ====================================================================================================== power stage
def _fets():
    """SiZ240DT drawn as two real MOSFETs: unit 1 high side (drain up, source = SW down), unit 2 low side (SW up, source down)."""
    return {"_custom": {"pins": {"G1": (-5.08, 0, 0), "D1": (2.54, 5.08, 270), "SW#1": (2.54, -5.08, 90),
                                 "G2": (-5.08, 0, 0), "SW#2": (2.54, 5.08, 270), "S2": (2.54, -5.08, 90)},
                         "gfx": ("Transistor_FET", "Q_NMOS_GSD")}}


def half_bridge(L, ref, x, ytop, hg, lg):
    """High and low FET of one SiZ240DT in a column; the drain pin end is at (x + 2.54, ytop). Returns the SW node point."""
    s = L.s
    g = _fets()
    y1 = snap(ytop + 5.08); y2 = snap(y1 + 20.32)
    tx = dict(ref_at=(x + 6.5, y1 - 1.3, "l"), val_at=(x + 6.5, y1 + 1.3, "l"))
    ty = dict(ref_at=(x + 6.5, y2 - 1.3, "l"), val_at=(x + 6.5, y2 + 1.3, "l"))
    h = L._sym(ref, x, y1, 0, unit=1, gaps=g, **tx)
    l = L._sym(ref, x, y2, 0, unit=2, gaps=g, **ty)
    xp = x + 2.54
    s.wire(xp, y1 + 5.08, xp, y2 - 5.08)
    s.wire(x - 5.08, y1, x - 10.16, y1); L.lab(hg, x - 10.16, y1, "L")
    s.wire(x - 5.08, y2, x - 10.16, y2); L.lab(lg, x - 10.16, y2, "L")
    s.gnd(xp, y2 + 5.08)
    return (xp, snap((y1 + y2) / 2)), h, l


def power_group(L, X, x0, y0):
    s, r, N = L.s, X.r, X.net
    yb = snap(y0 + 8.0)
    r424 = L.h(r("R", 24), snap(x0 + 10.16), yb, left=N("PPHV"), txt="ab")
    s.wire(r424.l[0], yb, snap(r424.l[0] - 3.81), yb); L.lab(N("PPHV"), snap(r424.l[0] - 3.81), yb, "L")
    xb0 = r424.r[0]
    caps = [r("C", k) for k in (30, 20, 23, 24, 27, 21, 56)]
    xmax, _ = L.ladder(caps, xb0, yb, N("AC_SNS_N"), 4, row_h=24.13, lead=8.89)
    xq = snap(xmax + 15.0)
    s.wire(xb0, yb, xq + 2.54, yb)
    s.path((snap(xb0 + 3.81), yb), (snap(xb0 + 3.81), yb - 3.81)); L.lab(N("AC_SNS_N"), snap(xb0 + 3.81), yb - 3.81, "R")
    sw1, h1, l1 = half_bridge(L, r("Q", 1), xq, yb, N("HG1"), N("LG1"))
    xq2 = snap(xq + 40.64)
    sw2, h2, l2 = half_bridge(L, r("Q", 2), xq2, yb, N("HG2"), N("LG2"))
    ind = L.h(r("L", 1), snap((sw1[0] + sw2[0]) / 2), sw1[1], left=N("SW1"), txt="ab")
    s.wire(sw1[0], sw1[1], ind.l[0], sw1[1]); s.wire(ind.r[0], sw2[1], sw2[0], sw2[1])
    for (px, py), nm in ((sw1, "SW1"), (sw2, "SW2")):
        xx = px + (8.0 if nm == "SW1" else -8.0)
        s.wire(xx, py, xx, py - 2.54); s.label(nm, xx, py - 2.54, 0, False)
    # output bus
    caps2 = [r("C", k) for k in (38, 31, 34)]
    s.wire(xq2 + 2.54, yb, xq2 + 2.54, yb)
    xs, xe = L.hang_row(caps2, xq2 + 2.54, yb, N("BAT_SNS_P"), lead=15.24)
    s.path((snap(xq2 + 2.54 + 5.08), yb), (snap(xq2 + 2.54 + 5.08), yb - 3.81)); L.lab(N("BAT_SNS_P"), snap(xq2 + 2.54 + 5.08), yb - 3.81, "R")
    L.note("Hot loops: C%d, C%d, C%d (and C%d) close the input loop to Q%d; C%d, C%d, C%d the output loop to Q%d.\n"
           "The 0R gate resistors R%d to R%d are in the charger group." % (X.n + 30, X.n + 20, X.n + 23, X.n + 24, X.n + 1, X.n + 38, X.n + 31, X.n + 34, X.n + 2, X.n + 44, X.n + 47),
           xq - 66.0, yb + 46.0)
    r427 = L.h(r("R", 27), snap(xs[-1] + 24.13), yb, left=N("BAT_SNS_P"), txt="ab")
    s.wire(xs[-1], yb, r427.l[0], yb)
    s.wire(r427.r[0], yb, snap(r427.r[0] + 3.81), yb); L.lab("PACK_P", snap(r427.r[0] + 3.81), yb, "R")


# ====================================================================================================== 9 V gate-drive supply
def v9_group(L, X, x0, y0):
    s, r, N = L.s, X.r, X.net
    u = L.ic(r("U", 6), snap(x0 + 44.0), snap(y0 + 14.0), text="above",
             gaps={"L": {"EN": 25.4}, "R": {"FB": 17.78}})
    P = u.pin
    # input: PACK_P with its capacitor
    pin_ = P("IN"); xa = snap(pin_[0] - 25.4)
    s.rail("PACK_P", xa, pin_[1], "+12V"); s.wire(xa, pin_[1], pin_[0], pin_[1])
    L.drop(r("C", 57), snap(pin_[0] - 10.16), pin_[1], L.netat(u, "IN"), side="L")
    L.use(u, "IN")
    # enable: pulled up from REGN, pulled low by Q409 which the PD controller drives
    pe = P("EN"); xe = snap(pe[0] - 22.86)
    s.wire(pe[0], pe[1], xe, pe[1])
    ren = L.pull(r("R", 54), xe, pe[1], L.netat(u, "EN") and [n for n in L.ends(r("R", 54)) if n != L.netat(u, "EN")][0], side="R")
    q = L._sym(r("Q", 9), snap(xe - 2.54), snap(pe[1] + 5.08), 0, ref_at=(snap(xe + 5.0), pe[1] + 5.08 - 1.3, "l"), val_at=(snap(xe + 5.0), pe[1] + 5.08 + 1.3, "l"))
    s.wire(*q.pin("D"), *q.pin("D"))
    s.gnd(*q.pin("S"))
    gx, gy = q.pin("G"); xg = snap(gx - 10.16)
    s.wire(gx, gy, xg - 7.62, gy)
    gate = L.netat(q, "G")
    L.lab(gate, xg - 7.62, gy, "L")
    L.pull(r("R", 55), xg, gy, [n for n in L.ends(r("R", 55)) if n != gate][0], side="L")
    L.use(u, "EN")
    # output with the feedback divider
    po, pf = P("OUT"), P("FB")
    xch = snap(po[0] + 12.7)
    s.wire(po[0], po[1], snap(xch + 40.0), po[1]); L.lab(L.netat(u, "OUT"), snap(xch + 40.0), po[1], "R")
    r452 = L.v(r("R", 52), xch, snap((po[1] + pf[1]) / 2), top=L.netat(u, "OUT"))
    s.wire(xch, po[1], xch, r452.t[1])
    s.path(pf, (xch, pf[1]), (xch, r452.b[1]))
    L.drop(r("R", 53), xch, pf[1], L.netat(u, "FB"))
    L.drop(r("C", 58), snap(xch + 22.86), po[1], L.netat(u, "OUT"))
    L.use(u, "OUT", "FB")
    L.finish(u)
    L.note("Output about 9.6 V from R%d / R%d on FB. Q%d, driven by the PD controller (DRV9_OFF),\n"
           "pulls EN low and turns the supply off; R%d holds DRV9_OFF high until the PD controller\n"
           "releases it. D%d lets this rail take over DRV_SUP from REGN." % (X.n + 52, X.n + 53, X.n + 9, X.n + 55, X.n + 11),
           snap(x0 + 2.0), snap(y0 + 62.0))
    return u


# ====================================================================================================== 5 V buck
def buck_group(L, X, x0, y0):
    s, r, N = L.s, X.r, X.net
    u = L.ic(r("U", 4), snap(x0 + 58.0), snap(y0 + 14.0), text="above",
             gaps={"L": {"EN": 20.32, "SS": 20.32, "RT": 20.32}, "R": {"SW": 12.7, "FB": 15.24}})
    P = u.pin
    # PACK_P in with its capacitors
    pv = P("VIN"); xa = snap(pv[0] - 38.1)
    s.rail("PACK_P", xa, pv[1], "+12V"); s.wire(xa, pv[1], pv[0], pv[1])
    L.drop(r("C", 46), snap(pv[0] - 10.16), pv[1], L.netat(u, "VIN"), side="L")
    L.drop(r("C", 44), snap(pv[0] - 25.4), pv[1], L.netat(u, "VIN"), side="L")
    L.use(u, "VIN")
    # enable pulled down, soft-start capacitor, RT to ground
    pe = P("EN"); xe = snap(pe[0] - 10.16)
    s.wire(pe[0], pe[1], snap(xe - 12.7), pe[1]); L.lab(L.netat(u, "EN"), snap(xe - 12.7), pe[1], "L")
    L.drop(r("R", 32), xe, pe[1], L.netat(u, "EN"), side="L")
    L.use(u, "EN")
    ps = P("SS")
    s.wire(ps[0], ps[1], xe, ps[1]); L.drop(r("C", 39), xe, ps[1], L.netat(u, "SS"), side="L")
    L.use(u, "SS")
    L.gdrop(u, "RT")
    # switch node, bootstrap capacitor, inductor, output capacitors and feedback divider
    pb, psw, pf = P("BST"), P("SW"), P("FB")
    xcb = snap(pb[0] + 7.62)
    s.wire(pb[0], pb[1], xcb, pb[1])
    c440 = L.v(r("C", 40), xcb, snap((pb[1] + psw[1]) / 2), top=L.netat(u, "BST"))
    s.wire(xcb, pb[1], xcb, c440.t[1]); s.wire(xcb, c440.b[1], xcb, psw[1])
    ind = L.h(r("L", 2), snap(pb[0] + 26.67), psw[1], left=L.netat(u, "SW"), txt="ab")
    s.wire(psw[0], psw[1], ind.l[0], psw[1])
    pp5 = N("PP5V")
    xp = snap(ind.r[0] + 7.62)
    s.wire(ind.r[0], psw[1], xp, psw[1])
    r433 = L.v(r("R", 33), xp, snap((psw[1] + pf[1]) / 2), top=pp5)
    s.wire(xp, psw[1], xp, r433.t[1])
    s.path(pf, (xp, pf[1]), (xp, r433.b[1]))
    L.drop(r("R", 34), xp, pf[1], L.netat(u, "FB"))
    xs, xe_ = L.hang_row([r("C", 41), r("C", 42), r("C", 43)], xp, psw[1], pp5, lead=22.86)
    s.wire(xs[-1], psw[1], snap(xs[-1] + 10.16), psw[1]); L.lab(pp5, snap(xs[-1] + 10.16), psw[1], "R")
    L.use(u, "BST", "SW", "FB")
    # the board ground test point hangs off the buck's ground
    gx, gy = L.stub(u, "GND", n=2.54); L.use(u, "GND")
    s.wire(gx, gy, snap(gx + 7.62), gy)
    L.pad(r("TP", 12), snap(gx + 7.62), gy, "R")
    L.finish(u)
    L.note("R%d / R%d on FB set PP5V to about 5.15 V; it powers the PD controller.\nEN_5V comes from the MCU; R%d keeps it off when undriven." % (X.n + 33, X.n + 34, X.n + 32),
           snap(x0 + 82.0), snap(y0 + 56.0))
    return u
