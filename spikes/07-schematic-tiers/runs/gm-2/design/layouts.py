"""One hand-composed picture per sheet. Each function gets a Cv (lay.py) and draws every part of its block.
Coordinates are millimetres on the sheet, on the 1.27 mm grid. Nothing here decides connectivity: net names come
from the netlist, and make.sh proves the result equals it."""
from lay import Cv, CHW

U = 1.27

def layout_3v3(c):
    c.s.paper = (210, 168)
    # ---- buck stage ----
    c.frame(12.7, 12.7, 200, 76.2, "TPS62177 3.3 V always-on buck, sleep mode under MCU control")
    ox, oy = 101.6, 49.53
    u = c.place("U204", ox, oy, ref_at=(ox - 9, oy - 14), val_at=(ox - 9, oy - 12), just="left")
    yv = u("VIN")[1]
    # input: rail from the PACK_P label, C206 on it, EN tied to VIN
    xl = 38.1
    c.lab(xl, yv, "PACK_P", "L")
    cin = c.vp("C206", 63.5, yv + 6.35, "PACK_P")
    c.w((xl, yv), u("VIN"))
    c.w(cin.top, (cin.top[0], yv)); c.w(cin.bot, (cin.bot[0], cin.bot[1] + 2.54)); c.end(cin.bot[0], cin.bot[1] + 2.54, "GND")
    xj = u("VIN")[0] - 5.08
    c.w(u("EN"), (xj, u("EN")[1]), (xj, yv))
    c.end(u("~{SLEEP}")[0], u("~{SLEEP}")[1], "3V3_SLEEP", "L", stub=2.54)
    c.nc(*u("PG"))
    # grounds under the package
    yb = u("PGND")[1] + 2.54
    for n in ("NC", "PAD", "PGND", "AGND"): c.w(u(n), (u(n)[0], yb))
    c.w((u("NC")[0], yb), (u("AGND")[0], yb)); c.end(u("PGND")[0], yb, "GND")
    # right: SW -> L201 -> 3V3, VOS back to the output node, FB to ground
    ind = c.hp("L201", ox + 30.48, yv, "SW_3V3", txt="above")
    c.w(u("SW"), ind.lft)
    xo = ox + 53.34
    c.w(ind.rgt, (xo, yv))
    c.w(u("VOS"), (xo, u("VOS")[1]))
    cout = c.vp("C207", xo, yv + 6.35, "3V3")
    c.w((xo, yv), cout.top); c.w(cout.bot, (xo, cout.bot[1] + 2.54)); c.end(xo, cout.bot[1] + 2.54, "GND")
    c.w((xo, yv), (xo + 15.24, yv)); c.lab(xo + 15.24, yv, "3V3", "R")
    fb = u("FB"); c.w(fb, (fb[0] + 2.54, fb[1])); c.gdown(fb[0] + 2.54, fb[1])
    c.text("SW_3V3", ox + 10.16 + 2.54, yv - 1.0, 1.27)
    c.note(120, 62, ["EN tied to VIN: always on.  FB to GND: fixed 3.3 V option.  PG unused."], size=1.27)
    c.note(12.7 + 2.54, 70.5, ["3V3_SLEEP: low = sleep mode. MCU DIO21 drives it, R313 (MCU sheet) pulls it high."], size=1.27)
    # ---- bulk ----
    c.frame(12.7, 83.8, 200, 125, "PACK_P shared bulk: 6x 22 uF 35 V 1210 for both chargers and both 5 V bucks")
    yr = 103.0
    c.lab(33.0, yr, "PACK_P", "L"); c.w((33.0, yr), (38.1, yr))
    c.bank([f"C{208 + i}" for i in range(6)], 38.1, yr, "PACK_P", "GND")


def layout_mcu(c):
    ox, oy = 177.8, 71.12
    c.s.paper = (275, 205)
    # ---- module, with its supply, I2C and interrupt pull-ups ----
    c.frame(12.7, 17.78, 262.0, 104.0, "CC2340R5MODA Bluetooth LE module")
    u = c.place("U301", ox, oy, ref_at=(ox - 14, oy - 22), val_at=(ox - 14, oy - 20), just="left")
    H = u.__dict__.setdefault("handled", set())
    # supply: VDDS up to the 3V3 rail, decoupling hanging from it right at the pin
    yr = 39.37
    pv = u("VDDS"); xv = pv[0] - 5.08; H.add(pv)
    c.w(pv, (xv, pv[1]), (xv, yr))
    xs = [xv - 6.35 - 12.7 * i for i in range(3)]
    for r, x in zip(["C302", "C303", "C301"], xs):
        p = c.vp(r, x, yr + 6.35, "3V3", side="L")
        c.w(p.top, (p.top[0], yr)); c.w(p.bot, (p.bot[0], p.bot[1] + 2.54)); c.end(p.bot[0], p.bot[1] + 2.54, "GND")
    x0 = 76.2
    c.pwr(x0, yr, "3V3")
    c.w((x0, yr), (xv, yr))
    c.one("TP301", x0 + 7.62, yr, "U")
    # reset: pull-up and filter cap, tied to the module by label
    c.pin_end(u, "RSTN")
    xr = 104.14
    r302 = c.vp("R302", xr, yr + 6.35, "3V3")
    c.w(r302.top, (xr, yr))
    yn = r302.bot[1] + 2.54
    c.w(r302.bot, (xr, yn))
    c4 = c.vp("C304", xr, yn + 6.35, "NRST")
    c.w((xr, yn), c4.top); c.w(c4.bot, (xr, c4.bot[1] + 2.54)); c.end(xr, c4.bot[1] + 2.54, "GND")
    c.end(xr, yn, "NRST", "L", stub=2.54)
    # left pins: radio and debug nets leave by label
    for k in ("ANT_IN", "RFIO", "DIO16/SWDIO", "DIO17/SWDCK", "GND"): c.pin_end(u, k)
    # right: pull-ups run in line to a 3V3 bus; the net label branches off the wire
    xb = 241.3
    for key, ref, txt, up, dx in (("DIO6_A1", "R304", "above", True, 5.08), ("DIO8", "R305", "below", False, 15.24),
                                  ("DIO21_A10", "R313", "above", True, 15.24), ("DIO11", "R314", "below", False, 5.08)):
        p = u(key); n = c.net("U301", u.names[key][0]); y = p[1]
        rr = c.hp(ref, xb - 12.7, y, n, txt=txt)
        c.w(p, rr.lft); c.w(rr.rgt, (xb, y))
        c.tee(p[0] + dx, y, n, up)
        H.add(p)
    ytop = u("DIO6_A1")[1] - 7.62
    c.w((xb, ytop), (xb, u("DIO11")[1]))
    c.pwr(xb, ytop, "3V3")
    for k in ("DIO18", "DIO20_A11", "DIO12", "DIO24_A7", "DIO3_X32P", "DIO4_X32N"): c.pin_end(u, k)
    c.rest(u)
    c.note(ox + 22, oy + 30, ["R313 holds the 3V3 buck out of sleep while this module is in reset.",
                              "R314: the one IRQ_N pull-up for the whole board (open-drain)."], size=1.27)
    # ---- antenna match ----
    y0 = 110.0
    c.frame(12.7, y0, 135.0, y0 + 40, "Antenna match: pi network from RFIO to ANT_IN")
    y = y0 + 22.86
    c.lab(33, y, "RFIO", "L"); c.w((33, y), (40, y))
    c313 = c.hp("C313", 48, y, "RFIO", txt="above"); c.w((40, y), c313.lft)
    xm = 66.04
    c.w(c313.rgt, (xm, y))
    c314 = c.vp("C314", xm, y + 7.62, "Net-(C313-Pad2)"); c.w((xm, y), c314.top); c.w(c314.bot, (xm, c314.bot[1] + 2.54)); c.end(xm, c314.bot[1] + 2.54, "GND")
    r321 = c.hp("R321", 84, y, "Net-(C313-Pad2)", txt="above"); c.w((xm, y), r321.lft)
    xa = 101.6
    c.w(r321.rgt, (xa, y))
    c315 = c.vp("C315", xa, y + 7.62, "ANT_IN"); c.w((xa, y), c315.top); c.w(c315.bot, (xa, c315.bot[1] + 2.54)); c.end(xa, c315.bot[1] + 2.54, "GND")
    c.w((xa, y), (xa + 7.62, y)); c.lab(xa + 7.62, y, "ANT_IN", "R")
    c.note(16, y0 + 35.0, ["C314 is DNP as on TI's LaunchPad; retune the match on this board."], size=1.27)
    # ---- connectors ----
    c.frame(141.0, y0, 262.0, y0 + 48, "Debug and gauge-training connectors (Tag-Connect, not fitted)")
    j1 = c.place("J301", 170.0, y0 + 25.4, ref_at=(163.0, y0 + 14.0), val_at=(163.0, y0 + 16.0), just="right")
    c.pin_end(j1, "VCC")
    for k in ("SWDIO", "~{RESET}", "SWCLK", "SWO", "GND"): c.pin_end(j1, k)
    c.rest(j1)
    j2 = c.place("J302", 225.0, y0 + 25.4, ref_at=(238, y0 + 11.0), val_at=(238, y0 + 13.0), just="left")
    pg2 = j2("GND"); xg2 = pg2[0] - 5.08
    c.w(pg2, (xg2, pg2[1])); c.gnd_side(xg2, pg2[1], "L"); j2.__dict__.setdefault("handled", set()).add(pg2)
    c.rest(j2)


def layout_cells(c):
    c.s.paper = (440, 232)
    N = lambda r, k: c.net(r, k)
    # ================= gauge =================
    c.frame(12.7, 17.78, 208.28, 190.5, "BQ40Z50 gauge: supply, cell-voltage filters, current sense, SMBus")
    ox, oy = 127.0, 107.95
    u = c.place("U101", ox, oy, ref_at=(ox - 12, oy - 33), val_at=(ox - 12, oy - 31), just="left")
    H = u.__dict__.setdefault("handled", set())
    nb = lambda ref, pin: c.net(ref, u.names[pin][0]) if False else c.net("U101", u.names[pin][0])
    keys = ["BAT", "VCC", "PBI", "PTCEN", "VC4", "VC3", "VC2", "VC1", "SRP", "SRN"]
    rel = [-72.39, -67.31, -62.23, -57.15, -52.07, -41.91, -31.75, -21.59, -6.35, 3.81]
    L = c.lanes(u, keys, "L", [oy + r for r in rel])
    lane = dict(zip(keys, L))
    xs = L[0][0]
    # -- supply lanes --
    x, n = lane["BAT"][0], nb("U101", "BAT")
    x, n = c.chain(*lane["BAT"], ["R105", "D101"], n)
    c.w((x, lane["BAT"][1]), (x - 5.08, lane["BAT"][1])); c.tee(x - 5.08, lane["BAT"][1], n, up=False, d="R", stub=3.81)
    j116 = c.one("J116", x - 10.16, lane["BAT"][1], "R", txt="L"); c.w((x - 5.08, lane["BAT"][1]), j116.pin)
    x, n = c.chain(*lane["VCC"], ["R106"], nb("U101", "VCC")); c.end(x, lane["VCC"][1], n, "L")
    x, n = c.chain(*lane["PBI"], ["C105"], nb("U101", "PBI")); c.w((x, lane["PBI"][1]), (x - 2.54, lane["PBI"][1])); c.gnd_side(x - 2.54, lane["PBI"][1], "L", "CELL_1N")
    px_, py_ = lane["PTCEN"]; c.w((px_, py_), (px_ - 2.54, py_)); c.gnd_side(px_ - 2.54, py_, "L", "CELL_1N")
    # -- cell inputs: R in line, caps stacked between the lanes, one per cell, then the pad --
    vc = ["VC4", "VC3", "VC2", "VC1"]; Rs = ["R104", "R103", "R102", "R101"]; Cs = ["C101", "C102", "C103", "C104"]
    pads = ["J116", "J111", "J110", "J109"]
    xcap = xs - 12.7
    for i, k in enumerate(vc):
        x0, y = lane[k]
        c.w((x0, y), (xcap, y))
        if i < 3:
            y2 = lane[vc[i + 1]][1]
            cp = c.vp(Cs[i], xcap, (y + y2) / 2, nb("U101", k))
            c.w((xcap, y), cp.top); c.w(cp.bot, (xcap, y2))
        else:
            cp = c.vp("C104", xcap, y + 6.35, nb("U101", k))
            c.w((xcap, y), cp.top); c.w(cp.bot, (cp.bot[0] + 2.54, cp.bot[1])); c.gnd_side(cp.bot[0] + 2.54, cp.bot[1], "R", "CELL_1N")
            c.w(cp.bot, (cp.bot[0], cp.bot[1] + 1.27)) if False else None
    for i, k in enumerate(vc):
        if k == "VC4": continue
        x, n = c.chain(xcap, lane[k][1], [Rs[i]], nb("U101", k))
        pad = pads[i]
        c.w((x, lane[k][1]), (x - 5.08, lane[k][1])); c.tee(x - 5.08, lane[k][1], n, up=False, d="R", stub=3.81)
        pp = c.one(pad, x - 10.16, lane[k][1], "R", txt="L"); c.w((x - 5.08, lane[k][1]), pp.pin)
    # VC4's own R104 shares CELL_4P with D101's lane: wire it to the same net by label
    x, n = c.chain(xcap, lane["VC4"][1], [Rs[0]], nb("U101", "VC4")); c.end(x, lane["VC4"][1], n, "L")
    # -- current sense: R107/R108 in line, C106 across, RS101 in the return path --
    ys_p, ys_n = lane["SRP"][1], lane["SRN"][1]
    c.w((lane["SRP"][0], ys_p), (xcap, ys_p)); c.w((lane["SRN"][0], ys_n), (xcap, ys_n))
    cp = c.vp("C106", xcap, (ys_p + ys_n) / 2, nb("U101", "SRP"))
    c.w((xcap, ys_p), cp.top); c.w(cp.bot, (xcap, ys_n))
    x1, _ = c.chain(xcap, ys_p, ["R107"], nb("U101", "SRP"))
    x2, _ = c.chain(xcap, ys_n, ["R108"], nb("U101", "SRN"))
    xr = min(x1, x2) - 7.62
    rs = c.vp("RS101", xr, (ys_p + ys_n) / 2, "CELL_N", side="L")
    c.w((x1, ys_p), (xr, ys_p)); c.w((xr, ys_p), rs.top)
    c.w((x2, ys_n), (xr, ys_n)); c.w(rs.bot, (xr, ys_n))
    j108 = c.one("J108", xr, ys_p - 7.62, "D", txt="L"); c.w((xr, ys_p), j108.pin)
    c.w((xr, ys_n), (xr, ys_n + 10.16)); c.end(xr, ys_n + 10.16, "GND")
    j114 = c.one("J114", xr - 7.62, ys_n + 5.08, "R", txt="L"); c.w((xr, ys_n + 5.08), j114.pin)
    tp109 = c.one("TP109", xr + 7.62, ys_n + 5.08, "L"); c.w((xr, ys_n + 5.08), tp109.pin)
    c.note(xr - 28, ys_n + 17.5, ["Kelvin: R107/R108 tap RS101 pads"], size=1.27)
    # -- PACK: R113 straight out of the pin --
    pk = u("PACK"); H.add(pk)
    x, n = c.chain(pk[0], pk[1], ["R113"], nb("U101", "PACK")); c.end(x, pk[1], n, "L")
    # -- thermistor lanes below --
    tk = ["TS1", "TS2", "TS3", "TS4", "PTC"]
    T = c.lanes(u, tk, "L", [oy + r for r in (19.05, 26.67, 34.29, 41.91, 49.53)])
    t = dict(zip(tk, T)); xt = T[0][0]
    x, n = c.chain(*t["TS1"], ["TH101"], nb("U101", "TS1")); c.gdown(x, t["TS1"][1], net="CELL_1N")
    j117 = c.one("J117", xt - 3.81, t["TS2"][1], "R", txt="L"); c.w(t["TS2"], j117.pin)
    j119 = c.one("J119", xt - 3.81, t["TS3"][1], "R", txt="L"); c.w(t["TS3"], j119.pin)
    x, n = c.chain(*t["TS4"], ["TH104"], nb("U101", "TS4")); c.gdown(x, t["TS4"][1], net="CELL_1N")
    yp_ = t["PTC"][1]; xe = xt - 62
    c.w(t["PTC"], (xe, yp_)); c.gdown(xe, yp_, net="CELL_1N")
    for k, ref in enumerate(["J115", "J118", "J120"]):
        c.one(ref, xt - 6 - 24 * k, yp_, "U", txt="R")
    c.note(xt - 62, yp_ + 14.0, ["Cell NTCs: TH101/TH104 on the board, TS2/TS3 on wires"], size=1.27)
    # ---- right side ----
    for k in ("CHG", "DSG", "FUSE"): c.pin_end(u, k)
    c.pin_end(u, "PCHG")
    xo_ = 30.48
    for key, ref, txt in (("SMBC", "R115", "line"), ("SMBD", "R116", "linebelow")):
        p = u(key); n = nb("U101", key); y = p[1]
        rr = c.hp(ref, p[0] + xo_, y, n, txt=txt)
        c.w(p, rr.lft); c.end(rr.rgt[0], y, c.net(ref, "2") if False else [m for m in c.ends(ref)[1] if m != n][0], "R")
        H.add(p)
    pp_, pd_ = u("PRES/SHUTDN"), u("DISP")
    c.w(pp_, (pp_[0] + 2.54, pp_[1]), (pp_[0] + 2.54, pd_[1]), pd_)
    c.gdown(pp_[0] + 2.54, pd_[1], net="CELL_1N")
    H.update([pp_, pd_])
    pb = u("BTP_INT"); H.add(pb)
    yq = oy + 12.7; xv = pb[0] + 15.24
    q3 = c.place("Q103", xv + 10.16, yq, ref_at=(xv + 15.24, yq - 3.0), val_at=(xv + 15.24, yq - 1.0), just="left")
    c.w(pb, (xv, pb[1]), (xv, yq), q3("G"))
    r117 = c.vp("R117", xv + 3.81, yq + 6.35, "BTP_INT")
    c.w((xv + 3.81, yq), r117.top); c.end(r117.bot[0], r117.bot[1], "CELL_1N")
    c.pin_end(q3, "D"); c.pin_end(q3, "S")
    c.note(xv - 4, yq + 24, ["Q103 level-shifts BTP_INT onto the shared", "open-drain IRQ_N line (inverting)"], size=1.27)
    c.rest(u)

    # ================= pack power path =================
    X0, Y0 = 215.9, 17.78
    c.frame(X0, Y0, 432.0, 104.14, "Pack power path: cells, fuse, back-to-back protection FETs, load")
    yp = 50.8
    XF = X0 + 60.96
    f = c.place("F102", XF, yp, ref_at=(XF, yp - 9.5), val_at=(XF, yp - 7.5), just="center")
    j112 = c.one("J112", X0 + 30.48, yp, "R", txt="above"); c.w(j112.pin, f("1"))
    x1 = X0 + 125.0; x2 = x1 + 38.1
    q1 = c.place("Q101", x1, yp + 6.35, 90, True, ref_at=(x1, yp - 6.2), val_at=(x1, yp - 4.2), just="center")
    q2 = c.place("Q102", x2, yp + 6.35, 90, False, ref_at=(x2, yp - 6.2), val_at=(x2, yp - 4.2), just="center")
    assert q1("S")[1] == yp and q1("S")[0] < q1("D")[0] and q2("D")[0] < q2("S")[0], (q1("S"), q1("D"), q2("D"), q2("S"))
    c.w(f("2"), q1("S"))
    c.w(q1("D"), q2("D"))
    c.lab((q1("D")[0] + q2("D")[0]) / 2 - 4.0, yp, "FET_MID", "R")
    yn = q1("G")[1] + 5.08
    # CELL_P tap lines: wake resistor and the CHG gate resistor
    xw = X0 + 84.0
    r118 = c.vp("R118", xw, yp + 6.35, "CELL_P"); c.w((xw, yp), r118.top)
    tp113 = c.one("TP113", xw, r118.bot[1] + 2.54, "U"); c.w(r118.bot, tp113.pin)
    xc = x1 - 12.7
    c.w((xc, yp), (xc, yn))
    r110 = c.hp("R110", (xc + q1("G")[0]) / 2, yn, "CELL_P"); c.w((xc, yn), r110.lft); c.w(r110.rgt, (q1("G")[0], yn))
    # PACK_P side
    xp2 = x2 + 12.7
    c.w(q2("S"), (x2 + 31.75, yp))
    c.w((xp2, yp), (xp2, yn + 10.16))
    r112 = c.hp("R112", (q2("G")[0] + xp2) / 2, yn, "DSG_G"); c.w((q2("G")[0], yn), r112.lft); c.w(r112.rgt, (xp2, yn))
    d103 = c.hp("D103", (q2("G")[0] + xp2) / 2, yn + 10.16, "DSG_G"); c.w((q2("G")[0], yn + 10.16), d103.lft); c.w(d103.rgt, (xp2, yn + 10.16))
    for q, rg, nm in ((q1, "R109", "CHG"), (q2, "R111", "DSG")):
        gx = q("G")[0]; y0_ = yn + (10.16 if q is q2 else 0)
        gate = "CHG_G" if q is q1 else "DSG_G"
        rv = c.vp(rg, gx, y0_ + 6.35, gate)
        c.w((gx, q("G")[1]), (gx, y0_ + 2.54))
        c.w(rv.bot, (rv.bot[0], rv.bot[1] + 2.54)); c.lab(rv.bot[0], rv.bot[1] + 2.54, nm, "R")
    # ESD pair across both FETs
    yc = yp - 17.78
    xu1 = x1 - 17.78; xa2 = x2 + 20.32
    c.w((xu1, yp), (xu1, yc))
    c110 = c.hp("C110", x1 - 2.54, yc, "CELL_P"); c.w((xu1, yc), c110.lft)
    c111 = c.hp("C111", x2 + 2.54, yc, "Net-(C110-Pad2)"); c.w(c110.rgt, c111.lft)
    c.w(c111.rgt, (xa2, yc), (xa2, yp))
    c.note(xa2 + 3, yc + 0.6, ["ESD: two caps in series", "across both FETs"], size=1.27)
    # output: pads, bulk pair, label
    xo = x2 + 31.75
    c.lab(xo + 12.7, yp, "PACK_P", "R"); c.w((xo, yp), (xo + 12.7, yp))
    c.one("J113", xo - 16.0, yp, "D", txt="above"); c.one("TP106", xo + 4.0, yp, "D", txt="above")
    c107 = c.vp("C107", xo, yp + 6.35, "PACK_P"); c.w((xo, yp), c107.top)
    c108 = c.vp("C108", xo, c107.bot[1] + 6.35 + 2.54, "PACK_CMID"); c.w(c107.bot, c108.top)
    c.w(c108.bot, (xo, c108.bot[1] + 2.54)); c.end(xo, c108.bot[1] + 2.54, "GND")
    # fuse heater and its driver
    xq = XF - 2.54
    q4 = c.place("Q104", xq, yp + 25.4, ref_at=(xq + 5.08, yp + 24.0), val_at=(xq + 5.08, yp + 26.0), just="left")
    c.w(f("3"), (XF, q4("D")[1] - 0)) if False else None
    c.w(f("HTR"), q4("D"))
    c.pin_end(q4, "S")
    q4.__dict__.setdefault("handled", set()).update({q4("G"), q4("D")})
    xg = q4("G")[0] - 12.7
    yG = q4("G")[1]
    c.w(q4("G"), (xg - 12.7, yG))
    r125 = c.vp("R125", xg, yG + 6.35, "Net-(Q104-G)"); c.w((xg, yG), r125.top); c.end(xg, r125.bot[1], "GND")
    c118 = c.vp("C118", xg - 12.7, yG + 6.35, "Net-(Q104-G)"); c.w((xg - 12.7, yG), c118.top); c.end(xg - 12.7, c118.bot[1], "CELL_1N")
    c.w((xg, yG), (xg, yG - 15.24))
    for k, (ref, y_) in enumerate((("R124", yG - 7.62), ("R126", yG - 15.24))):
        x_, n_ = c.chain(xg, y_, [ref], "Net-(Q104-G)")
        c.end(x_, y_, n_, "L")
    c.rest(q4)
    c.note(X0 + 6, yp + 50, ["Ground symbols on this sheet are CELL_1N, the gauge sense ground (not the board GND)."], size=1.27)
    c.note(X0 + 6, yp + 44, ["F102 is the only fuse in the pack path. Q104 heats it when U102 trips."], size=1.27)

    # ================= second-level protector =================
    UY = 110.0
    c.frame(X0, UY, 432.0, 183.0, "BQ294700 second-level protector: cell inputs, OUT drives the fuse heater")
    ox2, oy2 = X0 + 135.0, UY + 40.0
    u2 = c.place("U102", ox2, oy2, ref_at=(ox2 - 8, oy2 - 20), val_at=(ox2 - 8, oy2 - 18), just="left")
    pins2 = ["V4", "V3", "V2", "V1"]
    px = u2("V4")[0]; xcap2 = px - 12.7
    ys2 = [u2(k)[1] for k in pins2]
    for k in pins2: c.w(u2(k), (xcap2, u2(k)[1]))
    Cs2 = ["C112", "C113", "C114"]
    for i in range(3):
        cp = c.vp(Cs2[i], xcap2, (ys2[i] + ys2[i + 1]) / 2, c.net("U102", u2.names[pins2[i]][0]))
        c.w((xcap2, ys2[i]), cp.top); c.w(cp.bot, (xcap2, ys2[i + 1]))
    cp = c.vp("C115", xcap2, ys2[3] + 6.35, c.net("U102", u2.names["V1"][0]))
    c.w((xcap2, ys2[3]), cp.top); c.gdown(cp.bot[0], cp.bot[1], net="CELL_1N")
    for i, (k, r) in enumerate(zip(pins2, ["R119", "R120", "R121", "R122"])):
        x_, n_ = c.chain(xcap2, ys2[i], [r], c.net("U102", u2.names[k][0]))
        c.end(x_, ys2[i], n_, "L")
        u2.__dict__.setdefault("handled", set()).add(u2(k))
    # right side: VDD with C116 and R123, VSS, CD with C117, OUT
    hh = u2.__dict__.setdefault("handled", set())
    pv_ = u2("VDD"); hh.add(pv_)
    xn = pv_[0] + 20.32
    c.w(pv_, (xn, pv_[1]))
    c116 = c.vp("C116", xn - 7.62, pv_[1] + 6.35, c.net("U102", u2.names["VDD"][0]))
    c.w((xn - 7.62, pv_[1]), c116.top); c.w(c116.bot, (c116.bot[0] + 2.54, c116.bot[1])); c.gnd_side(c116.bot[0] + 2.54, c116.bot[1], "R", "CELL_1N")
    pcd = u2("CD"); hh.add(pcd)
    c.w(pcd, (pcd[0] + 17.0, pcd[1]))
    c117 = c.vp("C117", pcd[0] + 17.0, pcd[1] + 6.35, c.net("U102", u2.names["CD"][0]))
    c.w((pcd[0] + 17.0, pcd[1]), c117.top); c.end(*c117.bot, "CELL_1N")
    rr = c.hp("R123", xn + 6.35, pv_[1], c.net("U102", u2.names["VDD"][0]))
    c.w((xn, pv_[1]), rr.lft); c.end(rr.rgt[0], pv_[1], "CELL_4P", "R")
    c.pin_end(u2, "VSS"); c.pin_end(u2, "OUT")
    c.rest(u2)
    c.note(X0 + 6, UY + 70, ["CD delay about 1 to 2 s (0.1 uF). RIN must be 1k: the part is calibrated with it."], size=1.27)
    assert not [r for r in c.comps if c.comps[r]["block"] == "Cells and Gauge" and r not in c.drawn], [r for r in c.comps if c.comps[r]["block"] == "Cells and Gauge" and r not in c.drawn]

from layout_usb import layout_usb
LAYOUTS = {"3V3 Rail": layout_3v3, "MCU": layout_mcu, "Cells and Gauge": layout_cells,
           "USB Port 1": lambda c: layout_usb(c, 400), "USB Port 2": lambda c: layout_usb(c, 500)}
