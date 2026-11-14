"""Sheet layout of the cells and gauge block: pack power path with the protection FETs and fuse, the BQ40Z50 gauge
with its cell-tap ladder, the BQ2947 second-level protector, and the pack current sense."""


def view(d):
    d.page = (424.0, 219.0)
    d.grounds["CELL_1N"] = "GNDD"                      # the gauge's own ground: cell 1 negative tab, by Kelvin wire
    d.alias.update({"Net-(U102-OUT)": "OVP_OUT", "Net-(Q104-G)": "FUSE_G", "Net-(F102-HTR)": "FUSE_HTR"})
    power_path(d, 5.5, 5.5)
    gauge(d, 5.5, 35.5)
    protector(d, 87.5, 35.5)
    current_sense(d, 119.5, 5.5)
    ntc_wires(d, 143, 35.5)
    notes(d, 88, 61)


def power_path(d, x0, y0):
    d.section("PACK POWER PATH: cell stack + -> fuse -> charge FET -> discharge FET -> PACK_P (10 A)", x0, y0, 112.5, 28.5)
    RY = 15
    f = d.ic("F102", 27, RY, text=(-1.6, -3.2))
    d.tp("J112", d.go(f.p("1"), dx=-5.5), "L", text="U")
    q1 = d.ic("Q101", 61, RY - 3, text=(-1.5, -3.6))
    q2 = d.ic("Q102", 72, RY - 3, mirror=True, text=(-1.5, -3.6))
    d.wire(q1.p("D"), q2.p("D"))
    d.label(d.go(q1.p("D"), dx=1), "R")
    s1 = d.go(d.go(q1.p("S"), dx=1), to_y=RY)
    d.wire(s1, f.p("2"))
    d.label(d.go(f.p("2"), dx=1.5), "R")
    s2 = d.go(d.go(q2.p("S"), dx=-1), to_y=RY)
    # charge FET gate: series resistor from the gauge, 10M gate-source
    g1 = d.go(q1.p("G"), dx=-3.5)
    d.two("R110", g1, "D", gap=0.5, text="L")
    d.label(d.go(d.two("R109", g1, "L", gap=2), dx=-1), "L")
    # discharge FET gate: 10M and a 15 V zener gate-source, series resistor from the gauge
    g2 = d.go(q2.p("G"), dx=3.5)
    d.two("R112", g2, "D", gap=0.5)
    z = d.go(g2, dx=5)
    d.two("D103", z, "D", gap=0.5)
    d.label(d.go(d.two("R111", z, "R", gap=3), dx=1), "R")
    # two capacitors in series across both FETs (ESD)
    a = d.go(d.pt(57, RY, "CELL_P"), dy=3)
    m = d.two("C110", a, "R", gap=2.5, text="B")
    b = d.two("C111", m, "R", gap=6, text="B")
    d.wire(d.go(b, dx=3.5), d.pt(d.ux(b) + 3.5, RY, "PACK_P"))
    # wake pad
    w = d.go(d.two("R118", d.pt(41, RY, "CELL_P"), "D", text="L"), dy=1)
    d.tp("TP113", d.go(w, dx=3), "U")
    # fuse igniter: either the gauge (FUSE) or the second-level protector (OUT) turns Q104 on, which heats the fuse open
    q = d.ic("Q104", d.ux(f.p("HTR")) - 1, RY + 7, text=(2.3, -0.5))
    d.wire(f.p("HTR"), q.p("D"))
    d.gnd(q.p("S"), "D")
    n = d.go(q.p("G"), dx=-9.5)
    d.shunt("R125", d.pt(d.ux(q.p("G")) - 3, d.uy(n), n.net), "D")
    d.shunt("C118", d.pt(d.ux(q.p("G")) - 8, d.uy(n), n.net), "D", text="L")
    d.label(d.go(d.two("R126", n, "U", gap=0.5), dy=-0.5), "L")
    d.label(d.go(d.two("R124", n, "L", gap=2.5), dx=-1), "L")
    # output side
    o = d.go(s2, to_x=96)
    d.gnd(d.two("C108", d.two("C107", o, "D"), "D"), "D")
    t = d.go(o, dx=7); d.tp("TP106", t, "U")
    e = d.go(t, dx=6); d.pwr(d.go(e, dy=-1))
    d.tp("J113", d.go(e, dx=4), "R", text="U")


def gauge(d, x0, y0):
    d.section("BQ40Z50-R2 GAUGE AND FIRST-LEVEL PROTECTOR: cell taps, supply, SMBus, interrupt", x0, y0, 80.5, 41)
    u = d.ic("U101", 46, 23.5)
    P = u.p
    Y = lambda p: d.uy(p)
    Lx = d.ux(P("BAT")); Rx = d.ux(P("CHG"))
    # supply pins, fanned up to three lanes above the IC
    b = d.go(d.go(P("BAT"), dx=-1), to_y=6)
    d.label(d.go(d.two("D101", d.two("R105", b, "L", gap=2), "L", gap=1.5), dx=-1.5), "L")
    v = d.go(d.go(P("VCC"), dx=-2), to_y=9)
    d.label(d.go(d.two("R106", v, "L", gap=2), dx=-1), "L")
    c = d.go(d.go(d.go(P("PBI"), dx=-3), to_y=11.5), dx=-3)
    d.shunt("C105", c, "D", text="L")
    d.ground(d.go(P("PTCEN"), dx=-1), "D", show=False)
    # cell-tap ladder: tap wire, series resistor, capacitor to the next tap down
    xc, xt = Lx - 19, Lx - 31
    lines = [("J116", "R104", "C101", "VC4", 15), ("J111", "R103", "C102", "VC3", 19), ("J110", "R102", "C103", "VC2", 23),
             ("J109", "R101", "C104", "VC1", 27)]
    for i, (tap, res, cap, pin, y) in enumerate(lines):
        src = [n for n in d.ends(res) if n != P(pin).net][0]
        t = d.pt(xt, y, src)
        d.tp(tap, t, "L", text="L")
        d.label(d.pt(xt + 0.3, y, src), "R")
        f = d.two(res, t, "R", gap=5.5)
        vx = Lx - 12 - (1 if i in (1, 2) else 0)
        d.wire(d.wire(f, (vx, y)), P(pin), "vh")
        d.go(d.two(cap, d.pt(xc, y, f.net), "D", gap=0.5), dy=0.5)
    bot = d.pt(xt, 31, "CELL_1N")
    d.tp("J115", bot, "L", text="L")
    k = d.go(bot, to_x=xc)
    d.ground(d.go(k, dx=3, dy=1), "D")
    # pack voltage, current sense inputs
    d.label(d.go(d.two("R113", P("PACK"), "L", gap=2, text="S"), dx=-1), "L")
    # board thermistors; TS2 and TS3 go to the NTC wires
    d.shunt("TH104", d.go(P("TS4"), dx=-4.5), "D", gap=2.5)
    d.shunt("TH101", d.go(P("TS1"), dx=-12), "D", gap=5.5)
    d.ground(d.go(P("PTC"), dx=-1), "D", show=False)
    # right: gate drives, SMBus through 100R, interrupt level shifter
    d.label(d.go(P("FUSE"), dx=6), "R")
    d.label(d.go(d.two("R115", P("SMBC"), "R", gap=2), dx=1), "R")
    d.label(d.go(d.two("R116", P("SMBD"), "R", gap=9), dx=1), "R")
    q = d.ic("Q103", Rx + 19, Y(P("BTP_INT")), text=(2.3, -0.5))
    d.wire(P("BTP_INT"), q.p("G"))
    d.label(d.go(P("BTP_INT"), dx=1), "R")
    d.shunt("R117", d.pt(Rx + 14.5, Y(P("BTP_INT")), P("BTP_INT").net), "D", gap=0.5, text="L")
    d.label(d.go(d.go(q.p("D"), dy=-1), dx=1), "R")
    d.gnd(q.p("S"), "D")
    d.quiet = True; d.tie([P("PRES/SHUTDN"), P("DISP")], dx=1); d.quiet = False
    d.ground(d.go(P("VSS"), dx=1.5, dy=1), "D")


def protector(d, x0, y0):
    d.section("BQ2947 SECOND-LEVEL OVERVOLTAGE PROTECTOR (4.35 V/cell)", x0, y0, 54, 24)
    u = d.ic("U102", 30, 13)
    P = u.p
    for pin, res, cap in (("V4", "R119", "C112"), ("V3", "R120", "C113"), ("V2", "R121", "C114"), ("V1", "R122", "C115")):
        d.label(d.go(d.two(res, P(pin), "L", gap=9), dx=-1), "L")
        k = d.go(P(pin), dx=-2.5)
        if cap == "C115": d.shunt(cap, k, "D", gap=0, text="L")
        else: d.two(cap, k, "D", gap=0, text="L")
    n = d.go(P("VDD"), dx=2.5)
    d.two("C116", n, "D", gap=0)
    d.label(d.go(d.two("R123", n, "R", gap=6), dx=1), "R")
    c = d.go(P("CD"), dx=7.5)
    v = d.two("C117", c, "U", gap=0)
    d.ground(d.go(d.wire(P("VSS"), v), dx=7, dy=1), "D")
    d.label(d.go(P("OUT"), dx=1), "R")


def current_sense(d, x0, y0):
    d.section("PACK CURRENT SENSE (low side, 1 mOhm)", x0, y0, 43, 17)
    a = d.pt(15, 7.5, "CELL_N")
    d.tp("J108", d.go(a, dx=-6), "L", text="U")
    b = d.go(d.two("RS101", a, "R"), dx=1)
    fa, fb = d.kelvin(a, b, "R107", "R108", "C106")
    d.label(fa, "L"); d.label(fb, "R")
    t = d.go(b, dx=6); d.tp("TP109", t, "U")
    g = d.go(t, dx=6); d.gnd(d.go(g, dy=1), "D")
    d.tp("J114", d.go(g, dx=5), "R", text="U")


def ntc_wires(d, x0, y0):
    d.section("CELL NTC WIRES", x0, y0, 19.5, 24)
    for i, (ref, net) in enumerate((("J117", "TS2"), ("J118", "CELL_1N"), ("J119", "TS3"), ("J120", "CELL_1N"))):
        p = d.pt(6, 5.5 + 4.5 * i, net)
        d.tp(ref, p, "R", text="R")
        e = d.go(p, dx=-2)
        if net == "CELL_1N": d.ground(d.go(e, dy=1), "D", show=False)
        else: d.label(e, "L")


def notes(d, x0, y0):
    d.ox, d.oy = x0 * 2.54, y0 * 2.54
    d.note(0, 0, "NOTES\n"
                 "1. CELL_1N (bar symbol) is the gauge's own ground: the cell 1\n"
                 "   negative tab, brought in by its Kelvin wire J115. It differs from\n"
                 "   GND only by the drop in RS101 and the pack wire.\n"
                 "2. Cell taps: 100R + 0.1u per cell into the gauge (R101-R104),\n"
                 "   1k + 0.1u into the BQ2947 (R119-R122; it is calibrated with 1k).\n"
                 "3. BAT is fed from the cell top ahead of the fuse through D101, so\n"
                 "   the gauge stays powered and logging if F102 opens (TI fig. 9-12).\n"
                 "   VCC comes from the FET mid point.\n"
                 "4. CHG/DSG are driven 10.5-12 V above the pack. D103 clamps the\n"
                 "   Q102 gate in a hard PACK_P short. C110 + C111 across the FETs\n"
                 "   are ESD capacitors, two in series so one short is not a bypass.\n"
                 "5. F102 is the only fuse in the pack path. Q104 heats it open when\n"
                 "   the gauge (FUSE) or the BQ2947 (OUT, 1-2 s after an overvoltage,\n"
                 "   delay set by C117) drives its gate.\n"
                 "6. Q103 inverts BTP_INT onto the shared open-drain IRQ_N line.\n"
                 "7. TS1/TS4: NTCs on the board under cells 1 and 4.\n"
                 "   TS2/TS3: NTCs on wires (J117-J120).", 1.27)
