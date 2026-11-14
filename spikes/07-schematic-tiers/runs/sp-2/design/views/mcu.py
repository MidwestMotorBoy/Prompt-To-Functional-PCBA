"""MCU sheet drawn by hand-placed coordinates: U301 in the middle, supply and reset on its upper left, the
RFIO-ANT_IN pi network on its left, the SWD/gauge connectors below, the I2C and sleep/IRQ pull-ups on its right."""


def layout(ctx):
    sh, comps, pinnet, short, glob = ctx.sheet, ctx.comps, ctx.pinnet, ctx.short, ctx.glob
    horiz, rot = ctx.horiz, None
    import draw
    rot = draw.rot
    ox, oy = 152.4, 88.9                      # U301 centre
    U = "U301"
    sh.text(sh.title, ctx.X0, 21, 3.0)

    # pin geometry of U301 (symbol y up -> screen y down)
    pin = {}
    for p in ctx.pins_of[U]:
        pin.setdefault(p["num"], (ox + p["x"], oy - p["y"]))
    net = lambda ref, num: pinnet.get((ref, num))
    V3 = net(U, "6")
    xl = pin["6"][0]                           # left pin column
    xr = pin["9"][0]                           # right pin column

    def lab(n, x, y, ang):
        sh.label(short(n), x, y, ang, n in glob)

    def vpart(r, x, yc, up_net, side="R"):
        """upright two-pad part centred at (x, yc), up_net on top, text on side R or L. Returns (top pin y, bottom pin y)."""
        lib, name = comps[r]["lib"].split(":")
        pp = {}
        for p in ctx.pins_of[r]: pp.setdefault(p["num"], p)
        nums = sorted(pp); e = ctx.ends(r)
        up = nums[0] if e[0] == up_net else nums[1]
        dn = nums[1] if up == nums[0] else nums[0]
        for a in (0, 180):
            ux, uy = rot(pp[up]["x"], pp[up]["y"], a)
            if uy < 0: break
        dx, dy = rot(pp[dn]["x"], pp[dn]["y"], a)
        mirror = (a == 180)
        rv = comps[r]["value"]
        if side == "R":
            rx_, vx_ = x + 3.3, x + 3.3
        else:                                  # left-justified text laid out to end just before the part
            rx_, vx_ = x - 3.3 - len(r) * 1.1, x - 3.3 - len(rv) * 1.1
        sh.symbol(lib, name, r, rv, x, yc, a, footprint=comps[r]["footprint"], fields=comps[r]["fields"],
                  ref_at=(rx_, yc - 1.27), val_at=(vx_, yc + 1.27), mirror=mirror)
        return yc + uy, yc + dy

    def gnd_below(x, y):
        sh.gnd(x, y, 0)

    # ---------------------------------------------------------------- U301
    sh.symbol(*comps[U]["lib"].split(":"), U, comps[U]["value"], ox, oy, 0, footprint=comps[U]["footprint"],
              fields=comps[U]["fields"], ref_at=(ox - 13.97, oy - 22.5), val_at=(ox - 13.97, oy - 20.5))

    # ---------------------------------------------------------------- 3V3 rail above the chip
    yb = 58.42
    xv = xl - 5.08
    x_r302 = ox - 73.66
    x_left = ox - 86.36
    x_r305 = xr + 25.4
    x_r304 = xr + 7.62
    sh.wire(x_left, yb, x_r305, yb)
    lab(V3, x_left, yb, 180)
    sh.wire(xl, pin["6"][1], xv, pin["6"][1]); sh.wire(xv, pin["6"][1], xv, yb); sh.junction(xv, yb)
    # test point on the rail
    sh.symbol("Connector", "TestPoint", "TP301", comps["TP301"]["value"], ox - 78.74, yb, 0, footprint=comps["TP301"]["footprint"],
              fields=comps["TP301"]["fields"], ref_at=(ox - 76.2, yb - 4.5), val_at=(ox - 76.2, yb - 2.5))
    sh.junction(ox - 78.74, yb)
    # decoupling bank hanging from the rail, nearest the pin first
    for r, x in (("C301", xv - 15.24), ("C302", xv - 29.21), ("C303", xv - 43.18)):
        top, bot = vpart(r, x, yb + 2.54 + 3.81, V3, "R")
        sh.wire(x, yb, x, top); sh.junction(x, yb); gnd_below(x, bot)
    sh.text("VDDS decoupling", xv - 43.18, yb - 2.5)

    # ---------------------------------------------------------------- reset: R302 up to the rail, C304 down to ground
    NR = net(U, "14"); yR = pin["14"][1]
    top, bot = vpart("R302", x_r302, (yb + yR) / 2, V3, "L")
    sh.wire(x_r302, yb, x_r302, top); sh.junction(x_r302, yb)
    sh.wire(xl, yR, x_r302 - 5.08, yR); sh.junction(x_r302, yR)
    sh.wire(x_r302, bot, x_r302, yR)
    lab(NR, x_r302 - 5.08, yR, 180)
    top, bot = vpart("C304", x_r302, yR + 2.54 + 3.81, NR, "L")
    sh.wire(x_r302, yR, x_r302, top); gnd_below(x_r302, bot)
    sh.text("Power-on reset:", x_r302 - 24, bot + 5.5)
    sh.text("R302 pull-up + C304", x_r302 - 24, bot + 8)
    sh.text("(SWRS349A fig. 9-1)", x_r302 - 24, bot + 10.5)

    # ---------------------------------------------------------------- RFIO -> C313 -> R321 -> ANT_IN pi
    RF, AN = net(U, "4"), net(U, "3")
    MID = net("C313", "2")
    yA, yF = pin["3"][1], pin["4"][1]
    y4 = 90.17
    xf = xl - 17.78
    sh.wire(xl, yF, xf, yF); sh.wire(xf, yF, xf, y4)
    lx, rx = horiz("C313", xf - 2.54 - 3.81, y4, MID)            # returns (left x, right x)
    sh.wire(xf, y4, rx, y4)
    xm = lx - 2.54
    sh.wire(lx, y4, xm, y4)
    lx2, rx2 = horiz("R321", xm - 5.08 - 3.81, y4, AN)
    sh.wire(xm, y4, rx2, y4); sh.junction(xm, y4)
    xa = lx2 - 2.54
    sh.wire(lx2, y4, xa, y4)
    sh.wire(xa, y4, xa, yA); sh.wire(xa, yA, xl, yA)
    sh.junction(xa, y4)
    top, bot = vpart("C314", xm, y4 + 3.81, MID, "L"); gnd_below(xm, bot)
    top, bot = vpart("C315", xa, y4 + 3.81, AN, "L"); gnd_below(xa, bot)
    sh.text("RFIO - ANT_IN pi match", xa - 5.08, bot + 7.5)
    sh.text("(retune on this board)", xa - 5.08, bot + 10)

    # ---------------------------------------------------------------- GND pin
    sh.wire(xl, pin["1"][1], xl - 2.54, pin["1"][1]); gnd_below(xl - 2.54, pin["1"][1])

    # ---------------------------------------------------------------- SWD connector J301 below, its pins wired to U301
    J = "J301"
    cy, cx = 129.54, ox + 2.54
    pj = {}
    for p in ctx.pins_of[J]: pj.setdefault(p["num"], p)
    # mirrored in x: pins that faced right now face left
    jp = lambda n: (cx - pj[n]["x"], cy - pj[n]["y"])
    sh.symbol(*comps[J]["lib"].split(":"), J, comps[J]["value"], cx, cy, 0, footprint=comps[J]["footprint"],
              fields=comps[J]["fields"], mirror=True, ref_at=(cx + 12.0, cy - 6.35), val_at=(cx + 12.0, cy - 4.35))
    SD, SK = net(U, "20"), net(U, "19")
    x5, x6 = xl - 12.7, xl - 7.62
    pSWDIO, pSWCLK = jp("2"), jp("4")
    sh.wire(xl, pin["20"][1], x5, pin["20"][1]); sh.wire(x5, pin["20"][1], x5, pSWDIO[1]); sh.wire(x5, pSWDIO[1], pSWDIO[0], pSWDIO[1])
    sh.wire(xl, pin["19"][1], x6, pin["19"][1]); sh.wire(x6, pin["19"][1], x6, pSWCLK[1]); sh.wire(x6, pSWCLK[1], pSWCLK[0], pSWCLK[1])
    for n, nm in (("3", NR), ("6", net(J, "6"))):
        x, y = jp(n)
        sh.wire(x, y, x - 2.54, y); lab(nm, x - 2.54, y, 180)
    x, y = jp("1"); sh.wire(x, y, x, y - 2.54); lab(V3, x, y - 2.54, 90)
    x, y = jp("5"); sh.wire(x, y, x, y + 2.54); gnd_below(x, y + 2.54)
    sh.text("SWD debug header", cx - 12, cy + 17)
    sh.text("(Tag-Connect, not fitted)", cx - 12, cy + 19.5)

    # ---------------------------------------------------------------- right side
    ys = {n: pin[n][1] for n in pin}
    # I2C: pull-ups up to the rail, label out to the right (SCL pull-up nearer the pin so SDA's passes clear)
    for num, x_pu, r in (("9", x_r304, "R304"), ("10", x_r305, "R305")):
        n = net(U, num); y = ys[num]
        sh.wire(xr, y, x_pu + 2.54, y); sh.junction(x_pu, y)
        lab(n, x_pu + 2.54, y, 0)
        top, bot = vpart(r, x_pu, (yb + y) / 2, V3, "R")
        sh.wire(x_pu, yb, x_pu, top); sh.junction(x_pu, yb); sh.wire(x_pu, bot, x_pu, y)
    sh.text("I2C pull-ups", x_r304, yb - 2.5)
    # UART_TX to J301 SWO, NCs, outputs
    n = net(U, "16"); y = ys["16"]; sh.wire(xr, y, xr + 2.54, y); lab(n, xr + 2.54, y, 0)
    sh.nc(*pin["17"]); sh.nc(*pin["18"])
    for num in ("11", "12", "13"):
        n = net(U, num); y = ys[num]; sh.wire(xr, y, xr + 2.54, y); lab(n, xr + 2.54, y, 0)
    # SLEEP and IRQ_N pull-ups down to a rail below
    yl = oy + 28.58
    xp1, xp2 = xr + 7.62, xr + 25.4
    for num, x_pu, r, ystart in (("21", xp1, "R314", None), ("15", xp2, "R313", None)):
        n = net(U, num); y = ys[num]
        sh.wire(xr, y, x_pu + 2.54, y); sh.junction(x_pu, y)
        lab(n, x_pu + 2.54, y, 0)
        top, bot = vpart(r, x_pu, (y + yl) / 2, n, "R")
        sh.wire(x_pu, y, x_pu, top); sh.wire(x_pu, bot, x_pu, yl); sh.junction(x_pu, yl)
    sh.wire(xp1, yl, xp2, yl)
    lab(V3, xp1, yl, 180)
    sh.text("R314: the one IRQ_N pull-up", xp2 + 14, oy + 18)
    sh.text("R313: holds 3V3 buck out of sleep", xp2 + 14, oy + 20.5)
    sh.text("while U301 is in reset", xp2 + 14, oy + 23)

    # ---------------------------------------------------------------- gauge-training connector J302 (labels: nets leave the sheet)
    G2 = "J302"
    cx2, cy2 = ox + 81.28, 129.54
    pg = {}
    for p in ctx.pins_of[G2]: pg.setdefault(p["num"], p)
    gp = lambda n: (cx2 + pg[n]["x"], cy2 - pg[n]["y"])
    sh.symbol(*comps[G2]["lib"].split(":"), G2, comps[G2]["value"], cx2, cy2, 0, footprint=comps[G2]["footprint"],
              fields=comps[G2]["fields"], ref_at=(cx2 + 8.0, cy2 - 3.0), val_at=(cx2 + 8.0, cy2 - 1.0))
    for n in ("1", "2", "3", "6"):
        x, y = gp(n); nm = net(G2, n)
        sh.wire(x, y, x - 2.54, y); lab(nm, x - 2.54, y, 180)
    sh.nc(*gp("4"))
    x, y = gp("5"); sh.wire(x, y, x - 2.54, y); sh.gnd(x - 2.54, y, 270)
    sh.text("Gauge-training header", cx2 - 10, cy2 + 19)
    sh.text("(Tag-Connect, not fitted)", cx2 - 10, cy2 + 21.5)
    return True
