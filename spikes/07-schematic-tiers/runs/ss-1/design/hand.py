"""Hand layout helper: place parts on a grid and draw their wires, labels and grounds by pin name, the way a person
draws a small circuit. Coordinates are in units of 2.54 mm, relative to the origin of the section. Every function that
draws takes pins as "REF.PIN" strings or (x, y) points; wires are polylines and a corner is added when two points are
not aligned. Junctions are added where a wire ends on another wire. Nothing here decides connectivity: make.sh proves
the result equals the circuit."""
import symlib
from draw_util import rot, snap, G

U = 2.54
CH = 1.0

class Hand:
    def __init__(self, sheet, comps, pinnet, ncset, glob, short, ox, oy):
        self.sh, self.comps, self.pinnet, self.ncset, self.glob, self.short = sheet, comps, pinnet, ncset, glob, short
        self.ox, self.oy = ox, oy
        self.pos, self.segs, self.touch, self.bbox = {}, [], set(), [1e9, 1e9, -1e9, -1e9]
        self.placed, self.warn = set(), []

    # ---- geometry ----
    def xy(self, x, y):
        return snap(self.ox + x * U), snap(self.oy + y * U)

    def _grow(self, x, y, w=0.0):
        b = self.bbox
        b[0] = min(b[0], x); b[1] = min(b[1], y); b[2] = max(b[2], x + w); b[3] = max(b[3], y)

    def pt(self, p, prev=None):
        if isinstance(p, str):
            return self.pin(*p.split("."))
        x, y = p
        px, py = prev if prev else (None, None)
        if x is None: return (px, snap(self.oy + y * U))
        if y is None: return (snap(self.ox + x * U), py)
        return self.xy(x, y)

    def pin(self, ref, num):
        x, y, a, mir, unit = self.pos[ref]
        lib, name = self.comps[ref]["lib"].split(":")
        for p in symlib.pins(lib, name):
            if p["num"] == num and p["unit"] in (0, unit):
                px = -p["x"] if mir else p["x"]
                dx, dy = rot(px, p["y"], a)
                return snap(x + dx), snap(y + dy)
        raise KeyError(f"{ref}.{num}")

    # ---- parts ----
    def put(self, ref, x, y, rot_=0, mirror=False, unit=1, lab="r", ref_at=None, val_at=None, just=None, text=True):
        """lab: where the reference and value go: r, l (beside a vertical part), t (above a flat one), b (below)."""
        c = self.comps[ref]
        lib, name = c["lib"].split(":")
        X, Y = self.xy(x, y)
        self.pos[ref] = (X, Y, rot_, mirror, unit)
        self.placed.add(ref)
        horiz = rot_ in (90, 270)
        ra = va = None
        if ref_at: ra = (X + ref_at[0] * U, Y + ref_at[1] * U); va = (X + val_at[0] * U, Y + val_at[1] * U)
        elif horiz:
            dy = -5.0 if lab == "t" else 3.0
            ra, va = (X - 3.81, Y + dy), (X - 3.81, Y + dy + 2.0)
        elif lab == "l":
            ra, va, just = (X - 2.54, Y - 1.27), (X - 2.54, Y + 1.27), "right"
        else:
            ra, va = (X + 2.54, Y - 1.27), (X + 2.54, Y + 1.27)
        self.sh.symbol(lib, name, ref, c["value"], X, Y, rot_, unit=unit, footprint=c["footprint"], fields=c["fields"],
                       ref_at=ra, val_at=va, mirror=mirror, just=just, hide_ref=not text, hide_val=not text)
        n = len(c["value"]) + len(ref) + 1
        self._grow(X - 4, Y - 6); self._grow(X + 4, Y + 6, 3 + n * 1.2)
        return X, Y

    # ---- wires and labels ----
    def w(self, *pts):
        res = []
        for p in pts:
            q = self.pt(p, res[-1] if res else None)
            if res and res[-1][0] != q[0] and res[-1][1] != q[1]:
                res.append((q[0], res[-1][1]))
            if not res or res[-1] != q: res.append(q)
        for a, b in zip(res, res[1:]):
            self.sh.wire(a[0], a[1], b[0], b[1])
            self.segs.append((a, b)); self._grow(*a); self._grow(*b)
        for p in res: self.touch.add(p)
        return res[-1]

    def net_at(self, p):
        if isinstance(p, str):
            ref, num = p.split(".")
            return self.pinnet.get((ref, num)), (ref, num) in self.ncset
        return None, False

    def lab(self, p, side="R", name=None, mm=False):
        """The net name (or a ground, or a no-connect mark) at a pin or point, text running away on `side`."""
        net, is_nc = self.net_at(p)
        x, y = self.pt(p) if not mm else p
        self.touch.add((x, y))
        if name is None:
            if is_nc or net is None: return self.sh.nc(x, y)
            name = net
        if name == "GND":
            return self.sh.gnd(x, y, {"L": 270, "R": 90, "U": 180, "D": 0}[side])
        ang = {"L": 180, "R": 0, "U": 90, "D": 270}[side]
        self.sh.label(self.short(name), x, y, ang, name in self.glob)
        self._grow(x - 2, y - 2, 2 + len(self.short(name)) * CH)
        if side == "L": self._grow(x - len(self.short(name)) * CH - 2, y)

    def net(self, p):
        return self.net_at(p)[0]

    def stub(self, p, side="R", n=1, name=None):
        """A short wire out of a pin, then the net name (or a ground) at its end: keeps the name clear of the pin number."""
        x, y = self.pin(*p.split("."))
        dx, dy = {"L": (-1, 0), "R": (1, 0), "U": (0, -1), "D": (0, 1)}[side]
        q = (snap(x + dx * n * U), snap(y + dy * n * U))
        self.sh.wire(x, y, *q); self.segs.append(((x, y), q)); self.touch.update([(x, y), q])
        self.lab(q, side, name or self.net(p), mm=True)

    def gnd(self, p, side="D"):
        self.lab(p, side, "GND")

    def note(self, s, x, y, size=1.27):
        X, Y = self.xy(x, y)
        self.sh.text(s, X, Y, size)
        self._grow(X, Y - 3, len(s) * size * 0.9)

    def title(self, s, x, y):
        self.note(s, x, y, 1.0)

    # ---- end ----
    def finish(self):
        pts = {}
        for a, b in self.segs:
            pts.setdefault(a, [0, 0]); pts.setdefault(b, [0, 0])
            pts[a][0] += 1; pts[b][0] += 1
        pinpts = {}
        for ref in self.placed:
            lib, name = self.comps[ref]["lib"].split(":")
            for p in symlib.pins(lib, name):
                if p["unit"] in (0, self.pos[ref][4]):
                    q = self.pin(ref, p["num"]); pinpts[q] = pinpts.get(q, 0) + (0 if q in {x for x in pinpts} and False else 1)
        for q in pinpts: pts.setdefault(q, [0, 0])
        for p in list(pts):
            for a, b in self.segs:
                if p in (a, b): continue
                if a[0] == b[0] == p[0] and min(a[1], b[1]) < p[1] < max(a[1], b[1]): pts[p][1] += 1
                if a[1] == b[1] == p[1] and min(a[0], b[0]) < p[0] < max(a[0], b[0]): pts[p][1] += 1
        for p, (e, i) in pts.items():
            npin = 1 if p in pinpts else 0
            if e + npin >= 3 or (e + npin >= 1 and i >= 1): self.sh.junction(*p)
        # every pad of every placed part must end at a wire, label, ground or no-connect
        for ref in self.placed:
            lib, name = self.comps[ref]["lib"].split(":")
            for p in symlib.pins(lib, name):
                if p["unit"] not in (0, self.pos[ref][4]): continue
                if (ref, p["num"]) in self.ncset: continue
                if self.pin(ref, p["num"]) not in self.touch: self.warn.append(f"{ref}.{p['num']} not connected in drawing")
        b = self.bbox
        return (b[2] - self.ox + 4, b[3] - self.oy + 6) if b[2] > -1e8 else (0, 0)
