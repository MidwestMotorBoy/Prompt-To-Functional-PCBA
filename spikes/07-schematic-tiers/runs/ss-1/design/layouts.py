"""Hand layouts: how a person would draw the small circuits of a block. Each function draws one section through the
Hand helper (hand.py), in units of 2.54 mm from the section origin. The sections not named here are drawn by draw.py."""

def pad(h, ref, x, y):
    """A wire pad or test point: body left of its pin, net name after the pin, then reference and description."""
    net = h.pinnet[(ref, "1")]
    conn = h.comps[ref]["lib"].startswith("Connector_Generic")
    dx = len(h.short(net)) * 0.42 + 1.4 + (2.0 if conn else 0)
    h.put(ref, x - (2 if conn else 0), y, 180 if conn else 90, ref_at=(dx, -0.3), val_at=(dx + (len(ref) + 1) * 0.5, -0.3), just="left")
    h.lab(f"{ref}.1", "R")

def pads(h):
    h.title("Cell tabs", 0, 0.2)
    for i, r in enumerate(["J108", "J115"]): pad(h, r, 6, 3 + i * 2.5)
    h.title("Load side", 0, 9)
    for i, r in enumerate(["J113", "J114", "TP106", "TP109"]): pad(h, r, 6, 12 + i * 2.5)
    h.title("Cell NTC wires", 0, 23)
    for i, r in enumerate(["J117", "J118", "J119", "J120"]): pad(h, r, 6, 26 + i * 2.5)

def gauge_supply(h):
    h.put("D101", 8, 3, 180, ref_at=(-2, 1.6), val_at=(-2, 2.6), just="left")
    h.lab("D101.2", "L", "CELL_4P"); h.lab("D101.1", "R")
    h.note("BAT is fed from the cell 4 top, ahead of the fuse", 0, 7, 1.0)

def gauge(h):
    cx, cy = 52, 26
    H = h
    H.put("U101", cx, cy, 0, ref_at=(-5, -13.2), val_at=(-5, -12.2), just="left")
    # ---- right side: outputs and SMBus, short stubs to labels ----
    for p in ("31", "28", "25"): H.stub(f"U101.{p}", "R", 1.5)
    H.lab("U101.30", "R")
    H.put("R115", cx + 15, cy - 4.5, 90, lab="t"); H.w("U101.19", "R115.1"); H.lab("R115.2", "R")
    H.put("R116", cx + 24, cy - 3.5, 90, lab="b"); H.w("U101.18", "R116.1"); H.lab("R116.2", "R")
    H.stub("U101.15", "R", 1.5)
    for p in ("16", "17", "9"): H.stub(f"U101.{p}", "R", 1.5)
    for p in ("20", "21", "22", "7"): H.lab(f"U101.{p}", "R")
    # ---- left lower pins: labels only, kept short so the cell-filter wires pass clear of them ----
    for p in ("8", "6", "27", "10", "11", "12", "13", "23", "24"): H.stub(f"U101.{p}", "L", 1)
    # ---- cell filter ladder: tap, series R, capacitor between neighbouring cell lines, CELL_1N below ----
    PX, RX, CX = cx - 40, cx - 31, cx - 24
    lanes = {"4": cy + 10, "3": cy + 16, "2": cy + 22, "1": cy + 28}
    pads = {"4": "J116", "3": "J111", "2": "J110", "1": "J109"}
    res = {"4": "R104", "3": "R103", "2": "R102", "1": "R101"}
    turn = {"1": cx - 12, "2": cx - 14, "3": cx - 16, "4": cx - 18}
    pin = {"4": "2", "3": "3", "2": "4", "1": "5"}
    for k in "4321":
        y = lanes[k]
        H.put(res[k], RX, y, 90, lab="t")
        H.put(pads[k], PX, y, 90, ref_at=(-4, -1.8), val_at=(-4, -0.8), just="left")
        H.w(f"{pads[k]}.1", f"{res[k]}.1"); H.lab((PX + 4, y), "R", H.net(f"{pads[k]}.1"))
        H.w(f"U101.{pin[k]}", (turn[k], None), (turn[k], y), f"{res[k]}.2")
    for a, b, c in (("4", "3", "C101"), ("3", "2", "C102"), ("2", "1", "C103")):
        H.put(c, CX, (lanes[a] + lanes[b]) / 2, 0)
        H.w((CX, lanes[a]), f"{c}.1"); H.w(f"{c}.2", (CX, lanes[b]))
    H.put("C104", CX, lanes["1"] + 3, 0); H.w((CX, lanes["1"]), "C104.1")
    H.w("C104.2", (CX, lanes["1"] + 6), (CX - 5, lanes["1"] + 6)); H.lab((CX - 5, lanes["1"] + 6), "L", "CELL_1N")
    # ---- supply pins: cell 4 tap through the BAT diode and R105, R106 from the FET midpoint, PBI capacitor ----
    yb, yv, yp = cy - 16, cy - 12.5, cy - 9
    H.w("U101.32", (cx - 6, None), (cx - 6, yb))
    H.put("R105", cx - 12, yb, 90, lab="t"); H.w((cx - 6, yb), "R105.2")
    H.put("D101", cx - 17, yb, 180, ref_at=(-2, 1.4), val_at=(-2, 2.4), just="left"); H.w("R105.1", "D101.1")
    H.w("D101.2", (PX + 2, yb), (PX + 2, lanes["4"]))
    H.w((PX + 2, lanes["4"]), (PX + 2, lanes["4"]))
    H.w("U101.26", (cx - 8, None), (cx - 8, yv)); H.put("R106", cx - 13, yv, 90, lab="t")
    H.w((cx - 8, yv), "R106.2"); H.lab("R106.1", "L")
    H.w("U101.1", (cx - 10, None), (cx - 10, yp), (cx - 15, yp))
    H.put("C105", cx - 15, yp + 2.5, 0); H.w((cx - 15, yp), "C105.1"); H.stub("C105.2", "L", 1)
    H.stub("U101.24", "L", 1)
    # ---- the rest: pack sense resistor and the on-board cell NTCs ----
    H.put("R113", cx - 8, cy + 20, 90, lab="t"); H.lab("R113.1", "L"); H.lab("R113.2", "R")
    H.put("TH101", cx + 4, cy + 26, 0); H.stub("TH101.1", "U", 1); H.stub("TH101.2", "D", 1)
    H.put("TH104", cx + 12, cy + 26, 0); H.stub("TH104.1", "U", 1); H.stub("TH104.2", "D", 1)
    H.note("Cell NTCs on the board (TS1, TS4)", cx + 2, cy + 32, 1.0)

def current_sense(h):
    h.put("RS101", 6, 8, 0, lab="l")
    h.w("RS101.1", (6, 5)); h.lab((6, 5), "L", "CELL_N")
    h.put("R107", 11, 5, 90, lab="t"); h.w((6, 5), "R107.1")
    h.put("R108", 11, 11, 90, lab="t"); h.w("RS101.2", (6, 11), "R108.1"); h.w((6, 11), (6, 13)); h.gnd((6, 13), "D")
    h.put("C106", 15, 8, 0)
    h.w("R107.2", (15, 5), "C106.1"); h.w((15, 5), (19, 5)); h.lab((19, 5), "R", "SRP")
    h.w("R108.2", (15, 11), "C106.2"); h.w((15, 11), (19, 11)); h.lab((19, 11), "R", "SRN")
    h.note("Kelvin taps to the gauge", 0, 15, 1.0)

def protection(h):
    h.put("Q101", 14, 10, 0, ref_at=(-2.5, -3.5), val_at=(-2.5, -2.5))
    h.put("Q102", 24, 10, 0, mirror=True, ref_at=(-2.5, -3.5), val_at=(-2.5, -2.5))
    h.w("Q101.5", "Q102.5"); h.lab((17.5, 9.5), "R", "FET_MID")
    # charge FET gate
    h.put("R109", 7, 9.5, 90, lab="t"); h.lab("R109.1", "L")
    h.w("R109.2", "Q101.4")
    h.put("R110", 10, 12, 0); h.w((10, 9.5), "R110.1")
    # power path rails: CELL_P in from the left, PACK_P out to the right
    h.w("Q101.1", (16.5, 13.5), (8, 13.5)); h.lab((8, 13.5), "L", "CELL_P")
    h.w("Q102.1", (21.5, 13.5), (42, 13.5)); h.lab((42, 13.5), "R", "PACK_P")
    h.w("R110.2", (10, 13.5))
    # discharge FET gate
    h.put("R111", 33, 9.5, 270, lab="t"); h.lab("R111.1", "R")
    h.w("Q102.4", "R111.2")
    h.put("R112", 29, 12, 0, lab="l"); h.w((29, 9.5), "R112.1"); h.w("R112.2", (29, 13.5))
    h.put("D103", 31, 12, 270, ref_at=(1.5, -0.5), val_at=(1.5, 0.7)); h.w((31, 9.5), "D103.1"); h.w("D103.2", (31, 13.5))
    # ESD capacitors in series across both FETs
    h.put("C110", 14, 17, 0); h.w((14, 13.5), "C110.1")
    h.put("C111", 24, 17, 180); h.w((24, 13.5), "C111.2")
    h.w("C110.2", (14, 20), (24, 20), "C111.1")
    # capacitive divider on the pack side
    h.put("C107", 39, 17, 0); h.w((39, 13.5), "C107.1")
    h.put("C108", 39, 21, 0); h.w("C107.2", "C108.1"); h.gnd("C108.2", "D")
    # wake pull-up
    h.put("R118", 10, 17, 0, lab="l"); h.w((10, 13.5), "R118.1")
    h.w("R118.2", (10, 20)); h.put("TP113", 10, 20, 180, ref_at=(1, 1), val_at=(1, 2))
    h.note("Q101 charge and Q102 discharge, back to back (common drain)", 6, 6, 1.0)

def fuse(h):
    h.put("J112", 7, 4, 90, ref_at=(-6, -2.0), val_at=(-3.6, -2.0), just="left")
    h.put("F102", 14, 4, 0, ref_at=(-2.5, -3.5), val_at=(-2.5, -2.5), just="left")
    h.w("J112.1", "F102.1"); h.w("F102.2", (18, 4)); h.lab((18, 4), "R", "CELL_P")
    h.put("Q104", 13, 12, 0, ref_at=(2.5, -0.6), val_at=(2.5, 0.6))
    h.w("F102.3", "Q104.3"); h.gnd("Q104.2", "D")
    h.put("R124", 2, 8, 90, lab="t"); h.lab("R124.1", "L")
    h.put("R126", 2, 12, 270, lab="t"); h.lab("R126.2", "L")
    h.w("R124.2", (5.5, 8), (5.5, 12), "Q104.1"); h.w("R126.1", (5.5, 12))
    h.put("R125", 5.5, 16, 0, lab="l"); h.w((5.5, 12), (5.5, 14.5))
    h.gnd("R125.2", "D")
    h.put("C118", 9, 16, 0); h.w((9, 12), "C118.1"); h.w("C118.2", (9, 19)); h.lab((9, 19), "R", "CELL_1N")
    h.note("Gauge FUSE pin or the second-level protector ignites the heater", 0, 21, 1.0)

def interrupt(h):
    h.put("Q103", 10, 6, 0)
    h.w("Q103.1", (4, 6)); h.lab((4, 6), "L", "BTP_INT")
    h.put("R117", 6, 8.5, 0, lab="l"); h.w((4, 6), (4, 7), "R117.1") if False else h.w((6, 6), "R117.1"); h.w("R117.2", (6, 10.5)); h.lab((6, 10.5), "R", "CELL_1N")
    h.lab("Q103.3", "U"); h.gnd("Q103.2", "D")

def usb_c(n):
    J, D, U, C1, C2, CB, C50, CV, CP = (f"J{n+1}", f"D{n+1}", f"U{n+5}", f"C{n+1}", f"C{n+2}", f"C{n+6}", f"C{n+50}",
                                       f"C{n+51}", f"C{n+52}")
    def fn(h):
        h.put(J, 8, 16, 0, ref_at=(-6, -9.5), val_at=(-6, -8.5), just="left")
        # VBUS rail across the top with the port protection hung from it
        h.w(f"{J}.A4", (16, 10), (16, 2), (42, 2)); h.lab((42, 2), "R", h.net(f"{J}.A4"))
        h.put(CB, 29, 5, 0); h.w((29, 2), f"{CB}.1"); h.gnd(f"{CB}.2", "D")
        h.put(C50, 35, 5, 0); h.w((35, 2), f"{C50}.1"); h.gnd(f"{C50}.2", "D")
        h.put(D, 22, 6, 0, ref_at=(-3, -5.8), val_at=(-3, -4.8), just="left"); h.w((22, 2), f"{D}.4"); h.gnd(f"{D}.1", "D")
        # D+ and D- tied together: dedicated charging port, no data
        for p in ("A7", "B7", "A6", "B6"): h.w(f"{J}.{p}", (16, None))
        h.w((16, 15), (16, 18)); h.lab((16, 16.5), "R", h.net(f"{J}.A7"))
        for p in ("A8", "B8"): h.lab(f"{J}.{p}", "R")
        h.w(f"{J}.SH", f"{J}.A1"); h.gnd(f"{J}.A1", "D")
        # CC lines through the port protection
        h.put(U, 46, 16.5, 0, ref_at=(-6, 10), val_at=(-6, 11), just="left")
        h.w(f"{J}.A5", f"{U}.4"); h.lab((20, 12), "R", h.net(f"{J}.A5"))
        h.w(f"{J}.B5", f"{U}.5"); h.lab((20, 13), "R", h.net(f"{J}.B5"))
        h.stub(f"{U}.7", "L"); h.stub(f"{U}.6", "L")
        for p in ("1", "2", "20", "19"): h.lab(f"{U}.{p}", "L")
        h.w(f"{U}.12", (62, 12)); h.lab((62, 12), "R", h.net(f"{U}.12"))
        h.w(f"{U}.11", (62, 13)); h.lab((62, 13), "R", h.net(f"{U}.11"))
        h.put(C1, 56, 9, 180); h.w((56, 12), f"{C1}.1"); h.gnd(f"{C1}.2", "U")
        h.put(C2, 59, 16, 0); h.w((59, 13), f"{C2}.1"); h.gnd(f"{C2}.2", "D")
        h.lab(f"{U}.15", "R"); h.lab(f"{U}.14", "R")
        h.w(f"{U}.9", (56, 21)); h.lab((56, 21), "R", h.net(f"{U}.9"))
        # supplies of the protector: 3.3 V from the PD controller LDO, bias capacitor
        h.put(CP, 43, 6.5, 180); h.w(f"{U}.10", f"{CP}.1"); h.gnd(f"{CP}.2", "U")
        h.w(f"{CP}.1", (40, 8)); h.lab((40, 8), "L", h.net(f"{U}.10"))
        h.put(CV, 50, 6.5, 180); h.w(f"{U}.3", (47, 9), (50, 9), f"{CV}.1"); h.gnd(f"{CV}.2", "U")
        h.w(f"{U}.8", (45, 22)); h.w(f"{U}.16", (47, 22)); h.w((45, 22), (47, 22)); h.gnd((45, 22), "D")
    return fn

def usb_eeprom(n):
    E, C8 = f"U{n+2}", f"C{n+8}"
    pulls = [f"R{n+2}", f"R{n+3}", f"R{n+4}", f"R{n+41}"]
    def fn(h):
        h.w((2, 2), (22, 2)); h.lab((2, 2), "L", h.net(f"{pulls[0]}.1"))
        for i, r in enumerate(pulls):
            x = 4 + 6 * i
            h.put(r, x, 5, 0); h.w((x, 2), f"{r}.1"); h.w(f"{r}.2", (x, 8), (x + 1, 8)); h.lab((x + 1, 8), "R", h.net(f"{r}.2"))
        h.w((22, 2), (40, 2))
        h.put(C8, 28, 5, 0); h.w((28, 2), f"{C8}.1"); h.gnd(f"{C8}.2", "D")
        h.put(E, 40, 9, 0, ref_at=(-8, 7.2), val_at=(-8, 8.2), just="left")
        h.w(f"{E}.8", (40, 2))
        for p in ("1", "2", "3"): h.w(f"{E}.A{int(p)-1}" if False else f"{E}.{p}", (34, None))
        h.w((34, 8), (34, 10)); h.gnd((34, 10), "D")
        h.stub(f"{E}.5", "R", 1.5); h.stub(f"{E}.6", "R", 1.5)
        h.stub(f"{E}.7", "R", 1.5, "GND"); h.gnd(f"{E}.4", "D")
        h.note("EEPROM holds the PD controller configuration", 22, 21, 1.0)
    return fn

def mcu_module(h):
    cx, cy = 40, 14
    h.put("U301", cx, cy, 0, ref_at=(-5, -9.2), val_at=(-5, -8.2), just="left")
    # supply rail with the decoupling at the VDDS pin
    rail = cy - 12
    h.w((cx - 40, rail), (cx - 9, rail)); h.lab((cx - 40, rail), "L", h.net("U301.6"))
    h.w("U301.6", (cx - 9, None), (cx - 9, rail))
    for ref, x in (("C303", cx - 14), ("C302", cx - 20), ("C301", cx - 26)):
        h.put(ref, x, rail + 2.5, 0); h.w((x, rail), f"{ref}.1"); h.gnd(f"{ref}.2", "D")
    # reset: pull-up from the rail, filter capacitor to ground
    h.put("R302", cx - 33, cy - 8, 0, lab="l"); h.w((cx - 33, rail), "R302.1")
    h.w("R302.2", (cx - 33, cy - 4)); h.w("U301.14", (cx - 33, None)); h.lab((cx - 12, cy - 4), "R", "NRST")
    h.put("C304", cx - 33, cy - 1.5, 0, lab="l"); h.w((cx - 33, cy - 4), "C304.1"); h.gnd("C304.2", "D")
    for p in ("3", "4", "20", "19"): h.stub(f"U301.{p}", "L", 1)
    h.gnd("U301.1", "L")
    # right side: I2C with its pull-ups on the lines, GPIO lines straight to labels
    def pull(ref, row_pin, x, up=True):
        px, py = h.pin("U301", row_pin)
        yy = (py - h.oy) / 2.54 + 0 if False else None
    ry = lambda off: cy + off
    h.put("R304", cx + 9, ry(-7.5), 0, lab="r"); h.w("U301.9", "R304.2") if False else None
    # SCL
    h.w("U301.9", (cx + 9, ry(-6)), (cx + 12, ry(-6))); h.lab((cx + 12, ry(-6)), "R", h.net("U301.9"))
    h.w("R304.2", (cx + 9, ry(-6))); h.w("R304.1", (cx + 9, ry(-10))); h.lab((cx + 9, ry(-10)), "R", "3V3")
    # SDA
    h.put("R305", cx + 17, ry(-7.5) + 1, 0, lab="r")
    h.w("U301.10", (cx + 17, ry(-5)), (cx + 20, ry(-5))); h.lab((cx + 20, ry(-5)), "R", h.net("U301.10"))
    h.w("R305.2", (cx + 17, ry(-5))); h.w("R305.1", (cx + 17, ry(-10))); h.lab((cx + 17, ry(-10)), "R", "3V3")
    h.stub("U301.16", "R", 1.5)
    h.lab("U301.17", "R"); h.lab("U301.18", "R")
    for p in ("11", "12", "13"): h.stub(f"U301.{p}", "R", 1.5)
    # sleep line with its pull-up above, IRQ_N with its pull-up below
    h.put("R313", cx + 26, ry(4) - 2.5, 0, lab="r")
    h.w("U301.15", (cx + 26, ry(4)), (cx + 29, ry(4))); h.lab((cx + 29, ry(4)), "R", h.net("U301.15"))
    h.w("R313.2", (cx + 26, ry(4))); h.w("R313.1", (cx + 26, ry(4) - 5)); h.lab((cx + 26, ry(4) - 5), "R", "3V3")
    h.put("R314", cx + 10, ry(6) + 2.5, 180, lab="r")
    h.w("U301.21", (cx + 10, ry(6)), (cx + 14, ry(6))); h.lab((cx + 14, ry(6)), "R", h.net("U301.21"))
    h.w("R314.2", (cx + 10, ry(6))); h.w("R314.1", (cx + 10, ry(6) + 6)); h.lab((cx + 10, ry(6) + 6), "R", "3V3")

def antenna(h):
    h.put("C313", 7, 4, 90, lab="t"); h.w((2, 4), "C313.1"); h.lab((2, 4), "L", h.net("C313.1"))
    h.put("R321", 14, 4, 90, lab="t"); h.w("C313.2", (10, 4), "R321.1")
    h.put("C314", 10, 7.5, 0); h.w((10, 4), "C314.1"); h.gnd("C314.2", "D")
    h.put("C315", 17.5, 7.5, 0); h.w("R321.2", (17.5, 4), "C315.1"); h.gnd("C315.2", "D")
    h.w((17.5, 4), (22, 4)); h.lab((22, 4), "R", h.net("R321.2"))
    h.note("RFIO to ANT_IN: series C, shunt C, series R, shunt C. Retune on the board", 0, 12.5, 1.0)

def debug(h):
    h.put("J301", 8, 9, 0, ref_at=(-4.5, -8.5), val_at=(-4.5, -7.5), just="left")
    h.w("J301.1", (4.5, None)) if False else None
    h.lab("J301.1", "U"); h.gnd("J301.5", "D")
    for p in ("2", "4", "3", "6"): h.stub(f"J301.{p}", "R", 1.5)
    h.put("J302", 30, 9, 0, ref_at=(-2, -9.5), val_at=(-2, -8.5), just="left")
    for p in ("1", "2", "3", "6"): h.stub(f"J302.{p}", "L", 1.5)
    h.lab("J302.4", "L"); h.gnd("J302.5", "L") if False else h.stub("J302.5", "L", 1.5, "GND")
    h.put("TP301", 46, 12, 0); h.lab("TP301.1", "D") if False else h.w("TP301.1", (46, 14)); h.lab((46, 14), "R", h.net("TP301.1"))

LAYOUTS = {"Cells and Gauge": {
    "Cell and load connections": pads,
    "BQ40Z50 gauge: supply, cell inputs, SMBus": gauge,
    "Current sense": current_sense,
    "Protection FETs (charge and discharge, back to back)": protection,
    "Cell fuse and heater driver": fuse,
    "Gauge interrupt onto the shared IRQ line": interrupt,
}}

def usb_en9(n):
    Q, RP, RG = f"Q{n+9}", f"R{n+54}", f"R{n+55}"
    def fn(h):
        h.put(Q, 9, 11, 0, ref_at=(3, -0.6), val_at=(3, 0.6)); h.gnd(f"{Q}.2", "D")
        h.put(RP, 8, 5, 180); h.w(f"{RP}.2", (8, 2)); h.lab((8, 2), "R", h.net(f"{RP}.2"))
        h.w(f"{RP}.1", (8, 8), (10, 8), f"{Q}.3"); h.w((10, 8), (13, 8)); h.lab((13, 8), "R", h.net(f"{RP}.1"))
        h.w(f"{Q}.1", (5, 11), (2, 11)); h.lab((2, 11), "L", h.net(f"{Q}.1"))
        h.put(RG, 5, 8, 0, lab="l"); h.w((5, 5), f"{RG}.1"); h.lab((5, 5), "L", h.net(f"{RG}.1")); h.w(f"{RG}.2", (5, 11))
        h.note("GPIO6 high turns the 9 V LDO off", 0, 15.5, 1.0)
    return fn

def usb_misc(n):
    R, T = f"R{n+32}", f"TP{n+12}"
    def fn(h):
        h.put(R, 4, 6, 0); h.w(f"{R}.1", (4, 3)); h.lab((4, 3), "R", h.net(f"{R}.1")); h.gnd(f"{R}.2", "D")
        h.put(T, 14, 6, 0); h.gnd(f"{T}.1", "D")
    return fn

for _blk, _n in (("USB Port 1", 400), ("USB Port 2", 500)):
    LAYOUTS[_blk] = {"USB-C connector and port protection": usb_c(_n), "EEPROM and I2C pull-ups": usb_eeprom(_n),
                      "9 V LDO enable: PD controller GPIO6 switches it off": usb_en9(_n),
                      "5 V enable pull-down and ground test point": usb_misc(_n)}

LAYOUTS["MCU"] = {"CC2340R5MODA module": mcu_module,
                  "Antenna match (pi network between RFIO and ANT_IN)": antenna,
                  "Debug and gauge-training connectors (Tag-Connect, no part fitted)": debug}


# One or two sentences under a section title: what the circuit is for and what a reviewer should look at.
SECTION_NOTES = {
    "TPS62177 3.3 V always-on buck": "Fixed 3.3 V output: VOS senses the output directly and FB is tied to ground. EN is tied to VIN, so the rail is always on. SLEEP low selects the sleep mode.",
    "Pack-rail bulk capacitance": "Bulk capacitance on the pack rail, ahead of the buck input.",
    "BQ40Z50 gauge: supply, cell inputs, SMBus": "Each cell tap reaches the gauge through a series resistor and a filter capacitor. The pack, VCC and PBI supplies are filtered the same way.",
    "Current sense": "The gauge measures pack current across this shunt, through filtered sense lines.",
    "Protection FETs (charge and discharge, back to back)": "Charge and discharge FETs in series with their sources joined, so each one blocks one direction.",
    "Second-level protector and fuse": "Independent overvoltage watchdog on the cell taps. It blows the chemical fuse if the gauge's own protection fails.",
    "Gauge interrupt onto the shared IRQ line": "The gauge alert pulls the shared IRQ line toward the MCU.",
    "CC2340R5MODA module": "Decoupling at each supply pin, reset RC, and pull-ups tied to the lines they serve.",
    "Antenna match (pi network between RFIO and ANT_IN)": "Pi network between the module RF pin and the antenna feed. The values are tuning positions.",
    "Debug and gauge-training connectors (Tag-Connect, no part fitted)": "Footprint-only pads. Nothing is fitted.",
    "USB-C connector and port protection": "ESD and overvoltage protection sit at the connector, before anything else touches VBUS, CC or the data lines.",
    "USB PD controller TPS25751D, EEPROM and I2C pull-ups": "The PD controller reads its configuration from the EEPROM over I2C. The pull-ups hold the bus high.",
    "EEPROM and I2C pull-ups": "The PD controller reads its configuration from the EEPROM over I2C. The pull-ups hold the bus high.",
    "BQ25756 buck-boost charger: controller and current sense": "Input and battery current are sensed across Kelvin-connected resistors, with a filter on each sense pair.",
    "Four-switch power stage. 0R gate resistors are tuning positions": "Four switches let the charger step the voltage up or down from the same input.",
    "Charger programming: input window, frequency, current limits, battery feedback, thermistor": "Resistor dividers and single resistors set each programmed limit. Each net is named for what it sets.",
    "9 V gate-drive supply, diode-ORed with REGN": "Powers the gate drive from 9 V, diode-ORed with REGN.",
    "5 V buck for PP5V (TPS62933)": "Buck regulator that makes the 5 V PP5V rail.",
    "5 V enable pull-down and ground test point": "The pull-down holds the enable low by default.",
}
