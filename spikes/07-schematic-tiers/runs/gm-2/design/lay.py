"""Hand-composition canvas for schematic sheets: place symbols by pin, wire by coordinates, with automatic junctions and
a lint pass (text on text, text on wire, wire through a symbol body). Per-sheet pictures live in layouts.py."""
import math, zlib
import symlib
from draw import rot, snap, G

CHW = 1.2      # mm per character of 1.27 mm text (generous, for overlap checks)

class Pl:
    """A placed symbol: pin positions and outward directions in sheet coordinates."""
    def __init__(self, ref, x, y, angle, mirror, pos, dirs, names, box):
        self.ref, self.x, self.y, self.angle, self.mirror = ref, x, y, angle, mirror
        self.pos, self.dirs, self.names, self.box = pos, dirs, names, box
    def __call__(self, key):
        k = str(key)
        if k in self.pos: return self.pos[k]
        if k in self.names: return self.pos[self.names[k][0]]
        raise KeyError(f"{self.ref} has no pin {k}")
    def d(self, key):
        k = str(key)
        if k not in self.pos: k = self.names[k][0]
        return self.dirs[k]
    def x_(self, key): return self(key)[0]
    def y_(self, key): return self(key)[1]

class Cv:
    def __init__(self, sheet, comps, nets, nc, block, glob, title_h=0):
        self.s, self.comps, self.nets, self.block = sheet, comps, nets, block
        self.glob = glob
        self.pinnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
        self.ncset = {(r, p) for r, p in nc}
        self.drawn = set()
        self.wires, self.pinpts, self.texts, self.boxes = [], [], [], []
        self.juncs = set()
        self.placed = {}

    # ---- names ----
    ALIAS = {"Net-(Q104-G)": "HTR_GATE", "Net-(U102-OUT)": "U102_OUT", "Net-(F102-HTR)": "F102_HTR",
             "Net-(C110-Pad2)": "ESD_MID", "Net-(C313-Pad2)": "ANT_MATCH"}
    def short(self, n):
        if n in self.ALIAS: return self.ALIAS[n]
        return n.lstrip("/") if n in self.glob else n.split("/")[-1]
    def net(self, ref, num): return self.pinnet.get((ref, str(num)))

    # ---- symbols ----
    def place(self, ref, x, y, angle=0, mirror=False, unit=1, ref_at=None, val_at=None, just="left",
              hide_ref=False, hide_val=False):
        x, y = snap(x), snap(y)
        lib, name = self.comps[ref]["lib"].split(":")
        c = self.comps[ref]
        self.s.symbol(lib, name, ref, c["value"], x, y, angle, unit=unit, footprint=c["footprint"], fields=c["fields"],
                      ref_at=ref_at, val_at=val_at, mirror=mirror, just=just, hide_ref=hide_ref, hide_val=hide_val)
        pos, dirs, names = {}, {}, {}
        inner = []
        for p in symlib.pins(lib, name):
            if p["unit"] not in (0, unit): continue
            dx, dy = rot(p["x"], p["y"], angle)
            if mirror: dx = -dx                      # KiCad mirrors after it rotates
            pos[p["num"]] = (snap(x + dx), snap(y + dy))
            ox, oy = (-math.cos(math.radians(p["angle"])), -math.sin(math.radians(p["angle"])))
            sx, sy = rot(ox, oy, angle)
            if mirror: sx = -sx
            dirs[p["num"]] = "L" if sx < -0.5 else "R" if sx > 0.5 else "U" if sy < -0.5 else "D"
            names.setdefault(p["name"], []).append(p["num"])
            # inner end of the pin: move from the tip toward the body by the pin length
            tipx, tipy = pos[p["num"]]
            inner.append((tipx - sx * p["length"], tipy - sy * p["length"]))
            self.pinpts.append(pos[p["num"]])
        xs = [i[0] for i in inner]; ys = [i[1] for i in inner]
        box = (min(xs), min(ys), max(xs), max(ys))
        pl = Pl(ref, x, y, angle, mirror, pos, dirs, names, box)
        self.drawn.add(ref); self.placed[ref] = pl
        if len(pos) > 2 or max(xs) - min(xs) > 0.5 and max(ys) - min(ys) > 0.5:
            self.boxes.append((ref,) + box)
        # reference and value text
        for t, at in ((ref, ref_at), (c["value"], val_at)):
            if at and not (hide_ref and t == ref):
                self._text_box(t, at[0], at[1], just, f"{ref} text")
        return pl

    def orient2(self, ref, want):
        """Angle for a two-pad part so that pin `want` = ('num','U'|'D'|'L'|'R') sits in that direction from the other."""
        lib, name = self.comps[ref]["lib"].split(":")
        pp = {}
        for p in symlib.pins(lib, name): pp.setdefault(p["num"], p)
        nums = sorted(pp)
        num, d = want
        other = nums[1] if num == nums[0] else nums[0]
        for a in (0, 90, 180, 270):
            ax, ay = rot(pp[num]["x"], pp[num]["y"], a); bx, by = rot(pp[other]["x"], pp[other]["y"], a)
            vx, vy = ax - bx, ay - by
            if d == "U" and abs(vx) < .01 and vy < 0: return a
            if d == "D" and abs(vx) < .01 and vy > 0: return a
            if d == "L" and abs(vy) < .01 and vx < 0: return a
            if d == "R" and abs(vy) < .01 and vx > 0: return a
        raise ValueError(f"cannot orient {ref}")

    def ends(self, ref):
        lib, name = self.comps[ref]["lib"].split(":")
        nums = sorted({p["num"] for p in symlib.pins(lib, name)})
        return nums, [self.net(ref, n) for n in nums]

    def pad_of(self, ref, net, nth=0):
        nums, ns = self.ends(ref)
        return [n for n, m in zip(nums, ns) if m == net][nth]

    def vp(self, ref, x, y, top, side="R", ref_at=None, val_at=None, hide_val=False):
        """Two-pad part upright at (x, y) with net `top` on the upper pin. Returns Pl; .top / .bot pin points."""
        nums, ns = self.ends(ref)
        tn = nums[ns.index(top)] if top in ns else nums[0]
        a = self.orient2(ref, (tn, "U"))
        dx = 2.4 if side == "R" else -2.4
        j = "left" if side == "R" else "right"
        pl = self.place(ref, x, y, a, ref_at=ref_at or (x + dx, y - 1.4), val_at=val_at or (x + dx, y + 1.4), just=j,
                        hide_val=hide_val)
        pl.top = pl.pos[tn]; pl.bot = pl.pos[[n for n in nums if n != tn][0]]
        return pl

    def hp(self, ref, x, y, left, ref_at=None, val_at=None, txt="mid"):
        nums, ns = self.ends(ref)
        ln = nums[ns.index(left)] if left in ns else nums[0]
        a = self.orient2(ref, (ln, "L"))
        if txt in ("line", "linebelow"):        # "R101 100" on one line above the part: needs only 5 mm between lanes
            tw = (len(ref) + 1 + len(self.comps[ref]["value"])) * CHW
            dy = -2.6 if txt == "line" else 2.6
            ref_at = (x - tw / 2, y + dy); val_at = (x - tw / 2 + (len(ref) + 1) * CHW, y + dy)
            pl = self.place(ref, x, y, a, ref_at=ref_at, val_at=val_at, just="left")
        else:
            dy = {"mid": (-2.8, 2.8), "above": (-4.6, -2.8), "below": (2.8, 4.6)}[txt]
            pl = self.place(ref, x, y, a, ref_at=ref_at or (x, y + dy[0]), val_at=val_at or (x, y + dy[1]), just="center")
        pl.lft = pl.pos[ln]; pl.rgt = pl.pos[[n for n in nums if n != ln][0]]
        return pl

    def one(self, ref, px, py, d="U", txt="R"):
        """One-pad part (test point, wire pad) placed so its pin is at (px, py) and sticks out on side d of the symbol
        (d="U": pin up, the pad hangs below the point). Text beside the pad. Returns Pl with .pin."""
        lib, name = self.comps[ref]["lib"].split(":")
        p = symlib.pins(lib, name)[0]
        for a in (0, 90, 180, 270):
            dx, dy = rot(p["x"], p["y"], a)
            ox, oy = rot(-math.cos(math.radians(p["angle"])), -math.sin(math.radians(p["angle"])), a)
            dd = "L" if ox < -.5 else "R" if ox > .5 else "U" if oy < -.5 else "D"
            if dd == d: break
        x, y = snap(px - dx), snap(py - dy)
        if txt == "above":
            pl = self.place(ref, x, y, a, ref_at=(x, y - 5.2), val_at=(x, y - 3.6), just="center")
        else:
            tx = (x + 2.2, "left") if txt == "R" else (x - 2.2, "right")
            pl = self.place(ref, x, y, a, ref_at=(tx[0], y - 1.4), val_at=(tx[0], y + 1.4), just=tx[1])
        pl.pin = pl.pos[p["num"]]
        return pl

    def chain(self, x, y, refs, net, gap=1.27, txt="line"):
        """In-line two-pad parts laid leftwards from (x, y), the first one reached by a wire from x. `net` is the net at x.
        Returns (x where the next thing can attach, net there)."""
        for r in refs:
            nums, ns = self.ends(r)
            other = [n for n in ns if n != net]
            other = other[0] if other else net
            tw = (len(r) + 1 + len(self.comps[r]["value"])) * CHW
            wd = max(tw + 1.0, 8.9)
            xc = snap(x - gap - wd / 2)
            pl = self.hp(r, xc, y, other, txt=txt)
            self.w((x, y), pl.rgt)
            xn = snap(pl.lft[0] - max(0.0, (wd - 7.62) / 2 - 1.0))
            self.w(pl.lft, (xn, y))
            x, net = xn, other
        return x, net

    # ---- wires and labels ----
    def w(self, *pts):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            x1, y1, x2, y2 = snap(x1), snap(y1), snap(x2), snap(y2)
            if (x1, y1) == (x2, y2): continue
            if x1 != x2 and y1 != y2:
                raise ValueError(f"diagonal wire {(x1, y1)} -> {(x2, y2)}")
            if (x1, y1, x2, y2) in self.wires or (x2, y2, x1, y1) in self.wires: continue
            self.wires.append((x1, y1, x2, y2))

    def lab(self, x, y, net, d="R", force_glob=None):
        """Net label at (x, y): text runs away from the point in direction d (L or R)."""
        x, y = snap(x), snap(y)
        g = (net in self.glob or net in self.GROUNDS) if force_glob is None else force_glob
        t = self.short(net)
        self.s.label(t, x, y, 0 if d == "R" else 180, g)
        w = len(t) * CHW + (2.5 if g else 0)
        if g: self._tb(x - (w if d == "L" else 0), y - 1.0, x + (w if d == "R" else 0), y + 1.0, f"label {t}")
        else: self._tb(x - (w if d == "L" else 0), y - 1.7, x + (w if d == "R" else 0), y - 0.2, f"label {t}")

    def end(self, x, y, net, d="R", stub=2.54, sym=True):
        """Finish a wire end at (x, y): GND symbol, or a stub and a label. d is the direction the stub runs."""
        if net == "GND":
            self.s.gnd(x, y); self.pinpts.append((snap(x), snap(y)))
            self.boxes.append(("gnd", snap(x) - 1.5, snap(y), snap(x) + 1.5, snap(y) + 3.5))
            return
        if net in self.GROUNDS and sym:
            x, y = snap(x), snap(y); s = self.s
            s.npwr += 1
            ref = f"#PWR{zlib.crc32(s.name.encode()) % 90 + 10}{s.npwr:03d}"
            s.symbol("power", "GND", ref, self.short(net), x, y, 0, hide_ref=True, hide_val=True, key=f"pwr{s.npwr}",
                     val_at=(x, y + 5.6), just="center")
            self.pinpts.append((x, y))
            self.boxes.append(("gnd", x - 1.5, y, x + 1.5, y + 3.5))
            return
        dx = {"R": stub, "L": -stub}[d]
        if stub: self.w((x, y), (x + dx, y))
        self.lab(x + dx, y, net, d)

    def gnd_side(self, x, y, d="L", net="GND"):
        """Ground symbol lying on its side at the end of a horizontal wire (stem toward the wire, body away): no height."""
        if net in self.GROUNDS:
            sx = self.s; sx.npwr += 1
            ref = f"#PWR{zlib.crc32(sx.name.encode()) % 90 + 10}{sx.npwr:03d}"
            sx.symbol("power", "GND", ref, self.short(net), snap(x), snap(y), {"L": 270, "R": 90}[d], hide_ref=True, hide_val=True,
                      key=f"pwr{sx.npwr}", val_at=(snap(x), snap(y) + 5.6), just="center")
            self.pinpts.append((snap(x), snap(y)))
        else:
            self.s.gnd(x, y, {"L": 270, "R": 90}[d]); self.pinpts.append((snap(x), snap(y)))
        xb = snap(x) + (-3.5 if d == "L" else 0.0)
        self.boxes.append(("gnd", xb, snap(y) - 1.6, xb + 3.5, snap(y) + 1.6))

    def pwr(self, x, y, net, name=None):
        """Supply symbol (arrow up) named for the net, its pin at (x, y). Joins the global net of that name."""
        x, y = snap(x), snap(y)
        s = self.s
        s.npwr += 1
        ref = f"#PWR{zlib.crc32(s.name.encode()) % 90 + 10}{s.npwr:03d}"
        t = name or self.short(net)
        s.symbol("power", "+3V3", ref, t, x, y, 0, hide_ref=True, hide_val=False, key=f"pwr{s.npwr}",
                 val_at=(x, y - 4.2), just="center")
        self.pinpts.append((x, y))
        self.boxes.append(("pwr", x - .5, y - 3.0, x + .5, y))
        self._tb(x - len(t) * CHW / 2, y - 4.9, x + len(t) * CHW / 2, y - 3.5, f"pwr text {t}")

    def tee(self, x, y, net, up=True, stub=2.54, d="R"):
        """Branch off a wire at (x, y): a short stub up or down ending in a net label."""
        self.w((x, y), (x, y + (-stub if up else stub)))
        self.lab(x, y + (-stub if up else stub), net, d)
        self.junction(x, y)

    RAILS = set()
    GROUNDS = {"CELL_1N"}
    SUPPLY = {"3V3", "PACK_P", "VBUS", "CELL_P"}
    VEC = {"L": (-1, 0), "R": (1, 0), "U": (0, -1), "D": (0, 1)}
    def pin_end(self, pl, key, stub=2.54, net=None, d=None):
        """Finish one pin of a placed symbol: no-connect, ground, or a stub and a net label, going out of the symbol."""
        k = str(key)
        if k not in pl.pos: k = pl.names[k][0]
        x, y = pl.pos[k]; d = d or pl.dirs[k]
        pl.__dict__.setdefault("handled", set()).add((x, y))
        n = net or self.net(pl.ref, k)
        if (pl.ref, k) in self.ncset or n is None: return self.nc(x, y)
        vx, vy = self.VEC[d]; q = (x + vx * stub, y + vy * stub)
        self.w((x, y), q)
        if n == "GND" or n in self.GROUNDS:
            if d in "LR": self.gdown(*q, net=n)
            else: self.end(q[0], q[1], "GND")
        elif (d == "U" and n in self.SUPPLY) or n in self.RAILS:
            self.pwr(*q, n)
        else:
            self.lab(q[0], q[1], n, "L" if d == "L" else "R")

    def rest(self, pl, stub=2.54):
        """Stub every pin of pl that was not finished yet."""
        h = pl.__dict__.setdefault("handled", set())
        for k, p in list(pl.pos.items()):
            if p in h: continue
            self.pin_end(pl, k, stub)

    def nc(self, x, y):
        self.s.nc(x, y); self.pinpts.append((snap(x), snap(y)))

    def junction(self, x, y): self.juncs.add((snap(x), snap(y)))

    def text(self, s, x, y, size=1.27, just="left bottom"):
        x, y = snap(x), snap(y)
        j = f"(justify {just})" if just else ""
        self.s.items.append(f'(text "{s}" (exclude_from_sim no) (at {x} {y} 0) (effects (font (size {size} {size})) {j}) '
                            f'(uuid "{__import__("draw").uid(self.s.name, "t", s, x, y)}"))')
        self.s._ext(x + len(s) * CHW * size / 1.27, y)
        w = len(s) * CHW * size / 1.27
        self._tb(x, y - size * 1.1, x + w, y, f"text {s[:20]}")

    def note(self, x, y, lines, size=1.27, step=None):
        step = step or size * 1.9
        for i, l in enumerate(lines): self.text(l, x, y + i * step, size)

    def frame(self, x0, y0, x1, y1, title=None, size=2.0):
        import draw
        x0, y0, x1, y1 = snap(x0), snap(y0), snap(x1), snap(y1)
        self.s.items.append(f'(rectangle (start {x0} {y0}) (end {x1} {y1}) (stroke (width 0.15) (type dash)) (fill (type none)) '
                            f'(uuid "{draw.uid(self.s.name, "fr", x0, y0, x1, y1)}"))')
        self.s._ext(x1, y1)
        if title: self.text(title, x0 + 2.54, y0 + 6.0, size)

    def lanes(self, pl, keys, side, ys, gap=5.08, step=2.54):
        """Fan pins (listed top to bottom, all on one side) out to horizontal lanes at the given y values without crossings.
        Lanes above their pin turn top pin first, lanes below turn bottom pin first. Returns [(x where the lane starts, y)]."""
        sg = -1 if side == "L" else 1
        pts = [pl(k) for k in keys]; n = len(keys)
        up = [i for i in range(n) if ys[i] < pts[i][1] - .01]; dn = [i for i in range(n) if ys[i] > pts[i][1] + .01]
        col = {i: k for k, i in enumerate(up)}
        col.update({i: k for k, i in enumerate(reversed(dn))})
        ncol = max(len(up), len(dn))
        xs = pts[0][0] + sg * (gap + ncol * step)
        out = []
        for i, k in enumerate(keys):
            px, py = pts[i]
            if i in col:
                xc = px + sg * (gap + col[i] * step)
                self.w((px, py), (xc, py), (xc, ys[i]), (xs, ys[i]))
            else:
                self.w((px, py), (xs, ys[i]))
            pl.__dict__.setdefault("handled", set()).add(pts[i])
            out.append((snap(xs), snap(ys[i])))
        return out

    def gdown(self, x, y, drop=2.54, net="GND"):
        """Wire straight down from (x, y) and end in a ground symbol."""
        self.w((x, y), (x, y + drop)); self.end(x, y + drop, net)

    def bank(self, refs, x0, yr, top, bot, pitch=None, xend_wire=True, bus_label_left=True, gnd_at=0):
        """Parts side by side between net `top` (rail wire at yr, from x0) and `bot` (bus wire below). Returns (x of the
        last part, bottom bus y, next free x)."""
        x = snap(x0); xs = []
        for r in refs:
            wd = max(len(r), len(self.comps[r]["value"])) * CHW + 5.0
            xs.append(x); x = snap(x + (pitch or max(wd, 7.62)) + 0.01)
        pls = [self.vp(r, xi, yr + 6.35, top) for r, xi in zip(refs, xs)]
        yb = pls[0].bot[1] + 2.54
        self.w((xs[0], yr), (xs[-1], yr))
        for p in pls:
            self.w((p.top[0], yr), p.top); self.w(p.bot, (p.bot[0], yb))
        self.w((xs[0], yb), (xs[-1], yb))
        if bot == "GND": self.end(xs[gnd_at], yb, "GND")
        else: self.end(xs[0], yb, bot, "L")
        return xs[-1], yb, x

    def _tb(self, x0, y0, x1, y1, what):
        self.texts.append((what, x0, y0, x1, y1))
    def _text_box(self, t, x, y, just, what):
        w = len(t) * CHW
        if just == "left": box = (x, y - .7, x + w, y + .7)
        elif just == "right": box = (x - w, y - .7, x, y + .7)
        else: box = (x - w / 2, y - .7, x + w / 2, y + .7)
        self._tb(*box[:1], box[1], box[2], box[3], what)

    def finish(self, missing_ok=()):
        """Automatic junctions, then lint. Returns a list of warnings."""
        # a wire only connects to a pin at its end: split wires that run over a pin
        split = []
        pinset = set(self.pinpts)
        for x1, y1, x2, y2 in self.wires:
            cut = sorted({p for p in pinset if (x1 == x2 == p[0] and min(y1, y2) < p[1] < max(y1, y2)) or
                          (y1 == y2 == p[1] and min(x1, x2) < p[0] < max(x1, x2))},
                         key=lambda p: (p[0] - x1) ** 2 + (p[1] - y1) ** 2)
            chain = [(x1, y1)] + cut + [(x2, y2)]
            for a, b in zip(chain, chain[1:]): split.append(a + b)
        self.wires = split
        for x1, y1, x2, y2 in self.wires: self.s.wire(x1, y1, x2, y2)
        pts = {}
        def add(p, k, n=1): pts.setdefault(p, {}).setdefault(k, 0); pts[p][k] += n
        segs = []
        for x1, y1, x2, y2 in set(self.wires):
            segs.append((x1, y1, x2, y2)); add((x1, y1), "end"); add((x2, y2), "end")
        for p in self.pinpts: add(p, "pin")
        for p in list(pts):
            for x1, y1, x2, y2 in segs:
                if (x1 == x2 == p[0] and min(y1, y2) < p[1] < max(y1, y2)) or (y1 == y2 == p[1] and min(x1, x2) < p[0] < max(x1, x2)):
                    add(p, "thru", 2)
        for p, d in pts.items():
            if sum(d.values()) >= 3 and "end" in d or d.get("thru") and d.get("pin", 0) >= 1 and False:
                self.juncs.add(p)
        for x, y in sorted(self.juncs): self.s.junction(x, y)
        warns = []
        miss = [r for r in self.comps if self.comps[r]["block"] == self.block and r not in self.drawn]
        if miss: warns.append(f"NOT DRAWN: {' '.join(miss)}")
        T = self.texts
        for i in range(len(T)):
            for j in range(i + 1, len(T)):
                a, b = T[i], T[j]
                if a[1] < b[3] - .2 and b[1] < a[3] - .2 and a[2] < b[4] - .2 and b[2] < a[4] - .2:
                    warns.append(f"text overlap: [{a[0]}] x [{b[0]}] at ({a[1]:.0f},{a[2]:.0f})")
        for t in T:
            for x1, y1, x2, y2 in segs:
                if min(x1, x2) < t[3] - .2 and max(x1, x2) > t[1] + .2 and min(y1, y2) < t[4] - .2 and max(y1, y2) > t[2] + .2:
                    warns.append(f"text on wire: [{t[0]}] at ({t[1]:.0f},{t[2]:.0f})")
                    break
        for b in self.boxes:
            for x1, y1, x2, y2 in segs:
                if min(x1, x2) < b[3] - .3 and max(x1, x2) > b[1] + .3 and min(y1, y2) < b[4] - .3 and max(y1, y2) > b[2] + .3:
                    warns.append(f"wire through body of {b[0]} at ({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})")
            for t in T:
                if t[0].startswith(b[0] + " text") or t[0].startswith("label") and False: continue
                if t[1] < b[3] - .3 and b[1] < t[3] - .3 and t[2] < b[4] - .3 and b[2] < t[4] - .3:
                    warns.append(f"text [{t[0]}] over body of {b[0]}")
        return sorted(set(warns))
