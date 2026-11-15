"""Schematic canvas for draw.py: figures made of wires, symbols, labels and text that can be measured, moved and
joined, then written as a KiCad sheet. Nothing here knows about the circuit.

A Fig is a list of items in millimetres on the 1.27 mm grid (y grows downward). Every item carries the boxes it
covers on paper, so a figure can be measured (bbox), tested against another (hits) and checked for clutter (lint).
Junction dots are worked out when the sheet is written, from where wire ends and pins meet.
"""
import uuid, math
import symlib
from sx import find, first, get, val

NS = uuid.UUID("6f1c2b1e-58a5-4c6e-9a59-0d5a1f2b7c11")
G = 1.27
VERSION = "20260306"

def uid(*key):
    return str(uuid.uuid5(NS, "|".join(str(k) for k in key)))

def snap(v):
    return round(round(v / G) * G, 4)

def snap_up(v):
    return round(math.ceil(v / G - 1e-6) * G, 4)

def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'

def dump(node):
    if isinstance(node, tuple):
        return q(node[1])
    if isinstance(node, str):
        return node
    return "(" + " ".join(dump(c) for c in node) + ")"

# ---- text width of KiCad's stroke font, measured from a render (mm per character at 1.27 mm size) ----
_CW = {}
def _cw(chars, w):
    for c in chars: _CW[c] = w
_cw("ABCDGHKNOPQRSUXZ", 1.36); _cw("EFLTVYJ", 1.15); _cw("MW", 1.55); _cw("I", 0.7)
_cw("abdeghnopqucksxz", 1.2); _cw("ftr", 0.85); _cw("ijl", 0.72); _cw("vy", 1.05); _cw("mw", 1.6)
_cw("0123456789", 1.28); _cw("_ ", 1.05); _cw("-+=~", 1.65); _cw(".,:;'|!", 0.68); _cw("()[]", 0.92); _cw("/\\", 1.4)
_cw("%&@#", 1.55)

def tw(s, size=1.27):
    return sum(_CW.get(c, 1.25) for c in str(s)) * size / 1.27

def xf(x, y, angle=0, mirror=False):
    """Symbol coordinates (y up) -> offset on the sheet (y down) for a symbol placed at this angle, then mirrored
    left-right. This is the order KiCad applies them in (checked against its netlist)."""
    a = angle % 360
    if a == 0: xr, yr = x, y
    elif a == 90: xr, yr = -y, x
    elif a == 180: xr, yr = -x, -y
    else: xr, yr = y, -x
    return (-xr if mirror else xr), -yr

_bb = {}
def body_bbox(lib, name, unit=1):
    """Bounding box of the drawn body of a symbol unit, in symbol coordinates (y up): (x0, y0, x1, y1)."""
    key = (lib, name, unit)
    if key in _bb: return _bb[key]
    s = symlib.flat(lib, name); pts = []
    for u in find(s, "symbol"):
        un, style = (int(v) for v in val(u[1]).rsplit("_", 2)[-2:])
        if style > 1 or un not in (0, unit): continue
        for g in u[2:]:
            if not isinstance(g, list): continue
            if g[0] == "rectangle":
                for k in ("start", "end"):
                    a = first(g, k); pts.append((float(a[1]), float(a[2])))
            elif g[0] in ("polyline", "bezier"):
                for p in find(first(g, "pts"), "xy"): pts.append((float(p[1]), float(p[2])))
            elif g[0] == "circle":
                c = first(g, "center"); r = float(get(g, "radius"))
                pts += [(float(c[1]) - r, float(c[2]) - r), (float(c[1]) + r, float(c[2]) + r)]
            elif g[0] == "arc":
                for k in ("start", "mid", "end"):
                    a = first(g, k); pts.append((float(a[1]), float(a[2])))
    if not pts:
        pts = [(p["x"], p["y"]) for p in symlib.pins(lib, name)] or [(0, 0)]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    _bb[key] = (min(xs), min(ys), max(xs), max(ys))
    return _bb[key]

def sbox(lib, name, x, y, angle=0, mirror=False, unit=1):
    """Body box on the sheet of a symbol placed at (x, y)."""
    b = body_bbox(lib, name, unit)
    cs = [xf(px, py, angle, mirror) for px in (b[0], b[2]) for py in (b[1], b[3])]
    return (x + min(c[0] for c in cs), y + min(c[1] for c in cs), x + max(c[0] for c in cs), y + max(c[1] for c in cs))

PWR = {"gnd": ("power", "GND"), "gndref": ("power", "GNDREF"), "flag": ("power", "VCC")}


class Fig:
    def __init__(self):
        self.items, self.ports = [], {}

    def add(self, kind, pts, boxes=(), **kw):
        it = dict(kind=kind, pts=[(snap(x), snap(y)) if i < kw.get("ngrid", 99) else (x, y) for i, (x, y) in enumerate(pts)],
                  boxes=[tuple(b) for b in boxes], **kw)
        self.items.append(it)
        return it

    # ---- primitives ----
    def wire(self, x1, y1, x2, y2, net=None):
        x1, y1, x2, y2 = snap(x1), snap(y1), snap(x2), snap(y2)
        if (x1, y1) == (x2, y2): return
        if x1 != x2 and y1 != y2:
            raise ValueError(f"slanted wire {x1},{y1} to {x2},{y2} on net {net}")
        self.add("wire", [(x1, y1), (x2, y2)], [(min(x1, x2) - .12, min(y1, y2) - .12, max(x1, x2) + .12, max(y1, y2) + .12, "wire")], net=net)

    def path(self, pts, net=None):
        for a, b in zip(pts, pts[1:]): self.wire(a[0], a[1], b[0], b[1], net)

    def nc(self, x, y):
        self.add("nc", [(x, y)], [(x - .7, y - .7, x + .7, y + .7, "mark")])

    def label(self, text, x, y, d="R", glob=False, net=None, shape="passive"):
        """Net label whose text runs away from (x, y) in direction d: R, L, U or D."""
        w = tw(text)
        if glob:
            w += 3.2
            box = {"R": (x, y - 1.25, x + w, y + 1.25), "L": (x - w, y - 1.25, x, y + 1.25),
                   "U": (x - 1.25, y - w, x + 1.25, y), "D": (x - 1.25, y, x + 1.25, y + w)}[d]
        else:
            box = {"R": (x, y - 2.0, x + w + .3, y + .2), "L": (x - w - .3, y - 2.0, x, y + .2),
                   "U": (x - 2.0, y - w - .3, x + .2, y), "D": (x - 2.0, y, x + .2, y + w + .3)}[d]
        self.add("label", [(x, y)], [box + ("label",)], text=text, d=d, glob=glob, net=net, shape=shape)

    def power(self, kind, name, x, y, d="D"):
        """Power symbol. kind gnd (hollow triangle), gndref (three bars, named: a ground of its own) or flag (arrow up, named)."""
        x, y = snap(x), snap(y)
        if kind == "flag":
            ang, box, tp, ts = 0, (x - .8, y - 2.6, x + .8, y), (x, y - 3.6), 1.27
            show = True
        else:
            ang = {"D": 0, "L": 270, "R": 90, "U": 180}[d]
            box = {"D": (x - 1.3, y, x + 1.3, y + 2.6), "L": (x - 2.6, y - 1.3, x, y + 1.3), "R": (x, y - 1.3, x + 2.6, y + 1.3),
                   "U": (x - 1.3, y - 2.6, x + 1.3, y)}[d]
            show, ts = kind == "gndref", 1.0
            w = tw(name, ts)
            tp = {"D": (x, y + 3.7), "L": (x - 3.3 - w / 2, y), "R": (x + 3.3 + w / 2, y), "U": (x, y - 3.7)}[d]
        boxes = [box + ("sym",)]
        if show:
            w = tw(name, ts)
            boxes.append((tp[0] - w / 2, tp[1] - ts * .65, tp[0] + w / 2, tp[1] + ts * .65, "text"))
        self.add("pwr", [(x, y), tp], boxes, ngrid=1, pkind=kind, name=name, angle=ang, show=show, tsize=ts)

    def text(self, s, x, y, size=1.27, bold=False):
        """Free text, left bottom corner at (x, y). Lines are separated by newlines."""
        lines = str(s).split("\n")
        w = max(tw(l, size) for l in lines)
        h = len(lines) * size * 1.62
        self.add("text", [(x, y)], [(x, y - h, x + w, y + .2, "text")], text=s, size=size, bold=bold)

    def rect(self, x0, y0, x1, y1):
        self.add("rect", [(x0, y0), (x1, y1)], [])

    def sym(self, lib, name, ref, value, x, y, angle=0, mirror=False, unit=1, texts=None, footprint="", fields=None, tipnets=None):
        """Place a symbol. texts: {"ref": (x, y), "val": (x, y)} centres of the visible fields; a missing one is hidden.
        Returns {pin number: (x, y)}."""
        x, y = snap(x), snap(y)
        texts = texts or {}
        boxes = [sbox(lib, name, x, y, angle, mirror, unit) + ("sym",)]
        pts = [(x, y)]
        for k, s in (("ref", ref), ("val", value)):
            if k in texts:
                tx, ty = texts[k]; w = tw(s)
                boxes.append((tx - w / 2, ty - .85, tx + w / 2, ty + .85, "text"))
                pts.append((tx, ty))
            else:
                pts.append((x, y))
        out, tips = {}, []
        for p in symlib.pins(lib, name):
            if p["unit"] not in (0, unit): continue
            dx, dy = xf(p["x"], p["y"], angle, mirror)
            out[p["num"]] = (snap(x + dx), snap(y + dy))
            tips.append((p["num"], len(pts)))
            pts.append((x + dx, y + dy))
        self.add("sym", pts, boxes, ngrid=1, lib=lib, name=name, ref=ref, value=value, angle=angle, mirror=mirror, unit=unit,
                 show=[k in texts for k in ("ref", "val")], footprint=footprint, fields=fields or {}, tips=tips, tipnets=tipnets or {})
        return out

    # ---- composition ----
    def place(self, other, dx=0, dy=0):
        dx, dy = snap(dx), snap(dy)
        for it in other.items:
            n = dict(it)
            n["pts"] = [(round(x + dx, 4), round(y + dy, 4)) for x, y in it["pts"]]
            n["boxes"] = [(b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy, b[4]) for b in it["boxes"]]
            self.items.append(n)
        for k, (x, y) in other.ports.items():
            self.ports.setdefault(k, (snap(x + dx), snap(y + dy)))

    def boxes(self):
        return [b for it in self.items for b in it["boxes"]]

    def bbox(self):
        bs = self.boxes()
        if not bs: return (0.0, 0.0, 0.0, 0.0)
        return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))

    def hits(self, other, dx=0, dy=0, pad=0.6):
        """True when other, moved by (dx, dy), would touch anything in this figure."""
        mine = self.boxes()
        for b in other.boxes():
            x0, y0, x1, y1 = b[0] + dx - pad, b[1] + dy - pad, b[2] + dx + pad, b[3] + dy + pad
            for m in mine:
                if x0 < m[2] and m[0] < x1 and y0 < m[3] and m[1] < y1: return True
        return False

    def hit_box(self, box, pad=0.3, skip=("wire",)):
        x0, y0, x1, y1 = box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad
        for m in self.boxes():
            if m[4] in skip: continue
            if x0 < m[2] and m[0] < x1 and y0 < m[3] and m[1] < y1: return True
        return False


def lint(fig, name):
    """Clutter and short-circuit report for a finished sheet. Returns (list of problems, counts)."""
    probs = []
    wires = [it for it in fig.items if it["kind"] == "wire"]
    def on(p, w, inner=False):
        (x1, y1), (x2, y2) = w["pts"]
        if x1 == x2:
            if abs(p[0] - x1) > 1e-6: return False
            lo, hi = min(y1, y2), max(y1, y2); v = p[1]
        else:
            if abs(p[1] - y1) > 1e-6: return False
            lo, hi = min(x1, x2), max(x1, x2); v = p[0]
        return lo + 1e-6 < v < hi - 1e-6 if inner else lo - 1e-6 <= v <= hi + 1e-6
    contacts = []
    for it in fig.items:
        if it["kind"] == "wire":
            contacts += [(p, it["net"], "wire end") for p in it["pts"]]
        elif it["kind"] == "sym":
            for num, i in it["tips"]:
                contacts.append(((snap(it["pts"][i][0]), snap(it["pts"][i][1])), it["tipnets"].get(num), f"{it['ref']}.{num}"))
        elif it["kind"] == "label":
            contacts.append((it["pts"][0], it["net"], "label " + it["text"]))
    for p, net, what in contacts:
        for w in wires:
            if w["net"] != net and net is not None and w["net"] is not None and on(p, w):
                probs.append(f"SHORT {name}: {what} of net {net} touches a wire of net {w['net']} at {p}")
    seen = {}
    for p, net, what in contacts:
        if what == "wire end" or net is None: continue
        if p in seen and seen[p][0] != net and not what.startswith("label") :
            probs.append(f"SHORT {name}: {what} ({net}) and {seen[p][1]} ({seen[p][0]}) at the same point {p}")
        seen.setdefault(p, (net, what))
    # clutter: overlapping boxes of different items
    flat = [(b, i) for i, it in enumerate(fig.items) for b in it["boxes"]]
    flat.sort(key=lambda t: t[0][0])
    counts = {}
    for a in range(len(flat)):
        ba, ia = flat[a]
        for b in range(a + 1, len(flat)):
            bb, ib = flat[b]
            if bb[0] > ba[2] - .25: break
            if ia == ib: continue
            if ba[1] < bb[3] - .25 and bb[1] < ba[3] - .25 and min(ba[2], bb[2]) - max(ba[0], bb[0]) > .25:
                pair = tuple(sorted((ba[4], bb[4])))
                if pair in (("wire", "wire"), ("mark", "wire"), ("label", "wire")): continue
                if pair == ("sym", "wire"):
                    # a wire may end on the edge of a body (pin of zero length) but not run through it
                    w, s = (ba, bb) if ba[4] == "wire" else (bb, ba)
                    if min(w[2], s[2]) - max(w[0], s[0]) < .6 or min(w[3], s[3]) - max(w[1], s[1]) < .6: continue
                counts[pair] = counts.get(pair, 0) + 1
                ta, tb = fig.items[ia], fig.items[ib]
                d = lambda t: t.get("ref") or t.get("text") or t.get("name") or t.get("net") or t["kind"]
                probs.append(f"clutter {name}: {pair[0]} on {pair[1]}: {d(ta)} / {d(tb)} near ({max(ba[0], bb[0]):.0f}, {max(ba[1], bb[1]):.0f})")
    return probs, counts


class Sheet:
    """One KiCad sheet file, written from a finished Fig."""
    def __init__(self, name, project, root_uuid, title, num=1):
        self.name, self.project, self.root_uuid, self.title, self.num = name, project, root_uuid, title, num
        self.uuid = uid("sheet", name)
        self.libs = {}

    def lib(self, lib, name):
        key = f"{lib}:{name}"
        if key not in self.libs:
            s = symlib.flat(lib, name)
            s[1] = ("s", key)
            self.libs[key] = dump(s)
        return key

    def split_wires(self, fig):
        """Cut every wire where a pin, a power symbol, a label or the end of another wire lies on its run, so that
        KiCad sees the connection the drawing shows."""
        pts = set()
        for it in fig.items:
            if it["kind"] == "wire": pts.update(it["pts"])
            elif it["kind"] == "sym": pts.update((snap(it["pts"][i][0]), snap(it["pts"][i][1])) for _, i in it["tips"])
            elif it["kind"] in ("pwr", "label"): pts.add(it["pts"][0])
        byx, byy = {}, {}
        for p in pts: byx.setdefault(p[0], []).append(p[1]); byy.setdefault(p[1], []).append(p[0])
        out = []
        for it in fig.items:
            if it["kind"] != "wire": out.append(it); continue
            (x1, y1), (x2, y2) = it["pts"]
            if x1 == x2:
                cuts = sorted({y for y in byx.get(x1, ()) if min(y1, y2) < y < max(y1, y2)} | {y1, y2})
                segs = [((x1, a), (x1, b)) for a, b in zip(cuts, cuts[1:])]
            else:
                cuts = sorted({x for x in byy.get(y1, ()) if min(x1, x2) < x < max(x1, x2)} | {x1, x2})
                segs = [((a, y1), (b, y1)) for a, b in zip(cuts, cuts[1:])]
            for a, b in segs:
                n = dict(it); n["pts"] = [a, b]; out.append(n)
        fig.items = out

    def junctions(self, fig):
        """Points that need a dot: a wire end or pin on the run of another wire, or three or more ends meeting."""
        wires = [it["pts"] for it in fig.items if it["kind"] == "wire"]
        ends = {}
        for a, b in wires:
            ends[a] = ends.get(a, 0) + 1; ends[b] = ends.get(b, 0) + 1
        for it in fig.items:
            if it["kind"] == "sym":
                for p in {(snap(it["pts"][i][0]), snap(it["pts"][i][1])) for _, i in it["tips"]}:     # stacked pins count once
                    if p in ends: ends[p] += 1
            elif it["kind"] == "pwr":
                p = it["pts"][0]
                if p in ends: ends[p] += 1
        hs = {}; vs = {}
        for a, b in wires:
            if a[1] == b[1]: hs.setdefault(a[1], []).append((min(a[0], b[0]), max(a[0], b[0])))
            else: vs.setdefault(a[0], []).append((min(a[1], b[1]), max(a[1], b[1])))
        out = set()
        for p, n in ends.items():
            inner = any(lo + 1e-6 < p[0] < hi - 1e-6 for lo, hi in hs.get(p[1], ())) or any(lo + 1e-6 < p[1] < hi - 1e-6 for lo, hi in vs.get(p[0], ()))
            if inner or n >= 3: out.add(p)
        return out

    def write(self, fig, path, min_w=180, min_h=120):
        F = lambda s, j="": f"(effects (font (size {s} {s})){(' ' + j) if j else ''})"
        items, npwr = [], 0
        hid = lambda h: " (hide yes)" if h else ""
        inst = lambda ref, unit: (f'(instances (project {q(self.project)} (path {q("/" + self.root_uuid + "/" + self.uuid)} '
                                  f'(reference {q(ref)}) (unit {unit}))))')
        self.split_wires(fig)
        for it in fig.items:
            k, pts = it["kind"], it["pts"]
            if k == "wire":
                (x1, y1), (x2, y2) = pts
                items.append(f'(wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default)) (uuid {q(uid(self.name, "w", x1, y1, x2, y2))}))')
            elif k == "nc":
                x, y = pts[0]
                items.append(f'(no_connect (at {x} {y}) (uuid {q(uid(self.name, "nc", x, y))}))')
            elif k == "label":
                x, y = pts[0]; ang = {"R": 0, "U": 90, "L": 180, "D": 270}[it["d"]]
                if it["glob"]:
                    j = "(justify left)" if it["d"] in "RU" else "(justify right)"
                    items.append(f'(global_label {q(it["text"])} (shape {it["shape"]}) (at {x} {y} {ang}) {F(1.27, j)} '
                                 f'(uuid {q(uid(self.name, "gl", it["text"], x, y))}) (property "Intersheetrefs" "${{INTERSHEET_REFS}}" '
                                 f'(at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes))))')
                else:
                    j = "(justify left bottom)" if it["d"] in "RU" else "(justify right bottom)"
                    items.append(f'(label {q(it["text"])} (at {x} {y} {ang}) {F(1.27, j)} (uuid {q(uid(self.name, "l", it["text"], x, y))}))')
            elif k == "text":
                x, y = pts[0]; s = it["size"]
                b = " (bold yes)" if it.get("bold") else ""
                items.append(f'(text {q(it["text"])} (exclude_from_sim no) (at {x} {y} 0) (effects (font (size {s} {s}){b}) (justify left bottom)) '
                             f'(uuid {q(uid(self.name, "t", it["text"], x, y))}))')
            elif k == "rect":
                (x0, y0), (x1, y1) = pts
                items.append(f'(rectangle (start {x0} {y0}) (end {x1} {y1}) (stroke (width 0) (type dot)) (fill (type none)) '
                             f'(uuid {q(uid(self.name, "r", x0, y0, x1, y1))}))')
            elif k == "pwr":
                npwr += 1
                lib, name = PWR[it["pkind"]]
                lid = self.lib(lib, name)
                (x, y), (tx, ty) = pts
                ref = f"#PWR{self.num:02d}{npwr:03d}"
                fa = 90 if it["angle"] in (90, 270) else 0
                pin = symlib.pins(lib, name)[0]["drawn"]
                items.append(
                    f'(symbol (lib_id {q(lid)}) (at {x} {y} {it["angle"]}) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) '
                    f'(uuid {q(uid(self.name, "pwr", npwr))}) '
                    f'(property "Reference" {q(ref)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes))) '
                    f'(property "Value" {q(it["name"])} (at {tx:.2f} {ty:.2f} {fa}) (effects (font (size {it["tsize"]} {it["tsize"]})){hid(not it["show"])})) '
                    f'(property "Footprint" "" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes))) '
                    f'(pin {q(pin)} (uuid {q(uid(self.name, "pwrpin", npwr))})) {inst(ref, 1)})')
            elif k == "sym":
                lid = self.lib(it["lib"], it["name"])
                (x, y), (rx, ry), (vx, vy) = pts[:3]
                ang, unit, ref = it["angle"], it["unit"], it["ref"]
                fa = 90 if ang in (90, 270) else 0
                props = [f'(property "Reference" {q(ref)} (at {rx:.2f} {ry:.2f} {fa}) (effects (font (size 1.27 1.27)){hid(not it["show"][0])}))',
                         f'(property "Value" {q(it["value"])} (at {vx:.2f} {vy:.2f} {fa}) (effects (font (size 1.27 1.27)){hid(not it["show"][1])}))',
                         f'(property "Footprint" {q(it["footprint"])} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))']
                for fk, fv in it["fields"].items():
                    props.append(f'(property {q(fk)} {q(fv)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
                pins = " ".join(f'(pin {q(p)} (uuid {q(uid(self.name, ref, unit, "pin", p))}))'
                                for p in sorted({p["drawn"] for p in symlib.pins(it["lib"], it["name"]) if p["unit"] in (0, unit)}))
                items.append(
                    f'(symbol (lib_id {q(lid)}) (at {x} {y} {ang}){" (mirror y)" if it["mirror"] else ""} (unit {unit}) (exclude_from_sim no) '
                    f'(in_bom yes) (on_board yes) (dnp no) (uuid {q(uid(self.name, "sym", ref, unit))}) {" ".join(props)} {pins} {inst(ref, unit)})')
        for x, y in sorted(self.junctions(fig)):
            items.append(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid {q(uid(self.name, "j", x, y))}))')
        bb = fig.bbox()
        w = max(min_w, math.ceil((bb[2] + 14) / 5) * 5)
        h = max(min_h, math.ceil((bb[3] + 14) / 5) * 5)
        # keep the drawing clear of the title block in the bottom right corner
        low = max([b[3] for b in fig.boxes() if b[2] > w - 125] + [0])
        h = max(h, math.ceil((low + 51) / 5) * 5)
        out = [f'(kicad_sch (version {VERSION}) (generator "p2p_draw") (generator_version "10.0") (uuid {q(self.uuid)}) '
               f'(paper "User" {w} {h}) (title_block (title {q(self.title)}) (comment 1 "Generated from code. Do not edit: change the block source and rebuild."))',
               "(lib_symbols " + "\n".join(self.libs.values()) + ")"]
        out += items
        out.append("(embedded_fonts no))")
        open(path, "w").write("\n".join(out) + "\n")
        return w, h
