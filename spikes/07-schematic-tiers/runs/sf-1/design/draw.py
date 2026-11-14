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
        self.tb, self.bodies, self.wsegs = [], [], []     # text boxes, symbol bodies, wires, for the collision check

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
               hide_ref=False, hide_val=False, key=None, mirror=False, just=None):
        lid = self.lib(lib, name)
        x, y = snap(x), snap(y)
        self._ext(x + 10, y + 10)
        self._record_symbol(lib, name, ref, value, x, y, angle, unit, mirror, ref_at, val_at, hide_ref, hide_val, just)
        # KiCad turns field text with the symbol: undo that so text always reads left to right
        fa = 90 if angle in (90, 270) else 0
        fj = just or ("left" if (ref_at is None and val_at is None) else ("right" if (angle in (90, 180)) != mirror else "left"))
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
            f'(symbol (lib_id {q(lid)}) (at {x} {y} {angle}){" (mirror y)" if mirror else ""} (unit {unit}) (exclude_from_sim no) (in_bom yes) (on_board yes) '
            f'(dnp no) (uuid {q(su)}) {" ".join(props)} {pins} '
            f'(instances (project {q(self.project)} (path {q("/" + self.root_uuid + "/" + self.uuid)} (reference {q(ref)}) (unit {unit})))))')

    def _record_symbol(self, lib, name, ref, value, x, y, angle, unit, mirror, ref_at, val_at, hide_ref, hide_val, just):
        ps = [p for p in symlib.pins(lib, name) if p["unit"] in (0, unit)]
        if lib != "power" and ps and len({p["num"] for p in ps}) > 1:
            pts, hx, hy = [], False, False
            for p in ps:
                dx, dy = rot(-p["x"] if mirror else p["x"], p["y"], angle)
                pts.append((x + dx, y + dy))
                a = p["angle"]
                if mirror and a in (0, 180): a = 180 - a
                a = (a + angle) % 360
                if a in (0, 180): hx = True
                else: hy = True
            n = len({p["num"] for p in ps})
            ins = 1.27 if n <= 2 else 2.54
            x1, x2 = min(p[0] for p in pts), max(p[0] for p in pts)
            y1, y2 = min(p[1] for p in pts), max(p[1] for p in pts)
            if hx: x1, x2 = x1 + ins, x2 - ins
            if hy: y1, y2 = y1 + ins, y2 - ins
            if n <= 2:
                if hx: y1, y2 = y - 1.9, y + 1.9
                if hy: x1, x2 = x - 1.9, x + 1.9
            if x2 - x1 < 1.0: x1, x2 = x - 1.0, x + 1.0
            if y2 - y1 < 1.0: y1, y2 = y - 1.0, y + 1.0
            self.bodies.append((x1, y1, x2, y2, ref))
            if n > 2:
                for p in ps:
                    dx, dy = rot(-p["x"] if mirror else p["x"], p["y"], angle)
                    a = p["angle"]
                    if mirror and a in (0, 180): a = 180 - a
                    a = (a + angle) % 360
                    px, py = x + dx, y + dy
                    L = len(p["num"]) * CH
                    if a == 0: bx = (px, py - 1.3, px + max(L, 1.3), py)
                    elif a == 180: bx = (px - max(L, 1.3), py - 1.3, px, py)
                    elif a == 90: bx = (px, py - 2.5, px + 1.3, py)
                    else: bx = (px, py, px + 1.3, py + 2.5)
                    self.tb.append((bx, f"{ref}.pin{p['num']}"))
        fj = just or ("left" if (ref_at is None and val_at is None) else ("right" if (angle in (90, 180)) != mirror else "left"))
        for txt, at, hide, dflt in ((ref, ref_at, hide_ref, (x + 2.54, y - 1.27)), (value, val_at, hide_val, (x + 2.54, y + 1.27))):
            if hide: continue
            tx, ty = at or dflt
            L = len(txt) * 1.15
            self.tb.append(((tx, ty - 0.85, tx + L, ty + 0.85) if fj == "left" else (tx - L, ty - 0.85, tx, ty + 0.85), f"{ref}.field"))

    def wire(self, x1, y1, x2, y2):
        x1, y1, x2, y2 = snap(x1), snap(y1), snap(x2), snap(y2)
        if (x1, y1) == (x2, y2): return
        self.wsegs.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
        self._ext(max(x1, x2), max(y1, y2))
        self.items.append(f'(wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default)) '
                          f'(uuid {q(uid(self.name, "w", x1, y1, x2, y2))}))')

    def junction(self, x, y):
        x, y = snap(x), snap(y)
        self.items.append(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid {q(uid(self.name, "j", x, y))}))')

    def label(self, text, x, y, angle, glob):
        x, y = snap(x), snap(y)
        self._ext(x, y)
        L = len(text) * 1.15 + (2.5 if glob else 0)
        right = angle in (0, 90)
        yb, yt = (y - 1.0, y + 1.0) if glob else (y - 1.5, y)
        self.tb.append(((x, yb, x + L, yt) if right else (x - L, yb, x, yt), f"label {text}@{x:.0f},{y:.0f}"))
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
        self.tb.append(((x, y - size, x + len(s) * size * 0.95, y), f"text {s[:20]}"))
        self.items.append(f'(text {q(s)} (exclude_from_sim no) (at {x} {y} 0) (effects (font (size {size} {size})) (justify left bottom)) '
                          f'(uuid {q(uid(self.name, "t", s, x, y))}))')

    def collisions(self):
        """Pairs of overlapping text boxes, text and symbol body, text and wire, wire through a symbol body."""
        out, eps = [], 0.1
        ov = lambda a, b: a[0] < b[2] - eps and b[0] < a[2] - eps and a[1] < b[3] - eps and b[1] < a[3] - eps
        tb = self.tb
        for i in range(len(tb)):
            for j in range(i + 1, len(tb)):
                if ov(tb[i][0], tb[j][0]) and not (".pin" in tb[i][1] and ".pin" in tb[j][1]): out.append(f"text {tb[i][1]} / {tb[j][1]}")
            for b in self.bodies:
                if ov(tb[i][0], b[:4]) and not tb[i][1].endswith(tuple(f".pin{k}" for k in range(1, 100))) and ".pin" not in tb[i][1]: out.append(f"text {tb[i][1]} / body {b[4]}")
            for w in self.wsegs:
                a = tb[i][0]
                if ov((a[0], a[1] + 0.1, a[2], a[3] - 0.1), (w[0] - 0.05, w[1] - 0.05, w[2] + 0.05, w[3] + 0.05)): out.append(f"text {tb[i][1]} / wire {w[0]:.0f},{w[1]:.0f}")
        for w in self.wsegs:
            for b in self.bodies:
                if ov((w[0] - 0.05, w[1] - 0.05, w[2] + 0.05, w[3] + 0.05), (b[0] + 0.3, b[1] + 0.3, b[2] - 0.3, b[3] - 0.3)): out.append(f"wire {w[0]:.0f},{w[1]:.0f} / body {b[4]}")
        return sorted(set(out))

    def write(self, path, page):
        col = self.collisions()
        open(path + ".collisions.txt", "w").write("\n".join(col) + "\n")
        print(f"{self.name}: {len(col)} collisions" + ("" if not col else " (see " + os.path.basename(path) + ".collisions.txt)"))
        self.collisions_n = len(col)
        w = max(297, math.ceil((self.maxx + 25) / 10) * 10)
        h = max(150, math.ceil((self.maxy + 25) / 10) * 10)
        out = [f'(kicad_sch (version {VERSION}) (generator "p2p_draw") (generator_version "10.0") (uuid {q(self.uuid)}) '
               f'(paper "User" {w} {h}) (title_block (title {q(self.title)}) (comment 1 "Generated from code. Do not edit: change the block source and rebuild."))',
               "(lib_symbols " + "\n".join(self.libs.values()) + ")"]
        out += self.items
        out.append("(embedded_fonts no))")
        open(path, "w").write("\n".join(out) + "\n")


def draw_block(sheet, block, comps, nets, nc, cons, order):
    refs = [r for r in order if comps[r]["block"] == block]
    refset = set(refs)
    import sketches
    skset = set()
    for title_ in sketches.SKETCHES:
        if sketches.applies(title_, block): skset |= set(sketches.refs_of(title_, block))
    allrefs = refs
    refs = [r for r in refs if r not in skset]
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

    pins_of = {r: symlib.pins(*comps[r]["lib"].split(":")) for r in allrefs}
    npads = {r: len({p["num"] for p in pins_of[r]}) for r in allrefs}
    tdraw = {a: t for a, t in cons.get("draw", {}).items() if a in refset}
    templ = set()
    for t in tdraw.values():
        templ.update([t["inductor"]] + t.get("cin", []) + t.get("cout", []) + t.get("div", []) + [t[k] for k in ("boot", "rin", "rout") if t.get(k)])
    tskip = {t["q_out"] for t in tdraw.values() if t.get("q_out")}
    two = [r for r in refs if npads[r] <= 2 and r not in templ]
    anchors = [r for r in refs if npads[r] > 2 and r not in tskip]

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
        if tdraw.get(a, {}).get("kind") == "bridge4": continue      # drawn as a power path: it has no pins to hang parts on
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
        if cand:
            sec = comps[cell[1][0]].get("section") or block
            same = [a for a in cand if (comps[a].get("section") or block) == sec]
            if same: cand = same
            return max(set(cand), key=lambda a: (cand.count(a), -anchors.index(a)))
        for r in cell[1]:
            if r in serves and serves[r].split(".")[0] in two:        # serves a small part: follow it
                for c2 in cells:
                    if serves[r].split(".")[0] in c2[1] and c2 is not cell: return zone_of(c2)
        return None
    zones = {a: [] for a in anchors}
    rails = []
    for c in cells:
        z = zone_of(c) if npads[c[1][0]] > 1 else None
        (zones[z] if z else rails).append(c)

    # a part that ends on a private net shared with one inline part can continue the same line (R105 then D101)
    ext_cand = {}
    for a_ in anchors:
        for c_ in zones[a_]:
            if len(c_[1]) != 1 or c_[0] != "bank" or npads[c_[1][0]] != 2: continue
            p_ = c_[1][0]
            for o_ in ends(p_):
                if not o_ or o_ == "GND" or o_ in glob or o_ in power or len(nets[o_]) != 2: continue
                for c2 in cells:
                    q_ = c2[1][0]
                    if c2 is c_ or len(c2[1]) != 1 or c2[0] != "bank" or q_ in templ or npads[q_] != 2: continue
                    if o_ in ends(q_) and q_ not in ext_cand.values() and p_ not in ext_cand:
                        ext_cand[p_] = q_; break
    ext_cells = {id(c2) for c2 in cells if c2[1][0] in ext_cand.values()}
    for a_ in anchors: zones[a_] = [c_ for c_ in zones[a_] if id(c_) not in ext_cells or c_[1][0] in ext_cand]
    ext_taken, ext_done = set(), set()

    # ---- drawing ----
    def pin_label(x, y, side, n, key):
        """side: direction away from the symbol body: L R U D. A 2.54 mm stub leaves the pin tip, the label sits at its end."""
        ang = {"L": 180, "R": 0, "U": 90, "D": 270}[side]
        if n is None:
            return sheet.nc(x, y)
        dx, dy = {"L": (-2.54, 0), "R": (2.54, 0), "U": (0, -2.54), "D": (0, 2.54)}[side]
        if n == "GND":
            sheet.wire(x, y, x + dx, y + dy)
            return sheet.gnd(x + dx, y + dy, {"L": 270, "R": 90, "U": 180, "D": 0}[side])
        sheet.wire(x, y, x + dx, y + dy)
        sheet.label(short(n), x + dx, y + dy, ang if side in "LR" else (0 if side == "U" else 180), n in glob)

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

    TW = 1.15                                                     # mm per character of field text, with margin
    def width_of(r): return max(len(comps[r]["value"]), len(r)) * CH + 6.35

    def horiz(r, xc, y, left_net, ref_at=None, val_at=None):
        """Draw a two-pad part lying flat, centred at (xc, y), with left_net on its left pad. Returns (left x, right x)."""
        lib, name = comps[r]["lib"].split(":")
        pp = {}
        for p in pins_of[r]: pp.setdefault(p["num"], p)
        nums = sorted(pp); e = ends(r)
        lf = nums[0] if e[0] == left_net else nums[1]; rt = nums[1] if lf == nums[0] else nums[0]
        for a in (0, 90, 180, 270):
            lx, ly = rot(pp[lf]["x"], pp[lf]["y"], a); rx, ry = rot(pp[rt]["x"], pp[rt]["y"], a)
            if abs(ly) < 0.01 and abs(ry) < 0.01 and lx < rx: break
        xc, y = snap(xc), snap(y)
        sheet.symbol(lib, name, r, comps[r]["value"], xc, y, a, footprint=comps[r]["footprint"], fields=comps[r]["fields"],
                     ref_at=ref_at or (xc - 3.81, y - 5.0), val_at=val_at or (xc - 3.81, y - 3.0))
        return snap(xc + lx), snap(xc + rx)

    def hang(rs, x, y, net, sgn=1):
        """Parts hanging from a horizontal wire at y, each to ground or a label below. Returns (x of the last part, next free x)."""
        last = x
        for r in rs:
            if sgn < 0: x = snap(x - width_of(r))
            x = snap(x); last = x
            t, b = small(r, x, snap(y + 2.54 + 3.81), net)
            sheet.wire(x, y, x, t)
            other = [n for n in ends(r) if n != net]
            if not other or other[0] == "GND": sheet.gnd(x, b)
            else: sheet.wire(x, b, x, b + 2.54); sheet.label(short(other[0]), x, b + 2.54, 270, other[0] in glob)
            if sgn > 0: x = snap(x + width_of(r))
        return last, x

    def inline_extent(r, net, extra=0, ext=None):
        other = [n for n in ends(r) if n != net]
        if ext:
            o2 = [n for n in ends(ext) if n != other[0]][0]
            stub = 2.54 + extra
            tot = stub + 7.62 + len(short(other[0])) * CH + 5.08 + 7.62 + 2.54 + (len(short(o2)) * CH + 5.08 if o2 != "GND" else 5.08)
            return stub, tot, tot + 2.54
        users = [x for x in nets[net] if x[0] != r]
        stub = (2.54 if len(users) <= 1 else len(short(net)) * CH + 3.81 + (2.5 if net in glob else 0)) + extra
        tail = 10.16 if (not other or other[0] == "GND") else 2.54 + len(short(other[0])) * CH + (5.08 if other[0] in glob else 2.54)
        return stub, stub + 7.62 + tail, stub + 7.62 + tail + 2.54

    def inline(r, px, py, side, net, extra=0, ext=None, above=True):
        """One two-pad part straight out of a pin on the pin's own row, ending in ground or a label, its text after it."""
        sg = 1 if side == "R" else -1
        stub, far, total = inline_extent(r, net, extra, ext)
        other = [n for n in ends(r) if n != net]
        if ext:
            o = other[0]; o2 = [n for n in ends(ext) if n != o][0]
            xc = snap(px + sg * (stub + 3.81))
            l1, r1 = d.hor(r, xc, py, net if side == "R" else o, flip=(side == "L"))
            near, end = (l1, r1) if side == "R" else (r1, l1)
            sheet.wire(px, py, near, py)
            xc2 = snap(end + sg * (len(short(o)) * CH + 5.08 + 3.81))
            l2, r2 = d.hor(ext, xc2, py, o if side == "R" else o2, flip=(side == "L"))
            near2, end2 = (l2, r2) if side == "R" else (r2, l2)
            sheet.wire(end, py, near2, py)
            sheet.label(short(o), end + sg * 1.27, py, 0 if side == "R" else 180, False)
            sheet.wire(end2, py, end2 + sg * 2.54, py)
            if o2 == "GND": sheet.gnd(end2 + sg * 2.54, py, 90 if side == "R" else 270)
            else: sheet.label(short(o2), end2 + sg * 2.54, py, 0 if side == "R" else 180, o2 in glob)
            ext_taken.add(ext)
            return total
        if stub - extra > 2.54: sheet.label(short(net), px, py, 0 if side == "R" else 180, net in glob)
        xc = snap(px + sg * (stub + 3.81))
        xl, xr = d.hor(r, xc, py, net if side == "R" else (other[0] if other else net), above=above, flip=(side == "L"))
        near, end = (xl, xr) if side == "R" else (xr, xl)
        sheet.wire(px, py, near, py)
        if not other or other[0] == "GND":
            sheet.wire(end, py, end + sg * 2.54, py); sheet.gnd(end + sg * 2.54, py, 90 if side == "R" else 270)
        else:
            sheet.wire(end, py, end + sg * 2.54, py); sheet.label(short(other[0]), end + sg * 2.54, py, 0 if side == "R" else 180, other[0] in glob)
        return total

    def buck(a, t, ox, oy, lab_l, lab_r, draw=True):
        """Buck converter around IC a: input caps to the left of VIN, inductor in line with SW, feedback and output caps to the right.
        Returns (set of IC pin numbers it wired, width used left of the left pins, width used right of the right pins, depth below the top pin)."""
        P = lambda nm: next(p for p in pins_of[a] if p["name"] == nm)
        pos = lambda p: (snap(ox + p["x"]), snap(oy - p["y"]))
        vin, sw = P(t["vin"]), P(t["sw"])
        nvin, nsw = pinnet[(a, vin["num"])], pinnet[(a, sw["num"])]
        L = t["inductor"]; nout = [n for n in ends(L) if n != nsw][0]
        wl = lab_l + 2.54 + sum(width_of(r) for r in t.get("cin", [])) + 5.08 + len(short(nvin)) * CH + 5.08
        wired = {vin["num"], sw["num"]}
        for k in ("sense", "fb", "bst"):
            if t.get(k): wired.add(P(t[k])["num"])
        if not draw: return wired, wl, 0, 0
        (vx, vy), (sx, sy) = pos(vin), pos(sw)
        # input side
        last, _ = hang(t.get("cin", []), vx - lab_l - 2.54, vy, nvin, -1)
        for r in t.get("cin", [])[:-1]: pass
        xe = snap(last - 5.08)
        sheet.wire(vx, vy, xe, vy); sheet.label(short(nvin), xe, vy, 180, nvin in glob)
        x = vx - lab_l - 2.54
        for r in t.get("cin", []):
            x = snap(x - width_of(r)); sheet.junction(x, vy)
        # switch node, bootstrap, inductor
        xa = snap(sx + lab_r + 2.54)
        xi = xa + 5.08
        if t.get("boot"):
            (bx, by) = pos(P(t["bst"])); nb = pinnet[(a, P(t["bst"])["num"])]
            top, bot = (by, sy) if by < sy else (sy, by)
            t_, b_ = small(t["boot"], xa, snap((by + sy) / 2), nb if by < sy else nsw)
            sheet.wire(bx, by, xa, by); sheet.wire(xa, top, xa, t_); sheet.wire(xa, b_, xa, bot); sheet.junction(xa, sy)
            xi = xa + width_of(t["boot"]) + 5.08
        sheet.label(short(nsw), sx, sy, 0, False)
        xl, xr = horiz(L, snap(xi + 3.81), sy, nsw)
        sheet.wire(sx, sy, xl, sy)
        xo = snap(xr + 5.08)
        depth = 16
        nxt = xo + 7.62
        if t.get("sense"):
            (qx, qy) = pos(P(t["sense"]))
            sheet.wire(qx, qy, xo, qy); sheet.wire(xo, qy, xo, sy); sheet.junction(xo, sy)
        if t.get("fb"):
            (qx, qy) = pos(P(t["fb"])); nfb = pinnet[(a, P(t["fb"])["num"])]
            top_r, bot_r = t["div"]
            t1, b1 = small(top_r, xo, snap(sy + 2.54 + 3.81), nout)
            ym = snap(b1 + 2.54)
            t2, b2 = small(bot_r, xo, snap(ym + 2.54 + 3.81), nfb)
            sheet.wire(xo, sy, xo, t1); sheet.wire(xo, b1, xo, t2); sheet.junction(xo, ym); sheet.junction(xo, sy)
            nb2 = [n for n in ends(bot_r) if n != nfb]
            if not nb2 or nb2[0] == "GND": sheet.gnd(xo, b2)
            else: sheet.wire(xo, b2, xo, b2 + 2.54); sheet.label(short(nb2[0]), xo, b2 + 2.54, 270, nb2[0] in glob)
            xf = snap(xa + 2.54)
            sheet.wire(qx, qy, xf, qy); sheet.wire(xf, qy, xf, ym); sheet.wire(xf, ym, xo, ym)
            sheet.label(short(nfb), qx, qy, 0, False)
            nxt = xo + max(width_of(top_r), width_of(bot_r)) + 2.54
            depth = b2 + 8 - sy
        last, x2 = hang(t.get("cout", []), nxt, sy, nout, 1)
        x = nxt
        for r in t.get("cout", []):
            sheet.junction(snap(x), sy); x = snap(x) + width_of(r)
        xe = snap(x2 + 2.54)
        sheet.wire(xr, sy, xe, sy); sheet.label(short(nout), xe, sy, 0, nout in glob)
        return wired, wl, xe + len(short(nout)) * CH + 6.35 - sx, max(depth, 16) + (sy - vy if sy > vy else 0)

    def bridge4(a, t, x0, y0):
        """Four-switch buck-boost drawn as a power path, left to right: input shunt, input caps, input half bridge, inductor,
        output half bridge, output caps, output shunt. Returns (width, height)."""
        qa, qb = a, t["q_out"]
        net = lambda q, nm, u: next(pinnet[(q, p["num"])] for p in pins_of[q] if p["name"] == nm and p["unit"] == u)
        def box(q, u, x, y, mir):
            lib, name = comps[q]["lib"].split(":")
            sheet.symbol(lib, name, q, comps[q]["value"], x, y, 0, unit=u, footprint=comps[q]["footprint"], fields=comps[q]["fields"],
                         ref_at=(x - 6.35 + (11.43 if mir else 0), y - 7.0), val_at=(x - 6.35 + (11.43 if mir else 0), y - 5.0), mirror=mir)
            out = {}
            for p in pins_of[q]:
                if p["unit"] == u: out[p["name"]] = (snap(x + (-p["x"] if mir else p["x"])), snap(y - p["y"]))
            return out
        n_in, n_out = net(qa, "D1", 1), net(qb, "D1", 1)
        n_sw1, n_sw2 = net(qa, "SW", 1), net(qb, "SW", 1)
        lab = max(len(short(net(q, g, u))) for q in (qa, qb) for g, u in (("G1", 1), ("G2", 2))) * CH + 5.08
        yr = snap(y0 + 10.16); ya = snap(yr + 15.24); yb = snap(ya + 15.24)
        # input: label, shunt, caps
        n_src = [n for n in ends(t["rin"]) if n != n_in][0]
        x = snap(x0 + len(short(n_src)) * CH + 7.62)
        sheet.label(short(n_src), x, yr, 180, n_src in glob)
        xl, xr = horiz(t["rin"], x + 2.54 + 3.81, yr, n_src)
        sheet.wire(x, yr, xl, yr)
        sheet.label(short(n_in), xr + 1.27, yr, 0, False)
        xc = snap(xr + len(short(n_in)) * CH + 5.08)
        last, xn = hang(t["cin"], xc, yr, n_in, 1)
        xx = xc
        for r in t["cin"]: sheet.junction(snap(xx), yr); xx = snap(xx) + width_of(r)
        # input half bridge
        qx = snap(xn + lab + 6.35)
        A = box(qa, 1, qx, ya, False); B = box(qa, 2, qx, yb, False)
        xd, xs = snap(qx + 8.89), snap(qx + 11.43)
        sheet.wire(xr, yr, xd, yr); sheet.wire(xd, yr, xd, A["D1"][1]); sheet.wire(A["D1"][0], A["D1"][1], xd, A["D1"][1])
        ysw = A["SW"][1]
        sheet.wire(A["SW"][0], ysw, xs, ysw); sheet.wire(B["SW"][0], B["SW"][1], xs, B["SW"][1]); sheet.wire(xs, ysw, xs, B["SW"][1]); sheet.junction(xs, ysw)
        sheet.wire(B["S2"][0], B["S2"][1], xd, B["S2"][1]); sheet.gnd(xd, B["S2"][1], 90)
        sheet.label(short(net(qa, "G1", 1)), A["G1"][0], A["G1"][1], 180, False); sheet.label(short(net(qa, "G2", 2)), B["G2"][0], B["G2"][1], 180, False)
        # inductor
        sheet.label(short(n_sw1), xs + 1.27, ysw, 0, False)
        xi = snap(xs + len(short(n_sw1)) * CH + 5.08)
        il, ir = horiz(t["inductor"], xi + 3.81, ysw, n_sw1)
        sheet.wire(xs, ysw, il, ysw)
        sheet.label(short(n_sw2), ir + 1.27, ysw, 0, False)
        xs2 = snap(ir + len(short(n_sw2)) * CH + 5.08)
        # output half bridge, mirrored
        qx2 = snap(xs2 + 11.43)
        A2 = box(qb, 1, qx2, ya, True); B2 = box(qb, 2, qx2, yb, True)
        xd2 = snap(qx2 - 8.89)
        sheet.wire(ir, ysw, xs2, ysw); sheet.wire(xs2, ysw, A2["SW"][0], ysw); sheet.wire(xs2, ysw, xs2, B2["SW"][1]); sheet.wire(xs2, B2["SW"][1], B2["SW"][0], B2["SW"][1]); sheet.junction(xs2, ysw)
        sheet.wire(A2["D1"][0], A2["D1"][1], xd2, A2["D1"][1]); sheet.wire(xd2, A2["D1"][1], xd2, yr)
        sheet.wire(B2["S2"][0], B2["S2"][1], xd2, B2["S2"][1]); sheet.gnd(xd2, B2["S2"][1], 270)
        sheet.label(short(net(qb, "G1", 1)), A2["G1"][0], A2["G1"][1], 0, False); sheet.label(short(net(qb, "G2", 2)), B2["G2"][0], B2["G2"][1], 0, False)
        # output: caps, shunt, label
        xo = snap(qx2 + 6.35 + max(lab, 17.78))
        sheet.label(short(n_out), xo - len(short(n_out)) * CH - 1.27, yr, 0, False)
        last, xn = hang(t["cout"], xo + 2.54, yr, n_out, 1)
        xx = xo + 2.54
        for r in t["cout"]: sheet.junction(snap(xx), yr); xx = snap(xx) + width_of(r)
        n_dst = [n for n in ends(t["rout"]) if n != n_out][0]
        ol, orr = horiz(t["rout"], xn + 2.54 + 3.81, yr, n_out)
        sheet.wire(xd2, yr, ol, yr)
        xe = snap(orr + 2.54)
        sheet.wire(orr, yr, xe, yr); sheet.label(short(n_dst), xe, yr, 0, n_dst in glob)
        return xe + len(short(n_dst)) * CH + 7.62 - x0, yb + 10.16 - y0

    def cell_width(cell, att=None):
        labs = set()
        for r in cell[1]: labs.update(n for n in ends(r) if n and n != "GND" and not (att and n == att[0]))
        left = (max(len(short(n)) for n in labs) * CH + 8.89) if labs else (5.08 if att else 3 * CH + 6.35)
        extra = 0 if not att else (len(short(att[0])) * CH + 7.62 if att[0] in glob else 2.54)
        if cell[0] == "chain":
            return left, left + max(max(len(comps[r]["value"]), len(r)) for r in cell[1]) * CH + 7.62 + extra
        return left, left + sum(max(len(comps[r]["value"]), len(r)) * CH + 6.35 for r in cell[1]) + 2.54 + extra

    def end_label(x, y, n):
        """A net at a point of a cell, drawn as a stub to the left with a label, or a ground symbol."""
        sheet.wire(x, y, x - 2.54, y)
        sheet.label(short(n), x - 2.54, y, 180, n in glob)

    def draw_cell(cell, x0, y0, att=None):
        """Returns (height used, entry point). att = (net, side): that net gets a bare stub on the given side of the
        cell ("L" or "R") for a wire from an IC pin, instead of a label; the entry point is the stub's end."""
        left, _ = cell_width(cell, att)
        entry = [None]
        def end_label(x, y, n, xr=None):
            xr = x if xr is None else xr
            if not att or n != att[0]:
                if att and cell[0] == "chain" and att[1] == "L":      # keep other labels clear of the wire coming in on the left
                    sheet.wire(x, y, x + 2.54, y)
                    return sheet.label(short(n), x + 2.54, y, 0, n in glob)
                sheet.wire(x, y, x - 2.54, y)
                return sheet.label(short(n), x - 2.54, y, 180, n in glob)
            if xr != x: sheet.junction(x if att[1] == "L" else xr, y)
            if att[1] == "L":
                sheet.wire(x, y, x - 2.54, y); entry[0] = (snap(x - 2.54), snap(y))
                if n in glob: sheet.wire(xr, y, xr + 2.54, y); sheet.label(short(n), xr + 2.54, y, 0, True); sheet.junction(xr, y) if xr != x else None
            else:
                sheet.wire(xr, y, xr + 2.54, y); entry[0] = (snap(xr + 2.54), snap(y))
                if n in glob: sheet.wire(x, y, x - 2.54, y); sheet.label(short(n), x - 2.54, y, 180, True); sheet.junction(x, y) if xr != x else None
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
            return prev_bot + 8 - y0, entry[0]
        rs = cell[1]
        e = [n for n in ends(rs[0]) if n]
        yc = snap(y0 + 11.43)
        if len(e) == 1 and npads[rs[0]] == 1:                      # test point and the like
            for r in rs:
                _, b = small(r, x, yc, None)
                if e[0] == "GND": sheet.gnd(x, b)
                else: end_label(x, b, e[0])
                x = snap(x + len(comps[r]["value"]) * CH + 7.62)
            return 22, None
        up_net, dn_net = (e[0], e[1]) if len(e) > 1 else (e[0], e[0])
        if rank(dn_net) > rank(up_net): up_net, dn_net = dn_net, up_net
        if att and att[0] == dn_net and dn_net != "GND": up_net, dn_net = dn_net, up_net
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
        end_label(xs[0], yt, up_net, xs[-1])
        if dn_net != "GND": end_label(xs[0], yb, dn_net, xs[-1])
        return 26, entry[0]

    def flow(cells_, x0, y0, wmax):
        """Lay cells left to right, wrapping. Returns (width, height) used."""
        x, y, rowh, wused = x0, y0, 0, 0
        for c in cells_:
            _, w = cell_width(c)
            if x + w > x0 + wmax and x > x0:
                x, y, rowh = x0, y + rowh + 2.54, 0
            h, _ = draw_cell(c, x, y)
            rowh = max(rowh, h)
            x += w + 10.16
            wused = max(wused, x - x0)
        return wused, y + rowh - y0

    SEC_W = 230.0
    P_LANE = 15.24                                                # spacing of the lanes beside an IC

    def chain_nodes(seq):
        ns = [[n for n in ends(seq[0]) if n not in ends(seq[1])][0]]
        for i in range(len(seq) - 1): ns.append([n for n in ends(seq[i]) if n in ends(seq[i + 1])][0])
        ns.append([n for n in ends(seq[-1]) if n not in ends(seq[-2])][0])
        return ns

    def attach_plan(a, cs):
        """Which cells can be wired to side pins of IC a.
        Returns ({pin number: [(bank cell, net)]}, [chains with the pins their nodes tap], other cells)."""
        side_pin = {}
        for p in pins_of[a]:
            n = pinnet.get((a, p["num"]))
            if n and n != "GND" and p["angle"] in (0, 180) and (a, p["num"]) not in ncset: side_pin.setdefault(n, p)
        pinby = {}
        for p in pins_of[a]:
            if p["angle"] in (0, 180): pinby.setdefault(p["num"], p)
        banks, chains, rest = {}, [], []
        for c in cs:
            if npads[c[1][0]] == 1: rest.append(c); continue
            if c[0] == "chain":
                nodes = chain_nodes(c[1]); m = len(nodes) - 1
                taps = {i: side_pin[n]["num"] for i, n in enumerate(nodes) if n in side_pin and n not in glob and rank(n) == 1}
                if (not taps or any(i not in taps for i in range(1, m)) or len(set(taps.values())) < len(taps)
                        or len({pinby[v]["angle"] for v in taps.values()}) > 1):
                    rest.append(c); continue
                chains.append(dict(cell=c, seq=list(c[1]), nodes=nodes, taps=taps)); continue
            cn = set(x for r in c[1] for x in ends(r) if x)
            loc = sorted((n for n in cn if n in side_pin and n not in glob and rank(n) == 1), key=lambda n: (len(nets[n]), n))
            oth = sorted(n for n in cn if n in side_pin and n not in loc)
            if not (loc or oth): rest.append(c); continue
            n = (loc or oth)[0]
            banks.setdefault(side_pin[n]["num"], []).append((c, n))
        while True:                                                   # a chain's taps must land on neighbouring lanes, in order
            att = set(banks) | {num for ch in chains for num in ch["taps"].values()}
            bad = None
            for ch in chains:
                side = pinby[next(iter(ch["taps"].values()))]["angle"]
                order = sorted((n for n in att if pinby[n]["angle"] == side), key=lambda n: -pinby[n]["y"])
                idx = [order.index(ch["taps"][i]) for i in sorted(ch["taps"])]
                if idx == list(range(idx[0], idx[0] + len(idx))): continue
                if idx == list(range(idx[0], idx[0] - len(idx), -1)):
                    m = len(ch["nodes"]) - 1
                    ch["seq"].reverse(); ch["nodes"].reverse(); ch["taps"] = {m - i: num for i, num in ch["taps"].items()}
                    continue
                bad = ch; break
            if not bad: break
            chains.remove(bad); rest.append(bad["cell"])
        return banks, chains, rest

    def lanes(a, side, nums, ox, oy, labx, banks, chains):
        """The passives on one side of IC a, each pin fanned out to its own horizontal lane: parts to ground hang from the lane,
        one series part sits in line and ends in a label, divider chains stand across the lanes they tap.
        nums: pin numbers, top to bottom. Returns (width beyond the pins, top y, bottom y)."""
        if not nums: return 0, None, None
        sg = 1 if side == "R" else -1
        pb = {}
        for p in pins_of[a]:
            if p["angle"] == (180 if side == "R" else 0): pb.setdefault(p["num"], p)
        px = snap(ox + pb[nums[0]]["x"])
        pys = [snap(oy - pb[n]["y"]) for n in nums]
        n = len(nums); yc = snap(sum(pys) / n)
        between, skip, involved = {}, set(), set()                    # parts drawn upright between two neighbouring lanes (a ladder)
        for k_, num_ in enumerate(nums):
            net_k = pinnet[(a, num_)]
            for c_, cn_ in banks.get(num_, []):
                for r_ in c_[1]:
                    oth_ = [m_ for m_ in ends(r_) if m_ != net_k]
                    if len(ends(r_)) < 2 or not oth_ or oth_[0] == "GND" or net_k in glob or oth_[0] in glob: continue
                    for k2_ in (k_ - 1, k_ + 1):
                        if 0 <= k2_ < n and nums[k2_] != num_ and pinnet[(a, nums[k2_])] == oth_[0]:
                            between.setdefault(k_, []).append((r_, k2_)); skip.add(r_); involved |= {k_, k2_}; break
        invn = {nums[k_] for k_ in involved}
        def pitch(num):                                               # a lane with only a series part needs less room than one with caps
            its = banks.get(num, [])
            net_ = pinnet[(a, num)]
            if num in invn: return P_LANE
            if (len(its) == 1 and len(its[0][0][1]) == 1 and not any(num in ch["taps"].values() for ch in chains) and net_ not in glob
                    and [m_ for m_ in ends(its[0][0][1][0]) if m_ != its[0][1]] and [m_ for m_ in ends(its[0][0][1][0]) if m_ != its[0][1]][0] != "GND"):
                return 10.16
            if not its and not any(num in ch["taps"].values() for ch in chains): return 7.62
            return P_LANE
        gaps = [max(pitch(nums[k]), pitch(nums[k + 1])) for k in range(n - 1)]
        tot_ = sum(gaps)
        yl, acc = [], yc - tot_ / 2
        for k in range(n):
            yl.append(snap(acc))
            if k < n - 1: acc += gaps[k]
        up = [k for k in range(n) if yl[k] < pys[k] - 0.01]; dn = [k for k in range(n) if yl[k] > pys[k] + 0.01]
        col = {}
        for i, k in enumerate(up): col[k] = i + 1                     # going up: top pin turns first; going down: bottom pin first
        for i, k in enumerate(reversed(dn)): col[k] = i + 1
        xs = snap(px + sg * (labx + 2.54 * (max([0] + list(col.values())) + 1)))
        ends_x = []
        xcol = capw = None
        if involved:
            lr_ = max(len(short(pinnet[(a, nums[k_])])) * CH + 1.27 for k_ in involved if pinnet[(a, nums[k_])] not in glob)
            capw = max(width_of(r_) for l_ in between.values() for r_, _ in l_)
            xcol = snap(xs + sg * (lr_ + 2.54 + capw))
        for k, num in enumerate(nums):
            net = pinnet[(a, num)]; y = yl[k]
            if k in col:
                xc = snap(px + sg * (labx + 2.54 * col[k]))
                sheet.wire(px, pys[k], xc, pys[k]); sheet.wire(xc, pys[k], xc, y); sheet.wire(xc, y, xs, y)
            else: sheet.wire(px, pys[k], xs, y)
            lroom = 0
            if net not in glob:                                       # name the net on its lane, clear of the pin rows
                sheet.label(short(net), xs, y, 0 if sg > 0 else 180, False); lroom = len(short(net)) * CH + 1.27
            tapped = any(num in ch["taps"].values() for ch in chains)
            hangs, series = [], None
            for c, cn in banks.get(num, []):
                other = [m_ for m_ in ends(c[1][0]) if m_ != cn]
                if all(r_ in skip for r_ in c[1]): continue
                if len(c[1]) == 1 and other and other[0] != "GND" and not tapped and series is None and net not in glob: series = c[1][0]
                else: hangs += [r_ for r_ in c[1] if r_ not in skip]
            x, end = snap(xs + sg * (2.54 + lroom)), xs
            if k in involved:
                x, end = snap(xcol + sg * 2.54), xcol
                sheet.wire(xs, y, xcol, y)
                for r_, k2_ in between.get(k, []):
                    ya, yb = min(y, yl[k2_]), max(y, yl[k2_])
                    tnet = pinnet[(a, nums[k if y < yl[k2_] else k2_])]
                    t_, b_ = d.vert(r_, xcol, (ya + yb) / 2, tnet, "L" if sg > 0 else "R")
                    sheet.wire(xcol, ya, xcol, t_); sheet.wire(xcol, b_, xcol, yb); sheet.junction(xcol, ya); sheet.junction(xcol, yb)
            pts = []
            for r in hangs:
                other = [m_ for m_ in ends(r) if m_ != net]
                lbl = other[0] if other and other[0] != "GND" else None
                w = width_of(r)
                room = (len(short(lbl)) * CH + (6.35 if lbl in glob else 2.54)) if lbl else 0      # its label sits bottom left
                if sg < 0: x = snap(x - w)
                else: x = snap(x + room)
                t_, b_ = small(r, x, snap(y + 2.54 + 3.81), net)
                sheet.wire(x, y, x, t_)
                if not lbl: sheet.gnd(x, b_)
                else: sheet.wire(x, b_, x - 2.54, b_); sheet.label(short(lbl), x - 2.54, b_, 180, lbl in glob)
                pts.append(x); end = x
                if sg > 0: x = snap(x + w)
                else: x = snap(x - 2.54 - room)
            cont = bool(series) or tapped or net in glob
            for q_ in pts[:-1] + (pts[-1:] if cont else []): sheet.junction(q_, y)
            if pts: sheet.wire(xs, y, end, y)
            if series:
                other = [m_ for m_ in ends(series) if m_ != net][0]
                ex = ext_cand.get(series)
                o2 = [m_ for m_ in ends(ex) if m_ != other][0] if ex else None
                gap = len(short(other)) * CH + 5.08
                if sg > 0:
                    xl, xr = d.hor(series, x + 2.54 + 3.81, y, net, above=False)
                    sheet.wire(end, y, xl, y)
                    if ex:
                        sheet.label(short(other), xr + 1.27, y, 0, False)
                        xl2, xr2 = d.hor(ex, xr + gap + 3.81, y, other, above=False)
                        sheet.wire(xr, y, xl2, y); xr, other = xr2, o2; ext_done.add(series)
                    sheet.wire(xr, y, xr + 2.54, y); sheet.label(short(other), xr + 2.54, y, 0, other in glob)
                    x = xr + 2.54 + len(short(other)) * CH + 6.35; end = xr + 2.54
                else:
                    xl, xr = d.hor(series, x - 2.54 - 3.81, y, other, above=False, flip=True)
                    sheet.wire(end, y, xr, y)
                    if ex:
                        sheet.label(short(other), xl - 1.27, y, 180, False)
                        xl2, xr2 = d.hor(ex, xl - gap - 3.81, y, o2, above=False, flip=True)
                        sheet.wire(xl, y, xr2, y); xl, other = xl2, o2; ext_done.add(series)
                    sheet.wire(xl, y, xl - 2.54, y); sheet.label(short(other), xl - 2.54, y, 180, other in glob)
                    x = xl - 2.54 - len(short(other)) * CH - 6.35; end = xl - 2.54
            elif net in glob and not tapped:
                xe = snap(x + sg * 2.54)
                sheet.wire(end, y, xe, y); sheet.label(short(net), xe, y, 0 if sg > 0 else 180, True)
                x = xe + sg * (len(short(net)) * CH + 6.35); end = xe
            ends_x.append([x, end])
        xfar = max(e[0] for e in ends_x) if sg > 0 else min(e[0] for e in ends_x)
        top = yl[0] - 6.35
        def cap(net_, x, y, at_top):
            if net_ == "GND": return sheet.gnd(x, y, 180 if at_top else 0)
            sheet.wire(x, y, x + sg * 2.54, y); sheet.label(short(net_), x + sg * 2.54, y, 0 if sg > 0 else 180, net_ in glob)
        for ch in chains:
            seq, nodes, taps = ch["seq"], ch["nodes"], ch["taps"]
            if taps[min(taps)] not in nums: continue
            m = len(nodes) - 1
            w = max(width_of(r) for r in seq)
            lw = max([len(short(nodes[i])) * CH + 7.62 for i in (0, m) if i not in taps and nodes[i] != "GND"] + [0])
            if sg > 0: x = snap(xfar + 5.08); xfar = x + max(w, lw)
            else: x = snap(xfar - 5.08 - w); xfar = x - lw
            ys = {i: yl[nums.index(taps[i])] for i in taps}
            for i in taps:
                k = nums.index(taps[i]); sheet.wire(ends_x[k][1], ys[i], x, ys[i]); ends_x[k][1] = x
                if 0 < i < m: sheet.junction(x, ys[i])
            for j, r in enumerate(seq):
                yc_ = ys[j] + 7.62 if j in taps else ys[j + 1] - 7.62
                t_, b_ = small(r, x, snap(yc_), nodes[j])
                if j in taps: sheet.wire(x, ys[j], x, t_)
                else: cap(nodes[j], x, t_, True)
                if j + 1 in taps: sheet.wire(x, b_, x, ys[j + 1])
                else: cap(nodes[j + 1], x, b_, False)
            if min(taps) == 1 and taps[1] == nums[0]: top = yl[0] - 15.24
        return abs(xfar - px) + 2.54, top, yl[-1] + pitch(nums[-1])

    def measure(fn):
        """Run a drawing function on a scratch sheet and return its result."""
        nonlocal sheet
        real = sheet
        sheet = Sheet(real.name, real.project, real.root_uuid, real.title)
        try: return fn()
        finally: sheet = real

    def draw_anchor(a, x0, y0, cs=()):
        """One IC with a label on every pin, and the passives on its side pins wired to them: single parts on the pin's own row,
        the rest on lanes beside the IC, or by a template when the block names one. Returns (width, height, cells not drawn)."""
        lib, name = comps[a]["lib"].split(":")
        pp = pins_of[a]
        t = tdraw.get(a)
        if t and t["kind"] == "bridge4":
            w, h = bridge4(a, t, x0, y0)
            return w, h, list(cs)
        banks, chains, rest = attach_plan(a, list(cs))
        tapped = {num for ch in chains for num in ch["taps"].values()}
        inl = {}                                                      # pin number -> (pin, part, net): drawn on the pin's own row
        side_of = {}
        for p in pp:
            if p["angle"] in (0, 180): side_of.setdefault(p["num"], p)
        last_inl = {}                                                 # side -> y of the last inline pin: no two on neighbouring rows
        twired0 = buck(a, t, 0, 0, 0, 0, draw=False)[0] if t else set()
        for num, lst in sorted(banks.items(), key=lambda e: -side_of[e[0]]["y"]):
            c, n = lst[0]
            p0 = side_of[num]
            free_ = bool(t) and num not in twired0 and len(lst) == 1 and len(c[1]) == 1 and num not in tapped    # template IC: its other pins keep their parts
            if free_ and npads[c[1][0]] == 2:
                last_inl[p0["angle"]] = p0["y"]; inl[num] = (p0, c[1][0], n); del banks[num]; continue
            if len(lst) == 1 and len(c[1]) == 1 and n not in glob and num not in tapped:
                if any(pinnet.get((a, num)) in {m_ for c2_, _ in l2_ for r2_ in c2_[1] for m_ in ends(r2_)}
                       for n2_, l2_ in banks.items() if n2_ != num and side_of[n2_]["angle"] == p0["angle"]): continue   # a ladder rung ends here
                if any(q_["num"] != num and q_["angle"] == p0["angle"] and abs(q_["y"] - p0["y"]) < 2.6 and pinnet.get((a, q_["num"]))
                       and (a, q_["num"]) not in ncset for q_ in side_of.values()): continue
                last_inl[p0["angle"]] = p0["y"]
                inl[num] = (p0, c[1][0], n); del banks[num]
        if t:                                                         # a template owns the space beside the IC: no lanes
            twired = buck(a, t, 0, 0, 0, 0, draw=False)[0]
            for num in list(banks): rest += [c for c, _ in banks.pop(num)]
            rest += [ch["cell"] for ch in chains]; chains = []
            for num in list(inl):
                if num in twired: rest.append(("bank", [inl[num][1]])); del inl[num]
        stag = {}                                                     # parts on neighbouring pin rows step outward so bodies do not touch
        for ang in (0, 180):
            prev_y, k = None, 0
            for num, (p, r, n) in sorted(((nm, v) for nm, v in inl.items() if v[0]["angle"] == ang), key=lambda e: -e[1][0]["y"]):
                k = (k + 1) % 3 if prev_y is not None and abs(prev_y - p["y"]) < 2.6 else 0
                stag[num] = k * 12.7; prev_y = p["y"]
        for num, (p0, r_, n_) in inl.items():                          # start the part beyond the labels on the pins next to it
            need = 0
            for q_ in side_of.values():
                dyq = q_["y"] - p0["y"]
                if q_["num"] == num or q_["angle"] != p0["angle"] or not (-2.6 <= dyq <= 7.7) or q_["num"] in inl: continue
                nn = pinnet.get((a, q_["num"]))
                if nn is None or (a, q_["num"]) in ncset: continue
                need = max(need, 2.54 if nn == "GND" else len(short(nn)) * CH + (2.5 if nn in glob else 0) + 1.3)
            stag[num] = max(stag[num], need)
        inl_l = max([inline_extent(r, n, stag[nm], ext_cand.get(r))[2] for nm, (p, r, n) in inl.items() if p["angle"] == 0] + [0])
        inl_r = max([inline_extent(r, n, stag[nm], ext_cand.get(r))[2] for nm, (p, r, n) in inl.items() if p["angle"] == 180] + [0])
        units = sorted({p["unit"] for p in pp if p["unit"]}) or [1]
        lab = max([len(short(pinnet[(a, p["num"])])) for p in pp if pinnet.get((a, p["num"]))] + [4]) * CH + 5.08
        uy, width = y0, 0
        for u in units:
            ps = [p for p in pp if p["unit"] in (0, u)]
            minx = min(p["x"] for p in ps); maxx = max(p["x"] for p in ps)
            maxy = max(p["y"] for p in ps); miny = min(p["y"] for p in ps)
            has_left = any(p["angle"] == 0 for p in ps)
            has_top = any(p["angle"] == 270 for p in ps); has_bot = any(p["angle"] == 90 for p in ps)
            labl, labr = max(lab, inl_l + 2.54), max(lab, inl_r + 2.54)
            att = set(banks) | {num for ch in chains for num in ch["taps"].values()}
            mine = [num for num in att if side_of[num]["unit"] in ((0, u) if u == units[0] else (u,))]
            Ln = sorted((n for n in mine if side_of[n]["angle"] == 0), key=lambda n: -side_of[n]["y"])
            Rn = sorted((n for n in mine if side_of[n]["angle"] == 180), key=lambda n: -side_of[n]["y"])
            mL = measure(lambda: lanes(a, "L", Ln, 0, 0, labl, banks, chains))
            mR = measure(lambda: lanes(a, "R", Rn, 0, 0, labr, banks, chains))
            WL = mL[0] if Ln else (labl if has_left else 12.7)
            WR = mR[0] if Rn else labr
            ox = snap(x0 + WL - minx)
            if t: ox = snap(x0 + buck(a, t, 0, 0, labl, labr, draw=False)[1] - minx)
            oy = uy + (lab if has_top else 10.16) + maxy
            tops = [m_[1] for m_ in (mL, mR) if m_[1] is not None]
            if tops: oy = max(oy, uy + 5.08 - min(tops))
            oy = snap(oy)
            sheet.symbol(lib, name, a, comps[a]["value"], ox, oy, 0, unit=u, footprint=comps[a]["footprint"], fields=comps[a]["fields"],
                         ref_at=(ox + minx + 1.27, oy - maxy - (7.0 if not has_top else lab + 1.27)),
                         val_at=(ox + minx + 1.27, oy - maxy - (5.0 if not has_top else lab - 0.73)))
            wired = set(mine) | set(inl)
            tw = None
            if t:
                tw = buck(a, t, ox, oy, labl, labr)
                wired |= tw[0]
            for num, (p, r, n) in inl.items():
                nb_up = any(q_["num"] != num and q_["angle"] == p["angle"] and 0 < q_["y"] - p["y"] <= 5.1 and pinnet.get((a, q_["num"]))
                            for q_ in side_of.values())
                if p["unit"] in (0, u): inline(r, snap(ox + p["x"]), snap(oy - p["y"]), "L" if p["angle"] == 0 else "R", n, stag[num], ext_cand.get(r), above=not nb_up)
            seen = {(snap(ox + p["x"]), snap(oy - p["y"])) for p in ps if p["num"] in wired}
            for p in ps:
                px, py = snap(ox + p["x"]), snap(oy - p["y"])
                if (px, py) in seen or p["num"] in wired: continue
                seen.add((px, py))
                n = None if (a, p["num"]) in ncset else pinnet.get((a, p["num"]))
                pin_label(px, py, {0: "L", 180: "R", 90: "D", 270: "U"}[p["angle"]], n, (a, p["num"]))
            bottom = oy - miny + (lab if has_bot else 3.81)
            for side, nums_, labx in (("L", Ln, labl), ("R", Rn, labr)):
                r_ = lanes(a, side, nums_, ox, oy, labx, banks, chains)
                if r_[2] is not None: bottom = max(bottom, r_[2])
            uy = bottom + 3.81
            width = max(width, WL + (maxx - minx) + WR)
            if tw:
                uy = max(uy, oy - maxy + tw[3] + 12.7)
                width = max(width, tw[1] + (maxx - minx) + tw[2])
        for p_, q_ in ext_cand.items():
            if p_ in [c_[1][0] for c_ in zones[a]] and not any(p_ == v[1] for v in inl.values()) and p_ not in ext_done:
                rest.append(("bank", [q_]))
        return width, uy - y0, rest

    def pad_grid(rs, x0, y0, per_col=7, pitch=7.62):
        """Wire pads and test points in a tidy grid: the net name on a stub to the left of the pad, the reference and
        description to its right."""
        def geom(r):
            n = ends(r)[0]
            lab = len(short(n)) * CH + (2.5 if n in glob else 0) + 2.54 + 1.3 if n != "GND" else 5.08
            return lab, (9.0 if comps[r]["lib"].endswith("Conn_01x01") else 4.0)
        colw = [geom(r)[0] + geom(r)[1] + (len(r) + 1 + len(comps[r]["value"])) * CH + 6 for r in rs]
        cx, wtot, h = x0, 0, 0
        for c0 in range(0, len(rs), per_col):
            chunk = rs[c0:c0 + per_col]
            xp = snap(cx + max(geom(r)[0] for r in chunk))
            for i, r in enumerate(chunk):
                y = snap(y0 + 5.08 + i * pitch)
                lib, name = comps[r]["lib"].split(":")
                n = ends(r)[0]
                lab, body = geom(r)
                tx = xp + body
                conn = name == "Conn_01x01"
                sheet.symbol(lib, name, r, comps[r]["value"], xp + (5.08 if conn else 0), y, 0, footprint=comps[r]["footprint"],
                             fields=comps[r]["fields"], ref_at=(tx, y), val_at=(tx + (len(r) + 1) * CH + 1.0, y), just="left")
                sheet.wire(xp, y, xp - 2.54, y)
                if n == "GND": sheet.gnd(xp - 2.54, y, 270)
                else: sheet.label(short(n), xp - 2.54, y, 180, n in glob)
                h = max(h, 5.08 + (i + 1) * pitch)
            cx += max(colw[c0:c0 + per_col]); wtot = cx - x0
        return wtot, h

    class D: pass
    d = D()
    d.comps, d.nets, d.G, d.block = comps, nets, G, block
    d.snap = snap
    d.wire = lambda *pts: [sheet.wire(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]) for i in range(len(pts) - 1)]
    d.dot = lambda x, y: sheet.junction(x, y)
    d.text = lambda s_, x, y, size=1.27: sheet.text(s_, x, y, size)
    d.net = lambda r, num: pinnet.get((r, num))
    def d_lab(net, x, y, dr):
        """label for net with its anchor at (x, y); dr: side the text extends to (R, L)"""
        if net == "GND": return sheet.gnd(x, y, {"L": 270, "R": 90, "U": 180, "D": 0}[dr])
        sheet.label(short(net), x, y, {"R": 0, "L": 180, "U": 90, "D": 270}[dr], net in glob)
    d.lab = d_lab
    d.sheet_nc = lambda x, y: sheet.nc(x, y)
    d.gnd = lambda x, y, dr="D": sheet.gnd(x, y, {"L": 270, "R": 90, "U": 180, "D": 0}[dr])
    def d_vert(r, x, yc, up_net, side="R"):
        """two-pad part standing upright at (x, yc) with up_net on top, its text on the given side. Returns (top y, bottom y)."""
        lib, name = comps[r]["lib"].split(":")
        pp = {}
        for p in pins_of[r]: pp.setdefault(p["num"], p)
        nums = sorted(pp); e = ends(r)
        up = nums[0] if e[0] == up_net else nums[1]; dn = nums[1] if up == nums[0] else nums[0]
        for a in (0, 90, 180, 270):
            ux, uy = rot(pp[up]["x"], pp[up]["y"], a); dx, dy = rot(pp[dn]["x"], pp[dn]["y"], a)
            if abs(ux) < 0.01 and abs(dx) < 0.01 and uy < dy: break
        x, yc = snap(x), snap(yc)
        tx = x + 3.81 if side == "R" else x - 3.81
        sheet.symbol(lib, name, r, comps[r]["value"], x, yc, a, footprint=comps[r]["footprint"], fields=comps[r]["fields"],
                     ref_at=(tx, yc - 1.27), val_at=(tx, yc + 1.27), just="left" if side == "R" else "right")
        return snap(yc + uy), snap(yc + dy)
    d.vert = d_vert
    def d_hor(r, xc, y, left_net, above=True, flip=False):
        """two-pad part lying flat, left_net on its left pad, text above or below. Returns (left x, right x)."""
        lib, name = comps[r]["lib"].split(":")
        pp = {}
        for p in pins_of[r]: pp.setdefault(p["num"], p)
        nums = sorted(pp); e = ends(r)
        lf = nums[0] if e[0] == left_net else nums[1]; rt = nums[1] if lf == nums[0] else nums[0]
        for a in (0, 90, 180, 270):
            lx, ly = rot(pp[lf]["x"], pp[lf]["y"], a); rx, ry = rot(pp[rt]["x"], pp[rt]["y"], a)
            if abs(ly) < 0.01 and abs(ry) < 0.01 and lx < rx: break
        xc, y = snap(xc), snap(y)
        dy_ = -5.0 if above else 3.0
        tx = xc + 3.81 if flip else xc - 3.81
        sheet.symbol(lib, name, r, comps[r]["value"], xc, y, a, footprint=comps[r]["footprint"], fields=comps[r]["fields"],
                     ref_at=(tx, y + dy_), val_at=(tx, y + dy_ + 2.0), just="right" if flip else "left")
        return snap(xc + lx), snap(xc + rx)
    d.hor = d_hor
    def d_sym(r, x, y, angle=0, mirror=False, ref_at=None, val_at=None, just="left"):
        """any part at (x, y); returns {pad number: (x, y)} of its pins on the sheet"""
        lib, name = comps[r]["lib"].split(":")
        x, y = snap(x), snap(y)
        sheet.symbol(lib, name, r, comps[r]["value"], x, y, angle, footprint=comps[r]["footprint"], fields=comps[r]["fields"],
                     ref_at=ref_at, val_at=val_at, mirror=mirror, just=just)
        out = {}
        for p in pins_of[r]:
            dx, dy = rot(-p["x"] if mirror else p["x"], p["y"], angle)
            out[p["num"]] = (snap(x + dx), snap(y + dy))
        return out
    d.sym = d_sym

    def draw_section(title, members, x0, y0, wcells):
        """A titled group: its ICs down the left, each with its cells to the right. Returns (width, height)."""
        mem = set(members)
        if title in sketches.SKETCHES and sketches.applies(title, block):
            sheet.text(title, x0, y0 + 3.5, 2.0)
            note = cons.get("notes", {}).get(title)
            if note: sheet.text(note, x0, y0 + 7.0, 1.1)
            w_, h_ = sketches.SKETCHES[title][0](d, x0, y0 + (12.7 if note else 10.16))
            return max(w_, len(title) * 1.75, len(note or "") * 1.0), h_ + 12.7
        sec_anchors = [a for a in anchors if a in mem]
        claimed = {id(c) for a in anchors for c in zones[a]}        # drawn with their IC, whatever section they were written in
        if not sec_anchors and not [c for c in cells if c[1][0] in mem and id(c) not in claimed]: return 0, 0
        sheet.text(title, x0, y0 + 3.5, 2.0)
        note = cons.get("notes", {}).get(title)
        if note: sheet.text(note, x0, y0 + 7.0, 1.1)
        y, wmax = y0 + (10.16 if note else 6.35), max(len(title) * 1.75, len(note or "") * 1.0)
        cx, cy, rowh = 0.0, 0.0, 0.0
        SECW = SEC_W
        for a in sec_anchors:
            cs = zones[a]
            aw, ah, left_over = measure(lambda: draw_anchor(a, 0, 0, cs))
            lw = 0
            if left_over: lw, lh = measure(lambda: flow(left_over, 0, 0, max(wcells, aw))); ah_tot = ah + 2.54 + lh
            else: ah_tot = ah
            bw = max(aw, lw)
            if cx > 0 and cx + bw > SECW: cx, cy, rowh = 0.0, cy + rowh + 5.08, 0.0
            ax, ay = snap(x0 + cx), snap(y + cy)
            draw_anchor(a, ax, ay, cs)
            if left_over: flow(left_over, ax, ay + ah + 2.54, max(wcells, aw))
            wmax = max(wmax, cx + bw)
            rowh = max(rowh, ah_tot)
            cx += bw + 7.62
        y += cy + rowh + 5.08
        rest = [c for c in cells if c[1][0] in mem and id(c) not in claimed and id(c) not in ext_cells]
        pads = [r for c in rest if npads[c[1][0]] == 1 for r in c[1]]
        rest = [c for c in rest if npads[c[1][0]] != 1]
        if rest:
            cw, ch = flow(rest, x0, y, max(wcells + 60, wmax))
            wmax, y = max(wmax, cw), y + ch + 2.54
        if pads:
            cw, ch = pad_grid(pads, x0, y)
            wmax, y = max(wmax, cw), y + ch + 2.54
        return wmax, y - y0

    sections = []
    for r in allrefs:
        t = comps[r].get("section") or block
        if t not in [s_[0] for s_ in sections]: sections.append((t, []))
        [s_ for s_ in sections if s_[0] == t][0][1].append(r)
    X0, Y0, GAP = 20.32, 27.94, 7.62
    WC = 120
    # measure each section on a scratch sheet, then pack them in rows across the page; the page width is the one
    # whose packing wastes least area and is closest to a landscape sheet
    real = sheet
    sizes = []
    for t, mem in sections:
        sheet = Sheet(real.name, real.project, real.root_uuid, real.title)
        sizes.append(draw_section(t, mem, 0, 0, WC))
    sheet = real
    items = [(t, mem, w, h) for (t, mem), (w, h) in zip(sections, sizes) if w]
    def shelf(pw, items=items):
        """skyline packing in reading order: each section goes to the highest free spot, leftmost first"""
        placed, rows, wu, hu = [], [], 0, 0
        for t, mem, w, h in items:
            cands = sorted({X0} | {px + pw_ + GAP * 2 for px, py, pw_, ph in placed})
            best_ = None
            for cx in cands:
                if cx + w > pw and cx > X0: continue
                y = Y0
                for px, py, pw_, ph in placed:
                    if cx < px + pw_ + GAP and px < cx + w + GAP: y = max(y, py + ph + GAP * 2)
                if best_ is None or (y, cx) < best_: best_ = (y, cx)
            y, cx = best_
            placed.append((cx, y, w, h)); rows.append((t, mem, cx, y)); wu = max(wu, cx + w); hu = max(hu, y + h)
        return rows, wu, hu
    import random
    rnd = random.Random(7)
    orders = [list(items)]
    best = None
    for k_, o in enumerate(orders):
        for pw in range(200, 900, 20):
            rows, wu, hu = shelf(pw, o)
            W, H = wu + 15, hu + 30
            sc = W * H * (1 + 2 * abs(math.log(W / H / 1.5))) * (1.0 if k_ == 0 else 1.04)     # reading order wins ties
            if best is None or sc < best[0]: best = (sc, rows, wu, hu)
    _, rows, wu, hu = best
    fill = sum(w * h for _, _, w, h in items) / ((wu + 15) * (hu + 30))
    print(f"{block}: page {wu + 15:.0f} x {hu + 30:.0f} mm, fill ratio {fill:.2f}")
    sheet.text(sheet.title, X0, 21, 3.0)
    for t, mem, x, y in rows:
        draw_section(t, mem, snap(x), snap(y), WC)
    sheet.maxx = max(sheet.maxx, wu + 5); sheet.maxy = max(sheet.maxy, hu + 5)


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
