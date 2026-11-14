"""sch.py - a small scene-based schematic drawing kit for generated KiCad sheets.

The old generator (draw.py, draw_block) decides every position itself from the netlist. This module is the other
half of the design: a drawing kit in which a block's *layout* is written as a short program of placements and
connections between pins, and the kit takes care of everything a careful draftsman does by eye:

  * symbols are placed by pin position and know their pins as Ports (point + outward direction + net name);
  * wires are drawn pin to pin (link) and the kit refuses to join two different nets;
  * reference/value text is placed after the wiring, on the side of the part where it hits nothing;
  * junction dots are added wherever three or more things meet;
  * ground and supply symbols, net labels (global when the net leaves the sheet), no-connect marks;
  * titled, framed sections, notes, and a paper size that fits the drawing;
  * a lint pass reports overlapping text, wires through symbols, text on wires, pins touched by foreign wires,
    and re-derives the connectivity of the drawing from its geometry to compare it with the netlist.

Nothing here decides connectivity: the netlist (netlist.json) is the truth and `make.sh` proves the result equal to it.
"""
import copy, math, os, uuid
import symlib
from sx import find, first, get, val, parse

NS = uuid.UUID("6f1c2b1e-58a5-4c6e-9a59-0d5a1f2b7c11")
G = 1.27
VERSION = "20260306"
CW = 1.2                  # mm per character of 1.27 mm text (measured on the exported PDF)
TH = 1.5                  # height of a text line's box
LINE = 2.0                # pitch of multi-line text at 1.27 mm
DIRV = {"L": (-1, 0), "R": (1, 0), "U": (0, -1), "D": (0, 1)}
OPP = {"L": "R", "R": "L", "U": "D", "D": "U"}


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


def hide_stacked(sym):
    """Several pads of one net often share one drawn pin position (exposed-pad grounds, N.C. pads). KiCad's rule for
    that is: the first pin is drawn, the others carry (hide yes), and they still connect by geometry. A library symbol
    that forgot to hide them prints four pin numbers on top of each other, so hide them here. Power pins stay visible:
    a hidden power-input pin would join the net named like the pin."""
    for u in sym[2:]:
        if not (isinstance(u, list) and u[0] == "symbol"): continue
        seen = set()
        for pin in u[2:]:
            if not (isinstance(pin, list) and pin[0] == "pin"): continue
            at = next(c for c in pin if isinstance(c, list) and c[0] == "at")
            k = (at[1], at[2], at[3] if len(at) > 3 else "0")
            hidden = any(isinstance(c, list) and c[0] == "hide" for c in pin)
            if k in seen and not hidden and pin[1] not in ("power_in", "power_out"):
                pin.insert(next(i for i, c in enumerate(pin) if isinstance(c, list) and c[0] == "length") + 1, ["hide", "yes"])
            elif not hidden:
                seen.add(k)


def expand_stacked(sym):
    """A pin whose number is KiCad's stacked notation with more than two pads, such as [11,12,14,31,39], is drawn as a row of
    rotated numbers in brackets, 1.3 mm apart: on a pin that points down it is a smudge. Draw the first pad number and keep
    the other pads as hidden passive pins at the same point, as KiCad's own libraries do for exposed pads. They connect by
    geometry, so the net list is unchanged (checked by make.sh). Two-pad stacks such as [15,30] stay: they read well."""
    for u in sym[2:]:
        if not (isinstance(u, list) and u[0] == "symbol"): continue
        out = []
        for pin in u[2:]:
            nums = symlib.stack_numbers(get(pin, "number", "")) if isinstance(pin, list) and pin[0] == "pin" else None
            if not nums or len(nums) < 3:
                out.append(pin); continue
            for i, n in enumerate(nums):
                p = copy.deepcopy(pin)
                first(p, "number")[1] = ("s", n)
                if i:
                    p[1] = "passive"
                    p.insert(next(k for k, c in enumerate(p) if isinstance(c, list) and c[0] == "length") + 1, ["hide", "yes"])
                out.append(p)
        u[2:] = out


_LW = "(stroke (width 0.254) (type default))"
_FET = ("(polyline (pts (xy -3.81 1.27) (xy -1.27 1.27)) {s} (fill (type none)))"          # gate lead
        "(polyline (pts (xy -1.27 2.03) (xy -1.27 -2.03)) {s} (fill (type none)))"          # gate plate
        "(polyline (pts (xy -0.51 2.03) (xy -0.51 0.76)) {s} (fill (type none)))"           # channel, three pieces
        "(polyline (pts (xy -0.51 0.38) (xy -0.51 -0.38)) {s} (fill (type none)))"
        "(polyline (pts (xy -0.51 -0.76) (xy -0.51 -2.03)) {s} (fill (type none)))"
        "(polyline (pts (xy -0.51 1.27) (xy 3.81 1.27)) {s} (fill (type none)))"            # drain
        "(polyline (pts (xy -0.51 -1.27) (xy 3.81 -1.27)) {s} (fill (type none)))"          # source
        "(polyline (pts (xy -0.51 0) (xy 1.78 0) (xy 1.78 -1.27)) {s} (fill (type none)))"  # body tied to the source
        "(polyline (pts (xy 0.25 0.51) (xy -0.51 0) (xy 0.25 -0.51) (xy 0.25 0.51)) (stroke (width 0) (type default)) (fill (type outline)))"
        "(circle (center 1.78 -1.27) (radius 0.254) (stroke (width 0) (type default)) (fill (type outline)))")


def fet_glyph(sym):
    """Library MOSFETs drawn as a plain box (gate left, drain upper right, source lower right) read as ICs. Draw the
    transistor itself in the box's place and drop the pin names, which the glyph already says. Only symbols described as
    N-MOSFET with the box and pin positions of those two parts are touched."""
    d = [val(p[2]) for p in find(sym, "property") if val(p[1]) == "Description"]
    if not d or "N-MOSFET" not in d[0]: return
    for u in sym[2:]:
        if not (isinstance(u, list) and u[0] == "symbol" and val(u[1]).endswith("_0_1")): continue
        rects = [c for c in u[2:] if isinstance(c, list) and c[0] == "rectangle"]
        if len(rects) != 1: return
        r = rects[0]
        if [float(v) for v in first(r, "start")[1:3] + first(r, "end")[1:3]] != [-3.81, 3.81, 3.81, -3.81]: return
        i = u.index(r)
        u[i:i + 1] = parse("(g " + _FET.format(s=_LW) + ")")[1:]
        pn = first(sym, "pin_names")
        if pn is not None and not find(pn, "hide"): pn.append(["hide", "yes"])
        return


def rot(x, y, a):
    """Symbol coordinates (y up) rotated a degrees counter-clockwise, returned as a screen offset (y down)."""
    a = a % 360
    if a == 0: xr, yr = x, y
    elif a == 90: xr, yr = -y, x
    elif a == 180: xr, yr = -x, -y
    else: xr, yr = y, -x
    return xr, -yr


def vdir(dx, dy):
    if abs(dx) >= abs(dy): return "R" if dx > 0 else "L"
    return "D" if dy > 0 else "U"


def tw(s, size=1.27):
    """Width of a text line in mm."""
    return len(s) * CW * size / 1.27


# ---------------------------------------------------------------------------------------------------------------
# symbol geometry
# ---------------------------------------------------------------------------------------------------------------
_GEO = {}


def _pts_of(g):
    k = g[0]
    if k == "rectangle":
        a, b = first(g, "start"), first(g, "end")
        return [(float(a[1]), float(a[2])), (float(b[1]), float(b[2]))]
    if k == "polyline":
        return [(float(x[1]), float(x[2])) for x in find(first(g, "pts"), "xy")]
    if k == "circle":
        c = first(g, "center"); r = float(get(g, "radius")); cx, cy = float(c[1]), float(c[2])
        return [(cx - r, cy - r), (cx + r, cy + r)]
    if k == "arc":
        return [(float(first(g, n)[1]), float(first(g, n)[2])) for n in ("start", "mid", "end")]
    return []


def geom(lib, name):
    """({unit: [x0, y0, x1, y1]} body boxes in symbol coordinates (y up), [pins as symlib.pins])."""
    key = (lib, name)
    if key not in _GEO:
        s = symlib.flat(lib, name)
        boxes = {}
        for u in find(s, "symbol"):
            unit, style = (int(v) for v in val(u[1]).rsplit("_", 2)[-2:])
            if style > 1: continue
            for g in u[2:]:
                if isinstance(g, list) and g and g[0] in ("rectangle", "polyline", "circle", "arc"):
                    for x, y in _pts_of(g):
                        b = boxes.setdefault(unit, [1e9, 1e9, -1e9, -1e9])
                        b[0], b[1], b[2], b[3] = min(b[0], x), min(b[1], y), max(b[2], x), max(b[3], y)
        _GEO[key] = (boxes, symlib.pins(lib, name))
    return _GEO[key]


# ---------------------------------------------------------------------------------------------------------------
# ports and placed symbols
# ---------------------------------------------------------------------------------------------------------------
class Port:
    """A connection point: where a wire can attach, the direction a wire leaves it (away from the part), its net."""
    __slots__ = ("x", "y", "d", "net", "ref", "pin")

    def __init__(self, x, y, d=None, net=None, ref=None, pin=None):
        self.x, self.y, self.d, self.net, self.ref, self.pin = snap(x), snap(y), d, net, ref, pin

    def to(self, dx=0.0, dy=0.0, d="keep"):
        return Port(self.x + dx, self.y + dy, self.d if d == "keep" else d, self.net, self.ref, self.pin)

    def out(self, length):
        """The point `length` mm further out along the port's direction."""
        dx, dy = DIRV[self.d]
        return Port(self.x + dx * length, self.y + dy * length, self.d, self.net, self.ref, self.pin)

    def at(self, x=None, y=None):
        return Port(self.x if x is None else x, self.y if y is None else y, self.d, self.net, self.ref, self.pin)

    @property
    def xy(self):
        return (self.x, self.y)

    def __repr__(self):
        return f"Port({self.ref or ''}.{self.pin or ''} {self.x},{self.y} {self.d} {self.net})"


def _pt(p):
    return (p.x, p.y) if isinstance(p, Port) else (snap(p[0]), snap(p[1]))


class Placed:
    """One symbol (one unit of it) placed on the sheet."""

    def __init__(self, S, ref, x, y, angle=0, mirror=False, unit=1, value=None, text="auto", fieldsize=1.27):
        self.S, self.ref = S, ref
        c = S.comps[ref]
        self.lib, self.name = c["lib"].split(":")
        self.value = c["value"] if value is None else value
        self.x, self.y, self.angle, self.mirror, self.unit = snap(x), snap(y), angle, mirror, unit
        self.text, self.fs = text, fieldsize
        boxes, allpins = geom(self.lib, self.name)
        self.pins, self.byname = {}, {}
        xs, ys = [], []
        body = boxes.get(0), boxes.get(unit)
        bb = [b for b in body if b]
        if bb:
            bx = [min(b[0] for b in bb), min(b[1] for b in bb), max(b[2] for b in bb), max(b[3] for b in bb)]
            for cx, cy in ((bx[0], bx[1]), (bx[2], bx[3])):
                px, py = self.tf(cx, cy, False); xs.append(px); ys.append(py)
            self.body = (min(xs), min(ys), max(xs), max(ys))
        else:
            self.body = None
        for p in allpins:
            if p["unit"] not in (0, unit): continue
            tx, ty = self.tf(p["x"], p["y"])
            ca, sa = math.cos(math.radians(p["angle"])), math.sin(math.radians(p["angle"]))
            bx_, by_ = self.tf(p["x"] + ca, p["y"] + sa)
            d = vdir(tx - bx_, ty - by_)
            port = Port(tx, ty, d, S.net_of(ref, p["num"]), ref, p["name"])
            self.pins[p["num"]] = (port, p)
            if not p["hidden"]:
                self.byname.setdefault(p["name"], []).append(port)
                ex, ey = self.tf(p["x"] + ca * p["length"], p["y"] + sa * p["length"])
                xs += [tx, ex]; ys += [ty, ey]
        if self.body: xs += [self.body[0], self.body[2]]; ys += [self.body[1], self.body[3]]
        self.bbox = (min(xs), min(ys), max(xs), max(ys)) if xs else (self.x, self.y, self.x, self.y)
        self.tbox = []           # text boxes placed by resolve(): [(x0, y0, x1, y1)]
        self.fields = None       # resolved: (ref_pos, val_pos) set by the text placer

    # -- geometry ---------------------------------------------------------------------------------------------
    def tf(self, px, py, grid=True):
        dx, dy = rot(px, py, self.angle)
        if self.mirror: dx = -dx
        if not grid: return self.x + dx, self.y + dy
        return snap(self.x + dx), snap(self.y + dy)

    def p(self, key):
        """Port by pad number, else by pin name (the drawn one)."""
        key = str(key)
        if key in self.pins: return self.pins[key][0]
        if key in self.byname: return self.byname[key][0]
        raise KeyError(f"{self.ref} ({self.lib}:{self.name}) has no pin '{key}'. Pins: " +
                       " ".join(sorted({f"{n}:{v[1]['name']}" for n, v in self.pins.items()})))

    def ps(self, name):
        return list(self.byname[name])

    def drawn_pad(self, port):
        """pad number of the visible pin at a port"""
        for n, (pt, p) in self.pins.items():
            if pt is port: return p["drawn"]
        return None

    @property
    def cx(self): return (self.bbox[0] + self.bbox[2]) / 2

    @property
    def cy(self): return (self.bbox[1] + self.bbox[3]) / 2


class Two(Placed):
    """A two-pad part. Ports a and b; for a vertical part a is the top, for a horizontal one the left."""

    def __init__(self, S, ref, x, y, orient="v", first=None, **kw):
        c = S.comps[ref]
        lib, name = c["lib"].split(":")
        boxes, allpins = geom(lib, name)
        pads = {}
        for p in allpins:
            pads.setdefault(p["num"], p)
        nums = sorted(pads)
        assert len(nums) == 2, f"{ref} is not a two-pad part"
        na = nums[0]
        if first is not None:
            fnet = S.net(first)
            nets = [S.net_of(ref, n) for n in nums]
            if nets[1] == fnet and nets[0] != fnet: na = nums[1]
            elif nets[0] != fnet and nets[1] != fnet:
                raise ValueError(f"{ref}: neither pad is on net {fnet} (pads on {nets})")
        nb = nums[1] if na == nums[0] else nums[0]
        for a in (0, 90, 180, 270):
            ux, uy = rot(pads[na]["x"], pads[na]["y"], a); dx, dy = rot(pads[nb]["x"], pads[nb]["y"], a)
            if orient == "v" and abs(ux) < 0.01 and abs(dx) < 0.01 and uy < dy: break
            if orient == "h" and abs(uy) < 0.01 and abs(dy) < 0.01 and ux < dx: break
        else:
            raise ValueError(f"{ref}: cannot orient {lib}:{name} as {orient}")
        self.orient = orient
        super().__init__(S, ref, x, y, angle=a, **kw)
        self.a, self.b = self.pins[na][0], self.pins[nb][0]
        self.na, self.nb = na, nb

    @property
    def t(self): return self.a          # vertical: top

    @property
    def bt(self): return self.b         # vertical: bottom

    @property
    def l(self): return self.a          # horizontal: left

    @property
    def r(self): return self.b          # horizontal: right


# ---------------------------------------------------------------------------------------------------------------
# the scene
# ---------------------------------------------------------------------------------------------------------------
class Ctx:
    """What a sheet needs from the netlist."""

    def __init__(self, block, comps, nets, nc, cons):
        self.block = block
        self.comps, self.nets, self.cons = comps, nets, cons
        self.refs = {r for r, c in comps.items() if c["block"] == block}
        self.pinnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
        self.nc = {(r, p) for r, p in nc}
        self.glob = {n for n, nodes in nets.items()
                     if any(r not in self.refs for r, _ in nodes) and any(r in self.refs for r, _ in nodes)}
        self.power = {n for n, d in cons["nets"].items() if d.get("kind") == "power"}


class Scene:
    def __init__(self, ctx, name, project, root_uuid, title):
        self.ctx = ctx
        self.comps, self.pinnet, self.glob = ctx.comps, ctx.pinnet, ctx.glob
        self.name, self.project, self.root_uuid, self.title = name, project, root_uuid, title
        self.uuid = uid("sheet", name)
        self.items = []            # finished s-expressions (everything but symbols)
        self.libs = {}
        self.placed = []           # Placed symbols
        self.wires = []            # (x1, y1, x2, y2, net)
        self.junctions = set()
        self.boxes = []            # (x0, y0, x1, y1, kind, text) text-like things: labels, power values, notes, titles
        self.pwr = []              # (kind, x, y, dir, net) power symbols
        self.ncs = []
        self.frames = []           # (x0, y0, x1, y1)
        self.nobox = set()         # indices of wires that run between sections and do not count for section boxes
        self.npwr = 0
        self.sections = []
        self.warnings = []
        self.flags = []            # PWR_FLAG-like extra symbols: not used

    # ---- netlist access ---------------------------------------------------------------------------------------
    def net_of(self, ref, pad):
        if (ref, pad) in self.ctx.nc: return None
        return self.pinnet.get((ref, pad))

    def disp(self, net):
        """Name of a net as written on the sheet."""
        return net.lstrip("/") if net in self.glob else net.split("/")[-1]

    def net(self, name):
        """Full net name for a short one: 'VBUS' on sheet 'USB Port 1' is 'USB Port 1/VBUS'."""
        if name is None or name in self.ctx.nets: return name
        for cand in (f"{self.ctx.block}/{name}", f"/{name}"):
            if cand in self.ctx.nets: return cand
        return name

    def is_global(self, net):
        return net in self.glob

    def scratch(self):
        s = Scene(self.ctx, self.name, self.project, self.root_uuid, self.title)
        return s

    # ---- symbols ----------------------------------------------------------------------------------------------
    def place(self, ref, x, y, angle=0, mirror=False, unit=1, **kw):
        pl = Placed(self, ref, x, y, angle, mirror, unit, **kw)
        self.placed.append(pl)
        init_text(pl)
        return pl

    def two(self, ref, x, y, orient="v", first=None, **kw):
        pl = Two(self, ref, x, y, orient, first, **kw)
        self.placed.append(pl)
        init_text(pl)
        return pl

    def lib_key(self, lib, name):
        key = f"{lib}:{name}"
        if key not in self.libs:
            s = symlib.flat(lib, name)
            s[1] = ("s", key)
            expand_stacked(s)
            hide_stacked(s)
            fet_glyph(s)
            self.libs[key] = dump(s)
        return key

    # ---- wires and junctions ----------------------------------------------------------------------------------
    def wire(self, pts, net=None, bridge=False):
        """Polyline through points (Ports or (x, y)). Zero-length pieces are dropped, collinear pieces merged.
        bridge=True: the wire runs between two sections, so it does not stretch the box of the section it was drawn in."""
        P = [_pt(p) for p in pts]
        net = self.net(net)
        if net is None:
            for p in pts:
                if isinstance(p, Port) and p.net: net = self.net(p.net); break
        for p in pts:
            if isinstance(p, Port) and p.net and net and self.net(p.net) != net:
                raise ValueError(f"wire joins net '{net}' and '{p.net}' at {p}")
        for a, b in zip(P, P[1:]):
            if a == b: continue
            assert a[0] == b[0] or a[1] == b[1], f"diagonal wire {a} -> {b}"
            if bridge: self.nobox.add(len(self.wires))
            self.wires.append((a[0], a[1], b[0], b[1], net))

    def link(self, p, q_, how="auto", mid=None, net=None):
        """Wire from port p to port q. how: auto, hv, vh, hvh (jog at x=mid), vhv (jog at y=mid)."""
        a, b = _pt(p), _pt(q_)
        pd = p.d if isinstance(p, Port) else None
        qd = q_.d if isinstance(q_, Port) else None
        if how == "auto":
            if a[0] == b[0] or a[1] == b[1]: how = "straight"
            elif pd in ("L", "R") and qd in ("L", "R"): how = "hvh"
            elif pd in ("U", "D") and qd in ("U", "D"): how = "vhv"
            elif pd in ("L", "R"): how = "hv"
            elif pd in ("U", "D"): how = "vh"
            elif qd in ("L", "R"): how = "vh"
            else: how = "hv"
        if how == "straight": pts = [a, b]
        elif how == "hv": pts = [a, (b[0], a[1]), b]
        elif how == "vh": pts = [a, (a[0], b[1]), b]
        elif how == "hvh":
            m = snap((a[0] + b[0]) / 2) if mid is None else snap(mid)
            pts = [a, (m, a[1]), (m, b[1]), b]
        elif how == "vhv":
            m = snap((a[1] + b[1]) / 2) if mid is None else snap(mid)
            pts = [a, (a[0], m), (b[0], m), b]
        else:
            raise ValueError(how)
        pn = self.net(net)
        if pn is None:
            for e in (p, q_):
                if isinstance(e, Port) and e.net: pn = e.net; break
        if isinstance(p, Port) and isinstance(q_, Port) and p.net and q_.net and self.net(p.net) != self.net(q_.net):
            raise ValueError(f"link joins {p} and {q_}: different nets")
        self.wire(pts, pn)

    def junction(self, x, y):
        self.junctions.add((snap(x), snap(y)))

    # ---- power symbols, labels, no-connects -------------------------------------------------------------------
    def gnd(self, p, d="D", net="GND"):
        """Ground symbol. Ground-like nets other than GND (a Kelvin ground, say) get the signal-ground symbol with the
        net's name under it; like every power symbol it is global, so such a net must not also be written with labels."""
        x, y = _pt(p)
        self.pwr.append(("gnd", x, y, d, "GND" if net == "GND" else self.disp(self.net(net))))

    def rail(self, net, p, d="U"):
        """Supply symbol (arrow) for a rail; the net's name is the symbol's value."""
        x, y = _pt(p)
        self.pwr.append(("rail", x, y, d, self.disp(net)))      # the symbol's value: global in KiCad, so only for global or unique names
        return Port(x, y, OPP[d], net)

    def nc(self, p):
        x, y = _pt(p)
        self.ncs.append((x, y))

    def label(self, net, p, d="R", glob=None, text=None):
        """Net label at p; its text extends in direction d (R = to the right of the wire end)."""
        x, y = _pt(p)
        net = self.net(net)
        s = text or self.disp(net)
        glob = (net in self.glob) if glob is None else glob
        w = tw(s)
        if glob:
            ww = len(s) * 1.13 + 1.7                      # measured on the rendered flags: 1.13 mm per character + margins
            if d == "R": bx = (x, y - 1.27, x + ww, y + 1.27)
            elif d == "L": bx = (x - ww, y - 1.27, x, y + 1.27)
            elif d == "U": bx = (x - 1.27, y - ww, x + 1.27, y)
            else: bx = (x - 1.27, y, x + 1.27, y + ww)
            ang = {"R": 0, "L": 180, "U": 90, "D": 270}[d]
            just = "(justify left)" if d in ("R", "U") else "(justify right)"
            self.items.append(
                f'(global_label {q(s)} (shape passive) (at {x} {y} {ang}) (effects (font (size 1.27 1.27)) {just}) '
                f'(uuid {q(uid(self.name, "gl", s, x, y, d))}) (property "Intersheetrefs" "${{INTERSHEET_REFS}}" '
                f'(at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes))))')
        else:
            if d == "R": bx = (x + 0.3, y - 1.9, x + w + 0.6, y - 0.1)
            elif d == "L": bx = (x - w - 0.6, y - 1.9, x - 0.3, y - 0.1)
            elif d == "U": bx = (x - 1.9, y - w - 0.6, x - 0.1, y - 0.3)
            else: bx = (x - 1.9, y + 0.3, x - 0.1, y + w + 0.6)
            ang = {"R": 0, "L": 180, "U": 90, "D": 270}[d]
            just = "(justify left bottom)" if d in ("R", "U") else "(justify right bottom)"
            self.items.append(f'(label {q(s)} (at {x} {y} {ang}) (effects (font (size 1.27 1.27)) {just}) '
                              f'(uuid {q(uid(self.name, "l", s, x, y, d))}))')
        self.boxes.append(bx + ("label", s, (x, y)))

    def pin_label(self, p, d=None, length=2.54, net=None, text=None, glob=None):
        """Short wire out of a pin and a label on it. Returns the label's port."""
        d = d or p.d
        n = net or p.net
        e = p.out(length) if length else p
        if length: self.wire([p, e], n)
        self.label(n, e, d, glob=glob, text=text)
        return e

    def pin_gnd(self, p, length=0.0, net="GND"):
        e = p.out(length) if length else p
        if length: self.wire([p, e], net)
        d = {"L": "D", "R": "D", "U": "U", "D": "D"}[p.d]
        self.gnd(e, d, net)
        return e

    # ---- text -------------------------------------------------------------------------------------------------
    def _text_item(self, s, x, y, size, bold, justify, color):
        """(file item, lint box, bounding box) of a free text, its top-left (or top-right / top-centre) corner at (x, y)."""
        x, y = round(x, 3), round(y, 3)
        lines = s.split("\n")
        w = max(tw(l, size) for l in lines)
        h = len(lines) * LINE * size / 1.27
        x0 = x if justify == "left" else (x - w if justify == "right" else x - w / 2)
        col = f" (color {color})" if color else ""
        item = (f'(text {q(s)} (exclude_from_sim no) (at {x} {y} 0) (effects (font (size {size} {size}){" (bold yes)" if bold else ""}{col}) '
                f'(justify {justify} top)) (uuid {q(uid(self.name, "t", s, x, y))}))')
        return item, (x0, y - 0.1, x0 + w, y + h - 0.2), (x0, y, x0 + w, y + h)

    def text(self, s, x, y, size=1.27, bold=False, justify="left", color=None, kind="note"):
        """Free text, its top-left (or top-right / top-centre) corner at (x, y)."""
        item, box, bb = self._text_item(s, x, y, size, bold, justify, color)
        self.items.append(item)
        self.boxes.append(box + (kind, s, None))
        return bb

    def frame(self, x0, y0, x1, y1):
        self.frames.append((x0, y0, x1, y1))
        self.items.append(f'(rectangle (start {x0:.2f} {y0:.2f}) (end {x1:.2f} {y1:.2f}) '
                          f'(stroke (width 0.15) (type dash) (color 110 110 110 1)) (fill (type none)) '
                          f'(uuid {q(uid(self.name, "fr", x0, y0, x1, y1))}))')

    # ---- bounding box of what has been drawn ------------------------------------------------------------------
    def bbox(self, sub=None):
        """Box around everything drawn (or around the parts of a section: sub = (placed, wires, boxes, pwr, ncs) ranges)."""
        pr, wr, br, rr, nr = sub or (slice(None),) * 5
        xs, ys = [], []
        for pl in self.placed[pr]:
            xs += [pl.bbox[0], pl.bbox[2]]; ys += [pl.bbox[1], pl.bbox[3]]
            for b in pl.tbox: xs += [b[0], b[2]]; ys += [b[1], b[3]]
        for i in range(len(self.wires))[wr]:
            if i in self.nobox: continue
            w = self.wires[i]; xs += [w[0], w[2]]; ys += [w[1], w[3]]
        for b in self.boxes[br]: xs += [b[0], b[2]]; ys += [b[1], b[3]]
        for k, x, y, d, n in self.pwr[rr]:
            b = pwr_box(k, x, y, d, n); xs += [b[0], b[2]]; ys += [b[1], b[3]]
        for x, y in self.ncs[nr]: xs += [x - 1, x + 1]; ys += [y - 1, y + 1]
        if not xs: return None
        return (min(xs), min(ys), max(xs), max(ys))

    # ---- sections ---------------------------------------------------------------------------------------------
    def begin(self, title, x, y, note=None, pad=3.0):
        """Start a titled section whose top-left corner is (x, y). Returns it; its .ox/.oy is where contents start."""
        sec = Sec(self, title, snap(x), snap(y), note, pad)
        sec.start = (len(self.placed), len(self.wires), len(self.boxes), len(self.pwr), len(self.ncs))

        def head(s, y_, size, bold, kind):
            sec.hdr.append((len(self.items), len(self.boxes), s, y_, size, bold, kind))
            return self.text(s, sec.x + pad, y_, size, bold=bold, kind=kind)
        tb = head(title, sec.y + pad, 2.0, True, "title")
        ty = tb[3]
        if note:
            nb = head(note, ty + 0.8, 1.27, False, "note"); ty = nb[3]
        sec.ox = snap(sec.x + pad + 1.27)
        sec.oy = snap(ty + 4.0)
        self.sections.append(sec)
        return sec

    def end(self, sec):
        sec.stop = (len(self.placed), len(self.wires), len(self.boxes), len(self.pwr), len(self.ncs))
        return sec

    def finish(self):
        finish_scene(self)
        for sec in self.sections:
            if sec.stop is None: self.end(sec)
        for sec in self.sections:
            b = self.section_box(sec)
            self.retitle(sec, b[0])
            self.frame(*b)

    def retitle(self, sec, x0):
        """The title and description were written when the section began. A frame that a layout stretched to the left
        (Sec.max_x0) or that its content pushed out has its left edge further left by now: the header follows the corner."""
        nx = x0 + sec.pad
        if abs(nx - (sec.x + sec.pad)) < 0.01: return
        for ii, bi, s, y, size, bold, kind in sec.hdr:
            item, box, _ = self._text_item(s, nx, y, size, bold, "left", None)
            self.items[ii] = item
            self.boxes[bi] = box + (kind, s, None)

    def section_box(self, sec):
        sub = tuple(slice(a, b) for a, b in zip(sec.start, sec.stop))
        b = self.bbox(sub)
        return (min(sec.x, b[0] - sec.pad, 1e9 if sec.max_x0 is None else sec.max_x0), min(sec.y, b[1] - sec.pad),
                max(b[2] + sec.pad, sec.min_x1 or 0.0), max(b[3] + sec.pad, sec.min_y1 or 0.0))


class Sec:
    def __init__(self, S, title, x, y, note, pad):
        self.S, self.title, self.x, self.y, self.note, self.pad = S, title, x, y, note, pad
        self.start = self.stop = None
        self.hdr = []                          # the title and description texts: (item index, box index, text, y, size, bold, kind)
        self.min_x1 = self.min_y1 = None       # a layout may stretch the frame so that neighbours share an edge
        self.max_x0 = None                     # ... to the right and bottom (min_x1, min_y1) or to the left (max_x0)


def pwr_box(kind, x, y, d, net):
    if kind == "gnd" and net != "GND":                                   # signal ground with its name below
        w = max(tw(net) / 2 + 0.3, 1.4)
        return (x - w, y, x + w, y + 5.0)
    if kind == "gnd":
        return {"D": (x - 1.4, y, x + 1.4, y + 2.7), "U": (x - 1.4, y - 2.7, x + 1.4, y),
                "L": (x - 2.7, y - 1.4, x, y + 1.4), "R": (x, y - 1.4, x + 2.7, y + 1.4)}[d]
    w = tw(net) / 2 + 0.3
    return (x - max(w, 0.9), y - 5.0, x + max(w, 0.9), y)


# ---------------------------------------------------------------------------------------------------------------
# text placement
# ---------------------------------------------------------------------------------------------------------------
def tbox(s, x, y, just, size=1.27):
    w = tw(s, size)
    x0 = x if just == "left" else (x - w if just == "right" else x - w / 2)
    h = TH * size / 1.27
    return (x0, y - h / 2, x0 + w, y + h / 2)


def candidates(pl):
    """[(name, (ref x, y, justify), (value x, y, justify))] in order of preference."""
    r, v = pl.ref, pl.value
    out = []
    bx0, by0, bx1, by1 = pl.body or pl.bbox
    if isinstance(pl, Two) and pl.orient == "v":
        out.append(("R", (bx1 + 1.2, pl.y - 0.95, "left"), (bx1 + 1.2, pl.y + 0.95, "left")))
        out.append(("L", (bx0 - 1.2, pl.y - 0.95, "right"), (bx0 - 1.2, pl.y + 0.95, "right")))
    elif isinstance(pl, Two):
        out.append(("A", (pl.x, by0 - 2.9, "center"), (pl.x, by0 - 1.0, "center")))
        out.append(("B", (pl.x, by1 + 1.0, "center"), (pl.x, by1 + 2.9, "center")))
    else:
        x0, y0, x1, y1 = pl.bbox
        cy = (y0 + y1) / 2
        out.append(("TL", (x0, y0 - 3.4, "left"), (x0, y0 - 1.5, "left")))
        out.append(("R", (x1 + 1.1, cy - 0.95, "left"), (x1 + 1.1, cy + 0.95, "left")))
        out.append(("TR", (x1, y0 - 3.4, "right"), (x1, y0 - 1.5, "right")))
        out.append(("BL", (x0, y1 + 1.5, "left"), (x0, y1 + 3.4, "left")))
        out.append(("L", (x0 - 1.1, cy - 0.95, "right"), (x0 - 1.1, cy + 0.95, "right")))
        out.append(("BR", (x1, y1 + 1.5, "right"), (x1, y1 + 3.4, "right")))
    return out


def init_text(pl):
    """Candidate positions for the reference and value; the first one until the resolver chooses."""
    pl.cand_list = candidates(pl)
    if pl.text not in ("auto", None, "none"):
        sel = [c for c in pl.cand_list if c[0] == pl.text]
        if sel: pl.cand_list = sel
    nm, rp, vp = pl.cand_list[0]
    pl.fields = (rp, vp)
    pl.tbox = [tbox(pl.ref, *rp, pl.fs), tbox(pl.value, *vp, pl.fs)]
    pl.chosen = nm


def rect_hit(a, b, tol=0.15):
    return a[0] + tol < b[2] and b[0] + tol < a[2] and a[1] + tol < b[3] and b[1] + tol < a[3]


def seg_hit(w, r, tol=0.15):
    """axis-parallel wire w = (x1, y1, x2, y2, ...) against the open interior of rect r."""
    x1, y1, x2, y2 = w[:4]
    if x1 == x2:
        return r[0] + tol < x1 < r[2] - tol and min(y1, y2) < r[3] - tol and max(y1, y2) > r[1] + tol
    return r[1] + tol < y1 < r[3] - tol and min(x1, x2) < r[2] - tol and max(x1, x2) > r[0] + tol


def _flip_just(pl, j):
    flip = (pl.angle in (90, 180)) != pl.mirror
    if j == "center": return ""
    return " (justify %s)" % (("right" if j == "left" else "left") if flip else j)


class _Resolver:
    """Chooses, for every symbol, the side its reference and value are written on."""

    def __init__(self, S):
        self.S = S

    def run(self):
        """Greedy first pass, then sweeps in which every part is chosen again against all the others' current text."""
        S = self.S
        for sweep in range(5):
            changed = False
            for pl in S.placed:
                taken = [b for o in S.placed if o is not pl for b in o.tbox]
                best, bc = None, 1e9
                for i, (nm, rp, vp) in enumerate(pl.cand_list):
                    boxes = [tbox(pl.ref, *rp, pl.fs), tbox(pl.value, *vp, pl.fs)]
                    cost = i * 0.05
                    for b in boxes:
                        cost += self.cost(b, pl, taken)
                    if cost < bc: best, bc = (nm, rp, vp, boxes), cost
                nm, rp, vp, boxes = best
                if nm != pl.chosen: changed = True
                pl.fields = (rp, vp); pl.tbox = boxes; pl.cost = bc; pl.chosen = nm
            if not changed: break

    def cost(self, b, me, taken):
        S = self.S
        c = 0.0
        for pl in S.placed:
            if rect_hit(b, pl.bbox, 0.2) and pl is not me: c += 60
            elif pl is me and rect_hit(b, pl.bbox, 0.35): c += 60
        for w in S.wires:
            if seg_hit(w, b, 0.2): c += 40
            elif seg_hit(w, b, -0.6): c += 3                 # not touching, but too close for a clean read
        for bb in S.boxes:
            if rect_hit(b, bb[:4], 0.2): c += 60
        for k, x, y, d, n in S.pwr:
            if rect_hit(b, pwr_box(k, x, y, d, n), 0.2): c += 60
        for t in taken:
            if rect_hit(b, t, 0.2): c += 60
        return c


# ---------------------------------------------------------------------------------------------------------------
# emitting
# ---------------------------------------------------------------------------------------------------------------
def _emit_symbol(S, pl):
    lid = S.lib_key(pl.lib, pl.name)
    comp = S.comps[pl.ref]
    fa = 90 if pl.angle in (90, 270) else 0
    (rx, ry, rj), (vx, vy, vj) = pl.fields
    fs = pl.fs
    props = [f'(property "Reference" {q(pl.ref)} (at {snap_(rx)} {snap_(ry)} {fa}) (effects (font (size {fs} {fs})){_flip_just(pl, rj)}))',
             f'(property "Value" {q(pl.value)} (at {snap_(vx)} {snap_(vy)} {fa}) (effects (font (size {fs} {fs})){_flip_just(pl, vj)}))',
             f'(property "Footprint" {q(comp["footprint"])} (at {pl.x} {pl.y} 0) (effects (font (size 1.27 1.27)) (hide yes)))']
    for k, v in (comp.get("fields") or {}).items():
        props.append(f'(property {q(k)} {q(v)} (at {pl.x} {pl.y} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
    pins = " ".join(f'(pin {q(p)} (uuid {q(uid(S.name, pl.ref, pl.unit, "pin", p))}))'
                    for p in sorted({p["drawn"] for p in symlib.pins(pl.lib, pl.name) if p["unit"] in (0, pl.unit)}))
    su = uid(S.name, "sym", pl.ref, pl.unit)
    return (f'(symbol (lib_id {q(lid)}) (at {pl.x} {pl.y} {pl.angle}){" (mirror y)" if pl.mirror else ""} (unit {pl.unit}) '
            f'(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid {q(su)}) {" ".join(props)} {pins} '
            f'(instances (project {q(S.project)} (path {q("/" + S.root_uuid + "/" + S.uuid)} (reference {q(pl.ref)}) (unit {pl.unit})))))')


def snap_(v):
    return f"{v:.2f}"


def _emit_power(S, k, x, y, d, net, n):
    if k == "gnd" and net == "GND":
        lib, name, val_, ang = "power", "GND", "GND", {"D": 0, "U": 180, "L": 270, "R": 90}[d]
    elif k == "gnd":
        lib, name, val_, ang = "power", "GNDS", net, 0
    else:
        lib, name, val_, ang = "power", "VCC", net, 0
    lid = S.lib_key(lib, name)
    ref = f"#PWR{abs(hash(S.name)) % 90 + 10}{n:03d}"
    if k == "gnd" and net != "GND":
        vis = '(effects (font (size 1.27 1.27)))'
        vat = f"{x} {y + 3.8:.2f}"
    elif k == "gnd":
        vis = '(effects (font (size 1.27 1.27)) (hide yes))'
        vat = f"{x} {y}"
    else:
        vis = '(effects (font (size 1.27 1.27)))'
        vat = f"{x} {y - 3.8:.2f}"
    return (f'(symbol (lib_id {q(lid)}) (at {x} {y} {ang}) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) '
            f'(uuid {q(uid(S.name, "pwr", n))}) '
            f'(property "Reference" {q(ref)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes))) '
            f'(property "Value" {q(val_)} (at {vat} 0) {vis}) '
            f'(pin "1" (uuid {q(uid(S.name, "pwr", n, "pin"))})) '
            f'(instances (project {q(S.project)} (path {q("/" + S.root_uuid + "/" + S.uuid)} (reference {q(ref)}) (unit 1)))))')


# ---------------------------------------------------------------------------------------------------------------
# connectivity re-derived from the drawing, and lint
# ---------------------------------------------------------------------------------------------------------------
class _DSU:
    def __init__(self): self.p = {}

    def f(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]; a = self.p[a]
        return a

    def u(self, a, b): self.p[self.f(a)] = self.f(b)


def _on_seg(pt, w):
    x, y = pt
    x1, y1, x2, y2 = w[:4]
    if x1 == x2: return x == x1 and min(y1, y2) <= y <= max(y1, y2)
    return y == y1 and min(x1, x2) <= x <= max(x1, x2)


def _interior(pt, w):
    return _on_seg(pt, w) and pt not in ((w[0], w[1]), (w[2], w[3]))


def finish_scene(S):
    """Resolve text, add junctions."""
    _Resolver(S).run()
    # junctions: three or more things meet at a point that is an end of something
    pts = {}
    ends = {}
    for w in S.wires:
        for e in ((w[0], w[1]), (w[2], w[3])):
            ends[e] = ends.get(e, 0) + 1
    pins = {}
    for pl in S.placed:
        seen = set()
        for num, (pt, p) in pl.pins.items():
            if p["hidden"] or (pt.x, pt.y) in seen: continue
            seen.add((pt.x, pt.y)); pins[(pt.x, pt.y)] = pins.get((pt.x, pt.y), 0) + 1
    for k, x, y, d, n in S.pwr: pins[(x, y)] = pins.get((x, y), 0) + 1
    cand = set(ends) | set(pins)
    J = set(S.junctions)
    for pt in cand:
        thru = sum(1 for w in S.wires if _interior(pt, w))
        deg = ends.get(pt, 0) + 2 * thru + pins.get(pt, 0)
        if deg >= 3: J.add(pt)
    S.junctions = J


def render_items(S):
    out = list(S.items)
    for x, y in sorted(S.junctions):
        out.append(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid {q(uid(S.name, "j", x, y))}))')
    for x1, y1, x2, y2, net in S.wires:
        out.append(f'(wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default)) '
                   f'(uuid {q(uid(S.name, "w", x1, y1, x2, y2))}))')
    for x, y in S.ncs:
        out.append(f'(no_connect (at {x} {y}) (uuid {q(uid(S.name, "nc", x, y))}))')
    for pl in S.placed: out.append(_emit_symbol(S, pl))
    for i, (k, x, y, d, n) in enumerate(S.pwr): out.append(_emit_power(S, k, x, y, d, n, i + 1))
    return out


TOL_TEXT_WIRE = float(os.environ.get("LINT_TEXT_WIRE", "0.25"))      # negative: demand clearance between text and wires


def lint(S, verbose=True):
    """Overlap and connectivity checks on the finished scene. Returns a list of messages."""
    msg = []
    # ---- boxes ----
    texts = []                                   # (box, what)
    for pl in S.placed:
        texts.append((pl.tbox[0], f"{pl.ref} ref")); texts.append((pl.tbox[1], f"{pl.ref} value"))
    for b in S.boxes: texts.append((b[:4], f"{b[4]} '{b[5]}'"))
    for k, x, y, d, n in S.pwr:
        if k == "rail" or (k == "gnd" and n != "GND"): texts.append((pwr_box(k, x, y, d, n), f"rail {n}"))
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if rect_hit(texts[i][0], texts[j][0], 0.25): msg.append(f"text overlap: {texts[i][1]} / {texts[j][1]} at {tuple(round(v) for v in texts[i][0][:2])}")
    for k, x, y, d, n in S.pwr:                  # a text over a plain ground symbol (the resolver avoids them, a forced position may not)
        if k == "gnd" and n == "GND":
            gb = pwr_box(k, x, y, d, n)
            for b, what in texts:
                if rect_hit(b, gb, 0.25): msg.append(f"text on ground symbol: {what} at {(x, y)}")
    for b, what in texts:
        for pl in S.placed:
            if rect_hit(b, pl.bbox, 0.3) and not what.startswith(pl.ref + " "):
                msg.append(f"text on symbol: {what} over {pl.ref} at {tuple(round(v) for v in b[:2])}")
            elif what.startswith(pl.ref + " ") and rect_hit(b, pl.bbox, 0.3):
                msg.append(f"text on own symbol: {what}")
        own = what.split("'")[1] if what.startswith(("label '", "rail ")) and "'" in what else (what.split()[1] if what.startswith("rail ") else None)
        for w in S.wires:
            if TOL_TEXT_WIRE < 0 and own and (w[4] == own or str(w[4]).endswith("/" + own)): continue      # clearance check ignores a label's own wire
            if seg_hit(w, b, TOL_TEXT_WIRE): msg.append(f"wire through text: {what} at {tuple(round(v) for v in b[:2])} (net {w[4]})")
    # ---- wires against symbols ----
    for w in S.wires:
        for pl in S.placed:
            if seg_hit(w, pl.bbox, 0.2): msg.append(f"wire through symbol {pl.ref}: {w[:4]} net {w[4]}")
        for k, x, y, d, n in S.pwr:
            if seg_hit(w, pwr_box(k, x, y, d, n), 0.2) and not (k == "gnd" and (w[0], w[1]) == (x, y) or (w[2], w[3]) == (x, y)):
                msg.append(f"wire through power symbol at {(x, y)}")
    for i, a in enumerate(S.placed):
        for b in S.placed[i + 1:]:
            if rect_hit(a.bbox, b.bbox, 0.4): msg.append(f"symbols overlap: {a.ref} / {b.ref}")
    # ---- foreign wires touching pins / each other ----
    for pl in S.placed:
        for num, (pt, p) in pl.pins.items():
            if p["hidden"]: continue
            for w in S.wires:
                if _on_seg((pt.x, pt.y), w) and w[4] and pt.net and w[4] != pt.net:
                    msg.append(f"wire of net {w[4]} touches pin {pl.ref}.{num} of net {pt.net}")
    for i, a in enumerate(S.wires):
        for b in S.wires[i + 1:]:
            if a[4] == b[4] or a[4] is None or b[4] is None: continue
            ea = [(a[0], a[1]), (a[2], a[3])]; eb = [(b[0], b[1]), (b[2], b[3])]
            if any(_on_seg(e, b) for e in ea) or any(_on_seg(e, a) for e in eb):
                msg.append(f"wires of different nets touch: {a[4]} / {b[4]} near {ea[0]}")
    # ---- connectivity from geometry ----
    d = _DSU()
    W = S.wires
    for k in range(len(W)): d.f(("w", k))
    for k, w in enumerate(W):
        for k2 in range(k + 1, len(W)):
            w2 = W[k2]
            e1 = [(w[0], w[1]), (w[2], w[3])]; e2 = [(w2[0], w2[1]), (w2[2], w2[3])]
            if any(_on_seg(e, w2) for e in e1) or any(_on_seg(e, w) for e in e2): d.u(("w", k), ("w", k2))
    for jx in S.junctions:
        on = [k for k, w in enumerate(W) if _on_seg(jx, w)]
        for k in on[1:]: d.u(("w", on[0]), ("w", k))
    terms = []                                   # (key, xy, name)
    for pl in S.placed:
        for num, (pt, p) in pl.pins.items():
            if not p["hidden"]: terms.append(((pl.ref, num), (pt.x, pt.y), None))
    for i, (k, x, y, dd, n) in enumerate(S.pwr):
        terms.append((("pwr", i), (x, y), "GND" if (k == "gnd" and n == "GND") else n.lstrip("/")))
    for i, b in enumerate(S.boxes):
        if b[4] == "label": terms.append((("lab", i), b[6], b[5]))
    at = {}
    for key, xy, name in terms:
        d.f(key)
        at.setdefault(xy, []).append(key)
        for k, w in enumerate(W):
            if _on_seg(xy, w): d.u(key, ("w", k))
    for xy, ks in at.items():
        for k in ks[1:]: d.u(ks[0], k)
    byname = {}
    for key, xy, name in terms:
        if name: byname.setdefault(name, []).append(key)
    for name, ks in byname.items():
        for k in ks[1:]: d.u(ks[0], k)
    pinkeys = [(key, S.net_of(*key)) for key, xy, name in terms if len(key) == 2 and key[0] != "pwr" and key[0] != "lab"]
    exp, got = {}, {}
    for key, net in pinkeys:
        got[key] = d.f(key)
        if net: exp.setdefault(net, set()).add(key)
    for net, ks in exp.items():
        gs = {got[k] for k in ks}
        if len(gs) > 1:
            msg.append(f"net {net} is drawn as {len(gs)} separate pieces: " +
                       " | ".join(" ".join(f"{r}.{p}" for r, p in sorted(k for k in ks if got[k] == g)) for g in gs))
    pieces = {}
    for key, net in pinkeys: pieces.setdefault(got[key], set()).add(net)
    for g, nets in pieces.items():
        nets.discard(None)
        if len(nets) > 1: msg.append(f"pieces of different nets are joined: {sorted(nets)}")
    # ---- every wire end must hold a pin, a power symbol, a label or another wire (KiCad ERC: unconnected wire endpoint)
    held = {xy for key, xy, name in terms}
    for k, w in enumerate(W):
        for e in ((w[0], w[1]), (w[2], w[3])):
            if e not in held and not any(k2 != k and _on_seg(e, w2) for k2, w2 in enumerate(W)):
                msg.append(f"dangling wire end at {e} (net {w[4]})")
    return msg


# ---------------------------------------------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------------------------------------------
TB_W, TB_H = 112.0, 34.0        # the title block KiCad draws in the lower right corner


def _all_rects(S):
    r = []
    for pl in S.placed:
        r.append(pl.bbox); r += pl.tbox
    for w in S.wires: r.append((min(w[0], w[2]), min(w[1], w[3]), max(w[0], w[2]), max(w[1], w[3])))
    for b in S.boxes: r.append(b[:4])
    for k, x, y, d, n in S.pwr: r.append(pwr_box(k, x, y, d, n))
    r += S.frames
    return r


def fit_page(S, margin=14.0, minw=160.0, minh=110.0, frame_margin=18.0):
    """Page size: room for everything drawn, with the dashed section frames (which stand 3 mm out from their contents)
    kept clear of the sheet border, and the title block kept clear of every drawn thing."""
    b = S.bbox()
    fr = [f[2] for f in S.frames], [f[3] for f in S.frames]
    W = max(minw, math.ceil((b[2] + margin) / 5) * 5, math.ceil((max(fr[0], default=0) + frame_margin) / 5) * 5)
    H = max(minh, math.ceil((b[3] + margin) / 5) * 5, math.ceil((max(fr[1], default=0) + frame_margin) / 5) * 5)
    rects = _all_rects(S)
    while True:
        tb = (W - 10 - TB_W, H - 10 - TB_H, W - 10, H - 10)
        if not any(rect_hit(r, tb, 0.0) for r in rects): break
        H += 5
    return W, H


def write_scene(S, path, w, h):
    body = render_items(S)                      # collects the library symbols as it goes
    out = [f'(kicad_sch (version {VERSION}) (generator "p2p_draw") (generator_version "10.0") (uuid {q(S.uuid)}) '
           f'(paper "User" {w:g} {h:g}) (title_block (title {q(S.title)}) (comment 1 "Generated from code. Do not edit: change the block source and rebuild."))',
           "(lib_symbols " + "\n".join(S.libs.values()) + ")"]
    out += body
    out.append("(embedded_fonts no))")
    open(path, "w").write("\n".join(out) + "\n")
