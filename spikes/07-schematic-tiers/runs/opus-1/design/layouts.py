"""Layout scripts: how each block's sheet is drawn, as a person would draw it.

Each function receives a sheetkit.Kit for one block. It places the parts (coordinates in grid units of 2.54 mm,
origin top left of the page) and draws the wires it means. Every pin it leaves open is finished by the kit (ground,
rail symbol, no-connect or net label), so a script only states what a reader should see as wires.
Connectivity is never decided here: make.sh proves the drawn sheets equal the code's netlist.
"""
U = 2.54
CW = 1.05          # mm per character, as in sheetkit


def u(v): return round(v * U, 4)


# ------------------------------------------------------------------ reusable drawing patterns
def hang(k, ref, x, y_rail, net, drop=1.0, end=None, fields="right"):
    """A two-pad part hanging from a horizontal wire at y_rail (grid units), the pad on `net` up. The far pad goes to
    ground or gets its label (end overrides the far net's drawing: 'gnd', 'label', None = auto)."""
    p = k.two(ref, u(x), u(y_rail + drop + 1.5), first=net, fields=fields)
    k.w((u(x), u(y_rail)), p.a)
    return p


def bank(k, refs, x0, y, net, dx=5, gnd=True):
    """Parts in a row hanging from one wire at y, from x0 to the right. Returns (parts, x of last)."""
    ps = []
    for i, r in enumerate(refs):
        ps.append(hang(k, r, x0 + i * dx, y, net))
    k.w((u(x0), u(y)), (u(x0 + (len(refs) - 1) * dx), u(y)))
    return ps, x0 + (len(refs) - 1) * dx


def series_h(k, ref, x, y, left_net, fields="above"):
    """A two-pad part lying on a wire, centred at grid (x, y)."""
    return k.two(ref, u(x), u(y), first=left_net, horiz=True, fields=fields)


def title(k, s, x, y):
    k.title(s, u(x), u(y))


def notes(k, items, x, y, width=95, head="NOTES"):
    k.text(head, u(x), u(y), 1.5, bold=True)
    yy = u(y) + 3.2
    for i, s in enumerate(items):
        yy = k.note(f"{i + 1}. {s}", u(x), yy, width) + 0.8
    return yy


def part_notes(k, refs):
    """The Notes field of each part, as numbered notes: the reasons stay next to the drawing."""
    out = []
    for r in refs:
        n = k.comps[r]["fields"].get("Notes")
        if n: out.append(f"{r}: {n}")
    return out



def fanout(k, part, side, targets, first=1.0):
    """Spread pins of one side of an IC onto rows of their own: targets = [(pin, row in grid units)], top to bottom.
    Each pin runs out, turns at its own column, and lands on its row; the turns are ordered so no two cross.
    Returns ({pin key: (x mm, y mm) where the row starts}, x mm of the row starts)."""
    sg = -1 if side == "L" else 1
    pins = [(part[key], key, row) for key, row in targets]
    px = pins[0][0].x
    ups = sorted([e for e in pins if u(e[2]) < e[0].y - 0.01], key=lambda e: e[0].y)
    dns = sorted([e for e in pins if u(e[2]) > e[0].y + 0.01], key=lambda e: -e[0].y)
    col = {}
    for i, e in enumerate(ups): col[e[1]] = i
    for i, e in enumerate(dns): col[e[1]] = i
    ncol = max([0] + [c + 1 for c in col.values()])
    xs = px + sg * u(first + ncol)
    out = {}
    for p, key, row in pins:
        if key in col:
            jx = px + sg * u(first + col[key])
            k.w(p, (jx, p.y), (jx, u(row)), (xs, u(row)))
        else:
            k.w(p, (xs, p.y))
        out[key] = (xs, u(row))
    return out, xs


def chain(k, start, net, refs, d="L", gap=2.0, fields="line"):
    """Two-pad parts in series on a horizontal wire from start (mm) in direction d, starting on `net`.
    Returns (end point mm, net at the end, list of parts)."""
    x, y = start
    sg = -1 if d == "L" else 1
    cur, parts = net, []
    for r in refs:
        e = [k.pinnet.get((r, p["num"])) for p in k.pins_of(r)]
        other = [n for n in e if n != cur][0]
        cx = x + sg * u(gap + 1.5)
        if d == "L":
            p = k.two(r, cx, y, first=other, horiz=True, fields=fields); near, far = p.b, p.a
        else:
            p = k.two(r, cx, y, first=cur, horiz=True, fields=fields); near, far = p.a, p.b
        k.w((x, y), near)
        x, cur = far.x, other
        parts.append(p)
    return (x, y), cur, parts


def vpart(k, ref, x, ya, yb, top_net, fields="right"):
    """A two-pad part standing between two rows (grid units), wired to both rows if it is shorter than the gap."""
    p = k.two(ref, u(x), u((ya + yb) / 2), first=top_net, fields=fields)
    k.w((u(x), u(ya)), p.a); k.w(p.b, (u(x), u(yb)))
    return p


# ------------------------------------------------------------------ 3V3 rail
def rail_3v3(k):
    k.sheet.paper = "A4"
    k.rails |= {"PACK_P", "3V3"}
    title(k, "3.3 V ALWAYS-ON RAIL  (TPS62177 buck from the pack, sleep mode under MCU control)", 8, 9)
    # power path: PACK_P -> C206 -> U204 -> L201 -> C207 -> 3V3, on one line
    U204 = k.place("U204", u(40), u(21))
    vin, en, sw, vos, fb = U204["VIN"], U204["EN"], U204["SW"], U204["VOS"], U204["FB"]
    yr = vin.y / U
    k.rail((u(16), vin.y), "PACK_P")
    k.w((u(16), vin.y), vin)
    hang(k, "C206", 26, yr, "PACK_P")
    k.w(en, (u(33), en.y), (u(33), vin.y))                    # EN tied to VIN: always on
    k.label(U204["~{SLEEP}"], "3V3_SLEEP", stub=0)
    k.nc(U204["PG"])
    bot = sorted((U204[n] for n in ("NC", "PAD", "PGND", "AGND")), key=lambda p: p.x)
    yb = bot[0].y + u(1)
    for p in bot: k.w(p, (p.x, yb))
    k.w((bot[0].x, yb), (bot[-1].x, yb))
    k.gnd((bot[2].x, yb))
    k.gnd(fb)                                                 # fixed-output part: FB to ground
    L = series_h(k, "L201", 52, yr, "SW_3V3")
    k.w(sw, L.a)
    k.label((sw.x + u(2), sw.y), "SW_3V3", "R")
    xo = 58
    k.w(L.b, (u(xo), sw.y))
    k.w(vos, (u(xo), vos.y), (u(xo), sw.y))                  # VOS senses the output after the inductor
    hang(k, "C207", 62, yr, "3V3")
    k.w((u(xo), sw.y), (u(70), sw.y))
    k.rail((u(70), sw.y), "3V3")

    title(k, "PACK_P BULK CAPACITANCE  (shared by both chargers and both 5 V bucks)", 8, 33)
    k.rail((u(10), u(40)), "PACK_P")
    k.w((u(10), u(40)), (u(14), u(40)))
    bank(k, [f"C{208 + i}" for i in range(6)], 14, 40, "PACK_P", dx=7)

    notes(k, [
        "PACK_P (12 to 16.8 V) -> TPS62177 -> 3V3, 0.5 A: the MCU and both TPS25751 PD controllers. Always on: EN is tied to VIN.",
        "Fixed 3.3 V version: FB to GND per datasheet, VOS senses the output after L201. NC pin to GND per datasheet. PG unused.",
        "3V3_SLEEP low = sleep mode, driven by the MCU (U301 DIO21). R313 on the MCU sheet holds it high while the MCU is in reset.",
        "C206 closes the input hot loop (VIN-PGND): place it at the pins. C208-C213 are the shared pack-rail bulk, placed between the two power stages.",
    ], 8, 52, width=150)



# ------------------------------------------------------------------ MCU
def pullup(k, ref, x, y_line, rail="3V3", gap=0.0, fields="right"):
    """A pull-up standing on its line at grid (x, y_line): rail symbol on top, junction on the line."""
    p = k.two(ref, u(x), u(y_line - 2.5 - gap), first=rail, fields=fields)
    k.w(p.b, (u(x), u(y_line)))
    k.rail(p.a, rail, "U")
    return p


def mcu(k):
    k.sheet.ox, k.sheet.oy = -u(18), -u(23)                         # the drawing below starts at x 26, y 31
    k.sheet.paper = "A4"
    k.rails |= {"3V3"}
    title(k, "CC2340R5 BLUETOOTH LE MODULE  (system I2C host, charger inhibit, 5 V enables, 3V3 sleep)", 23, 30)
    M = k.place("U301", u(70), u(50))
    P = M.p
    # supply: 3V3 rail across the top, decoupling hanging from it, into VDDS
    vdds = P("VDDS")
    k.rail((u(28), u(36)), "3V3")
    k.w((u(28), u(36)), (u(61), u(36)), (u(61), vdds.y), vdds)
    for x, r in ((45, "C301"), (50, "C302"), (55, "C303")): hang(k, r, x, 36, "3V3")
    tp = k.place("TP301", u(38), u(34), fields="right")
    k.w(tp.pins[0], (u(38), u(36)))
    # reset: pull-up from the rail, RC to ground, on to the debug connectors by label
    rst = P("RSTN")
    k.w(rst, (u(26), rst.y))
    r302 = k.two("R302", u(31), u(39), first="3V3")
    k.w(r302.a, (u(31), u(36)))
    k.w(r302.b, (u(31), rst.y))
    hang(k, "C304", 36, rst.y / U, "NRST")
    k.label((u(26), rst.y), "NRST", "L")
    # antenna match: RFIO -> C313 -> R321 -> ANT_IN, shunts C314 and C315, drawn as a pi network under the module
    ant, rf = P("ANT_IN"), P("RFIO")
    yp = 60
    k.w(rf, (u(58), rf.y), (u(58), u(yp)))
    k.w(ant, (u(44), ant.y), (u(44), u(yp)))
    c313 = series_h(k, "C313", 55, yp, "Net-(C313-Pad2)")
    k.w((u(58), u(yp)), c313.b)
    r321 = series_h(k, "R321", 48, yp, "ANT_IN")
    k.w(c313.a, r321.b)
    hang(k, "C314", 51.5, yp, "Net-(C313-Pad2)")
    k.w(r321.a, (u(44), u(yp)))
    hang(k, "C315", 44, yp, "ANT_IN")
    k.label((u(58), u(yp - 4)), "RFIO", "R")
    k.label((u(44), u(yp - 4)), "ANT_IN", "L")
    k.gnd(P("GND"))
    # right side: I2C with its pull-ups (SCL lifted to its own row so each pull-up stands clear of the others)
    scl, sda = P("DIO6_A1"), P("DIO8")
    xe = 98
    k.w(scl, (u(78), scl.y), (u(78), u(38)), (u(xe), u(38)))
    k.label((u(xe), u(38)), "SCL", "R")
    pullup(k, "R304", 84, 38)
    k.w(sda, (u(xe), sda.y)); k.label((u(xe), sda.y), "SDA", "R")
    pullup(k, "R305", 88, sda.y / U)
    for nm in ("DIO18", "DIO24_A7", "DIO3_X32P", "DIO4_X32N"):
        p = P(nm); k.w(p, (u(xe), p.y)); k.label((u(xe), p.y), p.net, "R")
    # 3V3_SLEEP and IRQ_N fan down to rows of their own with their pull-ups
    slp, irq = P("DIO21_A10"), P("DIO11")
    k.w(slp, (u(80), slp.y), (u(80), u(62)), (u(xe), u(62))); k.label((u(xe), u(62)), slp.net, "R")
    pullup(k, "R313", 88, 62)
    k.w(irq, (u(78), irq.y), (u(78), u(70)), (u(xe), u(70))); k.label((u(xe), u(70)), irq.net, "R")
    pullup(k, "R314", 92, 70)

    title(k, "DEBUG AND GAUGE-TRAINING CONNECTORS  (Tag-Connect TC2030 footprints, no part fitted)", 23, 77)
    k.place("J301", u(34), u(87), fields="top")
    k.place("J302", u(70), u(87), fields="top")
    k.text("J301: SWD for U301 (SWO = UART_TX)", u(26), u(97))
    k.text("J302: SMBus + CHG_INH + NRST for gauge training", u(58), u(97))

    nts = ["3V3 is the always-on rail from the 3V3 Rail sheet. C301 at VDDS, C302/C303 at the module supply pins.",
           "NRST: R302 + C304 = SWRS349A fig. 9-1 power-on reset; J301 and J302 can both pull it low.",
           "SCL/SDA pull-ups R304/R305 (3.3k) are the only ones on the system I2C bus (gauge via R115/R116, PD controllers)."]
    nts += part_notes(k, ["R313", "R314", "C314", "R321"])
    notes(k, nts, 104, 33, width=58)



# ------------------------------------------------------------------ cells and gauge
def cells_gauge(k):
    k.sheet.ox, k.sheet.oy = u(4), u(3)
    k.rails |= {"PACK_P"}
    k.grounds["CELL_1N"] = "GNDREF"
    k.alias.update({"Net-(U101-VCC)": "GAUGE_VCC", "Net-(F102-HTR)": "FUSE_HTR", "Net-(Q104-G)": "FUSE_GATE"})
    title(k, "4S PACK: BQ40Z50 GAUGE AND PROTECTION FETS, BQ2947 SECOND-LEVEL PROTECTOR AND CHEMICAL FUSE", 0, 3)

    # ---- power path along the top: PACK+ wire -> F102 -> CELL_P -> Q101 (CHG) -> FET_MID -> Q102 (DSG) -> PACK_P
    Yp = 16
    title(k, "PACK POWER PATH  (cells -> fuse -> back-to-back CHG/DSG FETs -> PACK_P)", 46, 7)
    j112 = k.place("J112", u(46), u(Yp), fields="left")
    F = k.place("F102", u(52), u(Yp), fields="above")
    k.w(j112.pins[0], F["1"])
    q1 = k.place("Q101", u(94), u(Yp + 3.5), angle=90, mirror=True, fields=(u(96), u(Yp + 3.3), u(96), u(Yp + 4.2)))
    q2 = k.place("Q102", u(104), u(Yp + 3.5), angle=90, fields=(u(106), u(Yp + 3.3), u(106), u(Yp + 4.2)))
    s1, d1, g1 = q1["S"], q1["D"], q1["G"]
    d2, s2, g2 = q2["D"], q2["S"], q2["G"]
    k.w(F["2"], (s1.x, u(Yp)), s1)
    k.w(d1, (d1.x, u(Yp)), (d2.x, u(Yp)), d2)
    k.label((u(97.5), u(Yp)), "FET_MID", "R")
    xe = 136
    k.w(s2, (s2.x, u(Yp)), (u(xe), u(Yp)))
    k.rail((u(xe), u(Yp)), "PACK_P")
    k.label((u(70), u(Yp)), "CELL_P", "R")
    # WAKE pull-up and test point hang from CELL_P
    r118 = hang(k, "R118", 62, Yp, "CELL_P")
    k.place("TP113", r118.b.x, r118.b.y, angle=180, fields="right")
    # ESD caps bridge the FET pair: CELL_P -> C110 -> C111 -> PACK_P
    yb = Yp - 4
    xb1, xb2 = 82, 108
    k.w((u(xb1), u(Yp)), (u(xb1), u(yb)))
    c110 = series_h(k, "C110", 90, yb, "CELL_P")
    c111 = series_h(k, "C111", 100, yb, "Net-(C110-Pad2)")
    k.w((u(xb1), u(yb)), c110.a); k.w(c110.b, c111.a); k.w(c111.b, (u(xb2), u(yb)), (u(xb2), u(Yp)))
    # gate networks under the FETs: 10M gate-source bleeders, 5.1k from the gauge drivers, DSG zener clamp
    yg = Yp + 9
    k.w(g1, (g1.x, u(yg)))
    vpart(k, "R110", 88, Yp, yg, "CELL_P")
    k.w((u(88), u(yg)), (g1.x, u(yg)))
    r109 = k.two("R109", g1.x, u(yg + 2.5), first="CHG_G")
    k.w((g1.x, u(yg)), r109.a)
    k.w(g2, (g2.x, u(yg)))
    vpart(k, "R112", 112, Yp, yg, "PACK_P")
    vpart(k, "D103", 117, Yp, yg, "PACK_P")
    k.w((g2.x, u(yg)), (u(117), u(yg)))
    r111 = k.two("R111", g2.x, u(yg + 2.5), first="DSG_G")
    k.w((g2.x, u(yg)), r111.a)
    k.label((u(89), u(yg)), "CHG_G", "D") if False else None
    # PACK_P output: snubber pair to ground, load wire, test point
    c107 = hang(k, "C107", 122, Yp, "PACK_P")
    k.two("C108", u(122), c107.b.y + u(1.5), first="PACK_CMID")
    k.place("J113", u(128), u(Yp), fields="right")
    k.place("TP106", u(132), u(Yp), angle=180, fields="right")

    # ---- gauge
    gx, gy = 82, 52
    title(k, "BQ40Z50 GAUGE", 58, 27.5)
    G = k.place("U101", u(gx), u(gy), fields=(u(gx - 4), u(gy - 11.2), u(gx + 0.5), u(gy - 11.2)))
    tg = [("BAT", 32), ("VCC", 33.5), ("PBI", 35.5), ("PTCEN", 37), ("VC4", 40), ("VC3", 43), ("VC2", 46), ("VC1", 49),
          ("SRP", 55.5), ("SRN", 58.5), ("PACK", 61), ("TS1", 63.5), ("TS2", 66), ("TS3", 68), ("TS4", 70.5), ("PTC", 73)]
    rows, xs = fanout(k, G, "L", tg)
    xs_u = xs / U
    (xe_, ye_), nb_, _ = chain(k, rows["BAT"], "Net-(U101-BAT)", ["R105"], gap=2)
    dn = [k.net("D101", p["num"]) for p in k.pins_of("D101")]
    cx = xe_ - u(3.5 + 1.5)
    d101 = k.two("D101", cx, ye_, first=[n for n in dn if n != nb_][0], horiz=True, fields="above")
    k.w(d101.b, (xe_, ye_))
    chain(k, rows["VCC"], "Net-(U101-VCC)", ["R106"])
    chain(k, rows["PBI"], "Net-(U101-PBI)", ["C105"])
    for key in ("PTCEN", "PTC"):
        k.w(rows[key], (rows[key][0] - u(1), rows[key][1])); k.gref((rows[key][0] - u(1), rows[key][1]), "CELL_1N")
    for key in ("TS2", "TS3"): k.label(rows[key], key, "L")
    xc = xs_u - 4.5
    for key in ("VC4", "VC3", "VC2", "VC1", "SRP", "SRN"):
        k.w(rows[key], (u(xc), rows[key][1]))
    vpart(k, "C101", xc, 40, 43, "Net-(U101-VC4)")
    vpart(k, "C102", xc, 43, 46, "Net-(U101-VC3)")
    vpart(k, "C103", xc, 46, 49, "Net-(U101-VC2)")
    c104 = hang(k, "C104", xc, 49, "Net-(U101-VC1)")
    k.gref(c104.b, "CELL_1N", side="right")                     # name beside it: the SRP row runs just below
    for key, r, n in (("VC4", "R104", "Net-(U101-VC4)"), ("VC3", "R103", "Net-(U101-VC3)"), ("VC2", "R102", "Net-(U101-VC2)"), ("VC1", "R101", "Net-(U101-VC1)")):
        chain(k, (u(xc), rows[key][1]), n, [r])
    # current sense: Kelvin RC filter, then the 1 mOhm shunt standing in the current path CELL_N -> GND
    ysp, ysn = 55.5, 58.5
    vpart(k, "C106", xc, ysp, ysn, "SRP")
    (xa, ya), _, _ = chain(k, (u(xc), u(ysp)), "SRP", ["R107"])
    (xb, yb2), _, _ = chain(k, (u(xc), u(ysn)), "SRN", ["R108"])
    xr = xc - 8
    vpart(k, "RS101", xr, ysp, ysn, "CELL_N", fields="left")
    k.w((xa, ya), (u(xr), ya), (u(xr - 4), ya))
    k.w((xb, yb2), (u(xr), yb2), (u(xr - 7), yb2))
    k.label((u(xr - 1), ya), "CELL_N", "R") if False else None
    k.place("J108", u(xr - 4), ya, fields="above")
    k.place("J114", u(xr - 2.5), yb2, angle=180, fields="right")
    k.place("TP109", u(xr - 5), yb2, angle=180, fields="left")
    k.gnd((u(xr - 7), yb2))
    chain(k, rows["PACK"], "Net-(U101-PACK)", ["R113"])
    chain(k, rows["TS1"], "TS1", ["TH101"])
    chain(k, rows["TS4"], "TS4", ["TH104"])
    # right side: gate drive up to the FETs, fuse drive, SMBus, interrupt
    k.w(G["CHG"], (g1.x, G["CHG"].y), r109.b)
    k.w(G["DSG"], (g2.x, G["DSG"].y), r111.b)
    chain(k, G["SMBC"].pt, "Net-(U101-SMBC)", ["R115"], d="R")
    chain(k, G["SMBD"].pt, "Net-(U101-SMBD)", ["R116"], d="R", gap=9)
    pr, dp = G["PRES/SHUTDN"], G["DISP"]
    k.w(pr, (pr.x + u(1), pr.y), (pr.x + u(1), dp.y), dp)
    k.w((pr.x + u(1), dp.y), (pr.x + u(3), dp.y))
    k.gref((pr.x + u(3), dp.y), "CELL_1N")
    bt = G["BTP_INT"]
    q103 = k.place("Q103", bt.x + u(24), bt.y, fields="right")
    k.w(bt, q103["G"])
    hang(k, "R117", bt.x / U + 19, bt.y / U, "BTP_INT")
    dq = q103["D"]
    k.w(dq, (dq.x, dq.y - u(1)), (dq.x + u(3), dq.y - u(1)))
    k.label((dq.x + u(3), dq.y - u(1)), "IRQ_N", "R")

    # ---- second-level protector and the fuse ignition FET under F102
    title(k, "SECOND-LEVEL PROTECTOR  (OVP -> Q104 blows F102)", 0, 9)
    gr = Yp + 11.5
    P = k.place("U102", u(30), u(gr - 4.5), fields="top")
    q104 = k.place("Q104", u(51), u(gr), fields="right")
    k.w(F["HTR"], q104["D"])
    xl = P["V4"].x / U - 6
    for key, r, n in (("V4", "R119", "Net-(U102-V4)"), ("V3", "R120", "Net-(U102-V3)"), ("V2", "R121", "Net-(U102-V2)"), ("V1", "R122", "Net-(U102-V1)")):
        k.w(P[key], (u(xl), P[key].y))
        chain(k, (u(xl), P[key].y), n, [r])
    vpart(k, "C112", xl, P["V4"].y / U, P["V3"].y / U, "Net-(U102-V4)")
    vpart(k, "C113", xl, P["V3"].y / U, P["V2"].y / U, "Net-(U102-V3)")
    vpart(k, "C114", xl, P["V2"].y / U, P["V1"].y / U, "Net-(U102-V2)")
    hang(k, "C115", xl, P["V1"].y / U, "Net-(U102-V1)")
    vdd, vss, cd, out = P["VDD"], P["VSS"], P["CD"], P["OUT"]
    xr2 = vdd.x / U
    k.w(vdd, (vdd.x + u(2), vdd.y))
    vpart(k, "C116", xr2 + 2, vdd.y / U, vss.y / U, "Net-(U102-VDD)")
    vpart(k, "C117", xr2 + 2, vss.y / U, cd.y / U, "CELL_1N")
    k.w(cd, (cd.x + u(2), cd.y))
    k.w(vss, (vss.x + u(9), vss.y))
    k.gref((vss.x + u(9), vss.y), "CELL_1N")
    chain(k, (vdd.x + u(2), vdd.y), "Net-(U102-VDD)", ["R123"], d="R")
    (xo, yo), _, _ = chain(k, out.pt, "Net-(U102-OUT)", ["R124"], d="R")
    qg = q104["G"]
    k.w((xo, yo), qg)
    hang(k, "R125", xo / U + 1.5, gr, "Net-(Q104-G)")
    hang(k, "C118", xo / U + 5.5, gr, "Net-(Q104-G)")
    r126 = k.two("R126", xo + u(9), u(gr - 2.5), first="GAUGE_FUSE")
    k.w(r126.b, (xo + u(9), u(gr)))

    # ---- pack wires: cell sense taps and NTC wires, solder pads
    title(k, "PACK WIRES  (solder pads: cell taps, Kelvin wires, NTCs)", 0, 43)
    y = 47
    for r in ("J116", "J111", "J110", "J109", "J115"):
        k.place(r, u(12), u(y), angle=90, fields="left")
        y += 3
    y = 47
    for r in ("J117", "J118", "J119", "J120"):
        k.place(r, u(34), u(y), mirror=True, fields="left")
        y += 3

    nts = ["CELL_1N (ground symbol with name) is the gauge and protector ground: the Kelvin wire at the cell-1 negative tab. "
           "It differs from GND only by the drop across RS101 and the pack wire.",
           "Cell inputs: 100R + 0.1u RC per cell into the gauge (VC1-VC4), 1k + 0.1u into the BQ2947 (V1-V4; RIN must be 1k).",
           "RS101 sits in the pack current path (CELL_N to GND); SRP/SRN are Kelvin taps filtered by R107/R108/C106.",
           "Q101 (CHG) and Q102 (DSG) are back to back, drains common at FET_MID. The gauge drives the gates 10.5-12 V above the pack.",
           "Fuse F102 is blown by Q104 when the BQ2947 OUT (OVP) or the gauge FUSE pin goes high.",
           "IRQ_N: the gauge BTP_INT drives Q103 onto the shared open-drain IRQ_N line (pull-up R314 on the MCU sheet)."]
    nts += part_notes(k, ["F102", "D103", "D101", "C110", "R117", "Q103", "Q104", "U102", "RS101", "C117", "TH101", "TH104"])
    notes(k, nts, 146, 6, width=80)



# ------------------------------------------------------------------ USB port
def kelvin_shunt(k, rs, rp, rn, cd, cp, cn, x, y, left_net, w=4.5, up=6):
    """A current-sense shunt lying in the power line at grid (x, y), with its Kelvin RC filter drawn above it:
    rp / rn rise from each end of the shunt, cd bridges their tops, cp / cn go from each top to ground.
    Returns (shunt part, left top point, right top point) - the filtered nodes, mm."""
    S = series_h(k, rs, x, y, left_net, fields="linebelow")
    xl, xr = x - w, x + w
    k.w((u(xl), u(y)), S.a); k.w(S.b, (u(xr), u(y)))
    ra = vpart(k, rp, xl, y - up, y, None or k.net(rp, "1") if k.net(rp, "1") != left_net else k.net(rp, "2"), fields="right")
    rb = vpart(k, rn, xr, y - up, y, [n for n in (k.net(rn, "1"), k.net(rn, "2")) if n not in (left_net,) and n != k.net(rs, "1") and n != k.net(rs, "2")][0], fields="left")
    yt = y - up
    c = series_h(k, cd, x, yt, k.net(rp, "2") if k.net(rp, "2") != left_net else k.net(rp, "1"))
    k.w((u(xl), u(yt)), c.a); k.w(c.b, (u(xr), u(yt)))
    k.w((u(xl), u(yt)), (u(xl - 5), u(yt))); k.w((u(xr), u(yt)), (u(xr + 3), u(yt)))
    hang(k, cp, xl - 5, yt, k.net(cp, "1"))
    hang(k, cn, xr + 3, yt, k.net(cn, "1"))
    return S, (u(xl - 5), u(yt)), (u(xr + 3), u(yt))


def usb_port(k):
    k.sheet.ox, k.sheet.oy = u(4), u(3)
    n = int([r for r in k.refs if r.startswith("J")][0][1:]) - 1      # 400 or 500
    r = lambda i: str(n + i)
    port = k.block
    pn = port.split()[-1]
    N = lambda s: f"{port}/{s}"
    ldo = f"/P{pn}_LDO_3V3"
    k.rails |= {"PACK_P", "3V3", ldo}
    title(k, f"{port.upper()}: USB-C PD SOURCE/SINK PORT  (TPS25751D PD controller, BQ25756 four-switch buck-boost charger)", 0, 3)

    # ================= band A: connector, CC protection, PD controller, EEPROM
    title(k, "USB-C CONNECTOR AND PROTECTION", 0, 6.5)
    yJ = 25
    J = k.place("J" + r(1), u(6), u(yJ), fields="top")
    vb = J["VBUS"]
    yv = 10                                                      # VBUS runs above the CC protection to the PD controller
    k.w(vb, (vb.x + u(2), vb.y), (vb.x + u(2), u(yv)))
    xv0 = vb.x / U + 2
    D = k.place("D" + r(1), u(19.5), u(yv + 4), fields="right")
    k.w((u(19.5), u(yv)), D["IN"])
    hang(k, "C" + r(6), 27.5, yv, N("VBUS"))
    hang(k, "C" + r(50), 33.5, yv, N("VBUS"))
    k.label((u(36), u(yv)), N("VBUS"), "R") if False else None
    # D+ shorted to D-: dedicated charging port
    dps = [J[p] for p in ("A7", "B7", "A6", "B6")]
    xd = dps[0].x + u(1)
    for p in dps: k.w(p, (xd, p.y))
    k.w((xd, dps[0].y), (xd, dps[-1].y))
    k.text("D+ = D-: BC1.2 DCP", xd + 1.5, dps[1].y + 1.6, 1.0)
    # TPD6S300 between the connector CC pins and the PD controller
    E = k.place("U" + r(5), u(36), u(yJ + 0.5), fields=(u(30), u(yJ + 9.6), u(30), u(yJ + 10.5)))
    k.w(J["CC1"], E["C_CC1"]); k.w(J["CC2"], E["C_CC2"])
    k.w((u(27.5), E["C_CC1"].y), (u(27.5), E["RPD_G1"].y), E["RPD_G1"])      # dead-battery Rd to its own CC pin
    k.w((u(26.5), E["C_CC2"].y), (u(26.5), E["RPD_G2"].y), E["RPD_G2"])
    vp, vbias = E["VPWR"], E["VBIAS"]
    yt = vp.y / U - 1.5
    k.w(vp, (vp.x, u(yt - 1.5))); k.rail((vp.x, u(yt - 1.5)), ldo)
    c452 = series_h(k, "C" + r(52), vp.x / U - 4.5, yt, "GND", fields="line")
    k.w((vp.x, u(yt)), c452.b)
    k.w(vbias, (vbias.x, u(yt)))
    c451 = series_h(k, "C" + r(51), vbias.x / U + 4.5, yt, N("VBIAS"), fields="line")
    k.w((vbias.x, u(yt)), c451.a)
    k.gnd(E["GND"]); k.w(E["GND"], (E["GND"].x, E["GND"].y + u(1)), (E["N.C."].x, E["GND"].y + u(1)), E["N.C."])

    title(k, "USB PD CONTROLLER TPS25751D", 44, 6.5)
    P = k.place("U" + r(1), u(60), u(yJ), fields=(u(61), u(yJ - 11.6), u(61), u(yJ - 10.7)))
    c403 = k.two("C" + r(3), u(57), u(yJ - 13.5), first="3V3")
    k.rail(c403.a, "3V3")
    vin, vbi, vbs = P["VBUS_IN"], P["VBUS"], P["VIN_3V3"]
    xvb = vin.x / U - 3.5
    k.w((u(xv0), u(yv)), (u(xvb), u(yv)), (u(xvb), vin.y), vin)
    k.w(vbi, (vin.x - u(1.5), vbi.y), (vin.x - u(1.5), vin.y))
    k.label((u(40), u(yv)), N("VBUS"), "R")
    # CC lines with their caps
    k.w(E["CC1"], P["CC1"]); k.w(E["CC2"], P["CC2"])
    xc1 = E["CC1"].x / U + 2
    k.w((u(xc1), E["CC1"].y), (u(xc1), E["CC1"].y - u(2.5)))
    c401 = series_h(k, "C" + r(1), xc1 + 3, E["CC1"].y / U - 2.5, N("CC1"), fields="line")
    k.w((u(xc1), E["CC1"].y - u(2.5)), c401.a)
    xc2, yc2 = xc1 + 1, E["CC2"].y / U + 2.5
    k.w((u(xc2), E["CC2"].y), (u(xc2), u(yc2)))
    c402 = series_h(k, "C" + r(2), xc2 + 3, yc2, N("CC2"), fields="line")
    k.w((u(xc2), u(yc2)), c402.a)
    # SBU fault from the TPD6S300 to GPIO3, with its pull-up
    flt, g3 = E["~{FLT}"], P["GPIO3"]
    xf = 49
    yf = flt.y / U + 3
    k.w(flt, (flt.x + u(1), flt.y), (flt.x + u(1), u(yf)), (u(xf), u(yf)), (u(xf), g3.y), g3)
    pullup(k, "R" + r(41), 47, yf, rail=ldo, fields="left")
    g6 = P["GPIO6"]                                              # GPIO6 turns the 9 V gate-drive LDO off
    k.w(g6, (g6.x - u(3), g6.y), (g6.x - u(3), u(yf + 1.5)))
    k.label((g6.x - u(3), u(yf + 1.5)), k.net("U" + r(1), g6.num), "L")
    for g in ("GPIO0", "GPIO1", "GPIO2", "GPIO4", "GPIO5", "GPIO7", "GPIO11"):
        k.gnd(P[g].pt, d="L"); k._mark(P[g].pt)
    # right side of the PD controller
    pphv, pp5v = P["PPHV"], P["PP5V"]
    xR = pphv.x / U
    yph = yv
    k.w(pphv, (pphv.x + u(1.5), pphv.y), (pphv.x + u(1.5), u(yph)), (u(xR + 14), u(yph)))
    hang(k, "C" + r(49), xR + 5, yph, N("PPHV"))
    k.label((u(xR + 14), u(yph)), N("PPHV"), "R")
    k.w(pp5v, (u(xR + 12), pp5v.y))
    hang(k, "C" + r(7), xR + 9, pp5v.y / U, N("PP5V"))
    k.label((u(xR + 12), pp5v.y), N("PP5V"), "R")
    dr, dre = P["DRAIN"], P["DRAIN_EP"]
    k.w(dr, (dr.x + u(1), dr.y), (dr.x + u(1), dre.y), dre)
    k.label((dr.x + u(1), dr.y), N("PD_DRAIN"), "R") if False else None
    l15, l33 = P["LDO_1V5"], P["LDO_3V3"]
    y15 = l15.y / U - 1.5                                          # lifted so its ground clears the LDO_3V3 line
    k.w(l15, (l15.x + u(2), l15.y), (l15.x + u(2), u(y15)))
    chain(k, (l15.x + u(2), u(y15)), N("LDO_1V5"), ["C" + r(5)], d="R", gap=0.5)
    a1, a2 = P["ADCIN1"], P["ADCIN2"]
    xl3 = xR + 4
    k.w(l33, (u(88), l33.y))
    k.rail((u(88), l33.y), ldo)
    hang(k, "C" + r(4), xR + 4, l33.y / U, ldo)
    if k.net("U" + r(1), a1.num) == ldo:
        k.w(a1, (a1.x + u(1), a1.y), (a1.x + u(1), l33.y))
    k.gnd(a2.pt, d="R"); k._mark(a2.pt)
    if k.net("U" + r(1), a1.num) == "GND": k.gnd(a1.pt, d="R"); k._mark(a1.pt)
    # local I2C to the charger and EEPROM, pulled up to the PD controller's LDO
    rows, xs = fanout(k, P, "R", [("I2Cc_SCL", yJ + 5), ("I2Cc_SDA", yJ + 6), ("~{I2Cc_IRQ}", yJ + 7),
                                  ("I2Ct_SCL", yJ + 9), ("I2Ct_SDA", yJ + 10), ("~{I2Ct_IRQ}", yJ + 11)], first=1)
    for key, rr, xx in (("I2Cc_SCL", "R" + r(3), 78), ("I2Cc_SDA", "R" + r(2), 82), ("~{I2Cc_IRQ}", "R" + r(4), 86)):
        y0 = rows[key][1] / U
        k.w(rows[key], (u(xx), u(y0)))
        k.label((rows[key][0] + u(1), u(y0)), k.net("U" + r(1), P[key].num), "R")
        pr_ = k.two(rr, u(xx), u(l33.y / U + 3.5), first=ldo)
        k.w(pr_.b, (u(xx), u(y0)))
        k.w(pr_.a, (u(xx), l33.y))
    for key in ("I2Ct_SCL", "I2Ct_SDA", "~{I2Ct_IRQ}"):
        k.w(rows[key], (u(xx + 2), rows[key][1])); k.label((u(xx + 2), rows[key][1]), k.net("U" + r(1), P[key].num), "R")
    # EEPROM: configuration for the PD controller on the local I2C
    ee = k.place("U" + r(2), u(100), u(yJ + 6), mirror=True, fields=(u(97.5), u(yJ + 0.6), u(97.5), u(yJ + 1.5)))
    k.w(ee["VCC"], (ee["VCC"].x, ee["VCC"].y - u(1)))
    k.w((ee["VCC"].x, ee["VCC"].y - u(1)), (ee["VCC"].x + u(4), ee["VCC"].y - u(1)))
    k.rail((ee["VCC"].x + u(4), ee["VCC"].y - u(1)), ldo)
    hang(k, "C" + r(8), ee["VCC"].x / U + 4, ee["VCC"].y / U - 1, ldo)
    a0, a1_, a2_ = ee["A0"], ee["A1"], ee["A2"]
    for p in (a0, a1_, a2_): k.w(p, (p.x + u(1), p.y))
    k.w((a0.x + u(1), a0.y), (a2_.x + u(1), a2_.y)); k.gnd((a2_.x + u(1), a2_.y))
    k.w(ee["WP"], (ee["WP"].x - u(1), ee["WP"].y), (ee["WP"].x - u(1), ee["WP"].y + u(2.5)))
    k.gnd((ee["WP"].x - u(1), ee["WP"].y + u(2.5)))

    # ================= band B: four-switch power stage
    yr = 50
    title(k, "FOUR-SWITCH BUCK-BOOST POWER STAGE  (PPHV -> RAC -> input bridge Q" + r(1) + " -> L" + r(1) + " -> output bridge Q" + r(2) + " -> RBAT -> PACK_P)", 0, 38)
    k.w((u(2), u(yr)), (u(7.5), u(yr)))
    k.label((u(2), u(yr)), N("PPHV"), "L")
    rac, tl, tr = kelvin_shunt(k, "R" + r(24), "R" + r(25), "R" + r(26), "C" + r(14), "C" + r(15), "C" + r(16), 12, yr, N("PPHV"))
    k.label(tl, N("ACP_F"), "L") if False else None
    k.w(tl, (tl[0], tl[1] - u(2))); k.label((tl[0], tl[1] - u(2)), N("ACP_F"), "U")
    k.w(tr, (tr[0], tr[1] - u(2))); k.label((tr[0], tr[1] - u(2)), N("ACN_F"), "U")
    cin = ["C" + r(i) for i in (30, 20, 23, 24, 27, 21, 56)]
    for c, x in zip(cin, (24.5, 29, 33.5, 38, 42.5, 48, 53.5)):
        hang(k, c, x, yr, N("AC_SNS_N"))
    q1x, ya, yb = 59.5, yr + 6, yr + 12
    A = k.place("Q" + r(1), u(q1x), u(ya), unit=1, fields=(u(q1x - 1.5), u(ya - 2.0), u(q1x - 1.5), u(ya - 1.2)), hide_val=True)
    B = k.place("Q" + r(1), u(q1x), u(yb), unit=2, fields=(u(q1x - 2.5), u(yb + 2.6), u(q1x - 2.5), u(yb + 3.4)), hide_val=False)
    xdA, xsw = q1x + 3.5, q1x + 4.5
    k.w((u(16.5), u(yr)), (u(xdA), u(yr)), (u(xdA), A["D1"].y), A["D1"])
    k.w(A["SW"], (u(xsw), A["SW"].y), (u(xsw), B["SW"].y), B["SW"])
    k.w(B["S2"], (u(xdA), B["S2"].y)); k.gnd((u(xdA), B["S2"].y))
    chain(k, A["G1"].pt, N("HG1"), ["R" + r(44)], gap=1.5)
    chain(k, B["G2"].pt, N("LG1"), ["R" + r(45)], gap=1.5)
    ysw = A["SW"].y / U
    L = series_h(k, "L" + r(1), xsw + 8, ysw, N("SW1"))
    k.w((u(xsw), u(ysw)), L.a)
    q2x = xsw + 20 + 4.5
    A2 = k.place("Q" + r(2), u(q2x), u(ya), unit=1, mirror=True, fields=(u(q2x - 1.5), u(ya - 2.0), u(q2x - 1.5), u(ya - 1.2)), hide_val=True)
    B2 = k.place("Q" + r(2), u(q2x), u(yb), unit=2, mirror=True, fields=(u(q2x + 0.5), u(yb + 2.6), u(q2x + 0.5), u(yb + 3.4)))
    xsw2, xd2 = q2x - 4.5, q2x - 3.5
    k.w(L.b, (u(xsw2), u(ysw)))
    k.w(A2["SW"], (u(xsw2), A2["SW"].y), (u(xsw2), B2["SW"].y), B2["SW"])
    k.w(B2["S2"], (u(xd2), B2["S2"].y)); k.gnd((u(xd2), B2["S2"].y))
    chain(k, A2["G1"].pt, N("HG2"), ["R" + r(46)], d="R", gap=1.5)
    chain(k, B2["G2"].pt, N("LG2"), ["R" + r(47)], d="R", gap=1.5)
    k.label((u(xsw + 1), u(ysw)), N("SW1"), "R"); k.label((u(xsw2 - 4), u(ysw)), N("SW2"), "R")
    # bootstrap: cap from the switch node up to BTST, diode from DRV_SUP
    dk = []
    for xx, cref, dref, nb, sgn in ((xsw + 2.5, "C" + r(12), "D" + r(4), N("BTST1"), 1), (xsw2 - 2.5, "C" + r(13), "D" + r(5), N("BTST2"), -1)):
        cb = k.two(cref, u(xx), u(ysw - 2.5), first=nb, fields="right" if sgn > 0 else "left")
        k.w(cb.b, (u(xx), u(ysw)))
        k.w(cb.a, (u(xx), u(ysw - 7)))
        yd = u(ysw - 7)
        if sgn > 0: fd = (u(xx) + 1.0, yd + 3.0, u(xx) + 1.0, yd + 5.3)
        else:
            lr, lv = len(dref) * CW, len(k.comps[dref]["value"]) * CW
            fd = (u(xx) - 1.0 - lr, yd + 3.0, u(xx) - 1.0 - lv, yd + 5.3)
        dd = k.two(dref, u(xx + sgn * 2.5), yd, first=nb if sgn > 0 else N("DRV_SUP"), horiz=True, fields=fd)
        k.w((u(xx), u(ysw - 7)), dd.a if sgn > 0 else dd.b)
        dk.append(dd.b if sgn > 0 else dd.a)
        k.label((u(xx), u(ysw - 7)), nb, "L" if sgn > 0 else "R")
    k.w(dk[0], dk[1])                                            # both bootstrap diodes fed from DRV_SUP
    k.label(((dk[0].x + dk[1].x) / 2, dk[0].y), N("DRV_SUP"), "U")
    # output side
    k.w(A2["D1"], (u(xd2), A2["D1"].y), (u(xd2), u(yr)))
    cout = ["C" + r(i) for i in (38, 31, 34)]
    x = q2x + 9
    k.w((u(xd2), u(yr)), (u(x + 4.5 * len(cout) + 2), u(yr)))
    for c in cout:
        hang(k, c, x, yr, N("BAT_SNS_P")); x += 4.5
    rb, tl2, tr2 = kelvin_shunt(k, "R" + r(27), "R" + r(28), "R" + r(29), "C" + r(17), "C" + r(18), "C" + r(19), x + 6.5, yr, N("BAT_SNS_P"))
    k.w((u(x + 2), u(yr)), (u(x + 2), u(yr)))
    k.w((u(x - 2.5), u(yr)), (u(x + 2), u(yr)))
    k.w(tl2, (tl2[0], tl2[1] - u(2))); k.label((tl2[0], tl2[1] - u(2)), N("SRP_F"), "U")
    k.w(tr2, (tr2[0], tr2[1] - u(2))); k.label((tr2[0], tr2[1] - u(2)), N("SRN_F"), "U")
    xp = x + 6.5 + 4.5
    k.w((u(xp), u(yr)), (u(xp + 3), u(yr))); k.rail((u(xp + 3), u(yr)), "PACK_P")

    # ================= band C: BQ25756 controller and its programming
    gx, gy = 40, 86
    title(k, "BQ25756 CHARGE CONTROLLER  (programming pins, battery feedback, thermistor)", 0, gy - 17)
    C = k.place("U" + r(3), u(gx), u(gy), fields="top")
    tg = [("VAC", gy - 14), ("ACP", gy - 11.5), ("ACN", gy - 10), ("ACUV", gy - 6), ("ACOV", gy - 3), ("SCL", gy - 1), ("SDA", gy),
          ("~{INT}", gy + 1), ("~{CE}", gy + 4), ("FSW_SYNC", gy + 7), ("ICHG", gy + 8), ("ILIM_HIZ", gy + 9), ("TS", gy + 19)]
    rows, xs = fanout(k, C, "L", tg, first=2)
    X = xs / U
    for key in ("ACP", "ACN", "SCL", "SDA", "~{INT}"):
        k.label(rows[key], k.net("U" + r(3), C[key].num), "L")
    # input voltage window: PPHV -> R409 -> ACUV -> R410 -> ACOV -> R411 -> GND
    xdv = X - 6
    for key in ("VAC", "ACUV", "ACOV"): k.w(rows[key], (u(xdv), rows[key][1]))
    vpart(k, "R" + r(10), xdv, gy - 6, gy - 3, N("ACUV"), fields="left")
    vpart(k, "R" + r(9), xdv, gy - 14, gy - 6, N("PPHV"), fields="left")
    hang(k, "R" + r(11), xdv, gy - 3, N("ACOV"), fields="left")
    k.w((u(xdv), u(gy - 14)), (u(xdv - 8), u(gy - 14)))
    hang(k, "C" + r(9), xdv - 5, gy - 14, N("PPHV"), fields="left")
    k.label((u(xdv - 8), u(gy - 14)), N("PPHV"), "L")
    # charge enable: pulled up to 3V3, the MCU's CHG_INH can hold it high through R435
    ce = rows["~{CE}"]
    k.w(ce, (ce[0] - u(13), ce[1]))
    pullup(k, "R" + r(17), X - 11, ce[1] / U, rail="3V3")
    chain(k, (ce[0] - u(13), ce[1]), N("CE_N"), ["R" + r(35)], gap=1)
    # frequency, charge current and input current limit: one resistor to ground each
    for i, (key, rr) in enumerate((("FSW_SYNC", "R" + r(12)), ("ICHG", "R" + r(13)), ("ILIM_HIZ", "R" + r(14)))):
        xx = X - 2 - 5.5 * (2 - i)
        k.w(rows[key], (u(xx), rows[key][1]))
        rp_ = k.two(rr, u(xx), u(gy + 12.5), first=k.net("U" + r(3), C[key].num))
        k.w(rp_.a, (u(xx), rows[key][1]))
    # battery thermistor: REGN -> R415 -> TS -> R416 || TH401 -> GND
    ts = rows["TS"]
    xt = X - 15
    k.w(ts, (u(X - 21.5), ts[1]))
    pr_ = k.two("R" + r(15), u(xt), ts[1] - u(2.5), first=N("REGN"))
    k.w(pr_.b, (u(xt), ts[1])); k.label(pr_.a, N("REGN"), "U")
    hang(k, "R" + r(16), xt, ts[1] / U, N("TS"))
    hang(k, "TH" + r(1), X - 21.5, ts[1] / U, N("TS"))
    # right side: feedback divider, REGN / DRV_SUP diode-OR (gate drive and sense reach the power stage by name)
    tgr = [("FB", gy + 4), ("FBG", gy + 7), ("REGN", gy + 10), ("DRV_SUP", gy + 13)]
    rr_, xsr = fanout(k, C, "R", tgr, first=2)
    XR = xsr / U
    k.w(rr_["FB"], (u(XR + 1), rr_["FB"][1])); k.w(rr_["FBG"], (u(XR + 1), rr_["FBG"][1]))
    pullup(k, "R" + r(18), XR + 1, gy + 4, rail="PACK_P")
    vpart(k, "R" + r(19), XR + 1, gy + 4, gy + 7, N("FB"))

    # ================= 9 V gate-drive supply, diode-ORed with REGN
    a = XR + 8
    title(k, "9 V GATE-DRIVE SUPPLY  (TPS7A4101, diode-ORed with REGN into DRV_SUP; GPIO6 high turns it off)", a - 1, gy + 7)
    k.w(rr_["REGN"], (u(a + 12), rr_["REGN"][1]))
    k.w(rr_["DRV_SUP"], (u(a), rr_["DRV_SUP"][1]))
    vpart(k, "D" + r(10), a, gy + 10, gy + 13, N("REGN"))
    hang(k, "C" + r(10), a + 9, gy + 10, N("REGN"))
    k.label((u(a + 12), u(gy + 10)), N("REGN"), "R")
    hang(k, "C" + r(11), XR + 2, gy + 13, N("DRV_SUP"))
    k.label((u(XR + 3), u(gy + 13)), N("DRV_SUP"), "R")
    yo = gy + 18
    vpart(k, "D" + r(11), a, gy + 13, yo, N("DRV_SUP"))
    X6 = a + 21
    V = k.place("U" + r(6), u(X6), u(yo + 2), mirror=True, fields="top")
    k.w((u(a), u(yo)), V["OUT"])
    hang(k, "C" + r(58), a + 5, yo, N("V9_DRV"))
    k.label((u(a + 1), u(yo)), N("V9_DRV"), "R")
    vpart(k, "R" + r(52), X6 - 6, yo, V["FB"].y / U, N("V9_DRV"), fields="left")
    k.w(V["FB"], (u(X6 - 6), V["FB"].y))
    hang(k, "R" + r(53), X6 - 6, V["FB"].y / U, N("V9_FB"), fields="left")
    vin6, en6 = V["IN"], V["EN"]
    xi = vin6.x / U
    k.w(vin6, (u(xi + 4), vin6.y)); k.rail((u(xi + 4), vin6.y), "PACK_P")
    hang(k, "C" + r(57), xi + 4, vin6.y / U, "PACK_P")
    ye = yo + 8
    q9 = k.place("Q" + r(9), u(xi + 13), u(ye + 6.5), fields="right")
    k.w(en6, (en6.x + u(1), en6.y), (en6.x + u(1), u(ye)), (q9["D"].x, u(ye)), q9["D"])
    r54 = k.two("R" + r(54), u(xi + 10), u(ye - 2.5), first=N("REGN"))
    k.w(r54.b, (u(xi + 10), u(ye))); k.label(r54.a, N("REGN"), "U")
    g9 = q9["G"]
    k.w(g9, (g9.x - u(6), g9.y))
    pullup(k, "R" + r(55), g9.x / U - 2.5, g9.y / U, rail=ldo)
    k.label((g9.x - u(6), g9.y), N("DRV9_OFF"), "L")

    # ================= 5 V buck for PP5V, top right of the controller
    bx, by = 86, gy - 4
    title(k, "5 V BUCK FOR PP5V  (TPS62933, VBUS source and VCONN supply for the PD controller)", 60, gy - 17)
    B5 = k.place("U" + r(4), u(bx), u(by), fields="top")
    t5 = [("VIN", by - 9), ("EN", by - 2), ("SS", by + 2)]
    r5, x5 = fanout(k, B5, "L", t5, first=2)
    X5 = x5 / U
    k.w(r5["VIN"], (u(X5 - 14), r5["VIN"][1])); k.rail((u(X5 - 14), r5["VIN"][1]), "PACK_P")
    for c, xx in (("C" + r(46), X5 - 5), ("C" + r(44), X5 - 10.5)): hang(k, c, xx, by - 9, "PACK_P")
    k.w(r5["EN"], (u(X5 - 7), r5["EN"][1]))
    hang(k, "R" + r(32), X5 - 4, by - 2, k.net("U" + r(4), B5["EN"].num))
    k.label((u(X5 - 7), r5["EN"][1]), k.net("U" + r(4), B5["EN"].num), "L")
    k.w(r5["SS"], (u(X5 - 1), r5["SS"][1]))
    hang(k, "C" + r(39), X5 - 1, by + 2, N("SS_5V"), fields="left")
    k.gnd(B5["RT"].pt, d="L"); k._mark(B5["RT"].pt)
    bst, sw5, fb5 = B5["BST"], B5["SW"], B5["FB"]
    k.w(bst, (bst.x + u(2), bst.y)); k.w(sw5, (sw5.x + u(2), sw5.y))
    vpart(k, "C" + r(40), bst.x / U + 2, bst.y / U, sw5.y / U, N("BST_5V"))
    L5 = series_h(k, "L" + r(2), sw5.x / U + 9, sw5.y / U, N("SW_5V"))
    k.w((sw5.x + u(2), sw5.y), L5.a)
    xo = sw5.x / U + 14
    k.w(L5.b, (u(xo + 18), sw5.y))
    vpart(k, "R" + r(33), xo, sw5.y / U, fb5.y / U, N("PP5V"))
    k.w(fb5, (u(xo), fb5.y))
    hang(k, "R" + r(34), xo, fb5.y / U, N("FB_5V"))
    for i, c in enumerate(["C" + r(41), "C" + r(42), "C" + r(43)]): hang(k, c, xo + 4 + 4.5 * i, sw5.y / U, N("PP5V"))
    k.label((u(xo + 18), sw5.y), N("PP5V"), "R")
    k.place("TP" + r(12), u(xo + 19.5), u(sw5.y / U + 3), angle=180, fields="right")

    nts = ["Power flow: USB-C VBUS -> TPS25751D internal 5 A switch -> PPHV -> RAC (R" + r(24) + ") -> four-switch stage -> RBAT (R" + r(27) + ") -> PACK_P. "
           "The same path runs in reverse when the port sources power.",
           "Gate drive, bootstrap and sense nets join the power stage to the BQ25756 by name (HIDRV1, BTST1, SW1, ACP_F, SRN_F...).",
           "ADCIN1 strap sets the PD controller I2C target address: " + ("LDO_3V3 on this port." if k.net("U" + r(1), a1.num) != "GND" else "GND on this port.") + " The two ports must differ.",
           "Unused TPS25751 GPIOs are grounded (datasheet). GPIO3 = SBU/CC fault from the TPD6S300; GPIO6 high turns the 9 V gate-drive LDO off.",
           "R" + r(44) + "-R" + r(47) + ": 0R gate resistors are tuning positions. The first ceramic on each side of the bridge (C" + r(30) + ", C" + r(38) + ") closes the hot loop.",
           "C" + r(44) + "/C" + r(46) + " close the 5 V buck input hot loop on PACK_P; C" + r(57) + " is the 9 V LDO input cap."]
    nts += part_notes(k, [x for x in k.refs])
    notes(k, nts, 112, 96, width=80)


LAYOUTS = {"3V3 Rail": rail_3v3, "MCU": mcu, "Cells and Gauge": cells_gauge, "USB Port": usb_port}
