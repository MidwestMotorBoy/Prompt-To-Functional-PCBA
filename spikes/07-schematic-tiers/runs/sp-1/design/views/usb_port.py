"""USB port sheet: sections packed in rows of related blocks (input, charger, power stage + rails) instead of one per row."""
PAGE_W = 700.0
WC = 90
BESIDE = {"J401", "U405", "U406", "U404", "U402", "U401"}

def layout(ctx):
    sections = []
    for r in ctx.refs:
        t = ctx.comps[r].get("section") or "USB"
        if t not in [s[0] for s in sections]: sections.append((t, []))
        [s for s in sections if s[0] == t][0][1].append(r)
    sizes = [ctx.measure(lambda t=t, m=m: ctx.draw_section(t, m, 0, 0, WC)) for t, m in sections]
    sh = ctx.sheet_ref()
    X0, Y0, GAP = 20.32, 27.94, 7.62
    sh.text(sh.title, X0, 21, 3.0)
    idx = {t[:5]: i for i, (t, _) in enumerate(sections)}
    rows = [["USB-C", "USB P", "9 V g"], ["BQ257"], ["Four-", "5 V b"]]
    y = Y0; maxx = 0
    for row in rows:
        x, rh = X0, 0
        for k in row:
            i = idx[k]; w, h = sizes[i]
            if not w: continue
            ctx.draw_section(sections[i][0], sections[i][1], ctx.snap(x), ctx.snap(y), WC)
            x += w + GAP * 2; rh = max(rh, h)
        maxx = max(maxx, x)
        y += rh + GAP
    for t, m in sections:
        if sizes[idx[t[:5]]][0] == 0 and t[:5] not in sum(rows, []): pass
    sh.maxy = max(sh.maxy, y + 30)
    return True
