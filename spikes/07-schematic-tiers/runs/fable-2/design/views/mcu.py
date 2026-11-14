"""Sheet layout of the MCU block: the Bluetooth module, its pull-ups, the antenna match and the two Tag-Connect pads."""

def view(d):
    d.page = (297.0, 168.0)
    d.section("BLUETOOTH LE MCU MODULE (CC2340R5MODA): supply, I2C master, enables, antenna match", 5.5, 5.5, 66, 32)
    u = d.ic("U301", 33, 24)
    L = lambda n: u.p(n)
    # supply: decoupling on a short 3V3 rail above the module
    v = d.go(L("VDDS"), dx=-2, dy=-7)
    d.pwr(d.go(v, dy=-1))
    r = d.bank(["C303", "C302", "C301"], v, "L", first=4, pitch=5.5, text="L")
    d.tp("TP301", d.go(r, dx=-6), "U", text="U")
    # antenna: RFIO out through the pi match and back into ANT_IN
    m = d.two("C313", L("RFIO"), "L", gap=5, text="S")
    m = d.go(m, dx=-2); d.shunt("C314", m, "D")
    n = d.two("R321", m, "L", gap=2, text="S")
    n = d.go(n, dx=-2); d.shunt("C315", n, "D", text="L")
    a = L("ANT_IN")
    d.wire(d.go(d.go(n, dy=-2), to_x=d.ux(a) - 1), d.go(a, dx=-1))
    d.gnd(d.go(L("GND"), dx=-1, dy=1), "D")
    # I2C pull-ups and the two pull-ups that set the level while the MCU is in reset
    for pin, ref, x, gap in (("DIO6_A1", "R304", 4, 1), ("DIO8", "R305", 9, 2), ("DIO21_A10", "R313", 8, 1), ("DIO11", "R314", 12.5, 3)):
        p = d.go(L(pin), dx=x)
        d.end(d.two(ref, p, "U", gap=gap))
        d.label(d.go(p, to_x=d.ux(L(pin)) + 17), "R")

    d.section("DEBUG (SWD) AND GAUGE-TRAINING PADS (Tag-Connect)", 73.5, 5.5, 38, 32)
    j = d.ic("J301", 8, 24, text=(0.3, 4.2))
    d.pwr(d.go(j.p("VCC"), dy=-1))
    d.gnd(d.go(j.p("GND"), dy=1), "D")
    n = d.go(j.p("~{RESET}"), dx=4)
    d.end(d.two("R302", n, "U"))
    c = d.go(n, dx=5); d.shunt("C304", c, "D", gap=4.5)
    g = d.ic("J302", 30, d.uy(n) + 1, text=(-2, -8.2))
    d.wire(c, g.p("NRST"))
    d.label(d.pt(d.ux(c) + 1, d.uy(c), "NRST"), "R")

    d.ox, d.oy = 5.5 * 2.54, 39 * 2.54
    d.note(0, 0, "NOTES\n"
                 "1. Antenna match: TI LaunchPad values (15p series, 0R, 1p shunts). C314 is a tuning\n"
                 "   position: retune the pi network on this board.\n"
                 "2. R313 holds the 3V3 buck out of sleep while the MCU is in reset or blank.\n"
                 "3. R314 is the one IRQ_N pull-up (both PD controllers and the gauge pull it low,\n"
                 "   open drain). R304/R305 are the only pull-ups of the system I2C bus.\n"
                 "4. Reset: R302 pull-up with C304 as the power-on reset (TI SWRS349A fig. 9-1).\n"
                 "5. J301 and J302 are Tag-Connect TC2030-NL footprints: pads only, no part fitted.\n"
                 "   J302 gives the gauge programmer the system I2C bus, CHG_INH and reset.", 1.27)
