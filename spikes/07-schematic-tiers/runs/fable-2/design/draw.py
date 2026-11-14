"""Draws KiCad schematic sheets from netlist.json. The netlist is the truth; these sheets are a view of it.

Style: every IC sits in its own zone with a label on each pin. The two-pin parts around it are drawn as small
cells next to it, each a familiar shape: a bank of parallel parts between two nets (decoupling), a vertical
chain of resistors (divider), or a single part. Nothing here decides connectivity: check.py exports KiCad's
own netlist of the result and compares it with netlist.json.

usage: draw.py <build dir> <out dir> <project name>
"""
import json, os, sys, uuid, math, zlib
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
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'

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
               hide_ref=False, hide_val=False, key=None, mirror=False, ref_just="left", val_just="left"):
        lid = self.lib(lib, name)
        x, y = snap(x), snap(y)
        self._ext(x + 10, y + 10)
        # KiCad turns field text with the symbol: undo that so text always reads left to right
        fa = 90 if angle in (90, 270) else 0
        flip = (angle in (90, 180)) != mirror
        def fj(j):
            if j == "center": return ""
            return "(justify " + ({"left": "right", "right": "left"}[j] if flip else j) + ")"
        rx, ry = ref_at or (x + 2.54, y - 1.27)
        vx, vy = val_at or (x + 2.54, y + 1.27)
        hid = lambda h: " (hide yes)" if h else ""
        props = [f'(property "Reference" {q(ref)} (at {rx:.2f} {ry:.2f} {fa}) (effects (font (size 1.27 1.27)) {fj(ref_just)}{hid(hide_ref)}))',
                 f'(property "Value" {q(value)} (at {vx:.2f} {vy:.2f} {fa}) (effects (font (size 1.27 1.27)) {fj(val_just)}{hid(hide_val)}))',
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
        ref = f"#PWR{zlib.crc32(self.name.encode()) % 900 + 100}{self.npwr:03d}"
        self.symbol("power", "GND", ref, "GND", x, y, angle, hide_ref=True, hide_val=True,
                    val_at=(snap(x) - 1.9, snap(y) + 5.0), key=f"pwr{self.npwr}")

    def pwr(self, name, x, y):
        """Rail arrow pointing up. KiCad takes the net of a power symbol from its value."""
        self.npwr += 1
        ref = f"#PWR{zlib.crc32(self.name.encode()) % 900 + 100}{self.npwr:03d}"
        self.symbol("power", "VCC", ref, name, x, y, 0, hide_ref=True, val_at=(snap(x), snap(y) - 3.6), val_just="center",
                    key=f"pwr{self.npwr}")

    def ground(self, sym, name, x, y, angle=0, show=True):
        """A second ground (a Kelvin or analogue return): its own symbol shape, named by its value."""
        self.npwr += 1
        ref = f"#PWR{zlib.crc32(self.name.encode()) % 900 + 100}{self.npwr:03d}"
        x, y = snap(x), snap(y)
        va = {0: (x, y + 3.4), 90: (x + 2.8, y), 270: (x - 2.8, y), 180: (x, y - 3.4)}[angle]
        self.symbol("power", sym, ref, name, x, y, angle, hide_ref=True, hide_val=not show, val_at=va,
                    val_just={0: "center", 180: "center", 90: "left", 270: "right"}[angle], key=f"pwr{self.npwr}")

    def rect(self, x1, y1, x2, y2):
        self.items.append(f'(rectangle (start {snap(x1)} {snap(y1)}) (end {snap(x2)} {snap(y2)}) (stroke (width 0.15) (type dash)) '
                          f'(fill (type none)) (uuid {q(uid(self.name, "r", x1, y1, x2, y2))}))')
        self._ext(x2, y2)

    def nc(self, x, y):
        x, y = snap(x), snap(y)
        self.items.append(f'(no_connect (at {x} {y}) (uuid {q(uid(self.name, "nc", x, y))}))')

    def text(self, s, x, y, size=1.27, bold=False, top=False):
        x, y = snap(x), snap(y)
        self.items.append(f'(text {q(s)} (exclude_from_sim no) (at {x} {y} 0) (effects (font (size {size} {size}){" (bold yes)" if bold else ""}) (justify left {"top" if top else "bottom"})) '
                          f'(uuid {q(uid(self.name, "t", s, x, y))}))')

    def write(self, path, page):
        w = max(297, math.ceil((self.maxx + 25) / 10) * 10)
        h = max(210, math.ceil((self.maxy + 25) / 10) * 10)
        if getattr(self, "paper", None): w, h = self.paper
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

    def inline_extent(r, net, extra=0):
        other = [n for n in ends(r) if n != net]
        users = [x for x in nets[net] if x[0] != r]
        stub = (2.54 if len(users) <= 1 else len(short(net)) * CH + 3.81) + extra
        tail = 10.16 if (not other or other[0] == "GND") else 2.54 + len(short(other[0])) * CH + (5.08 if other[0] in glob else 2.54)
        return stub, stub + 7.62 + tail, stub + 7.62 + tail + (len(r) + 1 + len(comps[r]["value"])) * TW + 2.54

    def inline(r, px, py, side, net, extra=0):
        """One two-pad part straight out of a pin on the pin's own row, ending in ground or a label, its text after it."""
        sg = 1 if side == "R" else -1
        stub, far, total = inline_extent(r, net, extra)
        other = [n for n in ends(r) if n != net]
        if stub - extra > 2.54: sheet.label(short(net), px, py, 0 if side == "R" else 180, False)
        xc = snap(px + sg * (stub + 3.81))
        tl = (len(r) + 1 + len(comps[r]["value"])) * TW
        xt = px + far if side == "R" else px - far - tl
        xl, xr = horiz(r, xc, py, net if side == "R" else (other[0] if other else net),
                       ref_at=(xt, py), val_at=(xt + (len(r) + 1) * TW, py))
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
        left = (max(len(short(n)) for n in labs) * CH + 6.35) if labs else (5.08 if att else 3 * CH + 6.35)
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
            x += w + 5.08
            wused = max(wused, x - x0)
        return wused, y + rowh - y0

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
            loc = sorted(n for n in cn if n in side_pin and n not in glob and rank(n) == 1)
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
        yl = [snap(yc + (k - (n - 1) / 2) * P_LANE) for k in range(n)]
        up = [k for k in range(n) if yl[k] < pys[k] - 0.01]; dn = [k for k in range(n) if yl[k] > pys[k] + 0.01]
        col = {}
        for i, k in enumerate(up): col[k] = i + 1                     # going up: top pin turns first; going down: bottom pin first
        for i, k in enumerate(reversed(dn)): col[k] = i + 1
        xs = snap(px + sg * (labx + 2.54 * (max([0] + list(col.values())) + 1)))
        ends_x = []
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
                if len(c[1]) == 1 and other and other[0] != "GND" and not tapped and series is None and net not in glob: series = c[1][0]
                else: hangs += c[1]
            x, end = snap(xs + sg * (2.54 + lroom)), xs
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
                if sg > 0:
                    xl, xr = horiz(series, x + 2.54 + 3.81, y, net, ref_at=(x + 2.54, y + 3.0), val_at=(x + 2.54, y + 5.0))
                    sheet.wire(end, y, xl, y); sheet.wire(xr, y, xr + 2.54, y); sheet.label(short(other), xr + 2.54, y, 0, other in glob)
                    x = xr + 2.54 + len(short(other)) * CH + 6.35; end = xr + 2.54
                else:
                    xl, xr = horiz(series, x - 2.54 - 3.81, y, other, ref_at=(x - 10.16, y + 3.0), val_at=(x - 10.16, y + 5.0))
                    sheet.wire(end, y, xr, y); sheet.wire(xl, y, xl - 2.54, y); sheet.label(short(other), xl - 2.54, y, 180, other in glob)
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
        return abs(xfar - px) + 2.54, top, yl[-1] + P_LANE

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
        for num, lst in list(banks.items()):
            c, n = lst[0]
            if len(lst) == 1 and len(c[1]) == 1 and n not in glob and num not in tapped:
                inl[num] = (side_of[num], c[1][0], n); del banks[num]
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
        inl_l = max([inline_extent(r, n, stag[nm])[2] for nm, (p, r, n) in inl.items() if p["angle"] == 0] + [0])
        inl_r = max([inline_extent(r, n, stag[nm])[2] for nm, (p, r, n) in inl.items() if p["angle"] == 180] + [0])
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
                if p["unit"] in (0, u): inline(r, snap(ox + p["x"]), snap(oy - p["y"]), "L" if p["angle"] == 0 else "R", n, stag[num])
            seen = set()
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
        return width, uy - y0, rest

    def draw_section(title, members, x0, y0, wcells):
        """A titled group: its ICs down the left, each with its cells to the right. Returns (width, height)."""
        mem = set(members)
        sec_anchors = [a for a in anchors if a in mem]
        claimed = {id(c) for a in anchors for c in zones[a]}        # drawn with their IC, whatever section they were written in
        if not sec_anchors and not [c for c in cells if c[1][0] in mem and id(c) not in claimed]: return 0, 0
        sheet.text(title, x0, y0 + 3.5, 2.0)
        y, wmax = y0 + 6.35, len(title) * 1.75
        placed = set()
        for a in sec_anchors:
            cs = zones[a]
            aw, ah, left_over = draw_anchor(a, x0, y, cs)
            y += ah + 2.54
            cw, ch = flow(left_over, x0, y, max(wcells, aw)) if left_over else (0, 0)
            wmax = max(wmax, aw, cw)
            y += ch + 5.08
        rest = [c for c in cells if c[1][0] in mem and id(c) not in claimed]
        if rest:
            cw, ch = flow(rest, x0, y, max(wcells + 60, wmax))
            wmax, y = max(wmax, cw), y + ch + 2.54
        return wmax, y - y0

    sections = []
    for r in refs:
        t = comps[r].get("section") or block
        if t not in [s_[0] for s_ in sections]: sections.append((t, []))
        [s_ for s_ in sections if s_[0] == t][0][1].append(r)
    PAGE_W, X0, Y0, GAP = 594.0, 20.32, 27.94, 7.62      # A2 landscape
    WC = 120
    # measure each section on a scratch sheet, then pack them in rows across the page
    real = sheet
    sizes = []
    for t, mem in sections:
        sheet = Sheet(real.name, real.project, real.root_uuid, real.title)
        sizes.append(draw_section(t, mem, 0, 0, WC))
    sheet = real
    sheet.text(sheet.title, X0, 21, 3.0)
    x, y, rowh = X0, Y0, 0
    for (t, mem), (w, h) in zip(sections, sizes):
        if not w: continue
        if x + w > PAGE_W - 15 and x > X0:
            x, y, rowh = X0, y + rowh + GAP, 0
        draw_section(t, mem, snap(x), snap(y), WC)
        x += w + GAP * 2
        rowh = max(rowh, h)
    sheet.maxy = max(sheet.maxy, y + rowh + 30)


def main(build, out, project):
    import scene, views
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
        view = views.VIEWS.get(b) or next((v for k, v in views.VIEWS.items() if k.endswith("*") and b.startswith(k[:-1])), None)
        if view:                                                  # a planned sheet: see scene.py and views/
            sc = scene.Scene(s, b, comps, nets, nc, cons, order)
            view(sc)
            s.paper = sc.page
            sc.finish()
            for l in sc.lint: print(f"  lint {b}: {l}")
        else:                                                     # no view written for this block: automatic drawing
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
