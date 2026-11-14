"""Scene toolkit: place parts and wire them the way a person draws a schematic. Scenes (design/scenes_*.py) are short
programs over this API. The netlist stays the truth: a scene says where things go, the netlist check proves the wiring.

Conventions: mm, y down. A two-pin part drawn upright is 7.62 mm between its wire ends; its centre is on the grid.
"""
import symlib
import math
import os
from contextlib import contextmanager
from sheet import *
from sheet import snap, G, text_w, rot, body_box

RAILS = {"3V3": "+3V3", "PACK_P": "+12V"}        # global supply nets that get a supply symbol (arrow up)


class Part2:
    """A placed two-pin part. t/b (upright) or l/r (lying down) are its wire ends; net_* the nets there."""
    def __init__(self, ref, x, y, placed, vertical, nets):
        self.ref, self.x, self.y, self.pl, self.vertical = ref, x, y, placed, vertical
        a, b = nets
        if vertical:
            self.t, self.b = (x, snap(y - 3.81)), (x, snap(y + 3.81)); self.nt, self.nb = a, b
        else:
            self.l, self.r = (snap(x - 3.81), y), (snap(x + 3.81), y); self.nl, self.nr = a, b


class Lay:
    def __init__(self, sheet, comps, nets, nc, glob, cons, disp=None):
        self._init = (comps, nets, nc, glob, cons, dict(disp or {}))
        self.s, self.comps, self.nets, self.glob, self.cons = sheet, comps, nets, glob, cons
        self.pinnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
        self.ncset = {(r, p) for r, p in nc}
        self.disp = dict(disp or {})
        self.placed = {}
        self.frames = {}
        self.rails = dict(RAILS)

    # ------------------------------------------------------------------ names
    def short(self, n):
        if n in self.disp: return self.disp[n]
        if n in self.glob: return n.lstrip("/")
        return n.split("/")[-1]

    def netof(self, ref, pin):
        return self.pinnet.get((ref, str(pin)))

    def pads(self, ref):
        return sorted({p["num"] for p in symlib.pins(*self.comps[ref]["lib"].split(":"))})

    def ends(self, ref):
        return [self.pinnet.get((ref, n)) for n in self.pads(ref)]

    def val(self, ref): return self.comps[ref]["value"]

    # ------------------------------------------------------------------ parts
    def _sym(self, ref, x, y, angle, unit=1, mirror=False, gaps=None, **kw):
        lib, name = self.comps[ref]["lib"].split(":")
        c = self.comps[ref]
        pl = self.s.symbol(lib, name, ref, c["value"], x, y, angle, unit=unit, footprint=c["footprint"], fields=c["fields"],
                           mirror=mirror, gaps=gaps, **kw)
        self.placed[ref] = pl
        return pl

    def tw(self, ref, tag=None):
        """Width in mm of the text a part carries."""
        return max(text_w(ref), text_w(self.val(ref)))

    def v(self, ref, x, y, top=None, side="R", txt=True):
        """Upright two-pin part centred at (x, y) with net `top` (or pad 1) on top. Text on the right (side R) or left."""
        x, y = snap(x), snap(y)
        lib, name = self.comps[ref]["lib"].split(":")
        pads = self.pads(ref); e = self.ends(ref)
        up = pads[0] if (top is None or e[0] == top) else pads[1]
        if len(pads) == 1:
            up = pads[0]
        pp = {}
        for p in symlib.pins(lib, name): pp.setdefault(p["num"], p)
        angle = 0
        for a in (0, 90, 180, 270):
            if len(pads) == 1:
                _, dy = rot(pp[up]["x"], pp[up]["y"], a)
                dx = rot(pp[up]["x"], pp[up]["y"], a)[0]
                if abs(dx) < 0.01 and dy >= 0: angle = a; break
                continue
            dn = pads[1] if up == pads[0] else pads[0]
            ux, uy = rot(pp[up]["x"], pp[up]["y"], a); dx, dy = rot(pp[dn]["x"], pp[dn]["y"], a)
            if abs(ux) < 0.01 and abs(dx) < 0.01 and uy < dy: angle = a; break
        bx0, by0, bx1, by1 = body_box(lib, name, 1)
        hw = max(abs(bx0), abs(bx1)) if lib != "Connector" else 1.5
        hw = min(max(hw, 1.1), 2.4)
        kw = {}
        if txt is False: kw = dict(hide_ref=True, hide_val=True)
        elif side == "R": kw = dict(ref_at=(x + hw + 0.9, y - 1.3, "l"), val_at=(x + hw + 0.9, y + 1.3, "l"))
        else: kw = dict(ref_at=(x - hw - 0.9, y - 1.3, "r"), val_at=(x - hw - 0.9, y + 1.3, "r"))
        pl = self._sym(ref, x, y, angle, **kw)
        e = self.ends(ref)
        nets = (e[pads.index(up)], e[1 - pads.index(up)]) if len(pads) == 2 else (e[0], None)
        return Part2(ref, x, y, pl, True, nets)

    def h(self, ref, x, y, left=None, txt="ab"):
        """Two-pin part lying down centred at (x, y) with net `left` (or pad 1) on the left. Text above/below, centred."""
        x, y = snap(x), snap(y)
        lib, name = self.comps[ref]["lib"].split(":")
        pads = self.pads(ref); e = self.ends(ref)
        lf = pads[0] if (left is None or e[0] == left) else pads[1]
        rt = pads[1] if lf == pads[0] else pads[0]
        pp = {}
        for p in symlib.pins(lib, name): pp.setdefault(p["num"], p)
        angle = 0
        for a in (0, 90, 180, 270):
            lx, ly = rot(pp[lf]["x"], pp[lf]["y"], a); rx, ry = rot(pp[rt]["x"], pp[rt]["y"], a)
            if abs(ly) < 0.01 and abs(ry) < 0.01 and lx < rx: angle = a; break
        if txt == "ab": kw = dict(ref_at=(x, y - 2.9, "c"), val_at=(x, y + 2.9, "c"))
        elif txt == "aa": kw = dict(ref_at=(x, y - 5.0, "c"), val_at=(x, y - 3.2, "c"))
        elif txt == "bb": kw = dict(ref_at=(x, y + 3.2, "c"), val_at=(x, y + 5.0, "c"))
        else: kw = dict(hide_ref=True, hide_val=True)
        pl = self._sym(ref, x, y, angle, **kw)
        e = self.ends(ref)
        nets = (e[pads.index(lf)], e[pads.index(rt)])
        return Part2(ref, x, y, pl, False, nets)

    def ic(self, ref, x, y, gaps=None, unit=1, mirror=False, text="above", at_pin=None):
        """Place a many-pin part with the top left corner of its body at (x, y), or, with at_pin, with that pin's outer end
        at (x, y). gaps stretches its sides (see sheet.sym_node)."""
        lib, nm = self.comps[ref]["lib"].split(":")
        bx0, by0, bx1, by1 = body_box(lib, nm, unit, gaps)
        if mirror in (True, "y"): bx0, bx1 = -bx1, -bx0
        if at_pin is not None:
            from sheet import sym_pins
            pp = [p for p in sym_pins(lib, nm, gaps) if p["unit"] in (0, unit) and at_pin in (p["num"], p["name"])][0]
            px = -pp["x"] if mirror in (True, "y") else pp["x"]
            ox, oy = snap(x - px), snap(y + pp["y"])
            x, y = ox + bx0, oy - by1
        else:
            ox, oy = snap(x - bx0), snap(y + by1)
        x0 = ox + bx0; ytop = oy - by1
        if text == "above": kw = dict(ref_at=(snap(x0), ytop - 4.5, "l"), val_at=(snap(x0), ytop - 2.4, "l"))
        elif text == "below": kw = dict(ref_at=(snap(x0), snap(ytop + (by1 - by0) + 2.5), "l"), val_at=(snap(x0), snap(ytop + (by1 - by0) + 4.6), "l"))
        else: kw = dict(ref_at=text[0], val_at=text[1])
        return self._sym(ref, ox, oy, 0, unit=unit, mirror=mirror, gaps=gaps, **kw)

    # ------------------------------------------------------------------ wires and ends
    def wire(self, *pts): self.s.path(*pts)

    def lab(self, net, x, y, d="R", force_local=False):
        """A net label at (x, y) reading away from the wire: d is the way the wire runs into it (R: wire from the left)."""
        ang = {"R": 0, "L": 180, "D": 0, "U": 0}[d]
        self.s.label(self.short(net), x, y, ang, (net in self.glob) and not force_local)

    gnd_like = {"CELL_1N": "GNDA"}               # nets drawn with a ground-style symbol carrying the net name

    def term(self, net, x, y, d="D"):
        """Terminate a net at (x, y) where a wire arrives travelling in direction d: no-connect, ground symbol, named
        ground-style symbol, supply arrow (only when going up) or a label."""
        if net is None: return self.s.nc(x, y)
        ang = {"D": 0, "U": 180, "R": 90, "L": 270}[d]
        if net == "GND": return self.s.gnd(x, y, ang)
        if net in self.gnd_like: return self.s.pwr(self.gnd_like[net], self.short(net), x, y, ang)
        if net in self.rails and d == "U": return self.s.rail(self.short(net), x, y, self.rails[net])
        self.s.label(self.short(net), x, y, 180 if d == "L" else 0, net in self.glob)

    def end(self, net, x, y, d="D", stub=0.0):
        """term() after an optional stub of the given length."""
        if stub:
            dx, dy = {"D": (0, stub), "U": (0, -stub), "R": (stub, 0), "L": (-stub, 0)}[d]
            self.s.wire(x, y, x + dx, y + dy); x, y = x + dx, y + dy
        self.term(net, x, y, d)

    def stub(self, pl, pin, d=None, n=2.54, net="auto"):
        """Short wire from a pin of an IC straight out, ending in a label or symbol. Returns the end point."""
        pinf = [p for p in pl.pins if p["num"] == str(pin) or p["name"] == str(pin)][0]
        x, y = pinf["sx"], pinf["sy"]
        d = d or {0: "L", 180: "R", 270: "U", 90: "D"}[pinf["ang"]]
        net = self.netof(pl.ref, pinf["num"]) if net == "auto" else net
        if (pl.ref, pinf["num"]) in self.ncset: net = None
        dx, dy = {"D": (0, n), "U": (0, -n), "R": (n, 0), "L": (-n, 0)}[d]
        if net is None: self.s.nc(x, y); return (x, y)
        ex, ey = snap(x + dx), snap(y + dy)
        self.s.wire(x, y, ex, ey)
        self.term(net, ex, ey, d)
        return (ex, ey)

    def finish(self, pl, skip=(), n=2.54):
        """Every pin of an IC not named in skip gets a stub with its net label (or ground / no-connect)."""
        seen = set()
        for p in pl.pins:
            if p["num"] in skip or p["name"] in skip: continue
            pt = (p["sx"], p["sy"])
            if pt in seen: continue
            seen.add(pt)
            if pt in self._used_pins(pl): continue
            self.stub(pl, p["num"], n=n)

    def _used_pins(self, pl):
        return getattr(self, "_used", {}).get(pl.ref, set())

    def use(self, pl, *pins):
        """Mark pins as wired by the scene so finish() leaves them alone."""
        u = self.__dict__.setdefault("_used", {}).setdefault(pl.ref, set())
        for k in pins:
            for p in pl.pins:
                if p["num"] == str(k) or p["name"] == str(k): u.add((p["sx"], p["sy"]))

    # ------------------------------------------------------------------ text
    def title(self, s, x, y, size=2.5): self.s.text(s, x, y, size)
    def section(self, s, x, y): self.s.text(s, x, y, 2.0)
    def note(self, s, x, y, size=1.27): self.s.text(s, x, y, size, "left top")

    # ------------------------------------------------------------------ motifs
    def pitch(self, ref, other=None):
        """Horizontal room an upright part with text on its right needs."""
        w = self.tw(ref)
        if other and other not in ("GND",): w = max(w, text_w(self.short(other)) + (3.5 if other in self.glob else 0.5))
        return snap(2.4 + 0.9 + w + 2.6)

    def hang_row(self, refs, x0, y, net, step=None, lead=0):
        """Parts hanging from a horizontal wire at y (net `net`), each from `net` down to GND or a label.
        The wire runs from x0 to the last part. Returns the list of part x positions and the x after the row."""
        x = snap(x0 + lead); xs = []
        for r in refs:
            other = [n for n in self.ends(r) if n != net]
            other = other[0] if other else None
            p = self.v(r, x, y + 3.81, top=net)
            if other is not None and other == "GND": self.s.gnd(p.b[0], p.b[1], 0)
            else: self.end(other, p.b[0], p.b[1], "D")
            xs.append(x)
            x = snap(x + (step or self.pitch(r, other if other != "GND" else None)))
        if xs: self.s.wire(snap(x0), y, xs[-1], y)
        return xs, x

    def ladder(self, refs, x0, y0, net, per_row, row_h=26.0, lead=6.35):
        """Parallel parts on one net drawn as rows hanging from stacked rails, the rails joined at the left."""
        rows = [refs[i:i + per_row] for i in range(0, len(refs), per_row)]
        xmax, y = x0, y0
        for k, rr in enumerate(rows):
            xs, xe = self.hang_row(rr, x0, y, net, lead=lead)
            xmax = max(xmax, xe)
            if k: self.s.wire(x0, y - row_h, x0, y)
            y += row_h
        return xmax, y

    def pull(self, ref, x, y, rail, side="R"):
        """A part from net `rail` (supply arrow on top) down to the node at (x, y): a pull-up, drawn upright above the node."""
        p = self.v(ref, x, snap(y - 3.81), top=rail, side=side)
        if rail == "GND": return p
        if side == "L" and rail not in self.rails:
            self.s.label(self.short(rail), p.t[0], p.t[1], 180, rail in self.glob)
        else:
            self.end(rail, p.t[0], p.t[1], "U")
        return p

    def drop(self, ref, x, y, net, side="R"):
        """A part hanging from the node at (x, y) down to GND (ground symbol) or another net (label)."""
        other = [n for n in self.ends(ref) if n != net]
        other = other[0] if other else None
        p = self.v(ref, x, snap(y + 3.81), top=net, side=side)
        self.end(other, p.b[0], p.b[1], "D")
        return p

    def box_title(self, s, x, y):
        self.s.text(s, x, y, 2.0)

    def rule(self, x0, y0, x1, y1):
        """A thin dashed-looking frame is not drawn: KiCad schematic frames need graphics we do not use; keep as no-op."""
        pass

    def pinxy(self, pl, key):
        return pl.pin(key)

    def netat(self, pl, key):
        for p in pl.pins:
            if p["num"] == str(key) or p["name"] == str(key):
                return None if (pl.ref, p["num"]) in self.ncset else self.netof(pl.ref, p["num"])

    def out_pull(self, pl, pin, x, ref, rail, lab_dx=7.62, label=True):
        """A pin on the right of an IC runs to a label; a pull-up to `rail` hangs from the wire at x (supply arrow on top)."""
        px, py = pl.pin(pin); net = self.netat(pl, pin)
        xl = snap(x + lab_dx)
        self.s.wire(px, py, xl, py)
        r = self.pull(ref, snap(x), py, rail)
        if label: self.lab(net, xl, py, "R")
        self.use(pl, pin)
        return r

    def in_pull(self, pl, pin, x, ref, rail, lab_dx=7.62):
        """Same for a pin on the left, the label at the far left."""
        px, py = pl.pin(pin); net = self.netat(pl, pin)
        xl = snap(x - lab_dx)
        self.s.wire(xl, py, px, py)
        r = self.pull(ref, snap(x), py, rail)
        self.lab(net, xl, py, "L")
        self.use(pl, pin)
        return r

    # ------------------------------------------------------------------ single-pin parts
    def pad(self, ref, x, y, body="L", text=True):
        """A wire pad or test point whose connection end is at (x, y), its body extending toward `body` (L, R, U, D)."""
        lib, nm = self.comps[ref]["lib"].split(":")
        x, y = snap(x), snap(y)
        if lib == "Connector_Generic":                      # pin on the left of the body at -5.08
            a, ox, oy = (0, x + 5.08, y) if body == "R" else (180, x - 5.08, y)
            if body in ("U", "D"):
                a, ox, oy = (90, x, y - 5.08) if body == "U" else (270, x, y + 5.08)
        else:                                               # test point: pin at the origin, body above it
            a = {"U": 0, "L": 90, "D": 180, "R": 270}[body]; ox, oy = x, y
        if not text: kw = dict(hide_ref=True, hide_val=True)
        elif body == "L": kw = dict(ref_at=(x - 6.8, y - 1.3, "r"), val_at=(x - 6.8, y + 1.3, "r"))
        elif body == "R": kw = dict(ref_at=(x + 6.8, y - 1.3, "l"), val_at=(x + 6.8, y + 1.3, "l"))
        elif body == "U": kw = dict(ref_at=(x + 2.2, y - 5.0, "l"), val_at=(x + 2.2, y - 3.0, "l"))
        else: kw = dict(ref_at=(x + 2.2, y + 5.0, "l"), val_at=(x + 2.2, y + 7.0, "l"))
        return self._sym(ref, ox, oy, a, **kw)

    def fet(self, ref, x, y, drain_left=False, text=True):
        """A power FET drawn as a real MOSFET lying in the path: source left and drain right (or the other way round), gate
        below. y is the height of the path line; x the centre of the symbol."""
        gaps = {"_custom": {"pins": {"G": (-5.08, 0, 0), "D": (2.54, 5.08, 270), "S": (2.54, -5.08, 90)},
                            "gfx": ("Transistor_FET", "Q_NMOS_GSD")}}
        x, y = snap(x), snap(y)
        kw = dict(ref_at=(x, y - 8.0, "c"), val_at=(x, y - 6.0, "c")) if text else dict(hide_ref=True, hide_val=True)
        if drain_left: return self._sym(ref, x, y + 2.54, 90, gaps=gaps, **kw)
        return self._sym(ref, x, y + 2.54, 270, mirror="x", gaps=gaps, **kw)

    def gdrop(self, pl, pin, n=3.81, down=3.81):
        """A pin whose net is a ground-style net: a short stub sideways, then down to the symbol."""
        pinf = [p for p in pl.pins if p["num"] == str(pin) or p["name"] == str(pin)][0]
        x, y = pinf["sx"], pinf["sy"]
        sg = {0: -1, 180: 1}[pinf["ang"]]
        net = self.netof(pl.ref, pinf["num"])
        self.s.path((x, y), (x + sg * n, y), (x + sg * n, y + down))
        self.term(net, x + sg * n, y + down, "D")
        self.use(pl, pin)
        return (x + sg * n, y + down)

    def hrow(self, ref, x, y, left, txt="ab"):
        """Series part lying down on a row; returns the part (l / r are its ends)."""
        return self.h(ref, x, y, left=left, txt=txt)

    @contextmanager
    def group(self, title, pad=4.0, note=None, minw=0, top=None, bottom=None, left=None, right=None):
        """Everything drawn inside the with-block sits in a dashed frame with the title at its top left.
        top / bottom force the frame's top and bottom edge (to line up neighbouring frames)."""
        m = self.s.mark()
        yield
        x0, y0, x1, y1 = self.s.bbox_since(m)
        tw = text_w(title, 2.0)
        fx0, fy0 = x0 - pad, y0 - pad - 8.0
        fx1 = max(x1 + pad, fx0 + tw + 6.0, fx0 + minw)
        fy1 = y1 + pad
        if top is not None: fy0 = top
        if left is not None: fx0 = left
        if right is not None: fx1 = max(right, fx0 + tw + 6.0)
        if bottom is not None: fy1 = max(fy1, bottom)
        self.s.frame(fx0, fy0, fx1, fy1)
        self.s.text(title, fx0 + 2.5, fy0 + 6.4, 2.0)
        self.frames[title] = (fx0, fy0, fx1, fy1)


    # ------------------------------------------------------------------ automatic frame packer
    def scratch(self):
        """A fresh Lay on an empty copy of this sheet: draw a group there to measure it."""
        s = Sheet(self.s.name, self.s.project, self.s.root_uuid, self.s.title)
        comps, nets, nc, glob, cons, disp = self._init
        return Lay(s, comps, nets, nc, glob, cons, dict(disp))

    def pack(self, groups, left=20.32, top=34.0, gap=8.0, flow=0.12, fixed=False):
        """Draw titled groups (title, fn(L, ox, oy)) so the page is as small as it can be.  Each group is drawn once on a
        scratch sheet to measure its frame.  Every order of placement and every page width is then tried with a
        bottom-left skyline placer (each frame goes as high and as far left as it fits, so a short frame fills the pocket
        beside a tall one); a layout costs its paper area (kept near a landscape ratio and clear of the title block),
        with a penalty for every pair of groups that no longer reads in the order given (left to right, top to bottom).
        Frames stacked at the same left edge with nearly equal widths are made flush."""
        import itertools
        O = 25 * G * 4          # scratch origin, on the grid
        dims = []
        for t, fn in groups:
            S = self.scratch()
            with S.group(t):
                fn(S, O, O)
            f = S.frames[t]
            dims.append((f[2] - f[0] + 1.3, f[3] - f[1] + 1.3, f[0] - O, f[1] - O))
        n = len(groups)
        if os.environ.get('PACKDBG'): print('dims', [(round(d[0]), round(d[1])) for d in dims])

        def place(perm, wmax):
            boxes = {}
            for i in perm:
                w, h = dims[i][:2]
                xs = {left} | {b[0] for b in boxes.values()} | {b[2] + gap for b in boxes.values()}
                best = None
                for x in sorted(xs):
                    if x + w > wmax + 1e-6: continue
                    y = top
                    for b in boxes.values():
                        if x < b[2] + gap - 1e-6 and x + w + gap > b[0] + 1e-6: y = max(y, b[3] + gap)
                    if best is None or (y, x) < best[:2]: best = (y, x)
                if best is None: return None
                boxes[i] = (best[1], best[0], best[1] + w, best[0] + h)
            return boxes

        def flat(boxes):
            """make frames stacked on one left edge, with widths within 12 mm, flush"""
            out = dict(boxes)
            for i, b in boxes.items():
                same = [j for j, c in boxes.items() if abs(c[0] - b[0]) < 0.01]
                r = max(boxes[j][2] for j in same)
                for j in same:
                    c = out[j]
                    if r - c[2] < 12.0 and not any(k not in same and boxes[k][0] < r + gap and boxes[k][2] > c[2] - 1e-6 and
                                                  boxes[k][1] < c[3] + gap and boxes[k][3] > c[1] - gap for k in boxes):
                        out[j] = (c[0], c[1], r, c[3])
            return out

        best = None
        wsum = sum(d[0] for d in dims) + gap * n
        for perm in ([tuple(range(n))] if fixed else itertools.permutations(range(n))):
            seen = set()
            wmax = max(d[0] for d in dims) + left
            while wmax < wsum + left + 5:
                boxes = place(perm, wmax)
                wmax += 5.0
                if boxes is None: continue
                key = tuple(boxes[i] for i in range(n))
                if key in seen: continue
                seen.add(key)
                W = max(b[2] for b in boxes.values()); H = max(b[3] for b in boxes.values())
                w, h = fit_paper(list(boxes.values()), W, H)
                ovx = lambda a, b: a[0] < b[2] and b[0] < a[2]
                ovy = lambda a, b: a[1] < b[3] and b[1] < a[3]
                inv = sum(1 for i in range(n) for j in range(i + 1, n)
                          if (boxes[j][3] <= boxes[i][1] and ovx(boxes[i], boxes[j])) or (boxes[j][2] <= boxes[i][0] and ovy(boxes[i], boxes[j]))
                          or (boxes[j][2] <= boxes[i][0] and boxes[j][3] <= boxes[i][1]))
                r_ = w / h
                cost = w * h * ((1 + 0.5 * abs(math.log(r_ / 1.45))) if r_ >= 1.2 else (1 + 2.5 * abs(math.log(r_ / 1.2)))) * (1 + flow * inv)
                if os.environ.get('PACKDBG'): print('cand', perm, round(W), round(H), (w, h), inv, round(cost))
                if best is None or cost < best[0] - 1e-6: best = (cost, boxes)
        boxes = flat(best[1])
        frames = []
        for i, (t, fn) in enumerate(groups):
            x0, y0, x1, y1 = boxes[i]
            w_, h_, dx, dy = dims[i]
            ox, oy = ceilsnap(x0 - dx), ceilsnap(y0 - dy)
            with self.group(t, left=x0, right=x1 - 1.3, top=y0):
                fn(self, ox, oy)
            frames.append(self.frames[t])
        x0, y0, x1, y1 = self.s.content_box()
        self.s.force_paper = fit_paper(frames, x1, y1)
        return self.frames


def ceilsnap(v):
    return round(math.ceil(v / G - 1e-9) * G, 4)


def fit_paper(boxes, W, H, tb=(112, 36), edge=10):
    """Paper size (multiples of 10 mm) that holds content up to (W, H) and keeps the title block clear of every box."""
    w0 = max(150, math.ceil((W + 12) / 10) * 10)
    h0 = max(110, math.ceil((H + 12) / 10) * 10)
    clash = lambda w, h: any(b[2] > w - edge - tb[0] - 2 and b[3] > h - edge - tb[1] - 2 for b in boxes)
    if not clash(w0, h0): return (w0, h0)
    h1 = h0
    while clash(w0, h1): h1 += 10
    w1 = w0
    while clash(w1, h0): w1 += 10
    return (w0, h1) if w0 * h1 <= w1 * h0 else (w1, h0)
