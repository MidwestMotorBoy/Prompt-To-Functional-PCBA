"""3V3 Rail page, drawn by hand-placed coordinates: pack rail in at the left, the TPS62177 in the middle, 3V3 out at the right."""

def layout(ctx):
    s, c = ctx.sheet, ctx.comps
    sn = ctx.snap
    pn = ctx.pinnet
    X0 = ctx.X0
    ic = "U204"
    P = {p["name"]: p for p in ctx.pins_of[ic]}
    ox, oy = 156.21, 91.44
    tip = lambda nm: (sn(ox + P[nm]["x"]), sn(oy - P[nm]["y"]))
    net = lambda nm: pn[(ic, P[nm]["num"])]
    gl = lambda n: n in ctx.glob

    s.text(s.title, X0, 21, 3.0)
    s.symbol(*c[ic]["lib"].split(":"), ic, c[ic]["value"], ox, oy, 0, footprint=c[ic]["footprint"], fields=c[ic]["fields"],
             ref_at=(ox - 8.9, oy - 15.0), val_at=(ox - 8.9, oy - 13.0))

    # ---- input: pack rail on a bus above the IC, C206 at VIN, bulk bank further left ----
    vx, vy = tip("VIN"); ex, ey = tip("EN")
    ry = sn(vy - 17.78)                                    # input bus height
    jx = sn(vx - 7.62)
    s.wire(vx, vy, jx, vy); s.wire(jx, vy, jx, ry); s.junction(jx, vy)
    s.wire(ex, ey, jx, ey); s.wire(jx, vy, jx, ey)
    nin = net("VIN")
    xs = [sn(jx - 12.7 - 15.24 * i) for i in range(7)]
    caps = ["C206"] + [f"C{208 + i}" for i in range(6)]
    for r, x in zip(caps, xs):
        t, b = ctx.small(r, x, sn(ry + 6.35), nin)
        s.wire(x, ry, x, t); s.gnd(x, b); s.junction(x, ry)
    s.text("TPS62177 3.3 V always-on buck: pack in (12 to 16.8 V), 3.3 V out at 0.5 A", X0, ry - 17.78, 2.0)
    xend = sn(xs[-1] - 7.62)
    s.wire(jx, ry, xend, ry)
    s.label(ctx.short(nin), xend, ry, 180, gl(nin))
    s.text("C206 at VIN/PGND, then 6 x 22u bulk", xs[-1] - 5, ry - 3.0, 1.27)

    # ---- SLEEP in from the MCU, PG not used ----
    px, py = tip("~{SLEEP}")
    ctx.pin_label(px, py, "L", net("~{SLEEP}"), None)
    qx, qy = tip("PG")
    s.nc(qx, qy); s.text("PG unused", qx - 17.78, qy + 0.6, 1.27)

    # ---- switch node, inductor, output ----
    sx, sy = tip("SW"); wx, wy = tip("VOS"); fx, fy = tip("FB")
    nsw = net("SW"); nout = net("VOS")
    s.label(ctx.short(nsw), sx + 1.27, sy, 0, False)
    xl, xr = ctx.horiz("L201", sn(sx + 21.59), sy, nsw)
    s.wire(sx, sy, xl, sy)
    xo = sn(xr + 6.35)
    s.wire(xr, sy, xo, sy)
    s.wire(wx, wy, xo, wy); s.wire(xo, wy, xo, sy); s.junction(xo, sy)
    s.text("VOS senses the output", wx + 1.27, wy + 1.3, 1.27) if False else None
    # FB to ground (fixed 3.3 V part)
    s.wire(fx, fy, fx + 2.54, fy); s.wire(fx + 2.54, fy, fx + 2.54, fy + 3.81); s.gnd(fx + 2.54, fy + 3.81)
    s.text("FB to GND: fixed 3.3 V version", fx + 5.08, fy + 4.0, 1.27)
    # output cap and rail out
    cx = sn(xo + 12.7)
    t, b = ctx.small("C207", cx, sy + 6.35, nout)
    s.wire(xo, sy, cx, sy); s.junction(cx, sy); s.wire(cx, sy, cx, t); s.gnd(cx, b)
    xe = sn(cx + 12.7)
    s.wire(cx, sy, xe, sy); s.label(ctx.short(nout), xe, sy, 0, gl(nout))
    # ---- grounds: all four ground pins on one bus, one symbol ----
    gp = [tip(n) for n in ("NC", "PAD", "PGND", "AGND")]
    gy = sn(gp[0][1] + 3.81)
    for gx, y0 in gp: s.wire(gx, y0, gx, gy)
    s.wire(gp[0][0], gy, gp[-1][0], gy)
    for gx, _ in gp[1:3]: s.junction(gx, gy)
    s.wire(gp[2][0], gy, gp[2][0], gy + 2.54); s.gnd(gp[2][0], gy + 2.54)
    notes = ["Notes",
             "EN is tied to the pack rail, so the regulator is always on. SLEEP is driven by the MCU: low selects sleep mode.",
             "FB is grounded and VOS senses the output at the inductor: fixed 3.3 V version. PG is not used.",
             "C206 (2.2u) sits at VIN/PGND to keep the hot loop small; the six 22u caps are bulk on the pack rail.",
             "NC (pin 4), PAD, PGND and AGND all go to ground, one symbol."]
    for i, n in enumerate(notes): s.text(n, X0, gy + 22 + 5 * i, 1.27 if i else 2.0)
    s.maxx = max(s.maxx, xe + 22); s.maxy = max(s.maxy, gy + 55)
    return True
