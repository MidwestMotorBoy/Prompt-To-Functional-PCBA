"""A small drawing kit for hand-laid-out sheets: place a part, ask where its pins are, run wires between them.

A layout is a function  layout(S)  written in the block's own terms (references and pin names). The kit does the
bookkeeping a person does with a pencil: which way a two-pin part stands, where its pin ends are, which net a label
names. Nothing here decides connectivity; make.sh still proves the drawing equals the circuit.

Coordinates are millimetres on the sheet, y down. Parts are placed by the position of a named pin end, so a layout
reads as "this cap hangs from this wire".
"""
import symlib

G = 1.27
TW = 1.12                      # mm per character of 1.27 mm text

def snap(v):
    return round(round(v / G) * G, 4)

def rot(x, y, a):
    a = a % 360
    if a == 0: xr, yr = x, y
    elif a == 90: xr, yr = -y, x
    elif a == 180: xr, yr = -x, -y
    else: xr, yr = y, -x
    return xr, -yr


class Placed:
    """A placed symbol: where each pin ends. Look pins up by name or by pad number."""
    def __init__(self, ref, x, y, angle, mirror, unit, pins):
        self.ref, self.x, self.y, self.angle, self.unit = ref, x, y, angle, unit
        self.byname, self.bynum, self.dir = {}, {}, {}
        for p in pins:
            if p["unit"] not in (0, unit): continue
            dx, dy = rot(-p["x"] if mirror else p["x"], p["y"], angle)
            pt = (snap(x + dx), snap(y + dy))
            self.byname.setdefault(p["name"], pt); self.bynum.setdefault(p["num"], pt)
            self.dir.setdefault(p["num"], p["angle"])

    def __call__(self, key):
        key = str(key)
        if key in self.bynum: return self.bynum[key]
        if key in self.byname: return self.byname[key]
        raise KeyError(f"{self.ref} has no pin '{key}': {sorted(self.byname)} {sorted(self.bynum)}")


class Scene:
    def __init__(self, sheet, comps, pinnet, glob, ncset, block, block_refs):
        self.sh, self.comps, self.pinnet, self.glob, self.ncset = sheet, comps, pinnet, glob, ncset
        self.block, self.refs = block, set(block_refs)
        self.done = set()
        self.nets = {n for (_, _), n in pinnet.items()}
        self.pl = {}

    # ---------- nets ----------
    def netname(self, n):
        """Full net name as the netlist knows it, from a short name as written on the sheet."""
        n = getattr(self, "alias", {}).get(n, n)
        for c in (n, f"{self.block}/{n}", "/" + n):
            if c in self.nets: return c
        raise KeyError(f"no net '{n}' in block {self.block}")

    def disp(self, full):
        return full.lstrip("/") if full in self.glob else full.split("/")[-1]

    def net_of(self, ref, pin):
        p = self.pl[ref]
        num = pin if str(pin) in p.bynum else None
        if num is None:
            for q in symlib.pins(*self.comps[ref]["lib"].split(":")):
                if q["name"] == str(pin): num = q["num"]; break
        return self.pinnet.get((ref, num))

    # ---------- primitives ----------
    def w(self, *pts):
        """Wire through the points. Consecutive points must share x or y."""
        pts = [(snap(p[0]), snap(p[1])) for p in pts]
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) > 0.01 and abs(a[1] - b[1]) > 0.01:
                raise ValueError(f"diagonal wire {a} -> {b}")
            self.sh.wire(a[0], a[1], b[0], b[1])

    def _pin(self, x, y):
        self.sh.pinpts.add((snap(x), snap(y)))

    def gnd(self, x, y):
        self._pin(x, y); self.sh.gnd(x, y, 0)

    def gside(self, x, y, d):
        """Ground symbol lying on its side at the end of a stub that runs in direction d (L or R)."""
        self._pin(x, y); self.sh.gnd(x, y, 270 if d == "L" else 90)

    def gbus(self, pins, d="L", off=3.81, at=None):
        """Several pins of one side tied together and to one sideways ground. pins: pin points; d: side of the part."""
        sg = -1 if d == "L" else 1
        xb = pins[0][0] + sg * off
        for p in pins: self.w(p, (xb, p[1]))
        ys = [p[1] for p in pins]
        if len(pins) > 1: self.w((xb, min(ys)), (xb, max(ys)))
        ym = at if at is not None else pins[len(pins) // 2][1]
        self.w((xb, ym), (xb + sg * 2.54, ym)); self.gside(xb + sg * 2.54, ym, d)

    def hangs_stair(self, pt, d, items, step=10.16, gap=2.54):
        """Parts hanging to ground from one pin's line, farthest first is not needed: items = [(ref, net or None)]..."""
        raise NotImplementedError

    def gnda(self, x, y, show=False):
        """Ground symbol with a bar: CELL_1N, the Kelvin ground at the cell-1 negative tab."""
        self._pin(x, y); self.sh.power("GNDA", "CELL_1N", x, y, dy=4.6, show=show)

    def nc(self, pt):
        self.sh.nc(*pt)

    def label(self, net, x, y, d="R"):
        """Net label whose connection point is (x, y); text runs away in direction d (R, L, U or D)."""
        full = self.netname(net)
        self.sh.label(self.disp(full), x, y, {"R": 0, "L": 180, "U": 90, "D": 270}[d], full in self.glob)

    def stub(self, pt, d, net, n=2.54):
        """A short wire out of pt in direction d, ending in the label of net."""
        dx, dy = {"R": (1, 0), "L": (-1, 0), "U": (0, -1), "D": (0, 1)}[d]
        e = (pt[0] + dx * n, pt[1] + dy * n)
        self.w(pt, e); self.label(net, e[0], e[1], d)
        return e

    def pwr(self, kind, x, y):
        """Supply symbol: kind '3V3' or 'PACK_P'."""
        lib = {"3V3": "+3V3", "PACK_P": "+12V"}[kind]
        self._pin(x, y); self.sh.power(lib, kind, x, y)

    def text(self, s, x, y, size=1.27):
        self.sh.text(s, x, y, size, snapped=False)

    def title(self, s, x, y):
        self.sh.text(s, x, y, 2.0, snapped=False)

    def note(self, lines, x, y, size=1.27):
        for i, l in enumerate(lines): self.sh.text(l, x, y + i * (size + 1.1), size, snapped=False)

    def box(self, x1, y1, x2, y2): self.sh.box(x1, y1, x2, y2)

    # ---------- parts ----------
    def _sym(self, ref, x, y, angle, mirror, unit, ref_at, val_at, hide_val=False):
        lib, name = self.comps[ref]["lib"].split(":")
        c = self.comps[ref]
        self.sh.symbol(lib, name, ref, c["value"], x, y, angle, unit=unit, footprint=c["footprint"], fields=c["fields"],
                       ref_at=ref_at, val_at=val_at, mirror=mirror, hide_val=hide_val)
        self.done.add(ref)
        p = Placed(ref, snap(x), snap(y), angle, mirror, unit, symlib.pins(lib, name))
        self.pl[ref] = p
        self.sh.pinpts.update(p.bynum.values())
        return p

    def ic(self, ref, x, y, unit=1, mirror=False, ref_at=None, val_at=None):
        """A multi-pin part with its origin at (x, y). Reference and value go above the body unless told otherwise."""
        lib, name = self.comps[ref]["lib"].split(":")
        ps = [p for p in symlib.pins(lib, name) if p["unit"] in (0, unit)]
        top = max(p["y"] for p in ps if p["angle"] in (0, 180)) if any(p["angle"] in (0, 180) for p in ps) else 0
        tops = [p for p in ps if p["angle"] == 270]
        body_top = max([top + 2.54] + ([max(p["y"] - p["length"] for p in tops)] if tops else []))
        left = min(p["x"] for p in ps) + (max(p["length"] for p in ps if p["angle"] == 0) if any(p["angle"] == 0 for p in ps) else 0)
        if mirror: left = -max(p["x"] for p in ps) + 2.54
        ra = ref_at or (x + left, y - body_top - 3.4)
        va = val_at or (x + left, y - body_top - 1.3)
        return self._sym(ref, x, y, 0, mirror, unit, ra, va)

    def two(self, ref, x, y, axis="v", first=None, text="r", end="first", val=True, ra_=None, va_=None):
        """A two-pad part. (x, y) is the end of its pad `first` (pad number or net name of that end, default pad 1);
        axis 'v': that end is on top, the other below; 'h': that end is on the left, the other on the right.
        text: 'r' right of the part, 'l' left, 'a' above, 'b' below. Returns the placed part: .a = first end, .b = other end."""
        lib, name = self.comps[ref]["lib"].split(":")
        pins = symlib.pins(lib, name)
        pp = {}
        for p in pins: pp.setdefault(p["num"], p)
        nums = sorted(pp)
        if first is None: first = nums[0]
        if first not in pp:                                       # a net name: the pad whose net it is
            for n in nums:
                nn = self.pinnet.get((ref, n))
                if nn is not None and (nn == first or self.disp(nn) == first or nn == self.netname(first)): first = n; break
            else: raise KeyError(f"{ref}: no pad on net {first}")
        other = [n for n in nums if n != first][0]
        for a in (0, 90, 180, 270):
            fx, fy = rot(pp[first]["x"], pp[first]["y"], a); ox, oy = rot(pp[other]["x"], pp[other]["y"], a)
            if axis == "v" and abs(fx) < .01 and abs(ox) < .01 and fy < oy: break
            if axis == "h" and abs(fy) < .01 and abs(oy) < .01 and fx < ox: break
        else: raise ValueError(f"{ref}: cannot orient")
        cx, cy = snap(x - fx), snap(y - fy)
        L = abs(pp[first]["y"] - pp[other]["y"]) if axis == "v" else abs(pp[first]["x"] - pp[other]["x"])
        v, r = self.comps[ref]["value"], ref
        if axis == "v":
            if text == "r": ra, va = (cx + 2.54, cy - 1.4), (cx + 2.54, cy + 1.2)
            else: ra, va = (cx - 2.54 - len(r) * TW, cy - 1.4), (cx - 2.54 - len(v) * TW, cy + 1.2)
        else:
            if text == "a": ra, va = (cx - len(r) * TW / 2, cy - 5.0), (cx - len(v) * TW / 2, cy - 3.2)
            else: ra, va = (cx - len(r) * TW / 2, cy + 3.2), (cx - len(v) * TW / 2, cy + 5.0)
        p = self._sym(ref, cx, cy, a, False, 1, ra_ or ra, va_ or va, hide_val=not val)
        p.a, p.b = p(first), p(other)
        p.c = (cx, cy)
        return p

    def hang(self, refs, x0, y, pitch=12.7, to="GND", rail=None, text="r", first=None):
        """Parts standing under a horizontal wire at height y, one every `pitch` from x0, each ending on ground
        (or on a label of the net `to`). The wire along y is drawn from x0 to the last one. Returns the x of each part."""
        xs = []
        for i, r in enumerate(refs):
            x = snap(x0 + i * pitch)
            p = self.two(r, x, y, "v", first=first or rail, text=text)
            self.end(p.b, to)
            xs.append(x)
        if len(xs) > 1: self.w((xs[0], y), (xs[-1], y))
        return xs

    def end(self, pt, to="GND", d="D"):
        if to == "GND": self.gnd(*pt)
        elif to is None: pass
        else: self.stub(pt, d, to)

    def pad(self, ref, x, y, down=False, text="r"):
        """A one-pin test point or wire pad whose connection point is (x, y); the round pad sits above it, or below if down."""
        c = self.comps[ref]
        r, v = ref, c["value"]
        up = -1 if not down else 1
        if text == "r": ra, va = (x + 2.54, y + up * 4.6), (x + 2.54, y + up * 2.4)
        else: ra, va = (x - 2.54 - len(r) * TW, y + up * 4.6), (x - 2.54 - len(v) * TW, y + up * 2.4)
        if down: ra, va = (ra[0], y + 2.4), (va[0], y + 4.6)
        p = self._sym(ref, x, y, 180 if down else 0, False, 1, ra, va)
        return p

    def done_all(self):
        return self.refs - self.done
