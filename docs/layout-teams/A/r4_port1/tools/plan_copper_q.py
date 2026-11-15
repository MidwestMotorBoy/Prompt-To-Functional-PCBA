#!/usr/bin/env python3
"""plan_copper_q.py: team A r4_port1 planner = portcu planner P (all its options) + r4_port1 rules, each behind its
own option (0 = off; with no q option the output is identical to plan_copper_p.py). Same arguments as
tools/copper/plan_copper.py.

Imports portcu/tools/plan_copper_p.py (-> stagepwr plan_copper_a.py -> the stock planner, all unchanged)."""
import sys, os, json, math
sys.path.insert(0, '/home/claude/repo/tools/copper')
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/stagepwr/tools')
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/portcu/tools')
import numpy as np
from scipy import ndimage
from shapely.geometry import Point, LineString, Polygon, box
from shapely.ops import unary_union
import plan_copper as pc
import plan_copper_a as pa
import plan_copper_p as pp

QOPT = dict(gatevia=0, padjoin=0.0, connesc_big=0.0, connesc_big_len=0.8, connesc_big_via=0.15)
pp.OPT.update(QOPT)


class PlannerQ(pp.PlannerP):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        if pp.OPT["connesc_big"] > 0: self.conn_escapes_big()
        if pp.OPT["gatevia"]: self.gate_vias()

    # ---- rule q3 (--gatevia=1): the escape strip + via site that planner A reserves for a discrete FET's gate pin
    # sealed in its hot-loop hull (--sealed) is drawn as copper: a track of the gate net from the pin to the site and
    # a through via there. Found at Q401.1 (HG1): the site was free on F/B, but the Kelvin pair ACP_F (rank 0, routed
    # first) ran its In2 vertical straight over it, so the gate had no via left and failed every full route.
    # A placed via is an obstacle to every other net on every layer, and the router starts the gate edge from it.
    def gate_vias(self):
        rep = []
        for e in self.report.get("gate_escapes", []):
            ref, num = e["pad"].split(".", 1)
            if not ref.startswith("Q"): continue
            p = next((q for q in self.d.by_ref[ref] if q["num"] == num), None)
            if p is None: continue
            L = self.d.fp[ref]["layer"]; g = self.d.pad_poly(p, L); a0, b0, a1, b1 = g.bounds; cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
            dx, dy = e["dir"]; ln = e["len_mm"]
            ex = a0 if dx < 0 else a1 if dx > 0 else cx; ey = b0 if dy < 0 else b1 if dy > 0 else cy
            vx, vy = round(ex + ln * dx, 3), round(ey + ln * dy, 3)
            if any(math.hypot(v["x"] - vx, v["y"] - vy) < 0.75 for v in self.vias): continue
            w = min(0.25, self._short_side(g))
            self.tracks.append(dict(net=p["net"], layer=L, a=(round(cx, 4), round(cy, 4)), b=(vx, vy), w=w))
            self.vias.append(dict(net=p["net"], x=vx, y=vy, size=pc.VIA_D, drill=pc.VIA_DRILL))
            rep.append([e["pad"], vx, vy])
        self.report.setdefault("portcu", {})["gate_vias"] = rep

    # ---- rule q1 (--connesc_big=W): a connector signal pad wider than portcu's connesc limit (0.35 mm) and up to W mm
    # (a TC2030 / pogo pad) on the outer row of its connector keeps a strip straight out of the connector
    # (--connesc_big_len past the pad, 0.2 mm track + 2 x 0.25 mm HighCurrent rule wide) and a via site at its end
    # (via + --connesc_big_via) on both outer layers, which other nets' power copper keeps the clearance from.
    # Found at J302.6 (SCL): the CELL_P pour wrapped the pad row, the 0.4 mm escape room is narrower than a track
    # needs from a HighCurrent pour, and the next pads / NPTH pegs close the other sides.
    # ---- rule q2 (--padjoin=MM): a pad of a 2-pad part on a power net (a feedback divider top, a pull-up to a rail) that
    # the planned copper of its net does not reach, with that copper within MM on the same outer layer, gets a thin
    # straight (else L-shaped) track into it after the grow step, checked on exact shapes. Found at R433.1 (PP5V,
    # FB divider of the port-1 5 V buck): the router has to find a 3-7 mm stub out of a pad boxed in by 0402s and
    # GND vias, and failed it on every full route ("no way", seen ~220 cells).
    def pad_joins(self):
        D = float(pp.OPT["padjoin"]); rep = []
        for net in sorted(self.d.power):
            if net in self.d.ret: continue
            for L in self.outer:
                z = self.zones.get((net, L))
                if not z or z["soft"]: continue
                tr = [LineString([t["a"], t["b"]]).buffer(t["w"] / 2) for t in self.tracks if t["net"] == net and t["layer"] == L]
                cu = unary_union([z["geom"]] + tr); tin = cu.buffer(-0.12)
                if tin.is_empty: continue
                obs = None
                for p in self.d.pads:
                    if p["net"] != net or L not in p["shapes"] or p.get("drill") or len(self.d.by_ref[p["ref"]]) != 2: continue
                    pg = self.d.pad_poly(p, L)
                    if pg.intersects(cu.buffer(0.02)) or pg.distance(cu) > D: continue
                    c = pg.centroid; obs = self.obstacles(net, L) if obs is None else obs
                    q = tin.boundary.interpolate(tin.boundary.project(c)); ok = False
                    for w in (0.3, 0.25, 0.2):
                        if self._track_ok(net, L, (c.x, c.y), (q.x, q.y), w, obs=obs):
                            self._draw_track(net, L, (c.x, c.y), (q.x, q.y), w, "pad_join"); ok = True; break
                    if not ok:      # L shapes to the nearest few points of the copper
                        cands = sorted((c.distance(Point(x, y)), x, y) for x in np.arange(c.x - D, c.x + D + 0.01, 0.1) for y in np.arange(c.y - D, c.y + D + 0.01, 0.1) if tin.contains(Point(x, y)))[:200]
                        for _, x, y in cands:
                            for k in ((c.x, y), (x, c.y)):
                                for w in (0.25, 0.2):
                                    if self._track_ok(net, L, (c.x, c.y), k, w, obs=obs) and self._track_ok(net, L, k, (x, y), w, obs=obs):
                                        self._draw_track(net, L, (c.x, c.y), k, w, "pad_join"); self._draw_track(net, L, k, (x, y), w, "pad_join"); ok = True; break
                                if ok: break
                            if ok: break
                    rep.append([p["key"], net[-12:], L, ok])
        self.report.setdefault("portcu", {})["pad_joins"] = rep

    def grow_step(self, step=0.5):
        super().grow_step(step)
        if pp.OPT["padjoin"] > 0: self.pad_joins()

    def conn_escapes_big(self):
        rep = []; W = float(pp.OPT["connesc_big"]); ln = float(pp.OPT["connesc_big_len"]); w = 0.7
        for ref, ps in sorted(self.d.by_ref.items()):
            if not ref.startswith("J"): continue
            for L in self.outer:
                pp_ = [(p, self.d.pad_poly(p, L)) for p in ps if L in p["shapes"] and not p.get("drill")]
                if len(pp_) < 4: continue
                x0, y0, x1, y1 = unary_union([g for _, g in pp_]).bounds
                for p, g in pp_:
                    s_ = self._short_side(g)
                    if self.d.role(p["net"]) != "signal" or s_ <= 0.35 or s_ > W: continue
                    a0, b0, a1, b1 = g.bounds; cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
                    d = None
                    if b0 - y0 < 0.3: d = (0, -1, cx, b0)
                    elif y1 - b1 < 0.3: d = (0, 1, cx, b1)
                    elif a0 - x0 < 0.3: d = (-1, 0, a0, cy)
                    elif x1 - a1 < 0.3: d = (1, 0, a1, cy)
                    if d is None: continue
                    dx, dy, ex, ey = d; vx, vy = ex + dx * ln, ey + dy * ln
                    strip = LineString([(cx, cy), (vx, vy)]).buffer(w / 2, cap_style=2)
                    vs = Point(vx, vy).buffer(pc.VIA_D / 2 + float(pp.OPT["connesc_big_via"]), 16)
                    for LL in self.outer:
                        others = unary_union([qg for q, qg in self.padpoly[LL] if q["net"] != p["net"] and qg is not None] or [Polygon()])
                        k = (unary_union([strip, vs]) if LL == L else vs).difference(others.buffer(self.clr))
                        if k.is_empty: continue
                        self.gate_keep.setdefault(LL, []).append((p["net"], k))
                        self.block[LL] |= self.raster(k.buffer(self.clr))
                        self.blockgeom[LL].append(k)
                    rep.append(p["key"])
        self.report.setdefault("portcu", {})["conn_escapes_big"] = rep


def main():
    pp.PlannerP_orig = pp.PlannerP
    pp.PlannerP = PlannerQ          # pp.main() instantiates pp.PlannerP
    try: pp.main()
    finally: pp.PlannerP = pp.PlannerP_orig


if __name__ == "__main__":
    main()
