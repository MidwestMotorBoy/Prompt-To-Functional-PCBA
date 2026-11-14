"""MCU sheet: CC2340R5 module with its supply, reset, antenna match and pull-ups, and the debug connectors."""
from lay import *

G1 = "CC2340R5MODA Bluetooth LE module: supply, reset, antenna match, I2C and interrupt pull-ups"
G2 = "Debug and gauge-training connectors"


def scene(L):
    L.title("MCU", 20.32, 22.86, 3.0)
    L.pack([(G1, module), (G2, connectors)], top=32.0)


def module(L, X0, Y0):
    s = L.s
    u = L.ic("U301", X0 + 71.12, Y0 + 38.1, text="above",
             gaps={"L": {"RSTN": 17.78, "ANT_IN": 10.16, "RFIO": 17.78, "DIO16/SWDIO": 10.16, "DIO17/SWDCK": 5.08, "GND": 7.62},
                   "R": {"DIO8": 12.7, "DIO18": 10.16, "DIO20_A11": 5.08, "DIO12": 5.08, "DIO24_A7": 7.62, "DIO3_X32P": 5.08,
                         "DIO4_X32N": 5.08, "DIO21_A10": 10.16, "DIO11": 15.24}})
    P = u.pin
    # ---- supply: 3V3 rail from the left, three capacitors and the test point on it, then the pin
    xv, yv = P("VDDS")
    xa = snap(xv - 63.5)
    s.rail("3V3", xa, yv, "+3V3")
    xs, xe = L.hang_row(["C301", "C302", "C303"], xa + 7.62, yv, "3V3")
    L.pad("TP301", xe, yv, "D")
    s.wire(xa, yv, xv, yv)
    s.wire(xe, yv, xe, yv)
    L.use(u, "VDDS")
    # ---- reset: pull-up from the rail, filter capacitor to ground; NRST goes on by label
    xr, yr = P("RSTN")
    xp = snap(xr - 19.05)
    s.wire(xr, yr, xp - 6.35, yr)
    L.pull("R302", xp, yr, "3V3")
    L.drop("C304", xp - 6.35 - 0.0 + 12.7 - 12.7, yr, "NRST") if False else None
    xc = snap(xp - 12.7)
    L.drop("C304", xc, yr, "NRST")
    s.label("NRST", xp - 19.05 + 0, yr, 180, False) if False else None
    s.wire(xc - 7.62, yr, xr, yr)
    s.label("NRST", xc - 7.62, yr, 180, False)
    L.use(u, "RSTN")
    # ---- antenna match: RFIO -> C313 -> node (C314 to ground) -> R321 -> ANT_IN node (C315 to ground)
    xa, ya = P("ANT_IN"); xf, yf = P("RFIO")
    mid, ant = "Net-(C313-Pad2)", "ANT_IN"
    xm = snap(xf - 17.78)
    c313 = L.h("C313", snap(xm + 3.81), yf, left=mid, txt="aa")
    s.wire(xf, yf, c313.r[0], yf)
    L.drop("C314", xm, yf, mid, side="L")
    s.wire(xm, yf, xm, ya)
    r321 = L.h("R321", snap(xm + 8.89), ya, left=mid, txt="aa")
    s.wire(xm, ya, r321.l[0], ya)
    s.wire(r321.r[0], ya, xa, ya)
    L.drop("C315", r321.r[0], ya, ant, side="L")
    L.use(u, "ANT_IN", "RFIO")
    L.note("Antenna pi match: C314, R321\nand C315 are tuning positions;\nretune on this board.", X0 + 4, ya + 3.0)
    # ---- debug lines and ground on the left
    for nm in ("DIO16/SWDIO", "DIO17/SWDCK"):
        L.stub(u, nm, n=7.62)
    L.stub(u, "GND", n=5.08)
    L.use(u, "DIO16/SWDIO", "DIO17/SWDCK", "GND")
    # ---- right side: I2C pull-ups on one rail (SCL leaves first, SDA runs on past its pull-up), then the others
    xo = P("DIO6_A1")[0]
    ys, yd = P("DIO6_A1")[1], P("DIO8")[1]
    x1 = snap(xo + 10.16); x2 = snap(x1 + 15.24)
    yrail = snap(ys - 10.16)
    r304 = L.v("R304", x1, snap(yrail + 3.81), top="3V3")
    r305 = L.v("R305", x2, snap(yrail + 3.81), top="3V3")
    s.wire(xo, ys, snap(x1 + 5.08), ys); L.lab(L.netat(u, "DIO6_A1"), snap(x1 + 5.08), ys, "R")
    s.wire(x1, r304.b[1], x1, ys)
    s.wire(xo, yd, snap(x2 + 5.08), yd); L.lab(L.netat(u, "DIO8"), snap(x2 + 5.08), yd, "R")
    s.wire(x2, r305.b[1], x2, yd)
    s.wire(x1, yrail, x2, yrail); s.rail("3V3", x1, yrail, "+3V3")
    L.use(u, "DIO6_A1", "DIO8")
    x3 = snap(xo + 25.4)
    L.out_pull(u, "DIO21_A10", x3, "R313", "3V3", 7.62)
    L.out_pull(u, "DIO11", x3, "R314", "3V3", 7.62)
    L.note("R313 keeps the 3V3 buck out of sleep while the MCU is in reset or blank.\nR314 is the one pull-up of the shared open-drain IRQ_N line.\nLeaving by label: SCL, SDA, IRQ_N (gauge, PD controllers),\nCHG_INH and EN_5V1/2 (USB ports), 3V3_SLEEP (3V3 Rail).",
           xo + 3.0, P("DIO11")[1] + 3.5)
    L.finish(u)
    return u


def connectors(L, X0, Y0):
    s = L.s
    xj = X0 + 20.32
    # ---- debug and gauge-training connectors, wired to the module by labels
    L.note("Tag-Connect pads, no part fitted", xj - 12.7, Y0 + 12.7)
    j1 = L.ic("J301", xj, Y0 + 34.29, text=((xj - 2.54, Y0 + 41.0, "r"), (xj - 2.54, Y0 + 43.5, "r")))
    L.stub(j1, "VCC", n=3.81); L.stub(j1, "GND", n=3.81); L.use(j1, "VCC", "GND")
    L.finish(j1)
    xj2 = snap(xj + 5.08)
    j2 = L.ic("J302", xj2 + 12.7, Y0 + 69.85, text=((xj2 + 28, Y0 + 76, "l"), (xj2 + 28, Y0 + 78.5, "l")))
    L.finish(j2)
