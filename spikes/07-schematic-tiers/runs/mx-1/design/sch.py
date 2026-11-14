"""Low-level schematic writer: text metrics, symbol geometry, and a Sheet that records every item with an exact
bounding box so a drawing can be measured, moved, checked for clutter and given its junctions automatically.

Coordinates are millimetres, y down, on KiCad's 1.27 mm grid. A Sheet has a translation (tx, ty) that is added to
everything drawn, so an assembly drawn at the origin on a scratch sheet can be measured and then drawn again where
it is wanted.
"""
import math, os, uuid
import symlib
from sx import find, first, get, val

NS = uuid.UUID("6f1c2b1e-58a5-4c6e-9a59-0d5a1f2b7c11")
G = 1.27
VERSION = "20260306"
TS = 1.27                      # text size used everywhere
PAD_GAP = 1.3                  # between reference and value of a pad whose texts stand on one line

def uid(*key):
    return str(uuid.uuid5(NS, "|".join(str(k) for k in key)))

def snap(v):
    return round(round(v / G) * G, 4)

def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

def dump(node):
    if isinstance(node, tuple):
        return q(node[1])
    if isinstance(node, str):
        return node
    return "(" + " ".join(dump(c) for c in node) + ")"

# ---------------------------------------------------------------- text metrics (calibrated on KiCad's PDF output)
_W = {'I': .476, '.': .476, 'i': .476, 'l': .524, 't': .571, 'r': .619, '(': .667, ')': .667, ' ': .762, 'T': .762,
      '_': .762, 'J': .762, 'v': .762, 'L': .81, 's': .81, 'k': .81, 'A': .857, 'V': .857, 'F': .857, 'e': .857,
      'Y': .857, 'c': .857, 'u': .905, 'E': .905, 'n': .905, 'p': .905, 'o': .905, 'a': .905, 'd': .905, 'Z': .952,
      'X': .952, 'N': 1.03, 'H': 1.036, 'O': 1.045, 'Q': 1.045, 'U': 1.046, 'w': 1.048, '/': 1.048, 'W': 1.143,
      'M': 1.143, '%': 1.143, '-': 1.238, '+': 1.238, '&': 1.238, 'm': 1.333, ',': .5, ':': .5, ';': .5, '!': .5,
      '|': .5, '[': .667, ']': .667, 'f': .6, 'j': .6, '1': .959, '~': 1.0}

def tw(s, size=TS):
    """Width of a text string in mm."""
    return sum(_W.get(c, 0.96 if c.isdigit() else 1.0) for c in str(s)) * size

# ---------------------------------------------------------------- symbol geometry
_geo = {}

def _pts(node):
    out = []
    for p in find(node, "pts"):
        for xy in find(p, "xy"):
            out.append((float(xy[1]), float(xy[2])))
    return out

def geo(lib, name, unit=1, plan=None):
    """Body box of a symbol in symbol coordinates (y up): (x0, y0, x1, y1) of its graphics, and its pins."""
    key = (lib, name, unit, plan)
    if key in _geo: return _geo[key]
    s = symlib.flat(lib, name, plan)
    pts = []
    for u in find(s, "symbol"):
        un, st = (int(v) for v in val(u[1]).rsplit("_", 2)[-2:])
        if st > 1 or un not in (0, unit): continue
        for g in u[2:]:
            if not isinstance(g, list) or not g: continue
            if g[0] == "rectangle":
                a, b = first(g, "start"), first(g, "end")
                pts += [(float(a[1]), float(a[2])), (float(b[1]), float(b[2]))]
            elif g[0] in ("polyline", "bezier"):
                pts += _pts(g)
            elif g[0] == "circle":
                c, r = first(g, "center"), float(get(g, "radius"))
                cx, cy = float(c[1]), float(c[2])
                pts += [(cx - r, cy - r), (cx + r, cy + r)]
            elif g[0] == "arc":
                for k in ("start", "mid", "end"):
                    a = first(g, k)
                    pts.append((float(a[1]), float(a[2])))
    if pts:
        body = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
    else:
        body = None
    pins = [p for p in symlib.pins(lib, name, plan) if p["unit"] in (0, unit)]
    _geo[key] = dict(body=body, pins=pins)
    return _geo[key]

def rot(x, y, a):
    """Symbol coordinates (y up) rotated a degrees CCW, returned as a screen offset (y down)."""
    a = a % 360
    if a == 0: xr, yr = x, y
    elif a == 90: xr, yr = -y, x
    elif a == 180: xr, yr = -x, -y
    else: xr, yr = y, -x
    return xr, -yr

def xf(lx, ly, angle, mirror=False):
    if mirror: lx = -lx
    return rot(lx, ly, angle)

def pin_dir(p, angle, mirror=False):
    """Screen direction a pin leaves its connection point toward the body, after placing the symbol."""
    ca, sa = round(math.cos(math.radians(p["angle"]))), round(math.sin(math.radians(p["angle"])))
    x0, y0 = xf(p["x"], p["y"], angle, mirror)
    x1, y1 = xf(p["x"] + ca, p["y"] + sa, angle, mirror)
    return round(x1 - x0), round(y1 - y0)

# ---------------------------------------------------------------- the sheet
class Placed:
    """A symbol that has been placed: where its pins are, and its body box."""
    def __init__(self, ref, x, y, angle, mirror, pin, box, pdir):
        self.ref, self.x, self.y, self.angle, self.mirror, self.pin, self.box, self.pdir = ref, x, y, angle, mirror, pin, box, pdir

class Sheet:
    def __init__(self, name, project, root_uuid, title):
        self.name, self.project, self.root_uuid, self.title = name, project, root_uuid, title
        self.uuid = uid("sheet", name)
        self.items, self.libs, self.recs = [], {}, []
        self.tx = self.ty = 0.0
        self.npwr = 0
        self.nets_at = {}              # (x, y) -> set of net names that touch there (pins, wire ends)
        self._wk = set()

    # ---- bookkeeping
    def _rec(self, kind, box, **kw):
        self.recs.append(dict(kind=kind, box=box, **kw))

    def _p(self, x, y):
        return snap(x + self.tx), snap(y + self.ty)

    def bbox(self, kinds=None):
        bs = [r["box"] for r in self.recs if r["box"] and (kinds is None or r["kind"] in kinds)]
        if not bs: return None
        return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))

    def mark(self):
        return len(self.recs)

    def bbox_from(self, n):
        """Box of everything recorded since mark n, in the coordinates the drawing code works in (without tx, ty)."""
        bs = [r["box"] for r in self.recs[n:] if r["box"]]
        if not bs: return None
        return (min(b[0] for b in bs) - self.tx, min(b[1] for b in bs) - self.ty, max(b[2] for b in bs) - self.tx, max(b[3] for b in bs) - self.ty)

    def lib(self, lib, name, plan=None):
        key = f"{lib}:{name}"
        if key not in self.libs:
            s = symlib.flat(lib, name, plan)
            s[1] = ("s", key)
            self.libs[key] = dump(s)
            self.libplan = getattr(self, "libplan", {}); self.libplan[key] = plan
        assert self.libplan[key] == plan, f"two drawings of symbol {key} on one sheet"
        return key

    # ---- symbols
    def symbol(self, lib, name, ref, value, x, y, angle=0, unit=1, footprint="", fields=None, mirror=False,
               ref_at=None, val_at=None, ref_j="left", val_j="left", hide_ref=False, hide_val=False, key=None, nets=None,
               power=False, vert=False, plan=None):
        """Place a symbol. ref_at / val_at are where the field texts go (screen coordinates before the sheet translation),
        ref_j / val_j their justification on screen ('left', 'right' or 'center'). nets: {pad: net name} for checks."""
        lid = self.lib(lib, name, plan)
        lx, ly = x, y                                   # local coordinates, what the caller works in
        x, y = self._p(x, y)
        g = geo(lib, name, unit, plan)
        fa = 90 if angle in (90, 270) else 0
        def fj(j):
            if j == "center": return ""
            flip = (angle in (90, 180)) != mirror
            return f"(justify {'right' if (j == 'left') == flip else 'left'})"
        hid = lambda h: " (hide yes)" if h else ""
        props = []
        rx, ry = self._p(*ref_at) if ref_at else (x + 2.54, y - 1.27)
        vx, vy = self._p(*val_at) if val_at else (x + 2.54, y + 1.27)
        if vert: fa = 0 if angle in (90, 270) else 90; fj = lambda j: ""
        props.append(f'(property "Reference" {q(ref)} (at {rx:.2f} {ry:.2f} {fa}) (effects (font (size {TS} {TS})) {fj(ref_j)}{hid(hide_ref)}))')
        props.append(f'(property "Value" {q(value)} (at {vx:.2f} {vy:.2f} {fa}) (effects (font (size {TS} {TS})) {fj(val_j)}{hid(hide_val)}))')
        props.append(f'(property "Footprint" {q(footprint)} (at {x} {y} 0) (effects (font (size {TS} {TS})) (hide yes)))')
        for k, v in (fields or {}).items():
            props.append(f'(property {q(k)} {q(v)} (at {x} {y} 0) (effects (font (size {TS} {TS})) (hide yes)))')
        pins = " ".join(f'(pin {q(p)} (uuid {q(uid(self.name, ref, unit, "pin", p))}))' for p in sorted({p["drawn"] for p in g["pins"]}))
        su = uid(self.name, "sym", key or ref, unit)
        self.items.append(
            f'(symbol (lib_id {q(lid)}) (at {x} {y} {angle}){" (mirror y)" if mirror else ""} (unit {unit}) (exclude_from_sim no) (in_bom yes) (on_board yes) '
            f'(dnp no) (uuid {q(su)}) {" ".join(props)} {pins} '
            f'(instances (project {q(self.project)} (path {q("/" + self.root_uuid + "/" + self.uuid)} (reference {q(ref)}) (unit {unit})))))')
        pin, pdir, lpin = {}, {}, {}
        for p in g["pins"]:
            dx, dy = xf(p["x"], p["y"], angle, mirror)
            pin[p["num"]] = (snap(x + dx), snap(y + dy))
            lpin[p["num"]] = (snap(lx + dx), snap(ly + dy))
            pdir[p["num"]] = pin_dir(p, angle, mirror)
        box = None
        if g["body"]:
            b = g["body"]
            c = [xf(b[0], b[1], angle, mirror), xf(b[2], b[3], angle, mirror), xf(b[0], b[3], angle, mirror), xf(b[2], b[1], angle, mirror)]
            box = (x + min(a[0] for a in c), y + min(a[1] for a in c), x + max(a[0] for a in c), y + max(a[1] for a in c))
        ends = set(pin.values())
        full = box
        for pt in ends:                       # the symbol reaches out to its pin ends
            full = (min(full[0], pt[0]), min(full[1], pt[1]), max(full[2], pt[0]), max(full[3], pt[1])) if full else (pt[0], pt[1], pt[0], pt[1])
        self._rec("sym", full, body=box, ref=ref, pins=pin, power=power, nets=nets or {}, pdir=pdir)
        for num, pt in pin.items():
            self.nets_at.setdefault(pt, set()).add((nets or {}).get(num, f"?{ref}.{num}"))
        # field texts
        if not hide_ref and ref_at:
            w = tw(ref)
            self._rec("text", (rx - 0.65, ry - w / 2, rx + 0.65, ry + w / 2) if vert else self._tbox(rx, ry, w, ref_j, 0), text=ref, owner=ref)
        if not hide_val and val_at:
            w = tw(value)
            self._rec("text", (vx - 0.65, vy - w / 2, vx + 0.65, vy + w / 2) if vert else self._tbox(vx, vy, w, val_j, 0), text=value, owner=ref)
        lbox = None
        if box: lbox = (box[0] - self.tx, box[1] - self.ty, box[2] - self.tx, box[3] - self.ty)
        return Placed(ref, lx, ly, angle, mirror, lpin, lbox, pdir)

    @staticmethod
    def _tbox(x, y, w, j, a=0, h=1.3):
        if j == "left": return (x, y - h / 2, x + w, y + h / 2)
        if j == "right": return (x - w, y - h / 2, x, y + h / 2)
        return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)

    # ---- wires, junctions, labels
    def wire(self, x1, y1, x2, y2, net=None):
        x1, y1 = self._p(x1, y1); x2, y2 = self._p(x2, y2)
        if (x1, y1) == (x2, y2): return
        k = (min((x1, y1), (x2, y2)), max((x1, y1), (x2, y2)))
        if k in self._wk: return
        self._wk.add(k)
        self.items.append(f'(wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default)) '
                          f'(uuid {q(uid(self.name, "w", x1, y1, x2, y2))}))')
        self._rec("wire", (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)), seg=(x1, y1, x2, y2), net=net)

    def path(self, pts, net=None):
        for a, b in zip(pts, pts[1:]): self.wire(a[0], a[1], b[0], b[1], net)

    def junction(self, x, y):
        x, y = self._p(x, y)
        self.items.append(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid {q(uid(self.name, "j", x, y))}))')
        self._rec("junction", (x, y, x, y))

    def label(self, text, x, y, angle, glob, shape="passive", net=None):
        """A net label whose anchor is at (x, y); angle is the direction the text runs away from the anchor (0 right, 180 left,
        90 up, 270 down)."""
        x, y = self._p(x, y)
        w = tw(text)
        if glob:
            j = {0: "(justify left)", 90: "(justify left)", 180: "(justify right)", 270: "(justify right)"}[angle]
            self.items.append(f'(global_label {q(text)} (shape {shape}) (at {x} {y} {angle}) (effects (font (size {TS} {TS})) {j}) '
                              f'(uuid {q(uid(self.name, "gl", text, x, y))}) (property "Intersheetrefs" "${{INTERSHEET_REFS}}" '
                              f'(at {x} {y} 0) (effects (font (size {TS} {TS})) (hide yes))))')
            L = w + 1.4 + (1.27 if shape != "passive" else 0)
            box = {0: (x, y - 1.27, x + L, y + 1.27), 180: (x - L, y - 1.27, x, y + 1.27),
                   90: (x - 1.27, y - L, x + 1.27, y), 270: (x - 1.27, y, x + 1.27, y + L)}[angle]
        else:
            j = {0: "(justify left bottom)", 90: "(justify left bottom)", 180: "(justify right bottom)", 270: "(justify right bottom)"}[angle]
            self.items.append(f'(label {q(text)} (at {x} {y} {angle}) (effects (font (size {TS} {TS})) {j}) (uuid {q(uid(self.name, "l", text, x, y))}))')
            box = {0: (x, y - 1.5, x + w, y - 0.1), 180: (x - w, y - 1.5, x, y - 0.1),
                   90: (x - 1.5, y - w, x - 0.1, y), 270: (x - 1.5, y, x - 0.1, y + w)}[angle]
        self._rec("label", box, text=text, glob=glob, at=(x, y), net=net)
        self.nets_at.setdefault((x, y), set()).add(net or text)

    def nc(self, x, y):
        x, y = self._p(x, y)
        self.items.append(f'(no_connect (at {x} {y}) (uuid {q(uid(self.name, "nc", x, y))}))')
        self._rec("nc", (x - 0.9, y - 0.9, x + 0.9, y + 0.9))

    def text(self, s, x, y, size=TS, bold=False, color=None, anchor="left bottom"):
        color = None
        """Free text: the anchor is at the bottom left of the first line."""
        x, y = self._p(x, y)
        lines = str(s).split("\n")
        n = len(lines)
        w = max(tw(l, size) for l in lines)
        eff = f'(effects (font (size {size} {size}){" bold" if bold else ""}{f" (color {color})" if color else ""}) (justify left bottom))'
        self.items.append(f'(text {q(s)} (exclude_from_sim no) (at {x} {y} 0) {eff} (uuid {q(uid(self.name, "t", s, x, y))}))')
        self._rec("text", (x, y - size * 1.1 * n - 0.2, x + w, y + 0.2), text=lines[0], owner="free")

    def frame(self, x0, y0, x1, y1, color="132 132 160 1"):
        """A dashed group outline."""
        x0, y0 = self._p(x0, y0); x1, y1 = self._p(x1, y1)
        self.items.append(f'(rectangle (start {x0} {y0}) (end {x1} {y1}) (stroke (width 0.15) (type dash) (color {color})) '
                          f'(fill (type none)) (uuid {q(uid(self.name, "fr", x0, y0, x1, y1))}))')
        self._rec("frame", (x0, y0, x1, y1))

    # ---- finishing
    def junctions(self):
        """Add a junction wherever a wire end meets a wire's middle, a pin or a label sits in a wire's middle, or three or
        more things meet."""
        wires = [r["seg"] for r in self.recs if r["kind"] == "wire"]
        ends = {}
        for a, b, c, d in wires:
            ends[(a, b)] = ends.get((a, b), 0) + 1
            ends[(c, d)] = ends.get((c, d), 0) + 1
        pins = {}
        for r in self.recs:
            if r["kind"] == "sym":
                for p in set(r["pins"].values()): pins[p] = pins.get(p, 0) + 1
        labels = {r["at"] for r in self.recs if r["kind"] == "label"}
        have = {(r["box"][0], r["box"][1]) for r in self.recs if r["kind"] == "junction"}
        def inside(pt, seg):
            a, b, c, d = seg
            if a == c == pt[0] and min(b, d) < pt[1] < max(b, d): return True
            if b == d == pt[1] and min(a, c) < pt[0] < max(a, c): return True
            return False
        pts = set(ends) | set(pins) | labels
        for pt in sorted(pts):
            if pt in have: continue
            n = ends.get(pt, 0) + pins.get(pt, 0) + (1 if pt in labels else 0)
            mid = sum(1 for sg in wires if inside(pt, sg))
            if (n >= 3 and ends.get(pt, 0)) or (mid and (pt in pins or pt in labels or ends.get(pt, 0))):
                self.junction(pt[0] - self.tx, pt[1] - self.ty)

    def write(self, path, paper, notes=""):
        w, h = paper
        out = [f'(kicad_sch (version {VERSION}) (generator "p2p_draw") (generator_version "10.0") (uuid {q(self.uuid)}) '
               f'(paper "User" {w} {h}) (title_block (title {q(self.title)}) (comment 1 "Generated from code. Do not edit: change the block source and rebuild."))',
               "(lib_symbols " + "\n".join(self.libs.values()) + ")"]
        out += self.items
        out.append("(embedded_fonts no))")
        open(path, "w").write("\n".join(out) + "\n")

# ---------------------------------------------------------------- clutter check
def _inter(a, b, m=0.0):
    return a[0] + m < b[2] - m and b[0] + m < a[2] - m and a[1] + m < b[3] - m and b[1] + m < a[3] - m

def _seg_box(seg, box):
    x0, y0, x1, y1 = box
    ax, ay, bx, by = seg
    dx, dy = bx - ax, by - ay
    t0, t1 = 0.0, 1.0
    for p, qq in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
        if abs(p) < 1e-9:
            if qq < 0: return False
        else:
            r = qq / p
            if p < 0:
                if r > t1: return False
                t0 = max(t0, r)
            else:
                if r < t0: return False
                t1 = min(t1, r)
    return t0 <= t1

def lint(S, quiet=False, tight=None):
    """Overlaps a person would see. Returns a list of strings. With tight (env LINT_TIGHT=1) the margins are negative: things
    that come closer than about 0.6 mm (symbols 0.8 mm, power symbols included) are listed too, to find cramped spots."""
    out = []
    if tight is None: tight = bool(os.environ.get("LINT_TIGHT"))
    M = dict(ss=-0.4, ts=-0.25, wt=-0.2, tt=-0.2, ws=-0.2) if tight else dict(ss=0.3, ts=0.25, wt=0.25, tt=0.2, ws=0.3)
    syms = [r for r in S.recs if r["kind"] == "sym" and (tight or not r["power"]) and r["body"]]
    texts = [r for r in S.recs if r["kind"] in ("text", "label")]
    wires = [r for r in S.recs if r["kind"] == "wire"]
    for i, a in enumerate(syms):
        for b in syms[i + 1:]:
            if a["power"] and b["power"]: continue
            if _inter(a["body"], b["body"], M["ss"]): out.append(f"symbols overlap: {a['ref']} / {b['ref']} at {a['body'][0]:.0f},{a['body'][1]:.0f}")
    for t in texts:
        tb = t["box"]
        for s in syms:
            if _inter(tb, s["body"], M["ts"]): out.append(f"text '{t['text']}' on symbol {s['ref']} at {tb[0]:.0f},{tb[1]:.0f}")
        for w in wires:
            m = M["wt"]
            if t["kind"] == "label" and t.get("at") in ((w["seg"][0], w["seg"][1]), (w["seg"][2], w["seg"][3])): continue     # the wire the label hangs on
            if _seg_box(w["seg"], (tb[0] + m, tb[1] + m, tb[2] - m, tb[3] - m)): out.append(f"wire through text '{t['text']}' at {tb[0]:.0f},{tb[1]:.0f}")
    for i, a in enumerate(texts):
        for b in texts[i + 1:]:
            if _inter(a["box"], b["box"], M["tt"]): out.append(f"text overlap '{a['text']}' / '{b['text']}' at {a['box'][0]:.0f},{a['box'][1]:.0f}")
    for w in wires:
        x0, y0, x1, y1 = w["seg"]
        for s in syms:
            if s["power"]: continue
            b = s["body"]
            m = M["ws"]
            inner = (b[0] + m, b[1] + m, b[2] - m, b[3] - m)
            if inner[0] < inner[2] and inner[1] < inner[3] and _seg_box(w["seg"], inner):
                out.append(f"wire through symbol {s['ref']} at {x0:.0f},{y0:.0f}")
    # wires touching pins or wires of another net
    for w in wires:
        if w["net"] is None: continue
        x0, y0, x1, y1 = w["seg"]
        for s in S.recs:
            if s["kind"] != "sym": continue
            for num, (px, py) in s["pins"].items():
                on = (x0 == x1 == px and min(y0, y1) <= py <= max(y0, y1)) or (y0 == y1 == py and min(x0, x1) <= px <= max(x0, x1))
                if on:
                    pn = s["nets"].get(num)
                    if pn is not None and pn != w["net"]:
                        out.append(f"wire '{w['net']}' touches {s['ref']}.{num} ('{pn}') at {px:.0f},{py:.0f}")
    for i, a in enumerate(wires):
        if a["net"] is None: continue
        for b in wires[i + 1:]:
            if b["net"] is None or a["net"] == b["net"]: continue
            if _seg_cross(a["seg"], b["seg"]):
                out.append(f"wires '{a['net']}' and '{b['net']}' touch at {a['seg'][0]:.0f},{a['seg'][1]:.0f}")
    return out

def text_clashes(S, owner, margin=0.5):
    """How many things (wires, labels, other texts, symbol bodies) come within `margin` of the reference or value text of
    the symbol `owner`."""
    mine = [r for r in S.recs if r["kind"] == "text" and r.get("owner") == owner]
    n = 0
    for t in mine:
        tb = (t["box"][0] - margin, t["box"][1] - margin, t["box"][2] + margin, t["box"][3] + margin)
        for r in S.recs:
            if r["box"] is None or any(r is m for m in mine): continue
            k = r["kind"]
            if k in ("text", "label"):
                if _inter(tb, r["box"]): n += 1
            elif k == "wire":
                if _seg_box(r["seg"], tb): n += 1
            elif k == "sym" and r.get("body") and not r["power"]:
                if _inter(tb, r["body"]): n += 1
    return n

def _seg_cross(s1, s2):
    """Axis-aligned segments that cross or touch."""
    ax0, ay0, ax1, ay1 = s1; bx0, by0, bx1, by1 = s2
    ax0, ax1 = sorted((ax0, ax1)); ay0, ay1 = sorted((ay0, ay1)); bx0, bx1 = sorted((bx0, bx1)); by0, by1 = sorted((by0, by1))
    return ax0 <= bx1 and bx0 <= ax1 and ay0 <= by1 and by0 <= ay1
