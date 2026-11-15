#!/usr/bin/env python3
"""plan_copper_a.py: team A (stagepwr) copy of tools/copper/plan_copper.py with GATE ESCAPES. Same arguments.
The stock planner is imported unchanged; this file only adds one rule on top of it.

Why: a hot loop's supply / return pour is a convex hull of the loop's pads, and inside a hull a signal pad within
NEAR_TERM_MM of a loop pad keeps only the clearance (no 0.4 mm escape room). A half-bridge switch's high-side gate
pin (SiZ240DT pin 1, next to D1's big pad) then sits sealed in its own supply pour: no track and no via fit, so the
gate edge (Q401.1 -> R444, HG1) is blocked for the router. Intent lanes do not clip hot-loop pours.

Rule: for every switch of a hot loop, each signal pad of that switch (its gate pins) gets an escape: a strip
from the pad outward (the direction with the most free room to the nearest other-net pad, of the 4 package-edge
normals) plus a via site at the strip's end. All power copper of other nets keeps the clearance from it (in
clip_others, so hot-loop pours, trees, stubs and the grow step all respect it) and the planner's rasters treat it
as blocked. Options: --gate_len=MM (strip length past the pad edge, default 0.9), --gate_w=MM (strip width, 0.6),
--all_gates=1 (every gate pin; default only a gate pad whose centre lies inside the loop's supply or return pad hull)."""
import sys, os, json, math
sys.path.insert(0, '/home/claude/repo/tools/copper')
import plan_copper as pc
from shapely.geometry import Point, LineString, box
from shapely.ops import unary_union

GATE_LEN = 0.9
GATE_W = 0.6
GATE_VIA = 0.25    # via site radius beyond the via pad (router needs via + clearance + raster margin free on F.Cu)
TAPS = 0           # 1: switch-node taps (--taps=1)
SEALED = 0         # 1: also other small parts' signal pads inside a loop hull (--sealed=1)
ALL_GATES = 0      # 1: every gate pin, not only those inside a loop hull


class PlannerA(pc.Planner):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.gate_keep = {}            # layer -> list of (net, geom)
        self.gate_escapes()

    def gate_escapes(self):
        C = self.d.C; rep = []
        for name, hl in sorted(C.get("hot_loops", {}).items()):
            for sp in hl["switch_pins"][:1]:
                ref = sp.split(".")[0]
                if ref not in self.d.by_ref or not ref.startswith("Q"): continue      # discrete FETs only (not buck ICs)
                L = self.d.fp[ref]["layer"]; pads = [p for p in self.d.by_ref[ref] if L in p["shapes"]]
                if not pads: continue
                bx = unary_union([self.d.pad_poly(p, L) for p in pads]).bounds
                # the hulls the loop pours start from (as loop_pours' 'full'): only a gate pad inside one is sealed
                Pn, Gn = self.d.board(hl["supply"]), self.d.board(hl["ret"]); caps = [c for c in hl["caps"] if c in self.d.by_ref]
                cand = pads + [q for c in caps for q in self.d.by_ref[c] if L in q["shapes"]]
                hulls = [unary_union([self.d.pad_poly(q, L).buffer(0.3, 4) for q in cand if q["net"] == n]).convex_hull for n in (Pn, Gn)]
                todo = [p for p in pads]
                if SEALED:       # also every other small part's signal pad sealed inside the loop hulls (not IC pins)
                    for q, qg in self.padpoly[L]:
                        if qg is None or q["ref"] == ref or q in todo or len(self.d.by_ref[q["ref"]]) > 4: continue
                        if self.d.role(q["net"]) == "signal" and any(h.buffer(-0.05).contains(qg.centroid) for h in hulls): todo.append(q)
                for p in todo:
                    if self.d.role(p["net"]) != "signal": continue
                    if p["ref"] != ref:
                        bx = unary_union([self.d.pad_poly(q, L) for q in self.d.by_ref[p["ref"]] if L in q["shapes"]]).bounds
                    else:
                        bx = unary_union([self.d.pad_poly(q, L) for q in pads]).bounds
                    g = self.d.pad_poly(p, L); a0, b0, a1, b1 = g.bounds; cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
                    if ALL_GATES == 0 and not any(h.buffer(-0.05).intersects(g.centroid) for h in hulls): continue
                    best = None
                    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                        # edge of the pad in that direction, then a probe strip 3 mm long
                        ex = a0 if dx < 0 else a1 if dx > 0 else cx; ey = b0 if dy < 0 else b1 if dy > 0 else cy
                        probe = LineString([(ex, ey), (ex + 3 * dx, ey + 3 * dy)]).buffer(GATE_W / 2, cap_style=2)
                        # stay out of the package: the strip must leave the pad bbox of the switch
                        inside_pkg = (dx < 0 and ex - bx[0] > 0.3) or (dx > 0 and bx[2] - ex > 0.3) or (dy < 0 and ey - bx[1] > 0.3) or (dy > 0 and bx[3] - ey > 0.3)
                        if inside_pkg: continue
                        dmin = 3.0
                        for q, qg in self.padpoly[L]:
                            if q is p or qg is None or q["net"] == p["net"]: continue
                            if qg.intersects(probe):
                                dmin = min(dmin, Point(ex, ey).distance(qg))
                        if best is None or dmin > best[0]: best = (dmin, dx, dy, ex, ey)
                    if best is None: continue
                    dmin, dx, dy, ex, ey = best
                    ln = min(GATE_LEN, max(0.3, dmin - 0.6))
                    strip = LineString([(cx, cy), (ex + ln * dx, ey + ln * dy)]).buffer(GATE_W / 2, cap_style=2)
                    vs = Point(ex + ln * dx, ey + ln * dy).buffer(pc.VIA_D / 2 + GATE_VIA, 16)
                    keep = unary_union([strip, vs]).difference(unary_union([qg for q, qg in self.padpoly[L] if q["net"] != p["net"] and qg is not None]))
                    self.gate_keep.setdefault(L, []).append((p["net"], keep))
                    self.block[L] |= self.raster(keep.buffer(self.clr))
                    self.blockgeom[L].append(keep)
                    rep.append(dict(loop=name, pad=p["key"], net=p["net"], dir=[dx, dy], len_mm=round(ln, 2), free_mm=round(dmin, 2)))
        self.report["gate_escapes"] = rep

    def grow_step(self, step=0.5):
        super().grow_step(step)
        if TAPS:      # taps after the grow step: their thin copper must not grow into switch-node blobs
            for net in sorted(n for n in self.d.power if self.d.power[n]["kind"] == "switching"): self.taps(net)

    def run(self):
        if TAPS and self.grow <= 0: self.grow = 1e-9      # make sure grow_step (and with it the taps) runs
        return super().run()

    def taps(self, net):
        # switch-node taps: a small part's pad on a switching net that is not a planned terminal (a bootstrap cap's
        # SW pad) gets a MIN_W detour (vias + a corridor on the other outer layer + vias into the pour), because the
        # router only searches a window of 6 mm round such an edge's DRC end points, which misses the pour when the
        # pad sits more than ~6 mm from it (C412.2 -> SW1, blocked on every stage variant).
        rep = self.report.setdefault("nets", {}).get(net, {}); main = rep.get("main_layer")
        if not main or (net, main) not in self.zones: return
        T = {p["key"] for g in self.d.terminals(net) for p in g["pads"]}
        tree = self.cu[main] == self.netid[net]
        for p in self.d.pads:
            if p["net"] != net or p["key"] in T or main not in p["shapes"] or len(self.d.by_ref[p["ref"]]) > 4: continue
            gp = self.d.pad_poly(p, main)
            if self.zones[(net, main)]["geom"].distance(gp) < 3.0: continue      # near the pour: the router finds it
            ok = self.detour(net, main, gp, pc.MIN_W, 0.5, tree)
            self.report.setdefault("taps", []).append(dict(pad=p["key"], net=net, drawn=bool(ok)))

    def clip_others(self, net, L, g, loose_near=None):
        g = super().clip_others(net, L, g, loose_near)
        cut = [k.buffer(self.clr, 4) for n, k in getattr(self, "gate_keep", {}).get(L, []) if n != net]
        return g.difference(unary_union(cut)) if cut and not g.is_empty else g


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
    GATE_LEN = float(opt.pop("gate_len", GATE_LEN)); GATE_W = float(opt.pop("gate_w", GATE_W)); GATE_VIA = float(opt.pop("gate_via", GATE_VIA)); ALL_GATES = int(opt.pop("all_gates", ALL_GATES)); SEALED = int(opt.pop("sealed", SEALED)); TAPS = int(opt.pop("taps", TAPS))
    intent = json.load(open(a[3])) if len(a) > 3 else None
    pl = PlannerA(a[0], a[1], intent, escape=float(opt.get("escape", 0.4)), grow=float(opt.get("grow", 1.5)), mirror=float(opt.get("mirror", 3)))
    spec = pl.run(); json.dump(spec, open(a[2], "w"))
    R = spec["report"]
    for n, r in R.get("nets", {}).items():
        print(f"{n}: {r['current_a']} A, {r['terminals']} terminals, span {r['span_mm']} mm, layer {r.get('main_layer')}{' + ' + r['inner_layer'] if 'inner_layer' in r else ''}, vias {r['vias']}, left to router {r['left_to_router']}")
    print("hot loops", json.dumps(R.get("hot_loops")))
    print("return pads", json.dumps({k: (v if not isinstance(v, list) else v[:12]) for k, v in R["return_pads"].items()}))
    print("gate escapes", json.dumps(R.get("gate_escapes")))
    print("taps", json.dumps(R.get("taps")))
    print(f"{len(spec['zones'])} zones, {len(spec['vias'])} vias, {len(spec['tracks'])} tracks, {R['seconds']} s; notes: {R['notes']}")
