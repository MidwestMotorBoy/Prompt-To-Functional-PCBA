"""MCU sheet: the CC2340R5 module with its supply, reset and pull-ups, the antenna match and the two connectors."""
from layouts import layout
from sch import Port, snap
import patterns as P


def pullup(S, ref, x, yline, rail="3V3"):
    """Resistor standing on a signal line at (x, yline) with its own supply arrow on top."""
    r = S.two(ref, x, yline - 3.81, "v", first=rail)
    S.rail(rail, r.a)
    return r


@layout("mcu")
def mcu(S, p):
    X0, Y0 = 20.32, 30.48
    # ------------------------------------------------------------------ module, supply, reset, pull-ups
    sec = S.begin("CC2340R5MODA module", X0, Y0,
                  note="Supply and reset network; I2C, IRQ_N, charge inhibit, 5 V enables and SLEEP go to the other sheets")
    x0 = sec.ox                                             # left end of the 3V3 rail
    yR = snap(sec.oy + 4.5)
    xv = snap(x0 + 69.85)                                    # riser from the rail down to VDDS
    ux, uy = snap(xv + 21.59), snap(yR + 33)
    u = S.place("U301", ux, uy)
    vdds, rstn, ant, rfio = u.p("6"), u.p("RSTN"), u.p("ANT_IN"), u.p("RFIO")
    swdio, swclk, gnd = u.p("DIO16/SWDIO"), u.p("DIO17/SWDCK"), u.p("1")
    # ---- 3V3 rail comes in from the left, decoupling hangs from it, smallest capacitor nearest the pin
    S.rail("3V3", Port(x0, yR))
    S.wire([(x0, yR), (xv, yR), (xv, vdds.y), vdds], "3V3")
    S.place("TP301", x0 + 9, yR)
    for ref, dx in (("C301", 22), ("C303", 38), ("C302", 54)):
        t = S.two(ref, x0 + dx, yR + 3.81, "v", first="3V3")
        S.gnd(t.bt)
    # ---- reset: NRST line with the pull-up above and the power-on-reset capacitor below
    xr = snap(ux - 36)
    xe = snap(xr - 8)
    S.wire([rstn, (xe, rstn.y)], "NRST")
    pullup(S, "R302", xr, rstn.y)
    c304 = S.two("C304", xr, rstn.y + 3.81, "v", first="NRST")
    S.gnd(c304.bt)
    S.label("NRST", Port(xe, rstn.y), "L")
    # ---- RF pins, SWD pins and ground on the left
    for pin in (ant, rfio, swdio, swclk): S.pin_label(pin, "L", 2.54)
    S.pin_gnd(gnd, 2.54)
    # ---- right side: GPIO lines with their pull-ups staggered along the lines
    px = u.p("DIO6_A1").x
    for ref, nm, dx in (("R304", "DIO6_A1", 6.35), ("R305", "DIO8", 19.05), ("R313", "DIO21_A10", 19.05), ("R314", "DIO11", 41.91)):
        pin = u.p(nm)
        xp = snap(px + dx)
        pullup(S, ref, xp, pin.y)
        S.wire([pin, (xp + 3.81, pin.y)], pin.net)
        S.label(pin.net, Port(xp + 3.81, pin.y), "R")
    for nm in ("DIO18", "DIO24_A7", "DIO3_X32P", "DIO4_X32N"):
        S.pin_label(u.p(nm), "R", 2.54)
    for nm in ("DIO20_A11", "DIO12"): S.nc(u.p(nm))
    S.end(sec)
    b1 = S.section_box(sec)

    # ------------------------------------------------------------------ antenna match: RFIO - C313 - R321 - ANT_IN
    sec2 = S.begin("Antenna match", X0, b1[3] + 7, note="Pi network between RFIO and ANT_IN")
    ya = snap(sec2.oy + 9)
    xa = sec2.ox + 6.35
    S.label("RFIO", Port(xa, ya), "L")
    c313 = S.two("C313", xa + 17.78, ya, "h", first="RFIO")
    S.wire([Port(xa, ya), c313.l], "RFIO")
    xm = snap(c313.r.x + 7.62)
    S.wire([c313.r, (xm, ya)], "RF_MID")
    c314 = S.two("C314", xm, ya + 3.81, "v", first="RF_MID")
    S.gnd(c314.bt)
    r321 = S.two("R321", xm + 7.62 + 3.81, ya, "h", first="RF_MID")
    S.wire([(xm, ya), r321.l], "RF_MID")
    xn = snap(r321.r.x + 7.62)
    S.wire([r321.r, (xn + 7.62, ya)], "ANT_IN")
    c315 = S.two("C315", xn, ya + 3.81, "v", first="ANT_IN")
    S.gnd(c315.bt)
    S.label("ANT_IN", Port(xn + 7.62, ya), "R")
    S.end(sec2)
    b2 = S.section_box(sec2)

    # ------------------------------------------------------------------ notes (top right) and connectors under them
    sec.max_x0 = sec2.max_x0 = min(b1[0], b2[0])             # one left edge for the module and the antenna match
    notes = S.ctx.cons.get("notes", {}).get("MCU", [])
    k = len(notes) - 1                                       # the last note is about the antenna match and stands beside it
    xr_ = b1[2] + 8
    yn = P.notes_block(S, xr_, b1[1] + 1, notes[:k], width=78)
    sec3, b3 = P.fit(S, lambda T, x, y: connectors(T, x, y), xr_ - 1.0, yn + 7)
    xa_ = b2[2] + 10
    P.notes_block(S, xa_, b2[1] + 1, notes[k:], width=59.0, title="Notes, continued", first=k + 1)
    S.finish()


def connectors(S, x, y):
    sec3 = S.begin("Debug and gauge-training connectors", x, y, note="Tag-Connect pads, no part fitted")
    j301 = S.place("J301", sec3.ox + 12, sec3.oy + 14)
    for nm in ("~{RESET}", "SWCLK", "SWDIO", "SWO"): S.pin_label(j301.p(nm), "R", 2.54)
    vcc = j301.p("VCC")
    S.wire([vcc, vcc.out(2.54)], "3V3"); S.rail("3V3", vcc.out(2.54))
    S.pin_gnd(j301.p("GND"), 2.54)
    j302 = S.place("J302", sec3.ox + 50, sec3.oy + 14)
    for nm in ("SDA", "CHG_INH", "NRST", "SCL"): S.pin_label(j302.p(nm), "L", 2.54)
    S.nc(j302.p("NC"))
    S.pin_gnd(j302.p("GND"), 2.54)
    S.end(sec3)
    return sec3
