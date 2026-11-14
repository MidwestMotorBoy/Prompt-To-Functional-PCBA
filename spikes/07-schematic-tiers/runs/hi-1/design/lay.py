"""Layout engine: draw a schematic sheet as a person would, from explicit placements.

A layout function (see layouts.py) places parts and draws wires through the small API of `Sch`:

    u = s.ic("U204", x, y)                 # an IC at an origin; u.p("VIN") is the pin's (x, y) on the sheet
    c = s.two("C206", x, y, "v", a="PACK_P")   # a two-pin part with pad A (the net given) at (x, y), standing or lying
    s.w(p1, p2, p3)                         # a wire through points
    s.label(x, y, "R", "3V3_SLEEP")          # label at a wire end, text running right
    s.gnd(x, y); s.rail(x, y, "PACK_P")      # ground and supply symbols

The engine never decides connectivity: KiCad's own netlist of the result is compared with the code's (make.sh).
What it does do is the housekeeping a hand drawing needs: junctions where three wires meet, the page size chosen
from the drawing and the drawing centred on it, and a lint that reports wires through symbols, wires through
text, overlapping text, and wires that touch a pin they should not.
"""
import math, uuid
import symlib

NS = uuid.UUID("6f1c2b1e-58a5-4c6e-9a59-0d5a1f2b7c11")
G = 1.27
VERSION = "20260306"
CHW = 1.0            # mm per character of 1.27 mm text (estimate used for boxes)
PAPERS = [("A4", 297, 210), ("A3", 420, 297), ("A2", 594, 420), ("A1", 841, 594)]

def uid(*key):
    return str(uuid.uuid5(NS, "|".join(str(k) for k in key)))

def snap(v):
    return round(round(v / G) * G, 4)

def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

def dump(node):
    if isinstance(node, tuple): return q(node[1])
    if isinstance(node, str): return node
    return "(" + " ".join(dump(c) for c in node) + ")"

def rot(x, y, a):
    """Symbol coordinates (y up) rotated a degrees, returned as a screen offset (y down)."""
    a = a % 360
    if a == 0: xr, yr = x, y
    elif a == 90: xr, yr = -y, x
    elif a == 180: xr, yr = -x, -y
    else: xr, yr = y, -x
    return xr, -yr

DIRV = {"R": (1, 0), "L": (-1, 0), "U": (0, -1), "D": (0, 1)}
OPP = {"R": "L", "L": "R", "U": "D", "D": "U"}


class Part:
    """A placed symbol: pin positions on the sheet (by pad number and by name) and the way each pin leaves the body."""
    def __init__(self, ref, x, y, angle, pins, unit, mirror=False):
        self.ref, self.x, self.y, self.angle, self.unit = ref, x, y, angle, unit
        self.pad, self.byname, self.out = {}, {}, {}
        for p in pins:
            dx, dy = rot(p["x"], p["y"], angle)
            if mirror: dx = -dx
            pt = (round(x + dx, 4), round(y + dy, 4))
            ov = {0: (-1, 0), 180: (1, 0), 90: (0, -1), 270: (0, 1)}[p["angle"]]      # outward, symbol coordinates (y up)
            sx_, sy_ = rot(ov[0], ov[1], angle)
            if mirror: sx_ = -sx_
            od = {(1, 0): "R", (-1, 0): "L", (0, 1): "D", (0, -1): "U"}[(round(sx_), round(sy_))]
            self.pad[p["num"]] = pt
            self.out[p["num"]] = od
            self.byname.setdefault(p["name"], p["num"])
    def p(self, key):
        key = str(key)
        if key in self.pad: return self.pad[key]
        return self.pad[self.byname[key]]
    def d(self, key):
        key = str(key)
        if key not in self.pad: key = self.byname[key]
        return self.out[key]


class Sch:
    def __init__(self, name, project, root_uuid, title, comps, nets, nc, glob, rename=None):
        self.name, self.project, self.root_uuid, self.title = name, project, root_uuid, title
        self.uuid = uid("sheet", name)
        self.comps, self.nets, self.glob = comps, nets, glob
        self.pinnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
        self.ncset = {(r, p) for r, p in nc}
        self.rename = rename or {}
        self.libs = {}
        self.warn = []
        self.m = None
        self.reset(0, 0)

    # ---------- bookkeeping ----------
    def reset(self, ox, oy):
        self.ox, self.oy = ox, oy
        self.items, self.npwr = [], 0
        self.wires = []          # (x1,y1,x2,y2) layout coordinates
        self.pinpts = []         # (x,y,ref,pad)
        self.bodies = []         # (x0,y0,x1,y1,ref)
        self.texts = []          # (x0,y0,x1,y1,what)
        self.marks = []          # things that name the net at a point (labels, ground, supply symbols): (x, y, net)
        self.shown = {}
        self.notes = []
        self.ext = [1e9, 1e9, -1e9, -1e9]

    def _e(self, x0, y0, x1=None, y1=None):
        x1 = x0 if x1 is None else x1; y1 = y0 if y1 is None else y1
        e = self.ext
        e[0], e[1], e[2], e[3] = min(e[0], x0, x1), min(e[1], y0, y1), max(e[2], x0, x1), max(e[3], y0, y1)

    def X(self, v): return round(v + self.ox, 4)
    def Y(self, v): return round(v + self.oy, 4)

    def lib(self, lib, name):
        key = f"{lib}:{name}"
        if key not in self.libs:
            s = symlib.flat(lib, name)
            s[1] = ("s", key)
            self.libs[key] = dump(s)
        return key

    def netof(self, ref, pad):
        return self.pinnet.get((ref, str(pad)))

    def disp(self, n):
        """The text a label shows for net n."""
        if n in self.rename: return self.rename[n]
        if n in self.glob: return n.lstrip("/")
        return n.split("/")[-1]

    # ---------- text ----------
    def text_box(self, s, x, y, just="center", size=1.27, what=None, dy=0):
        w = len(s) * CHW * size / 1.27 + 0.6
        h = size * 1.1
        if just == "left": x0 = x
        elif just == "right": x0 = x - w
        else: x0 = x - w / 2
        self.texts.append((x0, y - h / 2 + dy, x0 + w, y + h / 2 + dy, what or s))
        self._e(x0, y - h / 2, x0 + w, y + h / 2)

    def text(self, s, x, y, size=1.27, bold=False, just="left"):
        """Free text, y is its vertical centre."""
        self.text_box(s, x, y, just, size, what="text:" + s[:20])
        self.items.append(f'(text {q(s)} (exclude_from_sim no) (at {self.X(x)} {self.Y(y + size * 0.5)} 0) '
                          f'(effects (font (size {size} {size}){" bold" if bold else ""}) (justify {just} bottom)) '
                          f'(uuid {q(uid(self.name, "t", s, x, y))}))')

    def note(self, lines, x, y, size=1.27):
        """A short note, one line per string, top-left at (x, y)."""
        for i, ln in enumerate(lines):
            self.text(ln, x, y + i * size * 1.75, size)

    def heading(self, s, x, y):
        """Section title in larger text."""
        self.text(s, x, y, 2.0, just="left")

    def header(self, title, sub=None):
        """Sheet header at the top left of the drawing. Pass 1 only measures the drawing without it."""
        if self.m is None: return
        x0, y0 = self.m[0], self.m[1]
        self.text(title, x0, y0 - 9.5, 3.0, bold=True)
        if sub: self.text(sub, x0, y0 - 4.8, 1.27)

    # ---------- symbols ----------
    def _symbol(self, lib, name, ref, value, x, y, angle, unit, footprint, fields, ref_at, val_at, hide_ref=False, hide_val=False,
                key=None, mirror=False):
        lid = self.lib(lib, name)
        pins = [p for p in symlib.pins(lib, name) if p["unit"] in (0, unit)]
        part = Part(ref, x, y, angle, pins, unit, mirror)
        fa = 90 if angle in (90, 270) else 0
        flip = angle in (90, 180)

        def prop(label, v, at, hide):
            if at is None: at = (x, y, "center")
            ax, ay, j = at
            if j == "left" and flip: j = "right"
            elif j == "right" and flip: j = "left"
            jj = "" if j == "center" else f" (justify {j})"
            return (f'(property {q(label)} {q(v)} (at {self.X(ax):.2f} {self.Y(ay):.2f} {fa}) '
                    f'(effects (font (size 1.27 1.27)){jj}{" (hide yes)" if hide else ""}))')
        props = [prop("Reference", ref, ref_at, hide_ref or ref_at is None), prop("Value", value, val_at, hide_val or val_at is None),
                 f'(property "Footprint" {q(footprint)} (at {self.X(x)} {self.Y(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))']
        for k, v in (fields or {}).items():
            props.append(f'(property {q(k)} {q(v)} (at {self.X(x)} {self.Y(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        pn = " ".join(f'(pin {q(p)} (uuid {q(uid(self.name, ref, unit, "pin", p))}))'
                      for p in sorted({p["drawn"] for p in pins}))
        su = uid(self.name, "sym", key or ref, unit)
        self.items.append(
            f'(symbol (lib_id {q(lid)}) (at {self.X(x)} {self.Y(y)} {angle}){' (mirror y)' if mirror else ''} (unit {unit}) (exclude_from_sim no) (in_bom yes) (on_board yes) '
            f'(dnp no) (uuid {q(su)}) {" ".join(props)} {pn} '
            f'(instances (project {q(self.project)} (path {q("/" + self.root_uuid + "/" + self.uuid)} (reference {q(ref)}) (unit {unit})))))')
        for pad, pt in part.pad.items():
            self.pinpts.append((pt[0], pt[1], ref, pad))
        for pt in set(part.pad.values()): self._e(*pt)
        # body box: hull of the pin base points (the pin end moved in by the pin length)
        if pins:
            bx = []
            for p in pins:
                L = p["length"]
                ix = {0: L, 180: -L, 90: 0, 270: 0}[p["angle"]]; iy = {90: L, 270: -L, 0: 0, 180: 0}[p["angle"]]
                dx, dy = rot(p["x"] + ix, p["y"] + iy, angle)
                if mirror: dx = -dx
                bx.append((x + dx, y + dy))
            self.bodies.append((min(b[0] for b in bx), min(b[1] for b in bx), max(b[0] for b in bx), max(b[1] for b in bx), ref))
        return part

    def _c(self, ref):
        c = self.comps[ref]
        return c["lib"].split(":") + [c["value"], c["footprint"], c["fields"]]

    def ic(self, ref, x, y, unit=1, angle=0, ref_at=None, val_at=None, hide=False, mirror=False):
        """Place a many-pin part with its origin at (x, y). Fields default to above the body, left aligned."""
        lib, name, value, fp, fields = self._c(ref)
        x, y = snap(x), snap(y)
        pins = [p for p in symlib.pins(lib, name) if p["unit"] in (0, unit)]
        ys = [rot(p["x"], p["y"], angle) for p in pins]
        top = min(p[1] for p in ys); left = min(p[0] for p in ys)
        ra = ref_at or (x + left + 1.27, y + top - 5.0, "left")
        va = val_at or (x + left + 1.27, y + top - 3.2, "left")
        hr, hv = hide is True, hide in (True, "val")
        if not hr: self.text_box(ref, ra[0], ra[1], ra[2], what="ref " + ref)
        if not hv: self.text_box(value, va[0], va[1], va[2], what="val " + ref)
        return self._symbol(lib, name, ref, value, x, y, angle, unit, fp, fields, ra, va, hide_ref=hr, hide_val=hv, mirror=mirror,
                            key=ref)

    def two(self, ref, x, y, o="v", a=None, text="R", hide=False):
        """Place a two-pad part with pad A at (x, y), the other pad 7.62 mm away: down for o='v', right for o='h'.
        a: net on pad A (default pad 1). text: 'R'/'L' beside a standing part, 'U'/'D' for a lying one.
        Returns the Part with .a, .b (its end points) and .ca (centre)."""
        lib, name, value, fp, fields = self._c(ref)
        pins = symlib.pins(lib, name)
        pp = {}
        for p in pins: pp.setdefault(p["num"], p)
        nums = sorted(pp)
        if len(nums) == 1:
            raise ValueError("use one() for single-pad parts")
        pa = nums[0]
        if a is not None:
            e0, e1 = self.netof(ref, nums[0]), self.netof(ref, nums[1])
            if e0 != a and e1 == a: pa = nums[1]
            elif e0 != a and e1 != a: self.warn.append(f"{ref}: neither pad is on {a} ({e0}, {e1})")
        pb = nums[1] if pa == nums[0] else nums[0]
        x, y = snap(x), snap(y)
        for ang in (0, 90, 180, 270):
            ax_, ay_ = rot(pp[pa]["x"], pp[pa]["y"], ang); bx_, by_ = rot(pp[pb]["x"], pp[pb]["y"], ang)
            if o == "v" and abs(ax_) < .01 and abs(bx_) < .01 and ay_ < by_: break
            if o == "h" and abs(ay_) < .01 and abs(by_) < .01 and ax_ < bx_: break
        else:
            raise ValueError(f"{ref}: cannot orient")
        ox_, oy_ = x - ax_, y - ay_
        L = abs(by_ - ay_) + abs(bx_ - ax_)
        cx, cy = (x + (L / 2 if o == "h" else 0), y + (L / 2 if o == "v" else 0))
        if o == "v":
            sgn = 1 if text == "R" else -1
            tx = cx + sgn * 2.8
            j = "left" if sgn > 0 else "right"
            ra, va = (tx, cy - 1.0, j), (tx, cy + 1.0, j)
            self.text_box(ref, *ra, what="ref " + ref); self.text_box(value, *va, what="val " + ref)
            rt = max(len(ref), len(value)) * CHW
            self._e(tx + sgn * rt, cy)
        else:
            if text == "U": ra, va = (cx, cy - 4.4, "center"), (cx, cy - 2.9, "center")
            elif text == "W": ra, va = (cx, cy - 4.8, "center"), (cx, cy + 4.8, "center")
            elif text == "S": ra, va = (cx, cy - 2.9, "center"), (cx, cy + 2.9, "center")
            else: ra, va = (cx, cy + 2.9, "center"), (cx, cy + 4.4, "center")
            self.text_box(ref, *ra, what="ref " + ref); self.text_box(value, *va, what="val " + ref)
        part = self._symbol(lib, name, ref, value, ox_, oy_, ang, 1, fp, fields, ra, va)
        part.a, part.b, part.ca = part.pad[pa], part.pad[pb], (cx, cy)
        part.na, part.nb = self.netof(ref, pa), self.netof(ref, pb)
        part.pa, part.pb = pa, pb
        # body box: narrower than IC logic: between the pad ends, inset by the pin length
        self.bodies.pop()
        if o == "v": self.bodies.append((x - 1.6, y + 1.27, x + 1.6, y + L - 1.27, ref))
        else: self.bodies.append((x + 1.27, y - 1.6, x + L - 1.27, y + 1.6, ref))
        return part

    def one(self, ref, x, y, o="D", text="R"):
        """A single-pad part (test point, wire pad): its pad is at (x, y); the body extends in direction o from the pad."""
        lib, name, value, fp, fields = self._c(ref)
        pins = symlib.pins(lib, name)
        p = pins[0]
        x, y = snap(x), snap(y)
        for ang in (0, 90, 180, 270):
            tmp = Part(ref, 0, 0, ang, [p], 1)
            if tmp.out[p["num"]] == OPP[o]: break
        dx, dy = rot(p["x"], p["y"], ang)
        ox_, oy_ = x - dx, y - dy
        if o in ("U", "D"):
            yy = y + (-3.5 if o == "U" else 3.5)
            ra = (x + 2.0, yy - 0.8, "left"); va = (x + 2.0, yy + 0.8, "left")
        else:
            s_ = 1 if o == "R" else -1
            ra = (x + s_ * 4.0, y - 4.4, "center"); va = (x + s_ * 4.0, y - 2.9, "center")
        self.text_box(ref, *ra, what="ref " + ref); self.text_box(value, *va, what="val " + ref)
        part = self._symbol(lib, name, ref, value, ox_, oy_, ang, 1, fp, fields, ra, va)
        part.a = (x, y)
        return part

    # ---------- wires, labels, power ----------
    def w(self, *pts):
        pts = [(snap(p[0]), snap(p[1])) for p in pts]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if (x1, y1) == (x2, y2): continue
            if x1 != x2 and y1 != y2: self.warn.append(f"diagonal wire {x1,y1}-{x2,y2}")
            self.wires.append((x1, y1, x2, y2))
            self._e(x1, y1, x2, y2)
            self.items.append(f'(wire (pts (xy {self.X(x1)} {self.Y(y1)}) (xy {self.X(x2)} {self.Y(y2)})) (stroke (width 0) (type default)) '
                              f'(uuid {q(uid(self.name, "w", x1, y1, x2, y2))}))')
        return pts[-1]

    def label(self, x, y, d, net, shown=None, above=False):
        """A net label whose connection point is (x, y), text running in direction d (R, L; U and D read sideways)."""
        x, y = snap(x), snap(y)
        text = shown or self.disp(net)
        ang = {"R": 0, "L": 180, "U": 90, "D": 270}[d]
        glob = net in self.glob
        w = len(text) * CHW + (3.2 if glob else 0.6)
        v = DIRV[d]
        x0, x1 = sorted((x, x + v[0] * w)); y0, y1 = sorted((y, y + v[1] * w))
        if d in "RL": y0, y1 = (y - 1.6, y - 0.1) if (above or net not in self.glob) else (y - 0.9, y + 0.9)
        else: x0, x1 = x - 0.9, x + 0.9
        self.texts.append((x0, y0, x1, y1, "label " + text))
        self._e(x0, y0, x1, y1)
        self.marks.append((x, y, net, "label"))
        self.shown.setdefault(text, set()).add(net)
        if glob:
            j = {0: "(justify left)", 90: "(justify left)", 180: "(justify right)", 270: "(justify right)"}[ang]
            self.items.append(f'(global_label {q(text)} (shape passive) (at {self.X(x)} {self.Y(y)} {ang}) (effects (font (size 1.27 1.27)) {j}) '
                              f'(uuid {q(uid(self.name, "gl", text, x, y))}) (property "Intersheetrefs" "${{INTERSHEET_REFS}}" '
                              f'(at {self.X(x)} {self.Y(y)} 0) (effects (font (size 1.27 1.27)) (hide yes))))')
        else:
            j = {0: "(justify left bottom)", 90: "(justify left bottom)", 180: "(justify right bottom)", 270: "(justify right bottom)"}[ang]
            self.items.append(f'(label {q(text)} (at {self.X(x)} {self.Y(y)} {ang}) (effects (font (size 1.27 1.27)) {j}) '
                              f'(uuid {q(uid(self.name, "l", text, x, y))}))')

    def netlabel(self, pt, d, net=None, ref=None, pad=None, stub=2.54):
        """Wire a short stub out of pt in direction d and put the net's label on its end."""
        net = net or self.netof(ref, pad)
        v = DIRV[d]
        e = (pt[0] + v[0] * stub, pt[1] + v[1] * stub)
        if stub: self.w(pt, e)
        self.label(e[0], e[1], d, net)
        return e

    def gnd(self, x, y):
        x, y = snap(x), snap(y)
        self.npwr += 1
        ref = f"#PWR{uid(self.name, 'p', x, y)[:6].upper()}"
        self._symbol("power", "GND", ref, "GND", x, y, 0, 1, "", {}, None, None, True, True, key=f"gnd{x}_{y}")
        self.marks.append((x, y, "GND", "power")); self._e(x, y + 3.2)
        self.bodies.pop(); self.bodies.append((x - 1.5, y + 0.1, x + 1.5, y + 3.0, "gnd"))
        self.pinpts.pop()                # a ground symbol is not a part pin to lint

    def gndx(self, x, y, net):
        """A ground-style symbol that names a net other than GND (the gauge's Kelvin ground): GND artwork, the net's name under it."""
        x, y = snap(x), snap(y)
        text = self.disp(net)
        ref = f"#PWR{uid(self.name, 'g', x, y)[:6].upper()}"
        self._symbol("power", "GND", ref, text, x, y, 0, 1, "", {}, None, (x, y + 4.6, "center"), True, False, key=f"gndx{x}_{y}")
        self.bodies.pop(); self.bodies.append((x - 1.5, y + 0.1, x + 1.5, y + 3.0, "gnd"))
        self.text_box(text, x, y + 4.6, "center", what="gnd " + text)
        self.pinpts.pop()
        self.marks.append((x, y, net, "power"))

    def fan(self, pins, targets, side="L", base=2.54, step=2.54):
        """Spread pins that sit 2.54 mm apart onto rows far enough apart for parts. Every pin runs straight out base mm,
        then jogs to its target row; jogs are staggered so no wire crosses another (rows that move up: topmost jogs
        nearest the body; rows that move down: bottom-most). Returns the (x, y) where each row now starts."""
        sx = -1 if side == "L" else 1
        n = len(pins)
        order = list(range(n))
        up = sorted([i for i in order if targets[i] < pins[i][1] - 0.01], key=lambda i: pins[i][1])
        down = sorted([i for i in order if targets[i] > pins[i][1] + 0.01], key=lambda i: -pins[i][1])
        res = {}
        for k, i in enumerate(up):
            xj = pins[i][0] + sx * (base + step * k)
            self.w(pins[i], (xj, pins[i][1]), (xj, targets[i])); res[i] = (xj, targets[i])
        for k, i in enumerate(down):
            xj = pins[i][0] + sx * (base + step * k)
            self.w(pins[i], (xj, pins[i][1]), (xj, targets[i])); res[i] = (xj, targets[i])
        for i in order:
            if i not in res:
                xj = pins[i][0] + sx * base
                self.w(pins[i], (xj, pins[i][1])); res[i] = (xj, pins[i][1])
        return [res[i] for i in order]

    def rail(self, x, y, net, up=True):
        """A supply symbol (arrow up, net name over it) sitting on a wire end at (x, y). Global nets only: it names the net."""
        x, y = snap(x), snap(y)
        text = self.disp(net)
        ref = f"#PWR{uid(self.name, 'r', x, y)[:6].upper()}"
        self._symbol("power", "+3V3", ref, text, x, y, 0, 1, "", {}, None, (x, y - 4.2, "center"), True, False, key=f"rail{x}_{y}")
        self.bodies.pop(); self.bodies.append((x - 1.2, y - 3.0, x + 1.2, y - 0.1, "rail"))
        self.text_box(text, x, y - 4.2, "center", what="rail " + text)
        self.pinpts.pop()
        self.marks.append((x, y, net, "power"))

    def nc(self, x, y):
        x, y = snap(x), snap(y)
        self.items.append(f'(no_connect (at {self.X(x)} {self.Y(y)}) (uuid {q(uid(self.name, "nc", x, y))}))')
        self.marks.append((x, y, None, "nc"))

    def sh(self, x, y):
        """Pin x, y of nothing: record that a wire ends here deliberately (no warning)."""
        pass

    # ---------- output ----------
    def junctions(self):
        pts = {}
        def bump(p, k, n=1): pts.setdefault(p, {}).setdefault(k, 0); pts[p][k] += n
        for (x1, y1, x2, y2) in self.wires:
            bump((x1, y1), "end"); bump((x2, y2), "end")
        for (x, y, ref, pad) in self.pinpts: bump((round(x, 4), round(y, 4)), "pin")
        for m in self.marks:
            if m[3] == "power": bump((round(m[0], 4), round(m[1], 4)), "pin")
        js = []
        for p, d in pts.items():
            thru = 0
            for (x1, y1, x2, y2) in self.wires:
                if x1 == x2 == p[0] and min(y1, y2) < p[1] < max(y1, y2): thru += 1
                elif y1 == y2 == p[1] and min(x1, x2) < p[0] < max(x1, x2): thru += 1
            n = d.get("end", 0) + d.get("pin", 0) + thru * 2
            if n >= 3 and (d.get("end", 0) or thru): js.append(p)
        return js

    def connectivity(self):
        """Union pins, marks and wires by geometry and check every connected group carries exactly one net."""
        P = {}
        def node(p): return P.setdefault(p, p)
        def find(p):
            while P[p] != p:
                P[p] = P[P[p]]; p = P[p]
            return p
        def union(a, b): P[find(node(a))] = find(node(b))
        pts = {}
        for (x, y, ref, pad) in self.pinpts: pts.setdefault((round(x, 4), round(y, 4)), []).append(("pin", ref, pad))
        for (x, y, net, _k) in self.marks: pts.setdefault((round(x, 4), round(y, 4)), []).append(("mark", net))
        for p in pts: node(p)
        for (x1, y1, x2, y2) in self.wires:
            node((x1, y1)); node((x2, y2)); union((x1, y1), (x2, y2))
            for p in pts:
                if (x1 == x2 == p[0] and min(y1, y2) <= p[1] <= max(y1, y2)) or (y1 == y2 == p[1] and min(x1, x2) <= p[0] <= max(x1, x2)):
                    union(p, (x1, y1))
        # wires meeting a wire's interior also connect (T junctions)
        for a in self.wires:
            for b in self.wires:
                for e in ((b[0], b[1]), (b[2], b[3])):
                    if (a[0] == a[2] == e[0] and min(a[1], a[3]) <= e[1] <= max(a[1], a[3])) or (a[1] == a[3] == e[1] and min(a[0], a[2]) <= e[0] <= max(a[0], a[2])):
                        union(e, (a[0], a[1]))
        groups = {}
        for p, items in pts.items():
            groups.setdefault(find(p), []).extend(items)
        W = []
        seen_pin = set()
        for g, items in groups.items():
            nets = set()
            for it in items:
                if it[0] == "pin":
                    n = self.netof(it[1], it[2])
                    nets.add(n)
                    seen_pin.add((it[1], it[2]))
                else: nets.add(it[1])
            nets.discard(None)
            if len(nets) > 1:
                W.append("SHORT: one drawn net carries " + " + ".join(sorted(nets)) + " at " + str(sorted(pts)[0] if False else [p for p in pts if find(p) == g][:2]))
        # every pin must touch a wire or a symbol or a mark
        wired = {find((a[0], a[1])) for a in self.wires}
        cnt = {}
        for g, items in groups.items():
            cnt[g] = len(items)
        for p, items in pts.items():
            for it in items:
                if it[0] == "pin" and not it[1].startswith("#"):
                    n = self.netof(it[1], it[2])
                    if n is None: continue
                    if cnt[find(p)] < 2 and find(p) not in wired:
                        W.append(f"pin {it[1]}.{it[2]} ({n}) is not connected to anything at {p}")
        for t, ns in self.shown.items():
            if len(ns) > 1: W.append(f"label text '{t}' used for different nets {sorted(ns)}")
        return W

    def lint(self):
        W = []
        W += self.connectivity()
        # collinear overlapping wires
        ws = self.wires
        for i in range(len(ws)):
            for j in range(i + 1, len(ws)):
                a, b = ws[i], ws[j]
                if a[0] == a[2] == b[0] == b[2] and max(min(a[1], a[3]), min(b[1], b[3])) < min(max(a[1], a[3]), max(b[1], b[3])):
                    W.append(f"overlapping wires {a} {b}")
                if a[1] == a[3] == b[1] == b[3] and max(min(a[0], a[2]), min(b[0], b[2])) < min(max(a[0], a[2]), max(b[0], b[2])):
                    W.append(f"overlapping wires {a} {b}")
        # wire inside a body or a text box
        def seg_in(w, box, m=0.15):
            x1, y1, x2, y2 = w
            bx0, by0, bx1, by1 = box[0] + m, box[1] + m, box[2] - m, box[3] - m
            if bx0 >= bx1 or by0 >= by1: return False
            return max(min(x1, x2), bx0) < min(max(x1, x2), bx1) and max(min(y1, y2), by0) < min(max(y1, y2), by1) or \
                (x1 == x2 and bx0 < x1 < bx1 and max(min(y1, y2), by0) < min(max(y1, y2), by1)) or \
                (y1 == y2 and by0 < y1 < by1 and max(min(x1, x2), bx0) < min(max(x1, x2), bx1))
        for w in self.wires:
            for b in self.bodies:
                if seg_in(w, b[:4]): W.append(f"wire {w} crosses body of {b[4]}")
            for t in self.texts:
                if seg_in(w, t[:4], 0.2): W.append(f"wire {w} runs through text '{t[4]}'")
        # overlaps text/text, text/body
        def ov(a, b, m=0.1):
            return a[0] + m < b[2] and b[0] + m < a[2] and a[1] + m < b[3] and b[1] + m < a[3]
        for i in range(len(self.texts)):
            for j in range(i + 1, len(self.texts)):
                if ov(self.texts[i], self.texts[j]): W.append(f"text overlap: '{self.texts[i][4]}' / '{self.texts[j][4]}'")
            for b in self.bodies:
                if ov(self.texts[i], b[:4], 0.2) and not self.texts[i][4].endswith(b[4]): W.append(f"text '{self.texts[i][4]}' over body of {b[4]}")
        for i in range(len(self.bodies)):
            for j in range(i + 1, len(self.bodies)):
                if ov(self.bodies[i], self.bodies[j], 0.3): W.append(f"bodies overlap: {self.bodies[i][4]} / {self.bodies[j][4]}")
        return W

    def write(self, path, layout, frame_title=None):
        """Run layout(self) twice: once to measure, once centred on the smallest standard page that holds it."""
        self.reset(0, 0); self.warn = []
        self.m = None
        layout(self)
        x0, y0, x1, y1 = self.ext
        self.m = (x0, y0, x1, y1)
        y0 -= 14                      # room for the header
        w, h = x1 - x0, y1 - y0
        for pname, pw, ph in PAPERS:
            if w <= pw - 40 and h <= ph - 20 - 36: break
        # usable area: frame margin 10 + 8, title block 36 high at the bottom
        ax0, ay0, ax1, ay1 = 18, 18, pw - 18, ph - 18 - 30
        ox = ax0 + (ax1 - ax0 - w) / 2 - x0
        oy = ay0 + (ay1 - ay0 - h) / 2 - y0
        ox, oy = snap(ox), snap(oy)
        self.reset(ox, oy); self.warn = []
        layout(self)
        for p in self.junctions():
            self.items.append(f'(junction (at {self.X(p[0])} {self.Y(p[1])}) (diameter 0) (color 0 0 0 0) (uuid {q(uid(self.name, "j", p[0], p[1]))}))')
        out = [f'(kicad_sch (version {VERSION}) (generator "p2p_draw") (generator_version "10.0") (uuid {q(self.uuid)}) '
               f'(paper {q(pname)}) (title_block (title {q(self.title)}) (comment 1 "Generated from code. Do not edit: change the block source and rebuild."))',
               "(lib_symbols " + "\n".join(self.libs.values()) + ")"]
        out += self.items
        out.append("(embedded_fonts no))")
        open(path, "w").write("\n".join(out) + "\n")
        W = self.warn + self.lint()
        print(f"  [{self.name}] paper {pname}, drawing {w:.0f} x {h:.0f} mm, {len(W)} lint warnings")
        for m in W[:60]: print("     ", m)
        return W


def chain(s, pt, side, net, items, text="S"):
    """Draw a row of parts and wire from pt in direction side ('L' or 'R'). net: the net at pt.
    items: numbers (wire length), ("p", ref) a part lying along the row, then one terminal:
    ("label",) the current net's label, ("gnd",), ("gndx", net), ("rail", net), ("pad", ref), ("nc",).
    Returns (x, y, net) at the end."""
    x, y = pt
    sg = -1 if side == "L" else 1
    for it in items:
        if isinstance(it, (int, float)):
            nx = x + sg * it; s.w((x, y), (nx, y)); x = nx; continue
        k = it[0]
        if k == "p":
            ref = it[1]
            n1, n2 = s.netof(ref, sorted({p for (r, p) in s.pinnet if r == ref})[0]), s.netof(ref, sorted({p for (r, p) in s.pinnet if r == ref})[1])
            other = n2 if n1 == net else n1
            if side == "L":
                part = s.two(ref, x - 7.62, y, "h", a=other, text=it[2] if len(it) > 2 else text)
                x = x - 7.62; net = other
            else:
                part = s.two(ref, x, y, "h", a=net, text=it[2] if len(it) > 2 else text)
                x = x + 7.62; net = other
        elif k == "label": s.label(x, y, side, net)
        elif k == "gnd": s.gnd(x, y)
        elif k == "gndx": s.gndx(x, y, it[1])
        elif k == "rail": s.rail(x, y, it[1])
        elif k == "nc": s.nc(x, y)
        elif k == "pad": s.one(it[1], x, y, it[2] if len(it) > 2 else ("R" if side == "L" else "L"))
    return x, y, net


class Shift:
    """A view of a Sch whose drawing calls are moved by (dx, dy): lets a section be written in its own coordinates and placed
    anywhere (e.g. as a second column of the sheet). Points and parts it returns are in the section's own coordinates."""
    def __init__(self, s, dx, dy):
        self.s, self.dx, self.dy = s, dx, dy

    def __getattr__(self, name):
        return getattr(self.s, name)

    def _p(self, pt): return (pt[0] + self.dx, pt[1] + self.dy)
    def _u(self, pt): return (round(pt[0] - self.dx, 4), round(pt[1] - self.dy, 4))
    def _at(self, at): return None if at is None else (at[0] + self.dx, at[1] + self.dy, at[2])

    def _part(self, part):
        import copy
        q = copy.copy(part)
        q.pad = {k: self._u(v) for k, v in part.pad.items()}
        for a in ("a", "b", "ca"):
            if hasattr(part, a): setattr(q, a, self._u(getattr(part, a)))
        return q

    def ic(self, ref, x, y, **k):
        for f in ("ref_at", "val_at"):
            if k.get(f): k[f] = self._at(k[f])
        return self._part(self.s.ic(ref, x + self.dx, y + self.dy, **k))

    def two(self, ref, x, y, *a, **k): return self._part(self.s.two(ref, x + self.dx, y + self.dy, *a, **k))
    def one(self, ref, x, y, *a, **k): return self._part(self.s.one(ref, x + self.dx, y + self.dy, *a, **k))
    def w(self, *pts): return self.s.w(*[self._p(p) for p in pts])
    def label(self, x, y, *a, **k): return self.s.label(x + self.dx, y + self.dy, *a, **k)
    def netlabel(self, pt, *a, **k): return self._u(self.s.netlabel(self._p(pt), *a, **k))
    def gnd(self, x, y): return self.s.gnd(x + self.dx, y + self.dy)
    def gndx(self, x, y, net): return self.s.gndx(x + self.dx, y + self.dy, net)
    def rail(self, x, y, net, **k): return self.s.rail(x + self.dx, y + self.dy, net, **k)
    def nc(self, x, y): return self.s.nc(x + self.dx, y + self.dy)
    def text(self, t, x, y, *a, **k): return self.s.text(t, x + self.dx, y + self.dy, *a, **k)
    def heading(self, t, x, y): return self.s.heading(t, x + self.dx, y + self.dy)
    def fan(self, pins, targets, *a, **k):
        r = self.s.fan([self._p(p) for p in pins], [t + self.dy for t in targets], *a, **k)
        return [self._u(p) for p in r]
