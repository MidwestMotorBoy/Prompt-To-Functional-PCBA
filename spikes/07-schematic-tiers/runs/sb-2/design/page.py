"""Hand-layout helpers: place parts at explicit coordinates and wire pin to pin, so a sheet can be laid out the way a
person draws it (power path left to right, supplies up, ground down, support parts at the pin they serve).
The netlist is still the truth: make.sh proves the drawing joins exactly the pins the code joins."""
import symlib

G = 1.27
CH = 1.0
SIDE = {0: "L", 180: "R", 90: "D", 270: "U"}


def snap(v):
    return round(round(v / G) * G, 4)


def rot(x, y, a):
    a = a % 360
    if a == 0: xr, yr = x, y
    elif a == 90: xr, yr = -y, x
    elif a == 180: xr, yr = -x, -y
    else: xr, yr = y, -x
    return xr, -yr


class Page:
    def __init__(self, sheet, comps, nets, nc, glob, refs, cons):
        self.S, self.c, self.glob, self.refs, self.cons = sheet, comps, glob, list(refs), cons
        self.pinnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
        self.nc = {tuple(x) for x in nc}
        self.pos = {}          # (ref, pad) -> (x, y, side)
        self.used = set()
        self.placed = set()
        self.names = {}        # ref -> {pin name: [pads]}
        self.pins = {}

    # ---- names -------------------------------------------------------------------------------------------------
    def short(self, n):
        return n.lstrip("/") if n in self.glob else n.split("/")[-1]

    def net(self, ref, key):
        return self.pinnet.get((ref, self._pad(ref, key)))

    def _pins(self, ref):
        if ref not in self.pins:
            lib, name = self.c[ref]["lib"].split(":")
            self.pins[ref] = symlib.pins(lib, name)
        return self.pins[ref]

    def _pad(self, ref, key):
        key = str(key)
        ps = self._pins(ref)
        for p in ps:
            if p["num"] == key: return key
        for p in ps:
            if p["name"] == key: return p["num"]
        raise KeyError(f"{ref} has no pin {key}")

    def P(self, ref, key):
        """(x, y) of a pin tip, by pad number or pin name."""
        x, y, _ = self.pos[(ref, self._pad(ref, key))]
        return x, y

    def side(self, ref, key):
        return self.pos[(ref, self._pad(ref, key))][2]

    def use(self, ref, key):
        pad = self._pad(ref, key)
        x, y, _ = self.pos[(ref, pad)]
        for (r, p), (x2, y2, _) in self.pos.items():
            if r == ref and (x2, y2) == (x, y) and self.pinnet.get((r, p)) == self.pinnet.get((ref, pad)):
                self.used.add((r, p))

    # ---- placing -----------------------------------------------------------------------------------------------
    def ic(self, ref, x, y, unit=1, mirror=False, ref_at=None, val_at=None, hide_text=False):
        """Place a multi-pin part with its symbol origin at (x, y). Pin tips are then found with P()."""
        c = self.c[ref]
        lib, name = c["lib"].split(":")
        x, y = snap(x), snap(y)
        ps = [p for p in self._pins(ref) if p["unit"] in (0, unit)]
        for p in ps:
            px = snap(x + (-p["x"] if mirror else p["x"])); py = snap(y - p["y"])
            side = SIDE[p["angle"]]
            if mirror and side in "LR": side = "R" if side == "L" else "L"
            self.pos[(ref, p["num"])] = (px, py, side)
        top = min(snap(y - p["y"]) for p in ps)
        xs = [snap(x + (-p["x"] if mirror else p["x"])) for p in ps]
        has_top = any(SIDE[p["angle"]] == "U" for p in ps)
        left = min(xs)
        rt = ref_at or (left + 1.27, top - (11.0 if has_top else 8.6))
        vt = val_at or (rt[0], rt[1] + 2.2)
        self.S.symbol(lib, name, ref, c["value"], x, y, 0, unit=unit, footprint=c["footprint"], fields=c["fields"],
                      ref_at=rt, val_at=vt, mirror=mirror, just="left")
        self.last_text = (rt, vt)
        self.placed.add(ref)

    def p2(self, ref, x, y, o, first=None, tpos="above", tdx=2.54, tleft=False):
        """Two-pad part. (x, y) is where its first end sits. o = 'v': first end on top, part hangs down (7.62 long).
        o = 'h': first end on the left, part runs right. first: net (or pad number) of the first end.
        Returns ((x1, y1), (x2, y2))."""
        c = self.c[ref]
        lib, name = c["lib"].split(":")
        pp = {}
        for p in self._pins(ref): pp.setdefault(p["num"], p)
        nums = sorted(pp)
        if len(nums) == 1:
            return self.p1(ref, x, y, o)
        e = [self.pinnet.get((ref, n)) for n in nums]
        if first is None or first == e[0] or first == nums[0] or (e[0] and self.short(e[0]) == first): a_, b_ = nums[0], nums[1]
        else: a_, b_ = nums[1], nums[0]
        for ang in (0, 90, 180, 270):
            ux, uy = rot(pp[a_]["x"], pp[a_]["y"], ang); dx, dy = rot(pp[b_]["x"], pp[b_]["y"], ang)
            if o == "v" and abs(ux) < .01 and abs(dx) < .01 and uy < dy: break
            if o == "h" and abs(uy) < .01 and abs(dy) < .01 and ux < dx: break
        x, y = snap(x), snap(y)
        ox, oy = snap(x - ux), snap(y - uy)
        if o == "v":
            rt, vt, j = (x + tdx, y + 2.54), (x + tdx, y + 5.08), "left"
            if tleft: rt, vt, j = (x - tdx, y + 2.54), (x - tdx, y + 5.08), "right"
        else:
            j = "center"
            if tpos == "above": rt, vt = (x + 3.81, y - 5.3), (x + 3.81, y - 3.8)
            elif tpos == "below": rt, vt = (x + 3.81, y + 3.8), (x + 3.81, y + 5.3)
            else: rt, vt = (x + 3.81, y - 3.3), (x + 3.81, y + 3.3)
        if ang in (90, 180) and j in ("left", "right"): j = "right" if j == "left" else "left"   # KiCad mirrors justification on rotated parts
        self.S.symbol(lib, name, ref, c["value"], ox, oy, ang, footprint=c["footprint"], fields=c["fields"],
                      ref_at=rt, val_at=vt, just="" if j == "center" else j)
        A = (snap(ox + ux), snap(oy + uy)); B = (snap(ox + dx), snap(oy + dy))
        sa, sb = ("U", "D") if o == "v" else ("L", "R")
        self.pos[(ref, a_)] = (*A, sa); self.pos[(ref, b_)] = (*B, sb)
        self.placed.add(ref)
        self.used.add((ref, a_)); self.used.add((ref, b_))
        self.far = self.pinnet.get((ref, b_))
        return A, B

    def p1(self, ref, x, y, flip=False, tl=False):
        """One-pad part (test point, wire pad): pin tip at (x, y). A test point stands above the tip (flip: hangs below it);
        a side-entry pad (Conn_01x01) lies to the right of the tip. tl: text to the left."""
        c = self.c[ref]
        lib, name = c["lib"].split(":")
        p = self._pins(ref)[0]
        x, y = snap(x), snap(y)
        side = SIDE[p["angle"]]
        ang = 0
        if flip and side in "UD": ang = 180
        ox, oy = x, y
        if ang == 0: ox, oy = x - p["x"], y + p["y"]
        sd = side if ang == 0 else ("U" if side == "D" else "D")
        if sd in "UD":
            ty = (y + 2.0, y + 4.5) if flip else (y - 4.5, y - 2.0)
        else:
            ty = (y - 2.5, y + 2.5) if False else (y - 4.5, y - 2.0)
        if tl: rt, vt, j = (x - 2.54, ty[0]), (x - 2.54, ty[1]), "right"
        else: rt, vt, j = (x + 2.54, ty[0]), (x + 2.54, ty[1]), "left"
        if ang in (90, 180): j = "right" if j == "left" else "left"
        self.S.symbol(lib, name, ref, c["value"], ox, oy, ang, footprint=c["footprint"], fields=c["fields"],
                      ref_at=rt, val_at=vt, just=j)
        self.pos[(ref, p["num"])] = (x, y, sd)
        self.placed.add(ref); self.used.add((ref, p["num"]))
        return (x, y), (x, y)

    # ---- wiring ------------------------------------------------------------------------------------------------
    def w(self, *pts):
        """Polyline through points; points may be (x, y) or a (ref, pin) pair of strings."""
        for p in pts:
            if isinstance(p[0], str): self.use(*p)
        pts = [self.P(*p) if isinstance(p[0], str) else p for p in pts]
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) > .01 and abs(a[1] - b[1]) > .01:
                self.S.wire(a[0], a[1], b[0], a[1]); self.S.wire(b[0], a[1], b[0], b[1])
            else:
                self.S.wire(a[0], a[1], b[0], b[1])
        for p in pts:
            pass
        return pts[-1]

    def j(self, x, y):
        self.S.junction(x, y)

    def lab(self, net, x, y, d="R", glob=None):
        """Net label at (x, y); text extends in direction d (R, L, U, D)."""
        ang = {"R": 0, "L": 180, "U": 90, "D": 270}[d]
        self.S.label(self.short(net), x, y, ang, net in self.glob)

    def gnd(self, x, y, d="D"):
        """Ground symbol at (x, y); d is the direction it points away from the wire (D: wire arrives from above)."""
        self.S.gnd(x, y, {"D": 0, "U": 180, "R": 90, "L": 270}[d])

    def stub(self, x, y, d, net, n=2.54, ld=None):
        """Wire stub of length n away from (x, y) in direction d ending in a label (or ground)."""
        dx, dy = {"R": (n, 0), "L": (-n, 0), "U": (0, -n), "D": (0, n)}[d]
        self.S.wire(x, y, x + dx, y + dy)
        if net == "GND": self.gnd(x + dx, y + dy, d)
        else: self.lab(net, x + dx, y + dy, ld or d)

    def tag(self, ref, key, n=2.54, net="auto"):
        """Finish a pin on its own: ground symbol, no-connect cross or a short stub with the net name."""
        pad = self._pad(ref, key)
        x, y, side = self.pos[(ref, pad)]
        nt = self.pinnet.get((ref, pad)) if net == "auto" else net
        self.use(ref, key)
        if (ref, pad) in self.nc or nt is None:
            return self.S.nc(x, y)
        if nt == "GND" and side == "D":
            return self.gnd(x, y, "D")
        self.stub(x, y, side, nt, n)

    def tag_all(self, ref, name):
        """Finish every pin of `ref` that carries this pin name (e.g. several NC pins)."""
        for q in self._pins(ref):
            if q["name"] == name: self.tag(ref, q["num"])

    def text(self, s, x, y, size=1.27):
        self.S.text(s, x, y, size)

    def finish(self):
        """Every pin of every part of the block that no wire used gets a label, ground or no-connect, so nothing is left open."""
        missing = [r for r in self.refs if r not in self.placed]
        if missing: print("NOT PLACED:", sorted(missing))
        left = []
        for r in self.refs:
            if r not in self.placed: continue
            done = set()
            for (rr, pad), (x, y, side) in list(self.pos.items()):
                if rr != r or (rr, pad) in self.used: continue
                if (x, y) in done: continue
                done.add((x, y))
                left.append((r, pad, self.pinnet.get((r, pad))))
                self.tag(r, pad)
        if left: print("auto-tagged pins:", ", ".join(f"{r}.{p}" for r, p, _ in left))


class Offset:
    """A sheet seen from a section's own origin: every coordinate is shifted by (dx, dy)."""
    def __init__(self, sheet, dx, dy):
        self.S, self.dx, self.dy = sheet, dx, dy
        self.name, self.title = sheet.name, sheet.title

    def __getattr__(self, k): return getattr(self.S, k)
    def symbol(self, lib, name, ref, value, x, y, angle=0, ref_at=None, val_at=None, **kw):
        sh = lambda p: None if p is None else (p[0] + self.dx, p[1] + self.dy)
        return self.S.symbol(lib, name, ref, value, x + self.dx, y + self.dy, angle, ref_at=sh(ref_at), val_at=sh(val_at), **kw)
    def wire(self, x1, y1, x2, y2): return self.S.wire(x1 + self.dx, y1 + self.dy, x2 + self.dx, y2 + self.dy)
    def junction(self, x, y): return self.S.junction(x + self.dx, y + self.dy)
    def label(self, t, x, y, a, g): return self.S.label(t, x + self.dx, y + self.dy, a, g)
    def gnd(self, x, y, a=0): return self.S.gnd(x + self.dx, y + self.dy, a)
    def nc(self, x, y): return self.S.nc(x + self.dx, y + self.dy)
    def text(self, s, x, y, size=1.27): return self.S.text(s, x + self.dx, y + self.dy, size)
