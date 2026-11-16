#!/usr/bin/env python3
"""plan_copper_b.py: team A (r4_bcu) planner = portcu planner P (all its options, imported unchanged) + rules that
keep switch-node and detour copper off the bottom layer. Same arguments as tools/copper/plan_copper.py. Every new rule
has its own option (0 = planner P behaviour):

  --sw_nogrow=1   a switch-node net's detour corridor on the other outer layer (zone kinds only {detour}: the
                  B.Cu SW2 path from the FET's enclosed SW pad to the inductor pad) is not grown by the grow step.
                  The corridor keeps the width the current needs (roles.width_mm) and nothing more: the grown
                  1.5 mm round it is pure dV/dt area facing whatever is below the board.
  --sw_w=MM       width of a switch-node detour corridor (default: roles.width_mm of the net current).
  --sw_vias=N     vias at each end of a switch-node detour (default: 1 A per via of the net current).
  --pw_nogrow=1   the same as --sw_nogrow for detours of non-switching power nets (the B.Cu PP5V corridor across the
                  VBUS stem). (portcu's --nogrow_detour=1 is both at once.)
  --stub_nogrow=1 a via stub on the other outer layer (zone kinds only {via stub}: the copper round a bottom-side
                  terminal pad and its via array, e.g. the B.Cu AC bulk caps C421/C521 and C456/C556) is not grown into
                  a blob; it keeps the pad, the vias and their links.
  --mirror_minw2=MM  mirror copies (step 5: a >= 3 A net copied onto the other outer layer where it is free) are
                  kept only as pieces at least MM wide on average (2 x area / perimeter): a long thin copy (the
                  AC_SNS_N corridor under the stage, BAT_SNS_P / PACK_P patches) carries little current and takes
                  routing room on the bottom layer. Unlike portcu's --mirror_minw it also cuts copies that were
                  merged into a zone with via stubs (only the pieces the mirror step added are judged; their
                  stitching vias go with them).
  --mirror_maxa=MM2  as --mirror_minw2, but drops added mirror pieces smaller than MM2 (patches).
  --mirror_skip_supply=1  hot-loop supply nets of discrete-FET loops (the charger stage input AC_SNS_N and output
                  BAT_SNS_P) get no mirror copy at all: the stage's own outer-layer copper and the In2/In3 layers
                  are the path; a copy under the stage is the bottom-layer corridor a reviewer sees.
  --ret_band=MM   a discrete switch of a hot loop with fewer than --ret_vias (4) return vias within 1.2 mm of its
                  return pins gets a band of return copper MM deep straight out of its return-pin row (away from the
                  package, as wide as the package + 1.5 mm each side, clipped by the other nets with escape room) and return vias in
                  it. The loop's own hull leaves the row with a thin strip when the row faces outward (Q402 hung
                  beside the inductor: 1 via at S2 instead of 3).
  --tap_max=MM    --taps (planner A) draws a switch-node tap only up to DETOUR_MAX_MM (10 mm) long; with the switch node
                  on F.Cu at the inductor the bootstrap cap's SW pad (beside the controller) can be 12-15 mm away. The
                  tap stays a 0.3 mm track on the other outer layer (drawn after the grow step, never grown).
  --sw_report=1   (always on) the report gets 'r4_bcu': switch-node and B.Cu areas per net.

Rule (a) of the task ("route the switch node on F.Cu from the FET's SW pads to the inductor pad, B.Cu only if no
F.Cu path of minimum width exists") is the stock net_step behaviour already: the F.Cu path is searched first (also
with clearance only), the detour is drawn only when none exists. With the SiZ240DT at rot 180 under the inductor the
SW pad's only F.Cu exit (between its gate pins) faces away from the inductor, and every other exit is closed by the
hot loop's own supply/return pours across the cap edge, so no F.Cu path exists; that needs a placement change.
Imports portcu/tools/plan_copper_p.py (-> stagepwr plan_copper_a.py -> stock tools/copper/plan_copper.py)."""
import sys, os, json, math
sys.path.insert(0, '/home/claude/repo/tools/copper')
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/stagepwr/tools')
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/portcu/tools')
import numpy as np
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
import plan_copper as pc
import plan_copper_a as pa
import plan_copper_p as pp

OPTB = dict(stub_nogrow=0, ret_band=0.0, ret_vias=4, tap_max=0.0, sw_nogrow=0, sw_w=0.0, sw_vias=0, pw_nogrow=0, mirror_minw2=0.0, mirror_maxa=0.0, mirror_skip_supply=0)


class PlannerB(pp.PlannerP):
    def _switching(self, net):
        return self.d.power.get(net, {}).get("kind") == "switching"

    # ---- switch-node detour width / via count
    def detour(self, net, L, gp, w, I, tree):
        if self._switching(net) and getattr(self, "_in_netstep", None) == net:
            if OPTB["sw_w"] > 0: w = OPTB["sw_w"]
            if OPTB["sw_vias"] > 0: I = float(OPTB["sw_vias"])
        return super().detour(net, L, gp, w, I, tree)

    def net_step(self, net):
        self._in_netstep = net
        try: return super().net_step(net)
        finally: self._in_netstep = None

    # ---- return band + vias at a discrete switch's return pins
    def hot_loops_step(self):
        super().hot_loops_step()
        if OPTB["ret_band"] <= 0: return
        from shapely.geometry import box as sbox
        rep = []
        for name, hl in sorted(self.d.C.get("hot_loops", {}).items()):
            ref = hl["switch_pins"][0].split(".")[0]
            if not ref.startswith("Q") or ref not in self.d.by_ref: continue
            G = self.d.board(hl["ret"]); L = self.d.fp[ref]["layer"]
            pads = [p for p in self.d.by_ref[ref] if L in p["shapes"]]
            row = [p for p in pads if p["net"] == G and p["key"] in self.d.switch_pins]
            if not row: continue
            rg = unary_union([self.d.pad_poly(p, L) for p in row]); pk = unary_union([self.d.pad_poly(p, L) for p in pads])
            c, r = pk.centroid, rg.centroid; dx, dy = r.x - c.x, r.y - c.y
            ux, uy = (1 if dx > 0 else -1, 0) if abs(dx) >= abs(dy) else (0, 1 if dy > 0 else -1)
            near = rg.buffer(1.2)
            have = [v for v in self.vias if v["net"] == G and near.contains(Point(v["x"], v["y"]))]
            if len(have) >= OPTB["ret_vias"]: rep.append(dict(loop=name, vias=len(have), added=0)); continue
            a0, b0, a1, b1 = rg.bounds; m = OPTB["ret_band"]; p0, q0, p1, q1 = pk.bounds; e = 1.5     # lateral: the package width + 1.5 mm
            if ux > 0: band = sbox(a1, q0 - e, a1 + m, q1 + e)
            elif ux < 0: band = sbox(a0 - m, q0 - e, a0, q1 + e)
            elif uy > 0: band = sbox(p0 - e, b1, p1 + e, b1 + m)
            else: band = sbox(p0 - e, b0 - m, p1 + e, b0)
            band = unary_union([band, rg]).intersection(self.inside)
            band = self.clip_others(G, L, band)
            band = unary_union([q for q in getattr(band, "geoms", [band]) if q.intersects(rg)])
            if band.is_empty or band.area < 0.5: rep.append(dict(loop=name, vias=len(have), added=0, why="no room")); continue
            self.add_zone(G, L, band, 25, kind="hot loop " + name)
            vs = self.place_vias(G, rg, OPTB["ret_vias"] - len(have), inside=band)
            rep.append(dict(loop=name, vias=len(have), added=len(vs), band_mm2=round(band.area, 1), dir=[ux, uy]))
        self.report.setdefault("r4_bcu", {})["ret_band"] = rep

    # ---- longer switch-node taps (a bootstrap cap's SW pad far from a switch node that now leaves its FET on F.Cu)
    def taps(self, net):
        if OPTB["tap_max"] <= 0: return super().taps(net)
        old = pc.DETOUR_MAX_MM; pc.DETOUR_MAX_MM = OPTB["tap_max"]
        try: return super().taps(net)
        finally: pc.DETOUR_MAX_MM = old

    # ---- detours not grown
    def grow_step(self, step=0.5):
        tag = []
        for (net, L), z in self.zones.items():
            if z["soft"] or L not in self.outer or not (z["kinds"] <= {"detour"} or z["kinds"] <= {"via stub"}): continue
            if OPTB["stub_nogrow"] and z["kinds"] <= {"via stub"}:
                z["kinds"].add("mirror"); tag.append((net, L)); continue
            if not (z["kinds"] <= {"detour"}): continue
            sw = self._switching(net)
            if (sw and OPTB["sw_nogrow"]) or (not sw and OPTB["pw_nogrow"]):
                z["kinds"].add("mirror"); tag.append((net, L))      # the grow step skips zones of kind mirror
        self.report.setdefault("r4_bcu", {})["not_grown"] = sorted(f"{n} {L}" for n, L in tag)
        try: super().grow_step(step)
        finally:
            for k in tag:
                if k in self.zones: self.zones[k]["kinds"].discard("mirror")

    # ---- mirror copies: skip supply nets of FET loops, drop thin / small added pieces
    def _loop_supplies(self):
        out = set()
        for name, hl in self.d.C.get("hot_loops", {}).items():
            ref = hl["switch_pins"][0].split(".")[0]
            if ref.startswith("Q"): out.add(self.d.board(hl["supply"]))
        return out

    def mirror_step(self, min_a):
        skip = self._loop_supplies() if OPTB["mirror_skip_supply"] else set()
        saved = {}
        if skip:       # hide the skipped nets from the mirror step
            for n in skip:
                if n in self.d.power: saved[n] = self.d.power.pop(n)
        before = {k: z["geom"] for k, z in self.zones.items()}
        nv0 = len(self.vias)
        try: super().mirror_step(min_a)
        finally: self.d.power.update(saved)
        mw, ma = OPTB["mirror_minw2"], OPTB["mirror_maxa"]
        drop = []
        if mw > 0 or ma > 0:
            new = self.vias[nv0:]
            for (net, L), z in list(self.zones.items()):
                if "mirror" not in z["kinds"] or z["soft"]: continue
                old = before.get((net, L))
                added = z["geom"] if old is None else z["geom"].difference(old.buffer(0.01))
                keep_add = []
                for q in getattr(added, "geoms", [added]):
                    if q.is_empty: continue
                    if old is not None and q.buffer(0.05).intersects(old): keep_add.append(q); continue
                    w = 2 * q.area / max(q.length, 1e-6)
                    if (mw > 0 and w < mw) or (ma > 0 and q.area < ma):
                        vs = [v for v in new if v["net"] == net and q.buffer(0.05).contains(Point(v["x"], v["y"]))]
                        self.unvia(vs); new = [v for v in new if v not in vs]
                        self.cu[L][self.raster(q) & (self.cu[L] == self.netid[net])] = -1
                        drop.append([net[-12:], L, round(q.area, 1), round(w, 2), len(vs)])
                    else: keep_add.append(q)
                g = unary_union(([old] if old is not None else []) + keep_add)
                if g.is_empty: del self.zones[(net, L)]
                else: z["geom"] = g
        self.report.setdefault("r4_bcu", {})["mirror_dropped"] = drop
        self.report.setdefault("r4_bcu", {})["mirror_skipped_nets"] = sorted(skip)

    def run(self):
        spec = super().run()
        sw = {n for n in self.d.power if self._switching(n)}
        rep = self.report.setdefault("r4_bcu", {}); a = {}
        for (n, L), z in self.zones.items():
            if L in self.outer and not z["soft"] and (n in sw or L == self.outer[-1]):
                a[f"{n} {L}"] = round(z["geom"].area, 1)
        rep["areas"] = a
        spec["report"] = self.report
        return spec


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
    for k in list(OPTB):
        if k in opt: OPTB[k] = type(OPTB[k])(float(opt.pop(k)))
    pa.GATE_LEN = float(opt.pop("gate_len", pa.GATE_LEN)); pa.GATE_W = float(opt.pop("gate_w", pa.GATE_W)); pa.GATE_VIA = float(opt.pop("gate_via", pa.GATE_VIA))
    pa.ALL_GATES = int(opt.pop("all_gates", pa.ALL_GATES)); pa.SEALED = int(opt.pop("sealed", pa.SEALED)); pa.TAPS = int(opt.pop("taps", pa.TAPS))
    for k in list(pp.OPT):
        if k in opt: pp.OPT[k] = type(pp.OPT[k])(float(opt.pop(k))) if isinstance(pp.OPT[k], (int, float)) else opt.pop(k)
    intent = json.load(open(a[3])) if len(a) > 3 else None
    pl = PlannerB(a[0], a[1], intent, escape=float(opt.get("escape", 0.4)), grow=float(opt.get("grow", 1.5)), mirror=float(opt.get("mirror", 3)))
    spec = pl.run(); json.dump(spec, open(a[2], "w"))
    R = spec["report"]
    print("portcu options", json.dumps(pp.OPT)); print("r4_bcu options", json.dumps(OPTB))
    for n, r in R.get("nets", {}).items():
        print(f"{n}: {r['current_a']} A, {r['terminals']} terminals, span {r['span_mm']} mm, layer {r.get('main_layer')}{' + ' + r['inner_layer'] if 'inner_layer' in r else ''}, vias {r['vias']}, left to router {r['left_to_router']}")
    print("hot loops", json.dumps(R.get("hot_loops")))
    print("return pads", json.dumps({k: (v if not isinstance(v, list) else v[:12]) for k, v in R["return_pads"].items()}))
    print("gate escapes", json.dumps(R.get("gate_escapes")))
    print("taps", json.dumps(R.get("taps")))
    for k in ("portcu", "r4_bcu"):
        if k in R: print(k, json.dumps(R[k]))
    print(f"{len(spec['zones'])} zones, {len(spec['vias'])} vias, {len(spec['tracks'])} tracks, {R['seconds']} s; notes: {R['notes']}")


if __name__ == "__main__":
    main()
