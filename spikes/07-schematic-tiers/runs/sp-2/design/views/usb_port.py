"""USB Port sheet: hand-arranged page. Connector column on the left, PD controller above the charger, power stage and 5 V buck below."""


def layout(ctx):
    sec = dict(ctx.sections)
    title = lambda part: next(t for t in sec if t.startswith(part))
    by_val = lambda v: next(a for a in ctx.anchors if ctx.comps[a]["value"].startswith(v))
    GAP = 7.62
    X0, Y0 = ctx.X0, ctx.Y0
    sheet_title = ctx.sheet.title

    def size(t):
        return ctx.measure(lambda: ctx.draw_section(t, sec[t], 0, 0, 120))

    def custom(t, plan, x0, y0, wc=120):
        """Draw section t with its anchors placed at (dx, dy) offsets from its top-left corner. Returns (w, h)."""
        ctx.sheet.text(t, x0, y0 + 3.5, 2.0)
        mem, w, h = set(sec[t]), len(t) * 1.75, 6.35
        for a, dx, dy in plan:
            aw, ah, left = ctx.draw_anchor(a, x0 + dx, y0 + 6.35 + dy, ctx.zones[a])
            if left:
                cw, ch = ctx.flow(left, x0 + dx, y0 + 6.35 + dy + ah + 2.54, max(wc, aw))
                aw, ah = max(aw, cw), ah + ch + 2.54
            w, h = max(w, dx + aw), max(h, 6.35 + dy + ah)
        return w, h

    ctx.sheet.text(sheet_title, X0, 21, 3.0)
    # ---- row 1: connector column, PD controller section ----
    tc, tp, tq = title("USB-C"), title("USB PD"), title("BQ25756")
    j, d, u5 = by_val("TYPE-C"), by_val("TVS2200"), by_val("TPD6S300")
    wj = ctx.measure(lambda: ctx.draw_anchor(j, 0, 0, ctx.zones[j]))
    wd = ctx.measure(lambda: ctx.draw_anchor(d, 0, 0, ctx.zones[d]))
    plan = [(j, 0, 0), (d, wj[0] + 10, 0), (u5, wj[0] + wd[0] + 20, 0)]
    wc_, hc_ = ctx.measure(lambda: custom(tc, plan, 0, 0))
    custom(tc, plan, X0, Y0)
    xp = snap_x = X0 + wc_ + GAP
    u1, u2 = by_val("TPS25751"), by_val("M24512")
    w1 = ctx.measure(lambda: ctx.draw_anchor(u1, 0, 0, ctx.zones[u1]))
    pplan = [(u1, 0, 0), (u2, 110, 56)]
    wp, hp = ctx.measure(lambda: custom(tp, pplan, 0, 0))
    custom(tp, pplan, xp, Y0)
    # ---- row 2: charger, then the 9 V supply on its right ----
    y2 = Y0 + max(hc_, hp) + GAP
    wq, hq = size(tq)
    ctx.draw_section(tq, sec[tq], X0, y2, 120)
    t9 = title("9 V")
    w9, h9 = size(t9)
    ctx.draw_section(t9, sec[t9], X0 + wq + GAP, y2, 120)
    # ---- row 3: power stage and 5 V buck ----
    y3 = y2 + max(hq, h9) + GAP
    ts, t5 = title("Four-switch"), title("5 V buck")
    ws, hs = size(ts)
    ctx.draw_section(ts, sec[ts], X0, y3, 120)
    ctx.draw_section(t5, sec[t5], X0 + ws + GAP, y3, 120)
    ctx.sheet.maxy += 5
    return True
