"""Draws KiCad schematic sheets from netlist.json. The netlist is the truth; these sheets are a view of it.

Style, as a person would draw it:
  * every IC is drawn with the parts on its pins WIRED to those pins. Each pin that has parts gets a horizontal
    "lane" leaving the IC: decoupling and pull-downs hang from the lane, pull-ups stand on it, series parts sit in
    line and the drawing follows them to the next node, a part between two neighbouring pins stands between their
    lanes (divider, differential filter, bootstrap), a small transistor is drawn at the end of the lane that drives it;
  * pins with nothing on them get a net label; neighbouring pins on one net are joined by a wire;
  * power stages use a template named by the block (draw_as "buck" / "bridge4"), with Kelvin sense filters drawn at
    their shunt;
  * labels are only used where a net leaves the group; ground is always a symbol pointing down where possible;
  * sections (titles from the block source) are packed on a page whose size is chosen to fit them.
Nothing here decides connectivity: make.sh exports KiCad's own netlist of the result and compares it with netlist.json.

usage: draw.py <build dir> <out dir> <project name>
"""
import json, os, sys, uuid, math, re
import symlib
from sx import find, first, get, val

_pins = {}
def sympins(lib, name):
    if (lib, name) not in _pins: _pins[(lib, name)] = symlib.pins(lib, name)
    return _pins[(lib, name)]

NS = uuid.UUID("6f1c2b1e-58a5-4c6e-9a59-0d5a1f2b7c11")
G = 1.27
CH = 1.2            # mm per character of 1.27 mm text, for reserving room
VERSION = "20260306"

def uid(*key):
    return str(uuid.uuid5(NS, "|".join(str(k) for k in key)))

def snap(v):
    return round(round(v / G) * G, 4)

def snap2(v):
    """up to the next 2.54 mm"""
    return round(math.ceil(v / 2.54 - 1e-6) * 2.54, 4)

def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

def dump(node):
    if isinstance(node, tuple):
        return q(node[1])
    if isinstance(node, str):
        return node
    return "(" + " ".join(dump(c) for c in node) + ")"

def rot(x, y, a):
    """Symbol coordinates (y up) rotated a degrees, returned as a screen offset (y down)."""
    a = a % 360
    if a == 0: xr, yr = x, y
    elif a == 90: xr, yr = -y, x
    elif a == 180: xr, yr = -x, -y
    else: xr, yr = y, -x
    return xr, -yr

FONT = "(effects (font (size 1.27 1.27)) {j})"

class Sheet:
    def __init__(self, name, project, root_uuid, title):
        self.name, self.project, self.root_uuid, self.title = name, project, root_uuid, title
        self.uuid = uid("sheet", name)
        self.items, self.libs, self.npwr = [], {}, 0
        self.wires, self.pins = [], []
        self.size = (297, 210)

    def lib(self, lib, name):
        key = f"{lib}:{name}"
        if key not in self.libs:
            s = symlib.flat(lib, name)
            s[1] = ("s", key)
            self.libs[key] = dump(s)
        return key

    def symbol(self, lib, name, ref, value, x, y, angle=0, unit=1, footprint="", fields=None, ref_at=None, val_at=None,
               hide_ref=False, hide_val=False, key=None, mirror=False, just=None):
        lid = self.lib(lib, name)
        x, y = snap(x), snap(y)
        for p in sympins(lib, name):
            if p["unit"] in (0, unit):
                dx, dy = rot(-p["x"] if mirror else p["x"], p["y"], angle)
                self.pins.append((snap(x + dx), snap(y + dy)))
        # KiCad turns field text with the symbol: undo that so text always reads left to right
        fa = 90 if angle in (90, 270) else 0
        want = just or "left"
        flip = (angle in (90, 180)) != mirror
        fj = {"left": "right", "right": "left"}[want] if flip else want
        rx, ry = ref_at or (x + 2.54, y - 1.27)
        vx, vy = val_at or (x + 2.54, y + 1.27)
        hid = lambda h: " (hide yes)" if h else ""
        props = [f'(property "Reference" {q(ref)} (at {rx:.2f} {ry:.2f} {fa}) (effects (font (size 1.27 1.27)) (justify {fj}){hid(hide_ref)}))',
                 f'(property "Value" {q(value)} (at {vx:.2f} {vy:.2f} {fa}) (effects (font (size 1.27 1.27)) (justify {fj}){hid(hide_val)}))',
                 f'(property "Footprint" {q(footprint)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))']
        for k, v in (fields or {}).items():
            props.append(f'(property {q(k)} {q(v)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        pins = " ".join(f'(pin {q(p)} (uuid {q(uid(self.name, ref, unit, "pin", p))}))'
                        for p in sorted({p["drawn"] for p in sympins(lib, name) if p["unit"] in (0, unit)}))
        su = uid(self.name, "sym", key or ref, unit)
        self.items.append(
            f'(symbol (lib_id {q(lid)}) (at {x} {y} {angle}){" (mirror y)" if mirror else ""} (unit {unit}) (exclude_from_sim no) (in_bom yes) (on_board yes) '
            f'(dnp no) (uuid {q(su)}) {" ".join(props)} {pins} '
            f'(instances (project {q(self.project)} (path {q("/" + self.root_uuid + "/" + self.uuid)} (reference {q(ref)}) (unit {unit})))))')

    def wire(self, x1, y1, x2, y2):
        x1, y1, x2, y2 = snap(x1), snap(y1), snap(x2), snap(y2)
        if (x1, y1) == (x2, y2): return
        self.wires.append((x1, y1, x2, y2))

    def label(self, text, x, y, angle, glob):
        x, y = snap(x), snap(y)
        j = {0: "(justify left bottom)", 90: "(justify left bottom)", 180: "(justify right bottom)", 270: "(justify right bottom)"}[angle]
        if glob:
            j = {0: "(justify left)", 90: "(justify left)", 180: "(justify right)", 270: "(justify right)"}[angle]
            self.items.append(f'(global_label {q(text)} (shape passive) (at {x} {y} {angle}) {FONT.format(j=j)} '
                              f'(uuid {q(uid(self.name, "gl", text, x, y))}) (property "Intersheetrefs" "${{INTERSHEET_REFS}}" '
                              f'(at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes))))')
        else:
            self.items.append(f'(label {q(text)} (at {x} {y} {angle}) {FONT.format(j=j)} (uuid {q(uid(self.name, "l", text, x, y))}))')

    def gnd(self, x, y, angle=0):
        self.npwr += 1
        ref = f"#PWR{abs(hash(self.name)) % 90 + 10}{self.npwr:03d}"
        self.symbol("power", "GND", ref, "GND", x, y, angle, hide_ref=True, hide_val=True,
                    val_at=(snap(x) - 1.9, snap(y) + 5.0), key=f"pwr{self.npwr}")

    def nc(self, x, y):
        x, y = snap(x), snap(y)
        self.items.append(f'(no_connect (at {x} {y}) (uuid {q(uid(self.name, "nc", x, y))}))')

    def text(self, s, x, y, size=1.27, bold=False):
        x, y = snap(x), snap(y)
        b = " (bold yes)" if bold else ""
        self.items.append(f'(text {q(s)} (exclude_from_sim no) (at {x} {y} 0) (effects (font (size {size} {size}){b}) (justify left bottom)) '
                          f'(uuid {q(uid(self.name, "t", s, x, y))}))')

    def rect(self, x1, y1, x2, y2):
        self.items.append(f'(rectangle (start {snap(x1)} {snap(y1)}) (end {snap(x2)} {snap(y2)}) (stroke (width 0.15) (type dash)) (fill (type none)) '
                          f'(uuid {q(uid(self.name, "r", x1, y1, x2, y2))}))')

    def _finish_wires(self):
        """Split wires where a pin or another wire ends on them, and put a junction dot wherever three or more meet."""
        ws = sorted(set((min((a, b), (c, d)) + max((a, b), (c, d))) for a, b, c, d in self.wires))
        pts = set(self.pins)
        for a, b, c, d in ws: pts.add((a, b)); pts.add((c, d))
        byx, byy = {}, {}
        for p in pts: byx.setdefault(p[0], []).append(p); byy.setdefault(p[1], []).append(p)
        out = []
        for a, b, c, d in ws:
            if a == c: cut = sorted(p for p in byx.get(a, []) if b < p[1] < d)
            elif b == d: cut = sorted(p for p in byy.get(b, []) if a < p[0] < c)
            else: cut = []
            chain = [(a, b)] + cut + [(c, d)]
            out += [(chain[i] + chain[i + 1]) for i in range(len(chain) - 1)]
        count = {}
        for p in self.pins: count[p] = count.get(p, 0) + 1
        for a, b, c, d in set(out):
            count[(a, b)] = count.get((a, b), 0) + 1; count[(c, d)] = count.get((c, d), 0) + 1
        for a, b, c, d in sorted(set(out)):
            self.items.append(f'(wire (pts (xy {a} {b}) (xy {c} {d})) (stroke (width 0) (type default)) '
                              f'(uuid {q(uid(self.name, "w", a, b, c, d))}))')
        for (x, y), n in sorted(count.items()):
            if n >= 3:
                self.items.append(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid {q(uid(self.name, "j", x, y))}))')

    def write(self, path, page):
        self._finish_wires()
        w, h = self.size
        out = [f'(kicad_sch (version {VERSION}) (generator "p2p_draw") (generator_version "10.0") (uuid {q(self.uuid)}) '
               f'(paper "User" {w} {h}) (title_block (title {q(self.title)}) (comment 1 "Generated from code. Do not edit: change the block source and rebuild."))',
               "(lib_symbols " + "\n".join(self.libs.values()) + ")"]
        out += self.items
        out.append("(embedded_fonts no))")
        open(path, "w").write("\n".join(out) + "\n")


class Canvas:
    """A drawing at its own origin: records what to draw and how much room it takes, to be placed on a sheet later."""
    def __init__(self):
        self.ops, self.bb = [], None

    def ext(self, x0, y0, x1, y1):
        x0, x1 = min(x0, x1), max(x0, x1); y0, y1 = min(y0, y1), max(y0, y1)
        b = self.bb
        self.bb = [x0, y0, x1, y1] if b is None else [min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1)]

    def symbol(self, comp, ref, x, y, angle=0, unit=1, ref_at=None, val_at=None, mirror=False, just=None):
        lib, name = comp["lib"].split(":")
        x, y = snap(x), snap(y)
        for p in sympins(lib, name):
            if p["unit"] in (0, unit):
                dx, dy = rot(-p["x"] if mirror else p["x"], p["y"], angle)
                self.ext(x + dx - 1.27, y + dy - 1.27, x + dx + 1.27, y + dy + 1.27)
        rx, ry = ref_at or (x + 2.54, y - 1.27)
        vx, vy = val_at or (x + 2.54, y + 1.27)
        for (tx, ty), s in (((rx, ry), ref), ((vx, vy), comp["value"])):
            if just == "right": self.ext(tx - len(s) * CH, ty - 1, tx, ty + 1)
            else: self.ext(tx, ty - 1, tx + len(s) * CH, ty + 1)
        self.ops.append(("symbol", (lib, name, ref, comp["value"], x, y, angle, unit, comp["footprint"], comp["fields"],
                                    (rx, ry), (vx, vy), mirror, just)))

    def wire(self, x1, y1, x2, y2):
        self.ext(x1, y1, x2, y2)
        self.ops.append(("wire", (x1, y1, x2, y2)))

    def label(self, text, x, y, angle, glob):
        w = len(text) * CH + (5.0 if glob else 0.5)
        if angle == 0: self.ext(x, y - 2.2, x + w, y + (1.6 if glob else 0))
        elif angle == 180: self.ext(x - w, y - 2.2, x, y + (1.6 if glob else 0))
        elif angle == 90: self.ext(x - 2.2, y - w, x + 1.6, y)
        else: self.ext(x - 2.2, y, x + 1.6, y + w)
        self.ops.append(("label", (text, x, y, angle, glob)))

    def gnd(self, x, y, angle=0):
        dx, dy = {0: (0, 3.3), 90: (3.3, 0), 180: (0, -3.3), 270: (-3.3, 0)}[angle]
        self.ext(x - 1.9, y - 1.9, x + 1.9, y + 1.9); self.ext(x, y, x + dx, y + dy)
        self.ops.append(("gnd", (x, y, angle)))

    def nc(self, x, y):
        self.ext(x - 1, y - 1, x + 1, y + 1)
        self.ops.append(("nc", (x, y)))

    def text(self, s, x, y, size=1.27, bold=False):
        self.ext(x, y - size * 1.4, x + len(s) * size * 0.93, y)
        self.ops.append(("text", (s, x, y, size, bold)))

    def add(self, other, dx, dy):
        if other.bb is None: return
        self.ops.append(("sub", (other, dx, dy)))
        b = other.bb
        self.ext(b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy)

    def emit(self, sheet, dx=0.0, dy=0.0):
        for op, a in self.ops:
            if op == "symbol":
                lib, name, ref, value, x, y, angle, unit, fp, fields, (rx, ry), (vx, vy), mirror, just = a
                sheet.symbol(lib, name, ref, value, x + dx, y + dy, angle, unit=unit, footprint=fp, fields=fields,
                             ref_at=(rx + dx, ry + dy), val_at=(vx + dx, vy + dy), mirror=mirror, just=just)
            elif op == "wire": sheet.wire(a[0] + dx, a[1] + dy, a[2] + dx, a[3] + dy)
            elif op == "label": sheet.label(a[0], a[1] + dx, a[2] + dy, a[3], a[4])
            elif op == "gnd": sheet.gnd(a[0] + dx, a[1] + dy, a[2])
            elif op == "nc": sheet.nc(a[0] + dx, a[1] + dy)
            elif op == "text": sheet.text(a[0], a[1] + dx, a[2] + dy, a[3], a[4])
            elif op == "sub": a[0].emit(sheet, dx + a[1], dy + a[2])

    w = property(lambda s: 0 if s.bb is None else s.bb[2] - s.bb[0])
    h = property(lambda s: 0 if s.bb is None else s.bb[3] - s.bb[1])


RAIL_RE = re.compile(r"^(P\d_)?(LDO_)?\d+V\d*$|^VCC|^VDD|^VBUS$|^PACK_P$|^PP(HV|\d+V\d*)$|^REGN$|^DRV_SUP$")

class Node:
    """One net along a lane, with what is drawn on it."""
    def __init__(self, net):
        self.net = net
        self.sh, self.pu, self.hg = [], [], []      # parts down to ground, parts up to a rail, parts down to a label
        self.ser = None                             # (part, Node): the part in line and the net after it
        self.term = None                            # a pad, test point or small transistor at the end of the lane
        self.close = None                           # index of the neighbouring lane this one loops back to
        self.conn = set()                           # (ref, pad) drawn connected to this net here
        self.inline_gnd = False

    def any(self):
        return bool(self.sh or self.pu or self.hg or self.ser or self.term)


def draw_block(sheet, block, comps, nets, nc, cons, order):
    refs = [r for r in order if comps[r]["block"] == block]
    refset = set(refs)
    pinnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
    # a net is global when it leaves the block
    glob = {n for n, nodes in nets.items() if any(r not in refset for r, _ in nodes) and any(r in refset for r, _ in nodes)}
    short = lambda n: n.lstrip("/") if n in glob else n.split("/")[-1]
    power = {n for n, d in cons["nets"].items() if d.get("kind") == "power"}
    netrefs = {n: {r for r, _ in nodes if r in refset} for n, nodes in nets.items()}
    netpads = {n: {(r, p) for r, p in nodes if r in refset} for n, nodes in nets.items()}
    rail = lambda n: n in power or bool(RAIL_RE.match(n.split("/")[-1]))
    hub = lambda n: n == "GND" or rail(n) or len(netrefs[n]) > 6
    section_of = lambda r: comps[r].get("section") or block
    isR = lambda r: comps[r]["lib"] == "Device:R"
    lw = lambda n: len(short(n)) * CH + (5.5 if n in glob else 1.0)        # room a label takes

    # ---- pins, grouped by where they are drawn (several pads can share one drawn pin) ----
    pins_of = {r: sympins(*comps[r]["lib"].split(":")) for r in refs}
    PG = {}
    for r in refs:
        out, idx = [], {}
        for p in pins_of[r]:
            k = (p["x"], p["y"], p["unit"])
            if k not in idx:
                idx[k] = len(out)
                out.append(dict(x=p["x"], y=p["y"], angle=p["angle"], unit=p["unit"], name=p["name"], nums=[]))
            out[idx[k]]["nums"].append(p["num"])
        for g in out:
            g["net"] = next((pinnet[(r, n)] for n in g["nums"] if (r, n) in pinnet), None)
        PG[r] = out
    npos = {r: len(PG[r]) for r in refs}
    ends = lambda r: [g["net"] for g in PG[r]]
    def other(r, n):
        e = [x for x in ends(r) if x != n]
        return e[0] if e else (n if npos[r] == 2 else None)
    pads_on = lambda r, n: {(r, num) for g in PG[r] if g["net"] == n for num in g["nums"]}
    ph = lambda r: math.hypot(PG[r][0]["x"] - PG[r][1]["x"], PG[r][0]["y"] - PG[r][1]["y"])
    tl = lambda r: max(len(r), len(comps[r]["value"])) * CH
    txo = lambda r: 2.54 if comps[r]["lib"].startswith("Device:") else 6.35
    bw = lambda r: 0.0 if comps[r]["lib"].startswith("Device:") else 5.08          # half width of a wide body
    tl1 = lambda r: (len(r) + 1 + len(comps[r]["value"])) * CH                       # reference and value on one line
    def wv(r, lab=None):
        """room along a lane for an upright part with its text on the right"""
        w = 2.54 + bw(r) + txo(r) + tl(r) + 1.27
        if lab: w = max(w, 2.54 + bw(r) + lw(lab) + 1.27)
        return snap2(w)

    small = [r for r in refs if npos[r] <= 2]
    attach = {}
    for r in small:
        for n in set(ends(r)):
            if n: attach.setdefault(n, []).append(r)

    # ---- templates named by the block ----
    tdraw = {a: t for a, t in cons.get("draw", {}).items() if a in refset}
    def kelvin_parts(rs):
        for kv in cons.get("kelvin", {}).values():
            if kv["resistor"] != rs: continue
            pos, neg = kv["pos"], kv["neg"]; e = ends(rs)
            f2 = lambda x, y: [r for r in attach.get(x, []) if r != rs and set(ends(r)) == {x, y}]
            for sa, sb in ((e[0], e[1]), (e[1], e[0])):
                rp, rn = f2(sa, pos), f2(sb, neg)
                if rp and rn:
                    return dict(pos=pos, neg=neg, src_pos=sa, src_neg=sb, rp=rp[0], rn=rn[0], cd=f2(pos, neg)[:1],
                                cp=f2(pos, "GND"), cn=f2(neg, "GND"))
        return None
    templ, tskip, twired, kel, fpair = set(), set(), {}, {}, {}
    for a, t in tdraw.items():
        if t["kind"] == "fetpair":
            # two FETs back to back in a power path: gate parts and the parts across the pair belong to the template
            F = dict(byp=list(t.get("bypass", [])), gate={}, taps=[])
            pn = lambda q_, nm: next(g["net"] for g in PG[q_] if g["name"] == nm)
            for q_ in (a, t["q_out"]):
                ng, ns = pn(q_, "G"), pn(q_, "S")
                gs = [r for r in attach.get(ng, []) if other(r, ng) == ns]
                ser = [r for r in attach.get(ng, []) if r not in gs and npos[r] == 2]
                F["gate"][q_] = (gs, ser)
                templ.update(gs + ser)
            ns = pn(a, "S")
            for r in attach.get(ns, []):
                if r in templ or r in F["byp"] or npos[r] != 2 or section_of(r) != section_of(a): continue
                o = other(r, ns)
                pad = [x for x in netrefs.get(o, ()) if x != r and npos[x] == 1] if o != "GND" and len(netrefs[o]) == 2 else []
                F["taps"].append((r, pad[0] if pad else None)); templ.update([r] + pad)
            templ.update(F["byp"]); tskip.add(t["q_out"]); fpair[a] = F
            continue
        templ.update([t["inductor"]] + t.get("cin", []) + t.get("cout", []) + t.get("div", []) + [t[k] for k in ("boot", "rin", "rout") if t.get(k)])
        if t.get("q_out"): tskip.add(t["q_out"])
        for k in ("rin", "rout"):
            if t.get(k):
                K = kelvin_parts(t[k])
                if K:
                    kel[t[k]] = K
                    templ.update([K["rp"], K["rn"]] + K["cd"] + K["cp"] + K["cn"])
        if t["kind"] == "buck":
            names = {t[k] for k in ("vin", "sw", "sense", "fb", "bst") if t.get(k)}
            twired[a] = {i for i, g in enumerate(PG[a]) if g["name"] in names}
    anchors = [r for r in refs if npos[r] > 2 and r not in tskip]
    anchorset = set(anchors)
    anch_on = {}
    for a in anchors:
        for g in PG[a]:
            if g["net"]: anch_on.setdefault(g["net"], set()).add(a)

    # ---- which pin each small part is drawn at: trees of parts growing out of IC pins ----
    sidenet = {}
    for a in anchors:
        d = {}
        for i in sorted(range(npos[a]), key=lambda i: -PG[a][i]["y"]):
            g = PG[a][i]
            if g["angle"] in (0, 180) and g["net"] and g["net"] != "GND" and i not in twired.get(a, ()):
                d.setdefault(g["net"], i)
        sidenet[a] = d
    served = {}
    for r, tgt in cons.get("serves", {}).items():
        if r not in refset or npos[r] != 2 or r in templ: continue
        a, pn = tgt.split(".", 1)
        if a not in anchorset: continue
        for i, g in enumerate(PG[a]):
            if g["name"] == pn and g["net"] in ends(r) and g["net"] != "GND" and g["angle"] in (0, 180, 270) and i not in twired.get(a, ()):
                if g["angle"] != 270 and sidenet[a].get(g["net"]) != i: i = sidenet[a][g["net"]]
                if g["angle"] == 270 and other(r, g["net"]) != "GND": continue
                served[r] = (a, i); break
    roots, bridges, owned, attached, started = {}, [], set(), set(), set()

    def series_like(r, n):
        o = other(r, n)
        return npos[r] == 2 and o not in (None, "GND", n) and not hub(o)

    def grow(node, a, i, depth, sec, inc=None):
        n = node.net
        g = PG[a][i]; sd = g["angle"]; top = sd == 270
        if depth == 0: node.conn |= {(a, num) for num in g["nums"]}
        if n == "GND" or (depth > 0 and (hub(n) or n in glob)): return
        can_attach = (not top and sd == 180 and node.term is None and node.ser is None and not hub(n))
        expand = True
        if can_attach:
            for qn in anchors:
                if qn != a and npos[qn] == 3 and qn not in started and qn not in attached and section_of(qn) == section_of(a) \
                        and qn not in tdraw and not any((qn, k) in roots for k in range(3)) and any(g2["angle"] == 0 and g2["net"] == n for g2 in PG[qn]):
                    node.term = qn; attached.add(qn); node.conn |= pads_on(qn, n); break
        if depth > 0:
            if anch_on.get(n, set()) - {node.term}: expand = False
            if sum(1 for r in attach.get(n, []) if r != inc and series_like(r, n)) >= 2: expand = False
        ser_c, rail_r = [], []
        for r in (attach.get(n, []) if expand else []):
            if r in owned or r in templ: continue
            sv = served.get(r)
            o = other(r, n)
            if sv is not None:
                if not (depth == 0 and sv == (a, i)): continue
            else:
                if sec is not None and section_of(r) != sec: continue
                if top: continue
                if hub(n):
                    ok = (o == "GND" and section_of(r) == section_of(a)) or \
                         (sec is None and o in sidenet[a] and PG[a][sidenet[a][o]]["angle"] == sd)
                    if not ok: continue
            if npos[r] == 1:
                if node.term is None and node.ser is None and not hub(n) and n not in glob and len(netrefs[n]) <= 3 and not top:
                    node.term = r; owned.add(r); node.conn |= pads_on(r, n)
                continue
            if o == n or o is None: continue
            if o == "GND":
                node.sh.append(r)
            elif depth == 0 and not top and o in sidenet[a] and sidenet[a][o] != i and PG[a][sidenet[a][o]]["angle"] == sd:
                j = sidenet[a][o]
                bridges.append([a, i, j, r]); roots[(a, i)] = node
                rj = roots.setdefault((a, j), Node(o))
                rj.conn |= pads_on(r, o) | {(a, num) for num in PG[a][j]["nums"]}
            elif top: continue
            elif rail(o):
                (rail_r if isR(r) else ser_c).append((r, o)); continue
            elif hub(o) and o not in glob:                           # a local reference net, such as a Kelvin ground
                node.hg.append((r, o, None))
            else:
                ser_c.append((r, o)); continue
            owned.add(r); node.conn |= pads_on(r, n)
        if ser_c:
            def score(c):
                r, o = c
                if hub(o) or o in glob: return 0
                if o in sidenet[a] and sidenet[a][o] != i: return 3 if (PG[a][sidenet[a][o]]["angle"] == sd and depth >= 1) else -1
                if anch_on.get(o): return 0
                return 2 if any(x != r and x not in owned for x in attach.get(o, [])) else 1
            inline_ok = node.ser is None and node.term is None and not (depth == 0 and (n in glob or hub(n)))
            best = max(ser_c, key=score) if inline_ok else None
            if best and score(best) < 0: best = None
            for r, o in ser_c:
                owned.add(r); node.conn |= pads_on(r, n)
                if best and r == best[0]:
                    ch = Node(o); ch.conn |= pads_on(r, o)
                    if score(best) == 3:
                        j = sidenet[a][o]; ch.close = j
                        rj = roots.setdefault((a, j), Node(o))
                        rj.conn |= pads_on(r, o) | {(a, num) for num in PG[a][j]["nums"]}
                    node.ser = (r, ch)
                else:
                    t = None
                    if not hub(o) and o not in glob and len(netrefs[o]) == 2:
                        x = [x for x in netrefs[o] if x != r][0]
                        if npos[x] == 1 and x not in owned: t = x; owned.add(x)
                    node.hg.append((r, o, t))
        for r, o in rail_r:
            owned.add(r); node.conn |= pads_on(r, n)
            elsewhere = n in glob or bool(anch_on.get(n, set()) - {a}) or depth > 0
            rbridge = depth == 0 and any(b[0] == a and i in (b[1], b[2]) and isR(b[3]) for b in bridges)
            if node.ser is not None or node.term is not None or elsewhere or rbridge or hub(n):
                node.pu.append(r)
            else:
                ch = Node(o); ch.conn |= pads_on(r, o); node.ser = (r, ch)
        if node.ser: grow(node.ser[1], a, i, depth + 1, sec, node.ser[0])

    for sec_pass in (True, False):
        for a in anchors:
            if a in attached or (a in tdraw and tdraw[a]["kind"] in ("bridge4", "fetpair")): continue
            sec = section_of(a) if sec_pass else None
            idxs = sorted(range(npos[a]), key=lambda i: ({0: 0, 180: 1, 270: 2, 90: 3}[PG[a][i]["angle"]], -PG[a][i]["y"], PG[a][i]["x"]))
            for i in idxs:
                g = PG[a][i]
                if g["net"] in (None, "GND") or i in twired.get(a, ()) or g["angle"] == 90: continue
                if g["angle"] != 270 and sidenet[a].get(g["net"]) != i: continue
                node = roots.get((a, i)) or Node(g["net"])
                grow(node, a, i, 0, sec)
                if node.any() or (a, i) in roots: roots[(a, i)] = node
            started.add(a)
    anchors = [a for a in anchors if a not in attached]

    # a differential pair with a capacitor across it: the resistor to ground on one leg is drawn in line, like its twin
    for (a, i), node in roots.items():
        if node.ser is None and node.term is None and any(b[0] == a and i in (b[1], b[2]) and not isR(b[3]) for b in bridges):
            rr = [r for r in node.sh if isR(r)]
            if rr and not hub(node.net):
                node.sh.remove(rr[0]); node.ser = (rr[0], Node("GND"))

    def lanes_of(a, sd):
        act = lambda i: roots[(a, i)].any() or any(b[0] == a and i in (b[1], b[2]) for b in bridges) or \
            any(nd.close == i for (a2, _), r0 in roots.items() if a2 == a for nd in walk(r0))
        return [i for i in sorted(range(npos[a]), key=lambda i: -PG[a][i]["y"])
                if PG[a][i]["angle"] == sd and (a, i) in roots and act(i)]
    def walk(node):
        while node is not None:
            yield node
            node = node.ser[1] if node.ser else None
    # parts between two pins can only stand between neighbouring lanes: the others get a label instead
    for a in anchors:
        changed = True
        while changed:
            changed = False
            for sd in (0, 180):
                ln = lanes_of(a, sd)
                for b in list(bridges):
                    if b[0] != a or b[1] not in ln: continue
                    if b[2] not in ln or abs(ln.index(b[1]) - ln.index(b[2])) != 1:
                        bridges.remove(b)
                        i_, j_, r_ = b[1], b[2], b[3]
                        if hub(roots[(a, i_)].net) and not hub(roots[(a, j_)].net): i_, j_ = j_, i_
                        ni, nj = roots[(a, i_)], roots[(a, j_)]
                        ni.conn |= pads_on(r_, ni.net); nj.conn -= pads_on(r_, nj.net)
                        if rail(nj.net) and isR(r_): ni.pu.append(r_)
                        else: ni.hg.append((r_, nj.net, None))
                        changed = True
                for i in ln:
                    for nd in walk(roots[(a, i)]):
                        if nd.close is not None and (nd.close not in ln or abs(ln.index(nd.close) - ln.index(i)) != 1):
                            roots[(a, nd.close)].conn -= {p for p in nd.conn}
                            nd.close = None; changed = True
    # a loop that closes onto the lane below it (pi filter): draw the chain on the lower lane, so the plain wire is on top
    for (a, i), n0 in list(roots.items()):
        chain = list(walk(n0))
        if chain[-1].close is None or len(chain) < 2: continue
        j = chain[-1].close
        rj = roots[(a, j)]
        if PG[a][j]["y"] > PG[a][i]["y"] or rj.any() or any(b[0] == a and j in (b[1], b[2]) for b in bridges): continue
        parts = [nd.ser[0] for nd in chain[:-1]]
        new = [Node(nd.net) for nd in chain[::-1]]
        for nn, old in zip(new, chain[::-1]):
            nn.sh, nn.pu, nn.hg, nn.term, nn.conn = old.sh, old.pu, old.hg, old.term, set(old.conn)
        new[0].conn |= rj.conn
        for k_, p in enumerate(parts[::-1]): new[k_].ser = (p, new[k_ + 1])
        new[-1].close = i
        roots[(a, j)] = new[0]
        ri = Node(n0.net); ri.conn = set(n0.conn); roots[(a, i)] = ri
    need_label = lambda node: node.net in glob or bool(netpads[node.net] - node.conn)

    # ---- drawing primitives ----
    def lab(cv, n, x, y, ang):
        """a net at the end of a wire: ground symbol or a label reading away from the wire"""
        if n == "GND": return cv.gnd(x, y, 0)
        cv.label(short(n), x, y, ang, n in glob)

    def vpart(cv, r, x, yc, up_net):
        """A two-terminal part upright at (x, yc) with up_net on top. Returns (top y, bottom y)."""
        gs = PG[r]; up = 0 if gs[0]["net"] == up_net else 1
        for a in (0, 90, 180, 270):
            ux, uy = rot(gs[up]["x"], gs[up]["y"], a); dx, dy = rot(gs[1 - up]["x"], gs[1 - up]["y"], a)
            if abs(ux) < 0.01 and abs(dx) < 0.01 and uy < dy: break
        t = txo(r)
        cv.symbol(comps[r], r, x, yc, a, ref_at=(snap(x) + t, snap(yc) - 1.27), val_at=(snap(x) + t, snap(yc) + 1.27))
        return snap(yc + uy), snap(yc + dy)

    def hpart(cv, r, xc, y, left_net, text_y=None):
        """A two-terminal part lying flat, centred at (xc, y), left_net on its left. Text centred above. Returns (left x, right x)."""
        gs = PG[r]; lf = 0 if gs[0]["net"] == left_net else 1
        for a in (0, 90, 180, 270):
            lx, ly = rot(gs[lf]["x"], gs[lf]["y"], a); rx, ry = rot(gs[1 - lf]["x"], gs[1 - lf]["y"], a)
            if abs(ly) < 0.01 and abs(ry) < 0.01 and lx < rx: break
        xc, y = snap(xc), snap(y)
        ty = y - 3.4 if text_y is None else text_y
        x0 = xc - tl1(r) / 2
        cv.symbol(comps[r], r, xc, y, a, ref_at=(x0, ty), val_at=(x0 + (len(r) + 1) * CH, ty))
        return snap(xc + lx), snap(xc + rx)

    def pad1(cv, r, x, y, sg, down=False):
        """A one-pin part (wire pad, test point) with its pin at (x, y); sg: which way its text goes."""
        g = PG[r][0]
        if comps[r]["lib"] == "Connector:TestPoint" or abs(g["x"]) < 0.01:
            if down:
                cv.symbol(comps[r], r, x, y, 180, ref_at=(x + 2.54, y + 2.0), val_at=(x + 2.54, y + 4.0))
            elif sg > 0: cv.symbol(comps[r], r, x, y, 0, ref_at=(x + 2.54, y - 2.54), val_at=(x + 2.54, y - 0.3))
            else: cv.symbol(comps[r], r, x, y, 0, ref_at=(x - 2.54, y - 2.54), val_at=(x - 2.54, y - 0.3), just="right")
        else:
            ox = x - g["x"] if sg > 0 else x + g["x"]
            if sg > 0: cv.symbol(comps[r], r, ox, y, 0, ref_at=(ox + 2.54, y - 1.27), val_at=(ox + 2.54, y + 1.27))
            else: cv.symbol(comps[r], r, ox, y, 0, mirror=True, ref_at=(ox - 2.54, y - 1.27), val_at=(ox - 2.54, y + 1.27), just="right")

    def vpins(cv, a, ox, oy):
        """Top and bottom pins of a part at (ox, oy): grounds joined to one symbol, supply pins with their capacitors
        on a short rail above the part, the rest a stub and a label."""
        gs = PG[a]
        P = lambda i: (snap(ox + gs[i]["x"]), snap(oy - gs[i]["y"]))
        bots = sorted([i for i in range(npos[a]) if gs[i]["angle"] == 90], key=lambda i: gs[i]["x"])
        tops = sorted([i for i in range(npos[a]) if gs[i]["angle"] == 270], key=lambda i: gs[i]["x"])
        gb = [i for i in bots if gs[i]["net"] == "GND"]
        if len(gb) == 1: cv.gnd(*P(gb[0]))
        elif gb:
            y2 = P(gb[0])[1] + 2.54
            for i in gb: cv.wire(P(i)[0], P(i)[1], P(i)[0], y2)
            cv.wire(P(gb[0])[0], y2, P(gb[-1])[0], y2)
            cv.gnd(P(gb[len(gb) // 2])[0], y2)
        for lst, sgn in ((bots, 1), (tops, -1)):
            lb = [i for i in lst if gs[i]["net"] not in (None, "GND") and not (sgn < 0 and (a, i) in roots and roots[(a, i)].sh)]
            for k, i in enumerate(lb):
                x, y = P(i)
                ye = y + sgn * 2.54 * (1 + (k % 2 if len(lb) > 2 else 0))
                cv.wire(x, y, x, ye)
                lab(cv, gs[i]["net"], x, ye, 180 if (len(lb) > 1 and k < len(lb) / 2) else 0)
            for i in lst:
                if gs[i]["net"] is None: cv.nc(*P(i))
                elif gs[i]["net"] == "GND" and sgn < 0: cv.gnd(*P(i), 180)
        runs = [i for i in tops if (a, i) in roots and roots[(a, i)].sh]
        for k, i in enumerate(runs):
            node = roots[(a, i)]; x, y = P(i)
            d = -1 if (len(runs) > 1 and k % 2 == 0) else 1
            yr = y - 17.78 - 17.78 * (k // 2)
            cv.wire(x, y, x, yr)
            xx = x + (5.08 if d > 0 else 0)
            for r in node.sh:
                w = wv(r)
                if d < 0: xx -= w
                t_, b_ = vpart(cv, r, xx, yr + 2.54 + ph(r) / 2, node.net)
                cv.wire(xx, yr, xx, t_); cv.gnd(xx, b_)
                last = xx
                if d > 0: xx += w
            xe = last
            if need_label(node):
                xe = snap(xx) if d > 0 else snap(xx - 2.54)
                lab(cv, node.net, xe, yr, 0 if d > 0 else 180)
            cv.wire(x, yr, xe, yr)

    def body(a):
        """rough outline of a symbol's body from its pins: (left, top, right, bottom) in symbol x and screen y"""
        gs = PG[a]
        sx = [g["x"] for g in gs if g["angle"] in (0, 180)]; sy = [-g["y"] for g in gs if g["angle"] in (0, 180)]
        vx = [g["x"] for g in gs if g["angle"] in (90, 270)]; vy = [-g["y"] for g in gs if g["angle"] in (90, 270)]
        hasl = any(g["angle"] == 0 for g in gs); hasr = any(g["angle"] == 180 for g in gs)
        left = min(g["x"] for g in gs if g["angle"] == 0) + 2.54 if hasl else min(vx + sx) - 5.08
        right = max(g["x"] for g in gs if g["angle"] == 180) - 2.54 if hasr else max(vx + sx) + 5.08
        top = min([-g["y"] for g in gs if g["angle"] == 270] or [1e9]) + 2.54
        if top > 1e8: top = min(sy) - 2.54
        bot = max([-g["y"] for g in gs if g["angle"] == 90] or [-1e9]) - 2.54
        if bot < -1e8: bot = max(sy) + 2.54
        return left, top, right, bot

    def lay_side(cv, a, sd, lane_idx, labx, ymin=None):
        """The lanes on one side of part a (drawn at 0,0). lane_idx: pin groups, top to bottom. labx: room next to the
        pins already taken by labels. ymin: nothing may be drawn above this y (a template's wire runs there)."""
        if not lane_idx: return
        sg = 1 if sd == 180 else -1
        gs = PG[a]; n = len(lane_idx)
        nodes = [roots[(a, i)] for i in lane_idx]
        pys = [snap(-gs[i]["y"]) for i in lane_idx]
        tip = max(sg * gs[i]["x"] for i in lane_idx) * sg
        br = [b for b in bridges if b[0] == a and b[1] in lane_idx and b[2] in lane_idx]
        def ext(node):
            up, dn = 2.54, 2.54
            if node.pu: up = max(up, 2.54 + max(ph(r) for r in node.pu) + 2.54 + 3.81)
            if node.sh: dn = max(dn, 2.54 + max(ph(r) for r in node.sh) + 5.08)
            for r, o, t in node.hg: dn = max(dn, 2.54 + ph(r) + 2.54 + (7.62 if t else 2.54))
            if node.ser:
                u2, d2 = ext(node.ser[1]); up = max(up, 5.08, u2); dn = max(dn, d2)
                if node.ser[1].net == "GND": dn = max(dn, 5.08)
            if node.term:
                if node.term in anchorset: up = max(up, 12.7); dn = max(dn, 12.7)
                else: up = max(up, 5.08)
            return up, dn
        ex = [ext(nd) for nd in nodes]
        # neighbouring lanes that each only have a pull-up to the same rail: resistors side by side under one rail wire
        brl = {i for b in br for i in (b[1], b[2])}
        pure = lambda k: len(nodes[k].pu) == 1 and not (nodes[k].sh or nodes[k].hg or nodes[k].ser or nodes[k].term) and lane_idx[k] not in brl
        prail = lambda k: other(nodes[k].pu[0], nodes[k].net)
        pgroups, k = [], 0
        while k < n:
            m = k
            if pure(k):
                while m + 1 < n and pure(m + 1) and prail(m + 1) == prail(k): m += 1
                if m > k:
                    pgroups.append(list(range(k, m + 1)))
                    for j in range(k + 1, m + 1): ex[j] = (2.54, ex[j][1])
            k = m + 1
        gap = []
        for k in range(n - 1):
            g_ = snap(ex[k][1] + ex[k + 1][0])
            for b in br:
                if {lane_idx.index(b[1]), lane_idx.index(b[2])} == {k, k + 1}: g_ = max(g_, snap2(ph(b[3]) + 5.08))
            gap.append(g_)
        rel = [0.0]
        for g_ in gap: rel.append(rel[-1] + g_)
        # lanes as close to their pins as their contents allow
        cl = [[k] for k in range(n)]
        off = lambda c: snap(sorted(pys[k] - rel[k] for k in c)[len(c) // 2])
        k = 0
        while k < len(cl) - 1:
            if off(cl[k]) > off(cl[k + 1]):
                cl[k] += cl.pop(k + 1); k = max(0, k - 1)
            else: k += 1
        yl = [0.0] * n
        for c in cl:
            for k in c: yl[k] = snap(rel[k] + off(c))
        if ymin is not None and yl[0] - ex[0][0] < ymin:
            yl[0] = snap(yl[0] + snap2(ymin - (yl[0] - ex[0][0])))
        for k in range(1, n): yl[k] = max(yl[k], snap(yl[k - 1] + gap[k - 1]))
        # fan-out from the pins to the lanes
        col, run, prev = {}, [], None
        def flush():
            if not run: return
            seq = run if prev == "up" else run[::-1]
            for c, k in enumerate(seq): col[k] = c + 1
        for k in range(n):
            d = "up" if yl[k] < pys[k] - 0.01 else "dn" if yl[k] > pys[k] + 0.01 else None
            if d != prev: flush(); run = []
            prev = d
            if d: run.append(k)
        flush()
        ncol = max([0] + list(col.values()))
        xs = snap(tip + sg * snap2(labx + 2.54 * (ncol + 1)))
        for k, i in enumerate(lane_idx):
            px = snap(gs[i]["x"])
            if k in col:
                xc = snap(tip + sg * (snap2(labx) + 2.54 * col[k]))
                cv.wire(px, pys[k], xc, pys[k]); cv.wire(xc, pys[k], xc, yl[k]); cv.wire(xc, yl[k], xs, yl[k])
            else: cv.wire(px, pys[k], xs, yl[k])
        # the zone next to the IC where parts stand between two lanes; dividers line up in one column
        slots, colw, zone = set(), {}, []
        usedmax = [-1] * n
        for b in sorted(br, key=lambda b: min(lane_idx.index(b[1]), lane_idx.index(b[2]))):
            k = min(lane_idx.index(b[1]), lane_idx.index(b[2]))
            c = 0
            while (k, "d", c) in slots or (k + 1, "u", c) in slots: c += 1
            slots |= {(k, "d", c), (k + 1, "u", c)}
            zone.append((c, k, "b", b[3])); colw[c] = max(colw.get(c, 0), wv(b[3]))
            usedmax[k] = max(usedmax[k], c); usedmax[k + 1] = max(usedmax[k + 1], c)
        inzone = set()
        for k, nd in enumerate(nodes):
            if usedmax[k] < 0: continue
            for kind, lst in (("u", [(r, None) for r in nd.pu]), ("d", [(r, None) for r in nd.sh] + [(r, o) for r, o, t in nd.hg if not t])):
                for r, o in lst:
                    for c in range(usedmax[k] + 1):
                        if (k, kind, c) not in slots:
                            slots.add((k, kind, c)); zone.append((c, k, kind, r)); inzone.add(r)
                            colw[c] = max(colw.get(c, 0), wv(r, o if o else (other(r, nd.net) if kind == "u" else None)))
                            break
        ucol = [0.0]
        for c in range(max(colw) + 1 if colw else 0): ucol.append(ucol[-1] + colw.get(c, 0))
        X = lambda u: snap(xs + sg * u)
        def colx(u, w, r=None):         # x of an upright part given the room u..u+w along the lane
            b = bw(r) if r else 0.0
            return snap(xs + u + 2.54 + b) if sg > 0 else snap(xs - (u + w) + 2.54 + b)
        touch = [[xs] for _ in range(n)]

        def pull(r, x, y, nd):
            o = other(r, nd.net)
            t_, b_ = vpart(cv, r, x, y - 2.54 - ph(r) / 2, o)
            cv.wire(x, b_, x, y); cv.wire(x, t_, x, t_ - 2.54); lab(cv, o, x, t_ - 2.54, 0)
        def shunt(r, x, y, nd):
            t_, b_ = vpart(cv, r, x, y + 2.54 + ph(r) / 2, nd.net)
            cv.wire(x, y, x, t_); cv.gnd(x, b_)
        def hang(r, o, t, x, y, nd):
            t_, b_ = vpart(cv, r, x, y + 2.54 + ph(r) / 2, nd.net)
            cv.wire(x, y, x, t_); cv.wire(x, b_, x, b_ + 2.54)
            if t: pad1(cv, t, x, b_ + 2.54, 1, down=True)
            else: lab(cv, o, x, b_ + 2.54, 0)

        ustart = [0.0] * n
        for ks in pgroups:
            u, xsr, rl = 0.0, [], prail(ks[0])
            for k in ks:
                r = nodes[k].pu[0]; w = wv(r); x = colx(u, w)
                t_, b_ = vpart(cv, r, x, yl[ks[0]] - 2.54 - ph(r) / 2, rl)
                cv.wire(x, b_, x, yl[k]); cv.wire(x, t_, x, t_ - 2.54)
                xsr.append(x); touch[k].append(x); inzone.add(r); u += w
            yr = t_ - 2.54
            xe = max(xsr) + 2.54 if sg > 0 else min(xsr) - 2.54
            cv.wire(min(xsr + [xe]), yr, max(xsr + [xe]), yr); lab(cv, rl, xe, yr, 0 if sg > 0 else 180)
            for k in ks: ustart[k] = u
        for c, k, kind, r in zone:
            w = colw[c]; x = colx(ucol[c], w); nd = nodes[k]
            if kind == "b":
                ym = snap((yl[k] + yl[k + 1]) / 2)
                t_, b_ = vpart(cv, r, x, ym, nd.net)
                cv.wire(x, yl[k], x, t_); cv.wire(x, b_, x, yl[k + 1])
                touch[k].append(x); touch[k + 1].append(x)
            elif kind == "u": pull(r, x, yl[k], nd); touch[k].append(x)
            else:
                hg = [h for h in nd.hg if h[0] == r]
                if hg: hang(r, hg[0][1], None, x, yl[k], nd)
                else: shunt(r, x, yl[k], nd)
                touch[k].append(x)

        def lay(nd, k, u, x0, depth):
            """draw one net of lane k from x0 (distance u from the lane start) outward. Returns (u at the end, x of the end)."""
            y = yl[k]; pts = [x0]
            if depth > 0 and (nd.net == "GND" or hub(nd.net) or nd.net in glob or not (nd.any() or nd.close is not None)):
                xe = snap(x0 + sg * 2.54); cv.wire(x0, y, xe, y)
                lab(cv, nd.net, xe, y, 0 if sg > 0 else 180)
                return u + 2.54 + (lw(nd.net) if nd.net != "GND" else 2.54), xe
            for r in nd.pu:
                if r in inzone: continue
                w = wv(r, other(r, nd.net)); x = colx(u, w, r); pull(r, x, y, nd); pts.append(x); u += w
            for r in nd.sh:
                if r in inzone: continue
                w = wv(r); x = colx(u, w, r); shunt(r, x, y, nd); pts.append(x); u += w
            for r, o, t in nd.hg:
                if r in inzone: continue
                w = wv(r, o) if not t else max(wv(r), snap2(2.54 + tl(t) + 3.81)); x = colx(u, w, r); hang(r, o, t, x, y, nd); pts.append(x); u += w
            far = lambda: max(pts) if sg > 0 else min(pts)
            ret = None
            if nd.ser:
                r, ch = nd.ser
                if need_label(nd):
                    cv.label(short(nd.net), X(u + 1.27), y, 0 if sg > 0 else 180, False); u += snap2(lw(nd.net) + 1.27)
                w = snap2(max(ph(r), tl1(r)) + 2.54)
                xc = X(u + w / 2)
                xl, xr = hpart(cv, r, xc, y, nd.net if sg > 0 else ch.net)
                near, fr = (xl, xr) if sg > 0 else (xr, xl)
                pts.append(near)
                ret = lay(ch, k, max(abs(fr - xs), u + w - 1.27), fr, depth + 1)
            elif nd.term:
                t = nd.term
                if need_label(nd):
                    cv.label(short(nd.net), X(u + 1.27), y, 0 if sg > 0 else 180, False); u += snap2(lw(nd.net) + 1.27)
                xe = X(u + 2.54); pts.append(xe)
                if t in anchorset:
                    gq = next(g2 for g2 in PG[t] if g2["angle"] == 0 and g2["net"] == nd.net)
                    ox, oy = snap(xe - gq["x"]), snap(y + gq["y"])
                    cv.symbol(comps[t], t, ox, oy, 0, ref_at=(ox + 6.35, oy - 1.27), val_at=(ox + 6.35, oy + 1.27))
                    vpins(cv, t, ox, oy)
                    ret = (u + 2.54 + 12.7 + tl(t), xe)
                else:
                    pad1(cv, t, xe, y, sg)
                    ret = (u + 2.54 + 5.08 + tl(t), xe)
            elif nd.close is not None:
                ret = (u, far())
            elif need_label(nd):
                xe = X(max(u, abs(far() - xs)) + 2.54); pts.append(xe)
                lab(cv, nd.net, xe, y, 0 if sg > 0 else 180)
                ret = (abs(xe - xs) + lw(nd.net), xe)
            else:
                ret = (u, far())
            cv.wire(x0, y, far(), y)
            return ret

        endx = {}
        for k, nd in enumerate(nodes):
            x0 = max(touch[k]) if sg > 0 else min(touch[k])
            cv.wire(xs, yl[k], x0, yl[k])
            u0 = ucol[usedmax[k] + 1] if usedmax[k] >= 0 else ustart[k]
            # in the bridge zone the lane's own label must not sit on a part: start after it
            endx[k] = lay(nd, k, u0, x0, 0)
        for k, nd0 in enumerate(nodes):
            for nd in walk(nd0):
                if nd.close is None: continue
                j = lane_idx.index(nd.close)
                xe = X(max(endx[k][0], endx[j][0]) + 2.54)
                cv.wire(endx[k][1], yl[k], xe, yl[k]); cv.wire(endx[j][1], yl[j], xe, yl[j]); cv.wire(xe, yl[k], xe, yl[j])

    def buck(cv, a, t, lab_l, lab_r):
        """Buck converter around IC a (at 0,0): input caps to the left of VIN, inductor in line with SW, feedback and
        output caps to the right."""
        P = lambda nm: next(g for g in PG[a] if g["name"] == nm)
        pos = lambda g: (snap(g["x"]), snap(-g["y"]))
        vin, sw = P(t["vin"]), P(t["sw"])
        nvin, nsw = vin["net"], sw["net"]
        L = t["inductor"]; nout = other(L, nsw)
        (vx, vy), (sx, sy) = pos(vin), pos(sw)
        def hang(rs, x, y, net):
            for r in rs:
                t_, b_ = vpart(cv, r, x, y + 2.54 + ph(r) / 2, net)
                cv.wire(x, y, x, t_)
                o = other(r, net)
                if o == "GND": cv.gnd(x, b_)
                else: cv.wire(x, b_, x, b_ + 2.54); lab(cv, o, x, b_ + 2.54, 0)
                x = snap(x + wv(r))
            return x
        # input side: the first capacitor listed sits nearest the IC
        x = snap(vx - snap2(lab_l) - 2.54)
        for r in t.get("cin", []):
            x = snap(x - wv(r)); hang([r], x, vy, nvin)
        xe = snap(x - 5.08)
        cv.wire(vx, vy, xe, vy); lab(cv, nvin, xe, vy, 180)
        # switch node, bootstrap, inductor
        xa = snap(sx + snap2(lab_r) + 2.54)
        xi = xa + 2.54
        if t.get("boot"):
            bx, by = pos(P(t["bst"])); nb = P(t["bst"])["net"]
            top, bot = (by, sy) if by < sy else (sy, by)
            t_, b_ = vpart(cv, t["boot"], xa, snap((by + sy) / 2), nb if by < sy else nsw)
            cv.wire(bx, by, xa, by); cv.wire(xa, top, xa, t_); cv.wire(xa, b_, xa, bot)
            xi = xa + wv(t["boot"])
        cv.label(short(nsw), sx + 1.27, sy, 0, False)
        xi = max(xi, sx + 1.27 + lw(nsw) + 1.27)
        wl_ = snap2(max(ph(L), tl1(L)) + 2.54)
        xl, xr = hpart(cv, L, snap(xi + wl_ / 2), sy, nsw)
        cv.wire(sx, sy, xl, sy)
        xo = snap(xr + 5.08)
        nxt = xo + 7.62
        if t.get("sense"):
            qx, qy = pos(P(t["sense"]))
            cv.wire(qx, qy, xo, qy); cv.wire(xo, qy, xo, sy)
        if t.get("fb"):
            qx, qy = pos(P(t["fb"])); nfb = P(t["fb"])["net"]
            top_r, bot_r = t["div"]
            t1, b1 = vpart(cv, top_r, xo, snap(sy + 2.54 + 3.81), nout)
            ym = snap(max(b1 + 2.54, qy))
            t2, b2 = vpart(cv, bot_r, xo, snap(ym + 2.54 + 3.81), nfb)
            cv.wire(xo, sy, xo, t1); cv.wire(xo, b1, xo, t2)
            lab(cv, other(bot_r, nfb), xo, b2, 0) if other(bot_r, nfb) == "GND" else (cv.wire(xo, b2, xo, b2 + 2.54), lab(cv, other(bot_r, nfb), xo, b2 + 2.54, 0))
            xf = snap(xa + 2.54) if not t.get("boot") else snap(xa - 0)
            if abs(qy - ym) < 0.01: cv.wire(qx, qy, xo, ym)
            else:
                xf = snap(sx + snap2(lab_r) + 2.54 + (0 if not t.get("boot") else 0))
                cv.wire(qx, qy, xf, qy); cv.wire(xf, qy, xf, ym); cv.wire(xf, ym, xo, ym)
            cv.label(short(nfb), qx + 1.27, qy, 0, False)
            nxt = xo + max(wv(top_r), wv(bot_r))
        x2 = hang(t.get("cout", []), nxt, sy, nout)
        xe = snap(x2 + 2.54)
        cv.wire(xr, sy, xe, sy); lab(cv, nout, xe, sy, 0)

    def bridge4(a, t):
        """Four-switch buck-boost drawn as a power path, left to right: input shunt with its Kelvin filter, input caps,
        input half bridge, inductor, output half bridge, output caps, output shunt with its Kelvin filter."""
        cv = Canvas()
        qa, qb = a, t["q_out"]
        net = lambda q_, nm, u: next(pinnet[(q_, p["num"])] for p in pins_of[q_] if p["name"] == nm and p["unit"] == u)
        def box(q_, u, x, y, mir):
            cv.symbol(comps[q_], q_, x, y, 0, unit=u, ref_at=(x - 6.35 + (11.43 if mir else 0), y - 7.0),
                      val_at=(x - 6.35 + (11.43 if mir else 0), y - 5.0), mirror=mir)
            out = {}
            for p in pins_of[q_]:
                if p["unit"] == u: out[p["name"]] = (snap(x + (-p["x"] if mir else p["x"])), snap(y - p["y"]))
            return out
        def hang(rs, x, y, net_):
            for r in rs:
                t_, b_ = vpart(cv, r, x, y + 2.54 + ph(r) / 2, net_)
                cv.wire(x, y, x, t_); cv.gnd(x, b_)
                x = snap(x + wv(r))
            return x
        def shunt(rs, x1, y, nl):
            """sense resistor rs in line from x1, left net nl; Kelvin filter below it if the block declares one. Returns right x."""
            K = kel.get(rs)
            x2 = snap(x1 + (30.48 if K else snap2(max(ph(rs), tl1(rs)) + 2.54)))
            xl, xr = hpart(cv, rs, snap((x1 + x2) / 2), y, nl)
            cv.wire(x1, y, xl, y); cv.wire(xr, y, x2, y)
            if not K: return x2, x2
            A = (K["rp"], K["pos"], K["cp"]); B = (K["rn"], K["neg"], K["cn"])
            if K["src_pos"] != nl: A, B = B, A
            yn = snap(y + 2.54 + 7.62 + 2.54)
            for (r, nn, cs), x, src in ((A, x1, nl), (B, x2, other(rs, nl))):
                t_, b_ = vpart(cv, r, x, y + 2.54 + 3.81, src)
                cv.wire(x, y, x, t_); cv.wire(x, b_, x, yn)
                xx = x
                for c in cs:
                    t_, b_ = vpart(cv, c, xx, yn + 2.54 + ph(c) / 2, nn)
                    cv.wire(xx, yn, xx, t_); cv.gnd(xx, b_)
                    xx = snap(xx + wv(c))
            if K["cd"]:
                cl_, cr_ = hpart(cv, K["cd"][0], snap((x1 + x2) / 2 + 1.27), yn, A[1], text_y=yn - 3.4)
                cv.wire(x1, yn, cl_, yn); cv.wire(cr_, yn, x2, yn)
            cv.wire(x1 - 2.54, yn, x1, yn); lab(cv, A[1], x1 - 2.54, yn, 180)
            cv.wire(x2, yn, x2 + 2.54, yn); lab(cv, B[1], x2 + 2.54, yn, 0)
            return x2, snap(x2 + max([2.54 + lw(B[1])] + [wv(B[0])] + [wv(c) for c in B[2]]))
        n_in, n_out = net(qa, "D1", 1), net(qb, "D1", 1)
        n_sw1, n_sw2 = net(qa, "SW", 1), net(qb, "SW", 1)
        lab_ = max(len(short(net(q_, g, u))) for q_ in (qa, qb) for g, u in (("G1", 1), ("G2", 2))) * CH + 5.08
        yr = 0.0; ya = snap(yr + 15.24); yb = snap(ya + 15.24)
        # input: label, shunt, caps
        n_src = other(t["rin"], n_in)
        x = 0.0
        lab(cv, n_src, x, yr, 180)
        x1 = snap(x + 5.08)
        cv.wire(x, yr, x1, yr)
        xr, xclear = shunt(t["rin"], x1, yr, n_src)
        cv.label(short(n_in), xr + 1.27, yr - 0.0, 0, False)
        xc = snap(max(xclear, xr + lw(n_in) + 2.54) + 2.54)
        xn = hang(t["cin"], xc, yr, n_in)
        # input half bridge
        qx = snap(xn + lab_ + 6.35)
        A = box(qa, 1, qx, ya, False); B = box(qa, 2, qx, yb, False)
        xd, xs_ = snap(qx + 8.89), snap(qx + 11.43)
        cv.wire(xr, yr, xd, yr); cv.wire(xd, yr, xd, A["D1"][1]); cv.wire(A["D1"][0], A["D1"][1], xd, A["D1"][1])
        ysw = A["SW"][1]
        cv.wire(A["SW"][0], ysw, xs_, ysw); cv.wire(B["SW"][0], B["SW"][1], xs_, B["SW"][1]); cv.wire(xs_, ysw, xs_, B["SW"][1])
        cv.wire(B["S2"][0], B["S2"][1], xd, B["S2"][1]); cv.wire(xd, B["S2"][1], xd, B["S2"][1] + 2.54); cv.gnd(xd, B["S2"][1] + 2.54)
        lab(cv, net(qa, "G1", 1), A["G1"][0], A["G1"][1], 180); lab(cv, net(qa, "G2", 2), B["G2"][0], B["G2"][1], 180)
        # inductor
        cv.label(short(n_sw1), xs_ + 1.27, ysw, 0, False)
        xi = snap(xs_ + lw(n_sw1) + 3.81)
        wl_ = snap2(max(ph(t["inductor"]), tl1(t["inductor"])) + 2.54)
        il, ir = hpart(cv, t["inductor"], xi + wl_ / 2, ysw, n_sw1)
        cv.wire(xs_, ysw, il, ysw)
        cv.label(short(n_sw2), ir + 1.27, ysw, 0, False)
        xs2 = snap(ir + lw(n_sw2) + 3.81)
        # output half bridge, mirrored
        qx2 = snap(xs2 + 11.43)
        A2 = box(qb, 1, qx2, ya, True); B2 = box(qb, 2, qx2, yb, True)
        xd2 = snap(qx2 - 8.89)
        cv.wire(ir, ysw, xs2, ysw); cv.wire(xs2, ysw, A2["SW"][0], ysw); cv.wire(xs2, ysw, xs2, B2["SW"][1]); cv.wire(xs2, B2["SW"][1], B2["SW"][0], B2["SW"][1])
        cv.wire(A2["D1"][0], A2["D1"][1], xd2, A2["D1"][1]); cv.wire(xd2, A2["D1"][1], xd2, yr)
        cv.wire(B2["S2"][0], B2["S2"][1], xd2, B2["S2"][1]); cv.wire(xd2, B2["S2"][1], xd2, B2["S2"][1] + 2.54); cv.gnd(xd2, B2["S2"][1] + 2.54)
        lab(cv, net(qb, "G1", 1), A2["G1"][0], A2["G1"][1], 0); lab(cv, net(qb, "G2", 2), B2["G2"][0], B2["G2"][1], 0)
        # output: caps, shunt, label
        xo = snap(qx2 + 6.35 + lab_ + 2.54)
        xn = hang(t["cout"], xo, yr, n_out)
        cv.label(short(n_out), xn, yr, 0, False)
        n_dst = other(t["rout"], n_out)
        K = kel.get(t["rout"])
        x1 = snap(xn + lw(n_out) + 2.54 + (lw(K["pos"]) if K else 0))
        cv.wire(xd2, yr, x1, yr)
        x2, xclear = shunt(t["rout"], x1, yr, n_out)
        xe = snap(x2 + 5.08)
        cv.wire(x2, yr, xe, yr); lab(cv, n_dst, xe, yr, 0)
        return cv

    def fetpair(a, t):
        """Two FETs back to back in a power path, left to right: source rail of the first along the bottom, drains joined,
        source rail of the second; gate-source parts stand between each gate and its source rail; gate drive in line."""
        cv = Canvas(); F = fpair[a]; qa, qb = a, t["q_out"]
        pn = lambda q_, nm: next(g for g in PG[q_] if g["name"] == nm)
        nmid = pn(qa, "D")["net"]
        xa = 0.0; xb = snap(xa + 12.7 + max(snap2(lw(nmid) + 7.62), sum(snap2(tl1(r) + 7.62) for r in F["byp"])) + 5.08)
        yb = 11.43
        ends_ = {}
        for q_, x, mir, sg in ((qa, xa, False, -1), (qb, xb, True, 1)):
            cv.symbol(comps[q_], q_, x, 0, 0, mirror=mir, ref_at=(x - 6.35, -7.0), val_at=(x - 6.35, -5.0))
            P = lambda nm: (snap(x + (-1 if mir else 1) * pn(q_, nm)["x"]), snap(-pn(q_, nm)["y"]))
            (gx, gy), (dx, dy), (sx, sy) = P("G"), P("D"), P("S")
            ng, ns = pn(q_, "G")["net"], pn(q_, "S")["net"]
            xr = snap(sx - sg * 2.54)
            cv.wire(sx, sy, xr, sy); cv.wire(xr, sy, xr, yb)
            gsl, ser = F["gate"][q_]
            xx = gx
            prev = None
            for r in gsl:
                if sg < 0: xx = snap(xx - wv(r))
                else: xx = snap(xx + (5.08 if prev is None else wv(prev)))
                prev = r
                t_, b_ = vpart(cv, r, xx, snap((gy + yb) / 2), ng)
                cv.wire(xx, gy, xx, t_); cv.wire(xx, b_, xx, yb)
            if sg > 0 and gsl: xx = snap(xx + wv(gsl[-1]) - 5.08)
            for r in ser:
                w = snap2(max(ph(r), tl1(r)) + 2.54)
                xc = snap(xx + sg * (2.54 + w / 2))
                o = other(r, ng)
                xl, xr2 = hpart(cv, r, xc, gy, o if sg < 0 else ng)
                far = xl if sg < 0 else xr2
                xe = snap(far + sg * 2.54)
                cv.wire(gx, gy, xr2 if sg < 0 else xl, gy); cv.wire(far, gy, xe, gy)
                lab(cv, o, xe, gy, 180 if sg < 0 else 0)
                xx = xe
            if not ser: cv.wire(gx, gy, xx, gy)
            ends_[q_] = (xr, xx, ns, (dx, dy))
        (xra, xla, nsa, da), (xrb, xlb, nsb, db) = ends_[qa], ends_[qb]
        cv.wire(da[0], da[1], db[0], db[1]); cv.label(short(nmid), da[0] + 2.54, da[1], 0, False)
        # taps on the first source rail, left of the gate parts
        xt = snap(xla - 2.54)
        for r, pad in F["taps"]:
            xt = snap(xt - wv(r))
            t_, b_ = vpart(cv, r, xt, yb + 2.54 + ph(r) / 2, nsa)
            cv.wire(xt, yb, xt, t_)
            o = other(r, nsa)
            if o == "GND": cv.gnd(xt, b_)
            else:
                cv.wire(xt, b_, xt, b_ + 2.54)
                if pad: pad1(cv, pad, xt, b_ + 2.54, 1, down=True)
                else: lab(cv, o, xt, b_ + 2.54, 0)
        x0 = snap(min(xt, xla) - 5.08)
        cv.wire(x0, yb, xra, yb); lab(cv, nsa, x0, yb, 180)
        x1 = snap(xlb + 2.54)
        cv.wire(xrb, yb, x1, yb); lab(cv, nsb, x1, yb, 0)
        # parts across the pair, in series from rail to rail
        if F["byp"]:
            yc = snap(yb + 8.89)
            cv.wire(xra, yb, xra, yc); cv.wire(xrb, yb, xrb, yc)
            n = len(F["byp"]); net_ = nsa; xprev = xra
            for k, r in enumerate(F["byp"]):
                xc = snap(xra + (xrb - xra) * (k + 1) / (n + 1))
                xl, xr2 = hpart(cv, r, xc, yc, net_, text_y=yc + 3.6)
                cv.wire(xprev, yc, xl, yc); xprev = xr2; net_ = other(r, net_)
            cv.wire(xprev, yc, xrb, yc)
        return cv

    def draw_anchor(a):
        """One part with more than two pins, the passives on its pins wired to them, and a label on every other pin."""
        t = tdraw.get(a)
        if t and t["kind"] == "bridge4": return bridge4(a, t)
        if t and t["kind"] == "fetpair": return fetpair(a, t)
        cv = Canvas(); gs = PG[a]
        tw = twired.get(a, set())
        ymin = None
        if t: ymin = snap(-next(g for g in gs if g["name"] == t["vin"])["y"]) + 2.54
        for sd in (0, 180):
            sg = 1 if sd == 180 else -1
            lst = sorted([i for i in range(npos[a]) if gs[i]["angle"] == sd], key=lambda i: -gs[i]["y"])
            lanes = lanes_of(a, sd)
            wired = set(lanes) | tw
            labx, k = 0.0, 0
            while k < len(lst):
                i = lst[k]; g = gs[i]; x, y = snap(g["x"]), snap(-g["y"]); n = g["net"]
                if i in wired: k += 1; continue
                if n is None: cv.nc(x, y); k += 1; continue
                m = k
                while m + 1 < len(lst) and lst[m + 1] not in wired and gs[lst[m + 1]]["net"] == n: m += 1
                xj = snap(x + sg * 2.54)
                adj = [lst[q_] for q_ in (k - 1, m + 1) if 0 <= q_ < len(lst) and lst[q_] in wired and gs[lst[q_]]["net"] == n]
                if m > k or adj:
                    ys = [snap(-gs[lst[q_]]["y"]) for q_ in range(k, m + 1)]
                    for yy in ys: cv.wire(x, yy, xj, yy)
                    y0, y1 = ys[0], ys[-1]
                    if adj: ya_ = snap(-gs[adj[0]]["y"]); y0, y1 = min(y0, ya_), max(y1, ya_)
                    cv.wire(xj, y0, xj, y1)
                    if adj: labx = max(labx, 2.54)
                    elif n == "GND": cv.gnd(xj, snap((ys[0] + ys[-1]) / 2), 90 if sg > 0 else 270); labx = max(labx, 2.54 + 3.81)
                    else: cv.label(short(n), xj, ys[0], 0 if sg > 0 else 180, n in glob); labx = max(labx, 2.54 + lw(n))
                elif n == "GND": cv.gnd(x, y, 90 if sg > 0 else 270); labx = max(labx, 3.81)
                else: cv.label(short(n), x, y, 0 if sg > 0 else 180, n in glob); labx = max(labx, lw(n))
                k = m + 1
            lay_side(cv, a, sd, lanes, labx + 1.27, ymin if sd == 0 else None)
        l, tp, rgt, bt = body(a)
        tops = sorted(g["x"] for g in gs if g["angle"] == 270); bots = sorted(g["x"] for g in gs if g["angle"] == 90)
        has_runs = any(gs[i]["angle"] == 270 and (a, i) in roots and roots[(a, i)].sh for i in range(npos[a]))
        tlen = tl(a)
        if npos[a] == 3 and tops and bots and not any(g["angle"] == 180 for g in gs):
            kw = dict(ref_at=(max(tops + bots) + 3.81, -1.27), val_at=(max(tops + bots) + 3.81, 1.27))
        elif not tops or tops[0] > l + tlen + 1.5:
            kw = dict(ref_at=(l, tp - 4.0), val_at=(l, tp - 2.0))
        elif not has_runs:
            kw = dict(ref_at=(tops[0] - 2.5, tp - 4.0), val_at=(tops[0] - 2.5, tp - 2.0), just="right")
        elif bots:
            kw = dict(ref_at=(bots[0] - 2.5, bt + 2.0), val_at=(bots[0] - 2.5, bt + 4.0), just="right")
        else:
            kw = dict(ref_at=(l, bt + 2.0), val_at=(l, bt + 4.0))
        cv.symbol(comps[a], a, 0, 0, 0, **kw)
        vpins(cv, a, 0, 0)
        if t:
            vx = snap(next(g for g in gs if g["name"] == t["vin"])["x"]); sx = snap(next(g for g in gs if g["name"] == t["sw"])["x"])
            buck(cv, a, t, max(0.0, vx - cv.bb[0]), max(0.0, cv.bb[2] - sx))
        return cv

    # ---- parts no pin claimed: wire pads, test points, capacitors across two rails ----
    rank = lambda n: 0 if n == "GND" else 2 if rail(n) else 1
    left = [r for r in small if r not in owned and r not in templ]
    left2 = [r for r in left if npos[r] == 2]; lset = set(left2)
    priv = lambda n: bool(n) and n != "GND" and not hub(n) and netrefs[n] <= lset and len(netrefs[n]) == 2
    used, cells = set(), []
    for r in left2:
        if r in used: continue
        pn = [n for n in ends(r) if priv(n)]
        if len(pn) != 1: continue
        seq, cur = [r], pn[0]; nodes = [other(r, cur), cur]
        while True:
            nx = [x for x in netrefs[cur] if x != seq[-1]][0]
            if nx in used or nx in seq: break
            seq.append(nx); o = other(nx, cur); nodes.append(o)
            if not priv(o): break
            cur = o
        if len(seq) > 1 and len(nodes) == len(seq) + 1:
            if rank(nodes[0]) < rank(nodes[-1]): seq.reverse(); nodes.reverse()
            cells.append(("chain", seq, nodes)); used.update(seq)
    banks = {}
    for r in left2:
        if r not in used: banks.setdefault((frozenset(ends(r)), section_of(r)), []).append(r)
    for rs in banks.values(): cells.append(("bank", rs, None))
    for r in left:
        if npos[r] == 1: cells.append(("pad", [r], None))
    cells.sort(key=lambda c: refs.index(c[1][0]))

    def draw_cell(c):
        cv = Canvas(); kind, rs, nodes = c
        if kind == "pad":
            r = rs[0]; n = ends(r)[0]
            pad1(cv, r, 0, 0, 1)
            if n == "GND":
                if abs(PG[r][0]["x"]) < 0.01: cv.gnd(0, 0)
                else: cv.wire(0, 0, -2.54, 0); cv.gnd(-2.54, 0)
            else: cv.wire(0, 0, -2.54, 0); lab(cv, n, -2.54, 0, 180)
        elif kind == "bank":
            e = sorted(set(ends(rs[0])), key=lambda n: -rank(n)); up, dn = e[0], e[-1]
            x, xs_, bs = 0.0, [], []
            for r in rs:
                t_, b_ = vpart(cv, r, x, 2.54 + ph(r) / 2, up)
                cv.wire(x, 0, x, t_); xs_.append(x); bs.append(b_)
                if dn == "GND": cv.gnd(x, b_)
                x = snap(x + wv(r))
            cv.wire(-2.54, 0, xs_[-1], 0); lab(cv, up, -2.54, 0, 180)
            if dn != "GND":
                yb = max(bs) + 2.54
                for xx, b_ in zip(xs_, bs): cv.wire(xx, b_, xx, yb)
                cv.wire(-2.54, yb, xs_[-1], yb); lab(cv, dn, -2.54, yb, 180)
        else:
            y = 0.0
            cv.wire(-2.54, 0, 0, 0); lab(cv, nodes[0], -2.54, 0, 180)
            for j, r in enumerate(rs):
                t_, b_ = vpart(cv, r, 0, y + 2.54 + ph(r) / 2, nodes[j])
                cv.wire(0, y, 0, t_)
                if j == len(rs) - 1:
                    if nodes[j + 1] == "GND": cv.gnd(0, b_)
                    else: cv.wire(0, b_, 0, b_ + 2.54); cv.wire(0, b_ + 2.54, -2.54, b_ + 2.54); lab(cv, nodes[j + 1], -2.54, b_ + 2.54, 180)
                else:
                    y = snap(b_ + 2.54); cv.wire(0, b_, 0, y)
                    if netrefs[nodes[j + 1]] - set(rs): cv.wire(0, y, -2.54, y); lab(cv, nodes[j + 1], -2.54, y, 180)
        return cv

    # ---- sections: title, notes, the parts ----
    sections = []
    for r in refs:
        t = section_of(r)
        if t not in [s_[0] for s_ in sections]: sections.append((t, []))
        [s_ for s_ in sections if s_[0] == t][0][1].append(r)
    notes = {}
    for sec_, lines in cons.get("notes", {}).get(block, {}).items(): notes.setdefault(sec_, []).extend(lines)
    for key, e in cons.get("expect", {}).items():
        if not key.startswith(block + "/") or not e.get("at"): continue
        a = e["at"].split(".")[0]
        if a not in refset: continue
        parts = [v for v in e["bind"].values() if v in refset]
        notes.setdefault(section_of(a), []).append(
            f"{key.split('/', 1)[1]}: {e['target']:g} {e['unit']} +/-{e['tol'] * 100:g}% at {e['at']}" + (f" (set by {', '.join(parts)})" if parts else ""))
    def tree_parts(a):
        out = [b[3] for b in bridges if b[0] == a]
        for (a2, _), n0 in roots.items():
            if a2 != a: continue
            for nd in walk(n0):
                out += nd.sh + nd.pu + [h[0] for h in nd.hg] + [h[2] for h in nd.hg if h[2]] + ([nd.ser[0]] if nd.ser else [])
                if nd.term: out += [nd.term] + (tree_parts(nd.term) if nd.term in anchorset else [])
        return out
    for t, mem in sections:
        here = [r for a in anchors if a in set(mem) for r in tree_parts(a)]
        for a in anchors:
            if a in set(mem) and a in tdraw:
                td = tdraw[a]; here += [td[k_] for k_ in ("inductor",) if k_ in td] + td.get("cin", []) + td.get("cout", [])
        other_sec = {}
        for r in here:
            if section_of(r) != t: other_sec.setdefault(section_of(r), []).append(r)
        for t2, rs in other_sec.items():
            if len(set(rs)) < 3: continue
            rs = sorted(set(rs), key=refs.index)
            notes.setdefault(t, []).append(f"Also drawn here: {t2.split(':')[0].split('.')[0]} ({', '.join(rs[:6])}{', ...' if len(rs) > 6 else ''})")
    items = {}
    for t, mem in sections:
        mset = set(mem)
        its = [draw_anchor(a) for a in anchors if a in mset]
        its += [draw_cell(c) for c in cells if c[1][0] in mset]
        items[t] = [i for i in its if i.bb is not None]

    def build_section(t, W):
        cv = Canvas()
        cv.text(t, 0, 0, 2.0, True)
        y = 0.5
        import textwrap
        wn = max([i.w for i in items[t]] + [len(t) * 1.9, 100.0])       # notes wrap to the width of what they describe
        for ln in notes.get(t, []):
            for part in textwrap.wrap(ln, max(40, int(wn / 1.42)), subsequent_indent="   "):
                y += 3.0; cv.text(part, 0, y, 1.5)
        y += 6.35
        x, rowh = 0.0, 0.0
        for it in items[t]:
            if x > 0 and x + it.w > W: x = 0.0; y += rowh + 7.62; rowh = 0.0
            cv.add(it, snap(x - it.bb[0]), snap(y - it.bb[1]))
            x += it.w + 10.16; rowh = max(rowh, it.h)
        return cv

    GX, GY = 17.78, 12.7
    colh = lambda c: sum(x.h for x in c) + GY * (len(c) - 1)
    colw = lambda c: max(x.w for x in c)
    roww = lambda row: sum(colw(c) for c in row) + GX * (len(row) - 1)
    def pack(W):
        """rows of columns of sections: a short section may sit under another one beside a tall section"""
        secs = [build_section(t, W) for t, _ in sections if items[t]]
        rows = []
        for s in secs:
            placed = False
            if rows:
                row = rows[-1]; rowh = max(colh(c) for c in row)
                for c in row[::-1]:
                    if colh(c) + GY + s.h <= rowh * 1.12 + 0.01 and roww(row) - colw(c) + max(colw(c), s.w) <= W:
                        c.append(s); placed = True; break
                if not placed and roww(row) + GX + s.w <= W: row.append([s]); placed = True
            if not placed: rows.append([[s]])
        return rows, max(roww(r) for r in rows), sum(max(colh(c) for c in r) for r in rows) + GY * (len(rows) - 1)
    MX, TOP, BOT = 20.0, 30.0, 16.0
    def place(rows, pw):
        out, y = [], TOP
        for row in rows:
            x = MX
            spare = min(30.0, max(0.0, (pw - 2 * MX - roww(row)) / len(row))) if len(row) > 1 else 0.0
            rowh = max(colh(c) for c in row)
            for c in row:
                yy = y
                vs = min(25.0, (rowh - colh(c)) / (len(c) - 1)) if len(c) > 1 else 0.0     # spread a short column down its row
                for s in c: out.append((s, x, yy)); yy += s.h + GY + vs
                x += colw(c) + GX + spare
            y += max(colh(c) for c in row) + GY
        return out
    best = None
    for W in range(150, 900, 10):
        rows, wused, h = pack(W)
        pw, phh = max(210.0, wused + 2 * MX), max(148.0, h + TOP + BOT)
        if any(x + s.w > pw - 125 and y + s.h > phh - 48 for s, x, y in place(rows, pw)): phh += 38      # keep clear of the title block
        fill = sum(s.w * s.h for row in rows for c in row for s in c) / (pw * phh)
        cost = 0.6 * abs(math.log((pw / phh) / 1.42)) - 1.5 * fill + (5 if not 1.15 <= pw / phh <= 1.9 else 0)
        if best is None or cost < best[0] - 1e-9: best = (cost, rows, pw, phh)
    _, rows, pw, phh = best
    pw, phh = math.ceil(pw / 10) * 10, math.ceil(phh / 10) * 10
    sheet.size = (pw, phh)
    sheet.text(sheet.title, MX, 19, 3.5, True)
    for s, x, y in place(rows, pw):
        s.emit(sheet, snap(x - s.bb[0]), snap(y - s.bb[1]))


def main(build, out, project):
    d = json.load(open(f"{build}/netlist.json"))
    cons = json.load(open(f"{build}/constraints.json"))
    comps, nets, nc = d["comps"], d["nets"], d.get("nc", [])
    order = sorted(comps, key=lambda r: comps[r].get("order", 0))
    os.makedirs(out, exist_ok=True)
    root_uuid = uid("root", project)
    blocks = []
    for r in order:
        b = comps[r]["block"]
        if b not in blocks: blocks.append(b)
    root = [f'(kicad_sch (version {VERSION}) (generator "p2p_draw") (generator_version "10.0") (uuid {q(root_uuid)}) (paper "A4") '
            f'(title_block (title {q(project)}) (comment 1 "Generated from code. Do not edit: change the source and rebuild.")) (lib_symbols)']
    for i, b in enumerate(blocks):
        fn = b.lower().replace(" ", "_") + ".kicad_sch"
        s = Sheet(b, project, root_uuid, b)
        draw_block(s, b, comps, nets, nc, cons, order)
        s.write(f"{out}/{fn}", i + 2)
        x, y = 30 + (i % 3) * 80, 40 + (i // 3) * 50
        root.append(
            f'(sheet (at {x} {y}) (size 60 30) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (stroke (width 0.1524) (type solid)) '
            f'(fill (color 0 0 0 0)) (uuid {q(s.uuid)}) '
            f'(property "Sheetname" {q(b)} (at {x} {y - 0.7} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) '
            f'(property "Sheetfile" {q(fn)} (at {x} {y + 30.6} 0) (effects (font (size 1.27 1.27)) (justify left top))) '
            f'(instances (project {q(project)} (path {q("/" + root_uuid)} (page {q(i + 2)})))))')
    root.append('(sheet_instances (path "/" (page "1"))) (embedded_fonts no))')
    open(f"{out}/{project}.kicad_sch", "w").write("\n".join(root) + "\n")
    print("wrote", len(blocks), "sheets to", out)

if __name__ == "__main__":
    main(*sys.argv[1:4])
