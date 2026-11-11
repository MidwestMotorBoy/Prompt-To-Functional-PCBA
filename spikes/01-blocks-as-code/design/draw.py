"""Draws KiCad schematic sheets from netlist.json. The netlist is the truth; these sheets are a view of it.

Style: every IC sits in its own zone with a label on each pin. The two-pin parts around it are drawn as small
cells next to it, each a familiar shape: a bank of parallel parts between two nets (decoupling), a vertical
chain of resistors (divider), or a single part. Nothing here decides connectivity: check.py exports KiCad's
own netlist of the result and compares it with netlist.json.

usage: draw.py <build dir> <out dir> <project name>
"""
import json, os, sys, uuid, math
import symlib
from sx import find, first, get, val

NS = uuid.UUID("6f1c2b1e-58a5-4c6e-9a59-0d5a1f2b7c11")
G = 1.27
CH = 1.0            # mm per character of 1.27 mm text, for reserving room
VERSION = "20260306"

def uid(*key):
    return str(uuid.uuid5(NS, "|".join(str(k) for k in key)))

def snap(v):
    return round(round(v / G) * G, 4)

def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

def dump(node):
    if isinstance(node, tuple):
        return q(node[1])
    if isinstance(node, str):
        return node
    return "(" + " ".join(dump(c) for c in node) + ")"

def rot(x, y, a):
    """Symbol coordinates (y up) rotated a degrees, returned as a screen offset (y down)."""
    a = a % 360
    if a == 0: xr, yr = x, y
    elif a == 90: xr, yr = -y, x
    elif a == 180: xr, yr = -x, -y
    else: xr, yr = y, -x
    return xr, -yr

FONT = "(effects (font (size 1.27 1.27)) {j})"

class Sheet:
    def __init__(self, name, project, root_uuid, title):
        self.name, self.project, self.root_uuid, self.title = name, project, root_uuid, title
        self.uuid = uid("sheet", name)
        self.items, self.libs, self.npwr = [], {}, 0
        self.maxx = self.maxy = 0.0

    def _ext(self, x, y):
        self.maxx, self.maxy = max(self.maxx, x), max(self.maxy, y)

    def lib(self, lib, name):
        key = f"{lib}:{name}"
        if key not in self.libs:
            s = symlib.flat(lib, name)
            s[1] = ("s", key)
            self.libs[key] = dump(s)
        return key

    def symbol(self, lib, name, ref, value, x, y, angle=0, unit=1, footprint="", fields=None, ref_at=None, val_at=None,
               hide_ref=False, hide_val=False, key=None):
        lid = self.lib(lib, name)
        x, y = snap(x), snap(y)
        self._ext(x + 10, y + 10)
        # KiCad turns field text with the symbol: undo that so text always reads left to right
        fa = 90 if angle in (90, 270) else 0
        fj = "right" if angle == 180 else "left"
        rx, ry = ref_at or (x + 2.54, y - 1.27)
        vx, vy = val_at or (x + 2.54, y + 1.27)
        hid = lambda h: " (hide yes)" if h else ""
        props = [f'(property "Reference" {q(ref)} (at {rx:.2f} {ry:.2f} {fa}) (effects (font (size 1.27 1.27)) (justify {fj}){hid(hide_ref)}))',
                 f'(property "Value" {q(value)} (at {vx:.2f} {vy:.2f} {fa}) (effects (font (size 1.27 1.27)) (justify {fj}){hid(hide_val)}))',
                 f'(property "Footprint" {q(footprint)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))']
        for k, v in (fields or {}).items():
            props.append(f'(property {q(k)} {q(v)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        pins = " ".join(f'(pin {q(p)} (uuid {q(uid(self.name, ref, unit, "pin", p))}))'
                        for p in sorted({p["drawn"] for p in symlib.pins(lib, name) if p["unit"] in (0, unit)}))
        su = uid(self.name, "sym", key or ref, unit)
        self.items.append(
            f'(symbol (lib_id {q(lid)}) (at {x} {y} {angle}) (unit {unit}) (exclude_from_sim no) (in_bom yes) (on_board yes) '
            f'(dnp no) (uuid {q(su)}) {" ".join(props)} {pins} '
            f'(instances (project {q(self.project)} (path {q("/" + self.root_uuid + "/" + self.uuid)} (reference {q(ref)}) (unit {unit})))))')

    def wire(self, x1, y1, x2, y2):
        x1, y1, x2, y2 = snap(x1), snap(y1), snap(x2), snap(y2)
        if (x1, y1) == (x2, y2): return
        self._ext(max(x1, x2), max(y1, y2))
        self.items.append(f'(wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default)) '
                          f'(uuid {q(uid(self.name, "w", x1, y1, x2, y2))}))')

    def junction(self, x, y):
        x, y = snap(x), snap(y)
        self.items.append(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid {q(uid(self.name, "j", x, y))}))')

    def label(self, text, x, y, angle, glob):
        x, y = snap(x), snap(y)
        self._ext(x, y)
        j = {0: "(justify left bottom)", 90: "(justify left bottom)", 180: "(justify right bottom)", 270: "(justify right bottom)"}[angle]
        if glob:
            j = {0: "(justify left)", 90: "(justify left)", 180: "(justify right)", 270: "(justify right)"}[angle]
            self.items.append(f'(global_label {q(text)} (shape passive) (at {x} {y} {angle}) {FONT.format(j=j)} '
                              f'(uuid {q(uid(self.name, "gl", text, x, y))}) (property "Intersheetrefs" "${{INTERSHEET_REFS}}" '
                              f'(at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes))))')
        else:
            self.items.append(f'(label {q(text)} (at {x} {y} {angle}) {FONT.format(j=j)} (uuid {q(uid(self.name, "l", text, x, y))}))')

    def gnd(self, x, y, angle=0):
        self.npwr += 1
        ref = f"#PWR{abs(hash(self.name)) % 90 + 10}{self.npwr:03d}"
        self.symbol("power", "GND", ref, "GND", x, y, angle, hide_ref=True, hide_val=True,
                    val_at=(snap(x) - 1.9, snap(y) + 5.0), key=f"pwr{self.npwr}")

    def nc(self, x, y):
        x, y = snap(x), snap(y)
        self.items.append(f'(no_connect (at {x} {y}) (uuid {q(uid(self.name, "nc", x, y))}))')

    def text(self, s, x, y, size=1.27):
        x, y = snap(x), snap(y)
        self.items.append(f'(text {q(s)} (exclude_from_sim no) (at {x} {y} 0) (effects (font (size {size} {size})) (justify left bottom)) '
                          f'(uuid {q(uid(self.name, "t", s, x, y))}))')

    def write(self, path, page):
        w = max(297, math.ceil((self.maxx + 25) / 10) * 10)
        h = max(210, math.ceil((self.maxy + 25) / 10) * 10)
        out = [f'(kicad_sch (version {VERSION}) (generator "p2p_draw") (generator_version "10.0") (uuid {q(self.uuid)}) '
               f'(paper "User" {w} {h}) (title_block (title {q(self.title)}) (comment 1 "Generated from code. Do not edit: change the block source and rebuild."))',
               "(lib_symbols " + "\n".join(self.libs.values()) + ")"]
        out += self.items
        out.append("(embedded_fonts no))")
        open(path, "w").write("\n".join(out) + "\n")


def draw_block(sheet, block, comps, nets, nc, cons, order):
    refs = [r for r in order if comps[r]["block"] == block]
    refset = set(refs)
    pinnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
    ncset = {(r, p) for r, p in nc}
    # a net is global when it leaves the block
    glob = {n for n, nodes in nets.items() if any(r not in refset for r, _ in nodes) and any(r in refset for r, _ in nodes)}
    short = lambda n: n.lstrip("/") if n in glob else n.split("/")[-1]
    power = {n for n, d in cons["nets"].items() if d.get("kind") == "power"}

    def rank(n):
        if n == "GND": return 0
        if n in power or n in glob and n.upper().lstrip("/").startswith(("3V3", "PACK", "VBUS", "VCC", "5V")): return 2
        return 1

    pins_of = {r: symlib.pins(*comps[r]["lib"].split(":")) for r in refs}
    npads = {r: len({p["num"] for p in pins_of[r]}) for r in refs}
    two = [r for r in refs if npads[r] <= 2]
    anchors = [r for r in refs if npads[r] > 2]

    def ends(r):
        """nets on the one or two pads of a small part, in pad order"""
        return [pinnet.get((r, n)) for n in sorted({p["num"] for p in pins_of[r]})]

    # ---- cells: resistor chains through private nodes, then banks of parts across the same two nets ----
    attach = {}
    for r in two:
        for n in ends(r):
            if n: attach.setdefault(n, []).append(r)
    isR = lambda r: comps[r]["lib"] in ("Device:R",)
    used, cells = set(), []
    def chain_from(r):
        seq = [r]
        while True:
            last = seq[-1]
            nxt = None
            for n in ends(last):
                if n and n != "GND" and n not in power and len(attach[n]) == 2 and all(isR(x) for x in attach[n]):
                    o = [x for x in attach[n] if x != last][0]
                    if o not in seq and o not in used:
                        nxt = o
            if not nxt: return seq
            seq.append(nxt)
    for r in two:
        if r in used or not isR(r) or len(ends(r)) < 2: continue
        # start a chain at an end: a resistor with at most one private node
        priv = [n for n in ends(r) if n and n != "GND" and n not in power and len(attach[n]) == 2 and all(isR(x) for x in attach[n])]
        if len(priv) != 1: continue
        seq = chain_from(r)
        if len(seq) > 1:
            # order top (higher rank) to bottom
            top_free = [n for n in ends(seq[0]) if n not in ends(seq[1])][0]
            bot_free = [n for n in ends(seq[-1]) if n not in ends(seq[-2])][0]
            if rank(top_free) < rank(bot_free): seq.reverse()
            cells.append(("chain", seq)); used.update(seq)
    banks = {}
    for r in two:
        if r in used: continue
        e = ends(r)
        banks.setdefault((frozenset(x for x in e if x), comps[r]["lib"] == "Device:R"), []).append(r)
    for (_, _), rs in banks.items():
        cells.append(("bank", rs))

    # ---- which zone each cell goes in ----
    serves = cons.get("serves", {})
    apins = {}
    for a in anchors:
        for p in pins_of[a]:
            n = pinnet.get((a, p["num"]))
            if n: apins.setdefault(n, []).append(a)
    def zone_of(cell):
        for r in cell[1]:
            if r in serves and serves[r].split(".")[0] in anchors: return serves[r].split(".")[0]
        cand = []
        for r in cell[1]:
            for n in ends(r):
                if n and rank(n) == 1 and n in apins: cand += apins[n]
        if cand: return max(set(cand), key=lambda a: (cand.count(a), -anchors.index(a)))
        for r in cell[1]:
            if r in serves and serves[r].split(".")[0] in two:        # serves a small part: follow it
                for c2 in cells:
                    if serves[r].split(".")[0] in c2[1] and c2 is not cell: return zone_of(c2)
        return None
    zones = {a: [] for a in anchors}
    rails = []
    for c in cells:
        z = zone_of(c)
        (zones[z] if z else rails).append(c)

    # ---- drawing ----
    def pin_label(x, y, side, n, key):
        """side: direction away from the symbol body: L R U D"""
        ang = {"L": 180, "R": 0, "U": 90, "D": 270}[side]
        if n is None:
            return sheet.nc(x, y)
        if n == "GND":
            return sheet.gnd(x, y, {"L": 270, "R": 90, "U": 180, "D": 0}[side])
        sheet.label(short(n), x, y, ang, n in glob)

    def small(r, x, yc, up_net):
        """Draw a one- or two-pad part upright at (x, yc) with up_net on top. Returns (top_y, bottom_y)."""
        lib, name = comps[r]["lib"].split(":")
        pp = {}
        for p in pins_of[r]: pp.setdefault(p["num"], p)
        nums = sorted(pp)
        if len(nums) == 1:
            p = pp[nums[0]]
            for a in (0, 90, 180, 270):
                dx, dy = rot(p["x"], p["y"], a)
                if abs(dx) < 0.01 and dy >= 0: break
            sheet.symbol(lib, name, r, comps[r]["value"], x, yc, a, footprint=comps[r]["footprint"], fields=comps[r]["fields"])
            return None, yc + dy
        e = ends(r)
        up = nums[0] if e[0] == up_net else nums[1]
        dn = nums[1] if up == nums[0] else nums[0]
        for a in (0, 90, 180, 270):
            ux, uy = rot(pp[up]["x"], pp[up]["y"], a); dx, dy = rot(pp[dn]["x"], pp[dn]["y"], a)
            if abs(ux) < 0.01 and abs(dx) < 0.01 and uy < dy: break
        sheet.symbol(lib, name, r, comps[r]["value"], x, yc, a, footprint=comps[r]["footprint"], fields=comps[r]["fields"])
        return yc + uy, yc + dy

    def cell_width(cell):
        labs = set()
        for r in cell[1]: labs.update(n for n in ends(r) if n and n != "GND")
        left = max([len(short(n)) for n in labs] + [3]) * CH + 6.35
        if cell[0] == "chain":
            return left, left + max(len(comps[r]["value"]) for r in cell[1]) * CH + 7.62
        return left, left + sum(max(len(comps[r]["value"]), len(r)) * CH + 6.35 for r in cell[1]) + 2.54

    def end_label(x, y, n):
        """A net at a point of a cell, drawn as a stub to the left with a label, or a ground symbol."""
        sheet.wire(x, y, x - 2.54, y)
        sheet.label(short(n), x - 2.54, y, 180, n in glob)

    def draw_cell(cell, x0, y0):
        """Returns the height used."""
        left, _ = cell_width(cell)
        cap = sorted({serves[r] for r in cell[1] if r in serves})
        if cap: sheet.text("for " + ", ".join(cap), x0, y0 + 2.2, 1.0)
        x = snap(x0 + left)
        if cell[0] == "chain":
            seq = cell[1]
            y = snap(y0 + 11.43)
            top_net = [n for n in ends(seq[0]) if n not in ends(seq[1])][0]
            prev_bot = None
            for i, r in enumerate(seq):
                up = top_net if i == 0 else [n for n in ends(r) if n in ends(seq[i - 1])][0]
                t, b = small(r, x, y, up)
                if i == 0:
                    sheet.wire(x, t, x, t - 2.54); end_label(x, t - 2.54, up)
                else:
                    sheet.wire(x, prev_bot, x, t)
                    mid = snap((prev_bot + t) / 2)
                    end_label(x, mid, up); sheet.junction(x, mid)
                prev_bot = b
                last_dn = [n for n in ends(r) if n != up][0]
                y = snap(b + 5.08 + 3.81)
            if last_dn == "GND": sheet.gnd(x, prev_bot)
            else:
                sheet.wire(x, prev_bot, x, prev_bot + 2.54); end_label(x, prev_bot + 2.54, last_dn)
            return prev_bot + 8 - y0
        rs = cell[1]
        e = [n for n in ends(rs[0]) if n]
        yc = snap(y0 + 11.43)
        if len(e) == 1 and npads[rs[0]] == 1:                      # test point and the like
            for r in rs:
                _, b = small(r, x, yc, None)
                if e[0] == "GND": sheet.gnd(x, b)
                else: end_label(x, b, e[0])
                x = snap(x + len(comps[r]["value"]) * CH + 7.62)
            return 22
        up_net, dn_net = (e[0], e[1]) if len(e) > 1 else (e[0], e[0])
        if rank(dn_net) > rank(up_net): up_net, dn_net = dn_net, up_net
        xs, tb = [], None
        for r in rs:
            tb = small(r, x, yc, up_net)
            xs.append(x)
            x = snap(x + max(len(comps[r]["value"]), len(r)) * CH + 6.35)
        t, b = tb
        yt, yb = t - 2.54, b + 2.54
        for i, xi in enumerate(xs):
            sheet.wire(xi, t, xi, yt)
            if i: sheet.wire(xs[i - 1], yt, xi, yt)
            if 0 < i < len(xs) - 1: sheet.junction(xi, yt)
            if dn_net == "GND": sheet.gnd(xi, b)
            else:
                sheet.wire(xi, b, xi, yb)
                if i: sheet.wire(xs[i - 1], yb, xi, yb)
                if 0 < i < len(xs) - 1: sheet.junction(xi, yb)
        end_label(xs[0], yt, up_net)
        if dn_net != "GND": end_label(xs[0], yb, dn_net)
        return 26

    def flow(cells_, x0, y0, wmax):
        """Lay cells left to right, wrapping. Returns (width, height) used."""
        x, y, rowh, wused = x0, y0, 0, 0
        for c in cells_:
            _, w = cell_width(c)
            if x + w > x0 + wmax and x > x0:
                x, y, rowh = x0, y + rowh + 2.54, 0
            h = draw_cell(c, x, y)
            rowh = max(rowh, h)
            x += w + 5.08
            wused = max(wused, x - x0)
        return wused, y + rowh - y0

    def draw_anchor(a, x0, y0):
        """One IC with a label on every pin. Returns (width, height)."""
        lib, name = comps[a]["lib"].split(":")
        pp = pins_of[a]
        units = sorted({p["unit"] for p in pp if p["unit"]}) or [1]
        lab = max([len(short(pinnet[(a, p["num"])])) for p in pp if pinnet.get((a, p["num"]))] + [4]) * CH + 5.08
        uy, width = y0, 0
        for u in units:
            ps = [p for p in pp if p["unit"] in (0, u)]
            minx = min(p["x"] for p in ps); maxx = max(p["x"] for p in ps)
            maxy = max(p["y"] for p in ps); miny = min(p["y"] for p in ps)
            has_left = any(p["angle"] == 0 for p in ps)
            has_top = any(p["angle"] == 270 for p in ps); has_bot = any(p["angle"] == 90 for p in ps)
            ox = snap(x0 + (lab if has_left else 12.7) - minx)
            oy = snap(uy + (lab if has_top else 10.16) + maxy)
            sheet.symbol(lib, name, a, comps[a]["value"], ox, oy, 0, unit=u, footprint=comps[a]["footprint"], fields=comps[a]["fields"],
                         ref_at=(ox + minx + 1.27, oy - maxy - (7.0 if not has_top else lab + 1.27)),
                         val_at=(ox + minx + 1.27, oy - maxy - (5.0 if not has_top else lab - 0.73)))
            seen = set()
            for p in ps:
                px, py = snap(ox + p["x"]), snap(oy - p["y"])
                if (px, py) in seen: continue
                seen.add((px, py))
                n = None if (a, p["num"]) in ncset else pinnet.get((a, p["num"]))
                pin_label(px, py, {0: "L", 180: "R", 90: "D", 270: "U"}[p["angle"]], n, (a, p["num"]))
            uy = oy - miny + (lab if has_bot else 3.81) + 3.81
            width = max(width, (lab if has_left else 12.7) + (maxx - minx) + lab)
        return width, uy - y0

    def draw_section(title, members, x0, y0, wcells):
        """A titled group: its ICs down the left, each with its cells to the right. Returns (width, height)."""
        sheet.text(title, x0, y0 + 3.5, 2.0)
        y, wmax = y0 + 6.35, len(title) * 1.75
        mem = set(members)
        sec_anchors = [a for a in anchors if a in mem]
        placed = set()
        for a in sec_anchors:
            aw, ah = draw_anchor(a, x0, y)
            cs = [c for c in zones[a] if c[1][0] in mem]
            placed.update(id(c) for c in cs)
            cw, ch = flow(cs, x0 + aw + 7.62, y, wcells) if cs else (0, 0)
            wmax = max(wmax, aw + 7.62 + cw)
            y += max(ah, ch) + 5.08
        rest = [c for c in cells if c[1][0] in mem and id(c) not in placed]
        if rest:
            cw, ch = flow(rest, x0, y, max(wcells + 60, wmax))
            wmax, y = max(wmax, cw), y + ch + 2.54
        return wmax, y - y0

    sections = []
    for r in refs:
        t = comps[r].get("section") or block
        if t not in [s_[0] for s_ in sections]: sections.append((t, []))
        [s_ for s_ in sections if s_[0] == t][0][1].append(r)
    PAGE_W, X0, Y0, GAP = 594.0, 15.24, 22.86, 7.62      # A2 landscape
    WC = 120
    # measure each section on a scratch sheet, then pack them in rows across the page
    real = sheet
    sizes = []
    for t, mem in sections:
        sheet = Sheet(real.name, real.project, real.root_uuid, real.title)
        sizes.append(draw_section(t, mem, 0, 0, WC))
    sheet = real
    sheet.text(sheet.title, X0, 14, 3.0)
    x, y, rowh = X0, Y0, 0
    for (t, mem), (w, h) in zip(sections, sizes):
        if x + w > PAGE_W - 15 and x > X0:
            x, y, rowh = X0, y + rowh + GAP, 0
        draw_section(t, mem, snap(x), snap(y), WC)
        x += w + GAP * 2
        rowh = max(rowh, h)
    sheet.maxx, sheet.maxy = max(sheet.maxx, PAGE_W - 30), max(sheet.maxy, y + rowh + 30)


def main(build, out, project):
    d = json.load(open(f"{build}/netlist.json"))
    cons = json.load(open(f"{build}/constraints.json"))
    comps, nets, nc = d["comps"], d["nets"], d.get("nc", [])
    order = sorted(comps, key=lambda r: comps[r].get("order", 0))
    os.makedirs(out, exist_ok=True)
    root_uuid = uid("root", project)
    blocks = []
    for r in order:
        b = comps[r]["block"]
        if b not in blocks: blocks.append(b)
    root = [f'(kicad_sch (version {VERSION}) (generator "p2p_draw") (generator_version "10.0") (uuid {q(root_uuid)}) (paper "A4") '
            f'(title_block (title {q(project)}) (comment 1 "Generated from code. Do not edit: change the source and rebuild.")) (lib_symbols)']
    for i, b in enumerate(blocks):
        fn = b.lower().replace(" ", "_") + ".kicad_sch"
        s = Sheet(b, project, root_uuid, b)
        draw_block(s, b, comps, nets, nc, cons, order)
        s.write(f"{out}/{fn}", i + 2)
        x, y = 30 + (i % 3) * 80, 40 + (i // 3) * 50
        root.append(
            f'(sheet (at {x} {y}) (size 60 30) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (stroke (width 0.1524) (type solid)) '
            f'(fill (color 0 0 0 0)) (uuid {q(s.uuid)}) '
            f'(property "Sheetname" {q(b)} (at {x} {y - 0.7} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) '
            f'(property "Sheetfile" {q(fn)} (at {x} {y + 30.6} 0) (effects (font (size 1.27 1.27)) (justify left top))) '
            f'(instances (project {q(project)} (path {q("/" + root_uuid)} (page {q(i + 2)})))))')
    root.append('(sheet_instances (path "/" (page "1"))) (embedded_fonts no))')
    open(f"{out}/{project}.kicad_sch", "w").write("\n".join(root) + "\n")
    print("wrote", len(blocks), "sheets to", out)

if __name__ == "__main__":
    main(*sys.argv[1:4])
