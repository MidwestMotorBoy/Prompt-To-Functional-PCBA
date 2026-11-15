#!/usr/bin/env python3
"""plan_copper_v.py: team A r4_vbus planner = portcu planner P (portcu/tools/plan_copper_p.py, imported unchanged) +
one rule behind its own option. Same arguments as plan_copper_p.py, plus:

  --padpair=MODE  rule V1, after the grow step (and after P's taps): for every power net (not the return net) and every
                series terminal with 2+ pads, the planner's own copper (zones, tracks, vias, pads; through vias and
                plated holes join the layers; pads of one part are NOT joined for free) is split into pieces. A pad that
                is not on the net's main piece (the piece holding the most terminal parts) is joined to it:
                  1  a same-layer link: straight, L, or a grid path (<= 1.5 x straight + 3 mm, escape room kept at
                     signal pads) of width --padpair_w (first that fits)
                  2  vias in or at the dead pad (place_vias: legal on both outer layers, prefers in-pad), then a
                     straight or L track on the other outer layer to the main piece there (its copy pour, or any of its
                     through vias), widths --padpair_w
                  3  as 2, but the link may be a grid path on the other outer layer and then the free inner layers,
                     widths --padpair_w (default thin)
                The pad pair itself is not grown (draw after grow; P's --nogrow_dead keeps it a pad), so the protector's
                CC pins next to it stay free. Typical case: the USB-C connector's second VBUS pin pair (A9/B4 / A4/B9),
                seeded as a pad-only piece.
  --padpair_w=0.8,0.6,0.5,0.4   link widths tried in order (mode 3 default 0.5,0.4,0.3)
  --padpair_vias=N              vias per dead pad (modes 2, 3; default 1)
  --padpair_len=MM              longest link (default 8 mm)
  --padpair_minpad=MM           pads narrower than this are skipped (fine-pitch IC pins such as a PD chip's small VBUS
                                supply pin: the router finishes those; default 0.45)
  --padpair_live=1  modes 2/3: always bridge pad to pad (via in the dead pad, via in a live pad of the same part, link
                    on the other layer), never to the net's other copper there, so both ports get the same bridge
  When no main copper is in reach on the other layer (port 2: the B.Cu VBUS copy is 10.8 mm away), modes 2/3 also
  put a via in a live pad of the same part (in-pad only) and link the two vias.
No refs or net names are typed in: nets, terminals and their pads come from roles.py like the stock planner."""
import sys, os, json, math
sys.path.insert(0, '/home/claude/repo/tools/copper')
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/stagepwr/tools')
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/portcu/tools')
import numpy as np
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
import plan_copper as pc
import plan_copper_a as pa
import plan_copper_p as pp

VOPT = dict(padpair=0, padpair_w='', padpair_vias=1, padpair_len=8.0, padpair_minpad=0.45, padpair_live=0)


class PlannerV(pp.PlannerP):
    def grow_step(self, step=0.5):
        super().grow_step(step)
        if os.environ.get("R4V_DUMP"):       # debug: the planner state just before the rule, for tools/padpair_dbg.py
            import pickle; pickle.dump(self, open(os.environ["R4V_DUMP"], "wb"))
        if int(VOPT["padpair"]): self.pad_pairs(int(VOPT["padpair"]))

    # ---- the planner's own copper of one net as connected pieces
    def _pieces(self, net):
        geo = {L: [] for L in self.layers}
        for (n, L), z in self.zones.items():
            if n == net and not z["geom"].is_empty: geo[L].append(z["geom"].buffer(-0.05, 4).buffer(0.05, 4))   # necks KiCad's fill drops
        for t in self.tracks:
            if t["net"] == net: geo[t["layer"]].append(LineString([t["a"], t["b"]]).buffer(t["w"] / 2, 4) if t["a"] != t["b"] else Point(t["a"]).buffer(t["w"] / 2))
        vs = [v for v in self.vias if v["net"] == net]
        for v in vs:
            for L in self.layers: geo[L].append(Point(v["x"], v["y"]).buffer(v.get("size", pc.VIA_D) / 2, 8))
        pads = [p for p in self.d.pads if p["net"] == net]
        for p in pads:
            for L in p["shapes"]:
                if L in geo: geo[L].append(self.d.pad_poly(p, L))
        pieces = {}
        for L in self.layers:
            u = unary_union([g.buffer(0.001) for g in geo[L] if g is not None and not g.is_empty]) if geo[L] else None
            pieces[L] = list(getattr(u, "geoms", [u])) if u is not None and not u.is_empty else []
        par = {(L, k): (L, k) for L in self.layers for k in range(len(pieces[L]))}
        def f(i):
            while par[i] != i: par[i] = par[par[i]]; i = par[i]
            return i
        trees = {L: STRtree(pieces[L]) for L in self.layers if pieces[L]}
        def at(L, pt):
            if L not in trees: return None
            for k in trees[L].query(pt):
                if pieces[L][k].intersects(pt): return (L, int(k))
            return None
        bar = [(Point(v["x"], v["y"]), self.layers) for v in vs] + [(Point(p["x"], p["y"]), [L for L in self.layers if L in p["shapes"]]) for p in pads if p.get("drill")]
        for pt, ls in bar:
            h = [x for x in (at(L, pt) for L in ls) if x is not None]
            for x in h[1:]:
                a, b = f(h[0]), f(x)
                if a != b: par[a] = b
        def comps(p):
            out = set()
            for L in p["shapes"]:
                if L not in trees: continue
                h = at(L, self.d.pad_poly(p, L).representative_point())
                if h is not None: out.add(f(h))
            return out
        return pieces, f, comps

    def pad_pairs(self, mode):
        rep = []
        ws = [float(x) for x in str(VOPT["padpair_w"]).split(",") if x] or ([0.5, 0.4, 0.3] if mode == 3 else [0.8, 0.6, 0.5, 0.4])
        for net in sorted(n for n in self.d.power if n not in self.d.ret):
            T = self.d.terminals(net)
            multi = [g for g in T if g["kind"] == "series" and len(g["pads"]) >= 2]
            if not multi: continue
            def state():
                pieces, f, comps = self._pieces(net); score = {}
                for g in T:
                    for p in g["pads"]:
                        for c in comps(p): score.setdefault(c, set()).add(g["ref"])
                return pieces, f, comps, (max(score, key=lambda c: len(score[c])) if score else None)
            pieces, f, comps, main = state()
            if main is None: continue
            for g in multi:
                on = [p for p in g["pads"] if main in comps(p)]
                if not on: continue                      # the whole terminal is off: not this rule's case (directjoin)
                dead = [p for p in g["pads"] if main not in comps(p)]
                done = set()
                for p in dead:
                    if p["key"] in done: continue
                    Lp = [L for L in p["shapes"] if L in self.outer]
                    if not Lp or self._short_side(self.d.pad_poly(p, Lp[0])) < float(VOPT["padpair_minpad"]):     # a fine-pitch pin: the router's
                        rep.append(dict(net=net, pads=[p["key"]], mode=mode, drawn=False, why="fine-pitch pin")); continue
                    # pads of the same part that share one dead piece are served together (A9 and B4 overlap)
                    mates = [q for q in dead if comps(q) & comps(p)]
                    ok = self._join_dead(net, p, mode, ws, pieces, f, main, live=on)
                    rep.append(dict(net=net, pads=[q["key"] for q in mates], mode=mode, drawn=ok))
                    done |= {q["key"] for q in mates}
                    if ok: pieces, f, comps, main = state()
        self.report.setdefault("r4v", {})["padpair"] = rep

    def _main_on(self, L, pieces, f, main, net):
        g = [q for k, q in enumerate(pieces[L]) if f((L, k)) == main]
        return unary_union(g) if g else None

    def _obs(self, net, L, esc=True):
        """Exact shapes a link of net on L keeps the clearance from: P's obstacles (other nets' pads, copper, vias,
        tracks, holes) + reserved strips (connector exits, pin escapes, gate escapes of other nets, lanes, keep-outs)
        + with esc the escape room round other nets' signal pads (a link must not take a signal's way out)."""
        g = [self.obstacles(net, L)] + list(self.blockgeom[L]) + [k for n, k in getattr(self, "gate_keep", {}).get(L, []) if n != net]
        if esc and self.escape > 0:
            g += [pg.buffer(self.escape, 4) for q, pg in self.padpoly[L] if pg is not None and q["net"] != net and self.d.role(q["net"]) == "signal"]
        return unary_union(g)

    def _link(self, net, L, a, tgt, ws, kind, grid=False, esc=True):
        """Track(s) from point a to the shape tgt on layer L: straight, then L-shaped, then (grid) a grid path.
        Returns the width drawn or None."""
        obs = self._obs(net, L, esc)
        tin = tgt.buffer(-0.1); tin = tin if not tin.is_empty else tgt
        q = tin.boundary.interpolate(tin.boundary.project(Point(a))) if not tin.contains(Point(a)) else Point(a)
        b = (q.x, q.y); maxl = float(VOPT["padpair_len"])
        if math.hypot(b[0] - a[0], b[1] - a[1]) > maxl: return None
        inside = lambda s: self.inside.contains(LineString(s).buffer(1e-3)) if len(s) > 1 else True
        okw = lambda u, v, w: LineString([u, v]).buffer(w / 2, 4).distance(obs) >= self.clr - 1e-4
        for w in ws:
            if okw(a, b, w) and inside([a, b]):
                self._draw_track(net, L, a, b, w, kind); return w
            for c in ((a[0], b[1]), (b[0], a[1])):
                if okw(a, c, w) and okw(c, b, w) and inside([a, c, b]) and tgt.buffer(0.01).contains(Point(b)):
                    self._draw_track(net, L, a, c, w, kind); self._draw_track(net, L, c, b, w, kind); return w
        if not grid: return None
        start = self.raster(Point(a).buffer(0.15)); goal = self.raster(tgt) & ~start
        if not goal.any(): return None
        for w in ws:
            pth, rr = self.path(net, L, start, goal, w, start, tight=False)
            if pth is None: continue
            line = LineString([a] + [self.xy(i, j) for i, j in pth]).simplify(0.05)
            st = math.hypot(b[0] - a[0], b[1] - a[1])
            if line.length > min(maxl, pc.WIND_MAX * st + pc.WIND_SLACK_MM): continue
            c = list(line.coords)
            if all(okw(u, v, w) for u, v in zip(c, c[1:])) and inside(c):
                for u, v in zip(c, c[1:]): self._draw_track(net, L, u, v, w, kind)
                return w
        return None

    def _via_sites(self, net, pg, n):
        """Up to n via sites in the dead pad (else within 0.6 mm of it), checked on exact shapes: clearance to every
        other net's copper, pads and reserved strips on both outer layers, board edge margin, hole gaps, no-via
        keep-outs. In-pad first, then nearest the pad centre."""
        r = pc.VIA_D / 2; c = pg.centroid; x0, y0, x1, y1 = pg.buffer(0.6).bounds
        obs = {L: self._obs(net, L, esc=False) for L in self.outer}
        inner = self.inside.buffer(-r)
        cand = []
        for x in np.arange(x0, x1 + 1e-9, 0.025):
            for y in np.arange(y0, y1 + 1e-9, 0.025):
                pt = Point(x, y); inpad = pg.contains(pt.buffer(r * 0.5))
                if not inner.contains(pt) or pg.distance(pt) > 0.6: continue
                cand.append((0 if inpad else 1, pt.distance(c), x, y))
        cand.sort(); out = []
        holes = [(v["x"], v["y"], pc.VIA_DRILL) for v in self.vias] + self.drilled
        for _, _, x, y in cand:
            if len(out) >= n: break
            i, j = int((y - self.y0) / pc.RES), int((x - self.x0) / pc.RES)
            if self.novia[i, j]: continue
            d = Point(x, y).buffer(r, 16)
            if any(d.distance(obs[L]) < self.clr + 0.01 for L in self.outer): continue
            if any(math.hypot(x - a, y - b) < (dd + pc.VIA_DRILL) / 2 + (pc.PAD_HOLE_GAP if dd >= 0.5 else pc.HOLE_GAP) for a, b, dd in holes): continue
            v = dict(net=net, x=round(float(x), 3), y=round(float(y), 3), size=pc.VIA_D, drill=pc.VIA_DRILL)
            out.append(v); self.vias.append(v); holes.append((x, y, pc.VIA_DRILL))
            self.viamap[self.disk(x, y, r) & (self.viamap < 0)] = self.netid[net]
        return out

    def _join_dead(self, net, p, mode, ws, pieces, f, main, live=()):
        L0 = [L for L in p["shapes"] if L in self.outer]
        if not L0: return False
        L0 = L0[0]; pg = self.d.pad_poly(p, L0); c = pg.centroid
        if mode == 1:
            tgt = self._main_on(L0, pieces, f, main, net)
            return bool(tgt is not None and self._link(net, L0, (c.x, c.y), tgt, ws, "padpair_strip", grid=True))
        # modes 2 and 3: vias at the pad, then a link on another layer
        vs = self._via_sites(net, pg, int(VOPT["padpair_vias"]))
        self.report.setdefault("r4v", {}).setdefault("via_sites", []).append(dict(pad=p["key"], vias=[[v["x"], v["y"]] for v in vs]))
        if not vs: return False
        for v in vs:      # a via outside the pad gets a short link on the pad's layer (escape room not needed: own pad)
            if not pg.buffer(0.01).contains(Point(v["x"], v["y"])):
                if not self._link(net, L0, (v["x"], v["y"]), pg, [min(0.5, self._short_side(pg)), 0.3], "padpair_vialink", esc=False):
                    self.unvia(vs); return False
        others = [L for L in self.outer if L != L0] + (self.inner_free if mode == 3 else [])
        for Lo in (others if not int(VOPT["padpair_live"]) else []):
            tz = self._main_on(Lo, pieces, f, main, net)
            if tz is None: continue
            for v in vs:
                w = self._link(net, Lo, (v["x"], v["y"]), tz, ws, "padpair_link", grid=(mode == 3))
                if w:
                    self.report.setdefault("r4v", {}).setdefault("links", []).append(dict(net=net, pad=p["key"], layer=Lo, w=w, via=[v["x"], v["y"]]))
                    return True
        # no main copper within reach on another layer: a via in a live pad of the same part, and a link via to via
        for q in live:
            Lq = [L for L in q["shapes"] if L in self.outer]
            if not Lq or q.get("drill"): continue
            lv = self._via_sites(net, self.d.pad_poly(q, Lq[0]), 1)
            if not lv: continue
            if not self.d.pad_poly(q, Lq[0]).buffer(0.01).contains(Point(lv[0]["x"], lv[0]["y"])): self.unvia(lv); continue    # in-pad only
            for Lo in others:
                for v in vs:
                    w = self._link(net, Lo, (v["x"], v["y"]), Point(lv[0]["x"], lv[0]["y"]).buffer(pc.VIA_D / 2), ws, "padpair_link", grid=(mode == 3))
                    if w:
                        self.report.setdefault("r4v", {}).setdefault("links", []).append(dict(net=net, pad=p["key"], layer=Lo, w=w, via=[v["x"], v["y"]], live_via=[lv[0]["x"], lv[0]["y"], q["key"]]))
                        return True
            self.unvia(lv)
        self.unvia(vs); return False


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
    for k in list(VOPT):
        if k in opt:
            v = opt.pop(k); VOPT[k] = v if isinstance(VOPT[k], str) else type(VOPT[k])(float(v))
    pa.GATE_LEN = float(opt.pop("gate_len", pa.GATE_LEN)); pa.GATE_W = float(opt.pop("gate_w", pa.GATE_W)); pa.GATE_VIA = float(opt.pop("gate_via", pa.GATE_VIA))
    pa.ALL_GATES = int(opt.pop("all_gates", pa.ALL_GATES)); pa.SEALED = int(opt.pop("sealed", pa.SEALED)); pa.TAPS = int(opt.pop("taps", pa.TAPS))
    for k in list(pp.OPT):
        if k in opt: pp.OPT[k] = type(pp.OPT[k])(float(opt.pop(k))) if isinstance(pp.OPT[k], (int, float)) else opt.pop(k)
    intent = json.load(open(a[3])) if len(a) > 3 else None
    pl = PlannerV(a[0], a[1], intent, escape=float(opt.get("escape", 0.4)), grow=float(opt.get("grow", 1.5)), mirror=float(opt.get("mirror", 3)))
    spec = pl.run(); json.dump(spec, open(a[2], "w"))
    R = spec["report"]
    print("portcu options", json.dumps(pp.OPT)); print("r4v options", json.dumps(VOPT))
    for n, r in R.get("nets", {}).items():
        print(f"{n}: {r['current_a']} A, {r['terminals']} terminals, span {r['span_mm']} mm, layer {r.get('main_layer')}{' + ' + r['inner_layer'] if 'inner_layer' in r else ''}, vias {r['vias']}, left to router {r['left_to_router']}")
    print("hot loops", json.dumps(R.get("hot_loops")))
    print("return pads", json.dumps({k: (v if not isinstance(v, list) else v[:12]) for k, v in R["return_pads"].items()}))
    print("gate escapes", json.dumps(R.get("gate_escapes")))
    print("taps", json.dumps(R.get("taps")))
    for k in ("portcu", "r4v"):
        if k in R: print(k, json.dumps(R[k]))
    print(f"{len(spec['zones'])} zones, {len(spec['vias'])} vias, {len(spec['tracks'])} tracks, {R['seconds']} s; notes: {R['notes']}")


if __name__ == "__main__":
    main()
