"""3V3 Rail: the TPS62177 buck as the datasheet draws it, and the pack-rail bulk bank under it."""


def draw(h):
    h.text(20.32, 21, "3V3 Rail", 3.0)
    X0 = 38.1
    yr = 50.8                                             # the power row: PACK_P in, SW out
    ox, oy = 111.76, yr + 7.62                              # IC origin: VIN pin row on the power row
    with h.group("TPS62177 3.3 V always-on buck (28 V in, 0.5 A, sleep mode)"):
        u = h.ic("U204", ox, oy, fields="above")
        vin, en, slp, pg = u.p("VIN"), u.p("EN"), u.p("~{SLEEP}"), u.p("PG")
        sw, vos, fb = u.p("SW"), u.p("VOS"), u.p("FB")
        # input: label, rail, 2.2u at the pin, EN strapped to VIN (always on)
        xc = vin[0] - 25.4
        h.lab(X0, yr, "PACK_P", "L")
        h.w((X0, yr), vin)
        h.hang(yr, xc, "C206", "PACK_P", txt="l")
        h.w(en, (en[0] - 5.08, en[1]), (en[0] - 5.08, yr))
        h.tie(slp, "3V3_SLEEP", "L", 5.08)                  # sleep control from the MCU
        h.nc(*pg)                                           # PG not used
        # inductor and output; the output sense is taken after the inductor
        xl = sw[0] + 17.78
        L = h.two("L201", xl, yr, "h", first="SW_3V3", txt="a")
        h.w(sw, L.a)
        xo = L.b[0] + 10.16
        h.w(L.b, (xo, yr))
        h.w(vos, (xo, vos[1]), (xo, yr))
        h.tie(fb, "GND", "R", 2.54)                         # fixed 3.3 V part: FB to ground
        h.hang(yr, xo + 10.16, "C207", "3V3")
        h.w((xo, yr), (xo + 10.16, yr), (xo + 22.86, yr))
        h.lab(xo + 22.86, yr, "3V3", "R")
        # the ground pins share one bar
        gl, gr = u.p("NC"), u.p("AGND")
        h.w(gl, gr)
        h.gnd(u.p("PGND")[0], u.p("PGND")[1] + 2.54, "D")
        h.w(u.p("PGND"), (u.p("PGND")[0], u.p("PGND")[1] + 2.54))
        h.note(X0, u.p("PGND")[1] + 9, ["EN is tied to VIN: the rail is always on. The MCU drives SLEEP (3V3_SLEEP)",
                                          "to enter the low-power mode. PG is not used.",
                                          "FB goes to ground on this fixed 3.3 V part; VOS senses the output after the inductor."], 1.27)
    # ---------------------------------------------------------------- bulk: two rows of three, beside the buck
    xb = 214.0
    y1, y2 = yr, yr + 25.4
    xs = [xb + 12.7 + i * 15.24 for i in range(3)]
    with h.group("Pack-rail bulk capacitance (shared by both chargers and both 5 V bucks)"):
        h.lab(xb, y1, "PACK_P", "L")
        h.w((xb, y1), (xs[-1] + 7.62, y1))
        h.w((xb, y1), (xb, y2), (xs[-1] + 7.62, y2))
        for r, x in zip(["C208", "C209", "C210"], xs): h.hang(y1, x, r, "PACK_P")
        for r, x in zip(["C211", "C212", "C213"], xs): h.hang(y2, x, r, "PACK_P")
        h.note(xb - 6, y2 + 18, ["Six 22u / 35 V ceramics on the pack rail.", "The buck input, both 5 V bucks and both charger",
                                 "outputs draw from this rail."], 1.27)
