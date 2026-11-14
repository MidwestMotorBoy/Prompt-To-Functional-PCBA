"""3V3 Rail sheet: TPS62177 buck, drawn as the textbook step-down converter."""
from lay import *


def scene(L):
    L.title("3V3 Rail", 20.32, 22.86, 3.0)
    L.pack([("Pack-rail bulk capacitors", bulk), ("TPS62177 3.3 V always-on buck, fed straight from the pack", buck)])


def bulk(L, ox, oy):
    s = L.s
    yr = snap(oy + 22.86)                                           # the input rail
    x1 = snap(ox + 4)
    s.rail("PACK_P", x1, yr, "+12V")
    xs, xe = L.hang_row([f"C{208 + i}" for i in range(6)], x1, yr, "PACK_P", lead=8.89)
    L.note("Shared with both USB ports, on the pack rail\nahead of the converter.", x1 + 4, yr + 23.0)


def buck(L, ox, oy):
    s = L.s
    yr = snap(oy + 22.86)
    xa = snap(ox)
    s.rail("PACK_P", xa, yr, "+12V")
    xu = snap(xa + 38.1)
    u = L.ic("U204", xu, yr, at_pin="VIN")
    vin, en, slp, pg = u.pin("VIN"), u.pin("EN"), u.pin("~{SLEEP}"), u.pin("PG")
    sw, vos, fb = u.pin("SW"), u.pin("VOS"), u.pin("FB")
    L.hang_row(["C206"], snap(vin[0] - 15.24), yr, "PACK_P")
    s.wire(xa, yr, vin[0], yr)
    s.wire(en[0], en[1], en[0] - 2.54, en[1]); s.wire(en[0] - 2.54, en[1], en[0] - 2.54, yr)     # EN tied to VIN: always on
    L.stub(u, "~{SLEEP}", n=5.08); L.stub(u, "PG")
    L.use(u, "VIN", "EN", "~{SLEEP}", "PG")
    # bottom pins: all ground, one symbol
    pins = [u.pin(k) for k in ("NC", "PAD", "PGND", "AGND")]
    yb = pins[0][1] + 2.54
    for px, py in pins: s.wire(px, py, px, yb)
    s.wire(pins[0][0], yb, pins[-1][0], yb); s.gnd(u.pin("PGND")[0], yb)
    L.use(u, "NC", "PAD", "PGND", "AGND")
    # --- switch node, inductor, output
    L_x = snap(sw[0] + 15.24)
    ind = L.h("L201", L_x, sw[1], left="SW_3V3", txt="aa")
    s.wire(sw[0], sw[1], ind.l[0], ind.l[1])
    s.label("SW_3V3", sw[0] + 2.54, sw[1], 0, False)
    xo = snap(ind.r[0] + 5.08)
    c207x = snap(xo + 7.62)
    xend = snap(c207x + 15.24)
    s.wire(ind.r[0], ind.r[1], xend, ind.r[1])
    L.hang_row(["C207"], c207x, ind.r[1], "3V3")
    s.rail("3V3", xend, ind.r[1], "+3V3")
    # VOS senses the output at the inductor; FB grounded (fixed-output part)
    s.wire(vos[0], vos[1], xo, vos[1]); s.wire(xo, vos[1], xo, ind.r[1])
    s.wire(fb[0], fb[1], fb[0] + 2.54, fb[1]); s.gnd(fb[0] + 2.54, fb[1], 0)
    L.use(u, "SW", "VOS", "FB")
    L.finish(u)
    L.note("U204 is the fixed 3.3 V part: VOS senses the output, FB goes to ground (datasheet).\n"
           "EN is tied to VIN, so the rail is always on; SLEEP low (MCU) puts the converter in sleep mode.\n"
           "C206 sits right at VIN. The 3V3 output feeds the MCU and\nthe VIN_3V3 pin of each PD controller.", xa, yb + 8.0)
