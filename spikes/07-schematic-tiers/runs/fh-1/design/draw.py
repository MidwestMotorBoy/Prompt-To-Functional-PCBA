"""Draws KiCad schematic sheets from netlist.json. The netlist is the truth; these sheets are a view of it.

How a sheet is drawn (the way a person would):
  * Every part with three or more pins is drawn once, with what belongs to each pin wired to that pin: decoupling
    and filter parts hang from the pin's wire to ground, pull-ups stand on it (pull-ups of neighbouring pins stand
    side by side and their leads cross the wires in between), series parts and inductors lie in line, a part
    between two pins of the same side (bootstrap capacitor, divider, cell filter) stands between their wires, a
    chain from one pin back to another (pi network) runs along one wire and a wire closes it. Where neighbouring
    pins need more room than the pin pitch gives, their wires move to lanes; the lanes are solved for the least
    wire and the fewest bends.
  * Which part belongs to which pin comes from the circuit (the nets), from `serves` in the block, or from a
    drawing hint (kernel.draw_hint, draw_as).
  * A power path named in the block (draw_as "path") is drawn left to right through its elements: wire pads at
    the ends, a part whose path pins are side by side hangs under the path with its gate parts, what touches a node
    hangs from it, a chain across elements arcs over them, a shunt has its Kelvin filter below it.
    A four-switch power stage (draw_as "bridge4") is drawn the same way: shunt, capacitors, half bridge, inductor,
    half bridge, capacitors, shunt.
  * Ground is a ground symbol; ground pins next to each other share one. A ground of its own (kernel.draw_net
    style="ground") has its own symbol with its name. Supplies with a top-level name are arrows pointing up.
    A label is used only where a net leaves the figure; a wire pad of that net is drawn at the end of its wire.
  * A small transistor driven from one pin is drawn at the end of that pin's wire.
  * What is left (parallel capacitors, loose wire pads) is drawn as a bank or a list under its section title.
  * Sections are packed on a page sized to the drawing, clear of the title block.
Nothing here decides connectivity: make.sh exports KiCad's own netlist of the result and compares it with
netlist.json. sch.lint() reports overlapping text, symbols and wires, and shorts, on every build (out/sheets/lint.txt).

usage: draw.py <build dir> <out dir> <project name>
"""
import json, os, sys, math, bisect, itertools
import symlib
from sch import Fig, Sheet, lint, tw, xf, snap, snap_up, body_bbox, sbox, uid, q, G, VERSION

GAP = 1.27                  # between neighbouring things on a wire
W_DY, W_BEND, W_DX = 2.0, 8.0, 1.0      # cost of moving a pin's wire to a lane (per mm, per bend) and of running it further out

class Cyclic(Exception): pass

class O:
    def __init__(self, **kw): self.__dict__.update(kw)

DIRV = {"R": (1, 0), "L": (-1, 0), "U": (0, -1), "D": (0, 1)}


class Blk:
    """One block = one sheet. Holds the circuit of the block and builds the figures."""
    def __init__(self, block, comps, nets, nc, cons, order):
        self.block, self.comps, self.nets, self.cons = block, comps, nets, cons
        self.refs = [r for r in order if comps[r]["block"] == block]
        self.refset = set(self.refs)
        self.idx = {r: i for i, r in enumerate(self.refs)}
        self.pinnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
        self.ncset = {(r, p) for r, p in nc}
        self.glob = {n for n, nodes in nets.items() if any(r not in self.refset for r, _ in nodes) and any(r in self.refset for r, _ in nodes)}
        self.power = {n for n, d in cons["nets"].items() if d.get("kind") == "power"}
        self.dn = cons.get("draw_nets", {})
        self.hint = cons.get("draw_hints", {})
        self.pins_of = {r: symlib.pins(*comps[r]["lib"].split(":")) for r in self.refs}
        self.groups = {r: self._groups(r) for r in self.refs}
        self.tdraw = {a: t for a, t in cons.get("draw", {}).items() if a in self.refset}
        self.small = [r for r in self.refs if len(self.groups[r]) == 2]
        self.pads = [r for r in self.refs if len(self.groups[r]) == 1]
        self.anchors = [r for r in self.refs if len(self.groups[r]) > 2]
        self.used, self.leftover, self.pad_taken = set(), [], set()
        self.assign()

    # ------------------------------------------------------------------ circuit queries
    def _groups(self, r):
        """Pins of a part grouped by where they are drawn (stacked pins share a place)."""
        gs = {}
        for p in self.pins_of[r]:
            g = gs.setdefault((p["x"], p["y"], p["unit"]), O(x=p["x"], y=p["y"], unit=p["unit"], nums=[], names=[], side={0: "L", 180: "R", 90: "D", 270: "U"}[p["angle"]], hidden=True))
            g.nums.append(p["num"])
            if not p["hidden"]: g.hidden = False; g.names.insert(0, p["name"])
            else: g.names.append(p["name"])
        out = []
        for g in gs.values():
            ns = {self.pinnet.get((r, n)) for n in g.nums if (r, n) not in self.ncset}
            g.nc = not ns or ns == {None}
            if len(ns) > 1: raise SystemExit(f"{r}: stacked pins {g.nums} are on different nets {ns}")
            g.net = None if g.nc else next(iter(ns))
            if g.hidden and g.nc: continue          # hidden unused pins inside the body
            out.append(g)
        out.sort(key=lambda g: (len(g.nums[0]), g.nums[0]))
        return out

    def E(self, r):
        return [g.net for g in self.groups[r]]

    def other(self, r, n):
        e = self.E(r)
        return e[1] if e[0] == n else e[0]

    def pn(self, r, n):
        return {(r, num) for g in self.groups[r] if g.net == n for num in g.nums}

    def lib(self, r): return self.comps[r]["lib"]

    def style(self, n):
        if n == "GND": return "gnd"
        if self.dn.get(n, {}).get("style") == "ground": return "gndref"
        if self.supply(n) and "/" not in n.lstrip("/"): return "flag"      # top-level name: safe as a global arrow
        return "glabel" if n in self.glob else "label"

    def supply(self, n):
        return n != "GND" and (n in self.power or self.dn.get(n, {}).get("style") == "supply")

    def signal(self, n):
        return n is not None and self.style(n) not in ("gnd", "gndref") and not self.supply(n)

    def nm(self, n):
        if "name" in self.dn.get(n, {}): return self.dn[n]["name"]
        s = n.split("/")[-1]
        if s.startswith("Net-(") and s.endswith(")"): s = s[5:-1].replace("-", "_")
        return s

    def pin_group(self, a, pin):
        for g in self.groups[a]:
            if pin in g.nums or pin in g.names: return g
        raise SystemExit(f"drawing hint: {a} has no pin {pin}")

    # ------------------------------------------------------------------ which part is drawn where
    def assign(self):
        """zone[r]: the anchor (or template key) a small part is drawn with. at[r]: (anchor, pin numbers) when a pin is named."""
        comps, cons = self.comps, self.cons
        zone, at = {}, {}
        aset = set(self.anchors)
        self.tkey = {}                      # part -> template that draws it
        for a, t in self.tdraw.items():
            if t["kind"] == "buck":
                for r in [t.get("inductor")] + t.get("cin", []) + t.get("cout", []) + t.get("div", []) + [t.get("boot")]:
                    if r: zone[r] = a
            elif t["kind"] == "bridge4":
                t["_parts"] = self.bridge4_parts(a, t)
                for r in t["_parts"]: self.tkey[r] = a
            elif t["kind"] == "path":
                t["_elems"] = [O(ref=e.split(":")[0], io=(e.split(":")[1].split(">") if ":" in e else None)) for e in t["elems"]]
                for e in t["_elems"]: self.tkey[e.ref] = a
                for r in self.path_kelvin(t): self.tkey[r] = a
                for r in t.get("dock", {}).values(): self.tkey[r] = a
        self.torder = {}
        for a, t in self.tdraw.items():
            for i, r in enumerate(t.get("cin", []) + t.get("cout", [])): self.torder[r] = i
        serves = cons.get("serves", {})
        for r in self.small:
            h = self.hint.get(r, {}).get("at") or (serves.get(r) if serves.get(r, "").split(".")[0] in aset else None)
            if h:
                a, pin = h.split(".", 1)
                g = self.pin_group(a, pin)
                if g.net in self.E(r): at[r] = (a, g.nums)
                if r not in zone or "at" in self.hint.get(r, {}): zone[r] = a
        for hl in cons.get("hot_loops", {}).values():
            a = hl["switch_pins"][0].split(".")[0]
            for r in hl["caps"]:
                if r in self.refset and r not in zone and a in aset: zone[r] = a
        sec = lambda r: comps[r].get("section")
        def by_nets(r, pred):
            cand = {}
            for n in self.E(r):
                if not pred(n): continue
                for a in {a for a, _ in self.nets[n]}:
                    if a in aset and a != r: cand[a] = cand.get(a, 0) + 1
            if cand: return max(cand, key=lambda a: (cand[a], sec(a) == sec(r), -self.idx[a]))
        for r in self.small:
            if r in zone or r in self.tkey: continue
            z = by_nets(r, self.signal) or by_nets(r, lambda n: self.supply(n) and n not in self.glob)
            if z: zone[r] = z
        for _ in range(4):                  # parts that only touch other small parts follow them
            for r in self.small:
                if r in zone or r in self.tkey: continue
                s = serves.get(r, "").split(".")[0]
                if s in zone: zone[r] = zone[s]; continue
                for n in self.E(r):
                    if self.signal(n) and len(self.nets[n]) <= 3:
                        for o, _ in self.nets[n]:
                            if o != r and o in zone: zone[r] = zone[o]
        # a part drawn with an element of a path is drawn by the path
        for r in list(zone):
            k = self.tkey.get(zone[r])
            if k and self.tdraw[k]["kind"] == "path" and zone[r] in [e.ref for e in self.tdraw[k]["_elems"]]: zone[r] = k
        for a, t in self.tdraw.items():
            if t["kind"] != "path": continue
            nodes = self.path_nodes(t)
            for r in self.small:
                if r not in zone and r not in self.tkey and any(n in nodes for n in self.E(r)): zone[r] = a
            for _ in range(3):
                for r in self.small:
                    if r in zone or r in self.tkey: continue
                    for n in self.E(r):
                        if self.signal(n) and any(zone.get(o) == a for o, _ in self.nets[n] if o != r): zone[r] = a
        # a small transistor whose input is driven from a pin of another part is drawn at the end of that pin's wire
        self.dock = {}
        for qq in self.anchors:
            if len(self.groups[qq]) != 3 or qq in self.tkey or qq in self.tdraw: continue
            for g in self.groups[qq]:
                if g.side not in "LU" or g.nc or not self.signal(g.net) or g.net in self.glob: continue
                hosts = [(a, num) for a, num in self.nets[g.net] if a in aset and a != qq]
                if len(hosts) != 1: continue
                h, hnum = hosts[0]
                hg = self.pin_group(h, hnum)
                if hg.side not in "LR" or (g.side == "L" and hg.side != "R") or h in self.tkey or h in self.dock: continue
                self.dock[qq] = (h, tuple(hg.nums), g.nums[0])
                for r in self.small:
                    if zone.get(r) == qq and g.net in self.E(r): zone[r] = h
                break
        self.zone, self.at = zone, at

    def mine(self, a):
        rs = [r for r in self.small if self.zone.get(r) == a and r not in self.used and r not in self.tkey]
        rs.sort(key=lambda r: (self.torder.get(r, 99), self.idx[r]))
        return rs

    # ------------------------------------------------------------------ drawing primitives
    def put(self, f, r, x, y, angle=0, mirror=False, unit=1, texts=None):
        c = self.comps[r]; lib, name = c["lib"].split(":")
        if (r, unit) in self.used: raise SystemExit(f"{r} unit {unit} drawn twice")
        self.used.add((r, unit)); self.used.add(r)
        tn = {p["num"]: self.pinnet.get((r, p["num"])) for p in self.pins_of[r]}
        return f.sym(lib, name, r, c["value"], x, y, angle, mirror, unit, texts, c["footprint"], c["fields"], tn)

    def part2(self, f, r, x1, y1, d, first_net, tpos=None):
        """Two-terminal part with its first_net end at (x1, y1), lying in direction d (D, U, R, L). Returns the other end."""
        ga, gb = self.groups[r]
        if ga.net != first_net: ga, gb = gb, ga
        want = DIRV[d]
        for ang in (0, 90, 180, 270):
            ax, ay = xf(ga.x, ga.y, ang); bx, by = xf(gb.x, gb.y, ang)
            vx, vy = bx - ax, by - ay
            if abs(vx * want[1] - vy * want[0]) < 1e-6 and vx * want[0] + vy * want[1] > 0: break
        else:
            raise SystemExit(f"{r} cannot be drawn in direction {d}")
        ox, oy = snap(x1 - ax), snap(y1 - ay)
        x2, y2 = snap(ox + bx), snap(oy + by)
        lib, name = self.lib(r).split(":")
        b = sbox(lib, name, ox, oy, ang)
        ref, value = r, self.comps[r]["value"]
        wr, wv = tw(ref), tw(value)
        if tpos is None: tpos = "right" if d in "DU" else "above"
        if tpos in ("right", "left"):
            yc = (y1 + y2) / 2
            if tpos == "right": t = {"ref": (b[2] + .9 + wr / 2, yc - 1.2), "val": (b[2] + .9 + wv / 2, yc + 1.2)}
            else: t = {"ref": (b[0] - .9 - wr / 2, yc - 1.2), "val": (b[0] - .9 - wv / 2, yc + 1.2)}
        else:
            xc = (x1 + x2) / 2
            if wr + wv + 1.2 <= max(abs(x2 - x1) + 6.5, 15):
                x0 = xc - (wr + 1.2 + wv) / 2
                ty = b[1] - 1.25 if tpos == "above" else b[3] + 1.25
                t = {"ref": (x0 + wr / 2, ty), "val": (x0 + wr + 1.2 + wv / 2, ty)}
            elif tpos == "above": t = {"ref": (xc, b[1] - 3.1), "val": (xc, b[1] - 1.25)}
            else: t = {"ref": (xc, b[3] + 1.25), "val": (xc, b[3] + 3.1)}
        self.put(f, r, ox, oy, ang, texts=t)
        return x2, y2

    def vext(self, r):
        """(left, right) room a part standing upright needs beside its wire, with its text on the right."""
        lib, name = self.lib(r).split(":")
        ga, gb = self.groups[r]
        for ang in (0, 90):
            ax, ay = xf(ga.x, ga.y, ang); bx, by = xf(gb.x, gb.y, ang)
            if abs(ax - bx) < 1e-6: break
        b = sbox(lib, name, -ax, 0, ang)
        return -b[0], b[2] + .9 + max(tw(r), tw(self.comps[r]["value"]))

    def span(self, r):
        ga, gb = self.groups[r]
        return snap(math.hypot(ga.x - gb.x, ga.y - gb.y))

    def term(self, f, n, x, y, d):
        """End net n at (x, y), where its wire arrives heading in direction d."""
        st, nm = self.style(n), self.nm(n)
        if st in ("gnd", "gndref"):
            if d == "U":
                f.wire(x, y, x + 2.54, y, n); f.power(st, nm, x + 2.54, y, "D")
            else: f.power(st, nm, x, y, d)
        elif st == "flag":
            if d == "U": f.power("flag", nm, x, y)
            elif d == "D":
                f.wire(x, y, x + 2.54, y, n); f.label(nm, x + 2.54, y, "R", True, n)
            else: f.label(nm, x, y, d, True, n)
        elif d in "LR":
            f.label(nm, x, y, d, st == "glabel", n)
        elif st == "glabel":
            f.wire(x, y, x + 2.54, y, n); f.label(nm, x + 2.54, y, "R", True, n)
        elif d == "U":
            f.label(nm, x, y, "R", False, n)
        else:
            f.wire(x, y, x, y + 2.54, n); f.label(nm, x, y + 2.54, "R", False, n)

    def pad(self, f, r, x, y, d, tpos=None):
        """Single-pad part (wire pad, test point) connected at (x, y) with its body in direction d."""
        g = self.groups[r][0]
        lib, name = self.lib(r).split(":")
        b = body_bbox(lib, name)
        bc = ((b[0] + b[2]) / 2 - g.x, (b[1] + b[3]) / 2 - g.y)
        for ang in (0, 90, 180, 270):
            vx, vy = xf(bc[0], bc[1], ang)
            if vx * DIRV[d][0] + vy * DIRV[d][1] > 0.5 * math.hypot(vx, vy): break
        px, py = xf(g.x, g.y, ang)
        ox, oy = snap(x - px), snap(y - py)
        bb = sbox(lib, name, ox, oy, ang)
        ref, value = r, self.comps[r]["value"]
        wr, wv = tw(ref), tw(value)
        tpos = tpos or {"R": "right", "L": "left", "D": "right", "U": "above"}[d]
        if tpos == "right": t = {"ref": (bb[2] + .9 + wr / 2, (bb[1] + bb[3]) / 2 - 1.2), "val": (bb[2] + .9 + wv / 2, (bb[1] + bb[3]) / 2 + 1.2)}
        elif tpos == "left": t = {"ref": (bb[0] - .9 - wr / 2, (bb[1] + bb[3]) / 2 - 1.2), "val": (bb[0] - .9 - wv / 2, (bb[1] + bb[3]) / 2 + 1.2)}
        elif tpos == "line":
            x0 = bb[0] - .9 - wr - 1.2 - wv if d == "L" else bb[2] + .9
            t = {"ref": (x0 + wr / 2, (bb[1] + bb[3]) / 2), "val": (x0 + wr + 1.2 + wv / 2, (bb[1] + bb[3]) / 2)}
        elif tpos == "none": t = {}
        else: t = {"ref": ((bb[0] + bb[2]) / 2, bb[1] - 3.1), "val": ((bb[0] + bb[2]) / 2, bb[1] - 1.25)}
        self.put(f, r, ox, oy, ang, texts=t)

    def free_pad(self, n):
        """A single-pad part on net n that is not drawn yet."""
        for r, _ in self.nets[n]:
            if r in self.refset and len(self.groups[r]) == 1 and r not in self.used and r not in self.tkey: return r

    # ---- things on a pin's wire. Each is a small figure with its connection point at (0, 0) ----
    def hang_fig(self, chain, net):
        f = Fig(); y = 0
        for i, r in enumerate(chain):
            _, y = self.part2(f, r, 0, y, "D", net)
            net = self.other(r, net)
            if i < len(chain) - 1: f.wire(0, y, 0, y + 2.54, net); y += 2.54
        p = self.free_pad(net) if self.signal(net) and len(self.nets[net]) == 2 else None
        if p: self.pad(f, p, 0, y, "D")
        else: self.term(f, net, 0, y, "D")
        return f

    def stand_fig(self, r, net, sg=1):
        f = Fig()
        _, y = self.part2(f, r, 0, 0, "U", net)
        m = self.other(r, net)
        st = self.style(m)
        if st == "flag": f.power("flag", self.nm(m), 0, y)
        elif st == "glabel": f.wire(0, y, 2.54 * sg, y, m); f.label(self.nm(m), 2.54 * sg, y, "R" if sg > 0 else "L", True, m)
        elif st in ("gnd", "gndref"): f.wire(0, y, 2.54 * sg, y, m); f.power(st, self.nm(m), 2.54 * sg, y, "D")
        else: f.label(self.nm(m), 0, y, "R", False, m)
        return f

    def series_fig(self, r, net, sg, tpos="above"):
        f = Fig()
        x2, _ = self.part2(f, r, 0, 0, "R" if sg > 0 else "L", net, tpos)
        f.ports["out"] = (x2, 0)
        return f

    # ------------------------------------------------------------------ a part with its pins
    def anchor_fig(self, a, open_num=None):
        """Part a at (0, 0) with everything that hangs on its pins. open_num: a pin left bare for the caller to wire
        (its end is ports["open"])."""
        mine, claimed = self.mine(a), set()
        units = sorted({g.unit for g in self.groups[a]} - {0}) or [1]
        out, y = Fig(), 0.0
        for u in units:                     # the units of a part are drawn one below the other
            fu = self.unit_fig(a, u, [g for g in self.groups[a] if g.unit in (0, u) and (g.unit or u == units[0])], mine, claimed, open_num)
            bx = fu.bbox()
            out.place(fu, 0, snap_up(y - bx[1]) if u != units[0] else 0)
            y = out.bbox()[3] + 5.08
        self.leftover += [r for r in mine if r not in claimed]
        return out

    def unit_fig(self, a, unit, gs, mine, claimed, open_num):
        f = Fig()
        lib, name = self.lib(a).split(":")
        b = body_bbox(lib, name, unit)
        body = (b[0], -b[3], b[2], -b[1])
        side = {s: [g for g in gs if g.side == s] for s in "LRUD"}
        ctx = O(a=a, mine=mine, claimed=claimed, open=open_num, gs=self.groups[a])
        for s in "LR":
            if side[s]: self.side(f, ctx, s, sorted(side[s], key=lambda g: -g.y))
        self.top_bottom(f, ctx, sorted(side["U"], key=lambda g: g.x), sorted(side["D"], key=lambda g: g.x), body)
        # reference and value: the first corner of the body where they are clear of everything drawn
        ref, value = a, self.comps[a]["value"]
        wr, wv = tw(ref), tw(value)
        w = max(wr, wv)
        stubs = [(g.x - .4, min(-g.y, body[1]), g.x + .4, max(-g.y, body[3])) for g in gs if g.side in "UD"]
        def clear(box):
            return not f.hit_box(box, skip=()) and not any(box[0] < b_[2] and b_[0] < box[2] and box[1] < b_[3] and b_[1] < box[3] for b_ in stubs)
        cands = []
        if body[3] - body[1] <= 10.5:           # a small body: beside it, as KiCad does
            for x_ in ([body[2] + .9] if not side["R"] else []) + ([body[0] - .9 - w] if not side["L"] else []):
                cands.append(({"ref": (x_ + wr / 2, -1.2), "val": (x_ + wv / 2, 1.2)}, (x_, -2.1, x_ + w, 2.1)))
        xs = [body[0], body[2] - w] + [body[0] + 2.54 * k for k in range(1, 14)] + [body[0] - 2.54 * k for k in range(1, 6)]
        for cx in xs:
            for top in (True, False):
                ys = (body[1] - 3.3, body[1] - 1.4) if top else (body[3] + 1.4, body[3] + 3.3)
                cands.append(({"ref": (cx + wr / 2, ys[0]), "val": (cx + wv / 2, ys[1])}, (cx, ys[0] - .9, cx + w, ys[1] + .9)))
        t = next((t_ for t_, box in cands if clear(box)), cands[0][0])
        self.put(f, a, 0, 0, unit=unit, texts=t)
        return f

    def side(self, f, ctx, s, groups):
        """Everything on the left or right pins of a part: see the module text. Where the parts between the pins
        cannot be put in an order without crossing, the pins are drawn one by one with labels instead."""
        keep = (set(self.used), set(ctx.claimed), list(self.leftover), set(self.pad_taken))
        for plain in (False, True):
            try: return self._side(f, ctx, s, groups, plain)
            except Cyclic:
                if plain: raise SystemExit(f"{ctx.a}: the parts on the {s} pins cannot be put in order")
                self.used = set(keep[0]); ctx.claimed.clear(); ctx.claimed.update(keep[1]); self.leftover[:] = keep[2]
                self.pad_taken = set(keep[3])

    def _side(self, f, ctx, s, groups, plain):
        a, mine, claimed = ctx.a, ctx.mine, ctx.claimed
        sg = 1 if s == "R" else -1
        rows = [O(g=g, i=i, net=g.net, px=g.x, py=-g.y, kind=None, nodes=[], seq=[], dx=0.0, flat=False, y=-g.y, ext=0.0, grp=None, stand_end=0.0) for i, g in enumerate(groups)]
        for r in rows:
            if r.g.nc: r.kind = "nc"
            elif ctx.open is not None and ctx.open in r.g.nums: r.kind = "open"
            elif self.style(r.net) in ("gnd", "gndref"): r.kind = "gnd"       # a ground pin gets a symbol, nothing else
        live = [r for r in rows if r.kind is None]
        bynet = {}
        for r in live: bynet.setdefault(r.net, []).append(r)
        multi = {n: rs for n, rs in bynet.items() if len(rs) > 1 and not plain}
        bad = {n for n, rs in multi.items()
               if any(m != n and any(rs[0].i < r2.i < rs[-1].i for r2 in rs2) and any(rs2[0].i < r1.i < rs2[-1].i for r1 in rs) for m, rs2 in multi.items())}
        host = {n: rs[0] for n, rs in bynet.items() if n not in bad and not plain}
        cols, bridges = [], []
        newnode = lambda row, n, depth: O(net=n, depth=depth, row=row, cols=[], hangs=[], stands=[], series=None, end=None, pre=False, att=set(), isl=None)
        for n, rs in multi.items():
            if n in bad: continue
            for r in rs[1:]: r.kind = "strap"; r.nodes = [newnode(r, n, 0)]

        pinnets = {g.net for g in ctx.gs if not g.nc}
        private = lambda n: all(r_ == a or r_ in mine for r_, _ in self.nets[n])
        def grow(row, n, depth):
            nd = newnode(row, n, depth); row.nodes.append(nd)
            if depth > 0 and n in host and host[n] is not row:
                bridges.append((None, nd, host[n]))
            if depth == 0:                  # a test point of this part's section stands on the wire
                for pr, _ in self.nets[n]:
                    if pr in self.refset and len(self.groups[pr]) == 1 and pr not in self.used and pr not in self.tkey \
                            and pr not in self.pad_taken and self.comps[pr].get("section") == self.comps[a].get("section"):
                        self.pad_taken.add(pr); nd.stands.append((pr, None))
            cands = []
            rownums = {num for r2 in bynet.get(row.net, [row]) for num in r2.g.nums}
            for p in mine:
                if p in claimed or n not in self.E(p): continue
                h = self.at.get(p)
                if h and h[0] == a and depth == 0 and not (set(h[1]) & rownums): continue
                m = self.other(p, n)
                st = self.style(m)
                if st in ("gnd", "gndref"):
                    claimed.add(p); nd.hangs.append([p])
                elif m in host and host[m] is not row and self.lib(p) == "Device:L":
                    cands.append((p, m))                            # an inductor lies in line; a wire closes the loop to the sense pin
                elif m in host and host[m] is not row:
                    if (self.supply(m) or self.supply(n)) and abs(host[m].py - row.py) > 10.2:
                        # a pull-up stands on the signal's wire instead of spanning half the part
                        if self.supply(m) and not (depth > 0 and self.supply(n)): claimed.add(p); nd.stands.append((p, m))
                    elif depth == 0 or self.supply(n): claimed.add(p); bridges.append((p, nd, host[m]))
                    elif private(n): cands.append((p, m))            # a chain between two pins runs on; a wire closes it
                    # else it is left for the row of that pin
                elif depth > 0 and self.supply(n): continue         # a supply reached through an inductor is not followed further
                elif self.supply(m) and self.lib(p) != "Device:L":
                    claimed.add(p); nd.stands.append((p, m))
                elif (self.supply(n) or depth > 0) and m in pinnets: continue      # left for the row of that pin
                else: cands.append((p, m))
            if cands:
                cont = lambda pm: any(o not in claimed and o != pm[0] and pm[1] in self.E(o) for o in mine) or pm[1] in host
                cands.sort(key=lambda pm: not cont(pm))
                p, m = cands[0]
                for p2, m2 in cands[1:]: claimed.add(p2); nd.stands.append((p2, m2))
                claimed.add(p); nd.series = (p, m)
                grow(row, m, depth + 1)

        for r in live:
            if r.kind is None: grow(r, r.net, 0)
        # ---- columns: parts and straps that stand between the wires of two or more pins ----
        for p, nd, rowb in bridges:
            pair = sorted([nd, rowb.nodes[0]], key=lambda x: x.row.i)
            cols.append(O(nodes=pair, parts=[p], head=None, tail=None, u=0.0))
        for n, rs in multi.items():
            if n in bad: continue
            col = O(nodes=[r.nodes[0] for r in rs], parts=[None] * (len(rs) - 1), head=None, tail=None, u=0.0)
            if self.style(n) in ("gnd", "gndref"): col.tail = ("term", n)
            cols.append(col)
        merged = True
        while merged:                       # a divider or a cell-filter ladder: bridges end to end become one column
            merged = False
            for c1 in cols:
                for c2 in cols:
                    if c1 is c2 or c1.parts[-1] is None or c2.parts[0] is None or c1.tail or c2.head: continue
                    if c1.nodes[-1] is c2.nodes[0] and c1.nodes[-1].depth == 0 and self.lib(c1.parts[-1]) == self.lib(c2.parts[0]):
                        c1.nodes += c2.nodes[1:]; c1.parts += c2.parts; c1.tail = c2.tail
                        cols.remove(c2); merged = True; break
                if merged: break
        for c in cols:
            if c.parts[-1] is not None and not c.tail and c.nodes[-1].depth == 0:
                for ch in c.nodes[-1].hangs:
                    if self.lib(ch[0]) == self.lib(c.parts[-1]): c.tail = ("hang", ch); c.nodes[-1].hangs.remove(ch); break
            if c.parts[0] is not None and c.nodes[0].depth == 0 and self.lib(c.parts[0]) == "Device:R":
                for st in c.nodes[0].stands:
                    if self.lib(st[0]) == "Device:R": c.head = st; c.nodes[0].stands.remove(st); break
            for nd in c.nodes: nd.cols.append(c)
        for r in rows:
            for nd in r.nodes: nd.cols.sort(key=lambda c: (c.nodes[-1].row.i - c.nodes[0].row.i, c.nodes[-1].row.i, cols.index(c)))
        # ---- what is still to be named: every island of wire needs a label unless all pins of the net are on it ----
        par = {}
        def find_(x):
            while par.get(id(x), x) is not x: x = par[id(x)]
            return x
        allnodes = [nd for r in rows for nd in r.nodes]
        for r in rows:
            prev = None
            for nd in r.nodes:
                if nd.depth == 0: nd.att |= {(a, num) for num in r.g.nums}
                for ch in nd.hangs: nd.att |= self.pn(ch[0], nd.net)
                for p, _ in nd.stands: nd.att |= self.pn(p, nd.net)
                if nd.series: nd.att |= self.pn(nd.series[0], nd.net)
                if prev is not None: nd.att |= self.pn(prev.series[0], nd.net)
                prev = nd
        for c in cols:
            for i, p in enumerate(c.parts):
                na, nb = c.nodes[i], c.nodes[i + 1]
                if p is None: par[id(find_(nb))] = find_(na)
                else: na.att |= self.pn(p, na.net); nb.att |= self.pn(p, nb.net)
            if c.head: c.nodes[0].att |= self.pn(c.head[0], c.nodes[0].net)
            if c.tail and c.tail[0] == "hang": c.nodes[-1].att |= self.pn(c.tail[1][0], c.nodes[-1].net)
        isl = {}
        for nd in allnodes: isl.setdefault(id(find_(nd)), []).append(nd)
        for nds in isl.values():
            n = nds[0].net
            if n is None: continue
            rest = set(map(tuple, self.nets[n])) - set().union(*[nd.att for nd in nds])
            if not rest: continue
            if any(c.tail and c.tail[0] == "term" and c.nodes[0] in nds for c in cols): continue      # ground bus: its symbol names it
            weight = lambda nd: (nd.series is None, len(nd.hangs) + len(nd.stands) + len(nd.cols))
            nd = max(nds, key=weight)
            if nd.series: nd.pre = True; continue
            pads = [x for x in rest if x[0] in self.refset and len(self.groups[x[0]]) == 1 and x[0] not in self.used and x[0] not in self.tkey
                    and x[0] not in self.pad_taken]
            if len(rest) == 1 and pads and self.signal(n): nd.end = ("pad", pads[0][0]); self.pad_taken.add(pads[0][0])
            elif pads and self.signal(n) and n not in self.glob and nd.depth <= 1 and nd.row.kind != "strap":
                nd.end = ("padlabel", pads[0][0]); self.pad_taken.add(pads[0][0])       # the wire pad of this net, and its name
            elif len(rest) == 1 and next(iter(rest))[0] in self.dock and self.dock[next(iter(rest))[0]][:2] == (a, tuple(nd.row.g.nums)) \
                    and next(iter(rest))[0] not in self.used and nd.row.kind != "strap":
                qq = next(iter(rest))[0]; nd.end = ("dock", qq, self.dock[qq][2])
            else: nd.end = ("term", n)
        # ---- kinds of rows; a single resistor to ground lies in line with its pin ----
        for r in rows:
            if r.kind in ("nc", "open", "gnd"): continue
            nd = r.nodes[0]
            if len(r.nodes) == 1 and not nd.cols and not nd.stands and not nd.series:
                if not nd.hangs and (nd.end is None or nd.end[0] == "term") and self.style(nd.net) != "flag": r.kind = "simple"; continue
                if len(nd.hangs) == 1 and nd.end is None and self.lib(nd.hangs[0][0]) == "Device:R" and self.style(self.other(nd.hangs[0][0], nd.net)) == "gnd":
                    p = nd.hangs.pop()[0]; nd.series = (p, "GND"); r.flat = True
                    n2 = newnode(r, "GND", 1); n2.end = ("term", "GND"); r.nodes.append(n2)
            r.kind = "trunk"
        trunk = [r for r in rows if r.kind == "trunk"]
        # rows that end on a column and carry nothing else get their name at the start
        for r in trunk:
            nd = r.nodes[0]
            if len(r.nodes) == 1 and nd.cols and not nd.hangs and not nd.stands and nd.end and nd.end[0] == "term" and all(c.nodes[0] is not nd for c in nd.cols):
                nd.pre = True; nd.end = None
        # ---- the things on each row, in order outward from the pin ----
        def mk(fig, kind, thru=0.0):
            bx = fig.bbox()
            u0, u1 = (bx[0], bx[2]) if sg > 0 else (-bx[2], -bx[0])
            return O(kind=kind, fig=fig, u0=u0, u1=u1, up=-bx[1], dn=bx[3], thru=thru, col=None, u=0.0)
        for c in cols:
            lefts, rights = [0.6], [0.6]
            for p in c.parts:
                if p is not None:
                    l, r_ = self.vext(p); lefts.append(l); rights.append(r_)
            c.headfig = self.stand_fig(c.head[0], c.nodes[0].net, sg) if c.head else None
            c.tailfig = None
            if c.tail and c.tail[0] == "hang": c.tailfig = self.hang_fig(c.tail[1], c.nodes[-1].net)
            elif c.tail:
                c.tailfig = Fig(); c.tailfig.wire(0, 0, 0, 2.54, c.tail[1]); self.term(c.tailfig, c.tail[1], 0, 2.54, "D")
            for fg in (c.headfig, c.tailfig):
                if fg: bx = fg.bbox(); lefts.append(-bx[0]); rights.append(bx[2])
            c.left, c.right = (max(lefts), max(rights)) if sg > 0 else (max(rights), max(lefts))
        for r in trunk:
            for nd in r.nodes:
                if nd.pre:
                    fg = Fig(); fg.label(self.nm(nd.net), 0, 0, "R" if sg > 0 else "L", self.style(nd.net) in ("glabel", "flag", "gndref"), nd.net)
                    e = mk(fg, "pre"); e.u1 += 1.27; r.seq.append(e)
                for c in nd.cols: r.seq.append(O(kind="col", col=c, fig=None, thru=0.0, u=0.0))
                for ch in nd.hangs: r.seq.append(mk(self.hang_fig(ch, nd.net), "hang"))
                for p, m in nd.stands:
                    if m is None:
                        fg = Fig(); self.pad(fg, p, 0, 0, "U", "above"); r.seq.append(mk(fg, "stand"))
                    else: r.seq.append(mk(self.stand_fig(p, nd.net, sg), "stand"))
                if nd.series:
                    fg = self.series_fig(nd.series[0], nd.net, sg, "below" if r.flat else "above")
                    r.seq.append(mk(fg, "series", abs(fg.ports["out"][0])))
                elif nd.end:
                    fg = Fig()
                    if nd.end[0] == "term":
                        st = self.style(nd.net)
                        if st in ("gnd", "gndref"): self.term(fg, nd.net, 0, 0, "D")
                        elif st == "flag": fg.power("flag", self.nm(nd.net), 0, 0)
                        else: self.term(fg, nd.net, 0, 0, s)
                    elif nd.end[0] == "pad": self.pad(fg, nd.end[1], 0, 0, s, "line")
                    elif nd.end[0] == "padlabel":
                        nm_ = self.nm(nd.net); w = snap_up(tw(nm_) + 2.54)
                        fg.wire(0, 0, sg * w, 0, nd.net); fg.label(nm_, sg * 1.27, 0, s, False, nd.net)
                        self.pad(fg, nd.end[1], sg * w, 0, s, "line")
                    else:
                        sub = self.anchor_fig(nd.end[1], nd.end[2])
                        ox, oy = sub.ports["open"]
                        if self.pin_group(nd.end[1], nd.end[2]).side == "U":
                            fg.wire(0, 0, sg * 2.54, 0, nd.net); fg.wire(sg * 2.54, 0, sg * 2.54, 2.54, nd.net); fg.place(sub, sg * 2.54 - ox, 2.54 - oy)
                        else: fg.place(sub, -ox, -oy)
                    r.seq.append(mk(fg, "end"))
        free = [r for r in trunk if not any(e.kind == "col" for e in r.seq)]
        # ---- pull-ups on neighbouring pins: the resistors stand side by side above the first of those wires and
        #      their leads cross the wires in between, so that every wire stays straight ----
        groups_, g = [], None
        for r in rows:
            if r.kind != "trunk": continue
            nd = r.nodes[0]
            if len(r.nodes) == 1 and nd.stands and not nd.cols and not nd.hangs and not nd.series and not nd.pre:
                if g is None or r.py - g.rows[-1].py > 5.1: g = O(rows=[], endu=0.0); groups_.append(g)
                g.rows.append(r)
            else: g = None
        for g in groups_:
            if len(g.rows) > 1:
                for r in g.rows: r.grp = g

        def layout():
            for c in cols: c.u = 0.0
            for g in groups_: g.endu = 0.0
            for _ in range(40):
                changed = False
                for r in trunk:
                    cur = r.dx + GAP
                    g = r.grp
                    if g and r is not g.rows[0]: cur = max(cur, g.rows[g.rows.index(r) - 1].stand_end)
                    for e in r.seq:
                        if g and e.kind == "end":
                            r.stand_end = cur
                            if cur > g.endu + 1e-6: g.endu = cur; changed = True
                            e.u = snap_up(max(cur, g.endu) + GAP - e.u0); cur = e.u + max(e.u1, e.thru)
                        elif e.kind == "col":
                            u = snap_up(max(e.col.u, cur + GAP + e.col.left))
                            if u > e.col.u + 1e-6: e.col.u = u; changed = True
                            e.u = e.col.u; cur = e.u + e.col.right
                        elif e.kind == "pre":
                            e.u = snap_up(cur + GAP); cur = e.u + e.u1
                        else:
                            e.u = snap_up(cur + GAP - e.u0); cur = e.u + max(e.u1, e.thru)
                    if g and not (r.seq and r.seq[-1].kind == "end"):
                        r.stand_end = cur
                        if cur > g.endu + 1e-6: g.endu = cur; changed = True
                    r.ext = cur
                for c in cols:
                    lo, hi = c.nodes[0].row.i, c.nodes[-1].row.i
                    mem = {id(nd.row) for nd in c.nodes}
                    for r in trunk:
                        if lo < r.i < hi and id(r) not in mem:
                            u = snap_up(r.ext + GAP + c.left)
                            if u > c.u + 1e-6: c.u = u; changed = True
                if not changed: return
            raise Cyclic()

        def shapes(r):
            bs = []
            last = 0.0
            for e in r.seq:
                if e.kind == "col":
                    c = e.col
                    up = dn = 0.6
                    if c.nodes[0].row is r and c.headfig: up = -c.headfig.bbox()[1]
                    if c.nodes[-1].row is r and c.tailfig: dn = c.tailfig.bbox()[3]
                    bs.append((e.u - c.left, e.u + c.right, up, dn)); last = e.u
                elif e.kind == "stand" and r.grp:
                    bs.append((e.u - .3, e.u + .3, .6, .6)); last = e.u         # only its lead is on this wire
                else:
                    bs.append((e.u + e.u0, e.u + e.u1, max(e.up, .6), max(e.dn, .6))); last = e.u + e.thru
            if r.grp and r is r.grp.rows[0]:
                for o in r.grp.rows:
                    bs += [(e.u + e.u0, e.u + e.u1, e.up + 2.54, .6) for e in o.seq if e.kind == "stand"]
            bs.append((0.0, last, .6, .6))
            return bs

        def solve():
            layout()
            sh = {id(r): shapes(r) for r in trunk}
            n = len(trunk)
            sep = [[0.0] * n for _ in range(n)]
            for j in range(n):
                for k in range(j + 1, n):
                    sv = 2.54
                    for bj in sh[id(trunk[j])]:
                        for bk in sh[id(trunk[k])]:
                            if bj[0] < bk[1] + .4 and bk[0] < bj[1] + .4: sv = max(sv, bj[3] + bk[2] + .5)
                    sep[j][k] = snap_up(sv)
            pos = {id(r): i for i, r in enumerate(trunk)}
            for c in cols:
                for i, p in enumerate(c.parts):
                    j, k = pos[id(c.nodes[i].row)], pos[id(c.nodes[i + 1].row)]
                    sep[j][k] = max(sep[j][k], self.span(p) if p is not None else 2.54)
            P = [r.py for r in trunk]
            y = []
            for k in range(n):
                y.append(max([P[k]] + [y[j] + sep[j][k] for j in range(k)]))
            cost = lambda yy: sum(abs(a_ - b_) for a_, b_ in zip(yy, P))
            better = True
            while better:
                better = False
                for k in range(n):
                    for step in (20.32, 10.16, 5.08, 2.54, 1.27):
                        ny = list(y); ny[k] -= step
                        for j in range(k - 1, -1, -1):
                            lim = min(ny[m] - sep[j][m] for m in range(j + 1, n) if m <= k or ny[m] != y[m] or True)
                            if ny[j] > lim: ny[j] = lim
                        if cost(ny) < cost(y) - 1e-6: y = ny; better = True; break
            c_ = sum(W_DY * abs(a_ - b_) + (W_BEND if abs(a_ - b_) > 1e-6 else 0) for a_, b_ in zip(y, P)) + W_DX * sum(r.dx for r in trunk)
            return c_, y

        best, ys = solve()
        if free and best > W_DX:                    # run a wire further out where that saves bends
            for _ in range(2):
                for r in reversed(free):
                    if abs(ys[trunk.index(r)] - r.py) < 1e-6 and not any(abs(ys[trunk.index(o)] - o.py) > 1e-6 for o in trunk if abs(o.i - r.i) <= 2):
                        continue
                    keep = r.dx
                    for d in sorted({0.0} | {snap_up(o.ext + GAP) for o in trunk if o is not r and o.ext < 75}):
                        if d == keep: continue
                        r.dx = d
                        c_, y_ = solve()
                        if c_ < best - 1e-6: best, ys, keep = c_, y_, d
                    r.dx = keep
            best, ys = solve()
        for r, y_ in zip(trunk, ys): r.y = snap(y_)
        # ---- draw ----
        simple_ext = 0.0
        sfig = {}
        for r in rows:
            if r.kind == "simple" and r.nodes[0].end:
                fg = Fig(); fg.wire(0, 0, sg * 2.54, 0, r.net); self.term(fg, r.net, sg * 2.54, 0, s); sfig[id(r)] = fg
        k = 0
        while k < len(rows):                # ground pins: neighbours are joined and share one symbol
            if rows[k].kind != "gnd": k += 1; continue
            j = k
            while j + 1 < len(rows) and rows[j + 1].kind == "gnd" and rows[j + 1].net == rows[k].net: j += 1
            run, n = rows[k:j + 1], rows[k].net
            st, fg, y0, x1 = self.style(n), Fig(), rows[k].py, sg * 2.54
            for r in run: fg.wire(0, r.py - y0, x1, r.py - y0, n)
            fg.wire(x1, 0, x1, run[-1].py - y0, n)
            below = rows[j + 1].py - run[-1].py if j + 1 < len(rows) else 99
            if below >= (7.62 if st == "gndref" else 5.08) - 1e-6: fg.power(st, self.nm(n), x1, run[-1].py - y0, "D")
            else: fg.power(st, self.nm(n), x1, run[(len(run) - 1) // 2].py - y0, s)
            sfig[id(rows[k])] = fg
            k = j + 1
        if trunk:
            lo = min(min(r.py, r.y) - max([b[2] for b in shapes(r)]) for r in trunk) - 1.5
            hi = max(max(r.py, r.y) + max([b[3] for b in shapes(r)]) for r in trunk) + 1.5
            for r in rows:
                if id(r) in sfig and lo < r.py < hi:
                    bx = sfig[id(r)].bbox(); simple_ext = max(simple_ext, bx[2] if sg > 0 else -bx[0])
        S = snap_up(simple_ext + 1.0) if simple_ext else 0.0
        col_of = {}
        ups = [r for r in trunk if r.y < r.py - 1e-6]
        for r in ups:
            col_of[id(r)] = 1 + max([col_of[id(o)] for o in ups if o.i < r.i and r.y <= o.py + 1.3] + [0])
        downs = [r for r in reversed(trunk) if r.y > r.py + 1e-6]
        for r in downs:
            col_of[id(r)] = 1 + max([col_of[id(o)] for o in downs if o.i > r.i and r.y >= o.py - 1.3] + [0])
        ncol = max(col_of.values(), default=0)
        U0 = S + (2.54 * (ncol + 1) if ncol else 0.0)
        X = lambda r, u: snap(r.px + sg * u)
        for r in rows:
            x0 = snap(r.px)
            if r.kind == "nc": f.nc(x0, r.py)
            elif r.kind == "open": f.ports["open"] = (x0, snap(r.py))
            elif r.kind in ("simple", "gnd"):
                if id(r) in sfig: f.place(sfig[id(r)], x0, r.py)
            elif r.kind == "trunk":
                if id(r) in col_of:
                    xc = X(r, S + 2.54 * col_of[id(r)])
                    f.path([(x0, r.py), (xc, r.py), (xc, r.y)], r.net)
                    start = xc
                else: start = x0
                net = r.net
                nodes = iter(r.nodes)
                for e in r.seq:
                    ax = X(r, U0 + e.u)
                    if e.kind == "pre":
                        f.place(e.fig, ax, r.y); continue
                    f.wire(start, r.y, ax, r.y, net)
                    start = ax
                    if e.kind == "col": continue
                    if e.kind == "stand" and r.grp:
                        yy = r.grp.rows[0].y - 2.54
                        f.wire(ax, r.y, ax, yy, net); f.place(e.fig, ax, yy)
                    else: f.place(e.fig, ax, r.y)
                    if e.thru:
                        start = snap(ax + sg * e.thru)
                        net = [nd for nd in r.nodes if nd.series][[x for x in r.seq if x.thru].index(e)].series[1]
        for c in cols:
            x = X(c.nodes[0].row, U0 + c.u)
            for i, p in enumerate(c.parts):
                na, nb = c.nodes[i], c.nodes[i + 1]
                ya, yb = na.row.y, nb.row.y
                if p is None: f.wire(x, ya, x, yb, na.net)
                else:
                    y1 = snap(ya + (yb - ya - self.span(p)) / 2)
                    f.wire(x, ya, x, y1, na.net)
                    _, y2 = self.part2(f, p, x, y1, "D", na.net)
                    f.wire(x, y2, x, yb, nb.net)
            if c.headfig: f.place(c.headfig, x, c.nodes[0].row.y)
            if c.tailfig: f.place(c.tailfig, x, c.nodes[-1].row.y)

    def top_bottom(self, f, ctx, tops, bots, body):
        a, mine, claimed = ctx.a, ctx.mine, ctx.claimed
        xc = (body[0] + body[2]) / 2
        # bottom pins: grounds are joined to one symbol
        gnds = [g for g in bots if not g.nc and self.style(g.net) in ("gnd", "gndref") and not (ctx.open is not None and ctx.open in g.nums)]
        for n in {g.net for g in gnds}:
            gg = [g for g in gnds if g.net == n]
            y = -gg[0].y
            if len(gg) > 1: f.wire(gg[0].x, y, gg[-1].x, y, n)
            mid = min(gg, key=lambda g: abs(g.x - (gg[0].x + gg[-1].x) / 2))
            self.term(f, n, mid.x, y, "D")
        k = 0
        for g in bots:
            x, y = g.x, -g.y
            if g.nc: f.nc(x, y)
            elif ctx.open is not None and ctx.open in g.nums: f.ports["open"] = (snap(x), snap(y))
            elif g not in gnds:
                f.wire(x, y, x, y + 2.54 * (1 + k), g.net)
                if self.style(g.net) == "label": f.label(self.nm(g.net), x, y + 2.54 * (1 + k), "R", False, g.net)
                else: self.term(f, g.net, x, y + 2.54 * (1 + k), "D")
                k += 1
        level = 0
        for g in tops:
            x, y = g.x, -g.y
            if g.nc: f.nc(x, y); continue
            if ctx.open is not None and ctx.open in g.nums: f.ports["open"] = (snap(x), snap(y)); continue
            n = g.net
            hangs = [p for p in mine if p not in claimed and n in self.E(p) and self.style(self.other(p, n)) in ("gnd", "gndref")]
            d = 1 if x >= xc - 1e-6 else -1
            att = {(a, num) for num in g.nums}
            for p in hangs: att |= self.pn(p, n)
            rest = set(map(tuple, self.nets[n])) - att
            if not hangs:
                if self.style(n) == "flag": f.power("flag", self.nm(n), x, y)
                else:
                    h = 2.54 * (1 + level); level += 1
                    f.wire(x, y, x, y - h, n)
                    st = self.style(n)
                    if st in ("glabel", "gndref", "gnd"):
                        f.wire(x, y - h, x + d * 2.54, y - h, n)
                        if st == "glabel": f.label(self.nm(n), x + d * 2.54, y - h, "R" if d > 0 else "L", True, n)
                        else: f.power(st, self.nm(n), x + d * 2.54, y - h, "D")
                    else: f.label(self.nm(n), x, y - h, "R" if d > 0 else "L", False, n)
                continue
            t = Fig(); u = 2.54
            for p in hangs:
                claimed.add(p)
                hf = self.hang_fig([p], n); bx = hf.bbox()
                u = snap_up(u + (-bx[0] if d > 0 else bx[2]))
                t.place(hf, d * u, 0)
                u = u + (bx[2] if d > 0 else -bx[0]) + GAP
            u = snap_up(u)
            t.wire(0, 0, d * (u if rest else u - GAP - (bx[2] if d > 0 else -bx[0])), 0, n)
            if rest:
                if self.style(n) == "flag": t.power("flag", self.nm(n), d * u, 0)
                else: self.term(t, n, d * u, 0, "R" if d > 0 else "L")
            h = 15.24
            while f.hits(t, x, y - h, pad=1.0) and h < 80: h += 2.54
            f.wire(x, y, x, y - h, n)
            f.place(t, x, y - h)

    # ------------------------------------------------------------------ loose figures
    def bank_fig(self, rs):
        """Parallel parts between the same two nets: one rail on top, one below."""
        f = Fig()
        e = self.E(rs[0])
        rank = lambda n: 0 if self.style(n) in ("gnd", "gndref") else 2 if self.supply(n) else 1
        top, bot = (e[0], e[1]) if rank(e[0]) >= rank(e[1]) else (e[1], e[0])
        x, xs = 0.0, []
        for r in rs:
            l, rt = self.vext(r)
            x = snap_up(x + l) if xs else 0.0
            _, yb = self.part2(f, r, x, 0, "D", top)
            xs.append(x); x += rt + GAP
        if self.style(top) == "flag":
            f.wire(xs[0], 0, xs[0], -2.54, top); f.power("flag", self.nm(top), xs[0], -2.54)
        else:
            f.wire(xs[0], 0, xs[0] - 2.54, 0, top); self.term(f, top, xs[0] - 2.54, 0, "L")
        if len(xs) > 1: f.wire(xs[0], 0, xs[-1], 0, top)
        if self.style(bot) in ("gnd", "gndref"):
            if len(xs) > 2:
                f.wire(xs[0], yb, xs[-1], yb, bot); self.term(f, bot, xs[0], yb, "D")
            else:
                for x in xs: self.term(f, bot, x, yb, "D")
        else:
            if len(xs) > 1: f.wire(xs[0], yb, xs[-1], yb, bot)
            f.wire(xs[0], yb, xs[0] - 2.54, yb, bot); self.term(f, bot, xs[0] - 2.54, yb, "L")
        return f

    def padlist_fig(self, rs):
        """Wire pads and test points, one per line: the pad, what it is, and the net it is on."""
        f = Fig(); y = 0.0
        wtxt = max(tw(r) + 1.2 + tw(self.comps[r]["value"]) for r in rs)
        for r in rs:
            n = self.groups[r][0].net
            t = Fig()
            self.pad(t, r, 0, 0, "L", "none")
            it = t.items[-1]
            st = self.style(n)
            t.wire(0, 0, 5.08, 0, n)
            if st in ("gnd", "gndref"): self.term(t, n, 5.08, 0, "D")
            else: t.label(self.nm(n), 5.08, 0, "R", st in ("glabel", "flag"), n)
            bx = t.bbox()
            y = snap_up(y - bx[1]) if y else 0.0
            # text to the left of the pad, on one line
            xb = [b for b in it["boxes"] if b[4] == "sym"][0][0]
            ref, value = r, self.comps[r]["value"]
            x0 = xb - 1.2 - wtxt
            it["pts"][1] = (x0 + tw(ref) / 2, 0.0); it["pts"][2] = (x0 + tw(ref) + 1.2 + tw(value) / 2, 0.0)
            it["show"] = [True, True]
            it["boxes"] += [(x0, -.85, x0 + tw(ref), .85, "text"), (x0 + tw(ref) + 1.2, -.85, x0 + tw(ref) + 1.2 + tw(value), .85, "text")]
            f.place(t, 0, y)
            y += max(bx[3], 1.0) + 1.6
        return f

    # ------------------------------------------------------------------ Kelvin filter under a shunt
    def find_kelvin(self, rs):
        """Parts of the RC filter between a sense resistor and the pins that measure it:
        (pos net, neg net, {role: ref}) with roles ra, rb (series), cd (across), ca, cb (to ground), or None."""
        a, b = self.E(rs)
        pos = neg = None
        for k in self.cons.get("kelvin", {}).values():
            if k["resistor"] == rs: pos, neg = k["pos"], k["neg"]
        two = lambda n1, n2: next((r for r in self.small if r != rs and set(self.E(r)) == {n1, n2} and r not in self.used), None)
        if pos is None:
            for c in self.small:
                if self.lib(c) != "Device:C": continue
                p, n = self.E(c)
                if not (self.signal(p) and self.signal(n)): continue
                for p_, n_ in ((p, n), (n, p)):
                    if two(a, p_) and two(b, n_): pos, neg = p_, n_
        if pos is None: return None
        if two(a, pos) and two(b, neg): na, nb = pos, neg
        elif two(a, neg) and two(b, pos): na, nb = neg, pos
        else: return None
        roles = dict(ra=two(a, na), rb=two(b, nb), cd=two(na, nb), ca=two(na, "GND"), cb=two(nb, "GND"))
        for k in ("ca", "cb"):
            if roles[k] in (roles["ra"], roles["rb"]): roles[k] = None
        return na, nb, {k: v for k, v in roles.items() if v}

    def kelvin_fig(self, rs, x1, x2, k):
        """Filter below a shunt lying on y = 0 with its ends at x1 (left) and x2: a resistor down from each end,
        a capacitor across, a capacitor from each side to ground, and the two sense nets named."""
        f = Fig()
        a, b = self.E(rs)
        na, nb, roles = k
        xl, xr = x1 - 5.08, x2 + 5.08
        nets = self.kel_nets
        la, lb = nets
        f.wire(xl, 0, xl, 2.54, la); _, y = self.part2(f, roles["ra"], xl, 2.54, "D", la, "left")
        f.wire(xr, 0, xr, 2.54, lb); self.part2(f, roles["rb"], xr, 2.54, "D", lb, "right")
        y1 = snap(y + 2.54)
        f.wire(xl, y, xl, y1, na); f.wire(xr, y, xr, y1, nb)
        if "cd" in roles:
            sp = self.span(roles["cd"]); xa = snap(xl + (xr - xl - sp) / 2)
            f.wire(xl, y1, xa, y1, na); x_, _ = self.part2(f, roles["cd"], xa, y1, "R", na, "above"); f.wire(x_, y1, xr, y1, nb)
        f.wire(xl, y1, xl - 2.54, y1, na); f.label(self.nm(na), xl - 2.54, y1, "L", False, na)
        f.wire(xr, y1, xr + 2.54, y1, nb); f.label(self.nm(nb), xr + 2.54, y1, "R", False, nb)
        if "ca" in roles: f.place(self.hang_fig_side(roles["ca"], na, "left"), xl, y1)
        if "cb" in roles: f.place(self.hang_fig_side(roles["cb"], nb, "right"), xr, y1)
        return f

    def hang_fig_side(self, r, net, tpos):
        f = Fig()
        f.wire(0, 0, 0, 2.54, net)
        _, y = self.part2(f, r, 0, 2.54, "D", net, tpos)
        self.term(f, self.other(r, net), 0, y, "D")
        return f

    # ------------------------------------------------------------------ four-switch power stage
    def bridge4_parts(self, qa, t):
        qb = t["q_out"]
        parts = {qb, t["inductor"], t["rin"], t["rout"], *t["cin"], *t["cout"]}
        gates = {}
        for qq in (qa, qb):
            for g in self.groups[qq]:
                if g.names[0].startswith("G"):
                    for r in self.small:
                        if g.net in self.E(r) and r not in parts: gates[(qq, g.names[0])] = r; parts.add(r)
        t["_gates"] = gates
        for rs in (t["rin"], t["rout"]):
            k = self.find_kelvin(rs)
            if k: parts.update(k[2].values())
        return parts

    def bridge4_fig(self, qa, t):
        """Four-switch buck-boost as a power path, left to right: input shunt with its Kelvin filter, input capacitors,
        input half bridge, inductor, output half bridge, output capacitors, output shunt."""
        f = Fig()
        qb = t["q_out"]
        pin = lambda qq, nm, u: next(p for p in self.pins_of[qq] if p["name"] == nm and p["unit"] == u)
        net = lambda qq, nm, u: self.pinnet[(qq, pin(qq, nm, u)["num"])]
        n_in, n_out, n_sw1, n_sw2 = net(qa, "D1", 1), net(qb, "D1", 1), net(qa, "SW", 1), net(qb, "SW", 1)
        ya, yb = 22.86, 38.1

        def shunt(rs, x, left_net):
            """Shunt with its first end at x on the rail; returns the x where the rail is free again."""
            k = self.find_kelvin(rs)
            if k: x = snap_up(x + 17.78)
            x2, _ = self.part2(f, rs, x, 0, "R", left_net)
            if k:
                self.kel_nets = (left_net, self.other(rs, left_net))
                kk = k if self.find_side(k, rs, left_net) else (k[1], k[0], dict(ra=k[2]["rb"], rb=k[2]["ra"], cd=k[2].get("cd"), ca=k[2].get("cb"), cb=k[2].get("ca")))
                kk = (kk[0], kk[1], {a__: b__ for a__, b__ in kk[2].items() if b__})
                f.place(self.kelvin_fig(rs, x, x2, kk))
                return x, x2, snap_up(x2 + 5.08 + 17.78)
            return x, x2, x2 + 2.54

        def caps(rs, x, n):
            for r in rs:
                hf = self.hang_fig([r], n); bx = hf.bbox()
                x = snap_up(x - bx[0]); f.place(hf, x, 0); x += bx[2] + GAP
            return x

        def half(qq, x, mir):
            """Both switches of one half bridge, drain on the rail, with their gate resistors. x: the gate side of the body."""
            sg = -1 if mir else 1
            out = {}
            for u, y in ((1, ya), (2, yb)):
                tx = x + sg * 1.3
                w1, w2 = tw(qq + "AB"[u - 1]), tw(self.comps[qq]["value"])
                texts = {"ref": (tx, y - 6.9), "val": (tx, y - 5.1)} if u == 1 else {}
                c = self.comps[qq]; lib, name = c["lib"].split(":")
                tn = {p["num"]: self.pinnet.get((qq, p["num"])) for p in self.pins_of[qq]}
                self.used.add(qq)
                pins = f.sym(lib, name, qq, c["value"], x, y, 0, mir, u, texts, c["footprint"], c["fields"], tn)
                for p in self.pins_of[qq]:
                    if p["unit"] == u: out[(p["name"], u)] = pins[p["num"]]
            for gname, u in (("G1", 1), ("G2", 2)):
                gx, gy = out[(gname, u)]
                gn = net(qq, gname, u)
                r = t["_gates"].get((qq, gname))
                if r:
                    x1 = gx - sg * 2.54
                    f.wire(gx, gy, x1, gy, gn)
                    x2, _ = self.part2(f, r, x1, gy, "L" if sg > 0 else "R", gn)
                    dn = self.other(r, gn)
                    f.wire(x2, gy, x2 - sg * 2.54, gy, dn); f.label(self.nm(dn), x2 - sg * 2.54, gy, "L" if sg > 0 else "R", False, dn)
                else: f.label(self.nm(gn), gx, gy, "L" if sg > 0 else "R", False, gn)
            return out

        # input side
        n_src = self.other(t["rin"], n_in)
        f.label(self.nm(n_src), 0, 0, "L", self.style(n_src) != "label", n_src)
        xs1, xs2, x = shunt(t["rin"], 2.54, n_src)
        f.wire(0, 0, xs1, 0, n_src)
        f.label(self.nm(n_in), x - 15.24, 0, "R", False, n_in)
        x = caps(t["cin"], x, n_in)
        gate_w = 2.54 + 7.62 + 2.54 + max(tw(self.nm(net(qq, g, u))) for qq in (qa, qb) for g, u in (("G1", 1), ("G2", 2))) + 6
        qx = snap_up(x + gate_w + 6.35)
        A = half(qa, qx, False)
        xd, xsw = snap(qx + 8.89), snap(qx + 11.43)
        f.wire(xs2, 0, xd, 0, n_in)
        f.path([(xd, 0), (xd, A[("D1", 1)][1]), A[("D1", 1)]], n_in)
        ysw = A[("SW", 1)][1]
        f.path([A[("SW", 1)], (xsw, ysw), (xsw, A[("SW", 2)][1]), A[("SW", 2)]], n_sw1)
        f.wire(A[("S2", 2)][0], A[("S2", 2)][1], xd, A[("S2", 2)][1], "GND"); f.wire(xd, A[("S2", 2)][1], xd, A[("S2", 2)][1] + 2.54, "GND")
        self.term(f, "GND", xd, A[("S2", 2)][1] + 2.54, "D")
        # inductor
        xl = snap_up(xsw + tw(self.nm(n_sw1)) + 5.08)
        f.label(self.nm(n_sw1), xsw + 1.27, ysw, "R", False, n_sw1)
        x2, _ = self.part2(f, t["inductor"], xl, ysw, "R", n_sw1)
        f.wire(xsw, ysw, xl, ysw, n_sw1)
        xsw2 = snap_up(x2 + tw(self.nm(n_sw2)) + 6.35)
        f.label(self.nm(n_sw2), x2 + 3.81, ysw, "R", False, n_sw2)
        # output half bridge, mirrored
        qx2 = snap(xsw2 + 11.43)
        Bq = half(qb, qx2, True)
        xd2 = snap(qx2 - 8.89)
        f.path([(x2, ysw), (xsw2, ysw), Bq[("SW", 1)]], n_sw2)
        f.path([(xsw2, ysw), (xsw2, Bq[("SW", 2)][1]), Bq[("SW", 2)]], n_sw2)
        f.path([Bq[("D1", 1)], (xd2, Bq[("D1", 1)][1]), (xd2, 0)], n_out)
        f.wire(Bq[("S2", 2)][0], Bq[("S2", 2)][1], xd2, Bq[("S2", 2)][1], "GND"); f.wire(xd2, Bq[("S2", 2)][1], xd2, Bq[("S2", 2)][1] + 2.54, "GND")
        self.term(f, "GND", xd2, Bq[("S2", 2)][1] + 2.54, "D")
        # output side
        x = snap_up(qx2 + 6.35 + gate_w)
        f.label(self.nm(n_out), x - tw(self.nm(n_out)) - 2.54, 0, "R", False, n_out)
        x = caps(t["cout"], x, n_out)
        n_dst = self.other(t["rout"], n_out)
        xo1, xo2, x = shunt(t["rout"], x + 2.54, n_out)
        f.wire(xd2, 0, xo1, 0, n_out)
        f.wire(xo2, 0, x, 0, n_dst)
        self.term(f, n_dst, x, 0, "R")
        for r in t["_parts"]:
            if r not in self.used: self.leftover.append(r)
        return f

    def find_side(self, k, rs, left_net):
        """True when the first filter net of k belongs to the left end of the shunt."""
        return left_net in self.E(k[2]["ra"])

    # ------------------------------------------------------------------ power path
    def path_nodes(self, t):
        """Nets along a path, in order: before the first element, between elements, after the last."""
        out = []
        prev = None
        for e in t["_elems"]:
            gs = self.groups[e.ref]
            if e.io:
                a, b = self.pin_group(e.ref, e.io[0]).net, self.pin_group(e.ref, e.io[1]).net
            elif len(gs) == 1: a = b = gs[0].net
            else:
                a, b = self.E(e.ref)
                if prev is not None and b == prev: a, b = b, a
                elif prev is None:
                    nxt = t["_elems"][t["_elems"].index(e) + 1] if len(t["_elems"]) > 1 else None
                    if nxt and a in [g.net for g in self.groups[nxt.ref]]: a, b = b, a
            e.a, e.b = a, b
            if not out: out.append(a)
            if len(gs) > 1: out.append(b)
            prev = b
        t["_nodes"] = out
        return out

    def path_kelvin(self, t):
        out = set()
        for e in t["_elems"]:
            if len(self.groups[e.ref]) == 2:
                k = self.find_kelvin(e.ref)
                if k: out.update(k[2].values())
        return out

    def path_fig(self, key, t):
        """A power path on y = 0, left to right through the elements named in the block. Pads end it; a part with the
        path's pins side by side hangs under it; what touches a node hangs from that node; a chain of parts from one
        node to a later one arcs over the path; a Kelvin filter sits under its shunt."""
        f = Fig()
        nodes = self.path_nodes(t)
        mine = self.mine(key)
        claimed = set()
        elems = t["_elems"]
        x = 0.0
        first = elems[0]
        nodex = {}                          # node index -> [start x, end x]
        gates = []                          # (gate net, tip, element body box, in x, out x, in net, out net)
        def chain_from(p, n):
            """Follow a part from net n through private nets. Returns (parts, end net)."""
            ch = [p]; m = self.other(p, n)
            while self.signal(m) and m not in nodes and len(self.nets[m]) == 2:
                nxt = [r for r, _ in self.nets[m] if r != ch[-1] and r in mine and r not in claimed and r not in ch]
                if not nxt: break
                ch.append(nxt[0]); m = self.other(nxt[0], m)
            return ch, m
        last = len(nodes) - 1
        own = {e.ref for e in elems} | set(mine) | set(self.path_kelvin(t)) | set(t.get("dock", {}).values())
        arcs = []
        gate_nets = set()
        for e in elems:
            if e.io: gate_nets |= {g.net for g in self.groups[e.ref] if not g.nc} - {self.pin_group(e.ref, e.io[0]).net, self.pin_group(e.ref, e.io[1]).net}
        def hang_node(ni, x):
            """What hangs on node ni is drawn from x on. Returns the x where the path is free again."""
            n = nodes[ni]; start = nodex[ni][0]
            if 0 < ni < last and any(r not in own for r, _ in self.nets[n]):
                f.label(self.nm(n), start + 1.27, 0, "R", self.style(n) != "label", n)
                x = max(x, snap_up(start + 2.54 + tw(self.nm(n)) + (3.2 if self.style(n) != "label" else 0)))
            x = max(x, start + 2.54)
            for p in mine:
                if p in claimed or n not in self.E(p) or any(n2 in gate_nets for n2 in self.E(p)): continue
                ch, m = chain_from(p, n)
                claimed.update(ch)
                if m in nodes and m != n:
                    arcs.append((ni, nodes.index(m), ch)); continue
                hf = self.hang_fig(ch, n); bx = hf.bbox()
                x = snap_up(x - bx[0])
                while f.hits(hf, x, 0, pad=1.0): x += 2.54
                f.place(hf, x, 0); nodex[ni][2] = x; x = snap_up(x + bx[2] + GAP)
            return x
        for i, e in enumerate(elems):
            gs = self.groups[e.ref]
            if len(gs) == 1:
                if i == 0: self.pad(f, e.ref, 0, 0, "L", "above"); nodex[0] = [0.0, None, 0.0]; x = hang_node(0, x)
                else: e.endpad = True
                continue
            if i == 0:
                nodex[0] = [0.0, None, 0.0]; f.label(self.nm(e.a), 0, 0, "L", self.style(e.a) != "label", e.a); x = hang_node(0, x)
            ni = 1 + sum(1 for e2 in elems[:i] if len(self.groups[e2.ref]) > 1)       # index of the node after this element
            # what hangs from the node before this element is placed first
            if len(gs) == 2:
                k = self.find_kelvin(e.ref)
                x1 = snap_up(x + (17.78 if k else 5.08))
                x2, _ = self.part2(f, e.ref, x1, 0, "R", e.a)
                if k:
                    self.kel_nets = (e.a, e.b)
                    kk = k if self.find_side(k, e.ref, e.a) else (k[1], k[0], dict(ra=k[2]["rb"], rb=k[2]["ra"], cd=k[2].get("cd"), ca=k[2].get("cb"), cb=k[2].get("ca")))
                    kk = (kk[0], kk[1], {a_: b_ for a_, b_ in kk[2].items() if b_})
                    f.place(self.kelvin_fig(e.ref, x1, x2, kk))
                    for r in kk[2].values(): claimed.add(r)
                    nxt = snap_up(x2 + 5.08 + 15.24)
                else: nxt = x2
                e.xin, e.xout = x1, x2
            else:
                gi, go = self.pin_group(e.ref, e.io[0]), self.pin_group(e.ref, e.io[1])
                lib, name = self.lib(e.ref).split(":")
                for ang, mir in ((0, False), (0, True), (270, False), (270, True), (90, False), (90, True)):
                    ax, ay = xf(gi.x, gi.y, ang, mir); bx_, by_ = xf(go.x, go.y, ang, mir)
                    body = sbox(lib, name, 0, 0, ang, mir)
                    inline = abs(ay - by_) < 1e-6 and ax < bx_ and ax <= body[0] and bx_ >= body[2]
                    under = abs(ay - by_) < 1e-6 and ax < bx_ and ay <= body[1]
                    if inline or under: break
                else: raise SystemExit(f"path: {e.ref} cannot be drawn with {e.io[0]} left of {e.io[1]}")
                others = [g for g in gs if g is not gi and g is not go and not g.nc]
                gate_parts = {g.nets if False else g.net: [p for p in mine if g.net in self.E(p)] for g in others}
                pull_in = [p for g in others for p in gate_parts[g.net] if self.other(p, g.net) == e.a]
                room = sum(sum(self.vext(p)) + 2.54 for p in pull_in)
                x1 = snap_up(x + 5.08 + room)
                ox, oy = snap(x1 - ax), snap((2.54 if under else 0) - ay)
                b = sbox(lib, name, ox, oy, ang, mir)
                ref, value = e.ref, self.comps[e.ref]["value"]
                if under: texts = {"ref": (b[2] + .9 + tw(ref) / 2, (b[1] + b[3]) / 2 - 1.2), "val": (b[2] + .9 + tw(value) / 2, (b[1] + b[3]) / 2 + 1.2)}
                else: texts = {"ref": ((b[0] + b[2]) / 2, b[1] - 3.1), "val": ((b[0] + b[2]) / 2, b[1] - 1.25)}
                pins = self.put(f, e.ref, ox, oy, ang, mir, texts=texts)
                x2 = snap(ox + bx_)
                if under: f.wire(x1, 0, x1, 2.54, e.a); f.wire(x2, 0, x2, 2.54, e.b)
                e.xin, e.xout = x1, x2
                nxt = max(x2, snap_up(b[2] + .9 + max(tw(ref), tw(value)) + 1.27)) if under else x2
                for g in others:
                    tip = pins[g.nums[0]]
                    dock = t.get("dock", {}).get(f"{e.ref}.{g.names[0]}")
                    if dock:
                        qg = next(gg for gg in self.groups[dock] if gg.net == g.net)
                        sub = self.anchor_fig(dock, qg.nums[0])
                        px, py = sub.ports["open"]
                        e.dock = (sub, tip, px, py, g.net)
                        continue
                    parts = [p for p in gate_parts[g.net] if p not in claimed]
                    yb = snap(tip[1] + 2.54)
                    xs = [tip[0]]
                    f.wire(tip[0], tip[1], tip[0], yb, g.net)
                    xl = x1
                    for p in parts:
                        if self.other(p, g.net) != e.a: continue
                        claimed.add(p); l, r_ = self.vext(p)
                        xl = snap(xl - r_ - 2.0)
                        y_, _y = yb - self.span(p), yb
                        self.part2(f, p, xl, y_, "D", e.a); f.wire(xl, 0, xl, y_, e.a)
                        xs.append(xl); xl -= l
                    xr = snap_up(max(b[2] + .9 + max(tw(ref), tw(value)) + 2.5, x2 + 3.81) if under else x2 + 3.81)
                    for p in parts:
                        if self.other(p, g.net) != e.b or p in claimed: continue
                        claimed.add(p); l, r_ = self.vext(p)
                        xr = snap_up(xr + l)
                        y_ = yb - self.span(p)
                        self.part2(f, p, xr, y_, "D", e.b); f.wire(xr, 0, xr, y_, e.b)
                        xs.append(xr); xr += r_ + GAP; nxt = max(nxt, xr)
                    xg = tip[0]
                    for p in parts:
                        if p in claimed: continue
                        claimed.add(p)
                        _, y_ = self.part2(f, p, xg, yb, "D", g.net)
                        self.term(f, self.other(p, g.net), xg, y_, "D")
                        xs.append(xg); xg = snap_up(xg + sum(self.vext(p)) + GAP)
                    f.wire(min(xs), yb, max(xs), yb, g.net)
            nodex[ni - 1][1] = e.xin
            nodex[ni] = [e.xout, None, e.xout]
            f.wire(nodex[ni - 1][0], 0, e.xin, 0, e.a)
            x = hang_node(ni, nxt)
        # ---- the end of the path: wire pads and test points stand on it, then the net is named ----
        n = nodes[last]
        xe = nodex[last][2]
        pads = [e.ref for e in elems if getattr(e, "endpad", False)]
        pads += [r for r, _ in self.nets[n] if r in self.refset and len(self.groups[r]) == 1 and r not in self.used and r not in self.tkey]
        for r in pads:
            pf = Fig(); self.pad(pf, r, 0, 0, "U", "above"); bx = pf.bbox()
            x = snap_up(max(x, xe + 2.54) - bx[0])
            while f.hits(pf, x, 0, pad=1.0): x += 2.54
            f.place(pf, x, 0); xe = x; x = snap_up(x + bx[2] + GAP)
        xe = snap_up(max(xe, x - GAP) + 2.54)
        if self.style(n) in ("gnd", "gndref"):
            f.wire(xe, 0, xe, 2.54, n); self.term(f, n, xe, 2.54, "D")
        elif any(r not in own and r not in pads for r, _ in self.nets[n]): self.term(f, n, xe, 0, "R")
        else: xe -= 2.54
        f.wire(nodex[last][0], 0, xe, 0, n)
        for na, nb, ch in arcs:
            if na > nb: na, nb = nb, na; ch = ch[::-1]
            xa, xb = nodex[na][1], nodex[nb][0]
            n1 = nodes[na]
            for h in (10.16, 12.7, 15.24, 17.78, 20.32, 25.4):
                af = Fig()
                w = sum(self.span(p) for p in ch) + 5.08 * (len(ch) - 1)
                xs = snap(xa + (xb - xa - w) / 2)
                af.path([(xa, 0), (xa, -h), (xs, -h)], n1)
                net = n1
                for p in ch:
                    x2, _ = self.part2(af, p, xs, -h, "R", net)
                    self.used.discard(p); self.used.discard((p, 1))
                    net = self.other(p, net)
                    xs = x2 + 5.08 if p is not ch[-1] else x2
                    if p is not ch[-1]: af.wire(x2, -h, xs, -h, net)
                af.path([(xs, -h), (xb, -h), (xb, 0)], net)
                body = Fig(); body.items = [it for it in af.items if not (it["kind"] == "wire" and it["pts"][0][0] == it["pts"][1][0])]
                if not f.hits(body, 0, 0, pad=0.8) or h > 25: break
            for p in ch: self.used.add(p); self.used.add((p, 1))
            f.place(af)
        for e in elems:
            if getattr(e, "dock", None):
                sub, tip, px, py, n = e.dock
                L = 5.08
                while f.hits(sub, tip[0] - px, tip[1] + L - py, pad=1.0) and L < 60: L += 2.54
                f.wire(tip[0], tip[1], tip[0], tip[1] + L, n)
                f.place(sub, tip[0] - px, tip[1] + L - py)
        self.leftover += [r for r in mine if r not in claimed]
        return f

    # ------------------------------------------------------------------ sections and the page
    def sections(self):
        secs = []
        for r in self.refs:
            t = self.comps[r].get("section") or self.block
            if t not in [s.title for s in secs]: secs.append(O(title=t, refs=[], figs=[]))
            next(s for s in secs if s.title == t).refs.append(r)
        sec_of = {r: s for s in secs for r in s.refs}
        # templates first (they own their parts), then every other part with three or more pins
        for a, t in self.tdraw.items():
            if t["kind"] == "bridge4": t["_fig"] = self.bridge4_fig(a, t)
            elif t["kind"] == "path": t["_fig"] = self.path_fig(a, t)
        for s in secs:
            for r in s.refs:
                if r in self.tdraw and "_fig" in self.tdraw[r]:
                    s.figs.append(self.tdraw[r].pop("_fig"))
                elif r in self.anchors and r not in self.used and r not in self.dock and r not in self.tkey:
                    s.figs.append(self.anchor_fig(r))
        for s in secs:                      # transistors that found no wire to sit on
            for r in s.refs:
                if r in self.anchors and r not in self.used: s.figs.append(self.anchor_fig(r))
        # what is left: banks of parallel parts, then single parts, then pads
        for s in secs:
            rest = [r for r in s.refs if r in self.small and r not in self.used]
            banks = {}
            for r in rest: banks.setdefault(frozenset(self.E(r)), []).append(r)
            for rs in banks.values(): s.figs.append(self.bank_fig(rs))
            pads = [r for r in s.refs if r in self.pads and r not in self.used]
            if pads: s.figs.append(self.padlist_fig(pads))
        return [s for s in secs if s.figs]

    def section_fig(self, s, wmax):
        """Title, notes, then the figures of the section left to right, wrapping at wmax."""
        f = Fig()
        notes = self.cons.get("notes", {}).get(self.block + "|" + (s.title if s.title != self.block else ""), [])
        f.text(s.title, 0, 0, 2.0, bold=True)
        y = 2.2
        if notes:
            wn = max([100.0] + [fg.bbox()[2] - fg.bbox()[0] for fg in s.figs])
            lines = []
            for ln in notes:                # wrap to the width of the drawing below
                cur = ""
                for word in ln.split(" "):
                    if cur and tw(cur + " " + word) > wn: lines.append(cur); cur = word
                    else: cur = (cur + " " + word).strip()
                lines.append(cur)
            notes = lines
            txt = "\n".join(notes)
            y += len(notes) * 1.27 * 1.62 + 0.6
            f.text(txt, 0, y - 0.4, 1.27)
            y += 1.0
        y += 2.54
        y0 = y
        x, rowh = 0.0, 0.0
        for fg in s.figs:
            bx = fg.bbox(); w, h = bx[2] - bx[0], bx[3] - bx[1]
            if x > 0 and x + w > wmax: x, y, rowh = 0.0, y + rowh + 7.62, 0.0
            f.place(fg, snap_up(x - bx[0]), snap_up(y - bx[1]))
            x += w + 10.16; rowh = max(rowh, h)
        f.top = y0                          # the drawing starts here; above it are only the title and the notes
        return f


def draw_block(sheet, block, comps, nets, nc, cons, order, out_path):
    B = Blk(block, comps, nets, nc, cons, order)
    secs = B.sections()
    missing = [r for r in B.refs if r not in B.used]
    if missing: raise SystemExit(f"{block}: not drawn: {missing}")
    figs = [B.section_fig(s, 330.0) for s in secs]
    sizes = [(fg.bbox()[2] - fg.bbox()[0], fg.bbox()[3] - fg.bbox()[1]) for fg in figs]
    prof = []                               # per section: how far down it reaches to the right of a given x
    for fg in figs:
        bx = fg.bbox()
        arr = sorted(((b_[2] - bx[0], b_[3] - bx[1]) for b_ in fg.boxes()), reverse=True)
        xs, run, m = [], [], 0.0
        for x2, y2 in arr:
            m = max(m, y2); xs.append(-x2); run.append(m)
        prof.append((xs, run))
    def below(i, t):
        xs, run = prof[i]
        k = bisect.bisect_left(xs, -t)
        return run[k - 1] if k else 0.0
    GX, GY, X0, Y0 = 15.24, 12.7, 15.24, 24.13
    TBW, TBH = 122, 48                      # the title block in the bottom right corner
    MINW, MINH = 180, 120
    n = len(sizes)
    def place(order, wpage, wider=0):
        """Sections in rows of at most wpage, in the given order, on a page wider than they need by `wider`.
        Returns the page size and where each section goes."""
        rows, x = [[]], 0.0
        for i in order:
            if rows[-1] and x + sizes[i][0] > wpage: rows.append([]); x = 0.0
            rows[-1].append(i); x += sizes[i][0] + GX
        W = max(sum(sizes[i][0] for i in r) + GX * (len(r) - 1) for r in rows)
        H = sum(max(sizes[i][1] for i in r) for r in rows) + GY * (len(rows) - 1)
        Wp = max(MINW, math.ceil((X0 + W + 14) / 5) * 5) + wider; Hp = max(MINH, math.ceil((Y0 + H + 14) / 5) * 5)
        pos, y = [], Y0
        for r in rows:
            wr = sum(sizes[i][0] for i in r) + GX * (len(r) - 1)
            gap = GX + (min((Wp - 2 * X0 - wr) / (len(r) - 1), 25) if len(r) > 1 else 0)      # spread a row over the page width
            x = X0
            for i in r:
                pos.append((i, x, y)); x += sizes[i][0] + gap
            y += max(sizes[i][1] for i in r) + GY
        low = max(y + below(i, Wp - TBW - 3 - x) for i, x, y in pos)       # what is above the title block must end above it
        Hp = max(Hp, math.ceil((low + TBH + 3) / 5) * 5)
        return Wp, Hp, pos
    orders = itertools.permutations(range(n)) if n <= 7 else [tuple(range(n))]
    wmin, wtot = max(w for w, h in sizes), sum(w for w, h in sizes) + GX * (n - 1)
    widths = sorted({wmin + 0.1} | {wmin + 10.0 * k for k in range(1, int((wtot - wmin) / 10) + 2)})
    best = None
    for order in orders:
        inv = sum(1 for i in range(n) for j in range(i + 1, n) if order[i] > order[j])
        for wpage in widths:
            for wider in (0, 15, 30, 45):   # a wider page can keep the drawing clear of the title block
                Wp, Hp, pos = place(order, wpage, wider)
                score = Wp * Hp * (1 + 0.4 * abs(math.log((Wp / Hp) / 1.45))) * (1 + 0.015 * inv)
                if best is None or score < best[0] - 1e-6: best = (score, Wp, Hp, pos)
    _, Wp, Hp, pos = best
    page = Fig()
    page.text(sheet.title, X0, 16.5, 3.0, bold=True)
    for i, x, y in pos:
        bx = figs[i].bbox()
        page.place(figs[i], snap_up(x - bx[0]), snap_up(y - bx[1]))
    probs, counts = lint(page, block)
    w, h = sheet.write(page, out_path, Wp, Hp)
    return probs, counts, (w, h)


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
    report = []
    for i, b in enumerate(blocks):
        fn = b.lower().replace(" ", "_") + ".kicad_sch"
        s = Sheet(b, project, root_uuid, b, i + 2)
        probs, counts, size = draw_block(s, b, comps, nets, nc, cons, order, f"{out}/{fn}")
        report += probs
        print(f"{b}: page {size[0]} x {size[1]} mm, clutter {dict(counts) or 'none'}")
        x, y = 30 + (i % 3) * 80, 40 + (i // 3) * 50
        root.append(
            f'(sheet (at {x} {y}) (size 60 30) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (stroke (width 0.1524) (type solid)) '
            f'(fill (color 0 0 0 0)) (uuid {q(s.uuid)}) '
            f'(property "Sheetname" {q(b)} (at {x} {y - 0.7} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) '
            f'(property "Sheetfile" {q(fn)} (at {x} {y + 30.6} 0) (effects (font (size 1.27 1.27)) (justify left top))) '
            f'(instances (project {q(project)} (path {q("/" + root_uuid)} (page {q(i + 2)})))))')
    root.append('(sheet_instances (path "/" (page "1"))) (embedded_fonts no))')
    open(f"{out}/{project}.kicad_sch", "w").write("\n".join(root) + "\n")
    open(f"{out}/lint.txt", "w").write("\n".join(report) + "\n")
    shorts = [p for p in report if p.startswith("SHORT")]
    for p in shorts[:20]: print("  " + p)
    print("wrote", len(blocks), "sheets to", out, f"({len(report)} lint findings in lint.txt)")

if __name__ == "__main__":
    main(*sys.argv[1:4])
