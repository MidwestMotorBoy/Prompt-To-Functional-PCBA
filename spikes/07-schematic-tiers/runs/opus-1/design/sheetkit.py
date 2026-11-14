"""Sheet kit: draw a block the way a person would, from a short layout script.

A layout script (layouts.py) places parts relative to each other and draws the wires it means; the kit does the rest:
  * every pin the script did not wire gets what it needs: a ground symbol, a rail symbol, a no-connect flag, or a net
    label pointing away from the part (local inside the sheet, global when the net leaves it);
  * junction dots are found from the drawing (three or more ends at a point, or an end on the middle of a wire);
  * fields are placed beside the body so they read left to right;
  * lint() reports overlapping text, text on wires, wires through bodies, and pins touched by a wire of another net.
Nothing here decides connectivity: make.sh exports KiCad's own netlist of the result and compares it with the code.
"""
import symlib
from sx import find, get, val

G = 1.27
CW = 1.05          # mm per character of 1.27 mm text (KiCad default font, with a little margin)


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


DIRV = {"L": (-1, 0), "R": (1, 0), "U": (0, -1), "D": (0, 1)}


class Pin:
    """A placed pin: connection point (x, y) and the direction pointing away from the body."""
    def __init__(self, ref, num, name, x, y, d, net):
        self.ref, self.num, self.name, self.x, self.y, self.d, self.net = ref, num, name, x, y, d, net
    @property
    def pt(self): return (self.x, self.y)
    def out(self, k=2.54):
        dx, dy = DIRV[self.d]
        return (snap(self.x + dx * k), snap(self.y + dy * k))
    def __repr__(self): return f"Pin({self.ref}.{self.num} {self.name} @{self.x},{self.y} {self.d} {self.net})"


def _body_box(lib, name, unit):
    """Bounding box of the drawn body (no pins), symbol coordinates y up: (x1, y1, x2, y2)."""
    s = symlib.flat(lib, name)
    xs, ys = [], []
    for u in find(s, "symbol"):
        un, st = (int(v) for v in val(u[1]).rsplit("_", 2)[-2:])
        if un not in (0, unit) or st > 1: continue
        for g in u[1:]:
            if not isinstance(g, list): continue
            if g[0] == "rectangle":
                for k in ("start", "end"):
                    f = [c for c in g if isinstance(c, list) and c[0] == k][0]
                    xs.append(float(f[1])); ys.append(float(f[2]))
            elif g[0] in ("polyline", "bezier"):
                pts = [c for c in g if isinstance(c, list) and c[0] == "pts"][0]
                for xy in pts[1:]:
                    xs.append(float(xy[1])); ys.append(float(xy[2]))
            elif g[0] == "circle":
                c = [c for c in g if isinstance(c, list) and c[0] == "center"][0]
                r = float([c for c in g if isinstance(c, list) and c[0] == "radius"][0][1])
                xs += [float(c[1]) - r, float(c[1]) + r]; ys += [float(c[2]) - r, float(c[2]) + r]
            elif g[0] == "arc":
                for k in ("start", "mid", "end"):
                    f = [c for c in g if isinstance(c, list) and c[0] == k]
                    if f: xs.append(float(f[0][1])); ys.append(float(f[0][2]))
    if not xs: return (-1, -1, 1, 1)
    return (min(xs), min(ys), max(xs), max(ys))


class Part:
    def __init__(self, kit, ref, x, y, angle, mirror, unit):
        self.kit, self.ref, self.x, self.y, self.angle, self.mirror, self.unit = kit, ref, x, y, angle, mirror, unit
        lib, name = kit.comps[ref]["lib"].split(":")
        self.lib, self.name = lib, name
        self.pins = []
        for p in kit.pins_of(ref):
            if p["unit"] not in (0, unit): continue
            dx, dy = rot(p["x"], p["y"], angle)
            if mirror: dx = -dx                   # KiCad rotates first, then mirrors
            # direction into the body is the pin angle; away from it is the opposite
            a = (p["angle"] + 180 + angle) % 360
            if mirror: a = (180 - a) % 360
            d = {0: "R", 90: "U", 180: "L", 270: "D"}[a]
            net = kit.pinnet.get((ref, p["num"]))
            if (ref, p["num"]) in kit.ncset: net = None
            self.pins.append(Pin(ref, p["num"], p["name"], snap(x + dx), snap(y + dy), d, net))
        bx1, by1, bx2, by2 = _body_box(lib, name, unit)
        c = [rot(bx1, by1, angle), rot(bx2, by2, angle)]
        if mirror: c = [(-c[0][0], c[0][1]), (-c[1][0], c[1][1])]
        self.box = (x + min(c[0][0], c[1][0]), y + min(c[0][1], c[1][1]), x + max(c[0][0], c[1][0]), y + max(c[0][1], c[1][1]))

    def p(self, key):
        """Pin by number or name (first visible one of that name)."""
        key = str(key)
        m = [p for p in self.pins if p.num == key] or [p for p in self.pins if p.name == key]
        if not m: raise KeyError(f"{self.ref} has no pin {key} in unit {self.unit}: {[p.name for p in self.pins]}")
        return m[0]
    __getitem__ = p

    def net_pin(self, net):
        return [p for p in self.pins if p.net == net][0]


class Shifted:
    """The sheet as the layout sees it: everything drawn is moved by (ox, oy), so a layout can start at 0, 0."""
    def __init__(self, sheet): self.s, self.ox, self.oy = sheet, 0.0, 0.0
    def __getattr__(self, k): return getattr(self.s, k)
    def __setattr__(self, k, v):
        if k in ("s", "ox", "oy"): object.__setattr__(self, k, v)
        else: setattr(self.s, k, v)
    def _p(self, x, y): return x + self.ox, y + self.oy
    def symbol(self, lib, name, ref, value, x, y, angle=0, ref_at=None, val_at=None, **kw):
        x, y = self._p(x, y)
        if ref_at: ref_at = self._p(*ref_at)
        if val_at: val_at = self._p(*val_at)
        return self.s.symbol(lib, name, ref, value, x, y, angle, ref_at=ref_at, val_at=val_at, **kw)
    def wire(self, x1, y1, x2, y2): self.s.wire(*self._p(x1, y1), *self._p(x2, y2))
    def junction(self, x, y): self.s.junction(*self._p(x, y))
    def label(self, text, x, y, angle, glob): self.s.label(text, *self._p(x, y), angle, glob)
    def nc(self, x, y): self.s.nc(*self._p(x, y))
    def text(self, s, x, y, size=1.27, bold=False): self.s.text(s, *self._p(x, y), size, bold=bold)


class Kit:
    def __init__(self, sheet, block, comps, nets, nc, cons, pins_of):
        sheet = Shifted(sheet)
        self.sheet, self.block, self.comps, self.cons = sheet, block, comps, cons
        self.pins_of = pins_of
        self.refs = [r for r in comps if comps[r]["block"] == block]
        refset = set(self.refs)
        self.nets = nets
        self.pinnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
        self.ncset = {(r, p) for r, p in nc}
        self.glob = {n for n, nodes in nets.items() if any(r not in refset for r, _ in nodes) and any(r in refset for r, _ in nodes)}
        self.parts = {}
        self.wires = []          # ((x1,y1),(x2,y2)) after snapping
        self.anchors = {}        # point -> count of label / power / nc anchors placed there
        self.alias = {}          # net -> display name of its local label
        self.rails = set()       # nets drawn with a rail (power) symbol instead of a label
        self.grounds = {}        # net -> ground-style symbol (e.g. GNDREF) drawn with its name, instead of a label
        self.texts = []          # (x1, y1, x2, y2, what) boxes of text for lint
        self.npwr = 0
        self.notes = []

    # ---------------- names ----------------
    def short(self, n):
        if n in self.alias: return self.alias[n]
        if n in self.glob: return n.lstrip("/")
        s = n.split("/")[-1]
        if s.startswith("Net-("):                      # Net-(U101-VC4) -> U101_VC4
            s = s[5:-1].replace("-Pad", ".").replace("-", ".")
        return s

    def net(self, ref, pin):
        return self.pinnet.get((ref, str(pin)))

    # ---------------- parts ----------------
    def place(self, ref, x, y, angle=0, mirror=False, unit=1, fields="auto", hide_val=False, hide_ref=False):
        """Place a part with its origin at (x, y). fields: auto | right | left | above | below | top | (rx, ry, vx, vy)."""
        x, y = snap(x), snap(y)
        key = (ref, unit)
        if key in self.parts: raise ValueError(f"{ref} unit {unit} placed twice")
        pt = Part(self, ref, x, y, angle, mirror, unit)
        self.parts[key] = pt
        c = self.comps[ref]
        val_ = c["value"]
        x1, y1, x2, y2 = pt.box
        lr, lv = len(ref) * CW, len(val_) * CW
        if fields == "auto":
            n = len({p.num for p in pt.pins})
            fields = "right" if n <= 3 and (y2 - y1) > (x2 - x1) else ("above" if n <= 3 else "top")
        if fields == "right":
            ym = (y1 + y2) / 2
            f = (x2 + 1.0, ym - 0.7, x2 + 1.0, ym + 1.6)
        elif fields == "left":
            ym = (y1 + y2) / 2
            f = (x1 - 1.0 - lr, ym - 0.7, x1 - 1.0 - lv, ym + 1.6)
        elif fields == "above":
            xm = (x1 + x2) / 2
            f = (xm - lr / 2, y1 - 3.3, xm - lv / 2, y1 - 1.0)
        elif fields == "line":                    # "R105 100" on one line over a part lying flat
            xm = (x1 + x2) / 2
            f = (xm - (lr + lv + 2 * CW) / 2, y1 - 1.0, xm - (lr + lv + 2 * CW) / 2 + lr + 2 * CW, y1 - 1.0)
        elif fields == "linebelow":
            xm = (x1 + x2) / 2
            f = (xm - (lr + lv + 2 * CW) / 2, y2 + 2.2, xm - (lr + lv + 2 * CW) / 2 + lr + 2 * CW, y2 + 2.2)
        elif fields == "below":
            xm = (x1 + x2) / 2
            f = (xm - lr / 2, y2 + 2.2, xm - lv / 2, y2 + 4.5)
        elif fields == "top":                     # IC: reference and value over the top left corner
            top = min([y1] + [p.y for p in pt.pins if p.d == "U"])
            extra = 0 if top == y1 else 0
            f = (x1, top - 3.3 - extra, x1, top - 1.0 - extra)
            if any(p.d == "U" for p in pt.pins):
                f = (x2 + 1.0, y1 - 3.3, x2 + 1.0, y1 - 1.0)
        else:
            f = fields
        rx, ry, vx, vy = f
        self.sheet.symbol(self.lib_of(ref), self.name_of(ref), ref, val_, x, y, angle, unit=unit,
                          footprint=c["footprint"], fields=c["fields"], ref_at=(rx, ry), val_at=(vx, vy), mirror=mirror,
                          hide_val=hide_val, hide_ref=hide_ref, raw_fields=True)
        if not hide_ref: self.texts.append((rx, ry - 1.0, rx + lr, ry + 0.3, f"{ref} ref"))
        if not hide_val: self.texts.append((vx, vy - 1.0, vx + lv, vy + 0.3, f"{ref} value"))
        return pt

    def lib_of(self, ref): return self.comps[ref]["lib"].split(":")[0]
    def name_of(self, ref): return self.comps[ref]["lib"].split(":")[1]

    def two(self, ref, x, y, first=None, horiz=False, fields=None):
        """A two-pad part. Vertical: the pad on net `first` on top. Horizontal: `first` on the left.
        Returns the part; .a is the top/left pin, .b the bottom/right pin."""
        pins = self.pins_of(ref)
        pp = {}
        for p in pins: pp.setdefault(p["num"], p)
        nums = sorted(pp)
        if first is None: first = self.pinnet.get((ref, nums[0]))
        e = [self.pinnet.get((ref, n)) for n in nums]
        if first not in e: raise ValueError(f"{ref} is not on {first}: {e}")
        f = nums[e.index(first)]; o = [n for n in nums if n != f][0]
        for a in (0, 90, 180, 270):
            fx, fy = rot(pp[f]["x"], pp[f]["y"], a); ox, oy = rot(pp[o]["x"], pp[o]["y"], a)
            if not horiz and abs(fx) < .01 and abs(ox) < .01 and fy < oy: break
            if horiz and abs(fy) < .01 and abs(oy) < .01 and fx < ox: break
        pt = self.place(ref, x, y, a, fields=fields or ("above" if horiz else "right"))
        pt.a = [p for p in pt.pins if p.num == f][0]
        pt.b = [p for p in pt.pins if p.num == o][0]
        return pt

    # ---------------- drawing ----------------
    def w(self, *pts):
        """Polyline through points (tuples or Pins)."""
        ps = [(snap(p.x), snap(p.y)) if isinstance(p, Pin) else (snap(p[0]), snap(p[1])) for p in pts]
        for a, b in zip(ps, ps[1:]):
            if a == b: continue
            if a[0] != b[0] and a[1] != b[1]: raise ValueError(f"diagonal wire {a} {b}")
            self.wires.append((a, b))

    def hv(self, a, b):
        """Wire from a to b, horizontal first."""
        a = a.pt if isinstance(a, Pin) else a; b = b.pt if isinstance(b, Pin) else b
        self.w(a, (b[0], a[1]), b)

    def vh(self, a, b):
        a = a.pt if isinstance(a, Pin) else a; b = b.pt if isinstance(b, Pin) else b
        self.w(a, (a[0], b[1]), b)

    def _mark(self, pt):
        pt = (snap(pt[0]), snap(pt[1]))
        self.anchors[pt] = self.anchors.get(pt, 0) + 1

    def gnd(self, at, d="D", net="GND"):
        """Ground symbol at a point (tuple or Pin). A sideways pin gets a short stub and the symbol under its end."""
        if net != "GND":
            return self.gref(at, net)
        if isinstance(at, Pin):
            if at.d in ("L", "R"):
                e = at.out(2.54); self.w(at, e); at = e
            elif at.d == "U":
                return self._sym_gnd(at.pt, 180)
            else: at = at.pt
        self._sym_gnd(at, {"D": 0, "U": 180, "L": 270, "R": 90}[d])

    def _sym_gnd(self, pt, angle):
        self.npwr += 1
        x, y = snap(pt[0]), snap(pt[1])
        self.sheet.symbol("power", "GND", f"#PWR{abs(hash(self.sheet.name)) % 90 + 10}{self.npwr:03d}", "GND", x, y, angle,
                          hide_ref=True, hide_val=True, key=f"pwr{self.npwr}")
        self._mark((x, y))

    def gref(self, at, net, side="below"):
        """A ground-style symbol carrying a name (a second ground such as the gauge's Kelvin ground)."""
        if isinstance(at, Pin):
            if at.d in ("L", "R"):
                e = at.out(2.54); self.w(at, e); at = e
            elif at.d == "U":
                e = at.out(1.27); self.w(at, e); at = e
            else: at = at.pt
        self.npwr += 1
        x, y = snap(at[0]), snap(at[1])
        name = self.short(net)
        tl = len(name) * CW
        vat = (x - tl / 2, y + 4.4) if side == "below" else (x + 1.8, y + 2.2)
        self.sheet.symbol("power", self.grounds[net], f"#PWR{abs(hash(self.sheet.name)) % 90 + 10}{self.npwr:03d}", name, x, y, 0,
                          hide_ref=True, val_at=vat, key=f"pwr{self.npwr}", raw_fields=True)
        self.texts.append((vat[0], vat[1] - 1.0, vat[0] + tl, vat[1] + 0.3, f"gref {name}"))
        self._mark((x, y))

    def rail(self, at, net, d=None):
        """Supply symbol (arrow up) carrying the net name, for a rail shared across sheets."""
        if isinstance(at, Pin):
            if at.d in ("L", "R"):
                e = at.out(2.54); self.w(at, e); at = e; d = d or "U"
            else:
                d = d or at.d; at = at.pt
        d = d or "U"
        self.npwr += 1
        x, y = snap(at[0]), snap(at[1])
        angle = {"U": 0, "D": 180, "L": 90, "R": 270}[d]
        name = self.short(net)
        tl = len(name) * CW
        if d == "U": vat = (x - tl / 2, y - 3.6)
        elif d == "D": vat = (x - tl / 2, y + 4.6)
        elif d == "L": vat = (x - 3.6 - tl, y + 0.5)
        else: vat = (x + 3.6, y + 0.5)
        self.sheet.symbol("power", "VCC", f"#PWR{abs(hash(self.sheet.name)) % 90 + 10}{self.npwr:03d}", name, x, y, angle,
                          hide_ref=True, val_at=vat, key=f"pwr{self.npwr}", raw_fields=True, flat_text=True)
        self.texts.append((vat[0], vat[1] - 1.0, vat[0] + tl, vat[1] + 0.3, f"rail {name}"))
        self._mark((x, y))

    def label(self, at, net, d=None, stub=0):
        """Net label at a point or pin, text running in direction d (default: away from the pin)."""
        if isinstance(at, Pin):
            d = d or at.d
            if stub:
                e = at.out(stub); self.w(at, e); at = e
            else: at = at.pt
        d = d or "R"
        x, y = snap(at[0]), snap(at[1])
        if net in self.rails:
            return self.rail((x, y), net, "U" if d in ("L", "R", "U") else "D")
        if net in self.grounds:
            return self.gref((x, y), net)
        glob = net in self.glob
        ang = {"R": 0, "U": 90, "L": 180, "D": 270}[d]
        self.sheet.label(self.short(net), x, y, ang, glob)
        tl = len(self.short(net)) * CW + (3.0 if glob else 0.5)
        if d == "R": b = (x, y - 1.6, x + tl, y + (0.8 if glob else 0))
        elif d == "L": b = (x - tl, y - 1.6, x, y + (0.8 if glob else 0))
        elif d == "U": b = (x - 1.6, y - tl, x + (0.8 if glob else 0), y)
        else: b = (x - 1.6, y, x + (0.8 if glob else 0), y + tl)
        self.texts.append(b + (f"label {self.short(net)}",))
        self._mark((x, y))

    def nc(self, at):
        at = at.pt if isinstance(at, Pin) else at
        self.sheet.nc(at[0], at[1]); self._mark(at)

    def text(self, s, x, y, size=1.27, bold=False):
        self.sheet.text(s, x, y, size, bold=bold)
        lines = s.split("\n")
        self.texts.append((x, y - size * 1.1, x + max(len(l) for l in lines) * size * 0.85, y + (len(lines) - 1) * size * 1.6 + 0.3, "text " + lines[0][:20]))

    def title(self, s, x, y):
        self.text(s, x, y, 2.0, bold=True)

    def note(self, s, x, y, width=80, size=1.27):
        """Wrapped note text from (x, y) down. Returns the y below it."""
        words, lines, cur = s.split(), [], ""
        for wd in words:
            if len(cur) + len(wd) + 1 > width and cur: lines.append(cur); cur = wd
            else: cur = (cur + " " + wd).strip()
        if cur: lines.append(cur)
        for i, l in enumerate(lines):
            self.sheet.text(l, x, y + i * size * 1.7, size)
        self.texts.append((x, y - size, x + width * size * 0.82, y + (len(lines) - 1) * size * 1.7 + 0.3, "note"))
        return y + len(lines) * size * 1.7

    # ---------------- finishing ----------------
    def wired_points(self):
        pts = {}
        for a, b in self.wires:
            for p in (a, b): pts[p] = pts.get(p, 0) + 1
        return pts

    def on_wire_interior(self, p):
        for a, b in self.wires:
            if a[0] == b[0] == p[0] and min(a[1], b[1]) < p[1] < max(a[1], b[1]): return True
            if a[1] == b[1] == p[1] and min(a[0], b[0]) < p[0] < max(a[0], b[0]): return True
        return False

    def finish(self, auto=True):
        """Labels for every pin left open, then junction dots."""
        ends = self.wired_points()
        pinpts = {}
        for pt in self.parts.values():
            for p in pt.pins: pinpts.setdefault(p.pt, []).append(p)
        done = set()
        if auto:
            for pt in self.parts.values():
                for p in pt.pins:
                    if p.pt in done: continue
                    touched = p.pt in ends or p.pt in self.anchors or len({q.ref for q in pinpts[p.pt]}) > 1 or self.on_wire_interior(p.pt)
                    if touched: continue
                    done.add(p.pt)
                    if p.net is None: self.nc(p)
                    elif p.net == "GND": self.gnd(p)
                    elif p.net in self.grounds: self.gref(p, p.net)
                    elif p.net in self.rails: self.rail(p, p.net)
                    else: self.label(p, p.net)
        self._split()
        for a, b in self.wires: self.sheet.wire(a[0], a[1], b[0], b[1])
        ends = self.wired_points()
        for p, k in ends.items():
            n = k + len({q.ref for q in pinpts.get(p, [])})
            if n >= 3: self.sheet.junction(*p)

    def _split(self):
        """Break every wire at the points where another wire ends or a pin sits, so a T is a real connection."""
        pts = set(self.wired_points()) | set(self.anchors)
        for pt in self.parts.values():
            for p in pt.pins: pts.add(p.pt)
        out = []
        self.joined = [p for pt in self.parts.values() for p in pt.pins if self.on_wire_interior(p.pt)]
        for a, b in dict.fromkeys(self.wires):
            if a[0] == b[0]:
                cut = sorted({a[1], b[1]} | {p[1] for p in pts if p[0] == a[0] and min(a[1], b[1]) < p[1] < max(a[1], b[1])})
                out += [((a[0], y1), (a[0], y2)) for y1, y2 in zip(cut, cut[1:])]
            else:
                cut = sorted({a[0], b[0]} | {p[0] for p in pts if p[1] == a[1] and min(a[0], b[0]) < p[0] < max(a[0], b[0])})
                out += [((x1, a[1]), (x2, a[1])) for x1, x2 in zip(cut, cut[1:])]
        self.wires = list(dict.fromkeys(out))

    def extent(self):
        xs, ys = [0], [0]
        for a, b in self.wires: xs += [a[0], b[0]]; ys += [a[1], b[1]]
        for pt in self.parts.values(): xs += [pt.box[0], pt.box[2]]; ys += [pt.box[1], pt.box[3]]
        for t in self.texts: xs.append(t[2]); ys.append(t[3])
        return max(xs) + self.sheet.ox, max(ys) + self.sheet.oy

    # ---------------- lint ----------------
    def lint(self):
        """Overlaps a reader would trip on. Returns a list of strings."""
        out = []
        bodies = [(pt.box, f"{pt.ref}") for pt in self.parts.values()]
        T = self.texts
        def ov(a, b, m=0.0):
            return a[0] < b[2] - m and b[0] < a[2] - m and a[1] < b[3] - m and b[1] < a[3] - m
        for i in range(len(T)):
            for j in range(i + 1, len(T)):
                if ov(T[i], T[j], 0.15): out.append(f"text overlap: {T[i][4]} / {T[j][4]} at {T[i][0]:.1f},{T[i][1]:.1f}")
            for bx, nm in bodies:
                if ov(T[i], bx, 0.3) and not T[i][4].startswith(nm + " "): out.append(f"text on body: {T[i][4]} / {nm}")
        for a, b in self.wires:
            wb = (min(a[0], b[0]) - 0.01, min(a[1], b[1]) - 0.01, max(a[0], b[0]) + 0.01, max(a[1], b[1]) + 0.01)
            for bx, nm in bodies:
                if ov(wb, bx, 0.2): out.append(f"wire through body: {nm} {a}-{b}")
            for t in T:
                if t[4].startswith("label") or t[4].startswith("rail"): continue
                if ov(wb, t, 0.25): out.append(f"wire through text: {t[4]} {a}-{b}")
        # a wire end or a pin landing on a wire of another net is a short: check pins against wires
        for p in getattr(self, "joined", []):
            out.append(f"pin on the middle of a wire (joined to it): {p}")
        return out
