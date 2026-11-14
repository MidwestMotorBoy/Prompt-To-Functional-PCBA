"""Sheet layout of the 3V3 rail block: one buck converter drawn as a power path, and the shared pack-rail bulk."""

def view(d):
    d.page = (236.0, 152.0)
    d.section("3.3 V ALWAYS-ON RAIL: TPS62177 step-down, 12-16.8 V pack in, 3.3 V 0.5 A out", 5.5, 5.5, 82, 18.5)
    u = d.ic("U204", 37, 10.5)
    # input: rail symbol, input capacitor, EN strapped to VIN
    vin = u.p("VIN")
    en = d.go(u.p("EN"), dx=-2)
    d.wire(en, d.pt(d.ux(en), d.uy(vin), "PACK_P"))
    c = d.go(vin, dx=-13)
    d.shunt("C206", c, "D", text="L")
    d.pwr(d.go(c, dx=-8, dy=-1))
    d.label(d.go(u.p("~{SLEEP}"), dx=-4), "L")
    # output: inductor in line with SW, VOS sensing the output node, output capacitor
    sw = u.p("SW")
    d.label(d.go(sw, dx=1.5), "R")
    out = d.two("L201", sw, "R", gap=8)
    node = d.go(out, dx=4)
    d.wire(u.p("VOS"), node, "hv")
    cap = d.go(node, dx=6)
    d.shunt("C207", cap, "D")
    d.pwr(d.go(cap, dx=8, dy=-1))
    d.gnd(d.go(u.p("FB"), dx=3, dy=1.5), "D")
    # ground pins along the bottom share one ground symbol
    b = [d.go(u.p(n), dy=1) for n in ("NC", "PAD", "PGND", "AGND")]
    d.wire(b[0], b[-1]); d.gnd(d.go(b[2], dy=1), "D")

    d.section("PACK_P BULK CAPACITANCE: 6 x 22u 35V", 5.5, 25.5, 46, 15)
    p = d.pt(5, 7.5, "PACK_P")
    d.pwr(d.go(p, dy=-1))
    d.bank([f"C{208 + i}" for i in range(6)], p, "R", first=4, pitch=6.5)

    d.ox, d.oy = 53.5 * 2.54, 25.5 * 2.54
    d.note(0, 0.5, "NOTES\n"
                   "1. EN is strapped to VIN: the rail is always on.\n"
                   "2. SLEEP low = sleep mode. The MCU drives 3V3_SLEEP; R313 (MCU sheet) pulls\n"
                   "   it up, so an MCU in reset or unprogrammed leaves the rail in normal mode.\n"
                   "3. Fixed 3.3 V version: FB to ground, VOS senses the output at the inductor.\n"
                   "4. PG is not used. Pin 4 (NC) is grounded, as the datasheet asks.\n"
                   "5. C206 is the buck's own input capacitor and closes its hot loop.\n"
                   "6. C208-C213 are the shared pack-side bulk for both chargers and both 5 V\n"
                   "   bucks; placed between the two power stages, beside the RBAT sense resistors.", 1.27)
