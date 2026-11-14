"""Hand-guided drawing: a small toolkit for sheets whose layout a block describes itself (design/layouts/*.py).

The block says where each part goes and how it is wired, the way a person draws a schematic: parts are placed on the
page, wires are drawn between pin ends, nets that leave the neighbourhood get a label. The toolkit takes care of
everything mechanical: symbol orientation, text placement, junctions, labels on pins nobody wired, paper size, and a
lint pass that lists overlaps (symbol on symbol, wire through a symbol body, text on text or on a wire).
Nothing here decides connectivity: make.sh exports KiCad's own netlist of the result and compares it with the code.
"""
import math
import symlib
from sx import find, first, get, val

G = 1.27
TW = 1.22            # mm per character of 1.27 mm text (estimate used for spacing and lint)

def snap(v):
    return round(round(v / G) * G, 4)

def rot(x, y, a):
    a = a % 360
    if a == 0: xr, yr = x, y
    elif a == 90: xr, yr = -y, x
    elif a == 180: xr, yr = -x, -y
    else: xr, yr = y, -x
    return xr, -yr

DIR = {0: "L", 180: "R", 90: "D", 270: "U"}          # pin angle -> direction pointing away from the body
VEC = {"L": (-1, 0), "R": (1, 0), "U": (0, -1), "D": (0, 1)}
ANG = {"R": 0, "L": 180, "U": 90, "D": 270}          # label angle by the direction it extends

def pin_dir(pin_angle, angle, mirror):
    """Direction a pin's wire leaves in on the page (L R U D), from the pin's angle in the library, the symbol's rotation and mirror."""
    ang = pin_angle
    if mirror and ang in (0, 180): ang = 180 - ang
    v = {0: (-1, 0), 180: (1, 0), 90: (0, -1), 270: (0, 1)}[ang]       # away from the body, symbol space (y up)
    vx, vy = rot(v[0], v[1], angle)
    return "L" if vx < -0.5 else "R" if vx > 0.5 else "U" if vy < -0.5 else "D"

_bbcache = {}
def body_bbox(lib, name, unit):
    """Bounding box of the drawn body (no pins) in symbol coordinates, y up: (x0, y0, x1, y1)."""
    key = (lib, name, unit)
    if key in _bbcache and (lib, name) not in symlib.OVER: return _bbcache[key]
    s = symlib.flat(lib, name)
    xs, ys = [], []
    for u in find(s, "symbol"):
        un, style = (int(v) for v in val(u[1]).rsplit("_", 2)[-2:])
        if style > 1 or un not in (0, unit): continue
        for r in find(u, "rectangle"):
            for k in ("start", "end"):
                a = first(r, k); xs.append(float(a[1])); ys.append(float(a[2]))
        for pl in find(u, "polyline"):
            for pt in find(first(pl, "pts"), "xy"): xs.append(float(pt[1])); ys.append(float(pt[2]))
        for c in find(u, "circle"):
            cx, cy = (float(v) for v in first(c, "center")[1:3]); rr = float(first(c, "radius")[1])
            xs += [cx - rr, cx + rr]; ys += [cy - rr, cy + rr]
        for a in find(u, "arc"):
            for k in ("start", "mid", "end"):
                p = first(a, k); xs.append(float(p[1])); ys.append(float(p[2]))
    bb = (min(xs), min(ys), max(xs), max(ys)) if xs else (-1, -1, 1, 1)
    _bbcache[key] = bb
    return bb


class Sym:
    def __init__(s, ref, x, y, angle, mirror, unit, pins, bbox):
        s.ref, s.x, s.y, s.angle, s.mirror, s.unit = ref, x, y, angle, mirror, unit
        s.pins = pins            # list of dict(num,name,pos,dir,net)
        s.bbox = bbox            # screen box (x0, y0, x1, y1)
        s.a = s.b = None
        s.na = s.nb = None

    def p(s, key):
        key = str(key)
        for q in s.pins:
            if q["num"] == key: return q["pos"]
        for q in s.pins:
            if q["name"] == key: return q["pos"]
        raise KeyError(f"{s.ref} has no pin {key}: {[(q['num'], q['name']) for q in s.pins]}")

    def d(s, key):
        key = str(key)
        for q in s.pins:
            if q["num"] == key or q["name"] == key: return q["dir"]

    def net(s, key):
        key = str(key)
        for q in s.pins:
            if q["num"] == key or q["name"] == key: return q["net"]


class Hand:
    def __init__(s, sheet, comps, nets, nc, cons, refs, glob, short):
        s.sh, s.comps, s.nets, s.cons = sheet, comps, nets, cons
        s.refs = list(refs)
        s.glob, s.short = glob, short
        s.pinnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
        s.ncset = {(r, p) for r, p in nc}
        s.syms = {}
        s.segs = []                # (x1, y1, x2, y2)
        s.pts = set()              # connection points other than wire ends: pins, label anchors, power symbols
        s.texts = []               # (x0, y0, x1, y1, what)
        s.bodies = []              # (x0, y0, x1, y1, ref)
        s.touched = set()
        s.boxes = []
        s.groups = []
        s.npwr = 0
        s.bb = [1e9, 1e9, -1e9, -1e9]

    # ---------------------------------------------------------------- helpers
    def ext(s, x0, y0, x1=None, y1=None):
        x1 = x0 if x1 is None else x1; y1 = y0 if y1 is None else y1
        b = s.bb; b[0] = min(b[0], x0); b[1] = min(b[1], y0); b[2] = max(b[2], x1); b[3] = max(b[3], y1)

    def ends(s, ref):
        """Nets on the pads of a small part, in pad order."""
        pads = sorted({p["num"] for p in symlib.pins(*s.comps[ref]["lib"].split(":"))}, key=lambda n: (len(n), n))
        return [s.pinnet.get((ref, n)) for n in pads]

    def netname(s, n):
        """Accept a net name as written in the block, with or without the block prefix."""
        if n in s.nets: return n
        pre = getattr(s, "prefix", "")
        if pre and pre + n in s.nets: return pre + n
        for k in s.nets:
            if k.split("/")[-1] == n and (not pre or k.startswith(pre) or "/" not in k.lstrip("/")): return k
        raise KeyError(f"no net '{n}'")

    def note_text(s, x, y, w, what):
        s.texts.append((x, y, w, what))

    def text_box(s, x, y, txt, just="left", size=1.27, rot90=False, vert="center"):
        w = len(txt) * TW * size / 1.27; h = size * 1.1
        x0 = x if just == "left" else (x - w if just == "right" else x - w / 2)
        if vert == "bottom": y0, y1 = y - h, y
        else: y0, y1 = y - h / 2, y + h / 2
        return (x0, y0, x0 + w, y1)

    # ---------------------------------------------------------------- symbols
    def _place(s, ref, x, y, angle, mirror, unit, ref_at, val_at, just, hide_ref=False, hide_val=False):
        c = s.comps[ref]
        lib, name = c["lib"].split(":")
        x, y = snap(x), snap(y)
        pins = []
        seen = set()
        for p in symlib.pins(lib, name):
            if p["unit"] not in (0, unit): continue
            px = -p["x"] if mirror else p["x"]
            dx, dy = rot(px, p["y"], angle)
            pos = (snap(x + dx), snap(y + dy))
            dirn = pin_dir(p["angle"], angle, mirror)
            pins.append(dict(num=p["num"], name=p["name"], pos=pos, dir=dirn, net=s.pinnet.get((ref, p["num"])),
                             nc=(ref, p["num"]) in s.ncset, hidden=p["hidden"], drawn=p["drawn"]))
            s.pts.add(pos)
        bx0, by0, bx1, by1 = body_bbox(lib, name, unit)
        corners = []
        for cx, cy in ((bx0, by0), (bx1, by1)):
            dx, dy = rot(-cx if mirror else cx, cy, angle); corners.append((x + dx, y + dy))
        bb = (min(c[0] for c in corners), min(c[1] for c in corners), max(c[0] for c in corners), max(c[1] for c in corners))
        sym = Sym(ref, x, y, angle, mirror, unit, pins, bb)
        s.syms.setdefault(ref, sym)
        s.bodies.append((*bb, ref))
        s.ext(*bb)
        return sym, lib, name

    def _emit(s, sym, lib, name, ref_at, val_at, just, hide_ref=False, hide_val=False):
        c = s.comps[sym.ref]
        s.sh.symbol(lib, name, sym.ref, c["value"], sym.x, sym.y, sym.angle, unit=sym.unit, footprint=c["footprint"],
                    fields=c["fields"], ref_at=ref_at, val_at=val_at, hide_ref=hide_ref, hide_val=hide_val,
                    mirror=sym.mirror, just=just)
        for at, txt, j in ((ref_at, sym.ref, just[0]), (val_at, c["value"], just[1])):
            if at and not (txt == sym.ref and hide_ref) and not (txt == c["value"] and hide_val):
                b = s.text_box(at[0], at[1], txt, j)
                s.texts.append((*b, f"{sym.ref} {'ref' if txt == sym.ref else 'value'}"))
                s.ext(b[0], b[1], b[2], b[3])

    def ic(s, ref, x, y, unit=1, mirror=False, angle=0, ref_at=None, val_at=None, fields="above", hide_val=False, lift=0.0):
        """A part with any number of pins, origin at (x, y). Returns a Sym with .p(pin name or number)."""
        sym, lib, name = s._place(ref, x, y, angle, mirror, unit, None, None, None)
        bx0, by0, bx1, by1 = sym.bbox
        top = min([by0] + [q["pos"][1] for q in sym.pins if q["dir"] == "U"])
        bot = max([by1] + [q["pos"][1] for q in sym.pins if q["dir"] == "D"])
        if ref_at is None:
            if fields == "above": ref_at, val_at = (bx0, top - 4.2 - lift), (bx0, top - 2.6 - lift)
            elif fields == "below": ref_at, val_at = (bx0, bot + 4.4), (bx0, bot + 6.0)
            elif fields == "right": ref_at, val_at = (bx1 + 2.0, (by0 + by1) / 2 - 1.3), (bx1 + 2.0, (by0 + by1) / 2 + 1.3)
            elif fields == "left": ref_at, val_at = (bx0 - 2.0, (by0 + by1) / 2 - 1.3), (bx0 - 2.0, (by0 + by1) / 2 + 1.3)
        j = "right" if fields == "left" and ref_at is not None else "left"
        s._emit(sym, lib, name, ref_at, val_at, (j, j), hide_val=hide_val)
        return sym

    def two(s, ref, x, y, o="v", first=None, txt=None):
        """A two-pad part. o: "v" upright (first net on top) or "h" lying (first net on the left).
        txt: where the text goes: v: "r" or "l" (default r); h: "a" above or "b" below (default a).
        The part's pin ends are sym.a (first net) and sym.b; sym.na / sym.nb are the nets."""
        c = s.comps[ref]
        lib, name = c["lib"].split(":")
        pp = {}
        for p in symlib.pins(lib, name): pp.setdefault(p["num"], p)
        nums = sorted(pp, key=lambda n: (len(n), n))
        e = s.ends(ref)
        if first is not None:
            first = s.netname(first)
            if first not in e: raise KeyError(f"{ref} is not on net {first} (it is on {e})")
        top = nums[0] if (first is None or e[0] == first) else nums[1]
        bot = nums[1] if top == nums[0] else nums[0]
        for a in (0, 90, 180, 270):
            ux, uy = rot(pp[top]["x"], pp[top]["y"], a); dx, dy = rot(pp[bot]["x"], pp[bot]["y"], a)
            if o == "v" and abs(ux) < 0.01 and abs(dx) < 0.01 and uy < dy: break
            if o == "h" and abs(uy) < 0.01 and abs(dy) < 0.01 and ux < dx: break
        else:
            raise ValueError(f"cannot orient {ref}")
        sym, lib, name = s._place(ref, x, y, a, False, 1, None, None, None)
        sym.a = (snap(sym.x + ux), snap(sym.y + uy)); sym.b = (snap(sym.x + dx), snap(sym.y + dy))
        sym.na = s.pinnet.get((ref, top)); sym.nb = s.pinnet.get((ref, bot))
        bx0, by0, bx1, by1 = sym.bbox
        if o == "v":
            side = txt or "r"
            if side == "r": ref_at, val_at, j = (bx1 + 1.3, sym.y - 1.3), (bx1 + 1.3, sym.y + 1.3), "left"
            else: ref_at, val_at, j = (bx0 - 1.3, sym.y - 1.3), (bx0 - 1.3, sym.y + 1.3), "right"
        else:
            side = txt or "a"
            if side == "a": ref_at, val_at, j = (sym.x, by0 - 3.5), (sym.x, by0 - 1.9), "center"
            else: ref_at, val_at, j = (sym.x, by1 + 1.9), (sym.x, by1 + 3.5), "center"
        s._emit(sym, lib, name, ref_at, val_at, (j, j))
        return sym

    def one(s, ref, x, y, wire_dir="D", txt="r"):
        """txt: "r" or "l" beside a pad hanging up or down; "a" above or "b" below a pad with a sideways wire."""
        """A one-pad part (test point, wire pad): its pad end at (x, y), the wire leaving in direction wire_dir."""
        c = s.comps[ref]
        lib, name = c["lib"].split(":")
        p = symlib.pins(lib, name)[0]
        for a in (0, 90, 180, 270):
            if pin_dir(p["angle"], a, False) == wire_dir: break
        dx, dy = rot(p["x"], p["y"], a)
        sym, lib, name = s._place(ref, x - dx, y - dy, a, False, 1, None, None, None)
        sym.a = sym.b = (snap(x), snap(y))
        bx0, by0, bx1, by1 = sym.bbox
        cy = (by0 + by1) / 2; cx = (bx0 + bx1) / 2
        if wire_dir in "UD":
            if txt == "r": ref_at, val_at, j = (bx1 + 1.2, cy - 0.9), (bx1 + 1.2, cy + 0.9), "left"
            else: ref_at, val_at, j = (bx0 - 1.2, cy - 0.9), (bx0 - 1.2, cy + 0.9), "right"
        elif txt == "b":
            ref_at, val_at, j = (cx, by1 + 1.9), (cx, by1 + 3.5), "center"
        elif txt == "l":
            ref_at, val_at, j = (bx0 - 1.2, cy - 0.9), (bx0 - 1.2, cy + 0.9), "right"
        else:
            ref_at, val_at, j = (cx, by0 - 3.5), (cx, by0 - 1.9), "center"
        s._emit(sym, lib, name, ref_at, val_at, (j, j))
        return sym

    # ---------------------------------------------------------------- copper
    def w(s, *pts):
        """Wire along the given points (each a tuple), snapped to the grid. Marks pin ends it touches."""
        pts = [(snap(p[0]), snap(p[1])) for p in pts]
        for a, b in zip(pts, pts[1:]):
            if a == b: continue
            if abs(a[0] - b[0]) > 0.01 and abs(a[1] - b[1]) > 0.01:
                raise ValueError(f"diagonal wire {a} -> {b}")
            s.sh.wire(a[0], a[1], b[0], b[1])
            s.segs.append((a[0], a[1], b[0], b[1]))
            s.ext(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
        for p in (pts[0], pts[-1]): s.touched.add(p)
        return pts[-1]

    def gnd(s, x, y, d="D"):
        """Ground symbol whose pin is at (x, y), hanging in direction d."""
        x, y = snap(x), snap(y)
        s.touched.add((x, y)); s.pts.add((x, y))
        a = {"D": 0, "U": 180, "R": 90, "L": 270}[d]
        s.sh.gnd(x, y, a)
        s.ext(x - 1.5, y, x + 1.5, y + 4.0)
        s.bodies.append((x - 1.3, y + 0.4, x + 1.3, y + 3.0, "GND"))

    def nc(s, x, y):
        x, y = snap(x), snap(y)
        s.touched.add((x, y)); s.pts.add((x, y))
        s.sh.nc(x, y)

    def junction(s, x, y):
        s.sh.junction(x, y)

    def lab(s, x, y, net, d="R"):
        """Net label with its anchor at (x, y) extending in direction d. Global when the net leaves this block."""
        x, y = snap(x), snap(y)
        net = s.netname(net)
        g = net in s.glob
        t = s.short(net)
        s.sh.label(t, x, y, ANG[d], g)
        s.touched.add((x, y))
        w = len(t) * TW + (3.2 if g else 0.4); hgt = 2.6 if g else 1.5
        if d == "R": b = (x, y - (hgt / 2 if g else hgt), x + w, y + (hgt / 2 if g else 0.0))
        elif d == "L": b = (x - w, y - (hgt / 2 if g else hgt), x, y + (hgt / 2 if g else 0.0))
        elif d == "U": b = (x - (hgt / 2 if g else hgt), y - w, x + (hgt / 2 if g else 0.0), y)
        else: b = (x - (hgt / 2 if g else hgt), y, x + (hgt / 2 if g else 0.0), y + w)
        s.texts.append((*b, f"label {t}"))
        s.ext(*b)
        return b

    def label_width(s, net, glob=None):
        net = s.netname(net)
        return len(s.short(net)) * TW + (3.2 if net in s.glob else 0.4)

    def stub(s, pos, d, net, n=2.54):
        """Wire of length n from a pin end in direction d, ending in a label of the net."""
        v = VEC[d]
        e = (pos[0] + v[0] * n, pos[1] + v[1] * n)
        if n: s.w(pos, e)
        s.lab(e[0], e[1], net, d)
        s.touched.add(pos)
        return e

    def tie(s, pos, net, d="L", n=2.54):
        """Pin end to a net: ground symbol for GND, label otherwise (or a no-connect flag when net is None)."""
        if net is None: s.nc(*pos); return pos
        if net == "GND":
            v = VEC[d]
            e = (pos[0] + v[0] * n, pos[1] + v[1] * n)
            if d in "UD":
                s.w(pos, e) if n else None
                s.gnd(e[0], e[1], "D" if d == "D" else "U")
            else:
                e2 = (e[0], e[1] + 2.54)
                s.w(pos, e, e2); s.gnd(e2[0], e2[1], "D")
            return e
        return s.stub(pos, d, net, n)

    def drop(s, pos, net, d="R", n=2.54):
        """Down from a pin end by n, then a label of the net extending sideways (d = L or R). For the bottom of a hanging part."""
        e = (pos[0], pos[1] + n)
        if n: s.w(pos, e)
        s.lab(e[0], e[1], net, d)
        return e

    def group(s, title, margin=5.0):
        """with h.group("title"): ... draws a dashed frame around what the block draws inside, titled above its top left corner."""
        import contextlib
        @contextlib.contextmanager
        def cm():
            saved = s.bb
            s.bb = [1e9, 1e9, -1e9, -1e9]
            try: yield
            finally:
                x0, y0, x1, y1 = s.bb
                s.bb = saved
                x0 -= margin; y0 -= margin; x1 += margin; y1 += margin
                s.box(x0, y0, x1, y1)
                s.title(x0, y0 - 1.5, title)
                s.groups.append((title, x0, y0, x1, y1))
        return cm()

    def tapdown(s, x, y, net, n=5.08, run=2.54):
        """From the point (x, y) on a wire: down n, then right by run, then a label. A short branch that names a net."""
        s.w((x, y), (x, y + n), (x + run, y + n))
        s.lab(x + run, y + n, net, "R")

    def text(s, x, y, txt, size=1.27, just="left"):
        s.sh.text(txt, x, y, size)
        b = s.text_box(snap(x), snap(y), txt, "left", size, vert="bottom")
        s.texts.append((*b, "text"))
        s.ext(*b)

    def title(s, x, y, txt):
        s.sh.text(txt, x, y, 2.0)
        b = s.text_box(snap(x), snap(y), txt, "left", 2.0, vert="bottom")
        b = (b[0], b[1], b[0] + len(txt) * 1.75, b[3])
        s.texts.append((*b, "title"))
        s.ext(*b)

    def note(s, x, y, lines, size=1.27):
        for i, t in enumerate(lines):
            s.text(x, y + i * 2.54, t, size)

    def box(s, x0, y0, x1, y1, title=None):
        """A dashed frame around a group, with its title inside the top left corner."""
        x0, y0, x1, y1 = snap(x0), snap(y0), snap(x1), snap(y1)
        import uuid
        s.sh.items.append(f'(rectangle (start {x0} {y0}) (end {x1} {y1}) (stroke (width 0.2) (type dash) (color 110 110 110 1)) (fill (type none)) '
                          f'(uuid "{uuid.uuid5(uuid.NAMESPACE_URL, f"{s.sh.name}|box|{x0}|{y0}|{x1}|{y1}")}"))')
        s.boxes.append((x0, y0, x1, y1))
        s.ext(x0, y0, x1, y1)
        if title: s.title(x0, y0 - 1.5, title)

    def lane(s, pos, d, parts, net, end="label", gap=2.54, step=2.54, txt="a", endgap=2.54):
        """Series parts lying in a row straight out of a pin end (direction d = L or R), the way a person draws a pin with
        a resistor or two on it. net: the net on the pin. end: "label" (a label of the last net), "gnd", "none".
        Returns (end point, [Sym], last net)."""
        v = VEC[d]
        x, y = pos
        cur = s.netname(net)
        out = []
        for i, ref in enumerate(parts):
            e = s.ends(ref)
            other = e[0] if e[1] == cur else e[1]
            g = gap if i == 0 else step
            cx = x + v[0] * (g + 3.81)
            sym = s.two(ref, cx, y, "h", first=(other if d == "L" else cur), txt=txt)
            near, far = (sym.b, sym.a) if d == "L" else (sym.a, sym.b)
            s.w((x, y), near)
            x = far[0]; cur = other; out.append(sym)
        if end == "label": s.stub((x, y), d, cur, endgap); x += v[0] * endgap
        elif end == "gnd": s.tie((x, y), "GND", d, endgap)
        return (x, y), out, cur

    # ---------------------------------------------------------------- patterns
    def hang(s, rail_y, x, ref, rail_net, other=None, txt="r", dy=None, up=False, ld="R"):
        """A part hanging from a horizontal rail at rail_y, at column x, ending in ground or a label. up=True: standing on the
        rail instead (ground symbol turned up). Returns the Sym."""
        rail_net = s.netname(rail_net)
        gap = dy if dy is not None else 2.54
        if not up:
            t = s.two(ref, x, snap(rail_y + 3.81 + gap), "v", first=rail_net, txt=txt)
            s.w((x, rail_y), t.a)
            far, on, d, v = t.b, t.nb, "D", 1
        else:
            e = s.ends(ref); on0 = e[0] if e[1] == rail_net else e[1]
            t = s.two(ref, x, snap(rail_y - 3.81 - gap), "v", first=on0, txt=txt)
            s.w((x, rail_y), t.b)
            far, on, d, v = t.a, t.na, "U", -1
        if on == "GND": s.gnd(far[0], far[1], d)
        elif other == "none": pass
        else: s.w(far, (far[0], far[1] + v * 2.54)); s.lab(far[0], far[1] + v * 2.54, on, ld)
        return t

    # ---------------------------------------------------------------- finish
    def finish(s, name=""):
        missing = [r for r in s.refs if r not in s.syms]
        import os
        if missing and os.environ.get("HAND_PARTIAL"): print(f"  [{name}] PARTIAL: not placed yet: {' '.join(missing)}")
        elif missing: raise RuntimeError(f"{name}: layout left parts unplaced: {missing}")
        extra = [r for r in s.syms if r not in s.refs]
        if extra: raise RuntimeError(f"{name}: layout placed parts of other blocks: {extra}")
        # pins nobody wired get a flag or a label on a short stub
        for ref, sym in s.syms.items():
            if len(sym.pins) <= 2 and sym.a is not None: continue
            done = set()
            for q in sym.pins:
                if q["pos"] in s.touched or q["pos"] in done or s.on_wire(q["pos"]): continue
                done.add(q["pos"])
                if q["hidden"] and any(o["pos"] == q["pos"] and not o["hidden"] for o in sym.pins): continue
                n = q["net"]
                s.auto = getattr(s, "auto", []) + [f"{ref}.{q['name'] or q['num']}"]
                if q["nc"] or n is None: s.nc(*q["pos"])
                else:
                    s.tie(q["pos"], n if n != "GND" else "GND", q["dir"])
        s.junctions()
        s.lint(name)

    def on_wire(s, p):
        x, y = p
        return any((abs(x1 - x2) < 0.01 and abs(x - x1) < 0.01 and min(y1, y2) - 0.01 <= y <= max(y1, y2) + 0.01) or
                   (abs(y1 - y2) < 0.01 and abs(y - y1) < 0.01 and min(x1, x2) - 0.01 <= x <= max(x1, x2) + 0.01)
                   for x1, y1, x2, y2 in s.segs)

    def junctions(s):
        ends, mids = {}, {}
        for x1, y1, x2, y2 in s.segs:
            for p in ((x1, y1), (x2, y2)): ends[p] = ends.get(p, 0) + 1
        for p in s.pts: ends[p] = ends.get(p, 0) + 1
        done = set()
        for p, n in ends.items():
            x, y = p
            mid = sum(1 for x1, y1, x2, y2 in s.segs
                      if ((abs(x1 - x2) < 0.01 and abs(x - x1) < 0.01 and min(y1, y2) + 0.01 < y < max(y1, y2) - 0.01) or
                          (abs(y1 - y2) < 0.01 and abs(y - y1) < 0.01 and min(x1, x2) + 0.01 < x < max(x1, x2) - 0.01)))
            if (mid >= 1 and n >= 1) or n >= 3:
                if p not in done: s.sh.junction(x, y); done.add(p)

    # ---------------------------------------------------------------- lint
    def lint(s, name):
        out = []
        sh = lambda b, d: (b[0] + d, b[1] + d, b[2] - d, b[3] - d)
        inter = lambda a, b: a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
        bod = [b for b in s.bodies if b[4] != "GND"]
        for i, a in enumerate(bod):
            for b in bod[i + 1:]:
                if a[4] != b[4] and inter(sh(a, 0.2), sh(b, 0.2)): out.append(f"symbols overlap: {a[4]} / {b[4]}")
        for x1, y1, x2, y2 in s.segs:
            sb = (min(x1, x2) - 0.01, min(y1, y2) - 0.01, max(x1, x2) + 0.01, max(y1, y2) + 0.01)
            for b in s.bodies:
                if inter(sb, sh(b[:4], 0.3)): out.append(f"wire ({x1:.1f},{y1:.1f})-({x2:.1f},{y2:.1f}) crosses body of {b[4]}")
        for i, a in enumerate(s.groups):
            for b in s.groups[i + 1:]:
                if inter(a[1:], b[1:]): out.append(f"frames overlap: {a[0]} / {b[0]}")
        tx = s.texts
        for i, a in enumerate(tx):
            for b in tx[i + 1:]:
                if inter(sh(a[:4], 0.25), sh(b[:4], 0.25)): out.append(f"text overlaps text: {a[4]} / {b[4]}")
            if a[4].startswith("title"): continue
            for x1, y1, x2, y2 in s.segs:
                sb = (min(x1, x2) - 0.01, min(y1, y2) - 0.01, max(x1, x2) + 0.01, max(y1, y2) + 0.01)
                if inter(sh(a[:4], 0.35), sb): out.append(f"text on wire ({x1:.1f},{y1:.1f})-({x2:.1f},{y2:.1f}): {a[4]}")
            for b in s.bodies:
                if a[4].startswith(b[4] + " "): continue
                if inter(sh(a[:4], 0.3), sh(b[:4], 0.2)): out.append(f"text on symbol {b[4]}: {a[4]} at ({a[0]:.0f},{a[1]:.0f})")
        # a pin end lying on another wire's interior
        for q in s.pts:
            for x1, y1, x2, y2 in s.segs:
                x, y = q
                if (abs(x1 - x2) < 0.01 and abs(x - x1) < 0.01 and min(y1, y2) + 0.01 < y < max(y1, y2) - 0.01) or \
                   (abs(y1 - y2) < 0.01 and abs(y - y1) < 0.01 and min(x1, x2) + 0.01 < x < max(x1, x2) - 0.01):
                    pass     # a T onto a wire is a junction: fine
        s.problems = list(dict.fromkeys(out))
        auto = getattr(s, "auto", [])
        print(f"  [{name}] {len(s.syms)} parts, {len(s.segs)} wire segments, {len(s.problems)} lint, {len(auto)} pins auto-labelled")
        for p in s.problems[:40]: print("     lint:", p)
        if auto: print("     auto-labelled pins:", " ".join(auto[:40]))
