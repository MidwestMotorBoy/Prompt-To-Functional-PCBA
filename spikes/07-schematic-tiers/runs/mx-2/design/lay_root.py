"""Root sheet: a map of the sheets. Each sheet symbol stands in a slot of a grid (hint: layout(..., slot=(col, row))) with the
list of sections the sheet holds under it. A table below says which nets run between sheets, so a reviewer who meets a flag
knows on which sheets its other end is."""
from sch import q, uid, tw

X0, Y0 = 24.0, 44.0
PITCH_X, PITCH_Y = 88.0, 56.0
BOX_W, BOX_H = 68.0, 20.0
COLS = 3
LINE = 2.0


def _text(key, s, x, y, size=1.27, bold=False):
    return (f'(text {q(s)} (exclude_from_sim no) (at {x:g} {y:g} 0) '
            f'(effects (font (size {size:g} {size:g}){" (bold yes)" if bold else ""}) (justify left top)) '
            f'(uuid {q(uid("root", key, s, x, y))}))')


def _wrap(s, width, size=1.27):
    cpl = max(10, int(width / tw("x", size)))
    lines, cur = [], ""
    for w in s.split():
        if cur and len(cur) + len(w) + 1 > cpl: lines.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    return lines + [cur]


def slots(blocks, hints):
    """Grid slot (col, row) of every sheet: the hinted one, or the next free one in reading order."""
    out = {b: tuple(hints[b]["slot"]) for b in blocks if hints.get(b, {}).get("slot")}
    free = ((c, r) for r in range(6) for c in range(COLS) if (c, r) not in out.values())
    for b in blocks:
        if b not in out: out[b] = next(free)
    return out


def shared_nets(comps, nets, blocks):
    """[(sheets, [net names])] for every net that touches more than one sheet, GND left out (it runs through all of them)."""
    groups = {}
    for n, nodes in nets.items():
        if n.lstrip("/") == "GND": continue
        bl = {comps[r]["block"] for r, _ in nodes}
        if len(bl) > 1: groups.setdefault(tuple(sorted(bl, key=blocks.index)), []).append(n.lstrip("/"))
    return sorted(groups.items(), key=lambda kv: (-len(kv[0]), kv[1]))


def root_items(project, root_uuid, entries, titles, comps, nets, cons):
    """entries: [(block, file, sheet uuid, page)]; titles: {block: [section title, ...]}. Returns s-expression strings."""
    blocks = [e[0] for e in entries]
    where = slots(blocks, cons.get("layout", {}))
    out = [_text("title", "Monolith battery bank", X0, 17.0, 3.0, bold=True)]
    y = 26.0
    for line in _wrap(" ".join(cons.get("notes", {}).get("", [])), 230.0):
        out.append(_text("about", line, X0, y)); y += LINE
    for b, fn, suid, page in entries:
        c, r = where[b]
        x, y = X0 + c * PITCH_X, Y0 + r * PITCH_Y
        out.append(
            f'(sheet (at {x:g} {y:g}) (size {BOX_W:g} {BOX_H:g}) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) '
            f'(stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0)) (uuid {q(suid)}) '
            f'(property "Sheetname" {q(b)} (at {x:g} {y - 0.7:g} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) '
            f'(property "Sheetfile" {q(fn)} (at {x:g} {y + BOX_H + 0.6:g} 0) (effects (font (size 1.27 1.27)) (justify left top))) '
            f'(instances (project {q(project)} (path {q("/" + root_uuid)} (page {q(page)})))))')
        ts = titles.get(b, [])
        if ts: out.append(_text("toc" + b, "\n".join(ts), x, y + BOX_H + 5.5))
    # table of nets that run between sheets
    yt = Y0 + (max(r for _, r in where.values()) + 1) * PITCH_Y - 5.0
    out.append(_text("tabt", "Nets that run between sheets (GND is common to all of them)", X0, yt, 1.6, bold=True))
    rows = shared_nets(comps, nets, blocks)
    colw = max((tw(", ".join(ns)) for _, ns in rows), default=0) + 8.0
    yt += 4.4
    for sheets, names in rows:
        out.append(_text("tabn", ", ".join(names), X0, yt))
        out.append(_text("tabs", ", ".join(sheets), X0 + colw, yt))
        yt += LINE + 0.6
    return out
