"""Composition of one sheet: ICs with their support parts (clusters), free groups of small parts, sections with a title
and a frame, and the page they are packed on.

A cluster is drawn on a scratch sheet at the origin, measured, and drawn again where it is wanted, so every item has an
exact size before the page is packed.
"""
import math, os
from sch import *
from ctx import Ctx, Dp
from parts import PartMixin
from lanes import LaneMixin, Row, Lane, Node, Att, STRETCH_MIN
import symlib
import templates

TB_W, TB_H = 112.0, 34.0            # the title block KiCad draws bottom right, with its clearance
EDGE = 16.0                         # content stays this far from the paper edge
SEC_GAP = 7.62                      # between sections on a page
ITEM_GAP = 7.62                     # between items of a section
LINK_LEN = 0.0                     # wire between two linked ICs, between the ends of their stubs
COLUMN_BONUS = 0.97                # page area one may pay for frames that line up in columns
INV_PENALTY = 0.015                 # extra page area one may pay per section that stands before one that comes earlier in the block file
FRAME_PAD = 3.81
TITLE_H = 7.0                       # room for the section title above its items


class Item:
    """Something drawn once: an IC cluster, a bank, a pad list. `fn(S)` draws it at the origin of S."""
    def __init__(self, name, fn, box, kind="free", order=0):
        self.name, self.fn, self.box, self.kind, self.order = name, fn, box, kind, order
        self.w, self.h = box[2] - box[0], box[3] - box[1]
        self.x = self.y = 0.0


class Block(Ctx, PartMixin, LaneMixin, templates.TemplateMixin):
    def __init__(self, block, comps, nets, nc, cons, order, idx, project, root_uuid):
        self.plans = {}
        Ctx.__init__(self, block, comps, nets, nc, cons, order)
        self.idx, self.project, self.root_uuid = idx, project, root_uuid
        self.order = order
        self.plans = {}                         # IC -> symbol plan: pins moved to the lanes that serve them
        self._planned, self._pin0 = set(), {}
        self.link_nets, self.stubs, self._cur = set(), {}, None     # nets drawn as one wire between two linked ICs, where their stubs end
        self.skip = set()                       # anchors drawn by another anchor's template
        for a, t in cons.get("draw", {}).items():
            if a in self.refset and t.get("kind") in ("bridge4", "fetpair"):
                self.skip.add(t["q_out"])

    # ------------------------------------------------------------------ scratch sheets
    def scratch(self):
        return Sheet(self.block, self.project, self.root_uuid, self.block)

    def measure(self, fn):
        S = self.scratch()
        fn(S)
        return S.bbox()

    def units(self, a):
        return sorted({d.unit for d in self.dp[a] if d.unit} or {1})

    # ------------------------------------------------------------------ an IC with everything on its pins
    def draw_anchor(self, S, a):
        t = self.cons.get("draw", {}).get(a, {})
        if t.get("kind") == "bridge4":
            return self.draw_bridge4(S, a)
        if t.get("kind") == "fetpair":
            return self.draw_fetpair(S, a)
        self.plan_stretch(a)
        best = None                                          # where the reference and value go: the first place that is clear
        for tpos in (("left", 0.0), ("left", -2.54), ("right", 0.0), ("right", -2.54), ("center", 0.0), ("center", -2.54), ("left", -5.08)):
            T = self.scratch()
            self._draw_anchor(T, a, tpos)
            n = text_clashes(T, a)
            if best is None or n < best[0]: best = (n, tpos)
            if n == 0: break
        return self._draw_anchor(S, a, best[1])

    def _draw_anchor(self, S, a, tpos):
        self._cur = a
        c = self.comps[a]
        lib, name = c["lib"].split(":")
        g = self._geo(a)
        b = g["body"] or (-2.54, -2.54, 2.54, 2.54)
        xl, xr, yt, yb = b[0], b[2], -b[3], -b[1]
        cl = self.claimed(a)
        used = set()
        n0 = S.mark()
        self._gstubs = []                                    # where the pins of this IC end in a ground symbol
        sides = {s: self.mkrows(a, s, 0, 0) for s in "LRUD"}
        self.plan_all(a, sides, cl, used)
        # the symbol first; its texts go above it, clear of any stub that leaves the top
        tx = xl
        tw_ = max(tw(a), tw(c["value"]))
        for r in sides["U"]:
            if r.kind != "nc" and any(tx - 0.5 < p[0] < tx + tw_ + 0.5 for p in r.pts): tx = max(p[0] for p in r.pts) + 2.0
        mode, dy = tpos
        x0 = {"left": tx, "right": xr, "center": (xl + xr) / 2}[mode]
        self.put(S, a, 0, 0, 0, ref_at=(x0, yt - 4.44 + dy), val_at=(x0, yt - 1.9 + dy), ref_j=mode, val_j=mode)
        for s in "LR":
            if sides[s]: self.side_lr(S, a, s, sides[s], cl, used)
        for s in "UD":
            if sides[s]: self.side_ud(S, a, s, sides[s], cl, used)
        self.ground_pads(S, cl, used, n0)
        left = [p for p in cl if p not in used]
        if left:
            if os.environ.get("DEBUG_LEFT"): print("  leftover at", a, left)
            self.draw_group(S, left, xl, S.bbox_from(n0)[3] + 6.0)

    # ------------------------------------------------------------------ pins that move to their lanes
    def plan_stretch(self, a):
        """An IC whose pins are 2.54 mm apart but whose lanes need 10 to 20 mm each would have its lanes fan out to the pins in a
        bundle of long parallel wires. Such a side is drawn like a person draws a part with a lot around its pins: the pins
        stand where their lanes are (same order, same names and numbers; the body grows to hold them), and every lane is a
        straight wire from its pin. The lanes are laid out once with the pins in place, the pins are moved to those places, and
        that is repeated until the lanes stand on their pins."""
        if a in self._planned: return
        self._planned.add(a)
        lib, name = self.comps[a]["lib"].split(":")
        if os.environ.get("NO_STRETCH") or self.units(a) != [1] or not symlib.plain_body(lib, name): return
        self._pin0[a] = [(d, d.x, d.y) for d in self.dp[a]]
        sides = None
        for it in range(4):
            self._vlog = {}
            try: self._draw_anchor(self.scratch(), a, ("left", 0.0))
            finally: log, self._vlog = self._vlog, None
            if sides is None:
                sides = {s for s, rows in log.items() if max([abs(r.ys - self._rowy(r)) for r in rows if r.kind != "nc"] + [0]) >= STRETCH_MIN}
                if not sides: return
            if not self._move_pins(a, log, sides): break

    def _move_pins(self, a, log, sides):
        """Put the pins of the given sides where their rows stand. Returns False when nothing moved."""
        new = {}                                                # id of a drawn pin -> new y (symbol coordinates, y up)
        for s in sides:
            cur = None
            for r in log[s]:
                half = (r.pts[-1][1] - r.pts[0][1]) / 2         # the lane of a row of several pins stands at the middle of them
                for k, d in enumerate(r.dps):
                    y = r.ys - half + (r.pts[k][1] - r.pts[0][1])  # the pins of one row keep their pitch
                    # a pin of several pads prints a line of number for each, upward from its own line: the pin above stands clear of them
                    if cur is not None: y = max(y, cur + 2.54 + 1.27 * (d.nvis - 1))
                    cur = y
                    new[id(d)] = snap(-y)
        d0 = {id(d): (x0, y0) for d, x0, y0 in self._pin0[a]}
        if all(abs(new[i] - d.y) < 0.01 for d, _, _ in self._pin0[a] for i in [id(d)] if i in new): return False
        lib, name = self.comps[a]["lib"].split(":")
        body = geo(lib, name, 1)["body"]
        top0, bot0 = body[3], body[1]
        lr = [d for d, _, _ in self._pin0[a] if d.angle in (0, 180)]
        y_old = [d0[id(d)][1] for d in lr]
        y_new = [new.get(id(d), d0[id(d)][1]) for d in lr]
        top = max(top0, max(y_new) + (top0 - max(y_old)))
        bot = min(bot0, min(y_new) - (min(y_old) - bot0))
        pins = {}
        for d, x0, y0 in self._pin0[a]:
            y = new.get(id(d), y0)
            if d.angle == 270: y = y0 + (top - top0)                   # pins on the top edge and the bottom edge move with it
            elif d.angle == 90: y = y0 + (bot - bot0)
            pins[(round(x0, 3), round(y0, 3))] = round(y, 4)
        for d, x0, y0 in self._pin0[a]: d.y = pins[(round(x0, 3), round(y0, 3))]
        self.plans[a] = (tuple(sorted(pins.items())), (round(top, 4), round(bot, 4)))
        return True

    def ground_pads(self, S, cl, used, n0):
        """Test points and wire pads on a ground net sit beside a ground symbol of the IC they belong to: a wire runs on
        from the symbol and ends in the pad, wherever that is clear of what the IC already has around it."""
        def clear(box):
            bx = (box[0] + S.tx, box[1] + S.ty, box[2] + S.tx, box[3] + S.ty)
            return not any(r["box"] and r["box"][0] < bx[2] and r["box"][2] > bx[0] and r["box"][1] < bx[3] and r["box"][3] > bx[1]
                           for r in S.recs[n0:])
        for p in cl:
            if p in used or len(self.dp[p]) != 1: continue
            net = self.dp[p][0].net
            if net is None or self.role(net) != "down": continue
            txt = max(tw(p), tw(self.comps[p]["value"]))
            cands = [(pri, x, y, d) for n, x, y, d, pri in self._gstubs if n == net]
            for r in S.recs[n0:]:                              # then any ground symbol of this IC's circuit
                if r["kind"] == "sym" and r.get("power") and r["nets"].get("1") == net and "1" in r["pins"]:
                    cands.append((3, r["pins"]["1"][0] - S.tx, r["pins"]["1"][1] - S.ty, 1))
            for pri, x, y, d in sorted(cands):
                done = False
                for dd in (d, -d):
                    for dist in (5.08, 7.62, 10.16, 12.7):
                        xe = x + dd * dist
                        # the wire, the pad (2.5 to 4 mm of body) and its two lines of text beside it
                        x1, x2 = sorted((x + dd * 1.5, xe + dd * (4.06 + 1.9 + txt)))
                        if clear((x1, y - 2.2, x2, y + 2.2)):
                            S.wire(x, y, xe, y, net)
                            self.pad(S, p, xe, y, "R" if dd > 0 else "L", side=dd)
                            used.add(p); done = True; break
                    if done: break
                if done: break

    # ------------------------------------------------------------------ top and bottom pins
    def side_ud(self, S, a, s, rows, cl, used):
        up = s == "U"
        for r in rows:
            if r.kind == "nc":
                S.nc(*r.pts[0]); continue
            net = r.net
            xs = [p[0] for p in r.pts]
            y0 = r.pts[0][1]
            role = self.role(net)
            shunts = getattr(r, "shunts", [])
            sdir = getattr(r, "sdir", -1)
            if role == "down" and not up:
                ye = y0 + 2.54
                for x in xs: S.wire(x, y0, x, ye, net)
                if len(xs) > 1: S.wire(min(xs), ye, max(xs), ye, net)
                xm = snap((min(xs) + max(xs)) / 2)
                self.end(S, net, xm, ye, 1)
                self._gstubs.append((net, xm, ye, 1, 0))
                continue
            ye = y0 - 14.0 if (up and shunts) else (y0 - 2.54 if up else y0 + 2.54)
            for x in xs: S.wire(x, y0, x, ye, net)
            xm = snap(xs[0])
            if len(xs) > 1:
                S.wire(min(xs), ye, max(xs), ye, net)
            for k, p in enumerate(shunts):
                xc = (xm if sdir < 0 else max(xs)) + sdir * (10.16 if len(shunts) > 1 else 7.62) * (k + 1)
                top, bot = self.vpart(S, p, xc, ye + 1.27, net, sdir, at="top", vert=len(shunts) > 1)
                S.wire(xm, ye, xc, ye, net)
                S.wire(xc, ye, top[0], top[1], net)
                self.end(S, self.other(p, net), bot[0], bot[1], sdir)
                used.add(p)
            yend = ye + (-2.54 if up else 2.54)
            S.wire(xm, ye, xm, yend, net)
            self.end_v(S, net, xm, yend, -1 if up else 1)

    def end_v(self, S, net, x, y, d):
        """A vertical wire arrives at (x, y) heading d (-1 up, +1 down)."""
        if net in self.link_nets:                                # a wire carries on to the IC this one is linked to
            self.stubs[(self._cur, net)] = (x, y); return
        role = self.role(net)
        if role == "down" and d > 0:
            self.power(S, net, x, y, "gnd"); return
        if role == "up" and self.is_global_rail(net) and d < 0:
            self.power(S, net, x, y, "up"); return
        S.label(self.short(net), x, y, 90 if d < 0 else 270, net in self.glob, net=net)

    # ------------------------------------------------------------------ groups of parts without an IC
    def groups(self, parts):
        parts = list(parts)
        par = {p: p for p in parts}
        def find(p):
            while par[p] != p:
                par[p] = par[par[p]]; p = par[p]
            return p
        by = {}
        for p in parts:
            for d in self.dp[p]:
                n = d.net
                if n and self.role(n) is None: by.setdefault(n, []).append(p)
        for ps in by.values():
            for q_ in ps[1:]: par[find(q_)] = find(ps[0])
        out = {}
        for p in parts: out.setdefault(find(p), []).append(p)
        return list(out.values())

    def vrow(self, net, x, y):
        d = Dp()
        d.x, d.y, d.unit, d.nums, d.name, d.net, d.angle, d.type, d.hidden, d.nc, d.length = x, -y, 1, ["0"], net, net, 180, "passive", False, False, 0
        r = Row("R", [d], 0, 0)
        return r

    def start_net(self, group):
        best, bs = None, -99
        cnt = {}
        for p in group:
            for d in self.dp[p]:
                if d.net: cnt[d.net] = cnt.get(d.net, 0) + 1
        for n, k in cnt.items():
            role = self.role(n)
            sc = k
            if n in self.glob: sc += 3
            if role == "up": sc += 4
            if role == "down": sc -= 20
            if sc > bs: best, bs = n, sc
        return best

    def draw_group(self, S, parts, x, y):
        """Small parts without an IC, each connected set drawn as lanes from a start net, one below the other. Returns the
        y below the drawing."""
        for grp in self.groups(parts):
            n0 = S.mark()
            y = self.draw_one(S, grp, x, y)
            b = S.bbox_from(n0)
            if b: y = max(y, b[3])
            y += 5.08
        return y

    def draw_one(self, S, grp, x, y):
        pads = [p for p in grp if len(self.dp[p]) == 1]
        rest = [p for p in grp if len(self.dp[p]) > 1]
        used = set()
        cl = list(grp)
        if len(rest) == 1 and not pads and all(self.role(d.net) != "down" for d in self.dp[rest[0]]):
            self.draw_isolated(S, rest[0], x, y)               # a part between two rails or signals: its nets on either side
            return y + 7.62
        while True:
            left = [p for p in rest if p not in used]
            if not left: break
            net = self.start_net(left)
            r = self.vrow(net, x + tw(self.short(net)) + 4.0, y)
            u2 = set(used)
            lane = self.plan_lane(None, r, cl, u2, {})
            got = {p for p in left if p in u2}
            if lane is None or not got:
                self.draw_isolated(S, left[0], x, y)
                used.add(left[0]); y += 7.62
                continue
            r.lane = lane
            n0 = S.mark()
            self.end(S, net, r.pts[0][0], r.pts[0][1], -1)
            self.side_lr(S, None, "R", [r], cl, u2)
            used |= {p for p in u2 if p in cl}
            b = S.bbox_from(n0)
            y = max(y, b[3] if b else y) + 5.08
        left_pads = [p for p in pads if p not in used]
        if left_pads: y = self.draw_pads(S, left_pads, x, y)
        return y

    def draw_isolated(self, S, p, x, y):
        ds = self.dp[p]
        na, nb = ds[0].net, ds[1].net
        nm = {d.name: d.net for d in ds}
        if "A" in nm and "K" in nm: na, nb = nm["A"], nm["K"]       # a diode points to the right
        xl = x + tw(self.short(na)) + 4.0
        l, r = self.hpart(S, p, xl, y, na, at="left")
        S.wire(l[0] - 2.54, y, l[0], y, na)
        self.end(S, na, l[0] - 2.54, y, -1)
        S.wire(r[0], y, r[0] + 2.54, y, nb)
        self.end(S, nb, r[0] + 2.54, y, 1)

    def draw_pads(self, S, pads, x, y):
        """One-pin parts (wire pads, test points) as a grid: the net on the left, the pad with its texts on the right."""
        n = len(pads)
        cols = 1 if n == 1 else (2 if n <= 4 else 3)
        cells = []
        for p in pads:
            net = self.dp[p][0].net
            lab = tw(self.short(net)) + 3.0 if self.role(net) is None else 4.0
            txt = max(tw(p), tw(self.comps[p]["value"]))
            cells.append((p, net, lab + 2.54 + 3.0 + txt + 3.0))
        cw = max(c[2] for c in cells)
        rh = 8.89
        for k, (p, net, w) in enumerate(cells):
            cx, cy = x + (k % cols) * cw, y + (k // cols) * rh + 3.81
            role = self.role(net)
            if role == "down":
                self.pad(S, p, cx + 2.54, cy, "U"); self.power(S, net, cx + 2.54, cy, "gnd")
            elif role == "up" and self.is_global_rail(net):
                self.pad(S, p, cx + 2.54, cy, "D"); self.power(S, net, cx + 2.54, cy, "up")
            else:
                lab = tw(self.short(net)) + 1.6 + 1.4
                S.wire(cx + lab, cy, cx + lab + 2.54, cy, net)
                self.end(S, net, cx + lab, cy, -1)
                self.pad(S, p, cx + lab + 2.54, cy, "R")
        return y + (math.ceil(n / cols)) * rh

    # ------------------------------------------------------------------ sections and items
    def section_list(self):
        """[(title, [parts])] in drawing order: every part sits in the section it was declared in; small parts that belong to
        an IC travel with it."""
        secs, seen = [], {}
        for r in self.refs:
            s = self.comps[r].get("section", "")
            if s not in seen:
                seen[s] = len(secs); secs.append((s, []))
            secs[seen[s]][1].append(r)
        return secs

    def make_items(self):
        out = []
        for title, refs in self.section_list():
            items = []
            for r in refs:
                if r in self.anchors and r not in self.skip:
                    fn = (lambda S, a=r: self.draw_anchor(S, a))
                    box = self.measure(fn)
                    items.append(Item(r, fn, box, "ic", self.refs.index(r)))
            free = [r for r in refs if r in self.small and r not in self.owner]
            if free:
                for k, grp in enumerate(self.groups(free)):
                    fn = (lambda S, g=grp: self.draw_group(S, g, 0.0, 0.0))
                    box = self.measure(fn)
                    if box: items.append(Item(f"free{k}", fn, box, "free", self.refs.index(grp[0])))
            near = self.cons.get("drawing", {}).get("near", {})           # an IC drawn next to the one it is wired to
            for it in list(items):
                tgt = next((x for x in items if x.name == str(near.get(it.name, "")).split(".")[0] and x is not it), None)
                if tgt is not None:
                    items.remove(it); items.insert(items.index(tgt) + 1, it)
                    ln = self.link_item(it, tgt)
                    if ln is not None:
                        items.remove(it); items[items.index(tgt)] = ln
            if items: out.append((title, items))
        return out

    def link_item(self, up, dn):
        """Two ICs drawn next to each other whose only common net runs from a bottom pin of the first to a top pin of the
        second (the fuse and the FET that heats it): the first stands above the second and one short wire joins the pins, in
        place of a label at each end."""
        if up.kind != "ic" or dn.kind != "ic": return None
        a, b = up.name, dn.name
        nets = {d.net for d in self.dp[a] if d.net} & {d.net for d in self.dp[b] if d.net}
        nets = {n for n in nets if self.role(n) not in ("up", "down")}
        if len(nets) != 1: return None
        net = next(iter(nets))
        da = [d for d in self.dp[a] if d.net == net]; db = [d for d in self.dp[b] if d.net == net]
        if len(da) != 1 or len(db) != 1 or da[0].angle != 90 or db[0].angle != 270: return None
        def fn(S):
            self.link_nets = {net}
            try:
                tx0, ty0 = S.tx, S.ty
                self.draw_anchor(S, a)
                fx, fy = self.stubs[(a, net)]
                self.draw_anchor(self.scratch(), b)
                qx, qy = self.stubs[(b, net)]
                bx, by = fx - qx, fy - qy + LINK_LEN
                S.tx, S.ty = tx0 + bx, ty0 + by
                self.draw_anchor(S, b)
                S.tx, S.ty = tx0, ty0
                S.wire(fx, fy, bx + qx, by + qy, net)
            finally: self.link_nets = set()
        return Item(a, fn, self.measure(fn), "ic", up.order)

    # ------------------------------------------------------------------ arranging items in a section
    def arrange(self, items, maxw):
        """Items in reading order, broken into rows where that makes the section most compact: every way of cutting the
        list into rows is tried (rows no wider than maxw), the smallest area wins, wide and flat sections a little less."""
        n = len(items)
        best = None
        for mask in range(1 << max(n - 1, 0)):
            rows, cur = [], [items[0]]
            for k in range(1, n):
                if (mask >> (k - 1)) & 1: rows.append(cur); cur = [items[k]]
                else: cur.append(items[k])
            rows.append(cur)
            wr = [sum(it.w for it in r) + ITEM_GAP * (len(r) - 1) for r in rows]
            if max(wr) > maxw + 1e-6 and len(rows) < n: continue
            W = max(wr)
            H = sum(max(it.h for it in r) for r in rows) + ITEM_GAP * (len(rows) - 1)
            score = W * H * (1 + (math.log(W / H / 2.0)) ** 2) + len(rows) * 1e-3
            if best is None or score < best[0]: best = (score, rows)
        y = 0.0
        W = 0.0
        for r in best[1]:
            x = 0.0
            for it in r:
                it.x, it.y = x, y
                x += it.w + ITEM_GAP
                W = max(W, it.x + it.w)
            y += max(it.h for it in r) + ITEM_GAP
        return W, y - ITEM_GAP

    def wrap(self, text, width, size=1.27):
        """Break a sentence into lines no wider than `width` mm."""
        lines, cur = [], ""
        for w in text.split():
            t = (cur + " " + w).strip()
            if cur and tw(t, size) > width: lines.append(cur); cur = w
            else: cur = t
        if cur: lines.append(cur)
        return lines

    def notes_for(self, title):
        return [n["text"] for n in self.cons.get("drawing", {}).get("notes", [])
                if n["block"] == self.block and n["section"] == title]

    def build_sections(self):
        secs = []
        for title, items in self.make_items():
            tot = sum(it.w for it in items) + ITEM_GAP * (len(items) - 1)
            maxw = max(max(it.w for it in items), min(tot, 240.0))
            W, H = self.arrange(items, maxw)
            wn = min(max(W, 90.0), 170.0)
            lines = [l for t in self.notes_for(title) for l in self.wrap(t, wn)]
            nw = max([tw(l, 1.27) for l in lines] + [0.0])
            sec = dict(title=title, items=items, lines=lines,
                       w=max(W, nw) + 2 * FRAME_PAD if W < nw else max(W + 2 * FRAME_PAD, tw(title, 1.8) * 1.2 + 2 * FRAME_PAD),
                       h=H + 2 * FRAME_PAD + TITLE_H + (len(lines) * 2.54 + 1.27 if lines else 0.0), x=0.0, y=0.0)
            sec["w"] = max(sec["w"], nw + 2 * FRAME_PAD, tw(title, 1.8) * 1.2 + 2 * FRAME_PAD)
            secs.append(sec)
        secs.sort(key=lambda s: all(it.kind == "free" for it in s["items"]))     # lists of loose pads and test points come last
        return secs

    # ------------------------------------------------------------------ packing sections on a page
    def pack(self, secs, W, order=None):
        """Masonry packing: every section goes to the place where it sits lowest (leftmost on a tie) within the width W."""
        sky = [(0.0, W + SEC_GAP, 0.0)]                       # skyline: (x0, x1, height), left to right
        right = bottom = 0.0
        for s in (order or secs):
            w, h = s["w"], s["h"]
            best = None
            for x in sorted({seg[0] for seg in sky}):
                if x + w > W + 1e-6: continue
                y = max(seg[2] for seg in sky if seg[1] > x + 1e-6 and seg[0] < x + w - 1e-6)
                if best is None or (y, x) < best[0]: best = ((y, x), x, y)
            if best is None: x, y = 0.0, max(seg[2] for seg in sky)
            else: _, x, y = best
            s["x"], s["y"] = x, y
            top = y + h + SEC_GAP
            new = []
            for a_, b_, yy in sky:
                if b_ <= x + 1e-6 or a_ >= x + w + SEC_GAP - 1e-6: new.append((a_, b_, yy)); continue
                if a_ < x: new.append((a_, x, yy))
                if b_ > x + w + SEC_GAP: new.append((x + w + SEC_GAP, b_, yy))
            new.append((x, x + w + SEC_GAP, top))
            sky = sorted(new)
            right, bottom = max(right, x + w), max(bottom, y + h)
        return right, bottom

    def pack_cols(self, cols, widths):
        """Strict columns: the sections of each group stand one under the other in a column as wide as the widest of them, so
        the frames of a column share their left and right edges. Returns the size of what is packed."""
        x = right = bottom = 0.0
        for grp in cols:
            wc = max(widths[id(s)] for s in grp)
            y = 0.0
            for s in grp:
                s["x"], s["y"], s["w"] = x, y, wc
                bottom = max(bottom, y + s["h"])
                y += s["h"] + SEC_GAP
            x += wc + SEC_GAP
            right = max(right, x - SEC_GAP)
        return right, bottom

    @staticmethod
    def cuts(order):
        """Every way of cutting an order into consecutive groups (the columns)."""
        n = len(order)
        for mask in range(1 << max(n - 1, 0)):
            cols, cur = [], [order[0]]
            for k in range(1, n):
                if (mask >> (k - 1)) & 1: cols.append(cur); cur = [order[k]]
                else: cur.append(order[k])
            cols.append(cur)
            yield cols

    def page_size(self, secs, w, h):
        """Paper size for content of w x h, leaving the title block corner free: the page is as tall as the lowest section
        standing over the title block asks for, and no taller."""
        pw, ph = max(w + 2 * EDGE, TB_W + 2 * EDGE), h + 2 * EDGE
        x0 = pw - EDGE - TB_W
        low = max([EDGE + s["y"] + s["h"] for s in secs if EDGE + s["x"] + s["w"] > x0 and EDGE + s["x"] < pw - EDGE] + [0.0])
        ph = max(ph, low + 2.0 + TB_H + EDGE, TB_H + 2 * EDGE + 20)
        return pw, ph

    @staticmethod
    def swaps(n, max_inv=3):
        """Orders of range(n) that keep the given order except for at most max_inv pairs standing the wrong way round:
        [(order, inversions)]. The given order is the order of the block file (inputs first), so it is only left where that
        packs the page clearly better."""
        out = []
        def rec(prefix, left, inv):
            if not left:
                out.append((prefix, inv)); return
            for k, v in enumerate(left):
                if inv + k > max_inv: break
                rec(prefix + [v], left[:k] + left[k + 1:], inv + k)
        rec([], list(range(n)), 0)
        return out

    def best_layout(self, secs):
        base = list(secs)
        # the first section of a block is where the signal comes in (the connector, the gauge): it stays top left
        orders = [(f"given{k}", [base[i] for i in o], 1.0 + INV_PENALTY * k) for o, k in self.swaps(len(base)) if o[0] == 0]
        tall = sorted(secs, key=lambda s: -s["h"])
        if tall[0] is base[0]: orders.append(("tall first", tall, 1.0 + 3 * INV_PENALTY))
        best = None
        wmax = max(s["w"] for s in secs)
        wsum = sum(s["w"] + SEC_GAP for s in secs)
        for name, order, bias in orders:
            for k in range(0, 80):
                W = wmax + k * 8.0
                if W > wsum + 8: break
                w, h = self.pack(secs, W, order)
                pw, ph = self.page_size(secs, w, h)
                asp = pw / ph
                pen = 1 + 2.0 * max(0.0, abs(math.log(asp / 1.6)) - math.log(1.7)) ** 2           # any shape from tall-ish to wide is fine
                score = pw * ph * pen * bias
                if best is None or score < best[0]: best = (score, W, order)
        w0 = {id(s): s["w"] for s in secs}
        cbest = None
        for name, order, bias in orders:                                     # the same orders as strict columns
            for cols in self.cuts(order):
                w, h = self.pack_cols(cols, w0)
                pw, ph = self.page_size(secs, w, h)
                for s in secs: s["w"] = w0[id(s)]
                asp = pw / ph
                pen = 1 + 2.0 * max(0.0, abs(math.log(asp / 1.6)) - math.log(1.7)) ** 2
                score = pw * ph * pen * bias * COLUMN_BONUS
                if cbest is None or score < cbest[0]: cbest = (score, cols)
        if os.environ.get("DEBUG_LAYOUT"):
            print(f"  {self.block}: masonry {best[0]:.0f} (W {best[1]:.0f}, order {[base.index(x) for x in best[2]]}); columns {cbest[0]:.0f} {[[base.index(x) for x in c] for c in cbest[1]]}")
        if cbest is not None and cbest[0] < best[0]:
            w, h = self.pack_cols(cbest[1], w0)
        else:
            self.pack(secs, best[1], best[2])
            w = max(s["x"] + s["w"] for s in secs); h = max(s["y"] + s["h"] for s in secs)
        return self.page_size(secs, w, h)

    # ------------------------------------------------------------------ the sheet
    def draw_sheet(self):
        secs = self.build_sections()
        self.drawn_titles = [s["title"] for s in secs]
        pw, ph = self.best_layout(secs)
        S = Sheet(self.block, self.project, self.root_uuid, self.block)
        for sec in secs:
            ox, oy = EDGE + sec["x"], EDGE + sec["y"]
            S.frame(ox, oy, ox + sec["w"], oy + sec["h"])
            S.text(sec["title"], ox + FRAME_PAD, oy + 5.0, size=1.8, bold=True)
            for k, line in enumerate(sec["lines"]):
                S.text(line, ox + FRAME_PAD, oy + 5.0 + 3.81 + 2.54 * k, size=1.27)
            top = oy + TITLE_H + (len(sec["lines"]) * 2.54 + 1.27 if sec["lines"] else 0.0)
            for it in sec["items"]:
                bx0, by0 = it.box[0], it.box[1]
                S.tx = snap(ox + FRAME_PAD + it.x - bx0)
                S.ty = snap(top + FRAME_PAD + it.y - by0)
                it.fn(S)
                S.tx = S.ty = 0.0
        S.junctions()
        return S, (round(pw), round(ph))
