#!/usr/bin/env python3
"""plan_copper_g.py: team A r5_gauge planner = r4_port1 planner Q (all its options) + r5_gauge rules, each behind its
own option (with no g option the output is identical to plan_copper_q.py). Same arguments as plan_copper.py.

Rules
  g1 --fkeep='x0,y0,x1,y1;...'  boxes on F.Cu where no power copper is drawn (pours, trees, grow, mirror sources).
        Used for the J302 north-row band (between the TC2030 pads and H103 / J118): the 10 A CELL_P tree from Q101 to
        F102 ran through it on F (and its B mirror on B), and J302.2 / J302.6 (CHG_INH, SCL) have no other exit: the
        TC2030 pads are F only, 0.48 mm apart, with NPTH pegs beside them. With the band blocked on F the stock
        planner's detour() takes CELL_P on B.Cu under J302 (no B pads there) with vias at both ends, so CELL_P keeps a
        full-width path and the F band is left to the router.
  g2 --viasite='x,y;...'  a reserved via site (via + --viasite_clr) on both outer layers that power copper keeps the
        clearance from (the same mechanism as planner P's --pinesc), for an escape via at a fixed spot.
  g3 --pinvia='REF.PIN:LEN;...'  pinesc for named pins: a strip of the pad's width straight out of the package edge
        and a via site LEN mm past the pad, whatever the pin's neighbours (pinesc only serves pins near a power pad).
        Used for U101.19 (SMBC): the FET_MID pour of Q101/Q102 sits 0.4 mm east of the gauge's east pin row, so SMBC
        had no via site between the pin and the pour and the full routes closed its start cells (starts 21, seen 27).
  g4 --epnets=REF[,REF]  planner P's --epstrip (pin -> own exposed pad strip) for the EP net of the named ICs even when
        that net is not a hot-loop return net. Used for U101 (gauge): CELL_1N pins 9, 16, 17, 23, 24 join the EP (33),
        and the router failed U101.33 -> U101.16 on a full route (seen 187).
  g6 --fcut='x0,y0,x1,y1;...' (--fcut_vias=N)  a lane cut out of the finished F.Cu power copper (zones and planner
        tracks) after the grow step, with N vias placed on each side of the cut in every piece of a cut net that also has
        copper on B.Cu, so the current crosses the lane on B. Used for SCL J302.6: the 10 A CELL_P strip Q101 -> F102
        (F tree + B mirror) runs between J302's north row and H103; the only exit of J302.6 is north through it and
        then up between H103 and J118. The B mirror stays whole, so CELL_P keeps both layers except across the lane.
        --fcut_path="x,y/x,y/...;..."' (--fcut_w=0.7): the same with a lane of width fcut_w along a path (the F copper
        edge then sits fcut_w/2 from the lane centre: a 0.2 mm track there keeps 0.25 mm).
  g7 --bfill='NETSUFFIX@x0,y0,x1,y1;...'  the net's B.Cu copper also fills the free part of a box (before the fcut).
        Used for CELL_P under J302 (TC2030 pads are F only, B there held only the soft GND fill), to win back the loss
        of the fcut lane.
Imports r4_port1/tools/plan_copper_q.py (-> portcu P -> stagepwr A -> the stock planner, all unchanged)."""
import sys, math
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/r4_port1/tools')
import plan_copper_q as pq
from plan_copper_q import pp, pc, Point, LineString, Polygon, unary_union, box

GOPT = dict(fkeep='', viasite='', viasite_clr=0.15, pinvia='', epnets='', fcut='', fcut_vias=3, fcut_path='', fcut_w=0.7, bfill='')
pp.OPT.update(GOPT)


class PlannerG(pq.PlannerQ):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        rep = self.report.setdefault("r5_gauge", {})
        F = self.outer[0]
        for s in [s for s in str(pp.OPT["fkeep"]).split(";") if s.strip()]:
            x0, y0, x1, y1 = map(float, s.split(","))
            g = box(x0, y0, x1, y1)
            self.block[F] |= self.raster(g); self.blockgeom[F].append(g)
            rep.setdefault("fkeep", []).append([x0, y0, x1, y1])
        for s in [s for s in str(pp.OPT["pinvia"]).split(";") if s.strip()]:
            key, ln = s.split(":"); ref, num = key.split(".", 1)
            self._pin_via(ref, num, float(ln), rep)
        for s in [s for s in str(pp.OPT["viasite"]).split(";") if s.strip()]:
            x, y = map(float, s.split(",")[:2])
            vs = Point(x, y).buffer(pc.VIA_D / 2 + float(pp.OPT["viasite_clr"]), 16)
            for LL in self.outer:
                k = vs.difference(unary_union([qg for q, qg in self.padpoly[LL] if qg is not None] or [Polygon()]).buffer(self.clr))
                if k.is_empty: continue
                self.gate_keep.setdefault(LL, []).append(("", k))
                self.block[LL] |= self.raster(k.buffer(self.clr)); self.blockgeom[LL].append(k)
            rep.setdefault("viasite", []).append([x, y])

    def hot_loops_step(self):
        out = super().hot_loops_step()
        refs = [r for r in str(pp.OPT["epnets"]).split(",") if r]
        if refs:
            keep_ret, keep_by, keep_sv = self.d.ret, self.d.by_ref, getattr(self, "ep_served", set())
            nets = set()
            for r in refs:
                ps = self.d.by_ref.get(r, [])
                nets |= {p["net"] for p in ps if self.d.area(p) >= 1.0 and not p.get("drill")}
            n0 = len(self.tracks)
            try:
                self.d.ret = nets; self.d.by_ref = {r: keep_by[r] for r in refs if r in keep_by}
                self.ep_strips()
            finally:
                self.d.ret, self.d.by_ref = keep_ret, keep_by
                self.report.setdefault("r5_gauge", {})["epnets"] = [[t["net"][-10:], t["a"], t["b"], t["w"]] for t in self.tracks[n0:]]
                self.ep_served = keep_sv
        return out

    def usage(self):
        if str(pp.OPT["bfill"]).strip(): self._bfill()
        if str(pp.OPT["fcut"]).strip() or str(pp.OPT["fcut_path"]).strip(): self._fcut()
        return super().usage()

    def _bfill(self):
        """g7 --bfill='NETSUFFIX@x0,y0,x1,y1;...': the net's B.Cu copper also fills the free part of the box (other nets'
        pads, copper, vias, tracks, holes and keep-outs cleared), kept only where it touches the net's B copper."""
        B = self.outer[-1]; rep = self.report.setdefault("r5_gauge", {}).setdefault("bfill", [])
        for s in [s for s in str(pp.OPT["bfill"]).split(";") if s.strip()]:
            suf, bb = s.split("@"); b = list(map(float, bb.split(",")))
            net = next((n for (n, L) in self.zones if L == B and n.endswith(suf)), None)
            if net is None: rep.append([suf, "no B copper"]); continue
            z = self.zones[(net, B)]
            g = self.clip_others(net, B, box(*b).intersection(self.inside))
            tr = [LineString([t["a"], t["b"]]).buffer(t["w"] / 2 + self.clr, 4) for t in self.tracks if t["layer"] == B and t["net"] != net]
            bl = [q.buffer(self.clr, 4) for q in self.blockgeom[B]] + self.npth
            if tr or bl: g = g.difference(unary_union(tr + bl))
            g = g.buffer(-0.15, 4).buffer(0.15, 4)
            g = unary_union([q for q in getattr(g, "geoms", [g]) if q.intersects(z["geom"].buffer(0.05))])
            if g.is_empty: rep.append([suf, "nothing free"]); continue
            a0 = z["geom"].area; z["geom"] = unary_union([z["geom"], g]); z["kinds"].add("bfill")
            self.cu[B][self.raster(g) & (self.cu[B] < 0)] = self.netid[net]
            rep.append([net[-10:], b, round(z["geom"].area - a0, 1)])

    def _fcut(self):
        F, B = self.outer; rep = self.report.setdefault("r5_gauge", {}).setdefault("fcut", [])
        bx = [list(map(float, s.split(","))) for s in str(pp.OPT["fcut"]).split(";") if s.strip()]
        lanes = [LineString([tuple(map(float, q.split(","))) for q in s.split("/")]).buffer(float(pp.OPT["fcut_w"]) / 2, 8)
                 for s in str(pp.OPT["fcut_path"]).split(";") if s.strip()]
        cut = unary_union([box(*b).buffer(self.clr, 4) for b in bx] + lanes); cutc = cut
        nets = []
        for (net, L), z in list(self.zones.items()):
            if L != F or z["soft"] or not z["geom"].intersects(cutc): continue
            z["geom"] = z["geom"].difference(cutc); nets.append(net)
        keep = []
        for t in self.tracks:
            if t["layer"] != F: keep.append(t); continue
            ln = LineString([t["a"], t["b"]]); cc = cut.buffer(t["w"] / 2, 4)
            if not ln.intersects(cc): keep.append(t); continue
            if t["net"] not in nets: nets.append(t["net"])
            rest = ln.difference(cc)
            for q in getattr(rest, "geoms", [rest]):
                if q.is_empty or q.length < 0.05: continue
                c = list(q.coords); keep.append(dict(t, a=(round(c[0][0], 4), round(c[0][1], 4)), b=(round(c[-1][0], 4), round(c[-1][1], 4))))
        self.tracks[:] = keep
        lane = unary_union(lanes) if lanes else None
        if lane is not None:      # planner vias of any net inside a lane (+ via radius + clearance) go
            gone = [v for v in self.vias if Point(v["x"], v["y"]).distance(lane) < pc.VIA_D / 2 + self.clr]
            if gone:
                self.unvia(gone)
                self.report.setdefault("r5_gauge", {})["fcut_vias_removed"] = [[v["net"][-8:], v["x"], v["y"]] for v in gone]
        for net in nets:
            zf = self.zones.get((net, F)); zb = self.zones.get((net, B))
            if zf is None: continue
            nv = []
            if zb is not None:
                for pc_ in getattr(zf["geom"], "geoms", [zf["geom"]]):
                    if pc_.distance(cut) > 1.0 or pc_.area < 0.5: continue
                    both = pc_.intersection(zb["geom"]).buffer(-0.05)
                    if both.is_empty: continue
                    near = both.intersection(cut.buffer(2.0))
                    if near.is_empty: continue
                    vs = self.place_vias(net, near, int(pp.OPT["fcut_vias"]), inside=both, toward=cut.centroid.coords[0])
                    nv += [[v["x"], v["y"]] for v in vs]
            rep.append(dict(net=net, vias=nv))

    def _pin_via(self, ref, num, ln, rep):
        ps = self.d.by_ref.get(ref, []); p = next((q for q in ps if q["num"] == num), None)
        if p is None: rep.setdefault("pinvia_missing", []).append(f"{ref}.{num}"); return
        for L in self.outer:
            if L not in p["shapes"]: continue
            pp_ = [(q, self.d.pad_poly(q, L)) for q in ps if L in q["shapes"] and not q.get("drill")]
            x0, y0, x1, y1 = unary_union([g for q, g in pp_ if q["num"] != "33" and g.area < 1.0] or [g for _, g in pp_]).bounds
            g = self.d.pad_poly(p, L); a0, b0, a1, b1 = g.bounds; cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
            d = None
            if a0 - x0 < 0.3: d = (-1, 0, a0, cy)
            elif x1 - a1 < 0.3: d = (1, 0, a1, cy)
            elif b0 - y0 < 0.3: d = (0, -1, cx, b0)
            elif y1 - b1 < 0.3: d = (0, 1, cx, b1)
            if d is None: rep.setdefault("pinvia_inner", []).append(f"{ref}.{num}"); continue
            dx, dy, ex, ey = d; vx, vy = ex + dx * ln, ey + dy * ln; w = self._short_side(g)
            strip = LineString([(cx, cy), (vx, vy)]).buffer(w / 2, cap_style=2)
            vs = Point(vx, vy).buffer(pc.VIA_D / 2 + float(pp.OPT["pinesc_via"]), 16)
            for LL in self.outer:
                others = unary_union([qg for q, qg in self.padpoly[LL] if q["net"] != p["net"] and qg is not None] or [Polygon()])
                k = (unary_union([strip, vs]) if LL == L else vs).difference(others.buffer(self.clr))
                if k.is_empty: continue
                self.gate_keep.setdefault(LL, []).append((p["net"], k))
                self.block[LL] |= self.raster(k.buffer(self.clr)); self.blockgeom[LL].append(k)
            rep.setdefault("pinvia", []).append([f"{ref}.{num}", round(vx, 3), round(vy, 3)])


def main():
    orig = pp.PlannerP
    pp.PlannerP = PlannerG          # pp.main() instantiates pp.PlannerP
    try: pp.main()
    finally: pp.PlannerP = orig


if __name__ == "__main__":
    main()
