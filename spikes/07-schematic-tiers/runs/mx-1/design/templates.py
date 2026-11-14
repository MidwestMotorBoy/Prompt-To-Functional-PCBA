"""Textbook drawings of known circuits, chosen with draw_as() in the block files: the four-switch power stage."""
import math
from sch import *
from ctx import Dp
from lanes import Row


class TemplateMixin:
    # ------------------------------------------------------------------ helpers
    def unit_row(self, a, unit, ox, oy, mirror=False):
        """The row of the gate pin of one unit placed at (ox, oy): the pin on the left, or on the right when mirrored."""
        d0 = next(d for d in self.dp[a] if d.unit == unit and d.angle == 0)
        if not mirror:
            return Row("L", [d0], ox, oy)
        d = Dp()
        for k in Dp.__slots__: setattr(d, k, getattr(d0, k))
        d.x, d.angle = -d0.x, 180
        return Row("R", [d], ox, oy)

    def rail_bank(self, S, parts, x0, y, net, dirn):
        """Parts hanging from a rail at height y, starting at x0 and stepping in direction dirn, each down to its other net.
        Returns the x of the last one."""
        x = x0
        for c in parts:
            top, bot = self.vpart(S, c, x, y + 1.27, net, dirn, at="top", vert=len(parts) > 2)
            S.wire(x, y, top[0], top[1], net)
            self.end(S, self.other(c, net), bot[0], bot[1], dirn)
            x += dirn * 10.16
        return x - dirn * 10.16

    # ------------------------------------------------------------------ four-switch buck-boost stage
    def draw_bridge4(self, S, q1):
        n0 = S.mark()
        h = self.cons["draw"][q1]
        q2, L, rin, rout = h["q_out"], h["inductor"], h["rin"], h["rout"]
        cin, cout = h["cin"], h["cout"]
        pn = lambda r, p: self.pinnet.get((r, p))
        top1, sw1, gnd, top2, sw2 = pn(q1, "2"), pn(q1, "9"), pn(q1, "5"), pn(q2, "2"), pn(q2, "9")
        YB, X2 = 12.7, 30.48
        used = set()
        cl1, cl2 = self.claimed(q1), self.claimed(q2)
        # the four switches: a half bridge on each side of the inductor, the second one mirrored
        a1 = self.put(S, q1, 0, 0, 0, unit=1, ref_at=(-3.81, -8.24), val_at=(-3.81, -5.7), ref_j="left", val_j="left")
        b1 = self.put(S, q1, 0, YB, 0, unit=2, ref_at=(-3.81, YB + 5.7), val_at=(-3.81, YB + 8.24), ref_j="left", val_j="left")
        a2 = self.put(S, q2, X2, 0, 0, unit=1, mirror=True, ref_at=(X2 + 3.81, -8.24), val_at=(X2 + 3.81, -5.7), ref_j="right", val_j="right")
        b2 = self.put(S, q2, X2, YB, 0, unit=2, mirror=True, ref_at=(X2 + 3.81, YB + 5.7), val_at=(X2 + 3.81, YB + 8.24), ref_j="right", val_j="right")
        yr = a1.pin["2"][1] - 20.32                               # the rails run above everything
        # left half bridge: drain up to the input rail, source to ground, switch node to the inductor
        xs1 = a1.pin["9"][0] + 2.54
        S.path([a1.pin["2"], (xs1, a1.pin["2"][1]), (xs1, yr)], top1)
        S.path([a1.pin["9"], (xs1, a1.pin["9"][1]), (xs1, b1.pin["9"][1]), b1.pin["9"]], sw1)
        S.path([b1.pin["5"], (xs1, b1.pin["5"][1])], gnd)
        S.wire(xs1, b1.pin["5"][1], xs1, b1.pin["5"][1] + 2.54, gnd)
        self.end(S, gnd, xs1, b1.pin["5"][1] + 2.54, 1)
        # right half bridge, mirrored
        xs2 = a2.pin["9"][0] - 2.54
        S.path([a2.pin["2"], (xs2, a2.pin["2"][1]), (xs2, yr)], top2)
        S.path([a2.pin["9"], (xs2, a2.pin["9"][1]), (xs2, b2.pin["9"][1]), b2.pin["9"]], sw2)
        S.path([b2.pin["5"], (xs2, b2.pin["5"][1])], gnd)
        S.wire(xs2, b2.pin["5"][1], xs2, b2.pin["5"][1] + 2.54, gnd)
        self.end(S, gnd, xs2, b2.pin["5"][1] + 2.54, 1)
        S.label(self.short(sw1), xs1, snap((a1.pin["9"][1] + b1.pin["9"][1]) / 2), 180, sw1 in self.glob, net=sw1)
        S.label(self.short(sw2), xs2, snap((a2.pin["9"][1] + b2.pin["9"][1]) / 2), 0, sw2 in self.glob, net=sw2)
        # the inductor between the two switch nodes
        ym = snap((a1.pin["9"][1] + b1.pin["9"][1]) / 2)
        xc = snap((xs1 + xs2) / 2)
        l, r = self.hpart(S, L, xc, ym, sw1, text="above")
        S.wire(xs1, ym, l[0], ym, sw1)
        S.wire(r[0], ym, xs2, ym, sw2)
        used.add(L)
        # input: R424 from the source, then the rail with its capacitors, down to the first drain
        xlast = self.rail_bank(S, cin, xs1 - 12.7, yr, top1, -1)
        S.wire(xs1, yr, xlast, yr, top1)
        S.wire(xs1 - 3.81, yr, xs1 - 3.81, yr - 2.54, top1)
        S.label(self.short(top1), xs1 - 3.81, yr - 2.54, 180, top1 in self.glob, net=top1)
        d_in = math.ceil(max(8.89, 7.3 + max(tw(rin), tw(self.comps[rin]["value"])) / 2) / G - 1e-6) * G   # clear of the texts of the bank
        l, r = self.hpart(S, rin, xlast - d_in, yr, pn(rin, "1"), text="above")
        S.wire(r[0], yr, xlast, yr, top1)
        te = self.end_tail(rin, pn(rin, "1"))
        S.wire(l[0], yr, l[0] - te, yr, pn(rin, "1"))
        self.end(S, pn(rin, "1"), l[0] - te, yr, -1)
        # output: the rail with its capacitors, then R427 to the pack
        xlast2 = self.rail_bank(S, cout, xs2 + 12.7, yr, top2, 1)
        S.wire(xs2, yr, xlast2, yr, top2)
        S.wire(xs2 + 3.81, yr, xs2 + 3.81, yr - 2.54, top2)
        S.label(self.short(top2), xs2 + 3.81, yr - 2.54, 0, top2 in self.glob, net=top2)
        d_out = math.ceil(max(8.89, 7.3 + max(tw(rout), tw(self.comps[rout]["value"])) / 2) / G - 1e-6) * G
        l, r = self.hpart(S, rout, xlast2 + d_out, yr, top2, text="above")
        S.wire(xlast2, yr, l[0], yr, top2)
        te = self.end_tail(rout, pn(rout, "2"))
        S.wire(r[0], yr, r[0] + te, yr, pn(rout, "2"))
        self.end(S, pn(rout, "2"), r[0] + te, yr, 1)
        used.update(cin + cout + [rin, rout])
        # the gate resistors on the outer sides
        for q, unit, ox, oy, mir, cl in ((q1, 1, 0, 0, False, cl1), (q1, 2, 0, YB, False, cl1), (q2, 1, X2, 0, True, cl2), (q2, 2, X2, YB, True, cl2)):
            row = self.unit_row(q, unit, ox, oy, mir)
            side = "R" if mir else "L"
            self.plan_all(q, {side: [row]}, cl, used)
            self.side_lr(S, q, side, [row], cl, used)
        left = [p for p in cl1 + cl2 if p not in used]
        if left:
            self.draw_group(S, left, -12.7, S.bbox_from(n0)[3] + 6.0)

    # ------------------------------------------------------------------ two FETs back to back in a power path
    def chain_order(self, parts, start):
        """Parts of a series chain in order from net `start`; returns [(part, near net, far net)]."""
        out, cur, left = [], start, list(parts)
        while left:
            nxt = next((p for p in left if cur in [d.net for d in self.dp[p]]), None)
            if nxt is None: break
            far = self.other(nxt, cur)
            out.append((nxt, cur, far)); left.remove(nxt); cur = far
        return out

    def draw_fetpair(self, S, qa):
        """Two N-FETs back to back (drains together in the middle, sources outward) as the datasheet draws a protection
        stage: the path runs left to right, gate drive and pull-downs on the outside, the source rails below, the
        capacitors across the pair under it."""
        n0 = S.mark()
        h = self.cons["draw"][qa]
        qb = h["q_out"]
        pn = lambda r, p: self.pinnet.get((r, p))
        src_a, src_b, mid = pn(qa, "1"), pn(qb, "1"), pn(qa, "5")
        esd, byp, wake = h.get("esd", []), h.get("bypass", []), h.get("wake", [])
        cla, clb = self.claimed(qa), self.claimed(qb)
        used = set()
        n = len(esd)
        chain_w = math.ceil((n * 7.62 + (n + 1) * 2.54) / 1.27 - 1e-6) * 1.27 if n else 12.7
        X2 = snap(17.78 + chain_w)
        yr, yc = 8.89, 17.78
        a = self.put(S, qa, 0, 0, 0, ref_at=(-3.81, -8.44), val_at=(-3.81, -5.9), ref_j="left", val_j="left")
        b = self.put(S, qb, X2, 0, 0, mirror=True, ref_at=(X2 + 3.81, -8.44), val_at=(X2 + 3.81, -5.9), ref_j="right", val_j="right")
        da, db_ = a.pin["5"], b.pin["5"]
        S.wire(da[0], da[1], db_[0], db_[1], mid)
        S.label(self.short(mid), snap((da[0] + db_[0]) / 2), da[1], 0, mid in self.glob, net=mid)
        xa, xb = a.pin["1"][0], b.pin["1"][0]
        S.wire(xa, a.pin["1"][1], xa, yc if esd else yr, src_a)
        S.wire(xb, b.pin["1"][1], xb, yc if esd else yr, src_b)
        # the capacitors across the pair, in series from one source to the other
        cur_x = xa
        for k, (c, near, far) in enumerate(self.chain_order(esd, src_a)):
            l, r = self.hpart(S, c, xa + 2.54 + 3.81 + k * 10.16, yc, near, text="above")
            S.wire(cur_x, yc, l[0], yc, near)
            cur_x = r[0]
            used.add(c)
        if esd: S.wire(cur_x, yc, xb, yc, src_b)
        # gate drive and pull-downs on the outer sides, hanging down to the source rail
        rail_end = {}
        for q, unit, ox, mir, cl, src in ((qa, 1, 0, False, cla, src_a), (qb, 1, X2, True, clb, src_b)):
            side = "R" if mir else "L"
            row = self.unit_row(q, unit, ox, 0, mir)
            self.plan_all(q, {side: [row]}, cl, used)
            if row.lane:
                for att in row.lane.nodes[0].atts:
                    if att.kind in ("up", "hang", "dn") and att.far == src:
                        att.kind, att.rail = "hang", yr
            self.side_lr(S, q, side, [row], cl, used)
            sg = 1 if mir else -1
            xs = [row.pts[0][0] + sg * (att.u + self.att_w(att) - 2.0) for att in (row.lane.nodes[0].atts if row.lane else []) if att.rail is not None]
            rail_end[q] = (max(xs) if sg > 0 else min(xs)) + sg * (1.27 + 0.5 * tw(self.short(src))) if xs else (b.pin["1"][0] if mir else a.pin["1"][0])
        S.wire(xa, yr, rail_end[qa], yr, src_a)
        self.end(S, src_a, rail_end[qa], yr, -1)
        S.wire(xb, yr, rail_end[qb], yr, src_b)
        self.end(S, src_b, rail_end[qb], yr, 1)
        # a pull from the source rail to a test point or a net of its own (the wake line), below the rail
        for c in wake:
            if c in self.small and len(self.dp[c]) == 2:
                top, bot = self.vpart(S, c, snap(xa - 6.35), yr + 1.27, src_a, -1, at="top")
                S.wire(snap(xa - 6.35), yr, top[0], top[1], src_a)
                nxt = self.other(c, src_a)
                used.add(c)
                pads = [q_ for q_ in wake if q_ in self.small and len(self.dp[q_]) == 1 and self.dp[q_][0].net == nxt]
                if pads:
                    S.wire(bot[0], bot[1], bot[0], bot[1] + 2.54, nxt)
                    self.pad(S, pads[0], bot[0], bot[1] + 2.54, "D", side=-1)
                    used.add(pads[0])
                else:
                    self.end(S, nxt, bot[0], bot[1], -1)
        # series capacitors from the output rail to ground (a bypass pair), below the rail
        if byp:
            xk = snap(xb + 6.35)
            y = yr
            S.wire(xk, yr, xk, yr + 1.27, src_b)
            y = yr + 1.27
            for c, near, far in self.chain_order(byp, src_b):
                top, bot = self.vpart(S, c, xk, y, near, 1, at="top")
                if y > yr + 1.27: S.wire(xk, y - 2.54, xk, y, near)
                y = bot[1] + 2.54
                last, lastnet = bot, far
                used.add(c)
            self.end(S, lastnet, xk, last[1], 1)
        left = [p for p in cla + clb if p not in used]
        if left:
            self.draw_group(S, left, -12.7, S.bbox_from(n0)[3] + 6.0)
