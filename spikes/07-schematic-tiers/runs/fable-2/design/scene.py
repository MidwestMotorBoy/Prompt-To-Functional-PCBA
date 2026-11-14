"""Scene: the drawing toolkit a block's *view* is written with.

A view (design/views/*.py) says where things go, the way an engineer plans a sheet: "this IC here, its input
caps on a rail to the left, the divider standing at the output". It never says what is connected: every point
handed around carries its net from netlist.json, and the toolkit refuses to wire two different nets together.
What the view leaves out is finished automatically: an untouched pin gets a ground symbol, a rail symbol, a
no-connect mark or a label; junction dots are added where wires meet. Before the sheet is written it is checked
twice: `netcheck` rebuilds the connectivity of the drawing and compares it with the netlist (so a mistake is
reported with coordinates, before KiCad is even run), and `lint` reports text, symbols and wires that overlap.

Coordinates given by a view are in units of U = 2.54 mm (one pin pitch), relative to the current section.
"""
import symlib
from sx import find

U = 2.54
G = 1.27
CW = 1.15                      # mm per character of 1.27 mm text
DIRS = {"L": (-1, 0), "R": (1, 0), "U": (0, -1), "D": (0, 1)}
OPP = {"L": "R", "R": "L", "U": "D", "D": "U"}


def snap(v):
    return round(round(v / G) * G, 4)


def rot(x, y, a):
    """Symbol coordinates (y up) rotated a degrees, returned as a screen offset (y down)."""
    a = a % 360
    if a == 0: xr, yr = x, y
    elif a == 90: xr, yr = -y, x
    elif a == 180: xr, yr = -x, -y
    else: xr, yr = y, -x
    return xr, -yr


class Pt:
    """A point of the drawing that knows its net and which way is 'away from the part'."""
    __slots__ = ("x", "y", "net", "d")
    def __init__(self, x, y, net=None, d=None):
        self.x, self.y, self.net, self.d = snap(x), snap(y), net, d
    @property
    def xy(self): return (self.x, self.y)
    def turn(self, d): return Pt(self.x, self.y, self.net, d)
    def __repr__(self): return f"Pt({self.x / U:g}u,{self.y / U:g}u,{self.net},{self.d})"


_bbox_cache = {}
def body_box(lib, name, unit):
    """Bounding box of a symbol unit's drawn body in symbol coordinates (y up): (x0, y0, x1, y1)."""
    key = (lib, name, unit)
    if key in _bbox_cache: return _bbox_cache[key]
    xs, ys = [], []
    def num(v):
        try: return float(v)
        except (TypeError, ValueError): return None
    def walk(n):
        if not isinstance(n, list) or not n: return
        if n[0] in ("xy", "start", "end", "mid") and len(n) >= 3 and num(n[1]) is not None:
            xs.append(float(n[1])); ys.append(float(n[2]))
        elif n[0] == "circle":
            c = [c for c in n if isinstance(c, list) and c[0] == "center"][0]
            r = float([c for c in n if isinstance(c, list) and c[0] == "radius"][0][1])
            xs.extend([float(c[1]) - r, float(c[1]) + r]); ys.extend([float(c[2]) - r, float(c[2]) + r])
        elif n[0] in ("pin", "property", "text"):
            return
        else:
            for c in n[1:]: walk(c)
    s = symlib.flat(lib, name)
    for u in find(s, "symbol"):
        un = int(str(u[1][1] if isinstance(u[1], tuple) else u[1]).rsplit("_", 2)[-2])
        if un in (0, unit): walk(u)
    if not xs:
        ps = [p for p in symlib.pins(lib, name) if p["unit"] in (0, unit)]
        xs = [p["x"] for p in ps]; ys = [p["y"] for p in ps]
    _bbox_cache[key] = (min(xs), min(ys), max(xs), max(ys))
    return _bbox_cache[key]


class Sym:
    def __init__(self, scene, ref, x, y, angle, mirror, unit):
        self.s, self.ref, self.x, self.y, self.angle, self.mirror, self.unit = scene, ref, x, y, angle, mirror, unit
        self.lib, self.name = scene.comps[ref]["lib"].split(":")
        self.pins = [p for p in scene.pins_of(ref) if p["unit"] in (0, unit)]
        x0, y0, x1, y1 = body_box(self.lib, self.name, unit)
        cs = [self._tr(a, b) for a in (x0, x1) for b in (y0, y1)]
        self.box = (min(c[0] for c in cs), min(c[1] for c in cs), max(c[0] for c in cs), max(c[1] for c in cs))

    def _tr(self, px, py):
        if self.mirror: px = -px
        dx, dy = rot(px, py, self.angle)
        return snap(self.x + dx) if abs(dx / G - round(dx / G)) < 1e-6 else self.x + dx, \
               snap(self.y + dy) if abs(dy / G - round(dy / G)) < 1e-6 else self.y + dy

    def _dir(self, p):
        dx, dy = rot(*{0: (-1, 0), 180: (1, 0), 90: (0, -1), 270: (0, 1)}[p["angle"]], self.angle)
        if self.mirror and self.angle in (0, 180): dx = -dx
        if self.mirror and self.angle in (90, 270): dy = -dy
        return {(-1, 0): "L", (1, 0): "R", (0, -1): "U", (0, 1): "D"}[(round(dx), round(dy))]

    def p(self, key):
        """Pin by name or number -> Pt (the pin's connection point, its net, the direction away from the body)."""
        key = str(key)
        m = [p for p in self.pins if p["num"] == key] or [p for p in self.pins if p["name"] == key]
        if not m: raise KeyError(f"{self.ref} unit {self.unit} has no pin {key}: {sorted({p['name'] for p in self.pins})}")
        m.sort(key=lambda p: p["hidden"])
        p = m[0]
        x, y = self._tr(p["x"], p["y"])
        return Pt(x, y, self.s.pinnet.get((self.ref, p["num"])), self._dir(p))

    def all_pins(self):
        for p in self.pins:
            x, y = self._tr(p["x"], p["y"])
            yield p, Pt(x, y, self.s.pinnet.get((self.ref, p["num"])), self._dir(p))

    @property
    def left(self): return self.box[0]
    @property
    def right(self): return self.box[2]
    @property
    def top(self): return self.box[1]
    @property
    def bottom(self): return self.box[3]


class SceneError(Exception):
    pass


class Scene:
    def __init__(self, sheet, block, comps, nets, nc, cons, order):
        self.sheet, self.block, self.comps, self.cons = sheet, block, comps, cons
        self.refs = [r for r in order if comps[r]["block"] == block]
        refset = set(self.refs)
        self.nets = nets
        self.pinnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes if r in refset}
        self.ncset = {(r, p) for r, p in nc}
        self.glob = {n for n, nodes in nets.items() if any(r not in refset for r, _ in nodes) and any(r in refset for r, _ in nodes)}
        self.rails = {n for n in self.glob if cons["nets"].get(n, {}).get("kind") == "power" or n in ("3V3",)}
        self.alias = {}
        self.grounds = {}                 # net -> power-library symbol drawn for it (a second ground)
        self.quiet = False
        self.ox = self.oy = 0.0
        self.syms = []                    # placed Sym
        self.placed = {}                  # ref -> set of units placed
        self.wires = []                   # (x1, y1, x2, y2)
        self.marks = {}                   # (x, y) -> list of ("label", text, glob) | ("gnd",) | ("pwr", text) | ("nc",)
        self.rects = []                   # lint: (kind, x0, y0, x1, y1, tag)
        self.page = (297.0, 210.0)
        self.errors = []
        self._pins = {}
        base = [int(r[1:]) for r in self.refs if r[0] == "U" and r[1:].isdigit()]
        self.base = (min(base) // 100) * 100 if base else 0

    # ---- names -------------------------------------------------------------------------------------------------
    def r(self, k):
        """Reference number for a block that is used more than once: r(3) -> '403' on port 1, '503' on port 2."""
        return str(self.base + k)

    def pins_of(self, ref):
        if ref not in self._pins: self._pins[ref] = symlib.pins(*self.comps[ref]["lib"].split(":"))
        return self._pins[ref]

    def name(self, n):
        if n in self.alias: return self.alias[n]
        return n.lstrip("/") if n in self.glob else n.split("/")[-1]

    def net(self, short):
        """Full net name from the name shown on the sheet."""
        for n in self.nets:
            if self.name(n) == short and any((r, p) in self.pinnet for r, p in self.nets[n]): return n
        raise KeyError(short)

    def ends(self, ref):
        return [self.pinnet.get((ref, n)) for n in sorted({p["num"] for p in self.pins_of(ref)})]

    # ---- coordinates -------------------------------------------------------------------------------------------
    def mm(self, pos):
        if isinstance(pos, Pt): return pos.x, pos.y
        return snap(self.ox + pos[0] * U), snap(self.oy + pos[1] * U)

    def pt(self, xu, yu, net=None, d=None):
        x, y = self.mm((xu, yu))
        return Pt(x, y, self.net(net) if isinstance(net, str) and net not in self.nets else net, d)

    def ux(self, p): return (p.x - self.ox) / U
    def uy(self, p): return (p.y - self.oy) / U

    # ---- sections and text -------------------------------------------------------------------------------------
    def section(self, title, xu, yu, wu, hu, note=None, note_at=None):
        """A titled, framed region. Everything drawn after this call is positioned relative to its top left corner."""
        self.ox, self.oy = snap(xu * U), snap(yu * U)
        x1, y1 = snap(self.ox + wu * U), snap(self.oy + hu * U)
        self.sheet.rect(self.ox, self.oy, x1, y1)
        self.sheet.text(title, self.ox + 1.6, self.oy + 1.4, 1.9, bold=True, top=True)
        self.rects.append(("text", self.ox + 1.6, self.oy + 1.2, self.ox + 1.6 + len(title) * 1.75, self.oy + 3.6, "title " + title))
        self.rects.append(("frame", self.ox, self.oy, x1, y1, title))
        if note: self.note(note_at[0] if note_at else 0.7, note_at[1] if note_at else 2.2, note)

    def note(self, xu, yu, s, size=1.1):
        x, y = self.mm((xu, yu))
        self.sheet.text(s, x, y, size, top=True)
        lines = s.split("\n")
        self.rects.append(("text", x, y, x + max(len(l) for l in lines) * size * 0.84, y + len(lines) * size * 1.62, "note " + lines[0][:20]))

    # ---- symbols -----------------------------------------------------------------------------------------------
    def _place(self, ref, x, y, angle, mirror, unit, ref_at, val_at, rj="left", vj="left", hide_val=False):
        c = self.comps[ref]
        lib, name = c["lib"].split(":")
        sym = Sym(self, ref, snap(x), snap(y), angle, mirror, unit)
        if unit in self.placed.setdefault(ref, set()): raise SceneError(f"{ref} unit {unit} placed twice")
        self.placed[ref].add(unit)
        self.sheet.symbol(lib, name, ref, c["value"], sym.x, sym.y, angle, unit=unit, footprint=c["footprint"], fields=c["fields"],
                          ref_at=ref_at, val_at=val_at, mirror=mirror, ref_just=rj, val_just=vj, hide_val=hide_val)
        self.syms.append(sym)
        b = sym.box
        self.rects.append(("body", b[0], b[1], b[2], b[3], ref))
        for (tx, ty), txt, j in ((ref_at, ref, rj), (val_at, c["value"], vj)):
            if txt is c["value"] and hide_val: continue
            w = len(txt) * CW
            x0 = tx if j == "left" else tx - w if j == "right" else tx - w / 2
            self.rects.append(("text", x0, ty - 0.8, x0 + w, ty + 0.8, f"{ref} field"))
        return sym

    def ic(self, ref, xu, yu, unit=1, mirror=False, text=None, angle=0, hide_val=False, just="left"):
        """Place a multi-pin part with its centre at (xu, yu). text=(xu, yu): where the reference goes, relative to the
        centre (the value goes on the line below); default is above the top left corner of the body."""
        x, y = self.mm((xu, yu))
        tmp = Sym(self, ref, x, y, angle, mirror, unit)
        if text: tx, ty = x + text[0] * U, y + text[1] * U
        else: tx, ty = tmp.box[0], tmp.box[1] - 3.3
        return self._place(ref, x, y, angle, mirror, unit, (tx, ty), (tx, ty + 1.9), just, just, hide_val=hide_val)

    def tp(self, ref, at, d="U", text="R"):
        """A one-pin part (test point, wire pad) on point `at`, its body pointing in direction d."""
        p = self.pins_of(ref)[0]
        if self.pinnet.get((ref, p["num"])) != at.net: raise SceneError(f"{ref} is not on {at.net}")
        out = {0: (-1, 0), 180: (1, 0), 90: (0, -1), 270: (0, 1)}[p["angle"]]      # pin's outward direction, y up
        for a in (0, 90, 180, 270):
            ox, oy = rot(out[0], out[1], a)
            if (round(ox), round(oy)) == tuple(-v for v in DIRS[d]): break
        px, py = rot(p["x"], p["y"], a)
        cx, cy = snap(at.x - px), snap(at.y - py)
        tmp = Sym(self, ref, cx, cy, a, False, 1)
        b = tmp.box
        if text == "R": t, j = (b[2] + 0.8, (b[1] + b[3]) / 2 - 1.0), "left"
        elif text == "L": t, j = (b[0] - 0.8, (b[1] + b[3]) / 2 - 1.0), "right"
        elif text == "U": t, j = ((b[0] + b[2]) / 2, b[1] - 3.0), "center"
        else: t, j = ((b[0] + b[2]) / 2, b[3] + 1.2), "center"
        self._place(ref, cx, cy, a, False, 1, t, (t[0], t[1] + 1.9), j, j)

    def two(self, ref, at, d=None, gap=1.0, text=None):
        """Place a two-pin part in line with point `at`, heading in direction d (default: the point's own direction),
        gap units of wire away from it. The pin that belongs on the point's net goes on the point's side.
        Returns the point at the far pin (carrying the net of that pin)."""
        d = d or at.d
        dx, dy = DIRS[d]
        pp = {}
        for p in self.pins_of(ref): pp.setdefault(p["num"], p)
        nums = sorted(pp)
        if len(nums) != 2: raise SceneError(f"{ref} is not a two-pin part")
        e = [self.pinnet.get((ref, n)) for n in nums]
        if at.net not in e: raise SceneError(f"{ref} has no pin on {at.net} (it is across {e}); asked at {at}")
        near, far = (nums[0], nums[1]) if e[0] == at.net else (nums[1], nums[0])
        for a in (0, 90, 180, 270):
            nx, ny = rot(pp[near]["x"], pp[near]["y"], a); fx, fy = rot(pp[far]["x"], pp[far]["y"], a)
            if abs(fx - nx - dx * 7.62) < 0.01 and abs(fy - ny - dy * 7.62) < 0.01: break
        else: raise SceneError(f"{ref}: cannot orient")
        cx, cy = snap(at.x + dx * (gap * U) - nx), snap(at.y + dy * (gap * U) - ny)
        lib, name = self.comps[ref]["lib"].split(":")
        tmp = Sym(self, ref, cx, cy, a, False, 1)
        b = tmp.box
        val = self.comps[ref]["value"]
        if d in ("U", "D"):
            side = text or "R"
            if side == "R": ra, va, j = (b[2] + 0.7, cy - 1.05), (b[2] + 0.7, cy + 1.05), "left"
            elif side == "L": ra, va, j = (b[0] - 0.7, cy - 1.05), (b[0] - 0.7, cy + 1.05), "right"
            else: raise SceneError("text side for a vertical part is L or R")
        else:
            side = text or "T"
            j = "center"
            if side == "T": ra, va = (cx, b[1] - 2.9), (cx, b[1] - 1.1)
            elif side == "B": ra, va = (cx, b[3] + 1.2), (cx, b[3] + 3.0)
            elif side == "S": ra, va = (cx, b[1] - 1.1), (cx, b[3] + 1.2)
            else: raise SceneError("text side for a horizontal part is T, B or S")
        sym = self._place(ref, cx, cy, a, False, 1, ra, va, j, j)
        pn = Pt(cx + nx, cy + ny, at.net)
        if gap: self.wire(at, pn)
        return Pt(cx + fx, cy + fy, self.pinnet.get((ref, far)), d)

    def shunt(self, ref, at, d="D", gap=1.0, text=None, tail=0.0, name=False):
        """A two-pin part from the point to ground, a rail or a named net: placed like two(), then ended."""
        f = self.two(ref, at, d, gap, text)
        if tail: f = self.go(f, **({"dx": tail * DIRS[d][0]} if d in "LR" else {"dy": tail * DIRS[d][1]}))
        self.end(f)
        return f

    def bank(self, refs, at, d="R", pitch=None, first=None, hang="D", text=None, tail=0.0):
        """Parts side by side hanging from one rail that starts at `at` and runs in direction d.
        Returns the point at the end of the rail (over the last part)."""
        p = at
        for i, r in enumerate(refs):
            trailing = ((text or "R") == "R") == (d == "R")         # the previous part's text lies between the two parts
            step = (first if first is not None else 2.0) if i == 0 else (pitch or self.pitch(refs[i - 1] if trailing else r))
            p = self.go(p, dx=step * DIRS[d][0])
            self.shunt(r, p, hang, text=text, tail=tail)
        return p

    def pitch(self, ref):
        """Units of room a vertical part needs beside it for its text."""
        w = max(len(ref), len(self.comps[ref]["value"])) * CW + 5.2
        return max(3.0, -(-w // G) * G / U)

    # ---- wires, ends -------------------------------------------------------------------------------------------
    def _seg(self, x1, y1, x2, y2):
        x1, y1, x2, y2 = snap(x1), snap(y1), snap(x2), snap(y2)
        if (x1, y1) == (x2, y2): return
        if x1 != x2 and y1 != y2: raise SceneError(f"diagonal wire {(x1, y1, x2, y2)}")
        self.wires.append((x1, y1, x2, y2))

    def wire(self, a, b, mode=None):
        """Wire from a to b (points, or (xu, yu) for b). Not in line: mode 'hv' goes sideways first, 'vh' up/down first.
        Both points must be on the same net. Returns b as a point on that net."""
        bx, by = self.mm(b)
        if isinstance(b, Pt) and b.net is not None and a.net is not None and a.net != b.net:
            raise SceneError(f"wire would join {a.net} and {b.net}: {a} -> {b}")
        if a.x == bx or a.y == by: self._seg(a.x, a.y, bx, by)
        elif (mode or "hv") == "hv": self._seg(a.x, a.y, bx, a.y); self._seg(bx, a.y, bx, by)
        else: self._seg(a.x, a.y, a.x, by); self._seg(a.x, by, bx, by)
        d = b.d if isinstance(b, Pt) else None
        return Pt(bx, by, a.net or (b.net if isinstance(b, Pt) else None), d)

    def go(self, a, dx=0.0, dy=0.0, to_x=None, to_y=None):
        """Wire from a by (dx, dy) units, or to an absolute section coordinate; sideways first if both are given.
        Returns the end point, heading the way the wire was going."""
        x = a.x + dx * U if to_x is None else self.ox + to_x * U
        y = a.y + dy * U if to_y is None else self.oy + to_y * U
        x, y = snap(x), snap(y)
        if x != a.x: self._seg(a.x, a.y, x, a.y)
        if y != a.y: self._seg(x, a.y, x, y)
        d = ("D" if y > a.y else "U") if y != a.y else ("R" if x > a.x else "L") if x != a.x else a.d
        return Pt(x, y, a.net, d)

    def _mark(self, p, m): self.marks.setdefault(p.xy, []).append(m)

    def gnd(self, p, d=None):
        d = d or p.d or "D"
        if p.net != "GND": raise SceneError(f"ground symbol on {p.net} at {p}")
        self.sheet.gnd(p.x, p.y, {"L": 270, "R": 90, "U": 180, "D": 0}[d])
        self._mark(p, ("gnd",))
        dx, dy = DIRS[d]
        self.rects.append(("body", min(p.x, p.x + dx * 2.6) - 1.3 * abs(dy), min(p.y, p.y + dy * 2.6) - 1.3 * abs(dx),
                           max(p.x, p.x + dx * 2.6) + 1.3 * abs(dy), max(p.y, p.y + dy * 2.6) + 1.3 * abs(dx), "GND"))

    def pwr(self, p):
        """Rail symbol (arrow up) for a net that is a supply on every sheet."""
        if p.net not in self.rails: raise SceneError(f"{p.net} is not a global rail, at {p}")
        t = self.name(p.net)
        self.sheet.pwr(t, p.x, p.y)
        self._mark(p, ("pwr", t))
        self.rects.append(("body", p.x - 0.8, p.y - 2.54, p.x + 0.8, p.y, "PWR"))
        self.rects.append(("text", p.x - len(t) * CW / 2, p.y - 4.4, p.x + len(t) * CW / 2, p.y - 2.8, "rail " + t))

    def label(self, p, d=None):
        """Net name at a point. d: the way the text runs away from the point (default: the point's direction)."""
        d = d or p.d or "R"
        if p.net is None: raise SceneError(f"label on a point without a net: {p}")
        g = p.net in self.glob
        t = self.name(p.net)
        self.sheet.label(t, p.x, p.y, {"L": 180, "R": 0, "U": 90, "D": 270}[d], g)
        self._mark(p, ("label", t, g))
        n = len(t) * CW + (3.6 if g else 0.4)
        dx, dy = DIRS[d]
        if g:
            if dx: r = (min(p.x, p.x + dx * n), p.y - 1.2, max(p.x, p.x + dx * n), p.y + 1.2)
            else: r = (p.x - 1.2, min(p.y, p.y + dy * n), p.x + 1.2, max(p.y, p.y + dy * n))
        else:
            if dx: r = (min(p.x, p.x + dx * n), p.y - 2.0, max(p.x, p.x + dx * n), p.y - 0.25)
            else: r = (p.x - 2.0, min(p.y, p.y + dy * n), p.x - 0.25, max(p.y, p.y + dy * n))
        self.rects.append(("text", r[0], r[1], r[2], r[3], "label " + t))

    def nc(self, p):
        self.sheet.nc(p.x, p.y); self._mark(p, ("nc",))

    def ground(self, p, d=None, show=None):
        d = d or p.d or "D"
        sym = self.grounds[p.net]
        t = self.name(p.net)
        show = (not self.quiet) if show is None else show
        self.sheet.ground(sym, t, p.x, p.y, {"L": 270, "R": 90, "U": 180, "D": 0}[d], show)
        self._mark(p, ("pwr", t))
        dx, dy = DIRS[d]
        self.rects.append(("body", min(p.x, p.x + dx * 2.1) - 1.3 * abs(dy), min(p.y, p.y + dy * 2.1) - 1.3 * abs(dx),
                           max(p.x, p.x + dx * 2.1) + 1.3 * abs(dy), max(p.y, p.y + dy * 2.1) + 1.3 * abs(dx), t))
        if show:
            w = len(t) * CW
            if d == "D": r = (p.x - w / 2, p.y + 2.6, p.x + w / 2, p.y + 4.2)
            elif d == "U": r = (p.x - w / 2, p.y - 4.2, p.x + w / 2, p.y - 2.6)
            elif d == "R": r = (p.x + 2.8, p.y - 0.8, p.x + 2.8 + w, p.y + 0.8)
            else: r = (p.x - 2.8 - w, p.y - 0.8, p.x - 2.8, p.y + 0.8)
            self.rects.append(("text", r[0], r[1], r[2], r[3], "gnd name " + t))

    def end(self, p, d=None):
        """Finish a point the usual way for its net: ground symbol, rail arrow (when heading up), else a label."""
        d = d or p.d or "R"
        if p.net is None: return self.nc(p)
        if p.net in self.grounds: return self.ground(p, d)
        if p.net == "GND": return self.gnd(p, d)
        if p.net in self.rails and d == "U": return self.pwr(p)
        return self.label(p, d)

    def tie(self, pts, dx=1.0, end="D"):
        """Join several pins of one net that sit in a column with a bar dx units out, and end the net once below (or above)."""
        pts = sorted(pts, key=lambda p: p.y)
        outs = [self.go(p, dx=dx * DIRS[p.d][0]) for p in pts]
        self.wire(outs[0], outs[-1])
        if not end: return outs[0]
        tail = self.go(outs[-1] if end == "D" else outs[0], dy=1.0 if end == "D" else -1.0)
        self.end(tail)
        return tail

    def kelvin(self, a, b, ra, rb, cd, ca=None, cb=None, drop=1.0):
        """The filter of a current-sense resistor that lies between points a and b on a horizontal rail: a resistor down
        from each end, a capacitor across the two filtered nodes, optionally one from each to ground.
        Returns the two filtered nodes (left, right), ready for a label or a wire."""
        fa = self.go(self.two(ra, a, "D", gap=drop, text="L"), dy=1)
        fb = self.go(self.two(rb, b, "D", gap=drop, text="R"), dy=1)
        w = (fb.x - fa.x) / U
        far = self.two(cd, fa, "R", gap=(w - 3) / 2, text="T")
        self.wire(far, fb)
        if ca: self.shunt(ca, fa, "D", text="L")
        if cb: self.shunt(cb, fb, "D", text="R")
        return fa, fb

    # ---- finishing ---------------------------------------------------------------------------------------------
    def _on(self, w, x, y):
        """Is (x, y) on wire w? Returns 0 no, 1 at an end, 2 inside."""
        x1, y1, x2, y2 = w
        if (x, y) in ((x1, y1), (x2, y2)): return 1
        if x1 == x2 == x and min(y1, y2) < y < max(y1, y2): return 2
        if y1 == y2 == y and min(x1, x2) < x < max(x1, x2): return 2
        return 0

    def finish(self):
        # 1. merge collinear overlapping/abutting wires? Kept as drawn; drop exact duplicates
        self.wires = list(dict.fromkeys((w if (w[0], w[1]) <= (w[2], w[3]) else (w[2], w[3], w[0], w[1])) for w in self.wires))
        # 2. every part of the block must be on the sheet
        for r in self.refs:
            units = {p["unit"] for p in self.pins_of(r)} - {0} or {1}
            miss = units - self.placed.get(r, set())
            if miss: self.errors.append(f"{r} is not drawn (units {sorted(miss)})")
        # 3. finish untouched pins
        wire_pts = set()
        for w in self.wires: wire_pts.add((w[0], w[1])); wire_pts.add((w[2], w[3]))
        pin_at = {}
        for s in self.syms:
            for p, pt in s.all_pins(): pin_at.setdefault(pt.xy, []).append((s, p, pt))
        for xy, lst in pin_at.items():
            if xy in wire_pts or xy in self.marks: continue
            if any(self._on(w, *xy) for w in self.wires): continue
            if len({s.ref for s, _, _ in lst}) > 1: continue               # two parts pin to pin
            s, p, pt = lst[0]
            if all((s.ref, q["num"]) in self.ncset for _, q, _ in lst): self.nc(pt)
            elif pt.net == "GND" or pt.net in self.grounds or pt.net in self.glob or len(s.pins) < 3: self.end(pt)
            else:                                                     # a short stub keeps the name clear of the pin number
                dx, dy = DIRS[pt.d]
                e = Pt(pt.x + dx * U, pt.y + dy * U, pt.net, pt.d)
                self._seg(pt.x, pt.y, e.x, e.y); wire_pts.add(pt.xy); wire_pts.add(e.xy)
                self.end(e)
        # 4. connectivity of the drawing
        self._netcheck(pin_at)
        # 5. junction dots: wherever a point has wires (or a pin) leaving in three or more directions
        pts = set(wire_pts) | set(pin_at)
        for (x, y) in pts:
            dirs = set()
            for w in self.wires:
                k = self._on(w, x, y)
                if not k: continue
                if w[1] == w[3]:
                    if k == 2 or max(w[0], w[2]) > x: dirs.add("R")
                    if k == 2 or min(w[0], w[2]) < x: dirs.add("L")
                else:
                    if k == 2 or max(w[1], w[3]) > y: dirs.add("D")
                    if k == 2 or min(w[1], w[3]) < y: dirs.add("U")
            if len(dirs) + (1 if (x, y) in pin_at else 0) >= 3: self.sheet.junction(x, y)
        # 6. merge wires that lie end to end or on top of each other
        merged = []
        for horiz in (True, False):
            lines = {}
            for w in self.wires:
                if (w[1] == w[3]) == horiz:
                    k = w[1] if horiz else w[0]
                    lines.setdefault(k, []).append((min(w[0], w[2]), max(w[0], w[2])) if horiz else (min(w[1], w[3]), max(w[1], w[3])))
            for k, iv in lines.items():
                iv.sort()
                cur = list(iv[0])
                for a_, b_ in iv[1:]:
                    if a_ <= cur[1]: cur[1] = max(cur[1], b_)
                    else:
                        merged.append((cur[0], k, cur[1], k) if horiz else (k, cur[0], k, cur[1])); cur = [a_, b_]
                merged.append((cur[0], k, cur[1], k) if horiz else (k, cur[0], k, cur[1]))
        self.wires = merged
        for w in self.wires: self.sheet.wire(*w)
        self._lint()
        if self.errors:
            raise SceneError(f"sheet '{self.block}':\n  " + "\n  ".join(self.errors))

    def _netcheck(self, pin_at):
        parent = {}
        def find_(a):
            while parent.setdefault(a, a) != a:
                parent[a] = parent[parent[a]]; a = parent[a]
            return a
        def union(a, b): parent[find_(a)] = find_(b)
        nodes = set(pin_at) | set(self.marks)
        for w in self.wires: nodes.add((w[0], w[1])); nodes.add((w[2], w[3]))
        for w in self.wires:
            union((w[0], w[1]), (w[2], w[3]))
            for n in nodes:
                if self._on(w, *n) == 2: union(n, (w[0], w[1]))
        cl = {}
        for n in nodes: cl.setdefault(find_(n), []).append(n)
        u = lambda xy: f"({(xy[0] - self.ox) / U:g}u,{(xy[1] - self.oy) / U:g}u abs {xy[0]:g},{xy[1]:g}mm)"
        by_net = {}
        for root, pts in cl.items():
            pn = {}
            for xy in pts:
                for s, p, pt in pin_at.get(xy, []):
                    pn.setdefault(pt.net if (s.ref, p["num"]) not in self.ncset else None, []).append(f"{s.ref}.{p['num']}")
            names = set()
            for xy in pts:
                for m in self.marks.get(xy, []):
                    if m[0] == "label": names.add(m[1])
                    elif m[0] == "pwr": names.add(m[1])
                    elif m[0] == "gnd": names.add("GND")
            if len(pn) > 1:
                self.errors.append(f"short: {', '.join(f'{k}: {v[:4]}' for k, v in pn.items())} near {u(pts[0])}")
                continue
            if not pn:
                if names: self.errors.append(f"label {names} on wires with no pin, near {u(pts[0])}")
                elif len(pts) > 1: self.errors.append(f"wire with no pin near {u(pts[0])}")
                continue
            net = next(iter(pn))
            if net is None:
                if len(pts) > 1 and (names or any(xy not in pin_at for xy in pts)): self.errors.append(f"NC pins {pn[None]} are wired, near {u(pts[0])}")
                continue
            want = "GND" if net == "GND" else self.name(net)
            if names - {want}: self.errors.append(f"net {net} carries the name {names - {want}} near {u(pts[0])}")
            by_net.setdefault(net, []).append((bool(names), pts, pn[net]))
        for net, cls in by_net.items():
            need = len(cls) > 1 or net in self.glob or net == "GND"
            for named, pts, pins in cls:
                if need and not named:
                    self.errors.append(f"net {net}: the piece with {pins[:5]} near {u(pts[0])} has no label or rail symbol and is not wired to the rest")
        shown = {}
        for n in by_net:
            t = self.name(n)
            if t in shown: self.errors.append(f"nets {n} and {shown[t]} would both be shown as '{t}'")
            shown[t] = n

    def _lint(self):
        out = []
        R = self.rects
        def hit(a, b, m=0.05):
            return a[1] + m < b[3] and b[1] + m < a[3] and a[2] + m < b[4] and b[2] + m < a[4]
        for i, a in enumerate(R):
            if a[0] == "frame": continue
            for b in R[i + 1:]:
                if b[0] == "frame": continue
                if a[0] == "body" and b[0] == "body":
                    if a[5] != b[5] and hit(a, b, 0.3): out.append(f"symbols overlap: {a[5]} / {b[5]} at {a[1]:.1f},{a[2]:.1f}")
                elif hit(a, b):
                    if a[5] == b[5] and a[0] == b[0] == "text" and a[5].startswith("label"): continue
                    out.append(f"{a[0]} '{a[5]}' overlaps {b[0]} '{b[5]}' at {max(a[1], b[1]):.1f},{max(a[2], b[2]):.1f}")
        for w in self.wires:
            wr = ("wire", min(w[0], w[2]), min(w[1], w[3]), max(w[0], w[2]), max(w[1], w[3]), "wire")
            for b in R:
                if b[0] == "frame":
                    inside = b[1] < wr[1] and wr[3] < b[3] and b[2] < wr[2] and wr[4] < b[4]
                    outside = wr[3] < b[1] or wr[1] > b[3] or wr[4] < b[2] or wr[2] > b[4]
                    continue
                m = 0.3 if b[0] == "body" else 0.1
                if wr[1] < b[3] - m and b[1] + m < wr[3] and wr[2] < b[4] - m and b[2] + m < wr[4]:
                    out.append(f"wire {w} runs through {b[0]} '{b[5]}'")
        pw, ph = self.page
        for b in R:
            if b[0] == "frame": continue
            if b[1] < 10.5 or b[2] < 10.5 or b[3] > pw - 10.5 or b[4] > ph - 10.5: out.append(f"{b[0]} '{b[5]}' is off the page at {b[1]:.0f},{b[2]:.0f}")
            if b[3] > pw - 119 and b[4] > ph - 43: out.append(f"{b[0]} '{b[5]}' is on the title block")
        self.lint = out
