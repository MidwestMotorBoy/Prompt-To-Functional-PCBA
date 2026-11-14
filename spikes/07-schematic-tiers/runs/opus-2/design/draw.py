"""Draws KiCad schematic sheets from netlist.json. The netlist is the truth; these sheets are a view of it.

How a sheet is drawn (the rules a careful engineer follows, as code):
  * Supplies are power symbols pointing up, grounds point down. Labels are kept for signals that leave the
    drawing; a global label marks a net that leaves the sheet.
  * Every IC is drawn with the passives that serve its pins wired straight to those pins: decoupling caps hang
    from the pin's wire to ground, pull-ups rise to their supply symbol, series parts sit in line and end in the
    label of the net they lead to, and a part between two pins of the same IC (a divider leg, a filter cap of an
    RC ladder) stands between the two pin wires. Pins with parts are spread onto lanes so the parts have room.
  * Known circuits have templates (buck converter, four-switch bridge, battery-pack power path, Kelvin sense
    filter) so they look like their textbook drawing; blocks ask for them with draw_as().
  * A final pass replaces label pairs of the same net that sit close together by a wire when a clean route
    exists, and checks that no wire, text or symbol overlaps another.
Nothing here decides connectivity: make.sh exports KiCad's own netlist of the result and compares it.

usage: draw.py <build dir> <out dir> <project name>
"""
import json, os, sys, uuid, math
import symlib
from sx import find, first, get, val

NS = uuid.UUID("6f1c2b1e-58a5-4c6e-9a59-0d5a1f2b7c11")
G = 1.27
CH = 1.27           # mm per character of 1.27 mm text (KiCad stroke font, measured)
VERSION = "20260306"
P2 = 2.54


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

def rot(x, y, a):
    """Symbol coordinates (y up) rotated a degrees, returned as a screen offset (y down)."""
    a = a % 360
    if a == 0: xr, yr = x, y
    elif a == 90: xr, yr = -y, x
    elif a == 180: xr, yr = -x, -y
    else: xr, yr = y, -x
    return xr, -yr

def xform(x, y, angle, mirror):
    sx, sy = rot(x, y, angle)
    return (-sx if mirror else sx), sy

OUTWARD = {0: (-1, 0), 180: (1, 0), 90: (0, -1), 270: (0, 1)}      # pin angle -> outward direction, symbol coords

_geo = {}
def geo(lib, name, unit):
    """Body box (symbol coordinates, y up) and the pins of one unit."""
    key = (lib, name, unit)
    if key not in _geo:
        s = symlib.flat(lib, name)
        xs, ys = [], []
        for u in find(s, "symbol"):
            uu, st = (int(v) for v in val(u[1]).rsplit("_", 2)[-2:])
            if uu not in (0, unit) or st > 1: continue
            for c in u[1:]:
                if not isinstance(c, list): continue
                if c[0] == "rectangle":
                    for k in ("start", "end"):
                        a = first(c, k); xs.append(float(a[1])); ys.append(float(a[2]))
                elif c[0] in ("polyline", "bezier"):
                    for p in find(first(c, "pts"), "xy"): xs.append(float(p[1])); ys.append(float(p[2]))
                elif c[0] == "circle":
                    ce = first(c, "center"); r = float(get(c, "radius"))
                    xs += [float(ce[1]) - r, float(ce[1]) + r]; ys += [float(ce[2]) - r, float(ce[2]) + r]
                elif c[0] == "arc":
                    for k in ("start", "mid", "end"):
                        a = first(c, k); xs.append(float(a[1])); ys.append(float(a[2]))
        pins = [p for p in symlib.pins(lib, name) if p["unit"] in (0, unit)]
        if not xs:
            xs = [p["x"] for p in pins] or [0]; ys = [p["y"] for p in pins] or [0]
        _geo[key] = ((min(xs), min(ys), max(xs), max(ys)), pins)
    return _geo[key]

def tbox(s, x, y, just, size=1.27):
    w = len(s) * CH * size / 1.27; h = size * 0.55
    if just == "left": return (x, y - h, x + w, y + h)
    if just == "right": return (x - w, y - h, x, y + h)
    return (x - w / 2, y - h, x + w / 2, y + h)

def overlap(a, b, m=0.0):
    return a[0] < b[2] - m and b[0] < a[2] - m and a[1] < b[3] - m and b[1] < a[3] - m


# ------------------------------------------------------------------------------------------------ the drawing

class Doc:
    """Drawing objects in mm, y down. Built at any origin and moved as a whole when sections are packed."""
    def __init__(self, ctx):
        self.ctx = ctx
        self.syms, self.wires, self.labels, self.texts, self.ncs = [], [], [], [], []

    # -- symbols
    def place(self, ref, x, y, angle=0, mirror=False, unit=1, tx="right", lib=None, value=None, net=None, power=None):
        ctx = self.ctx
        if lib is None:
            lib = ctx.comps[ref]["lib"]
        ln, nm = lib.split(":")
        x, y = snap(x), snap(y)
        (bx0, by0, bx1, by1), pins = geo("power" if ln == "power_local" else ln, nm, unit)
        cs = [xform(px, py, angle, mirror) for px, py in ((bx0, by0), (bx1, by1))]
        body = (x + min(c[0] for c in cs), y + min(c[1] for c in cs), x + max(c[0] for c in cs), y + max(c[1] for c in cs))
        S = dict(ref=ref, lib=lib, x=x, y=y, angle=angle, mirror=mirror, unit=unit, body=body, power=power, net=net,
                 value=value if value is not None else (ctx.comps[ref]["value"] if ref in ctx.comps else ""), fields=[], pins={})
        for p in pins:
            dx, dy = xform(p["x"], p["y"], angle, mirror)
            ox, oy = OUTWARD[p["angle"]]
            ox, oy = xform(ox, oy, angle, mirror)
            pt = (snap(x + dx), snap(y + dy))
            n = None
            if ref in ctx.comps:
                n = ctx.pinnet.get((ref, p["num"]))
            elif power:
                n = net
            S["pins"].setdefault(p["num"], dict(pt=pt, d=(round(ox), round(oy)), name=p["name"], net=n, hidden=p["hidden"]))
        self.syms.append(S)
        self.fields(S, tx)
        return S

    def fields(self, S, tx):
        """Reference and value text. tx: right | left | above | below | ic | hide | ((rx, ry, just), (vx, vy, just))."""
        x0, y0, x1, y1 = S["body"]; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        ref, v = S["ref"], S["value"]
        S["fields"] = []
        if tx == "hide":
            S["fields"] = [("Reference", ref, cx, cy, "center", True), ("Value", v, cx, cy, "center", True)]; return
        if tx == "right":
            f = [(x1 + 1.27, cy - 1.27, "left"), (x1 + 1.27, cy + 1.27, "left")]
        elif tx == "left":
            f = [(x0 - 1.27, cy - 1.27, "right"), (x0 - 1.27, cy + 1.27, "right")]
        elif tx in ("above", "below"):
            tot = (len(ref) + 1 + len(v)) * CH
            sx = cx - tot / 2; yy = (y0 - 1.4) if tx == "above" else (y1 + 1.4)
            f = [(sx, yy, "left"), (sx + (len(ref) + 1) * CH, yy, "left")]
        elif tx == "ic":
            f = [(x0, y0 - 3.4, "left"), (x0, y0 - 1.6, "left")]
        else:
            f = list(tx)
        S["fields"] = [("Reference", ref, f[0][0], f[0][1], f[0][2], False), ("Value", v, f[1][0], f[1][1], f[1][2], False)]

    def vert(self, ref, x, y_top_pin, top_net, tx="right", up=False):
        """A two-pad part standing upright with the pad on top_net at (x, y_top_pin) (or at the bottom when up=True)."""
        ctx = self.ctx
        ln, nm = ctx.comps[ref]["lib"].split(":")
        _, pins = geo(ln, nm, 1)
        pp = {}
        for p in pins: pp.setdefault(p["num"], p)
        nums = sorted(pp)
        e = ctx.ends(ref)
        a_num = nums[0] if e[0] == top_net else nums[1]
        b_num = nums[1] if a_num == nums[0] else nums[0]
        for ang in (0, 90, 180, 270):
            ax, ay = rot(pp[a_num]["x"], pp[a_num]["y"], ang); bx, by = rot(pp[b_num]["x"], pp[b_num]["y"], ang)
            if abs(ax) < 0.01 and abs(bx) < 0.01 and ((ay < by) != up): break
        cy = y_top_pin - ay
        return self.place(ref, x, cy, ang, tx=tx)

    def horiz(self, ref, xpin, y, net, s=1, tx="above"):
        """A two-pad part lying flat on row y, its pad on net at xpin and its other pad further in direction s."""
        ctx = self.ctx
        ln, nm = ctx.comps[ref]["lib"].split(":")
        _, pins = geo(ln, nm, 1)
        pp = {}
        for p in pins: pp.setdefault(p["num"], p)
        nums = sorted(pp)
        e = ctx.ends(ref)
        a_num = nums[0] if e[0] == net else nums[1]
        b_num = nums[1] if a_num == nums[0] else nums[0]
        for ang in (0, 90, 180, 270):
            ax, ay = rot(pp[a_num]["x"], pp[a_num]["y"], ang); bx, by = rot(pp[b_num]["x"], pp[b_num]["y"], ang)
            if abs(ay) < 0.01 and abs(by) < 0.01 and (ax < bx) == (s > 0): break
        S = self.place(ref, xpin - ax, y, ang, tx=tx)
        if tx == "above":
            # two short parts in a row: the second one's text goes below rather than onto its neighbour's
            mine = [tbox(t_, x_, y_, j_) for _, t_, x_, y_, j_, h_ in S["fields"] if not h_ and t_]
            others = [b for b, k in self.text_boxes() if k[:2] != ("field", ref)]
            if any(overlap(a, b) for a in mine for b in others):
                self.fields(S, "below")
        return S

    def pin_of(self, S, key):
        """Pin by number or name."""
        if key in S["pins"]: return S["pins"][key]
        for p in S["pins"].values():
            if p["name"] == key: return p
        raise KeyError(f"{S['ref']} has no pin {key}")

    def other_pin(self, S, net):
        """Of a two-pad part: the pin point that is not on net."""
        for p in S["pins"].values():
            if p["net"] != net: return p["pt"]
        return list(S["pins"].values())[-1]["pt"]

    def net_pin(self, S, net):
        for p in S["pins"].values():
            if p["net"] == net: return p["pt"]
        raise KeyError(f"{S['ref']} not on {net}")

    # -- power symbols, labels, wires
    def power(self, net, x, y, d):
        """A power symbol on net at (x, y), pointing in direction d (U D L R) away from what it connects to."""
        ctx = self.ctx
        k = ctx.kind(net)
        name = ctx.short(net)
        if k == "gnd":
            lib, hidev = "power:GND", net == "GND"
            ang = {"D": 0, "U": 180, "R": 90, "L": 270}[d]
        elif k == "gref":
            lib, hidev = "power:GNDREF", False
            ang = {"D": 0, "U": 180, "R": 90, "L": 270}[d]
        else:
            lib, hidev = "power:VCC", False
            ang = {"U": 0, "D": 180, "L": 90, "R": 270}[d]
        if net not in ctx.glob and net != "GND":
            lib = "power_local:" + lib.split(":")[1]
        S = self.place("#PWR", x, y, ang, lib=lib, value=name, net=net, power=True, tx="hide")
        x, y = snap(x), snap(y)
        off = 3.6 if k == "sup" else 4.0
        vx, vy, j = {"U": (x, y - off, "center"), "D": (x, y + off, "center"),
                     "L": (x - off + 0.3, y, "right"), "R": (x + off - 0.3, y, "left")}[d]
        S["fields"] = [("Reference", "#PWR", x, y, "center", True), ("Value", name, vx, vy, j, hidev)]
        return S

    def label(self, net, x, y, d):
        """A net label at (x, y) whose text runs in direction d."""
        ctx = self.ctx
        x, y = snap(x), snap(y)
        self.labels.append(dict(net=net, text=ctx.short(net), x=x, y=y, d=d, glob=net in ctx.glob))

    def wire(self, net, *pts):
        pts = [(snap(a), snap(b)) for a, b in pts]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if (x1, y1) != (x2, y2):
                if x1 != x2 and y1 != y2:
                    raise ValueError(f"diagonal wire {pts}")
                self.wires.append(dict(net=net, a=(x1, y1), b=(x2, y2)))

    def nc(self, x, y):
        self.ncs.append((snap(x), snap(y)))

    def text(self, s, x, y, size=1.27, bold=False):
        self.texts.append(dict(s=s, x=snap(x), y=snap(y), size=size, bold=bold))

    # -- geometry
    def label_box(self, L):
        w = len(L["text"]) * CH + (2.6 if L["glob"] else 0.3)
        x, y, d = L["x"], L["y"], L["d"]
        if L["glob"]:
            if d == "R": return (x, y - 1.0, x + w, y + 1.0)
            if d == "L": return (x - w, y - 1.0, x, y + 1.0)
            if d == "U": return (x - 1.0, y - w, x + 1.0, y)
            return (x - 1.0, y, x + 1.0, y + w)
        if d == "R": return (x + 0.2, y - 1.6, x + w, y - 0.2)
        if d == "L": return (x - w, y - 1.6, x - 0.2, y - 0.2)
        if d == "U": return (x - 1.6, y - w, x - 0.2, y - 0.2)
        return (x - 1.6, y + 0.2, x - 0.2, y + w)

    def text_boxes(self):
        out = []
        for S in self.syms:
            for f, s, x, y, j, hid in S["fields"]:
                if not hid and s: out.append((tbox(s, x, y, j), ("field", S["ref"], f)))
        for L in self.labels: out.append((self.label_box(L), ("label", L["net"])))
        for T in self.texts:
            lines = T["s"].split("\n")
            w = max(len(l) for l in lines) * CH * T["size"] / 1.27
            h = len(lines) * T["size"] * 1.6
            out.append(((T["x"], T["y"] - T["size"] * 1.1, T["x"] + w, T["y"] - T["size"] * 1.1 + h), ("text", T["s"][:20])))
        return out

    def bbox(self):
        xs, ys = [], []
        for S in self.syms:
            b = S["body"]; xs += [b[0], b[2]]; ys += [b[1], b[3]]
            for p in S["pins"].values(): xs.append(p["pt"][0]); ys.append(p["pt"][1])
        for W in self.wires: xs += [W["a"][0], W["b"][0]]; ys += [W["a"][1], W["b"][1]]
        for b, _ in self.text_boxes(): xs += [b[0], b[2]]; ys += [b[1], b[3]]
        for x, y in self.ncs: xs.append(x); ys.append(y)
        if not xs: return (0, 0, 0, 0)
        return (min(xs), min(ys), max(xs), max(ys))

    def move(self, dx, dy):
        dx, dy = snap(dx), snap(dy)
        for S in self.syms:
            S["x"] += dx; S["y"] += dy
            b = S["body"]; S["body"] = (b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy)
            for p in S["pins"].values(): p["pt"] = (snap(p["pt"][0] + dx), snap(p["pt"][1] + dy))
            S["fields"] = [(f, s, x + dx, y + dy, j, h) for f, s, x, y, j, h in S["fields"]]
            S["x"], S["y"] = snap(S["x"]), snap(S["y"])
        for W in self.wires:
            W["a"] = (snap(W["a"][0] + dx), snap(W["a"][1] + dy)); W["b"] = (snap(W["b"][0] + dx), snap(W["b"][1] + dy))
        for L in self.labels: L["x"] = snap(L["x"] + dx); L["y"] = snap(L["y"] + dy)
        for T in self.texts: T["x"] = snap(T["x"] + dx); T["y"] = snap(T["y"] + dy)
        self.ncs = [(snap(x + dx), snap(y + dy)) for x, y in self.ncs]
        return self

    def add(self, other, dx=0, dy=0):
        other.move(dx, dy)
        self.syms += other.syms; self.wires += other.wires; self.labels += other.labels
        self.texts += other.texts; self.ncs += other.ncs
        return other


# ------------------------------------------------------------------------------------------------ block context

class Ctx:
    def __init__(self, block, comps, nets, nc, cons, order):
        self.block, self.comps, self.nets, self.cons = block, comps, nets, cons
        self.refs = [r for r in order if comps[r]["block"] == block]
        rs = set(self.refs)
        self.pinnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
        self.ncset = {(r, p) for r, p in nc}
        self.glob = {n for n, nodes in nets.items() if any(r not in rs for r, _ in nodes) and any(r in rs for r, _ in nodes)}
        self.pins_of = {r: symlib.pins(*comps[r]["lib"].split(":")) for r in self.refs}
        self.npads = {r: len({p["num"] for p in self.pins_of[r]}) for r in self.refs}
        self.anchors = [r for r in self.refs if self.npads[r] > 2]
        ncons = cons.get("nets", {})
        self.gref = {n for n, d in ncons.items() if d.get("draw") == "ground"}
        sup = set()
        for r in self.anchors:
            for p in self.pins_of[r]:
                n = self.pinnet.get((r, p["num"]))
                if n and p["type"] in ("power_in", "power_out") and not n.startswith("Net-(") \
                        and ncons.get(n, {}).get("kind") != "switching":
                    sup.add(n)
        for n, d in ncons.items():
            if d.get("kind") == "power" and n in self.glob: sup.add(n)
        self.supply = sup - {"GND"} - self.gref
        self.icnets = {}
        for r in self.anchors:
            for p in self.pins_of[r]:
                n = self.pinnet.get((r, p["num"]))
                if n: self.icnets.setdefault(n, set()).add(r)
        self.serves = cons.get("serves", {})
        self.claimed = set()
        shorts = {}
        for n in nets:
            if any(r in rs for r, _ in nets[n]):
                s = self.short(n)
                if s in shorts and shorts[s] != n: raise ValueError(f"two nets show as {s}: {n} {shorts[s]}")
                shorts[s] = n

    def short(self, n):
        if n.startswith("Net-("): return n[5:-1].replace("-Pad", "_").replace("-", "_")
        return n.lstrip("/") if n in self.glob else n.split("/")[-1]

    def kind(self, n):
        if n == "GND": return "gnd"
        if n in self.gref: return "gref"
        if n in self.supply: return "sup"
        return "sig"

    def ends(self, r):
        return [self.pinnet.get((r, n)) for n in sorted({p["num"] for p in self.pins_of[r]})]

    def private(self, n):
        return n not in self.icnets and n not in self.glob and self.kind(n) == "sig"

    def parts_on(self, n):
        """Small parts on net n that may hang from a drawn row (wire pads and connectors are drawn as a list instead)."""
        return [r for r in self.refs if self.npads[r] <= 2 and n in self.ends(r) and not self.is_pad(r)]

    def is_pad(self, r):
        return self.npads[r] == 1 and not r.startswith("TP")

    def section(self, r):
        return self.comps[r].get("section") or self.block


# ------------------------------------------------------------------------------------------------ trees of parts

class Node:
    """A net drawn as a horizontal row, with the parts that hang from it. parts: [(ref, other net, child Node|None)]."""
    def __init__(self, net, parts=None, end_label=False):
        self.net, self.parts, self.end_label = net, parts or [], end_label
        self.reserve = 0.0          # width kept free at the start of the row (a bridge part stands there)
        self.down = set()           # parts that must hang from the row, never continue it

def grow(ctx, net, root_parts, seen=None):
    """Tree from net: root_parts hang from it; private nets behind them are followed and take every part on them."""
    seen = (seen or set()) | {net}
    node = Node(net)
    for r in root_parts:
        if r in ctx.claimed: continue
        ctx.claimed.add(r)
        o = [n for n in ctx.ends(r) if n != net]
        o = o[0] if o else None
        child = None
        if o and o not in seen and ctx.private(o):
            child = grow(ctx, o, [x for x in ctx.parts_on(o) if x not in ctx.claimed], seen)
            covered = {(r, p["num"]) for p in ctx.pins_of[r]}
            for r2, _, _ in child.parts: covered |= {(r2, p["num"]) for p in ctx.pins_of[r2]}
            child.end_label = any(tuple(x) not in covered for x in ctx.nets[o])
        node.parts.append((r, o, child))
    return node

def twidth(ctx, r):
    return max(len(r), len(ctx.comps[r]["value"])) * CH

def draw_node(doc, node, x, y, s):
    """Draw node's row from (x, y) in direction s (+1 right, -1 left). Returns the x where the drawing ends."""
    ctx = doc.ctx
    ups, dns, cont = [], [], None
    for (r, o, child) in node.parts:
        k = ctx.kind(o) if o else None
        if ctx.npads[r] == 1: ups.append(("tp", r, None, None)); continue
        if child is not None: dns.append(("sig", r, o, child))
        elif k in ("gnd", "gref"): dns.append(("gnd", r, o, None))
        elif k == "sup": ups.append(("sup", r, o, None))
        else: dns.append(("sig", r, o, child))
    cands = [d for d in dns if d[3] is not None and d[1] not in node.down] + \
            [d for d in dns if d[3] is None and d[0] == "sig" and d[1] not in node.down]
    if cands:
        cont = cands[0]; dns.remove(cont)
        # a nested child must be drawn last: it spreads outward below the row
    dns.sort(key=lambda d: d[3] is not None)
    tx = "right" if s > 0 else "left"
    xc = x + s * (P2 + node.reserve)
    xend = x
    ncol = max(len(ups), len(dns))
    for i in range(ncol):
        w = 0
        if i < len(ups):
            kind, r, o, _ = ups[i]
            if kind == "tp":
                j = "left" if s > 0 else "right"
                xo = xc + s * 1.6
                S = doc.place(r, xc, y, 0, tx=((xo, y - 5.6, j), (xo, y - 3.9, j)))
            else:
                S = doc.vert(r, xc, y, node.net, tx=tx, up=True)
                top = doc.other_pin(S, node.net)
                doc.power(o, top[0], top[1], "U")
            w = max(w, twidth(ctx, r))
        if i < len(dns):
            kind, r, o, child = dns[i]
            S = doc.vert(r, xc, y, node.net, tx=tx)
            bot = doc.other_pin(S, node.net)
            w = max(w, twidth(ctx, r))
            if kind == "gnd":
                doc.power(o, bot[0], bot[1], "D")
            elif child is not None:
                stack_down(doc, child, bot[0], bot[1], s)
            else:
                doc.wire(o, bot, (bot[0], bot[1] + P2))
                doc.label(o, bot[0], bot[1] + P2, "R" if s > 0 else "L")
                w = max(w, len(ctx.short(o)) * CH + (2.6 if o in ctx.glob else 0))
        doc.wire(node.net, (xend, y), (xc, y))
        xend = xc
        xc = xc + s * (w + 2.0 + 1.27 + 2.54)
    xw = xend
    if node.end_label:
        xl = xw + s * P2 if ncol else x + s * P2
        if cont:
            doc.label(node.net, xl, y, "R" if s > 0 else "L")
            xw2 = snap(xl + s * (len(ctx.short(node.net)) * CH + (3.0 if node.net in ctx.glob else 0.5) + 1.27))
            doc.wire(node.net, (xw, y), (xw2, y))
            xw = xw2
        else:
            if ctx.kind(node.net) == "sup":
                doc.wire(node.net, (xw, y), (xl, y)); doc.power(node.net, xl, y, "U")
            else:
                doc.wire(node.net, (xw, y), (xl, y)); doc.label(node.net, xl, y, "R" if s > 0 else "L")
            return xl + s * len(ctx.short(node.net)) * CH
    if cont:
        _, r, o, child = cont
        xn = xw + s * P2 if (ncol or node.end_label) else x + s * (P2 + node.reserve)
        S = doc.horiz(r, xn, y, node.net, s)
        near, far = doc.net_pin(S, node.net), doc.other_pin(S, node.net)
        doc.wire(node.net, (xw, y), near)
        if child is not None:
            return draw_node(doc, child, far[0], far[1], s)
        k = ctx.kind(o)
        if k in ("gnd", "gref"):
            doc.wire(o, far, (far[0] + s * P2, far[1])); doc.power(o, far[0] + s * P2, far[1], "D")
            return far[0] + s * P2
        if k == "sup":
            doc.wire(o, far, (far[0] + s * P2, far[1])); doc.power(o, far[0] + s * P2, far[1], "U")
            return far[0] + s * P2
        doc.label(o, far[0], far[1], "R" if s > 0 else "L")
        return far[0] + s * len(ctx.short(o)) * CH
    return xend

def stack_down(doc, node, x, y, s):
    """A child node met at the bottom pin of a hanging part: one part continues straight down, more spread outward."""
    ctx = doc.ctx
    if len(node.parts) == 1 and node.parts[0][2] is None and not node.end_label:
        r, o, _ = node.parts[0]
        tx = "right" if s > 0 else "left"
        if ctx.npads[r] == 1:
            doc.wire(node.net, (x, y), (x, y + P2))
            doc.place(r, x, y + P2, 180, tx=tx); return
        S = doc.vert(r, x, y, node.net, tx=tx)
        bot = doc.other_pin(S, node.net)
        k = ctx.kind(o) if o else None
        if k in ("gnd", "gref"): doc.power(o, bot[0], bot[1], "D")
        elif k == "sup": doc.power(o, bot[0], bot[1], "D")
        elif o:
            doc.wire(o, bot, (bot[0], bot[1] + P2)); doc.label(o, bot[0], bot[1] + P2, "R" if s > 0 else "L")
        return
    draw_node(doc, node, x, y, s)

def measure_node(ctx, node, s):
    d = Doc(ctx)
    claimed = set(ctx.claimed)
    draw_node(d, node, 0, 0, s)
    ctx.claimed = claimed
    b = d.bbox()
    return b, d


# ------------------------------------------------------------------------------------------------ an IC and its pins

def pin_rows(S):
    """Visible pins of a placed symbol grouped by the side they leave on: {L,R,U,D: [(num, pin)]}, sorted."""
    sides = {"L": [], "R": [], "U": [], "D": []}
    seen = set()
    for num, p in sorted(S["pins"].items(), key=lambda kv: kv[1]["hidden"]):
        if p["pt"] in seen: continue
        seen.add(p["pt"])
        side = {(-1, 0): "L", (1, 0): "R", (0, -1): "U", (0, 1): "D"}[p["d"]]
        sides[side].append((num, p))
    for k in "LR": sides[k].sort(key=lambda e: e[1]["pt"][1])
    for k in "UD": sides[k].sort(key=lambda e: e[1]["pt"][0])
    return sides

def nets_at(ctx, ref, pt_pin):
    """All nets of the pads drawn at one pin point (stacked pads share a point)."""
    return pt_pin["net"]

def draw_ic(ctx, a, trees=None, bridges=None, unit=1, angle=0, mirror=False, ic_text=True, skip=()):
    """IC a with its trees wired to its side pins on lanes. trees: {pin number: Node}; bridges: [(ref, num_top, num_bottom)]
    for two-pad parts standing between two pin wires of the same side. Returns the Doc (IC at the origin)."""
    trees = trees or {}
    bridges = bridges or []
    doc = Doc(ctx)
    S = doc.place(a, 0, 0, angle, mirror, unit, tx="hide")
    sides = pin_rows(S)
    bx0, by0, bx1, by1 = S["body"]
    ncpin = lambda num: (a, num) in ctx.ncset
    for k in sides: sides[k] = [e for e in sides[k] if e[0] not in skip]
    for side in "LR":
        rows = sides[side]
        if not rows: continue
        s = -1 if side == "L" else 1
        px = rows[0][1]["pt"][0]
        brs = [b for b in bridges if any(num == b[1] for num, _ in rows)]
        tree_nums = [num for num, _ in rows if num in trees or any(num in (b[1], b[2]) for b in brs)]
        for num in tree_nums: trees.setdefault(num, Node(ctx.pinnet.get((a, num))))
        plain = [(num, p) for num, p in rows if num not in tree_nums]
        # plain pins: same-net neighbours are joined, then one label / symbol per group
        labw = 0.0
        groups, cur = [], []
        for num, p in rows:
            n = p["net"] if not ncpin(num) else None
            if num in tree_nums:
                if cur: groups.append(cur); cur = []
                continue
            if cur and n is not None and n == cur[-1][2] and abs(p["pt"][1] - cur[-1][1]["pt"][1]) <= P2 + 0.01:
                cur.append((num, p, n))
            else:
                if cur: groups.append(cur)
                cur = [(num, p, n)]
        if cur: groups.append(cur)
        trow = {p["pt"][1]: p["net"] for num, p in rows if num in tree_nums}
        for g in groups:
            num, p, n = g[0]
            x, y = p["pt"]
            if n is None:
                doc.nc(x, y); continue
            tj = [ty for ty, tn in trow.items() if tn == n and (abs(ty - g[0][1]["pt"][1]) <= P2 + 0.01 or abs(ty - g[-1][1]["pt"][1]) <= P2 + 0.01)]
            if tj:
                xj = snap(x + s * G)
                for _, p2, _ in g: doc.wire(n, p2["pt"], (xj, p2["pt"][1]))
                ys_ = [p2["pt"][1] for _, p2, _ in g] + [tj[0]]
                doc.wire(n, (xj, min(ys_)), (xj, max(ys_)))
                continue
            if len(g) > 1:
                xs_ = x + s * P2
                for _, p2, _ in g: doc.wire(n, p2["pt"], (xs_, p2["pt"][1]))
                doc.wire(n, (xs_, g[0][1]["pt"][1]), (xs_, g[-1][1]["pt"][1]))
                x = xs_
            k = ctx.kind(n)
            if k in ("gnd", "gref", "sup"):
                doc.power(n, x, y, side)
                labw = max(labw, abs(x - px) + (len(ctx.short(n)) * CH + 4 if k != "gnd" else 3))
            else:
                doc.label(n, x, y, side)
                labw = max(labw, abs(x - px) + len(ctx.short(n)) * CH + (2.6 if n in ctx.glob else 0.3))
        if not tree_nums: continue
        # lanes for the pins with parts
        tr = [(num, p) for num, p in rows if num in tree_nums]
        bmap = {b[1]: b for b in brs}
        bin_ = {b[2]: b for b in brs}
        nums = [num for num, _ in tr]
        n_ = len(tr)
        for num in nums:
            node = trees[num]
            if num in bmap or num in bin_:
                node.reserve = twidth(ctx, (bmap.get(num) or bin_.get(num))[0]) + 4.5
            node.end_label = node.end_label or needs_label(ctx, a, num, node, bridges)
        def geom(num):
            b = measure_node(ctx, trees[num], s)[0]
            ext = max(abs(b[0]), abs(b[2]), trees[num].reserve + P2)
            return dict(up=-b[1], dn=b[3], ind=trees[num].reserve, ext=ext)
        M = {num: geom(num) for num in nums}
        fixed = {num for num in nums if num in bmap or num in bin_}
        # staircase: a row whose parts rise (or hang) can start beyond the end of its neighbour, so the two rows sit close
        for k in range(1, n_):
            u, v = M[nums[k - 1]], M[nums[k]]
            if nums[k] not in fixed and v["up"] > 5 and u["dn"] < 1.7 and u["ext"] < 60:
                trees[nums[k]].reserve = max(trees[nums[k]].reserve, u["ext"] + 3.81)
                M[nums[k]] = geom(nums[k])
        for k in range(n_ - 2, -1, -1):
            u, v = M[nums[k]], M[nums[k + 1]]
            if nums[k] not in fixed and u["dn"] > 3 and v["up"] < 6.5 and v["ext"] < 60:
                trees[nums[k]].reserve = max(trees[nums[k]].reserve, v["ext"] + 3.81)
                M[nums[k]] = geom(nums[k])
        def sep(i, j):
            A, B = M[nums[i]], M[nums[j]]
            ov = lambda a0, a1, b0, b1: a0 < b1 + P2 and b0 < a1 + P2
            g = P2
            if ov(0, B["ext"], A["ind"], A["ext"]): g = max(g, A["dn"] + 1.27)
            if ov(0, A["ext"], B["ind"], B["ext"]): g = max(g, B["up"] + 1.27)
            if ov(A["ind"], A["ext"], B["ind"], B["ext"]): g = max(g, A["dn"] + B["up"] + 2.54)
            if j == i + 1 and nums[i] in bmap and bmap[nums[i]][2] == nums[j]: g = max(g, 12.7)
            return g
        pys = [p["pt"][1] for _, p in tr]
        ys = list(pys)
        for j in range(1, n_):
            ys[j] = max([ys[j]] + [ys[i] + sep(i, j) for i in range(j)])
        shift = sum(p - y for p, y in zip(pys, ys)) / n_
        ys = [snap(round((y + shift) / P2) * P2 + (pys[0] - round(pys[0] / P2) * P2)) for y in ys]
        for j in range(1, n_):
            need = max([ys[i] + sep(i, j) for i in range(j)])
            if ys[j] < need - 1e-6:
                ys[j] = ys[j] + math.ceil((need - ys[j]) / P2 - 1e-6) * P2
        if os.environ.get("DBG"):
            for k in range(n_): print(a, side, nums[k], pys[k], ys[k], {q_: round(v_, 1) for q_, v_ in M[nums[k]].items()})
        up = [k for k in range(n_) if ys[k] < pys[k] - 0.01]
        dn = [k for k in range(n_) if ys[k] > pys[k] + 0.01]
        col = {}
        for i, k in enumerate(up): col[k] = i + 1
        for i, k in enumerate(reversed(dn)): col[k] = i + 1
        base = max(labw + 1.27, P2)
        xs = snap(px + s * (base + P2 * (max([0] + list(col.values())))))
        for k, (num, p) in enumerate(tr):
            net = p["net"]; y = ys[k]; py = pys[k]
            if k in col:
                xj = snap(px + s * (base + P2 * (col[k] - 1)))
                doc.wire(net, (px, py), (xj, py), (xj, y), (xs, y))
            else:
                doc.wire(net, (px, py), (xs, y))
            draw_node(doc, trees[num], xs, y, s)
        for b in brs:
            r, n1, n2 = b
            k1 = [num for num, _ in tr].index(n1); k2 = [num for num, _ in tr].index(n2)
            y1, y2 = ys[k1], ys[k2]
            xb = snap(xs + s * P2)
            net1 = ctx.pinnet[(a, n1)]
            yc = snap((y1 + y2) / 2 - 3.81)
            yc = max(y1, yc)
            Sb = doc.vert(r, xb, yc, net1, tx="right" if s > 0 else "left")
            t = doc.net_pin(Sb, net1); bt = doc.other_pin(Sb, net1)
            doc.wire(net1, (xs, y1), (xb, y1), t); doc.wire(ctx.pinnet[(a, n2)], bt, (xb, y2), (xs, y2))
    # top and bottom pins
    for side in "UD":
        rows = sides[side]
        groups, cur = [], []
        for num, p in rows:
            n = p["net"] if not ncpin(num) else None
            if num in trees:
                if cur: groups.append(cur); cur = []
                groups.append([(num, p, n)]); continue
            if cur and n is not None and n == cur[-1][2] and cur[-1][0] not in trees:
                cur.append((num, p, n))
            else:
                if cur: groups.append(cur)
                cur = [(num, p, n)]
        if cur: groups.append(cur)
        sg = -1 if side == "U" else 1
        for g in groups:
            num, p, n = g[0]
            x, y = p["pt"]
            if n is None: doc.nc(x, y); continue
            if num in trees:
                node = trees[num]
                node.end_label = node.end_label or needs_label(ctx, a, num, node, bridges)
                b = doc.bbox()
                s = -1 if x <= (bx0 + bx1) / 2 else 1
                mb, _ = measure_node(ctx, node, s)
                ty = snap((b[1] - mb[3] - 2.54) if side == "U" else (b[3] - mb[1] + 2.54))
                doc.wire(n, (x, y), (x, ty))
                draw_node(doc, node, x, ty, s)
                continue
            if len(g) > 1:
                yy = y + sg * P2
                for _, p2, _ in g: doc.wire(n, p2["pt"], (p2["pt"][0], yy))
                doc.wire(n, (g[0][1]["pt"][0], yy), (g[-1][1]["pt"][0], yy))
                y = yy
            k = ctx.kind(n)
            if k in ("gnd", "gref", "sup"):
                doc.power(n, x, y, side)
            else:
                doc.label(n, x, y, side)
    if ic_text == "right":
        doc.fields(S, ((bx1 + 2.54, (by0 + by1) / 2 - 1.0, "left"), (bx1 + 2.54, (by0 + by1) / 2 + 1.0, "left")))
    elif ic_text:
        b = [o for o in doc.text_boxes()]
        top = by0
        for (x0, y0, x1, y1), _ in b:
            if x1 > bx0 - 1 and x0 < bx1 + 1 and y1 <= by0 + 0.01: top = min(top, y0)
        for W in doc.wires:
            for pt in (W["a"], W["b"]):
                if bx0 - 1 < pt[0] < bx1 + 1 and pt[1] < by0: top = min(top, pt[1])
        for S2 in doc.syms:
            if S2 is not S and S2["body"][2] > bx0 - 1 and S2["body"][0] < bx1 + 1 and S2["body"][3] <= by0 + 0.01:
                top = min(top, S2["body"][1])
        doc.fields(S, ((bx0, top - 3.6, "left"), (bx0, top - 1.8, "left")))
    return doc

def needs_label(ctx, a, num, node, bridges):
    """A pin's row ends in a label when its net reaches pins that the row does not draw."""
    net = ctx.pinnet.get((a, num))
    if net is None or ctx.kind(net) in ("gnd", "gref"): return False
    drawn = {(a, num)}
    def walk(nd):
        for r, o, ch in nd.parts:
            for p in ctx.pins_of[r]: drawn.add((r, p["num"]))
            if ch: walk(ch)
    walk(node)
    for b in bridges:
        if num in (b[1], b[2]):
            for p in ctx.pins_of[b[0]]: drawn.add((b[0], p["num"]))
    stacked = {(a, p["num"]) for p in ctx.pins_of[a] if ctx.pinnet.get((a, p["num"])) == net}
    rest = [tuple(x) for x in ctx.nets[net] if tuple(x) not in drawn and tuple(x) not in stacked]
    return bool(rest) or net in ctx.glob


# ------------------------------------------------------------------------------------------------ who hangs where

def pin_num(ctx, ref, key):
    ps = [p for p in ctx.pins_of[ref] if p["num"] == key] or [p for p in ctx.pins_of[ref] if p["name"] == key]
    if not ps: return None
    vis = [p for p in ps if not p["hidden"]]
    return (vis or ps)[0]["num"]

def side_lists(ctx, a):
    """Visible side pins of IC a (unrotated), per side, top to bottom: [[num, ...], [num, ...]]"""
    out = {0: [], 180: []}
    seen = set()
    for p in sorted(ctx.pins_of[a], key=lambda p: p["hidden"]):
        if p["angle"] not in out or (p["x"], p["y"], p["unit"]) in seen: continue
        seen.add((p["x"], p["y"], p["unit"]))
        out[p["angle"]].append(p)
    return [[p["num"] for p in sorted(v, key=lambda p: -p["y"])] for v in out.values()]

def find_bridges(ctx, a):
    """Two-pad parts between the wires of two neighbouring pins on one side of IC a."""
    out = []
    for lst in side_lists(ctx, a):
        nets = [ctx.pinnet.get((a, n)) for n in lst]
        for k in range(len(lst) - 1):
            n1, n2 = nets[k], nets[k + 1]
            if not n1 or not n2 or n1 == n2 or (a, lst[k]) in ctx.ncset or (a, lst[k + 1]) in ctx.ncset: continue
            if ctx.kind(n1) in ("gnd", "gref") or ctx.kind(n2) in ("gnd", "gref"): continue
            for r in ctx.refs:
                if r in ctx.claimed or ctx.npads[r] != 2: continue
                if set(ctx.ends(r)) == {n1, n2}:
                    sv = ctx.serves.get(r)
                    if sv and sv.split(".")[0] != a: continue
                    ctx.claimed.add(r); out.append((r, lst[k], lst[k + 1])); break
    return out

def plan(ctx, attachable, overrides):
    """Trees for the pins of the attachable ICs: {(ic, pin number): Node}."""
    roots = {}
    def add(a, num, r):
        roots.setdefault((a, num), []).append(r)
    for r in ctx.refs:
        if r in ctx.claimed or ctx.npads[r] > 2: continue
        sv = ctx.serves.get(r)
        if sv:
            x, pn = sv.split(".", 1)
            if x in attachable:
                num = pin_num(ctx, x, pn)
                if num and (x, num) not in ctx.ncset: add(x, num, r); ctx.claimed.add(r)
    for r in ctx.refs:
        if r in ctx.claimed or ctx.npads[r] > 2: continue
        if ctx.npads[r] == 1 and not r.startswith("TP"): continue
        best = None
        for n in ctx.ends(r):
            if not n or ctx.kind(n) in ("gnd", "gref"): continue
            if ctx.kind(n) == "sup" and len(ctx.icnets.get(n, ())) != 1: continue
            for a in attachable:
                for p in ctx.pins_of[a]:
                    if ctx.pinnet.get((a, p["num"])) == n and not p["hidden"]:
                        key = (ctx.kind(n) == "sup", ctx.section(a) != ctx.section(r), attachable.index(a))
                        if best is None or key < best[0]: best = (key, a, p["num"])
                        break
        if best:
            add(best[1], best[2], r); ctx.claimed.add(r)
    trees = {}
    for (a, num), rs in roots.items():
        for r in rs: ctx.claimed.discard(r)
        n = ctx.pinnet[(a, num)]
        if (a, num) in overrides:
            node = overrides[(a, num)]
            for r in rs: ctx.claimed.discard(r)
            extra = grow(ctx, n, rs)
            node.parts += extra.parts
        else:
            node = grow(ctx, n, rs)
        trees[(a, num)] = node
    for k, node in overrides.items():
        trees.setdefault(k, node)
    return trees

def leftovers(ctx, refs):
    """Unclaimed small parts as trees rooted on a supply, a shared signal or ground: [(root net, Node, section)]."""
    out = []
    pool = [r for r in refs if r not in ctx.claimed and ctx.npads[r] <= 2]
    for r in pool:
        if r in ctx.claimed: continue
        e = [n for n in ctx.ends(r) if n]
        if not e: continue
        rank = lambda n: (0 if ctx.kind(n) == "sup" else 1 if not ctx.private(n) and ctx.kind(n) == "sig" else 2 if ctx.kind(n) == "sig" else 3)
        root = min(e, key=rank)
        if ctx.npads[r] == 1:
            ctx.claimed.add(r); out.append((root, Node(root, [(r, None, None)]), ctx.section(r), "pad")); continue
        sib = [x for x in pool if x not in ctx.claimed and root in ctx.ends(x) and ctx.npads[x] == 2
               and ctx.section(x) == ctx.section(r)]
        node = grow(ctx, root, sib)
        out.append((root, node, ctx.section(r), "row"))
    return out

def draw_leftover(ctx, item):
    root, node, sec, kind = item
    d = Doc(ctx)
    if kind == "pad":
        r = node.parts[0][0]
        lib = ctx.comps[r]["lib"]
        ang = 90 if lib == "Connector:TestPoint" else 180
        S = d.place(r, 0, 0, ang, tx="left")
        pt = list(S["pins"].values())[0]["pt"]
        k = ctx.kind(root)
        if k == "sig":
            d.wire(root, pt, (pt[0] + P2, pt[1])); d.label(root, pt[0] + P2, pt[1], "R")
        elif k == "sup":
            d.wire(root, pt, (pt[0] + P2, pt[1])); d.power(root, pt[0] + P2, pt[1], "U")
        else:
            d.wire(root, pt, (pt[0] + P2, pt[1])); d.power(root, pt[0] + P2, pt[1], "D")
        return d
    k = ctx.kind(root)
    if k == "sup":
        d.power(root, 0, 0, "U")
    elif k in ("gnd", "gref"):
        d.power(root, 0, 0, "D")
    else:
        d.label(root, 0, 0, "L")
    draw_node(d, node, 0, 0, 1)
    return d


# ------------------------------------------------------------------------------------------------ wires instead of labels

def seg_hits_box(a, b, box, m=0.25):
    x0, y0, x1, y1 = box
    if a[1] == b[1]:
        y = a[1]; lo, hi = sorted((a[0], b[0]))
        return y0 + m < y < y1 - m and lo < x1 - m and hi > x0 + m
    x = a[0]; lo, hi = sorted((a[1], b[1]))
    return x0 + m < x < x1 - m and lo < y1 - m and hi > y0 + m

def on_seg(pt, a, b, interior=False):
    if a[1] == b[1] == pt[1]:
        lo, hi = sorted((a[0], b[0]))
        return (lo < pt[0] < hi) if interior else (lo - 1e-6 <= pt[0] <= hi + 1e-6)
    if a[0] == b[0] == pt[0]:
        lo, hi = sorted((a[1], b[1]))
        return (lo < pt[1] < hi) if interior else (lo - 1e-6 <= pt[1] <= hi + 1e-6)
    return False

def collinear_overlap(a, b, c, d):
    if a[1] == b[1] == c[1] == d[1]:
        l1, h1 = sorted((a[0], b[0])); l2, h2 = sorted((c[0], d[0]))
        return min(h1, h2) - max(l1, l2) > 1e-6
    if a[0] == b[0] == c[0] == d[0]:
        l1, h1 = sorted((a[1], b[1])); l2, h2 = sorted((c[1], d[1]))
        return min(h1, h2) - max(l1, l2) > 1e-6
    return False

def crosses(a, b, c, d):
    if (a[1] == b[1]) == (c[1] == d[1]): return False
    if a[1] != b[1]: a, b, c, d = c, d, a, b
    y = a[1]; x = c[0]
    return min(a[0], b[0]) < x < max(a[0], b[0]) and min(c[1], d[1]) < y < max(c[1], d[1])

class Obstacles:
    def __init__(self, doc, skip_labels=()):
        self.bodies = [S["body"] for S in doc.syms if not S["power"]]
        self.pwr = [S for S in doc.syms if S["power"]]
        self.texts = [b for b, k in doc.text_boxes() if not (k[0] == "label" and id_in(k, skip_labels))]
        self.segs = [(W["a"], W["b"], W["net"]) for W in doc.wires]
        self.pts = []
        for S in doc.syms:
            for p in S["pins"].values():
                self.pts.append((p["pt"], p["net"]))
                if not S["power"]:
                    # the pin line, from its end toward the body
                    d = p["d"]; L = 2.54
                    self.segs.append((p["pt"], (snap(p["pt"][0] - d[0] * L), snap(p["pt"][1] - d[1] * L)), p["net"]))
            if S["power"]:
                b = S["body"]; self.bodies.append(b)
        for W in doc.wires:
            self.pts.append((W["a"], W["net"])); self.pts.append((W["b"], W["net"]))
        for L in doc.labels: self.pts.append(((L["x"], L["y"]), L["net"]))
        for x, y in doc.ncs: self.pts.append(((x, y), None))

def id_in(k, skip):
    return any(k[1] == s for s in skip)

def route_cost(ob, net, pts, ends):
    cost, cr = 0.0, 0
    for a, b in zip(pts, pts[1:]):
        if a == b: continue
        cost += abs(a[0] - b[0]) + abs(a[1] - b[1])
        for bx in ob.bodies:
            if seg_hits_box(a, b, bx, 0.1): return None
        for bx in ob.texts:
            if seg_hits_box(a, b, bx, 0.0): return None
        for c, d, n in ob.segs:
            if n == net: continue
            if collinear_overlap(a, b, c, d): return None
            if crosses(a, b, c, d): cr += 1
            if on_seg(c, a, b) or on_seg(d, a, b): return None
            if on_seg(a, c, d) or on_seg(b, c, d): return None
        for pt, n in ob.pts:
            if n != net and on_seg(pt, a, b): return None
    if cr > 1: return None          # a label reads better than a wire that weaves through others
    return cost + 5.0 * (len(pts) - 2) + 12.0 * cr

def find_route(doc, net, p, q, ob, lmax):
    (x1, y1), (x2, y2) = p, q
    if abs(x1 - x2) + abs(y1 - y2) > lmax: return None
    cands = []
    if x1 == x2 or y1 == y2: cands.append([p, q])
    cands += [[p, (x2, y1), q], [p, (x1, y2), q]]
    offs = [k * P2 for k in range(-8, 9)]
    for xm in sorted({x1 + o for o in offs} | {x2 + o for o in offs}):
        cands.append([p, (xm, y1), (xm, y2), q])
    for ym in sorted({y1 + o for o in offs} | {y2 + o for o in offs}):
        cands.append([p, (x1, ym), (x2, ym), q])
    best = None
    for c in cands:
        c = [(snap(a), snap(b)) for a, b in c]
        c2 = [c[0]]
        for pt in c[1:]:
            if pt != c2[-1]: c2.append(pt)
        if len(c2) < 2: continue
        cost = route_cost(ob, net, c2, (p, q))
        if cost is not None and (best is None or cost < best[0]): best = (cost, c2)
    if best and sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(best[1], best[1][1:])) <= lmax:
        return best[1]
    return None

def connect_labels(doc, lmax=60.0):
    """Label pairs of one net that sit close together become a wire when a clean route exists."""
    ctx = doc.ctx
    bynet = {}
    for i, L in enumerate(doc.labels): bynet.setdefault(L["net"], []).append(i)
    remove = set()
    for net, idx in bynet.items():
        if len(idx) < 2: continue
        parent = {i: i for i in idx}
        def f(i):
            while parent[i] != i: i = parent[i]
            return i
        pairs = sorted(((abs(doc.labels[i]["x"] - doc.labels[j]["x"]) + abs(doc.labels[i]["y"] - doc.labels[j]["y"]), i, j)
                        for ii, i in enumerate(idx) for j in idx[ii + 1:]))
        for dist, i, j in pairs:
            if dist > lmax or f(i) == f(j): continue
            Li, Lj = doc.labels[i], doc.labels[j]
            saved = doc.labels
            doc.labels = [L for k, L in enumerate(saved) if k not in (i, j) and k not in remove]
            ob = Obstacles(doc)
            doc.labels = saved
            r = find_route(doc, net, (Li["x"], Li["y"]), (Lj["x"], Lj["y"]), ob, lmax)
            if r:
                doc.wire(net, *r); parent[f(i)] = f(j)
        comps = {}
        for i in idx: comps.setdefault(f(i), []).append(i)
        for c in comps.values():
            if len(c) == 1: continue
            if len(c) == len(idx) and net not in ctx.glob:
                remove.update(c); continue
            # keep one label: the one whose text is clear of the new wires
            keep = None
            for i in c:
                b = doc.label_box(doc.labels[i])
                if not any(seg_hits_box(W["a"], W["b"], b, 0.0) for W in doc.wires): keep = i; break
            keep = c[0] if keep is None else keep
            remove.update(x for x in c if x != keep)
    doc.labels = [L for k, L in enumerate(doc.labels) if k not in remove]


# ------------------------------------------------------------------------------------------------ checks

def lint(doc, name):
    """Overlaps a reader would notice: text on text, text on a symbol, wire through text or a symbol body."""
    issues = []
    tb = doc.text_boxes()
    for i in range(len(tb)):
        for j in range(i + 1, len(tb)):
            if overlap(tb[i][0], tb[j][0], 0.05): issues.append(f"text overlap {tb[i][1]} / {tb[j][1]}")
    for b, k in tb:
        for S in doc.syms:
            if S["power"]: continue
            if overlap(b, S["body"], 0.2) and not (k[0] == "field" and k[1] == S["ref"] and False):
                issues.append(f"text on symbol {k} / {S['ref']}")
        for W in doc.wires:
            if seg_hits_box(W["a"], W["b"], b, 0.1): issues.append(f"wire through text {k} {W['net']}"); break
    for W in doc.wires:
        for S in doc.syms:
            if S["power"]: continue
            if seg_hits_box(W["a"], W["b"], S["body"], 0.3): issues.append(f"wire through {S['ref']} ({W['net']})")
    # connection points of two different nets touching
    pts = []
    for S in doc.syms:
        for p in S["pins"].values(): pts.append((p["pt"], p["net"], S["ref"]))
    for L in doc.labels: pts.append(((L["x"], L["y"]), L["net"], "label"))
    for W in doc.wires: pts += [(W["a"], W["net"], "wire"), (W["b"], W["net"], "wire")]
    for pt, n, who in pts:
        for W in doc.wires:
            if W["net"] != n and n is not None and W["net"] is not None and on_seg(pt, W["a"], W["b"]):
                issues.append(f"SHORT {who} {n} touches wire of {W['net']} at {pt}")
    by = {}
    for pt, n, who in pts:
        if n is None: continue
        by.setdefault(pt, set()).add(n)
    for pt, ns in by.items():
        if len(ns) > 1: issues.append(f"SHORT at {pt}: {sorted(ns)}")
    for i, A in enumerate(doc.wires):
        for B in doc.wires[i + 1:]:
            if A["net"] != B["net"] and collinear_overlap(A["a"], A["b"], B["a"], B["b"]):
                issues.append(f"SHORT overlapping wires {A['net']} {B['net']}")
    return issues


# ------------------------------------------------------------------------------------------------ templates

def other_net(ctx, r, n):
    o = [x for x in ctx.ends(r) if x != n]
    return o[0] if o else None

class Template:
    drawn = ()          # ICs this template draws itself
    section = None
    def __init__(self, ctx, a, t):
        self.ctx, self.a, self.t = ctx, a, t
        self.overrides, self.bridges = {}, {}
    def claim(self): pass
    def draw(self, trees, bridges): return None

class Buck(Template):
    """Buck converter: input caps on the VIN wire, inductor in line with SW, output caps and the feedback divider on
    the output, boot cap between BST and SW. The IC itself is drawn by draw_ic with these rows."""
    def claim(self):
        ctx, a, t = self.ctx, self.a, self.t
        P = lambda nm: pin_num(ctx, a, nm)
        own = lambda r: r in ctx.comps and ctx.comps[r]["block"] == ctx.block and r not in ctx.claimed and \
            (not ctx.serves.get(r) or ctx.serves[r].split(".")[0] in (a, t["inductor"]))
        vin, sw = P(t["vin"]), P(t["sw"])
        nvin, nsw = ctx.pinnet[(a, vin)], ctx.pinnet[(a, sw)]
        L = t["inductor"]; nout = other_net(ctx, L, nsw)
        cin = [r for r in t.get("cin", []) if own(r)]
        cout = [r for r in t.get("cout", []) if own(r)]
        ctx.claimed.update(cin + cout + [L])
        self.overrides[(a, vin)] = Node(nvin, [(r, other_net(ctx, r, nvin), None) for r in cin])
        out = Node(nout, [(r, other_net(ctx, r, nout), None) for r in cout], end_label=True)
        if t.get("fb") and t.get("div"):
            top, bot = t["div"]; nfb = ctx.pinnet[(a, P(t["fb"]))]
            ctx.claimed.update([top, bot])
            child = Node(nfb, [(bot, other_net(ctx, bot, nfb), None)], end_label=True)
            out.parts.append((top, nfb, child)); out.down.add(top)
        self.overrides[(a, sw)] = Node(nsw, [(L, nout, out)])
        if t.get("boot") and t.get("bst"):
            b = P(t["bst"])
            ys = {p["num"]: p["y"] for p in ctx.pins_of[a]}
            pair = (b, sw) if ys[b] > ys[sw] else (sw, b)
            ctx.claimed.add(t["boot"])
            self.bridges[a] = [(t["boot"],) + pair]

def kelvin_parts(ctx, shunt, cons_k):
    """The filter parts of a Kelvin pair: [(shunt-end net, filter net, resistor)], the differential cap, {net: cap to GND}."""
    if not cons_k: return None
    pos, neg = cons_k["pos"], cons_k["neg"]
    find = lambda a, b: next((r for r in ctx.refs if ctx.npads[r] == 2 and set(ctx.ends(r)) == {a, b}), None)
    sides = []
    for n in ctx.ends(shunt):
        for fnet in (pos, neg):
            r = find(n, fnet)
            if r: sides.append((n, fnet, r))
    if len(sides) != 2: return None
    used = {r for _, _, r in sides}
    cg = {f: next((r for r in ctx.refs if ctx.npads[r] == 2 and set(ctx.ends(r)) == {f, "GND"} and r not in used), None)
          for f in (pos, neg)}
    return sides, find(pos, neg), {k: v for k, v in cg.items() if v}

def claim_kelvin(ctx, shunt):
    k = {k_["resistor"]: k_ for k_ in ctx.cons.get("kelvin", {}).values()}.get(shunt)
    kp = kelvin_parts(ctx, shunt, k)
    if kp:
        ctx.claimed.update([r for _, _, r in kp[0]] + ([kp[1]] if kp[1] else []) + list(kp[2].values()))

def kelvin_filter(doc, shunt, y, cons_k):
    """RC filter of a Kelvin sense pair drawn above a shunt lying on row y: a resistor up from each end of the shunt,
    the differential cap across their tops, the common-mode caps to ground outside, and the labels to the controller."""
    ctx = doc.ctx
    kp = kelvin_parts(ctx, shunt, cons_k)
    if not kp: return
    sides, cdiff, cgs = kp
    pts = {p["net"]: p["pt"] for S in doc.syms if S["ref"] == shunt for p in S["pins"].values()}
    sides.sort(key=lambda s_: pts[s_[0]][0])
    ytop = snap(y - 12.7)
    xs = []
    for i, (n, fnet, r) in enumerate(sides):
        ctx.claimed.add(r)
        x = pts[n][0]
        S = doc.vert(r, x, ytop, fnet, tx="left" if i == 0 else "right")
        bot = doc.other_pin(S, fnet)
        doc.wire(n, bot, (x, y))
        xs.append(x)
    if cdiff:
        ctx.claimed.add(cdiff)
        doc.horiz(cdiff, xs[0], ytop, sides[0][1], 1)
    for i, (n, fnet, r) in enumerate(sides):
        s = -1 if i == 0 else 1
        x = xs[i]
        xc = snap(x + s * (twidth(ctx, r) + 5.08))
        cg = cgs.get(fnet)
        xe = xc
        if cg:
            ctx.claimed.add(cg)
            doc.vert(cg, xc, ytop, fnet, tx="left" if s < 0 else "right")
            doc.power("GND", xc, ytop + 7.62, "D")
            xe = snap(xc + s * (twidth(ctx, cg) + 4.5))
        doc.wire(fnet, (x, ytop), (xe, ytop))
        doc.label(fnet, xe, ytop, "L" if s < 0 else "R")

class Bridge4(Template):
    """Four-switch buck-boost power stage as a power path, left to right: input shunt with its sense filter, input caps,
    input half bridge, inductor, output half bridge, output caps, output shunt with its sense filter."""
    def claim(self):
        ctx, t = self.ctx, self.t
        self.drawn = (self.a, t["q_out"])
        ctx.claimed.update([t["inductor"], t["rin"], t["rout"]] + t["cin"] + t["cout"])
        claim_kelvin(ctx, t["rin"]); claim_kelvin(ctx, t["rout"])
        self.section = ctx.section(self.a)

    def draw(self, trees, bridges):
        ctx, t = self.ctx, self.t
        d = Doc(ctx)
        qa, qb = self.a, t["q_out"]
        net = lambda q, nm, u: next(ctx.pinnet[(q, p["num"])] for p in ctx.pins_of[q] if p["name"] == nm and p["unit"] == u)
        n_in, n_out = net(qa, "D1", 1), net(qb, "D1", 1)
        n_sw1, n_sw2 = net(qa, "SW", 1), net(qb, "SW", 1)
        kel = {k["resistor"]: k for k in ctx.cons.get("kelvin", {}).values()}
        yr = 0.0
        # input: supply symbol, shunt, filter above it
        n_src = other_net(ctx, t["rin"], n_in)
        x = 0.0
        d.power(n_src, x, yr, "U") if ctx.kind(n_src) == "sup" else d.label(n_src, x, yr, "L")
        Sr = d.horiz(t["rin"], x + 17.78, yr, n_src, 1, tx="below")
        d.wire(n_src, (x, yr), d.net_pin(Sr, n_src))
        kelvin_filter(d, t["rin"], yr, kel.get(t["rin"]))
        xr = d.net_pin(Sr, n_in)[0]
        xx = snap(xr + 17.78)
        cols = []
        for r in t["cin"]:
            S = d.vert(r, xx, yr, n_in); d.power(other_net(ctx, r, n_in), xx, yr + 7.62, "D")
            cols.append(xx); xx = snap(xx + twidth(ctx, r) + 6.35)
        # input half bridge (two units stacked), drains up to the rail, sources down to ground
        qx = snap(xx + 7.62)
        ya, yb = snap(yr + 11.43), snap(yr + 21.59)
        A = d.place(qa, qx, ya, 0, unit=1, tx="hide")
        B = d.place(qa, qx, yb, 0, unit=2, tx=((qx - 6.35, yb + 5.6, "left"), (qx - 6.35, yb + 7.4, "left")))
        pa = lambda S_, nm: d.pin_of(S_, nm)["pt"]
        xd = snap(pa(A, "D1")[0] + 2.54); xs = snap(pa(A, "D1")[0] + 5.08)
        d.wire(n_in, (d.net_pin(Sr, n_in)), (xd, yr), (xd, pa(A, "D1")[1]), pa(A, "D1"))
        d.wire(n_sw1, pa(A, "SW"), (xs, pa(A, "SW")[1]), (xs, pa(B, "SW")[1]), pa(B, "SW"))
        gS2 = pa(B, "S2")
        d.wire("GND", gS2, (xd, gS2[1]), (xd, gS2[1] + 2.54)); d.power("GND", xd, gS2[1] + 2.54, "D")
        for S_, g, u in ((A, "G1", 1), (B, "G2", 2)):
            gp = pa(S_, g); d.label(net(qa, g, u), gp[0], gp[1], "L")
        ysw = pa(A, "SW")[1]
        il = snap(xs + 12.7)
        Li = d.horiz(t["inductor"], il, ysw, n_sw1, 1)
        d.wire(n_sw1, (xs, ysw), (il, ysw))
        d.label(n_sw1, snap(xs + 2.54), ysw, "R")
        xr2 = d.net_pin(Li, n_sw2)[0]
        xs2 = snap(xr2 + 12.7)
        d.wire(n_sw2, (xr2, ysw), (xs2, ysw))
        d.label(n_sw2, snap(xs2 - 2.54 - len(ctx.short(n_sw2)) * CH), ysw, "R")
        qx2 = snap(xs2 + 5.08 + 6.35)
        A2 = d.place(qb, qx2, ya, 0, mirror=True, unit=1, tx="hide")
        B2 = d.place(qb, qx2, yb, 0, mirror=True, unit=2, tx=((qx2 + 6.35, yb + 5.6, "right"), (qx2 + 6.35, yb + 7.4, "right")))
        xd2 = snap(pa(A2, "D1")[0] - 2.54)
        d.wire(n_sw2, pa(A2, "SW"), (xs2, pa(A2, "SW")[1]), (xs2, pa(B2, "SW")[1]), pa(B2, "SW"))
        gS2b = pa(B2, "S2")
        d.wire("GND", gS2b, (xd2, gS2b[1]), (xd2, gS2b[1] + 2.54)); d.power("GND", xd2, gS2b[1] + 2.54, "D")
        for S_, g, u in ((A2, "G1", 1), (B2, "G2", 2)):
            gp = pa(S_, g); d.label(net(qb, g, u), gp[0], gp[1], "R")
        # output rail: drain up, caps, shunt, filter, destination
        lab_room = max(len(ctx.short(net(qb, g, u))) for g, u in (("G1", 1), ("G2", 2))) * CH + 5.08
        xx = snap(pa(A2, "G1")[0] + lab_room + 5.08)
        d.wire(n_out, pa(A2, "D1"), (xd2, pa(A2, "D1")[1]), (xd2, yr))
        x0 = xd2
        for r in t["cout"]:
            d.vert(r, xx, yr, n_out); d.power(other_net(ctx, r, n_out), xx, yr + 7.62, "D")
            xx = snap(xx + twidth(ctx, r) + 6.35)
        n_dst = other_net(ctx, t["rout"], n_out)
        Sro = d.horiz(t["rout"], snap(xx + 7.62), yr, n_out, 1, tx="below")
        d.wire(n_out, (x0, yr), d.net_pin(Sro, n_out))
        kelvin_filter(d, t["rout"], yr, kel.get(t["rout"]))
        xe = snap(d.net_pin(Sro, n_dst)[0] + 12.7)
        d.wire(n_dst, d.net_pin(Sro, n_dst), (xe, yr))
        d.power(n_dst, xe, yr, "U") if ctx.kind(n_dst) == "sup" else d.label(n_dst, xe, yr, "R")
        return d

class PackPath(Template):
    """Battery pack power path: cell-stack wire, fuse, back-to-back charge and discharge FETs with their gate networks,
    the pack output; and below it the return path with the current-sense shunt and its Kelvin filter."""
    def claim(self):
        ctx, t = self.ctx, self.t
        self.drawn = (t["fuse"], t["q_chg"], t["q_dsg"])
        ctx.claimed.update([t["wire_in"], t["wire_out"], t["ret_in"], t["ret_out"], t["shunt"], t["fuse"]])
        claim_kelvin(ctx, t["shunt"])
        self.section = t.get("title") or ctx.section(t["q_chg"])
        self.gate_parts = {}
        for q in (t["q_chg"], t["q_dsg"]):
            g = pin_num(ctx, q, "G")
            n_g = ctx.pinnet[(q, g)]
            self.gate_parts[q] = [r for r in ctx.parts_on(n_g) if r not in ctx.claimed]
            ctx.claimed.update(self.gate_parts[q])
        # series ESD caps across the FET pair
        n_cp, n_out = ctx.pinnet[(t["q_chg"], pin_num(ctx, t["q_chg"], "S"))], ctx.pinnet[(t["q_dsg"], pin_num(ctx, t["q_dsg"], "S"))]
        self.esd = None
        for r in ctx.parts_on(n_cp):
            mid = other_net(ctx, r, n_cp)
            if r in ctx.claimed or not mid or not ctx.private(mid): continue
            r2 = next((x for x in ctx.parts_on(mid) if x != r and other_net(ctx, x, mid) == n_out), None)
            if r2: self.esd = (r, mid, r2); ctx.claimed.update([r, r2]); break

    def draw(self, trees, bridges):
        ctx, t = self.ctx, self.t
        d = Doc(ctx)
        P = lambda S_, nm: d.pin_of(S_, nm)["pt"]
        y = 0.0
        # cell-stack wire and fuse
        Jin = d.place(t["wire_in"], 0, y, 90, tx=((-4.5, y - 4.4, "left"), (-4.5, y - 2.6, "left")))
        pin_in = list(Jin["pins"].values())[0]["pt"]
        n_raw = ctx.pinnet[(t["wire_in"], "1")]
        F = d.place(t["fuse"], snap(pin_in[0] + max(15.24, len(ctx.comps[t["wire_in"]]["value"]) * CH + 2.54) + 6.35), y, 0, tx="above")
        d.wire(n_raw, pin_in, P(F, "1"))
        n_cp = ctx.pinnet[(t["fuse"], "2")]
        qc, qd = t["q_chg"], t["q_dsg"]
        # the FETs lie under the path with drain and source up to it and the gate down (back to back: sources outside)
        x_q1 = snap(P(F, "2")[0] + 40.64)
        Q1 = d.place(qc, x_q1, y + 7.62, 90, mirror=True, tx="hide")
        x_q2 = snap(x_q1 + 48.26)
        Q2 = d.place(qd, x_q2, y + 7.62, 90, mirror=False, tx="hide")
        s1, d1 = P(Q1, "S"), P(Q1, "D"); d2, s2 = P(Q2, "D"), P(Q2, "S")
        n_mid = ctx.pinnet[(qc, pin_num(ctx, qc, "D"))]; n_out = ctx.pinnet[(qd, pin_num(ctx, qd, "S"))]
        d.wire(n_cp, P(F, "2"), (s1[0], y), s1)
        d.wire(n_mid, d1, (d1[0], y), (d2[0], y), d2)
        x_end = snap(s2[0] + 55.88)
        d.wire(n_out, s2, (s2[0], y), (x_end, y))
        for S_, ref, side in ((Q1, qc, 1), (Q2, qd, -1)):
            b = S_["body"]
            nm = ctx.comps[ref]["fields"].get("Notes", "")
            xt = b[2] + 1.27 if side > 0 else b[0] - 1.27
            j = "left" if side > 0 else "right"
            d.fields(S_, ((xt, b[1] + 2.0, j), (xt, b[1] + 3.8, j)))
            if nm: d.text(nm + " FET", xt if side > 0 else xt - (len(nm) + 4) * CH, b[1] + 6.4, 1.27)
        d.label(n_mid, snap((d1[0] + d2[0]) / 2 - len(ctx.short(n_mid)) * CH / 2), y, "R")
        # gate networks: gate-source resistor (and clamp) beside the FET up to the source wire, drive resistor down
        def gate(S_, ref, src_net, s):
            g = P(S_, "G")
            n_g = ctx.pinnet[(ref, pin_num(ctx, ref, "G"))]
            yg = snap(g[1] + 5.08)
            d.wire(n_g, g, (g[0], yg))
            parts = self.gate_parts[ref]
            src = [r for r in parts if other_net(ctx, r, n_g) == src_net]
            drv = [r for r in parts if r not in src]
            xg = g[0]
            x = snap(xg + s * 7.62)
            xlast = xg
            for r in src:
                Sx = d.vert(r, x, yg, n_g, tx="right" if s > 0 else "left", up=True)
                top = d.other_pin(Sx, n_g)
                d.wire(src_net, top, (top[0], y))
                xlast = x
                x = snap(x + s * (twidth(ctx, r) + 5.08))
            d.wire(n_g, (xg, yg), (xlast, yg))
            for r in drv:
                o = other_net(ctx, r, n_g)
                Sx = d.vert(r, xg, yg, n_g, tx="left" if s > 0 else "right")
                bot = d.other_pin(Sx, n_g)
                d.wire(o, bot, (bot[0], bot[1] + P2)); d.label(o, bot[0], bot[1] + P2, "L" if s > 0 else "R")
        gate(Q1, qc, n_cp, -1)
        gate(Q2, qd, n_out, 1)
        # what else hangs from a path node, always below the path
        def hang(net, xs_, ytop=y, s=1):
            parts = [r for r in ctx.parts_on(net) if r not in ctx.claimed]
            if not parts: return None
            node = grow(ctx, net, parts)
            node.down = {r for r, _, _ in node.parts}
            sub = Doc(ctx)
            draw_node(sub, node, 0, 0, s)
            d.add(sub, xs_ - s * 2.54, ytop)
            return sub.bbox()
        if self.esd:
            r, mid, r2 = self.esd
            ye = snap(y - 10.16)
            xa, xb = snap(s1[0] - 5.08), snap(s2[0] + 5.08)
            xm = snap((xa + xb) / 2)
            C1 = d.horiz(r, snap(xm - 12.7), ye, n_cp, 1)
            C2 = d.horiz(r2, snap(xm + 5.08), ye, mid, 1)
            d.wire(n_cp, (xa, y), (xa, ye), d.net_pin(C1, n_cp))
            d.wire(mid, d.other_pin(C1, n_cp), d.net_pin(C2, mid))
            d.wire(n_out, d.other_pin(C2, mid), (xb, ye), (xb, y))
            d.text("ESD caps across the FET pair", snap(xm - 12.7), snap(ye - 5.08), 1.0)
        hang(n_cp, snap(P(F, "2")[0] + 15.24))
        hang(n_out, snap(s2[0] + 30.48))
        d.place(t["wire_out"], x_end, y, 270, tx=((x_end + 1.5, y + 2.6, "left"), (x_end + 1.5, y + 4.4, "left")))
        d.power(n_out, x_end - 5.08, y, "U")
        # fuse heater down to the ignition FET
        htr = P(F, "HTR")
        n_htr = ctx.pinnet[(t["fuse"], "3")]
        q = t.get("q_fuse")
        if q:
            dn = next(p["num"] for p in ctx.pins_of[q] if ctx.pinnet.get((q, p["num"])) == n_htr)
            Dq = draw_ic(ctx, q, {k[1]: v for k, v in trees.items() if k[0] == q}, bridges.get(q, []), skip={dn}, ic_text="right")
            dpt = next(p["pt"] for S_ in Dq.syms if S_["ref"] == q for p in S_["pins"].values() if p["net"] == n_htr)
            d.add(Dq, htr[0] - dpt[0], snap(htr[1] + 7.62) - dpt[1])
            d.wire(n_htr, htr, (htr[0], snap(htr[1] + 7.62)))
        # return path: cell-stack minus wire, shunt with its Kelvin filter, ground out
        bb = d.bbox()
        yr = snap(bb[3] + 25.4)
        Jr = d.place(t["ret_in"], 0, yr, 90, tx=((-4.5, yr + 2.6, "left"), (-4.5, yr + 4.4, "left")))
        n_cn = ctx.pinnet[(t["ret_in"], "1")]
        pr = list(Jr["pins"].values())[0]["pt"]
        Sh = d.horiz(t["shunt"], snap(x_q1), yr, n_cn, 1, tx="below")
        d.wire(n_cn, pr, d.net_pin(Sh, n_cn))
        kel = {k["resistor"]: k for k in ctx.cons.get("kelvin", {}).values()}
        kelvin_filter(d, t["shunt"], yr, kel.get(t["shunt"]))
        d.text("Current sense (gauge SRP/SRN)", snap(x_q1 - 10.16), snap(yr - 21.0), 1.0)
        n_g = other_net(ctx, t["shunt"], n_cn)
        xg = snap(d.net_pin(Sh, n_g)[0])
        d.place(t["ret_out"], x_end, yr, 270, tx=((x_end + 1.5, yr + 2.6, "left"), (x_end + 1.5, yr + 4.4, "left")))
        d.wire(n_g, (xg, yr), (x_end, yr))
        d.power(n_g, snap(x_end - 5.08), yr, "D")
        hang(n_g, snap(xg + 25.4), yr)
        return d


TEMPLATES = {"buck": Buck, "bridge4": Bridge4, "pack_path": PackPath}


# ------------------------------------------------------------------------------------------------ a block = one sheet

def flow(ctx, docs, wmax, gap=7.62):
    out = Doc(ctx)
    x = y = rowh = 0.0
    for d in docs:
        b = d.bbox(); w, h = b[2] - b[0], b[3] - b[1]
        if x > 0 and x + w > wmax:
            x, y, rowh = 0.0, y + rowh + gap, 0.0
        out.add(d, x - b[0], y - b[1])
        x += w + gap; rowh = max(rowh, h)
    return out

def draw_block(block, comps, nets, nc, cons, order):
    ctx = Ctx(block, comps, nets, nc, cons, order)
    tmpls = []
    for a, t in cons.get("draw", {}).items():
        if a in ctx.refs and t["kind"] in TEMPLATES:
            tmpls.append(TEMPLATES[t["kind"]](ctx, a, t))
    for tp in tmpls: tp.claim()
    drawn_by_t = {x for tp in tmpls for x in tp.drawn}
    attachable = [a for a in ctx.anchors if a not in drawn_by_t]
    overrides = {k: v for tp in tmpls for k, v in tp.overrides.items()}
    bridges = {}
    for tp in tmpls:
        for a, b in tp.bridges.items(): bridges.setdefault(a, []).extend(b)
    for a in attachable:
        bridges.setdefault(a, []).extend(find_bridges(ctx, a))
    trees = plan(ctx, attachable, overrides)
    # what each section holds, in code order
    items = []
    for tp in tmpls:
        dd = tp.draw(trees, bridges)
        if dd is not None: items.append((tp.section or ctx.section(tp.a), ctx.refs.index(tp.a), dd))
    inside = set()
    for tp in tmpls:
        if isinstance(tp, PackPath) and tp.t.get("q_fuse"): inside.add(tp.t["q_fuse"])
    for a in attachable:
        if a in inside: continue
        dd = draw_ic(ctx, a, {k[1]: v for k, v in trees.items() if k[0] == a}, bridges.get(a, []))
        items.append((ctx.section(a), ctx.refs.index(a), dd))
    for lo in leftovers(ctx, ctx.refs):
        r0 = lo[1].parts[0][0] if lo[1].parts else None
        items.append((lo[2], ctx.refs.index(r0) + 10000 if r0 else 99999, draw_leftover(ctx, lo)))
    secs = []
    for r in ctx.refs:
        s = ctx.section(r)
        if s not in secs: secs.append(s)
    for tp in tmpls:
        if tp.section and tp.section not in secs: secs.insert(0, tp.section)
    notes = cons.get("notes", {})
    sec_docs = []
    for s in secs:
        mine = sorted([it for it in items if it[0] == s], key=lambda it: it[1])
        if not mine: continue
        big = [it[2] for it in mine if it[1] < 10000]
        small = [it[2] for it in mine if it[1] >= 10000]
        body = flow(ctx, big, 10 ** 6, 12.7) if big else Doc(ctx)
        if small:
            bw = body.bbox()
            wmax = max(bw[2] - bw[0], 120.0)
            pads = [d for d in small if len(d.syms) and ctx.comps.get(d.syms[0]["ref"], {}).get("lib", "").startswith(("Connector", "Connector_Generic")) and len(d.syms) <= 2]
            rest = [d for d in small if d not in pads]
            sm = flow(ctx, rest, wmax, 7.62) if rest else Doc(ctx)
            if pads:
                col = Doc(ctx); yy = 0.0
                for pd in pads:
                    b = pd.bbox(); col.add(pd, -b[2], yy - b[1]); yy += (b[3] - b[1]) + 2.54
                bb = sm.bbox() if sm.syms else (0, 0, 0, 0)
                sm.add(col, (bb[2] + 12.7 if sm.syms else 0) - col.bbox()[0], -col.bbox()[1] + bb[1])
            bb = body.bbox() if body.syms else (0, 0, 0, 0)
            sb = sm.bbox()
            body.add(sm, bb[0] - sb[0], (bb[3] + 10.16 if body.syms else 0) - sb[1])
        b = body.bbox()
        sec = Doc(ctx)
        sec.text(s, 0, 0, 2.0, True)
        yy = 3.81
        for n_ in notes.get(f"{block}|{s}", []):
            sec.text(n_, 0, yy, 1.27); yy += 2.54 * (n_.count("\n") + 1)
        sec.add(body, -b[0], yy + 6.35 - b[1])
        sec_docs.append(sec)
    return ctx, sec_docs

def pack(ctx, sec_docs, title):
    """Skyline packing of the sections (in code order, or tallest first when that fills the page better); the width is
    chosen so the sheet comes out near A-series shape with little empty space."""
    sizes = []
    for d in sec_docs:
        b = d.bbox(); sizes.append((b[2] - b[0], b[3] - b[1], b))
    GAP = 15.24
    def trial(W, order):
        sky = [(0.0, W, 0.0)]           # (x0, x1, height)
        pos = {}
        for i in order:
            w, h, _ = sizes[i]
            best = None
            for x in sorted({s[0] for s in sky}):
                if x + w > W + 1e-6 and x > 0: continue
                top = max([s[2] for s in sky if s[0] < x + w and s[1] > x] + [0.0])
                if best is None or top < best[1] - 1e-6: best = (x, top)
            x, top = best
            pos[i] = (x, top)
            ns = []
            for s in sky:
                if s[1] <= x or s[0] >= x + w + GAP: ns.append(s); continue
                if s[0] < x: ns.append((s[0], x, s[2]))
                if s[1] > x + w + GAP: ns.append((x + w + GAP, s[1], s[2]))
            ns.append((x, x + w + GAP, top + h + GAP))
            sky = sorted(ns)
        H = max(pos[i][1] + sizes[i][1] for i in pos)
        Wu = max(pos[i][0] + sizes[i][0] for i in pos)
        return Wu, H, [pos[i] for i in range(len(sizes))]
    n = len(sizes)
    code = list(range(n))
    widest = max(code, key=lambda i: sizes[i][0])
    orders = [(code, 1.0), ([i for i in code if i != widest] + [widest], 1.04),
              (sorted(code, key=lambda i: -sizes[i][1]), 1.08), (sorted(code, key=lambda i: -sizes[i][0]), 1.08),
              (sorted(code, key=lambda i: -sizes[i][0] * sizes[i][1]), 1.08)]
    best = None
    wmin = max(s[0] for s in sizes)
    for order, pen in orders:
        for W in [wmin + k * 10 for k in range(0, 80)]:
            Wu, H, pos = trial(W, order)
            Hp = H + 30
            score = Wu * Hp * (1 + 0.6 * abs(math.log(Wu / Hp / 1.414))) * pen
            if best is None or score < best[0]: best = (score, Wu, H, pos)
    _, Wu, H, pos = best
    sheet = Doc(ctx)
    sheet.text(title, 0, -12.7, 3.0, True)
    for d, (x, y), (w, h, b) in zip(sec_docs, pos, sizes):
        sheet.add(d, x - b[0], y - b[1])
    return sheet


# ------------------------------------------------------------------------------------------------ KiCad file

def fjust(angle, mirror, vis):
    if vis == "center": return ""
    flip = (angle in (90, 180)) != mirror
    j = vis if not flip else ("right" if vis == "left" else "left")
    return f"(justify {j})"

def lib_text(key):
    lib, name = key.split(":")
    if lib == "power_local":
        s = symlib.flat("power", name)
        s = [c if not (isinstance(c, list) and c and c[0] == "power") else ["power", "local"] for c in s]
    else:
        s = symlib.flat(lib, name)
    s[1] = ("s", key)
    return dump(s)

def write_sheet(doc, path, project, root_uuid, name, title, page):
    sh_uuid = uid("sheet", name)
    b = doc.bbox()
    M = 15.24
    dx, dy = snap(M + 10 - b[0]), snap(M + 10 - b[1])
    doc.move(dx, dy)
    b = doc.bbox()
    W = max(180, math.ceil((b[2] + M + 10) / 10) * 10)
    H = max(120, math.ceil((b[3] + 45) / 10) * 10)
    out = [f'(kicad_sch (version {VERSION}) (generator "p2p_draw") (generator_version "10.0") (uuid {q(sh_uuid)}) '
           f'(paper "User" {W} {H}) (title_block (title {q(title)}) (comment 1 "Generated from code. Do not edit: change the block source and rebuild."))']
    libs = sorted({S["lib"] for S in doc.syms})
    out.append("(lib_symbols " + "\n".join(lib_text(k) for k in libs) + ")")
    npwr = 0
    for i, S in enumerate(doc.syms):
        ref = S["ref"]
        if S["power"]:
            npwr += 1; ref = f"#PWR{page:02d}{npwr:03d}"
        fa = 90 if S["angle"] in (90, 270) else 0
        props = []
        for f, s, x, y, j, hid in S["fields"]:
            if f == "Reference": s = ref
            props.append(f'(property {q(f)} {q(s)} (at {x:.2f} {y:.2f} {fa}) (effects (font (size 1.27 1.27)) '
                         f'{fjust(S["angle"], S["mirror"], j)}{" (hide yes)" if hid else ""}))')
        if not S["power"]:
            c = doc.ctx.comps[S["ref"]]
            props.append(f'(property "Footprint" {q(c["footprint"])} (at {S["x"]} {S["y"]} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
            for k, v in c["fields"].items():
                props.append(f'(property {q(k)} {q(v)} (at {S["x"]} {S["y"]} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        ln, nm = S["lib"].split(":")
        src = ("power", nm) if ln == "power_local" else (ln, nm)
        drawn = sorted({p["drawn"] for p in symlib.pins(*src) if p["unit"] in (0, S["unit"])})
        key = S["ref"] if not S["power"] else ref
        pins = " ".join(f'(pin {q(p)} (uuid {q(uid(name, key, S["unit"], "pin", p))}))' for p in drawn)
        out.append(f'(symbol (lib_id {q(S["lib"])}) (at {S["x"]} {S["y"]} {S["angle"]}){" (mirror y)" if S["mirror"] else ""} '
                   f'(unit {S["unit"]}) (exclude_from_sim no) (in_bom {"no" if S["power"] else "yes"}) (on_board {"no" if S["power"] else "yes"}) (dnp no) '
                   f'(uuid {q(uid(name, "sym", key, S["unit"]))}) {" ".join(props)} {pins} '
                   f'(instances (project {q(project)} (path {q("/" + root_uuid + "/" + sh_uuid)} (reference {q(ref)}) (unit {S["unit"]})))))')
    # wires: split where another connection point of the same net lies inside, junction where three or more meet
    cpts = set()
    for S in doc.syms:
        for p in S["pins"].values(): cpts.add(p["pt"])
    for W in doc.wires: cpts.add(W["a"]); cpts.add(W["b"])
    for L in doc.labels: cpts.add((L["x"], L["y"]))
    segs = []
    for W in doc.wires:
        inner = sorted([p for p in cpts if on_seg(p, W["a"], W["b"], interior=True)],
                       key=lambda p: abs(p[0] - W["a"][0]) + abs(p[1] - W["a"][1]))
        chain = [W["a"]] + inner + [W["b"]]
        for a_, b_ in zip(chain, chain[1:]): segs.append(tuple(sorted((a_, b_))))
    segs = sorted(set(segs))
    deg = {}
    for a_, b_ in segs:
        deg[a_] = deg.get(a_, 0) + 1; deg[b_] = deg.get(b_, 0) + 1
    for S in doc.syms:
        for p in S["pins"].values():
            if p["pt"] in deg: deg[p["pt"]] += 1
    for a_, b_ in segs:
        out.append(f'(wire (pts (xy {a_[0]} {a_[1]}) (xy {b_[0]} {b_[1]})) (stroke (width 0) (type default)) (uuid {q(uid(name, "w", a_, b_))}))')
    for pt, n in sorted(deg.items()):
        if n >= 3:
            out.append(f'(junction (at {pt[0]} {pt[1]}) (diameter 0) (color 0 0 0 0) (uuid {q(uid(name, "j", pt))}))')
    for L in doc.labels:
        ang = {"R": 0, "U": 90, "L": 180, "D": 270}[L["d"]]
        x, y = L["x"], L["y"]
        if L["glob"]:
            j = {0: "(justify left)", 90: "(justify left)", 180: "(justify right)", 270: "(justify right)"}[ang]
            out.append(f'(global_label {q(L["text"])} (shape passive) (at {x} {y} {ang}) (effects (font (size 1.27 1.27)) {j}) '
                       f'(uuid {q(uid(name, "gl", L["text"], x, y))}) (property "Intersheetrefs" "${{INTERSHEET_REFS}}" '
                       f'(at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes))))')
        else:
            j = {0: "(justify left bottom)", 90: "(justify left bottom)", 180: "(justify right bottom)", 270: "(justify right bottom)"}[ang]
            out.append(f'(label {q(L["text"])} (at {x} {y} {ang}) (effects (font (size 1.27 1.27)) {j}) (uuid {q(uid(name, "l", L["text"], x, y))}))')
    for x, y in doc.ncs:
        out.append(f'(no_connect (at {x} {y}) (uuid {q(uid(name, "nc", x, y))}))')
    for T in doc.texts:
        bold = " bold" if T["bold"] else ""
        out.append(f'(text {q(T["s"])} (exclude_from_sim no) (at {T["x"]} {T["y"]} 0) (effects (font (size {T["size"]} {T["size"]}){bold}) (justify left bottom)) '
                   f'(uuid {q(uid(name, "t", T["s"], T["x"], T["y"]))}))')
    out.append("(embedded_fonts no))")
    open(path, "w").write("\n".join(out) + "\n")


def main(build, outdir, project):
    d = json.load(open(f"{build}/netlist.json"))
    cons = json.load(open(f"{build}/constraints.json"))
    comps, nets, nc = d["comps"], d["nets"], d.get("nc", [])
    order = sorted(comps, key=lambda r: comps[r].get("order", 0))
    os.makedirs(outdir, exist_ok=True)
    root_uuid = uid("root", project)
    blocks = []
    for r in order:
        b = comps[r]["block"]
        if b not in blocks: blocks.append(b)
    root = [f'(kicad_sch (version {VERSION}) (generator "p2p_draw") (generator_version "10.0") (uuid {q(root_uuid)}) (paper "A4") '
            f'(title_block (title {q(project)}) (comment 1 "Generated from code. Do not edit: change the source and rebuild.")) (lib_symbols)']
    total = 0
    for i, b in enumerate(blocks):
        fn = b.lower().replace(" ", "_") + ".kicad_sch"
        ctx, secs = draw_block(b, comps, nets, nc, cons, order)
        sheet = pack(ctx, secs, b)
        connect_labels(sheet)
        issues = lint(sheet, b)
        total += len(issues)
        if os.environ.get("DRAW_LINT"):
            for s in issues: print(f"  [{b}] {s}")
        print(f"{b}: {len(issues)} drawing issues")
        write_sheet(sheet, f"{outdir}/{fn}", project, root_uuid, b, b, i + 2)
        x, y = 30 + (i % 3) * 80, 40 + (i // 3) * 50
        root.append(
            f'(sheet (at {x} {y}) (size 60 30) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (stroke (width 0.1524) (type solid)) '
            f'(fill (color 0 0 0 0)) (uuid {q(uid("sheet", b))}) '
            f'(property "Sheetname" {q(b)} (at {x} {y - 0.7} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) '
            f'(property "Sheetfile" {q(fn)} (at {x} {y + 30.6} 0) (effects (font (size 1.27 1.27)) (justify left top))) '
            f'(instances (project {q(project)} (path {q("/" + root_uuid)} (page {q(i + 2)})))))')
    root.append('(sheet_instances (path "/" (page "1"))) (embedded_fonts no))')
    open(f"{outdir}/{project}.kicad_sch", "w").write("\n".join(root) + "\n")
    print("wrote", len(blocks), "sheets to", outdir)

if __name__ == "__main__":
    main(*sys.argv[1:4])
