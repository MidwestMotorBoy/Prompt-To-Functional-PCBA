"""secplace.py <recipe.json ...> --group=<port1|port2|pack> --out=fragments/<g>.json [--base=<fragment>] [--others=<dir>]
              [--claims=<claims.json>] [--step=0.1]
Team B section placer: runs recipe files in order and writes a fragment {ref: [x, y, turn, side]} plus
<out>.meta.json (rings, reserved boxes, claims, bottom refs, deviations, failed steps, per-part costs).

Start state: fixed parts at the template; --base fragment (own group) if given, minus every ref the recipes place
(a recipe owns its refs); the other groups' fragments from --others (default: the folder of --out) as obstacles,
with their meta rings and reserved boxes; for a group with no fragment there, its B1 boxes for chips with 12 pads
or more stand in. Claims from --claims (default <others>/claims.json) and from claim steps.

Recipe: a json list of steps (a dict {"steps": [...]} also works). Every placing step may carry "turns": [0, 90, ...]
and "side": "F"|"B". Steps:
  {"put": ref, "at": [x, y], "turn": t, "side": "F"}            explicit; fails if illegal (add "force": true to keep it anyway)
  {"ring": chip, "mm": 0.8, "allow": [refs]}                     escape ring round the chip's signal pad rows; parts that
                                                                 constraints "serves" declares for a pin of that row: 0.3 mm
  {"reserve": name, "box": [x0, y0, x1, y1], "sides": "F"|"B"|"FB", "except": [refs]}
  {"hot": cap, "switch": "Q401", "supply": [pads], "ret": [pads], "max_mm": 1.5, "soft": false}
        switch/supply/ret default to the hot loop in constraints.json that lists the cap. Cost: edge gap of the cap's
        supply pad to the nearest switch supply pad + the same for return; +20 per link with no clear L-shaped copper
        way (another net's pad in the way, the switch's own included), +20 if the two ways cross, +10 if no return-via
        spot is free next to the cap's return pad. Proxies only: screen the loop after the step.
  {"at_pin": ref, "pads": {"1": "U403.24"}, "max_mm": 2.0, "soft": false}   target "REF.PAD" or "REF.PIN" (or a list)
  {"auto": [refs]}                                               most connected first; target = serves pin, else the
                                                                 other pad of each two-pad net
  {"translate": [refs], "from_fragment": "port1", "map": "4->5", "dx": -23.02577, "dy": 0.006368}
        refs are the source refs (as in the fragment); an illegal copy is moved to the nearest legal spot (reported)
  {"twin_check": true, "dx": -23.02577, "dy": 0.006368}         later spots must also be legal shifted (against fixed
                                                                 parts, keep-outs and the board edge); false turns it off
  {"side": [refs], "to": "B"}                                    default side of those refs in later steps
  {"claim": ref, "box": [...], "why": "..."}   {"deviation": section, "box": [...], "why": "..."}   {"remove": [refs]}
Optional on hot and at_pin: "within": [x0, y0, x1, y1], the courtyard must lie inside this box (to keep a sub-area for
the next part; greedy placement takes the single best spot and can strand a neighbour); "step": 0.05, a finer grid
for a tight gap.
Search (hot, at_pin, auto): 0.1 mm grid in a window grown 3, 6, 12 mm round the targets, every allowed turn,
cheapest legal spot (greedy_fill.py style). Exit code 1 when a step failed."""
import sys, os, json, math, re, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blib
from blib import Board, Layout, GROUPS, grow, inter, box_gap, closest_points, map_ref, load_placement

GROWS = (3.0, 6.0, 12.0)

CLR = 0.15
def way_clear(p, t, obstacles):
    """an L-shaped copper way from pad p to pad t (either corner) that touches no pad of another net"""
    a = ((p[4][0] + p[4][2]) / 2, (p[4][1] + p[4][3]) / 2); b = ((t[4][0] + t[4][2]) / 2, (t[4][1] + t[4][3]) / 2)
    net = p[1]; ob = [o[4] for o in obstacles if o[1] != net]
    def leg(u, w, pad, end_pad):
        horiz = abs(u[1] - w[1]) < 1e-9
        across = (pad[4][3] - pad[4][1]) / 2 if horiz else (pad[4][2] - pad[4][0]) / 2
        hw = min(across, 0.25) + CLR
        bx = (min(u[0], w[0]), min(u[1], w[1]), max(u[0], w[0]), max(u[1], w[1]))
        return (bx[0] - (0 if horiz else hw), bx[1] - (hw if horiz else 0), bx[2] + (0 if horiz else hw), bx[3] + (hw if horiz else 0))
    for corner in ((b[0], a[1]), (a[0], b[1])):
        rects = []
        if abs(corner[0] - a[0]) + abs(corner[1] - a[1]) > 1e-9: rects.append(leg(a, corner, p, t))
        if abs(corner[0] - b[0]) + abs(corner[1] - b[1]) > 1e-9: rects.append(leg(corner, b, t, p))
        if not any(inter(R, o) for R in rects for o in ob): return True
    return False

VIA_R = 0.225 + 0.2       # via pad radius + clearance
ESCAPE = 0.4              # the copper planner keeps this much more from signal pads
def via_room(p, obstacles, B):
    """is there a spot for a return via within 0.5 to 1.1 mm of pad p (clear of other nets' pads, with the planner's
    escape room at signal pads)? The copper planner drops the via when there is none, and the loop opens."""
    b = p[4]; net = p[1]
    ob = [(o[4], VIA_R + (ESCAPE if B.is_signal_net(o[1]) else 0.0)) for o in obstacles if o[1] != net and o[4][0] < b[2] + 3 and o[4][2] > b[0] - 3 and o[4][1] < b[3] + 3 and o[4][3] > b[1] - 3]
    for d in (0.5, 0.8, 1.1):
        x0, y0, x1, y1 = b[0] - d, b[1] - d, b[2] + d, b[3] + d
        n = max(2, int(round((x1 - x0) / 0.2))); m = max(2, int(round((y1 - y0) / 0.2)))
        pts = [(x0 + (x1 - x0) * i / n, y) for i in range(n + 1) for y in (y0, y1)] + [(x, y0 + (y1 - y0) * j / m) for j in range(1, m) for x in (x0, x1)]
        for (px, py) in pts:
            if all(math.hypot(max(0.0, o[0] - px, px - o[2]), max(0.0, o[1] - py, py - o[3])) >= r for o, r in ob): return True
    return False

def seg_cross(a, b, c, d):
    """segments a-b and c-d cross (proper intersection)"""
    def o(p, q, r): return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0

class Runner:
    def __init__(self, args):
        self.opt = dict((x[2:].split("=", 1) + [""])[:2] for x in args if x.startswith("--"))
        self.recipes = [x for x in args if not x.startswith("--")]
        self.g = self.opt["group"]; assert self.g in GROUPS, f"--group must be one of {GROUPS}"
        self.out = self.opt["out"]; self.others = self.opt.get("others") or os.path.dirname(os.path.abspath(self.out))
        self.step = float(self.opt.get("step", 0.1))
        self.B = B = Board(); self.L = L = Layout(B, group=self.g)
        self.log = []; self.fail = []; self.costs = {}; self.placed_by_recipe = []
        self.my_rings = []; self.my_reserved = []; self.my_claims = []; self.deviations = []
        self.side_of = {}; self.twin = None
        # other groups
        for g2 in GROUPS:
            if g2 == self.g: continue
            f = os.path.join(self.others, g2 + ".json")
            if os.path.exists(f):
                F = load_placement(f)
                for r, v in F.items():
                    if r in B.parts and r not in B.fixed: L.put(r, v)
                m = blib.load_meta(os.path.join(self.others, g2 + ".meta.json"))
                for z in m.get("reserved", []): L.reserved.append(dict(name=f"{g2}:{z['name']}", box=tuple(z["box"]), sides=z.get("sides", "F"), **({"except": set(z["except"])} if z.get("except") else {})))
                for rg in m.get("rings", []):
                    if rg["chip"] in L.P: L.add_ring(rg["chip"], rg.get("mm", 0.8), rg.get("allow", ()))
                self.say(f"others: {g2} fragment {len(F)} parts, {len(m.get('rings', []))} rings, {len(m.get('reserved', []))} reserved")
            else:
                st = B.stand_in_boxes(g2); L.stand += st
                self.say(f"others: {g2} has no fragment in {self.others}; stand-in boxes: {[s[0][:50] for s in st]}")
        cf = self.opt.get("claims") or os.path.join(self.others, "claims.json")
        if os.path.exists(cf):
            for c in json.load(open(cf)):
                if c["ref"] not in L.claims: L.claims[c["ref"]] = tuple(c["box"])
        self.steps = []
        for rf in self.recipes:
            S = json.load(open(rf)); S = S["steps"] if isinstance(S, dict) else S
            self.steps += [(rf, i, s) for i, s in enumerate(S)]
        self.owned = set()
        for _, _, s in self.steps:
            for k in ("put", "hot", "at_pin"):
                if k in s: self.owned.add(s[k])
            if "auto" in s: self.owned |= set(s["auto"])
            if "translate" in s: self.owned |= {map_ref(r, s.get("map", "4->5")) or r for r in s["translate"]}
        if self.opt.get("base"):
            F = load_placement(self.opt["base"]); n = 0
            for r, v in F.items():
                if r in self.owned: continue
                if B.group_of.get(r) != self.g: self.say(f"base: {r} is not a {self.g} part, skipped"); continue
                L.put(r, v); n += 1
            self.say(f"base: {n} parts kept from {self.opt['base']}, {len(self.owned)} refs owned by the recipes")

    def say(self, s): print(s, flush=True); self.log.append(s)

    def bad(self, where, s): self.say(f"FAIL {where}: {s}"); self.fail.append(f"{where}: {s}")

    def side_for(self, r, s):
        return blib.side1(s["side"]) if s.get("side") else self.side_of.get(r, self.B.parts[r]["side"])

    def check_ref(self, r, where):
        if r not in self.B.parts: self.bad(where, f"unknown ref {r}"); return False
        if r in self.B.fixed: self.bad(where, f"{r} is fixed"); return False
        if self.B.group_of.get(r) != self.g: self.bad(where, f"{r} belongs to {self.B.group_of.get(r)}, not {self.g}"); return False
        return True

    # ---- grid search
    def search(self, r, side, turns, cbox, cost_fn, refine=None, grows=GROWS, step=None):
        L, B = self.L, self.B; st = step or self.step; ob = B.obox
        for gw in grows:
            w = (max(cbox[0] - gw, ob[0]), max(cbox[1] - gw, ob[1]), min(cbox[2] + gw, ob[2]), min(cbox[3] + gw, ob[3]))
            xs = np.round(np.arange(math.ceil(w[0] / st) * st, w[2] + 1e-9, st), 4); ys = np.round(np.arange(math.ceil(w[1] / st) * st, w[3] + 1e-9, st), 4)
            if not len(xs) or not len(ys): continue
            cx, cy = (cbox[0] + cbox[2]) / 2, (cbox[1] + cbox[3]) / 2
            cands = []
            for q in turns:
                qq = q // 90 % 4
                M = L.legal_mask(r, qq, side, xs, ys)
                if self.twin and M.any():
                    M &= L.legal_mask(r, qq, side, xs + self.twin[0], ys + self.twin[1], static_only=True, region=False)
                if not M.any(): continue
                c, ok = cost_fn(qq, xs, ys)
                c = c + 1e-3 * (np.abs(xs[None, :] - cx) + np.abs(ys[:, None] - cy))
                c = np.where(M & ok, c, np.inf)
                fin = np.isfinite(c)
                if not fin.any(): continue
                k = min(40 if refine else 1, int(fin.sum())); flat = np.argpartition(c.ravel(), k - 1)[:k]
                for fi in flat:
                    j, i = np.unravel_index(fi, c.shape); cands.append((float(c[j, i]), float(xs[i]), float(ys[j]), qq))
            if not cands: continue
            if refine:
                cands = sorted(cands)[:60]; cands = [(cv + refine(x, y, q), x, y, q) for cv, x, y, q in cands]
            return min(cands)
        return None

    def targets_of(self, spec):
        """'U403.24' / 'U403.REGN' / list -> list of present pad tuples"""
        out = []
        for t in (spec if isinstance(spec, list) else [spec]):
            ref, pin = t.split(".", 1)
            if ref not in self.L.P: continue
            nums = set(self.B.pin_pads(ref, pin))
            out += [p for p in self.L.geom(ref)[2] if p[0] in nums]
        return out

    def place_at_targets(self, r, side, turns, targets, max_mm=None, soft=False, extra_nets=True, where="", hot=None, within=None, step=None):
        """targets {pad num: [target pads]}; cost = Manhattan pad distance sum + half-perimeter growth of r's other signal nets"""
        L, B = self.L, self.B
        tn = set(targets)
        nets = [p["net"] for p in B.parts[r]["pads"] if p["num"] not in tn and B.is_signal_net(p["net"]) and len(B.nets[p["net"]]) < 12] if extra_nets else []
        nets = sorted(set(nets))
        pts = [t for tl in targets.values() for t in tl]
        if within: cbox = tuple(within)
        elif pts: cbox = (min(t[4][0] for t in pts), min(t[4][1] for t in pts), max(t[4][2] for t in pts), max(t[4][3] for t in pts))
        else:
            q = [p for n in nets for p in L.present_pads_of_net(n, skip=(r,))]
            if q: cbox = (min(p[2] for p in q), min(p[3] for p in q), max(p[2] for p in q), max(p[3] for p in q))
            else:
                R = B.regions[self.g]; cbox = tuple(R);
        def cost(q, xs, ys):
            man, worst, gsum = self.tcost(r, q, side, xs, ys, targets)
            c = (gsum + 0.01 * man) if hot else man
            if nets: c = c + L.hpwl_growth(r, q, side, xs, ys, nets)
            ok = np.ones_like(c, bool)
            if within:
                b = blib.tbox(B.parts[r]["court"], side != B.parts[r]["side"], q); W = within
                mx = (xs + b[0] >= W[0] - 1e-6) & (xs + b[2] <= W[2] + 1e-6); my = (ys + b[1] >= W[1] - 1e-6) & (ys + b[3] <= W[3] + 1e-6)
                ok = ok & (my[:, None] & mx[None, :])
            if max_mm is not None:
                if soft: c = c + 50.0 * np.maximum(0, worst - max_mm)
                else: ok = ok & (worst <= max_mm + 1e-9)
            return c, ok
        refine = None
        if hot:
            ret_num = list(targets)[-1]       # hot: {supply pad: ..., return pad: ...}
            obst = [(q2, p) for q2 in L.P for p in L.geom(q2)[2] if side in p[5] and p[1]
                    and p[4][2] > cbox[0] - 15 and p[4][0] < cbox[2] + 15 and p[4][3] > cbox[1] - 15 and p[4][1] < cbox[3] + 15]
            def refine(x, y, q):
                """20 per capacitor-to-switch link that has no clear L-shaped copper way (two legs, each as wide as the pad
                it leaves or enters up to 0.5 mm, plus 0.15 mm clearance, through no pad of another net, the switch's and
                the capacitor's own pads included), and 20 when the supply way crosses the return way"""
                v = (x, y, q * 90, side); mine = B.pads(r, v); pads = {p[0]: p for p in mine}; pen = 0.0; segs = []
                ob = [p for _, p in obst] + [p for p in mine if side in p[5]]
                for num, tl in targets.items():
                    p = pads.get(num)
                    if not p or not tl: continue
                    t = min(tl, key=lambda t: box_gap(p[4], t[4]))
                    if not way_clear(p, t, ob): pen += 20.0
                    segs.append((((p[4][0] + p[4][2]) / 2, (p[4][1] + p[4][3]) / 2), ((t[4][0] + t[4][2]) / 2, (t[4][1] + t[4][3]) / 2)))
                if len(segs) == 2 and seg_cross(*segs[0], *segs[1]): pen += 20.0
                rp_ = pads.get(ret_num)
                if rp_ is not None and not via_room(rp_, ob, B): pen += 10.0
                return pen
        best = self.search(r, side, turns, cbox, cost, refine, step=step)
        if best is None:
            self.bad(where, f"{r}: no legal spot within {GROWS[-1]} mm of its targets" + (f" with every target pad within {max_mm} mm" if max_mm is not None and not soft else ""))
            return None
        c, x, y, q = best; L.put(r, (x, y, q * 90, side)); self.costs[r] = round(c, 3); self.placed_by_recipe.append(r)
        v = (x, y, q * 90, side); pads = {p[0]: p for p in B.pads(r, v)}
        gaps = {num: round(min(box_gap(pads[num][4], t[4]) for t in tl), 2) for num, tl in targets.items() if tl and num in pads}
        self.say(f"  {r}: at {x:.2f},{y:.2f} turn {q * 90} {side} cost {c:.2f} pad gaps {gaps}")
        return best

    def tcost(self, r, q, side, xs, ys, targets):
        fl = side != self.B.parts[r]["side"]; lp = self.B.local_pads(r, q, fl)
        X = xs[None, :]; Y = ys[:, None]; man = np.zeros((len(ys), len(xs))); worst = np.zeros_like(man); gsum = np.zeros_like(man)
        for num, tl in targets.items():
            mine = [p for p in lp if p[0] == num]
            if not mine or not tl: continue
            p = mine[0]; hw = (p[4][2] - p[4][0]) / 2; hh = (p[4][3] - p[4][1]) / 2; dm = dg = None
            for t in tl:
                thw = (t[4][2] - t[4][0]) / 2; thh = (t[4][3] - t[4][1]) / 2
                tcx = (t[4][0] + t[4][2]) / 2; tcy = (t[4][1] + t[4][3]) / 2
                ax = np.abs(X + (p[4][0] + p[4][2]) / 2 - tcx); ay = np.abs(Y + (p[4][1] + p[4][3]) / 2 - tcy)
                m = ax + ay; g = np.hypot(np.maximum(0, ax - hw - thw), np.maximum(0, ay - hh - thh))
                dm = m if dm is None else np.minimum(dm, m); dg = g if dg is None else np.minimum(dg, g)
            man = man + dm; worst = np.maximum(worst, dg); gsum = gsum + dg
        return man, worst, gsum

    # ---- steps
    def run(self):
        for rf, i, s in self.steps:
            where = f"{os.path.basename(rf)}#{i}"
            t0 = time.time()
            try: self.do(s, where)
            except Exception as e:
                import traceback; traceback.print_exc(); self.bad(where, f"error {e!r} in step {json.dumps(s)[:120]}")
        self.finish()

    def do(self, s, where):
        L, B = self.L, self.B
        turns = s.get("turns", [0, 90, 180, 270])
        if "put" in s:
            r = s["put"]
            if not self.check_ref(r, where): return
            side = self.side_for(r, s); v = (float(s["at"][0]), float(s["at"][1]), int(s.get("turn", 0)), side)
            L.remove(r); f = L.faults(r, v)
            if self.twin and not f:
                tv = (v[0] + self.twin[0], v[1] + self.twin[1], v[2], v[3]); T = Layout(B)
                tf = [x for x in T.faults(r, tv, region=False, rings=False, reserved=False)]
                if tf: f = [f"twin: {x}" for x in tf]
            if f and not s.get("force"): self.bad(where, f"put {r} at {s['at']} turn {v[2]} {side}: {f}"); return
            L.put(r, v); self.placed_by_recipe.append(r); self.costs[r] = 0.0
            self.say(f"  {r}: put at {v[0]:.2f},{v[1]:.2f} turn {v[2]} {side}" + (f" FORCED despite {f}" if f else ""))
        elif "ring" in s:
            c = s["ring"]
            if c not in L.P: self.bad(where, f"ring {c}: chip not placed"); return
            L.add_ring(c, float(s.get("mm", 0.8)), s.get("allow", ()), float(s.get("serves_mm", 0.3)))
            self.my_rings.append(dict(chip=c, mm=float(s.get("mm", 0.8)), allow=list(s.get("allow", ())), serves_mm=float(s.get("serves_mm", 0.3))))
            viol = [r for r in L.P if r != c and any(inter(L.geom(r)[0], rb) for ch, rb in L.ring_boxes(r, L.geom(r)[1]) if ch == c)]
            self.say(f"  ring {c} {s.get('mm', 0.8)} mm, rows {[k for k, _, _ in L.rings[-1]['rows']]}" + (f"; parts already inside it: {viol}" if viol else ""))
        elif "reserve" in s:
            z = dict(name=s["reserve"], box=tuple(s["box"]), sides=s.get("sides", "F"))
            if s.get("except"): z["except"] = set(s["except"])
            L.reserved.append(z); self.my_reserved.append(dict(name=z["name"], box=list(z["box"]), sides=z["sides"], **({"except": sorted(z["except"])} if "except" in z else {})))
            viol = [r for r in L.P if r not in B.fixed and L.geom(r)[1] in z["sides"] and r not in z.get("except", ()) and inter(L.geom(r)[0], z["box"])]
            self.say(f"  reserve {z['name']} {z['box']} {z['sides']}" + (f"; parts already inside it: {viol}" if viol else ""))
        elif "hot" in s:
            cap = s["hot"]
            if not self.check_ref(cap, where): return
            sw, sup, ret = s.get("switch"), s.get("supply"), s.get("ret")
            if not (sw and sup and ret):
                hl = next((h for h in B.C["hot_loops"].values() if cap in h["caps"]), None)
                if not hl: self.bad(where, f"hot {cap}: no hot loop lists it; give switch, supply, ret"); return
                a, b = hl["switch_pins"]; sw = sw or a.split(".")[0]
                sup = sup or B.pin_pads(sw, a.split(".")[1]); ret = ret or B.pin_pads(sw, b.split(".")[1])
            if sw not in L.P: self.bad(where, f"hot {cap}: switch {sw} not placed"); return
            sp = [p for p in L.geom(sw)[2] if p[0] in set(map(str, sup))]; rp = [p for p in L.geom(sw)[2] if p[0] in set(map(str, ret))]
            if not sp or not rp: self.bad(where, f"hot {cap}: switch pads {sup} / {ret} not found on {sw}"); return
            sn, rn = sp[0][1], rp[0][1]
            cs = [p["num"] for p in B.parts[cap]["pads"] if p["net"] == sn]; cr = [p["num"] for p in B.parts[cap]["pads"] if p["net"] == rn]
            if not cs or not cr: self.bad(where, f"hot {cap}: no pad on {sn} and {rn}"); return
            L.remove(cap)
            self.place_at_targets(cap, self.side_for(cap, s), turns, {cs[0]: sp, cr[0]: rp}, s.get("max_mm", 1.5), s.get("soft", False), extra_nets=False, where=where, hot=sw, within=s.get("within"), step=s.get("step"))
        elif "at_pin" in s:
            r = s["at_pin"]
            if not self.check_ref(r, where): return
            L.remove(r); T = {}
            for num, spec in s["pads"].items():
                tl = self.targets_of(spec)
                if not tl: self.bad(where, f"at_pin {r}: target {spec} not placed or unknown"); return
                if tl[0][1] in blib.NEVER_TARGET: self.say(f"  warning: {r} pad {num} target {spec} is on {tl[0][1]}, a plane net")
                T[str(num)] = tl
            self.place_at_targets(r, self.side_for(r, s), turns, T, s.get("max_mm"), s.get("soft", False), where=where, within=s.get("within"), step=s.get("step"))
        elif "auto" in s:
            left = [r for r in s["auto"] if self.check_ref(r, where)]
            for r in left: L.remove(r)
            while left:
                r = max(left, key=lambda r: (self.connectedness(r), -left.index(r))); left.remove(r)
                T = self.auto_targets(r)
                self.place_at_targets(r, self.side_for(r, s), turns, T, s.get("max_mm"), s.get("soft", True) if s.get("max_mm") else False, where=where)
        elif "translate" in s:
            self.translate(s, where)
        elif "twin_check" in s:
            self.twin = (float(s["dx"]), float(s["dy"])) if s["twin_check"] else None
            self.say(f"  twin check {'on ' + str(self.twin) if self.twin else 'off'}")
        elif "side" in s:
            for r in s["side"]: self.side_of[r] = blib.side1(s["to"])
            self.say(f"  side {s['to']} for {s['side']}")
        elif "claim" in s:
            L.claims[s["claim"]] = tuple(s["box"]); self.my_claims.append(dict(ref=s["claim"], box=list(s["box"]), group=self.g, why=s.get("why", "")))
            self.say(f"  claim {s['claim']} {s['box']}")
        elif "deviation" in s:
            self.deviations.append(dict(section=s["deviation"], box=s.get("box"), why=s.get("why", "")))
        elif "remove" in s:
            for r in s["remove"]: L.remove(r)
        elif "comment" in s or "note" in s: pass
        else: self.bad(where, f"unknown step {json.dumps(s)[:100]}")

    def connectedness(self, r):
        B, L = self.B, self.L; sc = 0.0
        sv = B.served_pads(r)
        if sv and sv[0] in L.P: sc += 3
        for p in B.parts[r]["pads"]:
            n = p["net"]
            if not B.is_signal_net(n): continue
            m = sum(1 for q, i in B.nets[n] if q != r and q in L.P)
            if m: sc += 1 + (2 if len(B.nets[n]) == 2 else 0)
        return sc

    def auto_targets(self, r):
        B, L = self.B, self.L; T = {}
        sv = B.served_pads(r)
        if sv and sv[0] in L.P:
            tp = [p for p in L.geom(sv[0])[2] if p[0] in set(sv[1])]
            if tp:
                n = tp[0][1]; mine = [p["num"] for p in B.parts[r]["pads"] if p["net"] == n]
                if mine: T[mine[0]] = tp
        if not T:
            for p in B.parts[r]["pads"]:
                n = p["net"]
                if not n or n in blib.NEVER_TARGET or n.endswith("/GND") or len(B.nets[n]) != 2: continue
                o = [L.geom(q)[2][i] for q, i in B.nets[n] if q != r and q in L.P]
                if o: T[p["num"]] = o
        return T

    def translate(self, s, where):
        B, L = self.B, self.L; src = s["from_fragment"]
        f = src if src.endswith(".json") else os.path.join(self.others, src + ".json")
        if not os.path.exists(f) and not src.endswith(".json"): f = os.path.join(os.path.dirname(os.path.abspath(self.out)), src + ".json")
        if not os.path.exists(f): self.bad(where, f"translate: no fragment {f}"); return
        F = load_placement(f); dx, dy = float(s.get("dx", 0)), float(s.get("dy", 0)); m = s.get("map", "4->5")
        pairs = []
        for r0 in s["translate"]:
            r = map_ref(r0, m) if m else r0
            if r is None or r0 not in F: self.bad(where, f"translate {r0}: not in {f} or no twin"); continue
            if not self.check_ref(r, where): continue
            L.remove(r); pairs.append((r0, r))
        for r0, r in pairs:
            x, y, t, sd = F[r0]; side = sd or B.parts[r0]["side"]
            if side != B.parts[r0]["side"] and B.parts[r]["side"] == B.parts[r0]["side"]: pass
            v = (x + dx, y + dy, t, side); f0 = L.faults(r, v)
            if not f0:
                L.put(r, v); self.costs[r] = 0.0; self.placed_by_recipe.append(r); self.say(f"  {r}: copy of {r0} at {v[0]:.2f},{v[1]:.2f} turn {t} {side}"); continue
            x0, y0 = v[0], v[1]; q0 = t // 90 % 4
            def cost(q, xs, ys, x0=x0, y0=y0, q0=q0):
                c = np.abs(xs[None, :] - x0) + np.abs(ys[:, None] - y0) + (0.0 if q == q0 else 0.5); return c, np.ones_like(c, bool)
            c0, _ = B.court(r, v)
            best = self.search(r, side, [q0 * 90] + [k for k in (0, 90, 180, 270) if k != q0 * 90], c0, cost, grows=(1.0, 2.0, 4.0))
            if best is None: self.bad(where, f"translate {r}: copy illegal ({f0}) and no legal spot within 4 mm"); continue
            c, xx, yy, q = best; L.put(r, (xx, yy, q * 90, side)); self.costs[r] = round(c, 3); self.placed_by_recipe.append(r)
            self.say(f"  {r}: copy of {r0} illegal ({', '.join(f0[:3])}); moved {abs(xx - x0) + abs(yy - y0):.2f} mm to {xx:.2f},{yy:.2f} turn {q * 90}")

    def finish(self):
        B, L = self.B, self.L
        mine = sorted(r for r in L.P if r not in B.fixed and B.group_of.get(r) == self.g)
        frag = {r: L.val(r) for r in mine}
        os.makedirs(os.path.dirname(os.path.abspath(self.out)), exist_ok=True)
        json.dump(frag, open(self.out, "w"), indent=0)
        faults = {r: L.faults(r) for r in self.placed_by_recipe if r in L.P}
        faults = {r: f for r, f in faults.items() if f}
        base_f = sum(1 for r in mine if r not in self.placed_by_recipe and L.faults(r))
        meta = dict(rings=self.my_rings, reserved=self.my_reserved, claims=self.my_claims, bottom=[r for r in mine if frag[r][3] == "B"],
                    deviations=self.deviations, failed=self.fail, costs=self.costs, recipes=self.recipes, base=self.opt.get("base"), others=self.others)
        json.dump(meta, open(self.out[:-5] + ".meta.json", "w"), indent=1)
        exp = {r for r in B.movable if B.group_of[r] == self.g}
        self.say(f"wrote {self.out}: {len(frag)} of {len(exp)} {self.g} parts, placed by the recipes {len(self.placed_by_recipe)}, "
                 f"bottom {len(meta['bottom'])}, failed steps {len(self.fail)}")
        if faults: self.say(f"faults of recipe-placed parts after all steps (a later ring or reserve can cause these): {faults}")
        if base_f: self.say(f"base parts with a fault (e.g. touching courtyards on the hand board): {base_f}")
        missing = sorted(exp - set(frag))
        if missing: self.say(f"not placed yet: {len(missing)} {missing[:30]}{' ...' if len(missing) > 30 else ''}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or "--group" not in " ".join(sys.argv): print(__doc__); sys.exit(2)
    R = Runner(sys.argv[1:]); R.run(); sys.exit(1 if R.fail else 0)
