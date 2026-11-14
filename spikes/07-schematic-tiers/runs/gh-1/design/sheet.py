"""KiCad schematic sheet writer: symbols, wires, labels, texts, with automatic junctions, stretchable IC symbols,
paper sizing from the content, and a lint that reports what a person would call clutter.

Everything is in mm, y down, on a 1.27 mm grid. Nothing here decides connectivity.
"""
import copy, math, os, uuid
import symlib
from sx import find, first, get, val

NS = uuid.UUID("6f1c2b1e-58a5-4c6e-9a59-0d5a1f2b7c11")
G = 1.27
CH = 1.0
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


def text_w(s, size=1.27):
    """Width in mm of a string in KiCad's stroke font (measured from rendered PDFs, a little generous)."""
    w = 0.0
    for ch in s:
        if ch in ".,:;'|!": w += 0.6
        elif ch in "il1tjfIr()[]/ ": w += 0.85
        elif ch.islower(): w += 1.05
        else: w += 1.2
    return w * size / 1.27


# ------------------------------------------------------------------------------------------ symbols
def _remap(vals, req, olds_first):
    """vals: distinct coordinates in drawing order (first stays); req: {index: wanted gap}. Returns new coordinates."""
    out = [vals[0]]
    for i in range(1, len(vals)):
        gap = abs(vals[i] - vals[i - 1])
        out.append(out[-1] + math.copysign(max(gap, req.get(i, 0)), vals[i] - vals[i - 1]))
    return out


_stretch_cache = {}
_geom_cache = {}


def sym_node(lib, name, gaps=None):
    """Flattened symbol node; with gaps {"L": {pin: pitch}, "R": ..., "T"/"B": ...} the pins of that side are pulled
    apart (pitch = wanted distance to the pin before it on that side) and the body rectangle grows to match."""
    s = symlib.flat(lib, name)
    if not gaps: return s
    key = (lib, name, repr(gaps))
    if key in _stretch_cache: return copy.deepcopy(_stretch_cache[key])
    s = copy.deepcopy(s)
    units = find(s, "symbol")
    cust = gaps.get("_custom")
    if cust:
        fmt0 = lambda v: (f"{v:.4f}".rstrip("0").rstrip(".") or "0")
        for u in units:
            for p in find(u, "pin"):
                nm_ = get(p, "name")
                un_ = val(u[1]).rsplit("_", 2)[-2]
                key_ = nm_ + "#" + un_ if nm_ + "#" + un_ in cust["pins"] else nm_
                if key_ in cust["pins"]:
                    x_, y_, a_ = cust["pins"][key_]
                    at = first(p, "at"); at[1], at[2] = fmt0(x_), fmt0(y_)
                    if len(at) > 3: at[3] = str(a_)
                    else: at.append(str(a_))
            if cust.get("rect"):
                for r in find(u, "rectangle"):
                    x0_, y0_, x1_, y1_ = cust["rect"]
                    st, en = first(r, "start"), first(r, "end")
                    st[1], st[2], en[1], en[2] = fmt0(x0_), fmt0(y1_), fmt0(x1_), fmt0(y0_)
        if cust.get("gfx"):                    # take the body drawing of another symbol (the pins stay ours)
            g = symlib.flat(*cust["gfx"])
            gu = [u for u in find(g, "symbol") if val(u[1]).endswith("_0_1")][0]
            for u in units:
                if val(u[1]).endswith("_0_1"):
                    u[2:] = copy.deepcopy(gu[2:])
            pn = first(s, "pin_names")
            if pn is not None:
                pn[:] = ["pin_names", ["offset", "0"], ["hide", "yes"]]
        if not any(k in gaps for k in "LRTB"):
            _stretch_cache[key] = copy.deepcopy(s)
            return s
    sides = {"L": 0, "R": 180, "T": 270, "B": 90}
    info = []
    for u in units:
        for p in find(u, "pin"):
            at = first(p, "at")
            info.append(dict(node=p, x=float(at[1]), y=float(at[2]), a=int(float(at[3])) if len(at) > 3 else 0,
                             num=get(p, "number"), nm=get(p, "name")))
    if info:
        oldmin_y = min(i["y"] for i in info)
        for side, ang in sides.items():
            sp = [i for i in info if i["a"] == ang]
            if not sp: continue
            coord = "y" if side in "LR" else "x"
            distinct = sorted({i[coord] for i in sp}, reverse=side in "LR")
            req = {}
            for k, v in (gaps.get(side) or {}).items():
                for i in sp:
                    if k in (i["num"], i["nm"]): req[distinct.index(i[coord])] = v
            mp = dict(zip(distinct, _remap(distinct, req, None)))
            for i in sp: i["new_" + coord] = mp[i[coord]]
        new_miny = min([i["new_y"] for i in info if "new_y" in i] + [oldmin_y])
        dy = oldmin_y - new_miny                      # extra height added at the bottom
        xs = [i for i in info if "new_x" in i]
        dx = (max(i["new_x"] for i in xs) - max(i["x"] for i in xs)) if xs else 0
        fmt = lambda v: (f"{v:.4f}".rstrip("0").rstrip(".") or "0")
        for i in info:
            if "new_y" in i: i["y"] = i["new_y"]
            elif i["a"] == 90: i["y"] -= dy           # bottom pins ride on the bottom edge
            if "new_x" in i: i["x"] = i["new_x"]
            at = first(i["node"], "at")
            at[1], at[2] = fmt(i["x"]), fmt(i["y"])
        for u in units:
            for r in find(u, "rectangle"):
                st, en = first(r, "start"), first(r, "end")
                lo = en if float(en[2]) < float(st[2]) else st
                lo[2] = fmt(float(lo[2]) - dy)
                hi = en if float(en[1]) > float(st[1]) else st
                hi[1] = fmt(float(hi[1]) + dx)
    _stretch_cache[key] = copy.deepcopy(s)
    return s


def sym_pins(lib, name, gaps=None):
    """[{num,drawn,name,x,y,angle,unit,...}] in symbol coordinates, honouring a stretch."""
    if not gaps: return symlib.pins(lib, name)
    s = sym_node(lib, name, gaps)
    out = []
    for u in find(s, "symbol"):
        unit, style = (int(v) for v in val(u[1]).rsplit("_", 2)[-2:])
        if style > 1: continue
        for p in find(u, "pin"):
            at = first(p, "at"); num = get(p, "number")
            nums = [num]
            if num.startswith("[") and num.endswith("]"):
                nums = []
                for tok in num[1:-1].split(","):
                    if "-" in tok and all(t.strip().isdigit() for t in tok.split("-")):
                        a, b = (int(t) for t in tok.split("-")); nums += [str(i) for i in range(a, b + 1)]
                    else: nums.append(tok.strip())
            for n_ in nums:
                out.append(dict(num=n_, drawn=num, name=get(p, "name"), type=p[1], x=float(at[1]), y=float(at[2]),
                                angle=int(float(at[3])) if len(at) > 3 else 0, length=float(get(p, "length", 0)), unit=unit))
    return out


def body_box(lib, name, unit, gaps=None):
    """Bounding box (x0, y0, x1, y1) of a symbol body's graphics in symbol coordinates (y up), for the given unit."""
    key = (lib, name, unit, repr(gaps))
    if key in _geom_cache: return _geom_cache[key]
    s = sym_node(lib, name, gaps)
    xs, ys = [], []
    for u in find(s, "symbol"):
        un, style = (int(v) for v in val(u[1]).rsplit("_", 2)[-2:])
        if un not in (0, unit) or style > 1: continue
        for g in u[2:]:
            if not isinstance(g, list): continue
            if g[0] in ("rectangle", "polyline", "arc", "bezier"):
                for sub in g[1:]:
                    if isinstance(sub, list) and sub[0] in ("start", "end", "mid"):
                        xs.append(float(sub[1])); ys.append(float(sub[2]))
                    if isinstance(sub, list) and sub[0] == "pts":
                        for xy in sub[1:]:
                            xs.append(float(xy[1])); ys.append(float(xy[2]))
            elif g[0] == "circle":
                c = first(g, "center"); r = float(first(g, "radius")[1])
                xs += [float(c[1]) - r, float(c[1]) + r]; ys += [float(c[2]) - r, float(c[2]) + r]
    if not xs:
        for p in sym_pins(lib, name, gaps):
            if p["unit"] in (0, unit): xs.append(p["x"]); ys.append(p["y"])
    box = (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 0, 0)
    _geom_cache[key] = box
    return box


class Placed:
    """A symbol on a sheet: where its pins are."""
    def __init__(self, ref, x, y, angle, mirror, unit, pins, box):
        self.ref, self.x, self.y, self.angle, self.mirror, self.unit, self.box = ref, x, y, angle, mirror, unit, box
        self.pins = pins                         # list of dicts with sx, sy
    def pin(self, key):
        key = str(key)
        for p in self.pins:
            if p["num"] == key: return (p["sx"], p["sy"])
        for p in self.pins:
            if p["name"] == key: return (p["sx"], p["sy"])
        raise KeyError(f"{self.ref}: no pin {key}")
    def where(self, key):
        return self.pin(key)


class Sheet:
    def __init__(self, name, project, root_uuid, title):
        self.name, self.project, self.root_uuid, self.title = name, project, root_uuid, title
        self.uuid = uid("sheet", name)
        self.items, self.libs, self.npwr = [], {}, 0
        self.maxx = self.maxy = 0.0
        self.wires, self.texts, self.bodies, self.pinpts, self.labelpts, self.symrefs = [], [], [], [], [], []
        self.notes = []
        self.frames = []

    def _ext(self, x, y):
        self.maxx, self.maxy = max(self.maxx, x), max(self.maxy, y)

    def lib(self, lib, name, gaps=None):
        key = f"{lib}:{name}"
        if key not in self.libs:
            s = sym_node(lib, name, gaps)
            s[1] = ("s", key)
            self.libs[key] = dump(s)
            if gaps: self.libs[key + "#gaps"] = None
        return key

    # ---- text bookkeeping for lint ----
    def _tbox(self, kind, s, x, y, just, size=1.27, owner="", vert=False):
        w, h = text_w(s, size), size * 1.0
        if just == "l": x0, x1 = x, x + w
        elif just == "r": x0, x1 = x - w, x
        else: x0, x1 = x - w / 2, x + w / 2
        y0, y1 = y - h / 2, y + h / 2
        if vert: x0, x1, y0, y1 = x - h / 2, x + h / 2, y - w / 2, y + w / 2
        self.texts.append((kind, s, x0, y0, x1, y1, owner))
        self._ext(x1, y1)

    def symbol(self, lib, name, ref, value, x, y, angle=0, unit=1, footprint="", fields=None, ref_at=None, val_at=None,
               hide_ref=False, hide_val=False, key=None, mirror=False, gaps=None, ref_j=None, val_j=None):
        """Place a symbol. ref_at / val_at: (x, y) text anchors, optionally (x, y, 'l'|'r'|'c') for how the text hangs off
        the anchor on screen. Returns a Placed with the screen position of every pin."""
        lid = self.lib(lib, name, gaps)
        x, y = snap(x), snap(y)
        # KiCad turns field text with the symbol: undo that so text always reads left to right
        fa = 90 if angle in (90, 270) else 0
        my = mirror in (True, "y"); mx = mirror == "x"
        flip = (angle in (90, 180)) != my
        def fj(j):
            if j == "c": return ""
            vis_left = (j != "r")
            return "(justify left)" if (vis_left != flip) else "(justify right)"
        rx, ry, rj = (list(ref_at) + [None])[:3] if ref_at else (x + 2.54, y - 1.27, None)
        vx, vy, vj = (list(val_at) + [None])[:3] if val_at else (x + 2.54, y + 1.27, None)
        rj = rj or ref_j or "l"; vj = vj or val_j or "l"
        hid = lambda h: " (hide yes)" if h else ""
        props = [f'(property "Reference" {q(ref)} (at {rx:.2f} {ry:.2f} {fa}) (effects (font (size 1.27 1.27)) {fj(rj)}{hid(hide_ref)}))',
                 f'(property "Value" {q(value)} (at {vx:.2f} {vy:.2f} {fa}) (effects (font (size 1.27 1.27)) {fj(vj)}{hid(hide_val)}))',
                 f'(property "Footprint" {q(footprint)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))']
        for k, v in (fields or {}).items():
            props.append(f'(property {q(k)} {q(v)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        allpins = sym_pins(lib, name, gaps)
        pins = " ".join(f'(pin {q(p)} (uuid {q(uid(self.name, ref, unit, "pin", p))}))'
                        for p in sorted({p["drawn"] for p in allpins if p["unit"] in (0, unit)}))
        su = uid(self.name, "sym", key or ref, unit)
        self.items.append(
            f'(symbol (lib_id {q(lid)}) (at {x} {y} {angle}){" (mirror y)" if my else (" (mirror x)" if mx else "")} (unit {unit}) (exclude_from_sim no) (in_bom yes) (on_board yes) '
            f'(dnp no) (uuid {q(su)}) {" ".join(props)} {pins} '
            f'(instances (project {q(self.project)} (path {q("/" + self.root_uuid + "/" + self.uuid)} (reference {q(ref)}) (unit {unit})))))')
        # geometry
        pl = []
        for p in allpins:
            if p["unit"] not in (0, unit): continue
            dx, dy = rot(p["x"], p["y"], angle)
            if my: dx = -dx
            if mx: dy = -dy
            pl.append(dict(num=p["num"], name=p["name"], sx=snap(x + dx), sy=snap(y + dy), ang=p["angle"]))
            self.pinpts.append((snap(x + dx), snap(y + dy)))
        bx0, by0, bx1, by1 = body_box(lib, name, unit, gaps)
        cs = []
        for cx, cy in ((bx0, by0), (bx0, by1), (bx1, by0), (bx1, by1)):
            dx, dy = rot(cx, cy, angle)
            if my: dx = -dx
            if mx: dy = -dy
            cs.append((x + dx, y + dy))
        box = (min(c[0] for c in cs), min(c[1] for c in cs), max(c[0] for c in cs), max(c[1] for c in cs))
        if lib != "power":
            self.bodies.append((ref, unit) + box)
            self._ext(box[2], box[3])
            if not hide_ref: self._tbox("ref", ref, rx, ry, rj, owner=ref)
            if not hide_val: self._tbox("val", value, vx, vy, vj, owner=ref)
        self.symrefs.append(ref)
        return Placed(ref, x, y, angle, mirror, unit, pl, box)

    def wire(self, x1, y1, x2, y2):
        x1, y1, x2, y2 = snap(x1), snap(y1), snap(x2), snap(y2)
        if (x1, y1) == (x2, y2): return
        self._ext(max(x1, x2), max(y1, y2))
        self.wires.append((x1, y1, x2, y2))
        self.items.append(f'(wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default)) '
                          f'(uuid {q(uid(self.name, "w", x1, y1, x2, y2))}))')

    def path(self, *pts):
        """Wire through points; each leg must be horizontal or vertical (an elbow is added when it is not)."""
        pts = [(snap(a), snap(b)) for a, b in pts]
        for (a, b), (c, d) in zip(pts, pts[1:]):
            if a != c and b != d:
                self.wire(a, b, c, b); self.wire(c, b, c, d)
            else:
                self.wire(a, b, c, d)

    def junction(self, x, y):
        pass                                                         # junctions are computed from the wires on write

    def label(self, text, x, y, angle, glob):
        x, y = snap(x), snap(y)
        self._ext(x, y)
        j = {0: "(justify left bottom)", 90: "(justify left bottom)", 180: "(justify right bottom)", 270: "(justify right bottom)"}[angle]
        self.labelpts.append((x, y))
        w = text_w(text)
        if glob:
            j = {0: "(justify left)", 90: "(justify left)", 180: "(justify right)", 270: "(justify right)"}[angle]
            self.items.append(f'(global_label {q(text)} (shape passive) (at {x} {y} {angle}) {FONT.format(j=j)} '
                              f'(uuid {q(uid(self.name, "gl", text, x, y))}) (property "Intersheetrefs" "${{INTERSHEET_REFS}}" '
                              f'(at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes))))')
            wt = w + 2.2
            box = {0: (x, y - 1, x + wt, y + 1), 180: (x - wt, y - 1, x, y + 1),
                   90: (x - 1, y - wt, x + 1, y), 270: (x - 1, y, x + 1, y + wt)}[angle]
            self.texts.append(("glabel", text, *box, ""))
        else:
            self.items.append(f'(label {q(text)} (at {x} {y} {angle}) {FONT.format(j=j)} (uuid {q(uid(self.name, "l", text, x, y))}))')
            if angle == 0: box = (x, y - 1.35, x + w, y - 0.05)
            elif angle == 180: box = (x - w, y - 1.35, x, y - 0.05)
            elif angle == 90: box = (x - 1.35, y - w, x - 0.05, y)
            else: box = (x - 1.35, y, x - 0.05, y + w)
            self.texts.append(("label", text, *box, ""))
        self._ext(box[2], box[3])

    def gnd(self, x, y, angle=0):
        self.npwr += 1
        ref = f"#PWR{abs(hash(self.name)) % 90 + 10}{self.npwr:03d}"
        self.symbol("power", "GND", ref, "GND", x, y, angle, hide_ref=True, hide_val=True,
                    val_at=(snap(x) - 1.9, snap(y) + 5.0), key=f"pwr{self.npwr}")
        if angle == 0: self.texts.append(("gnd", "", x - 1.3, y, x + 1.3, y + 3, ""))

    def pwr(self, name, value, x, y, angle=0, show=True):
        """A named ground-style symbol (a net that behaves like a ground, such as a Kelvin return)."""
        self.npwr += 1
        ref = f"#PWR{abs(hash(self.name)) % 90 + 10}{self.npwr:03d}"
        xs, ys = snap(x), snap(y)
        show = show and angle == 0
        self.symbol("power", name, ref, value, xs, ys, angle, hide_ref=True, hide_val=not show, key=f"pwr{self.npwr}",
                    val_at=(xs, ys + 3.4, "c"))
        if show: self._tbox("val", value, xs, ys + 3.4, "c")
        self.texts.append(("gnd", "", xs - 1.3, ys, xs + 1.3, ys + 2.6, ""))

    def rail(self, net, x, y, name="+3V3"):
        """A supply symbol pointing up, its value showing the net name (the net is global, like a global label)."""
        self.npwr += 1
        ref = f"#PWR{abs(hash(self.name)) % 90 + 10}{self.npwr:03d}"
        xs, ys = snap(x), snap(y)
        self.symbol("power", name, ref, net, xs, ys, 0, hide_ref=True, hide_val=False, key=f"pwr{self.npwr}",
                    val_at=(xs, ys - 3.6, "c"))
        self._tbox("val", net, xs, ys - 3.6, "c")
        self.texts.append(("rail", "", xs - 1, ys - 2.6, xs + 1, ys, ""))

    def nc(self, x, y):
        x, y = snap(x), snap(y)
        self.items.append(f'(no_connect (at {x} {y}) (uuid {q(uid(self.name, "nc", x, y))}))')

    def text(self, s, x, y, size=1.27, just="left bottom"):
        x, y = snap(x), snap(y)
        lines = s.split("\n")
        self.items.append(f'(text {q(s)} (exclude_from_sim no) (at {x} {y} 0) (effects (font (size {size} {size})) (justify {just})) '
                          f'(uuid {q(uid(self.name, "t", s, x, y))}))')
        w = max(text_w(l, size) for l in lines); h = size * 1.45 * len(lines)
        x0 = x if "left" in just else (x - w if "right" in just else x - w / 2)
        y1 = y if "bottom" in just else (y + h if "top" in just else y + h / 2)
        self.texts.append(("text", lines[0], x0, y1 - h, x0 + w, y1, ""))
        self._ext(x0 + w, y1)

    # ---- grouping frames ----
    def mark(self): return (len(self.wires), len(self.texts), len(self.bodies))

    def bbox_since(self, m):
        xs, ys = [], []
        for w in self.wires[m[0]:]: xs += [w[0], w[2]]; ys += [w[1], w[3]]
        for t in self.texts[m[1]:]:
            if t[0] in ("gnd", "rail") : xs += [t[2], t[4]]; ys += [t[3], t[5]]
            else: xs += [t[2], t[4]]; ys += [t[3], t[5]]
        for b in self.bodies[m[2]:]: xs += [b[2], b[4]]; ys += [b[3], b[5]]
        return (min(xs), min(ys), max(xs), max(ys))

    def frame(self, x0, y0, x1, y1):
        x0, y0, x1, y1 = (round(v, 2) for v in (x0, y0, x1, y1))
        self.frames.append((x0, y0, x1, y1))
        self.items.append(f'(rectangle (start {x0} {y0}) (end {x1} {y1}) (stroke (width 0.2) (type dash)) (fill (type none)) '
                          f'(uuid {q(uid(self.name, "f", x0, y0, x1, y1))}))')
        self._ext(x1, y1)

    # ---- junctions and extents ----
    def _junctions(self):
        ends, mid, pins = {}, {}, {}
        for p in self.pinpts: pins[p] = pins.get(p, 0) + 1
        for x1, y1, x2, y2 in self.wires:
            for e in ((x1, y1), (x2, y2)): ends[e] = ends.get(e, 0) + 1
        pts = set(ends) | set(pins)
        out = []
        for pt in pts:
            n = ends.get(pt, 0) + pins.get(pt, 0)
            thru = 0
            for x1, y1, x2, y2 in self.wires:
                if x1 == x2 == pt[0] and min(y1, y2) < pt[1] < max(y1, y2): thru += 1
                elif y1 == y2 == pt[1] and min(x1, x2) < pt[0] < max(x1, x2): thru += 1
            if n >= 1 and n + 2 * thru >= 3 and not (n == 1 and thru == 1 and pins.get(pt, 0) == 1 and False):
                out.append(pt)
        return sorted(out)

    def _split_wires(self, js):
        """Cut every wire that passes through a junction point, so each connection is wire end to wire end."""
        jset = set(js)
        newitems, kept = [], []
        for it in self.items:
            if not it.startswith("(wire "): newitems.append(it); continue
            newitems.append(it)
        # rebuild wire items from the geometry
        wires = []
        for (x1, y1, x2, y2) in self.wires:
            cuts = [p for p in jset if (x1 == x2 == p[0] and min(y1, y2) < p[1] < max(y1, y2)) or (y1 == y2 == p[1] and min(x1, x2) < p[0] < max(x1, x2))]
            if not cuts: wires.append((x1, y1, x2, y2)); continue
            pts = sorted(cuts + [(x1, y1), (x2, y2)], key=lambda p: (p[0] - x1) ** 2 + (p[1] - y1) ** 2)
            wires += [(a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:])]
        self.items = [it for it in self.items if not it.startswith("(wire ")]
        seen = set()
        for (x1, y1, x2, y2) in wires:
            k = (min((x1, y1), (x2, y2)), max((x1, y1), (x2, y2)))
            if k in seen: continue
            seen.add(k)
            self.items.append(f'(wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default)) '
                              f'(uuid {q(uid(self.name, "w", x1, y1, x2, y2))}))')

    def content_box(self):
        xs, ys = [], []
        for w in self.wires: xs += [w[0], w[2]]; ys += [w[1], w[3]]
        for t in self.texts: xs += [t[2], t[4]]; ys += [t[3], t[5]]
        for b in self.bodies: xs += [b[2], b[4]]; ys += [b[3], b[5]]
        for f in self.frames: xs += [f[0], f[2]]; ys += [f[1], f[3]]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 100, 100)

    def write(self, path, page, paper=None):
        js = self._junctions()
        # self._split_wires(js)
        for jx, jy in js:
            self.items.append(f'(junction (at {jx} {jy}) (diameter 0) (color 0 0 0 0) (uuid {q(uid(self.name, "j", jx, jy))}))')
        x0, y0, x1, y1 = self.content_box()
        w = max(150, math.ceil((x1 + 12) / 10) * 10)
        h = math.ceil((y1 + 12) / 10) * 10
        # keep clear of the title block (about 112 x 36 mm in the bottom right corner)
        tb = (w - 10 - 112, h - 10 - 36)
        hit = lambda: any(t[4] > tb[0] and t[5] > tb[1] for t in self.texts) or any(
            max(a, c) > tb[0] and max(b, d) > tb[1] for a, b, c, d in self.wires) or any(
            b[4] > tb[0] and b[5] > tb[1] for b in self.bodies)
        if hit(): h += 40
        h = max(h, 110)
        paper = paper or getattr(self, 'force_paper', None)
        if paper: w, h = paper
        out = [f'(kicad_sch (version {VERSION}) (generator "p2p_draw") (generator_version "10.0") (uuid {q(self.uuid)}) '
               f'(paper "User" {w} {h}) (title_block (title {q(self.title)}) (comment 1 "Generated from code. Do not edit: change the block source and rebuild."))',
               "(lib_symbols " + "\n".join(v for k, v in self.libs.items() if v is not None) + ")"]
        out += self.items
        out.append("(embedded_fonts no))")
        open(path, "w").write("\n".join(out) + "\n")
        self.paper = (w, h)

    # ---- lint ----
    def lint(self):
        """Offences a person would call clutter. Returns a list of strings."""
        out = []
        T = self.texts
        eps = 0.25
        def ov(a, b):
            return a[0] < b[2] - eps and b[0] < a[2] - eps and a[1] < b[3] - eps and b[1] < a[3] - eps
        tb = [t for t in T if t[0] not in ("gnd", "rail")]
        for i in range(len(tb)):
            for j in range(i + 1, len(tb)):
                a, b = tb[i], tb[j]
                if ov(a[2:6], b[2:6]): out.append(f"text/text: '{a[1]}' ({a[0]}) x '{b[1]}' ({b[0]}) at {a[2]:.0f},{a[3]:.0f}")
        for t in tb:
            if t[0] in ("label", "glabel"): continue
            for (x1, y1, x2, y2) in self.wires:
                bx = (min(x1, x2) - 0.0, min(y1, y2) - 0.0, max(x1, x2) + 0.0, max(y1, y2) + 0.0)
                if ov(t[2:6], (bx[0], bx[1] - 0.0001, max(bx[2], bx[0] + 0.0002), bx[3] + 0.0001)) and (bx[2] - bx[0] > 0.01 or bx[3] - bx[1] > 0.01):
                    out.append(f"text/wire: '{t[1]}' ({t[0]}) on a wire at {t[2]:.0f},{t[3]:.0f}"); break
        for t in tb:
            if t[0] not in ("label", "glabel"): continue
            for (x1, y1, x2, y2) in self.wires:
                bx = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                if ov(t[2:6], bx) and (bx[2] - bx[0] > 0.01 or bx[3] - bx[1] > 0.01):
                    # a label may sit on its own wire; flag only wires that cross its text
                    out.append(f"label/wire: '{t[1]}' crossed by a wire at {t[2]:.0f},{t[3]:.0f}"); break
        for k, b in enumerate(self.bodies):
            inner = (b[2] + 0.35, b[3] + 0.35, b[4] - 0.35, b[5] - 0.35)
            if inner[2] <= inner[0] or inner[3] <= inner[1]: continue
            for (x1, y1, x2, y2) in self.wires:
                bx = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                if bx[0] < inner[2] and bx[2] > inner[0] and bx[1] < inner[3] and bx[3] > inner[1]:
                    out.append(f"wire/symbol: wire {x1:.1f},{y1:.1f}-{x2:.1f},{y2:.1f} crosses {b[0]}"); break
            for t in tb:
                if t[6] == b[0] or t[0] in ("glabel",): continue
                if ov(t[2:6], (inner[0], inner[1], inner[2], inner[3])) and t[0] not in ("ref", "val") or (t[0] in ("ref", "val") and t[6] != b[0] and ov(t[2:6], inner)):
                    out.append(f"text/symbol: '{t[1]}' ({t[0]}) over {b[0]}"); break
            for k2 in range(k + 1, len(self.bodies)):
                c = self.bodies[k2]
                if c[0] == b[0] and c[1] != b[1]: continue
                if ov(b[2:], c[2:]): out.append(f"symbol/symbol: {b[0]} overlaps {c[0]}")
        # wire passing through a foreign pin or end of another net's wire is caught by the netlist check; report long wires
        for (x1, y1, x2, y2) in self.wires:
            if abs(x2 - x1) + abs(y2 - y1) > 90: out.append(f"long wire {x1:.0f},{y1:.0f}-{x2:.0f},{y2:.0f} ({abs(x2 - x1) + abs(y2 - y1):.0f} mm)")
        return out


FONT = "(effects (font (size 1.27 1.27)) {j})"
