"""Hand-laid-out sheets, one function per block, written with the kit in scene.py."""
from scene import snap

def rail_3v3(S):
    S.sh.paper = (297, 138)
    S.title("3V3 Rail", 15, 18)
    # ---- one path, left to right: PACK_P in with its bulk, IC, inductor, 3V3 out ----
    S.text("TPS62177 3.3 V always-on buck: PACK_P in with the shared bulk, 3V3 out (0.5 A)", 15, 32, 1.6)
    S.box(14, 36, 283, 84)
    ox, oy = 168.91, 64.77
    u = S.ic("U204", ox, oy)
    vin, en, slp, pg = u("VIN"), u("EN"), u("~{SLEEP}"), u("PG")
    sw, vos, fb = u("SW"), u("VOS"), u("FB")
    yv = vin[1]
    S.pwr("PACK_P", 25.4, yv)
    refs = [f"C{208 + i}" for i in range(6)]
    xs = S.hang(refs, 40.64, yv, 15.24, "GND", rail="PACK_P")      # shared bulk on the PACK_P rail
    S.text("C208 to C213: shared PACK_P bulk, 6x 22u 35V 1210", 40.64, yv + 16.5)
    S.text("also serves both chargers and both 5 V bucks", 40.64, yv + 19.0)
    c206 = S.two("C206", vin[0] - 25.4, yv, "v", first="PACK_P", text="r"); S.gnd(*c206.b)
    S.w((25.4, yv), vin)
    S.w((vin[0] - 5.08, yv), (vin[0] - 5.08, en[1]), en)           # EN tied to VIN
    S.stub(slp, "L", "3V3_SLEEP", 7.62)
    S.nc(pg)
    S.w(u("NC"), u("AGND")); S.gnd(*u("PGND"))                     # NC, PAD, PGND, AGND: one ground
    S.w(sw, (sw[0] + 7.62, sw[1]))
    l = S.two("L201", sw[0] + 15.24, sw[1], "h", first="SW_3V3", text="a")
    S.w((sw[0] + 7.62, sw[1]), l.a)
    S.text("SW_3V3", sw[0] + 0.8, sw[1] - 1.8)
    xo = snap(l.b[0] + 7.62)
    S.w(vos, (xo, vos[1]), (xo, sw[1]))                            # VOS senses the output node
    S.w(fb, (fb[0] + 2.54, fb[1])); S.gnd(fb[0] + 2.54, fb[1])     # FB to ground on the fixed 3.3 V part
    c207 = S.two("C207", xo + 12.7, sw[1], "v", first="3V3", text="r"); S.gnd(*c207.b)
    S.w(l.b, c207.a, (xo + 25.4, sw[1]))
    S.pwr("3V3", xo + 25.4, sw[1])
    S.note(["Notes",
            "1. PACK_P (12 to 16.8 V) feeds VIN and EN directly, so the 3V3 rail is always on.",
            "2. SLEEP low puts the buck in sleep mode. The MCU drives it; R313 on the MCU sheet holds it high while the MCU is in reset.",
            "3. FB is tied to ground on the fixed 3.3 V version; VOS senses the output.",
            "4. PG is not used. The NC pin goes to ground as TI recommends."],
           20, 95)

def mcu(S):
    S.sh.paper = (297, 210)
    S.title("MCU", 15, 18)
    S.text("CC2340R5MODA Bluetooth LE module: supply, reset, I2C and control lines", 15, 30, 1.6)
    S.box(14, 34, 262, 112)
    ox, oy = 140.0, 83.82
    u = S.ic("U301", ox, oy)
    yr = 52.07
    # supply rail along the top: 3V3 in, pull-up for reset, decoupling at VDDS
    S.pwr("3V3", 22.86, yr)
    xv = ox - 16.51 - 5.08
    S.w((22.86, yr), (xv, yr), (xv, u("VDDS")[1]), u("VDDS"))
    S.two("R302", 35.56, yr, "v", first="3V3")
    xs = S.hang(["C301", "C302", "C303"], 70.0, yr, 15.24, "GND", rail="3V3")
    tp = S._sym("TP301", 53.34, yr, 0, False, 1, (55.88, yr - 4.6), (55.88, yr - 2.4))
    # reset: R302 pulls NRST up, C304 is the power-on reset capacitor
    ry = u("RSTN")[1]
    S.w(S.pl["R302"].b, (35.56, ry), u("RSTN"))
    S.w((25.4, ry), (35.56, ry)); S.label("NRST", 25.4, ry, "L")
    c304 = S.two("C304", 43.18, ry, "v", first="NRST"); S.gnd(*c304.b)
    # I2C pull-ups: up to 3V3 from the line, line carries on to its label
    for ref, pin, x, net in (("R304", "DIO6_A1", 165.4, "SCL"), ("R305", "DIO8", 181.9, "SDA")):
        p = u(pin)
        r = S.two(ref, x, p[1] - 7.62, "v", first="3V3")
        S.pwr("3V3", x, p[1] - 7.62)
        S.w(p, (x + 2.54, p[1])); S.label(net, x + 2.54, p[1], "R")
    S.stub(u("DIO18"), "R", "UART_TX", 5.08)
    S.nc(u("DIO20_A11")); S.nc(u("DIO12"))
    for pin, net in (("DIO24_A7", "CHG_INH"), ("DIO3_X32P", "EN_5V1"), ("DIO4_X32N", "EN_5V2")):
        S.stub(u(pin), "R", net, 5.08)
    for ref, pin, x, net in (("R313", "DIO21_A10", 194.6, "3V3_SLEEP"), ("R314", "DIO11", 223.8, "IRQ_N")):
        p = u(pin)
        S.two(ref, x, p[1] - 7.62, "v", first="3V3")
        S.pwr("3V3", x, p[1] - 7.62)
        S.w(p, (x + 2.54, p[1])); S.label(net, x + 2.54, p[1], "R")
    # left pins
    # antenna pi network, wired straight out of RFIO and ANT_IN: series C313, shunt C314, series R321, shunt C315
    rf, an = u("RFIO"), u("ANT_IN"); pxl = rf[0]
    c313 = S.two("C313", pxl - 24.13, rf[1], "h", first="ANT_MID", text="b")
    S.w(rf, c313.b)
    xm = pxl - 34.29
    S.w(c313.a, (xm, rf[1]))
    c314 = S.two("C314", xm, rf[1], "v", first="ANT_MID", text="l"); S.gnd(*c314.b)
    r321 = S.two("R321", pxl - 62.23, rf[1], "h", first="ANT_IN", text="b")
    S.w((xm, rf[1]), r321.b)
    xn_ = r321.a[0] - 5.08
    c315 = S.two("C315", xn_, rf[1], "v", first="ANT_IN", text="l"); S.gnd(*c315.b)
    S.w(r321.a, (xn_, rf[1]))
    S.w((xn_, rf[1]), (xn_, an[1]), an)
    S.stub(u("DIO16/SWDIO"), "L", "SWDIO", 5.08); S.stub(u("DIO17/SWDCK"), "L", "SWCLK", 5.08)
    g = u("GND"); S.w(g, (g[0] - 2.54, g[1])); S.gnd(g[0] - 2.54, g[1])
    S.note(["R302 and C304: RSTN pull-up with the power-on reset capacitor (TI SWRS349A fig. 9-1).",
            "R313 holds 3V3_SLEEP high while the MCU is in reset. R314 is the one IRQ_N pull-up.",
            "Antenna pi network C313, C314, R321, C315 between RFIO and ANT_IN. C314 is a placeholder (DNP as on TI's LaunchPad); retune all four."], 20, 100)

    # ---- connectors ----
    S.text("Debug and gauge-training connectors (Tag-Connect footprints, no part fitted)", 15, 121, 1.6)
    S.box(14, 125, 262, 162)
    j1 = S.ic("J301", 100.0, 144.78, ref_at=(78.0, 134.5), val_at=(78.0, 136.7))
    S.w(j1("VCC"), (j1("VCC")[0], j1("VCC")[1] - 2.54)); S.pwr("3V3", j1("VCC")[0], j1("VCC")[1] - 2.54)
    S.w(j1("GND"), (j1("GND")[0], j1("GND")[1] + 2.54)); S.gnd(j1("GND")[0], j1("GND")[1] + 2.54)
    for pin, net in (("~{RESET}", "NRST"), ("SWCLK", "SWCLK"), ("SWDIO", "SWDIO"), ("SWO", "UART_TX")):
        S.stub(j1(pin), "R", net, 5.08)
    j2 = S.ic("J302", 200.0, 144.78)
    for pin, net in (("SDA", "SDA"), ("CHG_INH", "CHG_INH"), ("NRST", "NRST"), ("SCL", "SCL")):
        S.stub(j2(pin), "L", net, 5.08)
    S.nc(j2("NC")); g = j2("GND"); S.w(g, (g[0] - 2.54, g[1])); S.gnd(g[0] - 2.54, g[1])

def cells_gauge(S):
    S.sh.paper = (420, 272)
    S.title("Cells and Gauge", 15, 18)
    gnda = lambda pt, show=False: S.gnda(pt[0], pt[1], show)

    # ================= gauge =================
    S.text("BQ40Z50 gauge: supply, cell inputs, SMBus, gate drive", 15, 30, 1.6)
    S.box(12, 34, 258, 148)
    ox, oy = 177.8, 104.14
    u = S.ic("U101", ox, oy)
    px, pr = u("VC4")[0], u("CHG")[0]
    # --- BAT, VCC, PBI: fanned up to three lanes above the cell inputs
    cols = [px - 13.97, px - 17.78, px - 21.59]
    lanes = [oy - 60.96, oy - 50.8, oy - 40.64]
    for name, col, ly in zip(("BAT", "VCC", "PBI"), cols, lanes):
        p = u(name); S.w(p, (col, p[1]), (col, ly))
    y = lanes[0]
    r105 = S.two("R105", cols[0] - 5.08 - 7.62, y, "h", first="BAT_D", text="a")
    S.w((cols[0], y), r105.b)
    d101 = S.two("D101", r105.a[0] - 5.08 - 7.62, y, "h", first="CELL_4P", text="a")
    S.w(r105.a, d101.b); S.w(d101.a, (d101.a[0] - 5.08, y)); S.label("CELL_4P", d101.a[0] - 5.08, y, "L")
    y = lanes[1]
    r106 = S.two("R106", cols[1] - 5.08 - 7.62, y, "h", first="FET_MID", text="a")
    S.w((cols[1], y), r106.b); S.w(r106.a, (r106.a[0] - 5.08, y)); S.label("FET_MID", r106.a[0] - 5.08, y, "L")
    y = lanes[2]; xh = cols[2] - 12.7
    S.w((cols[2], y), (xh, y))
    c105 = S.two("C105", xh, y, "v", first="PBI"); gnda(c105.b, True)
    # --- cell inputs: RC ladder fanned out from the four VC pins
    xn = px - 50.8
    lv = [oy - 26.67, oy - 13.97, oy - 1.27, oy + 11.43]
    for (name, col, ly) in (("VC4", px - 30.48, lv[0]), ("VC3", px - 34.29, lv[1]), ("VC2", px - 34.29, lv[2]), ("VC1", px - 30.48, lv[3])):
        p = u(name); S.w(p, (col, p[1]), (col, ly), (xn, ly)); S.label(name, xn + 3.81, ly, "R")
    cells = [("R104", "J116", "CELL_4P"), ("R103", "J111", "CELL3"), ("R102", "J110", "CELL2"), ("R101", "J109", "CELL1")]
    for (rr, jj, net), ly in zip(cells, lv):
        r = S.two(rr, xn - 5.08 - 7.62, ly, "h", first=net, text="a")
        S.w((xn, ly), r.b)
        xp = xn - 35.56
        S.w((xp, ly), r.a); S.label(net, xp + 5.08, ly, "R")
        S.pad(jj, xp, ly, text="l")
    for k, cc in enumerate(("C101", "C102", "C103")):
        c = S.two(cc, xn, lv[k] + 2.54, "v", first=f"VC{4 - k}")
        S.w((xn, lv[k]), c.a); S.w(c.b, (xn, lv[k + 1]))
    c104 = S.two("C104", xn, lv[3], "v", first="VC1"); gnda(c104.b, True)
    S.w(c104.b, (xn - 10.16, c104.b[1])); S.pad("J115", xn - 10.16, c104.b[1], text="l")
    # --- PACK sense: fanned down to a lane below
    p = u("PACK"); col = px - 13.97; ly = oy + 34.29
    S.w(p, (col, p[1]), (col, ly))
    r113 = S.two("R113", col - 5.08 - 7.62, ly, "h", first="PACK_P", text="a")
    S.w((col, ly), r113.b); S.w(r113.a, (r113.a[0] - 5.08, ly)); S.label("PACK_P", r113.a[0] - 5.08, ly, "L")
    # --- plain stubs
    for n in ("SRP", "SRN", "TS1", "TS2", "TS3", "TS4"): S.stub(u(n), "L", n, 5.08)
    for n in ("PTCEN", "PTC"):
        p = u(n); S.w(p, (p[0] - 5.08, p[1])); gnda((p[0] - 5.08, p[1]))
    # --- right side
    S.stub(u("CHG"), "R", "CHG", 5.08); S.stub(u("DSG"), "R", "DSG", 5.08)
    for n in ("PCHG", "LEDCNTLA", "LEDCNTLB", "LEDCNTLC", "NC"): S.nc(u(n))
    for name, rr, col, ly, net in (("FUSE", "R126", pr + 16.51, oy - 50.8, "Q104_G"), ("SMBC", "R115", pr + 20.32, oy - 40.64, "SCL"),
                                    ("SMBD", "R116", pr + 24.13, oy - 30.48, "SDA")):
        p = u(name); S.w(p, (col, p[1]), (col, ly))
        r = S.two(rr, col + 5.08, ly, "h", first=S.net_of("U101", name), text="a")
        S.w((col, ly), r.a); S.w(r.b, (r.b[0] + 5.08, ly)); S.label(net, r.b[0] + 5.08, ly, "R")
    # BTP_INT: 470k to ground and the gate of the interrupt FET
    p = u("BTP_INT"); xj = pr + 10.16
    r117 = S.two("R117", xj, p[1], "v", first="BTP_INT"); gnda(r117.b)
    q103 = S.ic("Q103", pr + 46.99, p[1], ref_at=(pr + 52, p[1] - 3.5), val_at=(pr + 52, p[1] - 1.1))
    S.w(p, q103("G"))
    d = q103("D"); S.w(d, (d[0], d[1] - 2.54), (d[0] + 2.54, d[1] - 2.54)); S.label("IRQ_N", d[0] + 2.54, d[1] - 2.54, "R")
    S.w(q103("S"), (q103("S")[0], q103("S")[1] + 2.54)); S.gnd(q103("S")[0], q103("S")[1] + 2.54)
    S.note(["Q103 shifts the gauge interrupt", "BTP_INT onto the shared IRQ_N line."], pr + 30, p[1] + 14)
    S.label("BTP_INT", xj + 3.81, p[1], "R")
    # PRES/SHUTDN, DISP and VSS to CELL_1N on one bus
    pres, disp, vss = u("PRES/SHUTDN"), u("DISP"), u("VSS")
    xb = pr + 5.08
    S.w(pres, (xb, pres[1]), (xb, vss[1] + 2.54)); S.w(disp, (xb, disp[1])); S.w(vss, (xb, vss[1])); gnda((xb, vss[1] + 2.54), True)

    # ================= power path =================
    S.text("Power path: pack cells, fuse, charge and discharge FETs, load; sense resistor in the return", 15, 156, 1.6)
    S.box(12, 160, 258, 252)
    yq, yc = 176.53, 196.85
    f = S.ic("F102", 52.07, yc)
    S.pad("J112", 25.4, yc); S.w((25.4, yc), f("1"))
    h = f("HTR"); S.w(h, (h[0], h[1] + 2.54)); S.label("HTR", h[0], h[1] + 2.54, "R")
    q1 = S.ic("Q101", 100.33, yq, ref_at=(93.98, yq - 9.5), val_at=(93.98, yq - 7.2))
    q2 = S.ic("Q102", 124.46, yq, mirror=True, ref_at=(118.11, yq - 9.5), val_at=(118.11, yq - 7.2))
    S.w(f("2"), (q1("S")[0], yc), q1("S")); S.label("CELL_P", 66.04, yc, "R")
    S.w(q1("D"), q2("D")); S.label("FET_MID", 107.95, yq - 1.27, "R")
    # gate of Q101: CHG -> 5.1k -> gate, 10M bleed to CELL_P
    xg = 86.36; gy = yq - 1.27
    S.w(q1("G"), (xg, gy))
    S.two("R110", xg, gy, "v", first="CHG_G", text="l"); S.w((xg, gy + 7.62), (xg, yc))
    r109 = S.two("R109", 63.5, gy, "h", first="CHG", text="a")
    S.w(r109.b, (xg, gy)); S.w(r109.a, (r109.a[0] - 5.08, gy)); S.label("CHG", r109.a[0] - 5.08, gy, "L")
    # gate of Q102: DSG -> 5.1k -> gate, 10M bleed and the 15 V zener to PACK_P
    xg2 = 139.7
    S.w(q2("G"), (xg2, gy))
    S.two("R112", xg2, gy, "v", first="DSG_G"); S.w((xg2, gy + 7.62), (xg2, yc))
    xz = 157.48
    S.w((xg2, gy), (xz, gy))
    S.two("D103", xz, gy, "v", first="DSG_G"); S.w((xz, gy + 7.62), (xz, yc))
    r111 = S.two("R111", 170.18, gy, "h", first="DSG_G", text="a")
    S.w((xz, gy), r111.a); S.w(r111.b, (r111.b[0] + 5.08, gy)); S.label("DSG", r111.b[0] + 5.08, gy, "R")
    # PACK_P rail to the load
    S.w(q2("S"), (q2("S")[0], yc), (244, yc)); S.pwr("PACK_P", 244, yc)
    S.pad("J113", 222.25, yc, text="r")
    S.pad("TP106", 196.85, yc, text="r")
    S.text("CHG FET", 93.98, yq - 11.5); S.text("DSG FET", 118.11, yq - 11.5)
    # PACK_P to ground through two caps (ESD)
    c107 = S.two("C107", 176.53, yc, "v", first="PACK_P")
    c108 = S.two("C108", 176.53, c107.b[1], "v", first="PACK_CMID"); S.gnd(*c108.b)
    # ESD caps across the FETs: two in series from CELL_P to PACK_P
    ye = 211.12
    S.w((96.52, yc), (96.52, ye))
    c110 = S.two("C110", 96.52, ye, "h", first="CELL_P", text="b")
    c111 = S.two("C111", c110.b[0] + 5.08, ye, "h", first="ESD_MID", text="b")
    S.w(c110.b, c111.a); S.w(c111.b, (130.81, ye), (130.81, yc))
    S.text("ESD: two caps in series across the FETs", 96.52, ye + 10)
    # WAKE pull
    r118 = S.two("R118", 74.93, yc, "v", first="CELL_P")
    S.w(r118.b, (74.93, r118.b[1] + 2.54)); S.pad("TP113", 74.93, r118.b[1] + 2.54, down=True)
    # return path with the sense resistor
    yn = 232.41
    S.text("Return path and current sense", 15, 224)
    S.pad("J108", 25.4, yn)
    rs = S.two("RS101", 50.8, yn, "h", first="CELL_N", text="a")
    S.w((25.4, yn), rs.a)
    xs1 = 38.1; xs2 = 76.2
    S.w(rs.b, (96.52, yn)); S.gnd(96.52, yn)
    S.pad("J114", 96.52, yn, text="r"); S.pad("TP109", 86.36, yn, text="l")
    r107 = S.two("R107", xs1, yn, "v", first="CELL_N")
    r108 = S.two("R108", xs2, yn, "v", first="GND")
    ys = yn + 12.7
    S.w(r107.b, (xs1, ys)); S.w(r108.b, (xs2, ys))
    c106 = S.two("C106", 52.07, ys, "h", first="SRP", text="b")
    S.w((xs1, ys), c106.a); S.w(c106.b, (xs2, ys))
    S.w((xs1, ys), (xs1 - 5.08, ys)); S.label("SRP", xs1 - 5.08, ys, "L")
    S.w((xs2, ys), (xs2 + 5.08, ys)); S.label("SRN", xs2 + 5.08, ys, "R")
    S.w((xs1, yn), (xs1, yn)); S.w((rs.a[0], yn), (xs1, yn)) if False else None
    S.text("R107, R108 and C106 filter the Kelvin taps SRP, SRN", 100, ys + 1)

    # ================= second-level protector =================
    S.text("Second-level protector BQ294700 and fuse ignition", 266, 89.3, 1.6)
    S.box(262, 93.5, 408, 183.5)
    ox2, oy2 = 331.47, 135.89
    u2 = S.ic("U102", ox2, oy2)
    px2 = u2("V4")[0]; xn2 = px2 - 30.48
    lv2 = [oy2 - 19.05, oy2 - 6.35, oy2 + 6.35, oy2 + 19.05]
    for (name, col, ly) in (("V4", px2 - 5.08, lv2[0]), ("V3", px2 - 8.89, lv2[1]), ("V2", px2 - 8.89, lv2[2]), ("V1", px2 - 5.08, lv2[3])):
        p = u2(name); S.w(p, (col, p[1]), (col, ly), (xn2, ly))
    for (rr, net), ly in zip((("R119", "CELL_4P"), ("R120", "CELL3"), ("R121", "CELL2"), ("R122", "CELL1")), lv2):
        r = S.two(rr, xn2 - 5.08 - 7.62, ly, "h", first=net, text="a")
        S.w((xn2, ly), r.b); S.w(r.a, (r.a[0] - 5.08, ly)); S.label(net, r.a[0] - 5.08, ly, "L")
    for k, cc in enumerate(("C112", "C113", "C114")):
        c = S.two(cc, xn2, lv2[k] + 2.54, "v", first=f"U102_V{4 - k}")
        S.w((xn2, lv2[k]), c.a); S.w(c.b, (xn2, lv2[k + 1]))
    c115 = S.two("C115", xn2, lv2[3], "v", first="U102_V1"); gnda(c115.b, True)
    vdd, vss, cd, out = u2("VDD"), u2("VSS"), u2("CD"), u2("OUT")
    xa = vdd[0] + 7.62
    S.w(vdd, (xa, vdd[1]))
    c116 = S.two("C116", xa, vdd[1], "v", first="U102_VDD"); gnda(c116.b)
    r123 = S.two("R123", xa + 5.08, vdd[1], "h", first="U102_VDD", text="a")
    S.w((xa, vdd[1]), r123.a); S.w(r123.b, (r123.b[0] + 5.08, vdd[1])); S.label("CELL_4P", r123.b[0] + 5.08, vdd[1], "R")
    S.w(vss, (vss[0] + 2.54, vss[1])); gnda((vss[0] + 2.54, vss[1]))
    xc = vdd[0] + 20.32
    S.w(cd, (xc, cd[1])); c117 = S.two("C117", xc, cd[1], "v", first="U102_CD"); gnda(c117.b)
    yo = oy2 + 19.05
    xo = out[0] + 3.81
    r124 = S.two("R124", out[0] + 12.7, yo, "h", first="U102_OUT", text="b")
    S.w(out, (xo, out[1]), (xo, yo), r124.a)
    nq = r124.b[0] + 7.62
    S.w(r124.b, (nq, yo)); S.label("Q104_G", r124.b[0] + 1.27, yo, "R")
    S.two("R125", nq, yo, "v", first="Q104_G")
    S.gnd(nq, yo + 7.62)
    c118 = S.two("C118", nq + 10.16, yo, "v", first="Q104_G"); gnda(c118.b)
    q104 = S.ic("Q104", nq + 29.2, yo, ref_at=(nq + 27, yo - 12.7), val_at=(nq + 27, yo - 10.5))
    S.w((nq, yo), q104("G"))
    d = q104("D"); S.w(d, (d[0], d[1] - 2.54), (d[0] + 2.54, d[1] - 2.54)); S.label("HTR", d[0] + 2.54, d[1] - 2.54, "R")
    S.w(q104("S"), (q104("S")[0], q104("S")[1] + 2.54)); S.gnd(q104("S")[0], q104("S")[1] + 2.54)
    S.text("Q104 ignites the fuse heater", nq - 5, yo + 14)

    # ================= thermistors =================
    S.text("Cell temperature inputs TS1 to TS4 (10k NTCs to CELL_1N)", 266, 30, 1.6)
    S.box(262, 34, 408, 84)
    y0 = 58.42
    for (ref, xx, net) in (("TH101", 290, "TS1"), ("TH104", 392, "TS4")):
        S.w((xx - 16, y0), (xx, y0)); S.label(net, xx - 16, y0, "L")
        t = S.two(ref, xx, y0, "v", first=net); gnda(t.b, True)
    for (ja, jb, xx, net) in (("J117", "J118", 322, "TS2"), ("J119", "J120", 356, "TS3")):
        a = S.ic(ja, xx + 5.08, y0, ref_at=(xx + 6, y0 - 8), val_at=(xx + 6, y0 - 5.8))
        S.stub(a("Pin_1"), "L", net, 5.08)
        b = S.ic(jb, xx + 5.08, y0 + 14, ref_at=(xx + 6, y0 + 6), val_at=(xx + 6, y0 + 8.3))
        p = b("Pin_1"); S.w(p, (p[0] - 2.54, p[1])); gnda((p[0] - 2.54, p[1]))
    S.note(["TS1 and TS4: NTCs on the board. TS2 and TS3: NTC wires, one pad for the signal and one for the return."], 266, 80)

    # ================= notes =================
    S.text("Notes", 266, 189.3, 1.6)
    S.box(262, 193.5, 408, 222)
    S.note(["1. CELL_1N (ground symbol with a bar) is the Kelvin ground at the cell-1 negative tab.",
            "    GND is the load ground, reached through the sense resistor RS101.",
            "2. CELL1 to CELL3 and CELL_4P are the cell sense wires J109 to J111 and J116.",
            "3. SRP and SRN: route as a Kelvin pair from the RS101 pads, filtered by R107, R108, C106.",
            "4. Q101 and Q102 are back to back with their drains joined (FET_MID).",
            "5. The 3V3 sheet, MCU and both USB ports see this sheet through PACK_P, SCL, SDA and IRQ_N."],
           266, 201)

from layouts_usb import usb_port
LAYOUTS = {"3V3 Rail": rail_3v3, "MCU": mcu, "Cells and Gauge": cells_gauge, "USB Port 1": usb_port, "USB Port 2": usb_port}
