#!/usr/bin/env python3
"""plan_copper_m.py: team A round-5 merged planner M = planner B (r4_bcu) + planner V (r4_vbus) + planner Q (r4_port1),
all subclasses of portcu planner P, imported unchanged and combined by cooperative multiple inheritance:

    class PlannerM(PlannerB, PlannerV, PlannerQ)      MRO: M -> B -> V -> Q -> P -> A -> stock Planner

Every overridden method of B, V and Q calls super() exactly once, so each method runs the three in MRO order.
Composition, method by method (decided explicitly; see NOTES.md):
  __init__        only Q: P.__init__ (pin escapes, conn escapes), then Q's conn_escapes_big / gate_vias.
  pin_escapes     only Q (records its own reservations for --gndtie).
  return_step     only Q (--gndtie after the stock return step).
  hot_loops_step  only B (--ret_band after P's gnd pairs / ep strips and the stock loops).
  net_step/detour only B (switch-node detour width / via count).
  mirror_step     only B (--mirror_skip_supply, --mirror_maxa, --mirror_minw2).
  taps            only B (--tap_max); called from planner A's grow_step after the stock grow.
  run             only B (adds the r4_bcu area report).
  grow_step       all three, in this order:
                    1. B: tag the detour / via-stub zones that must not grow (--pw_nogrow, --sw_nogrow, --stub_nogrow)
                    2. P: stock grow with --nogrow_dead (the dead VBUS pair stays an ungrown pad), then planner A's
                       taps (B's --tap_max applies)
                    3. Q: --padjoin thin tracks from 2-pad parts' power pads to their pour (needs the grown pour)
                    4. V: --padpair dead-pair via + B.Cu link (after the grow, so the link is never grown and it sees
                       Q's pad joins as obstacles)
                    5. B: untag
                  (MRO B -> V -> Q gives exactly that: B pre, V -> Q -> P, then Q post, V post, B post.)
  M-only rules (round 5, each behind its own option, 0 = off):
  --capjoin=1     after V: a shunt terminal pad (a power net's cap) that is not on its net's main copper piece
                  (V's piece analysis) gets joined: vias in/at the pad + link on another layer to the main piece,
                  or a same-layer link (V's _link / _via_sites). For C521 (port-2 68 uF AC bulk on B.Cu) and the
                  VAC caps C409/C509.  --capjoin_w=0.8,0.6,0.5,0.4,0.3  --capjoin_vias=N (default 2)
                  --capjoin_minpad=MM (pads narrower are skipped, 0.45)  --capjoin_refs=  (empty: all)
One main() parses VOPT (V), pp.OPT (P + Q's QOPT), OPTB (B), MOPT (M) and planner A's module options."""
import sys, os, json, math
sys.path.insert(0, '/home/claude/repo/tools/copper')
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/stagepwr/tools')
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/portcu/tools')
for _d in ('r4_vbus', 'r4_port1', 'r4_bcu'):
    sys.path.insert(0, f'/home/claude/repo/docs/layout-teams/A/{_d}/tools')
import numpy as np
from shapely.geometry import Point, LineString
import plan_copper as pc
import plan_copper_a as pa
import plan_copper_p as pp
import plan_copper_v as pv
import plan_copper_q as pq      # adds QOPT to pp.OPT
import plan_copper_b as pb

MOPT = dict(gatevia_chk=0, capjoin=0, capjoin_w='', capjoin_vias=2, capjoin_minpad=0.45, capjoin_refs='', capjoin_len=16.0)


class PlannerM(pb.PlannerB, pv.PlannerV, pq.PlannerQ):
    # ---- M rule --gatevia_chk=1: Q's --gatevia draws the gate-escape via at planner A's reserved site without a check
    # against the other outer layer. With r4_bcu's rot-90 Q402 the LG2 site (Q402.8) lands 0.11 mm from the bottom-side
    # AC bulk cap C421/C521 pad 1 (4 DRC errors on the merged board). Each gate via is checked on exact shapes against
    # every other net's pad on both outer layers (copper clearance and via-hole-to-pad 0.2 mm) and the other vias; a
    # via that fails is moved further out along the escape direction (0.05 mm steps, up to +0.8 mm, staying clear of
    # the FET's own other-net pads), else it and its track are dropped (the gate is then left to the router, as in k1).
    def gate_vias(self):
        n0, t0 = len(self.vias), len(self.tracks)
        super().gate_vias()
        if not int(MOPT["gatevia_chk"]): return
        new_v = self.vias[n0:]; new_t = self.tracks[t0:]; keep_v, keep_t = [], []; rep = []
        r = pc.VIA_D / 2; need_cu = r + max(self.clr, pc.MIN_CLR) + 0.02; need_hole = pc.VIA_DRILL / 2 + 0.2 + 0.02
        others = lambda net: [(q, g) for L in self.outer for q, g in self.padpoly[L] if g is not None and q["net"] != net]
        def ok(net, x, y, tr_w, a):
            pt = Point(x, y)
            for q, g in others(net):
                d = g.distance(pt)
                if d < need_cu or d < need_hole: return False
            if any(math.hypot(v["x"] - x, v["y"] - y) < pc.VIA_PITCH for v in self.vias[:n0] + keep_v): return False
            if not self.inside.buffer(-r - pc.EDGE_MM).contains(pt): return False
            return True
        for v, t in zip(new_v, new_t):
            net = v["net"]; a, b = t["a"], (v["x"], v["y"]); ux, uy = b[0] - a[0], b[1] - a[1]; ln = math.hypot(ux, uy) or 1; ux, uy = ux / ln, uy / ln
            placed = None
            for k in range(0, 17):
                x, y = round(b[0] + ux * 0.05 * k, 3), round(b[1] + uy * 0.05 * k, 3)
                if not ok(net, x, y, t["w"], b): continue
                seg = LineString([a, (x, y)]).buffer(t["w"] / 2)
                if any(seg.distance(g) < self.clr for q, g in self.padpoly[t["layer"]] if g is not None and q["net"] != net): continue
                placed = (x, y, k); break
            if placed is None: rep.append([net[-6:], b, "dropped"]); continue
            x, y, k = placed; v = dict(v, x=x, y=y); t = dict(t, b=(x, y)); keep_v.append(v); keep_t.append(t)
            if k: rep.append([net[-6:], b, "moved +%.2f" % (0.05 * k), [x, y]])
        self.vias[n0:] = keep_v; self.tracks[t0:] = keep_t
        self.report.setdefault("r5m", {})["gatevia_chk"] = rep

    def grow_step(self, step=0.5):
        super().grow_step(step)          # B pre -> V( Q( P grow + A taps ) + Q padjoin ) + V padpair -> B post
        if os.environ.get("R5M_DUMP"):       # debug: planner state just before the M rules
            import pickle; pickle.dump(self, open(os.environ["R5M_DUMP"], "wb"))
        if int(MOPT["capjoin"]): self.cap_joins()

    # ---- M rule: shunt (cap) terminal pads off the main piece of their power net
    def cap_joins(self):
        rep = []
        ws = [float(x) for x in str(MOPT["capjoin_w"]).split(",") if x] or [0.8, 0.6, 0.5, 0.4, 0.3]
        refs = [r for r in str(MOPT["capjoin_refs"]).split(",") if r]
        saved = dict(pv.VOPT)
        pv.VOPT["padpair_len"] = float(MOPT["capjoin_len"]); pv.VOPT["padpair_vias"] = int(MOPT["capjoin_vias"]); pv.VOPT["padpair_live"] = 0
        try:
            for net in sorted(n for n in self.d.power if n not in self.d.ret):
                T = self.d.terminals(net)
                caps = [g for g in T if g["kind"] == "shunt" and (not refs or g["ref"] in refs)]
                if not caps: continue
                def state():
                    pieces, f, comps = self._pieces(net); score = {}
                    for g in T:
                        for p in g["pads"]:
                            for c in comps(p): score.setdefault(c, set()).add(g["ref"])
                    return pieces, f, comps, (max(score, key=lambda c: len(score[c])) if score else None)
                pieces, f, comps, main = state()
                if main is None: continue
                for g in caps:
                    for p in g["pads"]:
                        if main in comps(p): continue
                        Lp = [L for L in p["shapes"] if L in self.outer]
                        if not Lp or self._short_side(self.d.pad_poly(p, Lp[0])) < float(MOPT["capjoin_minpad"]):
                            rep.append(dict(net=net[-14:], pad=p["key"], drawn=False, why="small")); continue
                        L0 = Lp[0]; pg = self.d.pad_poly(p, L0); c = pg.centroid
                        ok = None; snap = self._snap()
                        # 0. a via already on the pad's piece (the planner's via stub) linked on another layer to the main copper
                        ok = self._cap_old_via_join(net, p, comps, pieces, f, main, ws)
                        # 1. same-layer link to the main copper
                        tgt = self._main_on(L0, pieces, f, main, net)
                        if not ok and tgt is not None:
                            w = self._glink(net, L0, (c.x, c.y), tgt, ws, "capjoin_strip")
                            if w: ok = f"same-layer {w} mm on {L0}"
                        # 2. vias at the pad, link on the other outer layer (or the via lands on main copper there)
                        if not ok: ok = self._cap_via_join(net, p, L0, pg, ws, pieces, f, main)
                        if not ok: self._restore(snap)
                        rep.append(dict(net=net[-14:], pad=p["key"], drawn=bool(ok), how=ok))
                        if ok: pieces, f, comps, main = state()
        finally:
            pv.VOPT.update(saved)
        self.report.setdefault("r5m", {})["capjoin"] = rep

    def _snap(self):
        return dict(tracks=len(self.tracks), vias=list(self.vias), viamap=self.viamap.copy(), cu={L: a.copy() for L, a in self.cu.items()},
                    gk={L: len(v) for L, v in self.gate_keep.items()}, rep=json.dumps(self.report.get("portcu", {}), default=str))

    def _restore(self, s):
        del self.tracks[s["tracks"]:]; self.vias[:] = s["vias"]; self.viamap = s["viamap"]
        for L, a in s["cu"].items(): self.cu[L] = a
        for L in list(self.gate_keep):
            del self.gate_keep[L][s["gk"].get(L, 0):]
        self.report["portcu"] = json.loads(s["rep"])

    def _glink(self, net, L, a, tgt, ws, kind, esc=True):
        """V's _link (straight, then L), then a grid path oriented from a (V's grid fallback appends the dijkstra
        path in goal-to-start order, so its length check rejects every path; fixed here, V left unchanged)."""
        w = self._link(net, L, a, tgt, ws, kind, grid=False, esc=esc)
        if w: return w
        obs = self._obs(net, L, esc); maxl = float(pv.VOPT["padpair_len"])
        start = self.raster(Point(a).buffer(0.15)); goal = self.raster(tgt) & ~start
        if not goal.any(): return None
        st = tgt.distance(Point(a))
        inside = lambda c: self.inside.contains(LineString(c).buffer(1e-3))
        for w in ws:
            pth, rr = self.path(net, L, start, goal, w, start, tight=False)
            if pth is None: continue
            pts = [self.xy(i, j) for i, j in pth]
            if math.dist(pts[0], a) > math.dist(pts[-1], a): pts = pts[::-1]
            line = LineString([a] + pts).simplify(0.05)
            if line.length > min(maxl, pc.WIND_MAX * st + pc.WIND_SLACK_MM): continue
            c = list(line.coords)
            if all(LineString([u, v]).buffer(w / 2, 4).distance(obs) >= self.clr - 1e-4 for u, v in zip(c, c[1:])) and inside(c):
                for u, v in zip(c, c[1:]): self._draw_track(net, L, u, v, w, kind)
                return w
        return None

    def _cap_old_via_join(self, net, p, comps, pieces, f, main, ws):
        """The pad's own piece already has through vias (a bottom-side cap's via stub): a grid link on another outer
        layer from one of them to the main copper there."""
        mine = comps(p)
        if not mine: return None
        Lp = [L for L in p["shapes"] if L in self.outer][0]
        for v in [v for v in self.vias if v["net"] == net]:
            pt = Point(v["x"], v["y"])
            hit = [k for k, q in enumerate(pieces[Lp]) if q.intersects(pt) and f((Lp, k)) in mine]
            if not hit: continue
            for Lo in [L for L in self.outer if L != Lp]:
                tz = self._main_on(Lo, pieces, f, main, net)
                if tz is None: continue
                w = self._glink(net, Lo, (v["x"], v["y"]), tz, ws, "capjoin_link")
                if w: return f"existing via ({v['x']}, {v['y']}) + {w} mm on {Lo}"
        return None

    def _cap_via_join(self, net, p, L0, pg, ws, pieces, f, main):
        vs = self._via_sites(net, pg, int(MOPT["capjoin_vias"]))
        if not vs: return None
        for v in vs:
            if not pg.buffer(0.01).contains(Point(v["x"], v["y"])):
                if not self._link(net, L0, (v["x"], v["y"]), pg, [min(0.5, self._short_side(pg)), 0.3], "capjoin_vialink", esc=False):
                    self.unvia(vs); return None
        for Lo in [L for L in self.outer if L != L0]:
            tz = self._main_on(Lo, pieces, f, main, net)
            if tz is None: continue
            if any(tz.buffer(-0.05).contains(Point(v["x"], v["y"]).buffer(pc.VIA_D / 2)) for v in vs): return "via onto " + Lo
            for v in vs:
                w = self._glink(net, Lo, (v["x"], v["y"]), tz, ws, "capjoin_link")
                if w: return f"via + {w} mm on {Lo}"
        self.unvia(vs); return None


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
    for D in (pv.VOPT, MOPT):
        for k in list(D):
            if k in opt:
                v = opt.pop(k); D[k] = v if isinstance(D[k], str) else type(D[k])(float(v))
    for k in list(pb.OPTB):
        if k in opt: pb.OPTB[k] = type(pb.OPTB[k])(float(opt.pop(k)))
    pa.GATE_LEN = float(opt.pop("gate_len", pa.GATE_LEN)); pa.GATE_W = float(opt.pop("gate_w", pa.GATE_W)); pa.GATE_VIA = float(opt.pop("gate_via", pa.GATE_VIA))
    pa.ALL_GATES = int(opt.pop("all_gates", pa.ALL_GATES)); pa.SEALED = int(opt.pop("sealed", pa.SEALED)); pa.TAPS = int(opt.pop("taps", pa.TAPS))
    for k in list(pp.OPT):
        if k in opt: pp.OPT[k] = type(pp.OPT[k])(float(opt.pop(k))) if isinstance(pp.OPT[k], (int, float)) else opt.pop(k)
    left = [k for k in opt if k not in ("escape", "grow", "mirror")]
    if left: print("WARNING unknown options", left)
    intent = json.load(open(a[3])) if len(a) > 3 else None
    pl = PlannerM(a[0], a[1], intent, escape=float(opt.get("escape", 0.4)), grow=float(opt.get("grow", 1.5)), mirror=float(opt.get("mirror", 3)))
    spec = pl.run(); json.dump(spec, open(a[2], "w"))
    R = spec["report"]
    print("portcu options", json.dumps(pp.OPT)); print("r4v options", json.dumps(pv.VOPT)); print("r4_bcu options", json.dumps(pb.OPTB)); print("r5m options", json.dumps(MOPT))
    for n, r in R.get("nets", {}).items():
        print(f"{n}: {r['current_a']} A, {r['terminals']} terminals, span {r['span_mm']} mm, layer {r.get('main_layer')}{' + ' + r['inner_layer'] if 'inner_layer' in r else ''}, vias {r['vias']}, left to router {r['left_to_router']}")
    print("hot loops", json.dumps(R.get("hot_loops")))
    print("return pads", json.dumps({k: (v if not isinstance(v, list) else v[:12]) for k, v in R["return_pads"].items()}))
    print("gate escapes", json.dumps(R.get("gate_escapes")))
    print("taps", json.dumps(R.get("taps")))
    for k in ("portcu", "r4v", "r4_bcu", "r5m"):
        if k in R: print(k, json.dumps(R[k]))
    print(f"{len(spec['zones'])} zones, {len(spec['vias'])} vias, {len(spec['tracks'])} tracks, {R['seconds']} s; notes: {R['notes']}")


if __name__ == "__main__":
    main()
