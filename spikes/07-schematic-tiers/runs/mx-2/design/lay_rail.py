"""3V3 Rail sheet: the TPS62177 buck drawn as a power path, the shared pack-rail bulk capacitors as their own bank."""
from layouts import layout
from sch import Port, snap
import patterns as P


@layout("rail_3v3")
def rail_3v3(S, p):
    X0, Y0 = 20.32, 30.48
    # ---------------------------------------------------------------- buck
    sec = S.begin("TPS62177 3.3 V always-on buck", X0, Y0,
                  note="PACK_P (12 to 16.8 V) in, 3V3 (0.5 A) out. Always enabled; the MCU can put it to sleep through SLEEP")
    ry = snap(sec.oy + 6)                                   # row of VIN and SW
    u = S.place("U204", snap(sec.ox + 62), ry + 7.62)
    vin, en, sl, pg = u.p("VIN"), u.p("EN"), u.p("~{SLEEP}"), u.p("PG")
    sw, vos, fb = u.p("SW"), u.p("VOS"), u.p("FB")
    x_in = snap(sec.ox)
    S.rail("PACK_P", Port(x_in, ry))
    c206 = S.two("C206", vin.x - 27.94, ry + 3.81, "v", first="PACK_P")
    S.wire([(x_in, ry), vin])
    S.gnd(c206.bt)
    S.link(en, Port(en.x - 2.54, ry), "hv")                 # EN tied to VIN: always on
    S.pin_label(sl, "L", 5.08)
    S.nc(pg)
    yb = u.p("PGND").y
    S.wire([u.p("NC"), u.p("AGND")], "GND")
    S.gnd(Port(u.p("PGND").x - 1.27, yb))
    l201 = S.two("L201", sw.x + 17.78, ry, "h", first="SW_3V3")
    S.wire([sw, l201.l])
    S.label("SW_3V3", Port(sw.x + 2.54, ry), "R")
    xn = snap(l201.r.x + 7.62)
    S.wire([l201.r, (xn, ry)])
    S.wire([vos, (xn, vos.y), (xn, ry)])
    c207 = S.two("C207", xn + 12.7, ry + 3.81, "v", first="3V3")
    xe = snap(xn + 30.48)
    S.wire([(xn, ry), (xe, ry)], "3V3")
    S.gnd(c207.bt)
    S.rail("3V3", Port(xe, ry))
    S.wire([fb, (fb.x + 2.54, fb.y)], "GND"); S.gnd(Port(fb.x + 2.54, fb.y))
    S.end(sec)
    b1 = S.section_box(sec)
    # ---------------------------------------------------------------- shared bulk
    sec2 = S.begin("PACK_P bulk capacitance", X0, b1[3] + 7, note="Shared by both chargers and both 5 V bucks")
    ry2 = snap(sec2.oy + 6)
    S.rail("PACK_P", Port(sec2.ox, ry2))
    caps, xend = P.bank(S, sec2.ox + 15.24, ry2, [f"C{208 + i}" for i in range(6)], "PACK_P")
    S.wire([(sec2.ox, ry2), (sec2.ox + 15.24, ry2)], "PACK_P")
    S.end(sec2)
    b2 = S.section_box(sec2)
    # ---------------------------------------------------------------- notes
    notes = S.ctx.cons.get("notes", {}).get("3V3 Rail", [])
    P.notes_block(S, b1[2] + 8, b1[1] + 1, notes, width=80)
    S.finish()
