"""MCU page: module in the middle; supply rail, reset and antenna pi network on its left, I2C/sleep/IRQ pull-ups and the
GPIO labels on its right, the two Tag-Connect connectors in a row underneath."""

def layout(ctx):
    S, small, horiz, inline, short, glob, snap, comps, ends = (ctx.sheet, ctx.small, ctx.horiz, ctx.inline, ctx.short,
                                                              ctx.glob, ctx.snap, ctx.comps, ctx.ends)
    ncset, pinnet, pins_of = ctx.ncset, ctx.pinnet, ctx.pins_of
    S.text(S.title, 20.32, 21, 3.0)
    ox, oy = 127.0, 88.9
    pL, pR = ox - 16.51, ox + 16.51
    Y = lambda py: oy - py

    c = comps["U301"]
    lib, name = c["lib"].split(":")
    S.symbol(lib, name, "U301", c["value"], ox, oy, 0, unit=1, footprint=c["footprint"], fields=c["fields"],
             ref_at=(ox - 12.7, oy - 22.0), val_at=(ox - 12.7, oy - 20.0))

    def gnd_hang(r, x, y_top, up_net):
        t, b = small(r, x, snap(y_top + 6.35), up_net)
        S.wire(x, y_top, x, t); S.gnd(x, b)

    # ---- supply rail: VDDS up to a 3V3 rail with its decoupling caps and the test point
    RAIL = 55.88
    S.text("Supply and reset", 40.64, 49.5, 2.0)
    S.wire(pL, Y(15.24), 107.95, Y(15.24)); S.wire(107.95, Y(15.24), 107.95, RAIL); S.wire(107.95, RAIL, 40.64, RAIL)
    S.label("3V3", 40.64, RAIL, 180, True)
    for r, x in (("C301", 99.06), ("C302", 83.82), ("C303", 68.58)):
        gnd_hang(r, x, RAIL, "3V3"); S.junction(x, RAIL)
    # test point: pad above the rail, pin on the rail
    t_, b_ = ctx.measure(lambda: small("TP301", 0, 0, "3V3"))
    S.wire(58.42, RAIL, 58.42, RAIL - 0.0)
    small("TP301", 58.42, snap(RAIL - b_), "3V3"); S.junction(58.42, RAIL)
    # reset: pull-up to the rail, filter cap to ground
    RST = Y(10.16)
    t, b = small("R302", 45.72, snap(67.31), "3V3")
    S.wire(45.72, RAIL, 45.72, t); S.wire(45.72, b, 45.72, RST); S.junction(45.72, RAIL)
    S.wire(pL, RST, 45.72, RST); S.label("NRST", 102.87, RST, 0, False)
    gnd_hang("C304", 55.88, RST, "NRST"); S.junction(55.88, RST)

    # ---- antenna pi network: RFIO down column 1, ANT_IN down column 2 (outside it), R321 between, shunts to ground
    S.text("Antenna match (pi network, retune on this board)", 62.23, 146.05, 2.0)
    x1, x2, YM = 101.6, 76.2, 123.19
    S.wire(pL, Y(2.54), x1, Y(2.54)); S.wire(pL, Y(5.08), x2, Y(5.08))
    S.label("RFIO", 105.41, Y(2.54), 0, False); S.label("ANT_IN", 92.71, Y(5.08), 0, False)
    t, b = small("C313", x1, 113.03, "RFIO")
    S.wire(x1, Y(2.54), x1, t); S.wire(x1, b, x1, YM)
    xl, xr = horiz("R321", 88.9, YM, "ANT_IN")
    S.wire(x1, YM, xr, YM); S.wire(xl, YM, x2, YM); S.wire(x2, Y(5.08), x2, YM)
    gnd_hang("C314", x1, YM, "Net-(C313-Pad2)"); S.junction(x1, YM)
    gnd_hang("C315", x2, YM, "ANT_IN"); S.junction(x2, YM)
    # SWD/GND pins on the left
    S.label("SWDIO", pL, Y(-2.54), 180, False); S.label("SWCLK", pL, Y(-5.08), 180, False)
    S.gnd(pL, Y(-10.16), 270)

    # ---- right side: pull-ups out of their pins, GPIO as labels
    inl = {"9": ("R304", 0, 0), "10": ("R305", 12.7, 0), "15": ("R313", 0, 2.54), "21": ("R314", 0, 5.08)}
    S.text("I2C, interrupt and sleep pull-ups; GPIO", 147.32, 66.0, 2.0)
    for p in pins_of["U301"]:
        if p["angle"] != 180: continue
        px, py = pR, Y(p["y"])
        n = pinnet.get(("U301", p["num"]))
        if ("U301", p["num"]) in ncset: S.nc(px, py)
        elif p["num"] in inl:
            r, ex, drop = inl[p["num"]]
            if drop:                                    # net named at the pin, pull-up dropped one row below it
                S.label(short(n), px, py, 0, n in glob); S.wire(px, py, px, py + drop); py += drop
            inline(r, px, py, "R", n, ex)
        else: S.label(short(n), px, py, 0, n in glob)

    # ---- connectors, side by side underneath
    S.text("Debug and gauge-training connectors (Tag-Connect, no part fitted)", 40.64, 156.0, 2.0)
    for ref, cx, cy in (("J301", 63.5, 180.34), ("J302", 140.0, 180.34)):
        c = comps[ref]; lib, name = c["lib"].split(":")
        S.symbol(lib, name, ref, c["value"], cx, cy, 0, unit=(0 if ref == "J301" else 1), footprint=c["footprint"], fields=c["fields"],
                 ref_at=(cx + 1.27, cy - 20.0) if ref == "J301" else (cx - 5.08, cy - 20.0), val_at=(cx + 1.27, cy - 18.0) if ref == "J301" else (cx - 5.08, cy - 18.0))
        for p in pins_of[ref]:
            px, py = snap(cx + p["x"]), snap(cy - p["y"])
            n = pinnet.get((ref, p["num"]))
            if (ref, p["num"]) in ncset or n is None: S.nc(px, py)
            elif n == "GND": S.gnd(px, py, {0: 270, 180: 90, 270: 180, 90: 0}[p["angle"]])
            else: S.label(short(n), px, py, {0: 180, 180: 0, 270: 90, 90: 270}[p["angle"]], n in glob)
    S.maxy = max(S.maxy, 205)
    return True
