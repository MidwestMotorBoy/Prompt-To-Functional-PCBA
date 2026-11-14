"""MCU: the CC2340R5 module with its supply, reset and RF match on the left, the open-drain lines with their pull-ups on the
right, and the two Tag-Connect headers."""
import symlib

MOD = ("MonolithDev", "CC2340R5MODA")
sn = lambda v: round(v / 1.27) * 1.27


def draw(h):
    h.text(20.32, 21, "MCU", 3.0)
    symlib.respace(*MOD, {"VDDS": 48.26, "RSTN": 33.02, "RFIO": 12.7, "ANT_IN": 0, "DIO16/SWDIO": -12.7, "DIO17/SWDCK": -17.78,
                          "GND": -27.94,
                          "DIO6_A1": 40.64, "DIO8": 27.94, "DIO18": 17.78, "DIO20_A11": 12.7, "DIO12": 5.08, "DIO24_A7": 0,
                          "DIO3_X32P": -5.08, "DIO4_X32N": -10.16, "DIO21_A10": -22.86, "DIO11": -35.56})
    with h.group("CC2340R5 module: supply, reset, RF match, I/O"):
        module(h, 142.24, 96.52)
        h.note(28, 118, ["Reset: R302 pulls RSTN up, C304 gives a", "power-on delay; both headers share NRST.",
                         "RF: C313 / R321 / C314 / C315 is a pi match", "to the on-module antenna feed; C314 stays",
                         "unfitted until tuned.",
                         "SCL, SDA, IRQ_N, 3V3_SLEEP idle high through", "the pull-ups on the right."], 1.27)
    with h.group("Debug and gauge connectors (Tag-Connect)"):
        headers(h, 235.0, 62.23)


def module(h, ox, oy):
    u = h.ic("U301", ox, oy, fields="above")
    P = u.p
    xp = P("VDDS")[0]
    yv = P("VDDS")[1]
    # ---- supply rail: pin, rail, decoupling at the pin, reset pull-up, test point
    cols = [sn(xp - 15.24 - 15.24 * k) for k in range(5)]
    xl = sn(cols[-1] - 10.16)
    h.w(P("VDDS"), (xl, yv)); h.lab(xl, yv, "3V3", "L")
    r302 = h.two("R302", cols[0], yv + 3.81, "v", first="3V3")
    h.w((cols[0], yv), r302.a)
    yn = P("RSTN")[1]
    h.w(r302.b, (cols[0], yn))
    for c, x in zip(("C301", "C302", "C303"), cols[1:4]):
        h.hang(yv, x, c, "3V3")
    h.w((cols[4], yv), (cols[4], yv + 2.54)); h.one("TP301", cols[4], yv + 2.54, "U", txt="l")
    # ---- reset line: pull-up in, power-on-reset capacitor, label to the headers
    xr = sn(cols[1])
    h.w(P("RSTN"), (xr, yn))
    c304 = h.two("C304", xr, yn + 3.81, "v", first="NRST")
    h.w((xr, yn), c304.a); h.gnd(*c304.b)
    h.w((xr, yn), (xr - 12.7, yn)); h.lab(xr - 12.7, yn, "NRST", "L")
    # ---- antenna match: RFIO - C313 - node - R321 - ANT_IN, shunt capacitors at the node and at ANT_IN
    xm = sn(xp - 17.78)
    e1, (c313,), _ = h.lane(P("RFIO"), "L", ["C313"], "RFIO", gap=10.16, end="none")
    e2, (r321,), _ = h.lane(P("ANT_IN"), "L", ["R321"], "ANT_IN", gap=10.16, end="none")
    ym = sn((P("RFIO")[1] + P("ANT_IN")[1]) / 2)
    h.w(e1, (e1[0], P("ANT_IN")[1]), e2)
    xc = sn(e1[0] - 7.62)
    h.w((e1[0], ym), (xc, ym))
    c314 = h.two("C314", xc, ym + 3.81, "v", first="ANT_MID", txt="l")
    h.w((xc, ym), c314.a); h.gnd(*c314.b)
    xa = sn(xp - 3.81)
    c315 = h.two("C315", xa, P("ANT_IN")[1] + 3.81, "v", first="ANT_IN", txt="l")
    h.w((xa, P("ANT_IN")[1]), c315.a); h.gnd(*c315.b)
    h.lab(e1[0], ym - 0.0, "ANT_MID", "R") if False else None
    # ---- debug and ground
    h.stub(P("DIO16/SWDIO"), "L", "SWDIO", 5.08)
    h.stub(P("DIO17/SWDCK"), "L", "SWCLK", 5.08)
    h.tie(P("GND"), "GND", "L")
    # ---- right: lines out, pull-ups up to 3V3
    xr0 = P("DIO6_A1")[0]
    for pin, net, pu in (("DIO6_A1", "SCL", "R304"), ("DIO8", "SDA", "R305"), ("DIO21_A10", "3V3_SLEEP", "R313"), ("DIO11", "IRQ_N", "R314")):
        pos = P(pin)
        x = sn(pos[0] + 10.16)
        h.w(pos, (sn(pos[0] + 20.32), pos[1]))
        h.lab(sn(pos[0] + 20.32), pos[1], net, "R")
        r = h.two(pu, x, pos[1] - 3.81, "v", first="3V3")
        h.w(r.b, (x, pos[1]))
        h.w(r.a, (x, r.a[1] - 2.54)); h.lab(x, r.a[1] - 2.54, "3V3", "R")
    for pin, net in (("DIO18", "UART_TX"), ("DIO24_A7", "CHG_INH"), ("DIO3_X32P", "EN_5V1"), ("DIO4_X32N", "EN_5V2")):
        h.stub(P(pin), "R", net, 20.32 if pin != "DIO18" else 7.62)


def headers(h, x0, y0):
    j1 = h.ic("J301", x0, y0, fields="left")
    vcc = j1.p("VCC"); h.w(vcc, (vcc[0], vcc[1] - 5.08)); h.lab(vcc[0], vcc[1] - 5.08, "3V3", "R")
    h.tie(j1.p("GND"), "GND", "D")
    for pin, net in (("SWDIO", "SWDIO"), ("~{RESET}", "NRST"), ("SWCLK", "SWCLK"), ("SWO", "UART_TX")):
        h.stub(j1.p(pin), "R", net, 5.08)
    j2 = h.ic("J302", x0 + 5.08, y0 + 50.8, angle=180, fields="above")
    for pin, net in (("SDA", "SDA"), ("CHG_INH", "CHG_INH"), ("NRST", "NRST"), ("SCL", "SCL")):
        h.stub(j2.p(pin), "R", net, 5.08)
    h.nc(*j2.p("NC"))
    h.tie(j2.p("GND"), "GND", "R")
