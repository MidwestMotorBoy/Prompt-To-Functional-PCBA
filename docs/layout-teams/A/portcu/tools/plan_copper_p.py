#!/usr/bin/env python3
"""plan_copper_p.py: team A (portcu) planner = stagepwr planner A (gate escapes, --sealed, --taps) + ports joinfix +
port-top rules. Same arguments as tools/copper/plan_copper.py. Every rule has its own option (0 = off, stock
behaviour), so rules can be merged and switched one by one:

  --joinfix=1   return_join keeps the signal escape room (tight=False) instead of clearance only (ports worker's
                experiment). A GND pin of a 0.4 mm QFN otherwise gets a GND corridor under its signal neighbours.
  --epstrip=1   rule 1: a return-net (GND) pin of a fine-pitch IC whose own exposed pad is the same net gets a straight
                F.Cu track of pin width from the pin to the EP (or, failing that, to a same-net neighbour pin that has
                one), drawn before any power copper; the pin is then served (no via search, no return_join corridor).
  --directjoin=1 rule 5: a power terminal the tree could not reach ("no path") gets a straight track from its pad
                to the nearest copper of its net on the same layer (pour or same-net pad) when one fits within 2 mm.
  --nogrow_dead=1 rule 3: the grow step does not grow a dead piece of a hard pour: a piece under 3 mm2 that holds no
                via, touches no track or other piece of its net and holds only connector (J) pads
  --nogrow_detour=1 rule 4b: a pour that is only a detour corridor on the other outer layer (zone kinds = {detour})
                is not grown (the B.Cu PP5V detour across the VBUS stem, grown 1.5 mm, left no via site above U501's
                north pin row).
  --gndesc=1    rule 1b: return-net (GND) pins of connectors and of ICs with 8+ pins (pads <= 0.65 mm wide, not
                served by --epstrip) keep the signal escape room from foreign power copper, as signal pins do.
  --pinesc=1    rule 4: escape reservations at ICs with pins of two or more >= 1 A power nets (the PD chips):
                every signal pin gets a strip of pin width straight out of the package (--pinesc_len, default
                0.9 mm past the pad) and a via site at its end (via + --pinesc_via mm, default 0.2) that every other
                net's power copper keeps the clearance from, on both outer layers for the via site. It overrides the
                NEAR_TERM_MM exemption (CC1/CC2 at U501.28/29 sat within 1 mm of the VBUS pad and had no escape).
                --pinesc_refs=U401,U501 limits it to those refs. --pinesc_near=1: only the signal pins within
                NEAR_TERM_MM of a foreign power pad of the same IC (the pins that lose the escape room).
  --connesc=1   rule 3c: every signal pad of a connector (J part with pads <= 0.35 mm wide) gets a strip straight out of
                the connector (--connesc_len, 1.0 mm past the pad; --connesc_w, 0.4 mm wide = a 0.2 mm track plus the
                0.25 mm HighCurrent-to-signal clearance rule) that other nets' power copper keeps the clearance from,
                so a pour wrapped under the pad row cannot seal a CC pin between the VBUS pins.
  --gndpair=1   rule 1c: two neighbouring return-net (GND) pins of the same IC (centres <= 0.55 mm apart) are joined
                pin to pin by a track of pin width, so one via (or EP strip) serves both (U501.27 next to CC1 pin 28 lost
                its via site to pin 28's --pinesc reservation and was left isolated).
  --grow_viaroom=MM rule 4c: the grow step keeps MM mm clear round the signal pins of fine-pitch ICs (8+ pads, pins
                <= 0.45 mm wide) on the OTHER outer layer too, so a grown pour on B.Cu under the PD chip's pin row
                (port 2's PP5V detour blob) leaves via sites for those pins. Only grown copper is cut, never a
                corridor the net needs.
  --mirror_minw=MM rule 3b: a mirror piece (the copy of a pour on the other outer layer) whose mean width
                (2 x area / perimeter) is under MM is dropped with its stitching vias: a thin copy of a stem carries
                little current but walls both outer layers (the VBUS stem from the USB-C connector to the PD chip
                was copied onto B.Cu as a ~0.5 mm strip, so CC lines had no via site on either side of it). (e.g. the USB-C connector's second VBUS pad pair
                A9/B4, which the tree seeds as a pad-only piece; grown 1.5 mm it covered the protector's CC pins).

Imports stagepwr/tools/plan_copper_a.py (which imports the stock planner unchanged)."""
import sys, os, json, math
sys.path.insert(0, '/home/claude/repo/tools/copper')
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/stagepwr/tools')
import numpy as np
from scipy import ndimage
from shapely.geometry import Point, LineString, Polygon, box
from shapely.ops import unary_union
import plan_copper as pc
import plan_copper_a as pa

OPT = dict(joinfix=0, epstrip=0, directjoin=0, nogrow_dead=0, nogrow_detour=0, mirror_minw=0.0, gndesc=0, pinesc=0, pinesc_len=0.9, pinesc_via=0.2, pinesc_refs='', pinesc_near=0, connesc=0, connesc_len=1.0, connesc_w=0.4, gndpair=0, grow_viaroom=0.0)


class PlannerP(pa.PlannerA):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        if OPT["pinesc"]: self.pin_escapes()
        if OPT["connesc"]: self.conn_escapes()

    # ---- rule 3c: connector signal pads keep a straight exit
    def conn_escapes(self):
        rep = []
        for ref, ps in sorted(self.d.by_ref.items()):
            if not ref.startswith("J"): continue
            for L in self.outer:
                pp = [(p, self.d.pad_poly(p, L)) for p in ps if L in p["shapes"] and not p.get("drill")]
                if len(pp) < 6: continue
                x0, y0, x1, y1 = unary_union([g for _, g in pp]).bounds
                for p, g in pp:
                    if self.d.role(p["net"]) != "signal" or self._short_side(g) > 0.35: continue
                    a0, b0, a1, b1 = g.bounds; cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
                    d = None
                    if y1 - b1 < 0.3: d = (0, 1, cx, b1)
                    elif b0 - y0 < 0.3: d = (0, -1, cx, b0)
                    elif a0 - x0 < 0.3: d = (-1, 0, a0, cy)
                    elif x1 - a1 < 0.3: d = (1, 0, a1, cy)
                    if d is None: continue
                    dx, dy, ex, ey = d; ln = float(OPT["connesc_len"]); w = float(OPT["connesc_w"])
                    strip = LineString([(cx, cy), (ex + dx * ln, ey + dy * ln)]).buffer(w / 2, cap_style=2)
                    others = unary_union([qg for q, qg in self.padpoly[L] if q["net"] != p["net"] and qg is not None])
                    k = strip.difference(others.buffer(self.clr))
                    if k.is_empty: continue
                    self.gate_keep.setdefault(L, []).append((p["net"], k))
                    self.block[L] |= self.raster(k.buffer(self.clr))
                    self.blockgeom[L].append(k)
                    rep.append(p["key"])
        self.report.setdefault("portcu", {})["conn_escapes"] = rep

    # ---- rule 4: escape reservations at the PD chips' signal pins
    def pin_escapes(self):
        rep = []; refs = [r for r in str(OPT["pinesc_refs"]).split(",") if r]
        for ref, ps in sorted(self.d.by_ref.items()):
            if not ref.startswith("U") or (refs and ref not in refs): continue
            pw = {p["net"] for p in ps if p["net"] in self.d.power and self.d.current(p["net"]) >= 1.0 and self.d.role(p["net"]) != "return" and p["net"] not in self.d.ret}
            if len(pw) < 2 and not refs: continue
            for L in self.outer:
                pp = [(p, self.d.pad_poly(p, L)) for p in ps if L in p["shapes"] and not p.get("drill")]
                if not pp: continue
                x0, y0, x1, y1 = unary_union([g for _, g in pp]).bounds
                for p, g in pp:
                    if self.d.role(p["net"]) != "signal" or self._short_side(g) > 0.45: continue
                    if OPT["pinesc_near"] and not any(q["net"] in self.d.power and q["net"] not in self.d.ret and self.d.role(q["net"]) != "signal" and qg.distance(g) <= pc.NEAR_TERM_MM + 0.05 for q, qg in pp if q is not p): continue
                    a0, b0, a1, b1 = g.bounds; cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
                    d = None
                    if a0 - x0 < 0.3: d = (-1, 0, a0, cy)
                    elif x1 - a1 < 0.3: d = (1, 0, a1, cy)
                    elif b0 - y0 < 0.3: d = (0, -1, cx, b0)
                    elif y1 - b1 < 0.3: d = (0, 1, cx, b1)
                    if d is None: continue
                    dx, dy, ex, ey = d; ln = float(OPT["pinesc_len"]); w = self._short_side(g)
                    vx, vy = ex + dx * ln, ey + dy * ln
                    strip = LineString([(cx, cy), (vx, vy)]).buffer(w / 2, cap_style=2)
                    vs = Point(vx, vy).buffer(pc.VIA_D / 2 + float(OPT["pinesc_via"]), 16)
                    others = unary_union([qg for q, qg in self.padpoly[L] if q["net"] != p["net"] and qg is not None])
                    keep = unary_union([strip, vs]).difference(others.buffer(self.clr))
                    for LL in self.outer:
                        k = keep if LL == L else vs.difference(unary_union([qg for q, qg in self.padpoly[LL] if q["net"] != p["net"] and qg is not None] or [Polygon()]).buffer(self.clr))
                        if k.is_empty: continue
                        self.gate_keep.setdefault(LL, []).append((p["net"], k))
                        self.block[LL] |= self.raster(k.buffer(self.clr))
                        self.blockgeom[LL].append(k)
                    rep.append(p["key"])
        self.report.setdefault("portcu", {})["pin_escapes"] = rep

    # ---- helpers
    def _track_ok(self, net, L, a, b, w, pg=None, obs=None):
        obs = self.obstacles(net, L) if obs is None else obs
        seg = LineString([a, b]).buffer(w / 2, 4)
        return seg.distance(obs) >= self.clr - 1e-4

    def _draw_track(self, net, L, a, b, w, kind):
        t = dict(net=net, layer=L, a=(round(a[0], 4), round(a[1], 4)), b=(round(b[0], 4), round(b[1], 4)), w=round(w, 3))
        self.tracks.append(t)
        g = LineString([a, b]).buffer(w / 2, 4)
        self.cu[L][self.raster(g) & (self.cu[L] < 0)] = self.netid[net]
        self.gate_keep.setdefault(L, []).append((net, g))      # other nets' power copper keeps the clearance (clip_others)
        self.report.setdefault("portcu", {}).setdefault(kind, []).append([net[-8:], t["a"], t["b"], t["w"]])
        return t

    @staticmethod
    def _short_side(g):
        r = g.minimum_rotated_rectangle; c = list(r.exterior.coords)
        return min(math.hypot(c[1][0] - c[0][0], c[1][1] - c[0][1]), math.hypot(c[2][0] - c[1][0], c[2][1] - c[1][1]))

    # ---- rule 1: GND pin -> own exposed pad
    def ep_strips(self):
        served = set(); L = self.outer[0]
        for ref, pads in sorted(self.d.by_ref.items()):
            if len(pads) < 12: continue
            for net in sorted(self.d.ret):
                on = [p for p in pads if p["net"] == net and L in p["shapes"] and not p.get("drill")]
                eps = [p for p in on if self.d.area(p) >= 1.0]
                if not eps: continue
                ep = unary_union([self.d.pad_poly(p, L) for p in eps]); epnums = {p["num"] for p in eps}
                pins = [p for p in on if p["num"] not in epnums]
                obs = self.obstacles(net, L); done = {}
                for p in sorted(pins, key=lambda p: self.d.pad_poly(p, L).distance(ep)):
                    pg = self.d.pad_poly(p, L); c = pg.centroid; s = self._short_side(pg)
                    if pg.distance(ep) > 0.8 or s > 0.45: continue
                    epi = ep.buffer(-0.08)       # track end at least 0.08 mm inside the EP (KiCad joins it there)
                    cand = sorted((math.hypot(x - c.x, y - c.y), x, y) for x in np.arange(c.x - 1.2, c.x + 1.21, 0.05) for y in np.arange(c.y - 1.2, c.y + 1.21, 0.05)
                                  if math.hypot(x - c.x, y - c.y) <= 1.2 and epi.contains(Point(x, y)))
                    hit = None
                    for w in (min(0.25, s), 0.15):
                        for dd, x, y in cand[:400]:
                            if self._track_ok(net, L, (c.x, c.y), (x, y), w, obs=obs): hit = ((x, y), w); break
                        if hit: break
                    if hit: self._draw_track(net, L, (c.x, c.y), hit[0], hit[1], "ep_strip"); done[p["key"]] = (c.x, c.y); continue
                    # two segments: along the pin's own axis toward the EP (it keeps the pins' spacing), then into the EP
                    ec = ep.centroid; best2 = None
                    for ux, uy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        if (ec.x - c.x) * ux + (ec.y - c.y) * uy <= 0: continue
                        for k in np.arange(0.3, 1.01, 0.05):
                            e = (c.x + ux * k, c.y + uy * k)
                            for w in (min(0.25, s), 0.15):
                                if not self._track_ok(net, L, (c.x, c.y), e, w, obs=obs): continue
                                nn = sorted((math.hypot(x - e[0], y - e[1]), x, y) for x in np.arange(e[0] - 0.4, e[0] + 0.41, 0.05) for y in np.arange(e[1] - 0.4, e[1] + 0.41, 0.05) if epi.contains(Point(x, y)))
                                for dd, x, y in nn[:60]:
                                    if self._track_ok(net, L, e, (x, y), w, obs=obs):
                                        if best2 is None or k + dd < best2[0]: best2 = (k + dd, e, (x, y), w)
                                        break
                                break
                    if best2:
                        _, e, b2, w = best2
                        self._draw_track(net, L, (c.x, c.y), e, w, "ep_strip2"); self._draw_track(net, L, e, b2, w, "ep_strip2"); done[p["key"]] = (c.x, c.y)
                for p in pins:      # a pin with no straight strip: join a served same-net neighbour of the same IC
                    if p["key"] in done: continue
                    pg = self.d.pad_poly(p, L); c = pg.centroid
                    if self._short_side(pg) > 0.45 or pg.distance(ep) > 1.5: continue
                    for k, xy in sorted(done.items(), key=lambda kv: math.hypot(kv[1][0] - c.x, kv[1][1] - c.y)):
                        if math.hypot(xy[0] - c.x, xy[1] - c.y) > 1.3: break
                        if self._track_ok(net, L, (c.x, c.y), xy, 0.15, obs=obs):
                            self._draw_track(net, L, (c.x, c.y), xy, 0.15, "ep_neighbour"); done[p["key"]] = (c.x, c.y); break
                served |= set(done)
        self.ep_served = served

    def gnd_pairs(self):
        n = 0
        for ref, pads in sorted(self.d.by_ref.items()):
            if len(pads) < 8: continue
            for L in self.outer:
                for net in sorted(self.d.ret):
                    on = [p for p in pads if p["net"] == net and L in p["shapes"] and not p.get("drill") and self.d.area(p) < 1.0]
                    obs = None
                    for i, p in enumerate(on):
                        for q in on[i + 1:]:
                            dd = math.hypot(p["x"] - q["x"], p["y"] - q["y"])
                            if dd > 0.55 or dd < 0.05: continue
                            w = min(0.2, self._short_side(self.d.pad_poly(p, L)), self._short_side(self.d.pad_poly(q, L)))
                            obs = self.obstacles(net, L) if obs is None else obs
                            if self._track_ok(net, L, (p["x"], p["y"]), (q["x"], q["y"]), w, obs=obs):
                                self._draw_track(net, L, (p["x"], p["y"]), (q["x"], q["y"]), w, "gnd_pair"); n += 1

    def hot_loops_step(self):
        if OPT["gndpair"]: self.gnd_pairs()
        if OPT["epstrip"]: self.ep_strips()
        return super().hot_loops_step()

    def return_step(self):
        sv = getattr(self, "ep_served", set())
        if not sv: return super().return_step()
        keep = self.d.by_ref
        self.d.by_ref = {r: [p for p in ps if p["key"] not in sv] for r, ps in keep.items()}
        try: super().return_step()
        finally: self.d.by_ref = keep
        self.report["return_pads"]["ep_served"] = sorted(sv)

    # ---- rule 5: a power terminal with no path gets a straight track to its net's copper
    def net_step(self, net):
        super().net_step(net)
        if not OPT["directjoin"]: return
        rep = self.report.get("nets", {}).get(net)
        if not rep or not rep.get("left_to_router"): return
        main = rep.get("main_layer")
        if not main: return
        T = {g["ref"]: g for g in self.d.terminals(net)}; left = []
        for item in rep["left_to_router"]:
            ref = item.split(" ")[0]
            if ref not in T or "no path" not in item: left.append(item); continue
            ok = False; obs = self.obstacles(net, main)
            cu = self.zones.get((net, main), {}).get("geom")
            others = [self.d.pad_poly(q, main) for q in self.d.pads if q["net"] == net and q["ref"] != ref and main in q["shapes"]]
            tgt = unary_union(([cu] if cu is not None else []) + others)
            for p in T[ref]["pads"]:
                if main not in p["shapes"] or ok: continue
                pg = self.d.pad_poly(p, main); c = pg.centroid; s = self._short_side(pg)
                if tgt.is_empty or tgt.distance(pg) > 2.0: continue
                tin = tgt.buffer(-0.12)
                tin = tin if not tin.is_empty else tgt
                q = tin.boundary.interpolate(tin.boundary.project(c)) if not tin.contains(c) else c
                for w in (min(0.5, s), min(0.3, s), 0.2):
                    if self._track_ok(net, main, (c.x, c.y), (q.x, q.y), w, obs=obs):
                        self._draw_track(net, main, (c.x, c.y), (q.x, q.y), w, "direct_join"); ok = True; break
            if ok: rep["joined"].append(ref + " (direct track)")
            else: left.append(item)
        rep["left_to_router"] = left

    # ---- rule 1b: return-net pins of connectors / fine-pitch ICs keep escape room like signal pins
    def _gnd_esc(self):
        if not OPT["gndesc"]: return []
        if getattr(self, "_gesc", None) is None:
            sv = getattr(self, "ep_served", set()); out = {L: [] for L in self.outer}
            for p in self.d.pads:
                if p["net"] not in self.d.ret or p["key"] in sv or p.get("drill"): continue
                if not (p["ref"].startswith("J") or (p["ref"].startswith("U") and len(self.d.by_ref[p["ref"]]) >= 8)): continue
                for L in self.outer:
                    if L not in p["shapes"]: continue
                    g = self.d.pad_poly(p, L)
                    if self._short_side(g) > 0.65 or g.area > 1.0: continue
                    out[L].append(g)
            self._gesc = out
            self._gesc_r = {L: self.raster(unary_union(v).buffer(0.01)) if v else None for L, v in out.items()}
            self.report.setdefault("portcu", {})["gndesc_pads"] = sum(len(v) for v in out.values())
        return self._gesc

    def room(self, net, L, loose=False):
        r = super().room(net, L, loose)
        if loose or self.escape <= 0 or not OPT["gndesc"] or net in self.d.ret: return r
        self._gnd_esc(); m = self._gesc_r.get(L)
        if m is None: return r
        ds = ndimage.distance_transform_edt(~m) * pc.RES - self.clr - self.escape
        return np.minimum(r, ds)

    def clip_others(self, net, L, g, loose_near=None):
        g = super().clip_others(net, L, g, loose_near)
        if not OPT["gndesc"] or net in self.d.ret or g.is_empty: return g
        ps = self._gnd_esc().get(L, [])
        cut = [q.buffer(self.clr + self.escape, 4) for q in ps if loose_near is None or q.distance(loose_near) > pc.NEAR_TERM_MM]
        return g.difference(unary_union(cut)) if cut else g

    # ---- rule 3b: thin mirror strips are dropped
    def mirror_step(self, min_a):
        n0 = len(self.vias)
        super().mirror_step(min_a)
        mw = OPT["mirror_minw"]
        if mw <= 0: return
        new = self.vias[n0:]; drop = []
        for (net, L), z in list(self.zones.items()):
            if z["kinds"] != {"mirror"}: continue
            keep = []
            for q in getattr(z["geom"], "geoms", [z["geom"]]):
                w = 2 * q.area / max(q.length, 1e-6)
                if w >= mw: keep.append(q); continue
                vs = [v for v in new if v["net"] == net and q.buffer(0.05).contains(Point(v["x"], v["y"]))]
                self.unvia(vs); new = [v for v in new if v not in vs]
                self.cu[L][self.raster(q) & (self.cu[L] == self.netid[net])] = -1
                drop.append([net[-10:], L, round(q.area, 1), round(w, 2), len(vs)])
            if keep: z["geom"] = unary_union(keep)
            else: del self.zones[(net, L)]
        self.report.setdefault("portcu", {})["mirror_dropped"] = drop

    # ---- rule 3: dead pour pieces do not grow
    def _dead_pieces(self, net, L, geom):
        out = []
        trs = [LineString([t["a"], t["b"]]).buffer(t["w"] / 2) for t in self.tracks if t["net"] == net and t["layer"] == L]
        for q in getattr(geom, "geoms", [geom]):
            if q.area >= 3.0: continue
            if any(q.buffer(0.01).contains(Point(v["x"], v["y"])) for v in self.vias if v["net"] == net): continue
            if any(q.intersects(t) for t in trs): continue
            refs = {p["ref"] for p, pg in self.padpoly[L] if pg is not None and p["net"] == net and pg.intersects(q)}
            if not refs or not all(r.startswith("J") for r in refs): continue      # only a connector's duplicate pins (joined in the plug)
            out.append(q)
        return out

    def grow_step(self, step=0.5):
        if not (OPT["nogrow_dead"] or OPT["nogrow_detour"] or OPT["grow_viaroom"] > 0): return super().grow_step(step)
        vr = {}
        if OPT["grow_viaroom"] > 0:
            for L in self.outer:
                Lo = [l for l in self.outer if l != L][0]; gs = []
                for p in self.d.pads:
                    if not p["ref"].startswith("U") or len(self.d.by_ref[p["ref"]]) < 8 or Lo not in p["shapes"] or p.get("drill"): continue
                    if self.d.role(p["net"]) != "signal": continue
                    g = self.d.pad_poly(p, Lo)
                    if self._short_side(g) <= 0.45: gs.append(g.buffer(OPT["grow_viaroom"], 4))
                vr[L] = unary_union(gs) if gs else None
        rep = {}; nets = sorted(self.d.power, key=lambda n: (-self.d.current(n), n)); left = self.grow
        dead = {}
        for (net, L), z in self.zones.items():
            if OPT["nogrow_dead"] and L in self.outer and not z["soft"]: dead[(net, L)] = self._dead_pieces(net, L, z["geom"])
        frozen = {k for k, z in self.zones.items() if OPT["nogrow_detour"] and z["kinds"] <= {"detour"}}
        self.report.setdefault("portcu", {})["not_grown_detours"] = sorted(f"{n} {L}" for n, L in frozen)
        self.report.setdefault("portcu", {})["dead_pieces"] = {f"{n} {L}": [[round(q.centroid.x, 2), round(q.centroid.y, 2), round(q.area, 2)] for q in v] for (n, L), v in dead.items() if v}
        while left > 1e-6:
            d = min(step, left); left -= d
            for net in nets:
                for L in self.outer:
                    z = self.zones.get((net, L))
                    if not z or z["soft"] or "mirror" in z["kinds"] or (net, L) in frozen: continue
                    base = z["geom"]
                    dd = dead.get((net, L))
                    if dd: base = base.difference(unary_union([q.buffer(0.02) for q in dd]))
                    if base.is_empty: continue
                    g = base.buffer(d, 4).intersection(self.inside)
                    if dd: g = g.difference(unary_union([q.buffer(self.clr + 0.02) for q in dd]))       # keep apart: a dead piece stays its pad
                    if vr.get(L) is not None: g = g.difference(vr[L].difference(z["geom"]))      # only new (grown) copper is kept out
                    g = self.clip_others(net, L, g)
                    tr = [LineString([t["a"], t["b"]]).buffer(t["w"] / 2 + self.clr, 4) for t in self.tracks if t["layer"] == L and t["net"] != net]
                    bl = [b.buffer(self.clr, 4) for b in self.blockgeom[L]] + self.npth
                    if tr or bl: g = g.difference(unary_union(tr + bl))
                    g = unary_union([q for q in getattr(g, "geoms", [g]) if q.intersects(base) and q.intersection(base).area > 0.05])
                    if g.is_empty: continue
                    a0 = z["geom"].area; z["geom"] = unary_union([z["geom"], g]); self.cu[L][self.raster(g) & (self.cu[L] < 0)] = self.netid[net]
                    rep[f"{net} {L}"] = round(rep.get(f"{net} {L}", 0) + z["geom"].area - a0, 1)
        self.report["grown_mm2"] = rep
        if pa.TAPS:
            for net in sorted(n for n in self.d.power if self.d.power[n]["kind"] == "switching"): self.taps(net)

    def return_join(self, net, L, sh):
        if not OPT["joinfix"]: return super().return_join(net, L, sh)
        RES, NEAR = pc.RES, pc.NEAR_TERM_MM
        z = self.zones.get((net, L)); start = self.raster(sh)
        if z is None: return False
        m = self.raster(z["geom"].buffer(-0.1, 4).buffer(0.1, 4))
        lab, _ = ndimage.label(m | start)
        ids = {lab[int((v["y"] - self.y0) / RES), int((v["x"] - self.x0) / RES)] for v in self.vias if v["net"] == net}
        ids -= {0} | set(np.unique(lab[start]).tolist())
        if not ids: return False
        goal = np.isin(lab, list(ids))
        pth, rr = self.path(net, L, start, goal, pc.MIN_W, ndimage.binary_dilation(start | goal, iterations=int(NEAR / RES)), tight=False)
        if pth is None or len(pth) > 6 / RES: return False
        cor = self.clip_others(net, L, unary_union([self.corridor(pth, rr, pc.MIN_W), sh]), loose_near=sh.buffer(NEAR))
        self.add_zone(net, L, cor, 22, kind="return join"); self.spine(net, L, pth); return True


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
    pa.GATE_LEN = float(opt.pop("gate_len", pa.GATE_LEN)); pa.GATE_W = float(opt.pop("gate_w", pa.GATE_W)); pa.GATE_VIA = float(opt.pop("gate_via", pa.GATE_VIA))
    pa.ALL_GATES = int(opt.pop("all_gates", pa.ALL_GATES)); pa.SEALED = int(opt.pop("sealed", pa.SEALED)); pa.TAPS = int(opt.pop("taps", pa.TAPS))
    for k in list(OPT):
        if k in opt: OPT[k] = type(OPT[k])(float(opt.pop(k))) if isinstance(OPT[k], (int, float)) else opt.pop(k)
    intent = json.load(open(a[3])) if len(a) > 3 else None
    pl = PlannerP(a[0], a[1], intent, escape=float(opt.get("escape", 0.4)), grow=float(opt.get("grow", 1.5)), mirror=float(opt.get("mirror", 3)))
    spec = pl.run(); json.dump(spec, open(a[2], "w"))
    R = spec["report"]
    print("portcu options", json.dumps(OPT))
    for n, r in R.get("nets", {}).items():
        print(f"{n}: {r['current_a']} A, {r['terminals']} terminals, span {r['span_mm']} mm, layer {r.get('main_layer')}{' + ' + r['inner_layer'] if 'inner_layer' in r else ''}, vias {r['vias']}, left to router {r['left_to_router']}")
    print("hot loops", json.dumps(R.get("hot_loops")))
    print("return pads", json.dumps({k: (v if not isinstance(v, list) else v[:12]) for k, v in R["return_pads"].items()}))
    print("gate escapes", json.dumps(R.get("gate_escapes")))
    print("taps", json.dumps(R.get("taps")))
    for k in ("portcu",):
        if k in R: print(k, json.dumps(R[k]))
    print(f"{len(spec['zones'])} zones, {len(spec['vias'])} vias, {len(spec['tracks'])} tracks, {R['seconds']} s; notes: {R['notes']}")


if __name__ == "__main__":
    main()
