"""Drawing patterns on a sch.Scene: the small circuits a draftsman draws the same way every time."""
import math
from sch import Port, snap, tw, CW, geom


def part_w(S, ref, extra=0.0, size=1.27):
    """Room a vertical part needs along a rail: its body, the text beside it, and a gap."""
    c = S.comps[ref]
    lib, name = c["lib"].split(":")
    boxes, _ = geom(lib, name)
    b = (boxes.get(0) or boxes.get(1) or [-1, 0, 1, 0])
    hw = (b[2] - b[0]) / 2
    return max(tw(ref, size), tw(c["value"], size)) + 2 * hw + 1.1 + 1.4 + extra


def bank(S, x, ry, refs, net, to="gnd", gap=1.0, pitch=None, end=None):
    """Parts hanging from a horizontal rail at y=ry, side by side, each to ground (or a rail symbol / label below).
    x is the axis of the first part. The rail wire is drawn from x to the last part. Returns [Two] and the x after."""
    out = []
    xs = x
    for i, r in enumerate(refs):
        t = S.two(r, xs, ry + 3.81, "v", first=net)
        out.append(t)
        if to == "gnd": S.gnd(t.bt)
        xs = snap(xs + (pitch or (part_w(S, r) + gap)))
    S.wire([Port(x, ry, "L", net), Port(out[-1].a.x, ry, "R", net)], net)
    return out, xs


def notes_block(S, x, y, notes, width=95.0, title="Notes", size=1.27, cols=1, first=1):
    """Numbered notes (numbered from `first`) wrapped to `width` mm, top-left at (x, y); `cols` columns when the block would
    otherwise be wider than a comfortable line (about 100 characters). Returns the bottom y."""
    S.text(title, x, y, 1.6, bold=True, kind="title")
    y += 3.6
    gap = 6.0
    cw = (width - (cols - 1) * gap) / cols
    cpl = int(cw / (CW * size / 1.27))
    blocks = []
    for i, n in enumerate(notes, first):
        words, lines, cur = n.split(), [], ""
        for w in words:
            if len(cur) + len(w) + 1 > cpl - 3 and cur:
                lines.append(cur); cur = w
            else:
                cur = (cur + " " + w).strip()
        lines.append(cur)
        blocks.append((f"{i}. " + lines[0] + "".join("\n   " + l for l in lines[1:]), len(lines)))
    split = [len(blocks)]
    if cols > 1:                                   # first k notes in the first column, k chosen to balance the heights
        best = min(range(1, len(blocks)), key=lambda k: max(sum(b[1] for b in blocks[:k]), sum(b[1] for b in blocks[k:])))
        split = [best, len(blocks)]
    ybot, k0 = y, 0
    for c, k1 in enumerate(split):
        yy = y
        for txt, _ in blocks[k0:k1]:
            b = S.text(txt, x + c * (cw + gap), yy, size, kind="note")
            yy = b[3] + 1.0
        ybot = max(ybot, yy)
        k0 = k1
    return ybot


def hang(S, ref, x, y, net, to="gnd"):
    """A vertical two-pad part hanging from the point (x, y) of a wire on `net`, its far end to ground. Returns the Two."""
    t = S.two(ref, x, y + 3.81, "v", first=net)
    if to == "gnd": S.gnd(t.bt)
    return t


def tie(S, ports, net=None, d="R", reach=2.54):
    """Join several pins on one side of a symbol with a short bar `reach` mm out. Returns the bar's two end points."""
    outs = [p.out(reach) for p in ports]
    for p, o in zip(ports, outs): S.wire([p, o], net or p.net)
    ys = sorted(o.y for o in outs)
    S.wire([(outs[0].x, ys[0]), (outs[0].x, ys[-1])], net or ports[0].net)
    return outs


def pullup(S, ref, x, yline, rail="3V3"):
    """Resistor standing on a signal line at (x, yline) with its own supply arrow on top."""
    r = S.two(ref, x, yline - 3.81, "v", first=rail)
    S.rail(rail, r.a)
    return r


def fit(S, draw, x, y):
    """Draw a section so that its frame's left edge lands at x or to the right of it. A trial drawing on a scratch scene
    tells how far the finished section (texts included) reaches to the left of its origin.
    draw(scene, x, y) -> section or (section, ...). Returns (what draw returned, frame box)."""
    T = S.scratch()
    res = draw(T, x, y)
    T.finish()
    b = T.section_box((res[0] if isinstance(res, tuple) else res))
    dx = math.ceil((x - b[0]) / 1.27 - 1e-6) * 1.27 if b[0] < x - 1e-6 else 0.0
    res = draw(S, x + dx, y)
    return res, (b[0] + dx, b[1], b[2] + dx, b[3])
