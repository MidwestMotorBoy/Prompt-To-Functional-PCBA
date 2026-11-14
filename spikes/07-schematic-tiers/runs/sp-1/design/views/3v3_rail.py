"""3V3 rail page: buck at the top, the six bulk caps as a bank on the pack rail below it."""
def layout(c):
    sh = c.sheet_ref()
    X0, Y0 = 20.32, 27.94
    sh.text(sh.title, X0, 21, 3.0)
    buck_refs = [r for r in c.refs if r not in [f"C{208 + i}" for i in range(6)]]
    w, h = c.draw_section("TPS62177 3.3 V always-on buck", buck_refs, X0, Y0, 120)
    bulk = [f"C{208 + i}" for i in range(6)]
    y = c.snap(Y0 + h - 12.7)
    sh.text("Pack-rail bulk capacitance (input reservoir, 6 x 22 u)", X0, y, 2.0)
    yw = c.snap(y + 12.7)
    x = c.snap(X0 + 25.4)
    sh.wire(x - 5.08, yw, x, yw); sh.label("PACK_P", x - 5.08, yw, 180, True)
    last, nx = c.hang(bulk, x, yw, "PACK_P", 1)
    xx = x
    for r in bulk:
        sh.junction(c.snap(xx), yw); xx = c.snap(xx) + c.width_of(r)
    sh.wire(x, yw, c.snap(last), yw); sh.junction(x, yw)
    sh.maxy = max(sh.maxy, yw + 40)
    return True
