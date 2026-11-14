"""Cells and Gauge sheet, section 2: BQ40Z50 gauge with the cell input ladder, its supply feeds and its interface."""
from sch import Port, snap
import patterns as P


def cell_ladder(S, u, px, uy):
    """Cell sense wires J116/J111/J110/J109 and J115 at the left, each cell node through its 100R to its VC pin, the 0.1u
    capacitors standing between adjacent filtered nodes. The VC lines fan out to 7.62 mm rows with jogs that never cross."""
    rows = {"VC4": uy - 8.89, "VC3": uy - 1.27, "VC2": uy + 6.35, "VC1": uy + 13.97}
    xj = {"VC4": px - 40.64, "VC3": px - 35.56, "VC2": px - 30.48, "VC1": px - 25.4}
    xcap = snap(px - 50.8)
    xr = snap(xcap - 12.7)
    xpad = snap(xr - 3.81 - 15.24)
    r0 = uy + 21.59
    cells = {"VC4": ("CELL_4P", "R104", "J116"), "VC3": ("CELL3", "R103", "J111"),
             "VC2": ("CELL2", "R102", "J110"), "VC1": ("CELL1", "R101", "J109")}
    for vc, (cell, rref, jref) in cells.items():
        pt, yr = u.p(vc), rows[vc]
        r = S.two(rref, xr, yr, "h", first=cell)
        S.wire([pt, (xj[vc], pt.y), (xj[vc], yr), r.r], vc)
        S.place(jref, xpad, yr)
        S.wire([(xpad, yr), r.l], cell)
        S.label(cell, Port(xpad + 3.81, yr), "R")
    ys = [rows["VC4"], rows["VC3"], rows["VC2"], rows["VC1"], r0]
    nets = ["VC4", "VC3", "VC2", "VC1"]
    for i, cref in enumerate(("C101", "C102", "C103", "C104")):
        S.two(cref, xcap, (ys[i] + ys[i + 1]) / 2, "v", first=nets[i])
    S.place("J115", xpad, r0)
    S.wire([(xpad, r0), (xcap + 12.7, r0)], "CELL_1N")
    S.gnd(Port(xcap + 12.7, r0), "D", "CELL_1N")


def supply_feeds(S, u, px, uy):
    """BAT through D101 and R105 from CELL_4P, VCC through R106 from FET_MID, PBI capacitor: the three lines leave the pins
    upward, the top one farthest, and end in their own rows 7.62 mm apart."""
    bat, vcc, pbi = u.p("BAT"), u.p("VCC"), u.p("PBI")
    xa, xb, xc = snap(px - 7.62), snap(px - 12.7), snap(px - 17.78)
    yb, yv, yp = uy - 46.99, uy - 39.37, uy - 31.75
    S.wire([bat, (xa, bat.y), (xa, yb)], "GAUGE_BAT")
    r105 = S.two("R105", snap(xa - 8.89), yb, "h", first="BAT_D")
    S.wire([(xa, yb), r105.r], "GAUGE_BAT")
    d101 = S.two("D101", snap(xa - 21.59), yb, "h", first="CELL_4P")
    S.wire([d101.r, r105.l], "BAT_D")
    S.wire([d101.l, d101.l.to(-2.54, 0)], "CELL_4P"); S.label("CELL_4P", d101.l.to(-2.54, 0), "L")
    S.wire([vcc, (xb, vcc.y), (xb, yv)], "GAUGE_VCC")
    r106 = S.two("R106", snap(xb - 8.89), yv, "h", first="FET_MID")
    S.wire([(xb, yv), r106.r], "GAUGE_VCC")
    S.wire([r106.l, r106.l.to(-2.54, 0)], "FET_MID"); S.label("FET_MID", r106.l.to(-2.54, 0), "L")
    S.wire([pbi, (xc, pbi.y), (xc, yp), (xc - 7.62, yp)], "PBI")
    c105 = P.hang(S, "C105", xc - 7.62, yp, "PBI", to=None)
    S.gnd(c105.bt, "D", "CELL_1N")


def left_pins(S, u, px):
    """Pins that only need a short stub: sense inputs, PACK through R113, the thermistor lines, the tied-off pins."""
    for nm in ("SRP", "SRN", "TS1", "TS2", "TS3", "TS4"): S.pin_label(u.p(nm), "L", 2.54)
    pk = u.p("PACK")
    r113 = S.two("R113", snap(px - 6.35), pk.y, "h", first="PACK_P")
    S.wire([pk, r113.r], "GAUGE_PACK")
    S.pin_label(r113.l, "L", 2.54)
    for nm in ("PTCEN", "PTC"): S.pin_gnd(u.p(nm), 7.62, "CELL_1N")


def right_pins(S, u, rp):
    """CHG, DSG and FUSE leave as labels; SMBC/SMBD through staggered 100R to SCL/SDA; BTP_INT drives Q103."""
    for nm in ("CHG", "DSG", "FUSE"): S.pin_label(u.p(nm), "R", 2.54)
    for nm in ("PCHG", "LEDCNTLA", "LEDCNTLB", "LEDCNTLC", "NC"): S.nc(u.p(nm))
    smbc, smbd = u.p("SMBC"), u.p("SMBD")
    r115 = S.two("R115", snap(rp + 10.16), smbc.y, "h", first="SMBC")
    S.wire([smbc, r115.l], "SMBC"); S.pin_label(r115.r, "R", 2.54)
    r116 = S.two("R116", snap(rp + 33.02), smbd.y, "h", first="SMBD")
    S.wire([smbd, r116.l], "SMBD"); S.pin_label(r116.r, "R", 2.54)
    ends = P.tie(S, [u.p("PRES/SHUTDN"), u.p("DISP")], "CELL_1N", reach=5.08)
    S.gnd(Port(ends[0].x, max(e.y for e in ends)), "D", "CELL_1N")
    S.pin_gnd(u.p("VSS"), 5.08, "CELL_1N")
    bt = u.p("BTP_INT")
    xq = snap(rp + 55.88)
    q3 = S.place("Q103", xq, bt.y)
    S.wire([bt, q3.p("G")], "BTP_INT")
    r117 = P.hang(S, "R117", xq - 12.7, bt.y, "BTP_INT", to=None)
    S.gnd(r117.bt, "D", "CELL_1N")
    S.pin_label(q3.p("D"), "R", 2.54)
    S.gnd(q3.p("S"))


def gauge(S, x, y):
    sec = S.begin("BQ40Z50 gauge: cell inputs, supply and interface", x, y,
                  note="Each cell tap reaches its VC pin through 100R and a 0.1u capacitor to the next tap; the gauge's ground is the cell-1 Kelvin tap CELL_1N")
    ox, oy = sec.ox, sec.oy
    px = snap(ox + 100)
    ux, uy = snap(px + 12.7), snap(oy + 58)
    u = S.place("U101", ux, uy)
    cell_ladder(S, u, px, uy)
    supply_feeds(S, u, px, uy)
    left_pins(S, u, px)
    right_pins(S, u, ux + 12.7)
    S.end(sec)
    return sec
