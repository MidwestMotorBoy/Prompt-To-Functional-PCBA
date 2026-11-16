#!/usr/bin/env python3
"""plan_rules.py <bare.json> <constraints.json> <out spec.json> [intent.json] [--rules=<rules.json>] [--<rule>=0|1]
                [--<rule>_<param>=V] [--stock=1] [--escape= --grow= --mirror=] [--list=1]

Copper-rule add-on for the stock planner tools/copper/plan_copper.py. The stock planner is imported, not copied.
Every rule is one class below with a name (= its option), a default, a status (keep / rejected), its parameters and
a docstring that states the rule in board-independent terms. Rules key on what the circuit declares
(constraints.json: power nets with current, hot loops with switch pins and caps, the return net) and on geometry
(pad sizes, pitch, distances). Part kinds come from the reference-designator letter prefix (CLASSES, overridable in
rules.json "classes"), exactly as the stock roles.py does. No reference, net name or coordinate of any board is in
this file; board data lives in a rules.json file.

Where the stock planner has no hook, RulePlanner overrides one method and calls the stock method inside it; the
overridden methods are listed in OVERRIDES (and in NOTES.md / upstream.diff, which proposes the hooks upstream).
The only stock code copied is the body of Planner.grow_step (RulePlanner._grow_with_rules), because the grow loop has
no per-zone hook; it runs only when a grow rule is on.

Order of work (each rule hook runs at one point of the stock order):
  __init__ (stock)  -> setup()        reservations: gate_escape/sealed, pinesc, connesc (+ new rules)
  hot_loops_step    -> before_loops() pre-drawn tracks: gndpair, epstrip
  net_step(net)     -> after_net()    directjoin
  return_step       -> return_skip()  pads served by rule tracks (epstrip) are skipped
  return_join       -> join_tight()   joinfix
  room / clip_others-> room()/clip()  gndesc; reservations of every rule are honoured in clip_others
  mirror_step       -> after_mirror() mirror_minw (rejected)
  grow_step         -> grow_frozen/grow_base/grow_cut (nogrow_dead, nogrow_detour, grow_viaroom), after_grow() taps

Add a rule: subclass Rule, set name/default/status/params, write the docstring, implement the hooks it needs, and
append the class to RULES at the point of the order where it must run. See README.md."""
import sys, os, json, math, re, copy

HERE = os.path.dirname(os.path.abspath(__file__))


def _stock_dir():
    d = os.environ.get("PLAN_COPPER_DIR")
    if d: return d
    p = HERE
    while p != "/":
        if os.path.exists(os.path.join(p, "tools", "copper", "plan_copper.py")): return os.path.join(p, "tools", "copper")
        p = os.path.dirname(p)
    raise SystemExit("plan_rules: tools/copper/plan_copper.py not found (set PLAN_COPPER_DIR)")


sys.path.insert(0, _stock_dir())
import numpy as np
from scipy import ndimage
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
import plan_copper as pc

# Part kinds by reference-designator letter prefix (IPC-2612 / common practice). rules.json "classes" overrides.
CLASSES = {"connector": ["J", "CN", "X"], "ic": ["U", "IC"], "transistor": ["Q"]}
OVERRIDES = ["__init__", "run", "hot_loops_step", "net_step", "return_step", "return_join", "path", "room", "clip_others",
             "mirror_step", "grow_step"]


def prefix(ref):
    m = re.match(r"[A-Za-z]+", ref)
    return m.group(0).upper() if m else ""


# ------------------------------------------------------------------------------------------------------------ rules
class Rule:
    """Base class. name = option (--name=0|1); default = on/off; status = 'keep' or 'rejected'; params = extra
    numeric options (--name_param=V); measured = effect on the reference board (for the README table)."""
    name = ""; default = 0; status = "keep"; params = {}; measured = ""
    reserves = False                    # True: the rule makes reservations (keep_clear); power_first may withhold them

    def __init__(self, P, on, prm):
        self.P = P; self.on = bool(on); self.prm = prm

    def rep(self):
        return self.P.report.setdefault("rules", {}).setdefault(self.name, {})

    # hooks (no-ops by default)
    def setup(self): pass
    def before_loops(self): pass
    def after_net(self, net): pass
    def return_skip(self): return set()
    def join_tight(self): return None
    def join_fallback(self, net, L, sh): return False
    def room(self, net, L, r): return r
    def clip(self, net, L, g, loose_near): return g
    def after_mirror(self, n0): pass
    grows = False                       # True: the rule needs the hooked grow loop
    def grow_prepare(self): pass
    def grow_frozen(self, net, L, z): return False
    def grow_base(self, net, L, base): return base
    def grow_cut(self, net, L, z, g): return g
    def after_grow(self): pass


class GateEscape(Rule):
    """A hot loop's supply and return pours are convex hulls of the loop's pads. A signal pad whose centre lies inside
    such a hull keeps only the clearance and is sealed (no track or via fits). For each hot loop whose switch part is a
    discrete transistor (class 'transistor'), every signal pad of that part (its gate pins) that lies inside the
    loop's supply or return pad hull (pads grown 0.3 mm) gets an escape: a strip of width w from the pad centre out of
    the package, in the one of the four package-edge directions with the most free room within 3 mm, len mm past the
    pad edge (shortened to the free room - 0.6 mm, at least 0.3 mm), plus a via site (via + via_room mm) at its end.
    Other nets' power copper keeps the clearance from it. Defaults len 0.9, w 0.6, via_room 0.25 (router needs via +
    clearance + raster margin free); all_gates=1 takes every gate pin, also outside the hulls. Source: stagepwr
    round 2 (gate pin of a half-bridge FET beside the big D1 pad)."""
    name = "gate_escape"; default = 1; reserves = True; params = {"len": 0.9, "w": 0.6, "via_room": 0.25, "all_gates": 0}
    measured = "with sealed + taps: 29 -> 24 of 396"

    def setup(self):
        P = self.P; sealed = P.rule_on("sealed")
        if not (self.on or sealed): return
        C = P.d.C; rep = []; GL, GW, GV, ALL = self.prm["len"], self.prm["w"], self.prm["via_room"], int(self.prm["all_gates"])
        for name, hl in sorted(C.get("hot_loops", {}).items()):
            for sp in hl["switch_pins"][:1]:
                ref = sp.split(".")[0]
                if ref not in P.d.by_ref or not P.is_class(ref, "transistor"): continue
                L = P.d.fp[ref]["layer"]; pads = [p for p in P.d.by_ref[ref] if L in p["shapes"]]
                if not pads: continue
                Pn, Gn = P.d.board(hl["supply"]), P.d.board(hl["ret"]); caps = [c for c in hl["caps"] if c in P.d.by_ref]
                cand = pads + [q for c in caps for q in P.d.by_ref[c] if L in q["shapes"]]
                hulls = [unary_union([P.d.pad_poly(q, L).buffer(0.3, 4) for q in cand if q["net"] == n]).convex_hull for n in (Pn, Gn)]
                todo = [p for p in pads] if self.on else []
                if sealed:          # the 'sealed' rule: other small parts' signal pads inside the hulls too
                    for q, qg in P.padpoly[L]:
                        if qg is None or q["ref"] == ref or q in todo or len(P.d.by_ref[q["ref"]]) > 4: continue
                        if P.d.role(q["net"]) == "signal" and any(h.buffer(-0.05).contains(qg.centroid) for h in hulls): todo.append(q)
                for p in todo:
                    if P.d.role(p["net"]) != "signal": continue
                    own = pads if p["ref"] == ref else [q for q in P.d.by_ref[p["ref"]] if L in q["shapes"]]
                    bx = unary_union([P.d.pad_poly(q, L) for q in own]).bounds
                    g = P.d.pad_poly(p, L); a0, b0, a1, b1 = g.bounds; cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
                    if ALL == 0 and not any(h.buffer(-0.05).intersects(g.centroid) for h in hulls): continue
                    best = None
                    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                        ex = a0 if dx < 0 else a1 if dx > 0 else cx; ey = b0 if dy < 0 else b1 if dy > 0 else cy
                        probe = LineString([(ex, ey), (ex + 3 * dx, ey + 3 * dy)]).buffer(GW / 2, cap_style=2)
                        inside_pkg = (dx < 0 and ex - bx[0] > 0.3) or (dx > 0 and bx[2] - ex > 0.3) or (dy < 0 and ey - bx[1] > 0.3) or (dy > 0 and bx[3] - ey > 0.3)
                        if inside_pkg: continue
                        dmin = 3.0
                        for q, qg in P.padpoly[L]:
                            if q is p or qg is None or q["net"] == p["net"]: continue
                            if qg.intersects(probe): dmin = min(dmin, Point(ex, ey).distance(qg))
                        if best is None or dmin > best[0]: best = (dmin, dx, dy, ex, ey)
                    if best is None: continue
                    dmin, dx, dy, ex, ey = best
                    ln = min(GL, max(0.3, dmin - 0.6))
                    strip = LineString([(cx, cy), (ex + ln * dx, ey + ln * dy)]).buffer(GW / 2, cap_style=2)
                    vs = Point(ex + ln * dx, ey + ln * dy).buffer(pc.VIA_D / 2 + GV, 16)
                    keep = unary_union([strip, vs]).difference(unary_union([qg for q, qg in P.padpoly[L] if q["net"] != p["net"] and qg is not None]))
                    P.keep_clear(p["net"], L, keep)
                    rep.append(dict(loop=name, pad=p["key"], net=p["net"], dir=[dx, dy], len_mm=round(ln, 2), free_mm=round(dmin, 2)))
        P.report["gate_escapes"] = rep


class Sealed(Rule):
    """Extends gate_escape to every other small part (4 pads or fewer) whose signal pad centre lies inside a hot-loop
    hull (a gate resistor or bootstrap part between the loop pads). Same strip and via site as gate_escape; drawn in
    the same pass. Source: stagepwr round 2."""
    name = "sealed"; default = 1; reserves = True
    measured = "part of 29 -> 24 of 396 (with gate_escape, taps)"


class PinEscape(Rule):
    """A signal pin of a fine-pitch IC (pin short side <= max_pin mm) within NEAR_TERM_MM (1 mm) of a foreign power
    pad of the same IC gets no escape room from that pour (the stock planner exempts pads near a terminal). Such a pin
    gets a reservation: a pin-width strip straight out of the package, len mm past the pad, and a via site (via +
    via_room mm) at its end, kept by other nets' power copper on both outer layers. near=0 takes every signal pin of
    the selected ICs. Which ICs (select): 'walled' = plan once without this rule and pick the ICs that have at least
    one such near-power pin sealed in a closed pocket of its layer (see walled(): the free room connected to the pin
    reaches less than walled_r = 3 mm and holds no via site); 'walled_pins' = the same but only those pins; 'all' = every IC with pins of
    two or more >= 1 A power nets; 'refs' = the list in refs (board data in rules.json). Defaults len 0.9, via_room 0.2,
    max_pin 0.45, select walled. Source: portcu round 3 (CC pins 0.98 mm from the PD chip's VBUS pad)."""
    name = "pinesc"; default = 1; reserves = True
    params = {"len": 0.9, "via_room": 0.2, "near": 1, "max_pin": 0.45, "select": "walled", "refs": [], "pins": [], "walled_room": 0.0, "walled_r": 3.0}
    measured = "with gndpair: 7 of 373 -> 5 of 369 (refs=[port-2 PD chip]); all ICs: 7 of 371"

    def candidates(self, ref, L, ps):
        P = self.P; out = []
        pp = [(p, P.d.pad_poly(p, L)) for p in ps if L in p["shapes"] and not p.get("drill")]
        if not pp: return out
        x0, y0, x1, y1 = unary_union([g for _, g in pp]).bounds
        for p, g in pp:
            if P.d.role(p["net"]) != "signal" or P.short_side(g) > self.prm["max_pin"]: continue
            if int(self.prm["near"]) and not any(q["net"] in P.d.power and q["net"] not in P.d.ret and P.d.role(q["net"]) != "signal" and qg.distance(g) <= pc.NEAR_TERM_MM + 0.05 for q, qg in pp if q is not p): continue
            a0, b0, a1, b1 = g.bounds; cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
            d = None
            if a0 - x0 < 0.3: d = (-1, 0, a0, cy)
            elif x1 - a1 < 0.3: d = (1, 0, a1, cy)
            elif b0 - y0 < 0.3: d = (0, -1, cx, b0)
            elif y1 - b1 < 0.3: d = (0, 1, cx, b1)
            if d is None: continue
            out.append((p, g, (cx, cy), d))
        return out

    def power_ic(self, ps):
        P = self.P
        return {p["net"] for p in ps if p["net"] in P.d.power and P.d.current(p["net"]) >= 1.0 and P.d.role(p["net"]) != "return" and p["net"] not in P.d.ret}

    def setup(self):
        if not self.on: return
        P = self.P; rep = []; sel = self.prm["select"]; refs = set(self.prm["refs"] or []); pins = set(self.prm["pins"] or [])
        for ref, ps in sorted(P.d.by_ref.items()):
            if not P.is_class(ref, "ic"): continue
            if sel in ("refs", "walled", "walled_pins"):
                if ref not in refs: continue
            elif len(self.power_ic(ps)) < 2: continue
            for L in P.outer:
                for p, g, (cx, cy), (dx, dy, ex, ey) in self.candidates(ref, L, ps):
                    if sel == "walled_pins" and p["key"] not in pins: continue
                    ln = float(self.prm["len"]); w = P.short_side(g)
                    vx, vy = ex + dx * ln, ey + dy * ln
                    strip = LineString([(cx, cy), (vx, vy)]).buffer(w / 2, cap_style=2)
                    vs = Point(vx, vy).buffer(pc.VIA_D / 2 + float(self.prm["via_room"]), 16)
                    others = unary_union([qg for q, qg in P.padpoly[L] if q["net"] != p["net"] and qg is not None])
                    keep = unary_union([strip, vs]).difference(others.buffer(P.clr))
                    for LL in P.outer:
                        k = keep if LL == L else vs.difference(unary_union([qg for q, qg in P.padpoly[LL] if q["net"] != p["net"] and qg is not None] or [Polygon()]).buffer(P.clr))
                        if k.is_empty: continue
                        P.keep_clear(p["net"], LL, k)
                    rep.append(p["key"])
        self.rep()["pins"] = rep; self.rep()["select"] = sel

    def walled(self):
        """After a full plan without this rule: {ic ref: [pin keys]} of the candidate pins that sit in a closed pocket.
        Free cells of the pin's layer = cells at least the clearance from every other net's pad, planned copper, via,
        reservation and keep-out (room >= walled_room, default 0.0 mm: any opening at all). The pocket = the free
        cells connected to the pin's pad. A pin is walled when its pocket reaches no farther than walled_r (3 mm,
        about half the router's 6 mm search window) from the pin centre AND holds no via site (room for a via on both
        outer layers, as place_vias checks it). This is the local form of the router's 'no way' result."""
        P = self.P; out = {}; RES = pc.RES; t = float(self.prm["walled_room"]); R = float(self.prm["walled_r"])
        for ref, ps in sorted(P.d.by_ref.items()):
            if not P.is_class(ref, "ic"): continue
            for L in P.outer:
                for p, g, (cx, cy), d in self.candidates(ref, L, ps):
                    rm = {LL: P.room(p["net"], LL, loose=True) for LL in P.outer}
                    seed = P.raster(g); free = (rm[L] >= t) | seed
                    via = ~P.novia
                    for LL in P.outer: via &= (rm[LL] >= pc.VIA_D / 2 + pc.RAST_MM) & ~P.block[LL]
                    lab, _ = ndimage.label(free)
                    ids = np.unique(lab[seed]); ids = ids[ids > 0]
                    reg = np.isin(lab, ids); ii, jj = np.nonzero(reg)
                    far = float(np.hypot(P.x0 + (jj + 0.5) * RES - cx, P.y0 + (ii + 0.5) * RES - cy).max()) if len(ii) else 0.0
                    if far < R and not (reg & via).any(): out.setdefault(ref, []).append(p["key"])
        return out


class ConnEscape(Rule):
    """Each signal pad of a connector (class 'connector', 6+ pads on the layer, pad short side <= max_pad mm) on the
    package edge keeps a strip straight out of the connector, len mm past the pad and w mm wide, that other nets'
    power copper keeps the clearance from. A pour wrapped under a fine-pitch connector row otherwise leaves the
    stock 0.4 mm escape room, which is less than a signal track plus the high-current-to-signal clearance.
    Defaults len 1.0, w 0.4 (0.2 mm track + 2 x 0.1 mm over the 0.15 mm clearance, from the board's 0.25 mm
    HighCurrent-to-signal rule), max_pad 0.35. Source: portcu round 3 (USB-C CC pads between the VBUS pins)."""
    name = "connesc"; default = 1; reserves = True; params = {"len": 1.0, "w": 0.4, "max_pad": 0.35}
    measured = "9 -> 7 of 371"

    def setup(self):
        if not self.on: return
        P = self.P; rep = []
        for ref, ps in sorted(P.d.by_ref.items()):
            if not P.is_class(ref, "connector"): continue
            for L in P.outer:
                pp = [(p, P.d.pad_poly(p, L)) for p in ps if L in p["shapes"] and not p.get("drill")]
                if len(pp) < 6: continue
                x0, y0, x1, y1 = unary_union([g for _, g in pp]).bounds
                for p, g in pp:
                    if P.d.role(p["net"]) != "signal" or P.short_side(g) > self.prm["max_pad"]: continue
                    a0, b0, a1, b1 = g.bounds; cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
                    d = None
                    if y1 - b1 < 0.3: d = (0, 1, cx, b1)
                    elif b0 - y0 < 0.3: d = (0, -1, cx, b0)
                    elif a0 - x0 < 0.3: d = (-1, 0, a0, cy)
                    elif x1 - a1 < 0.3: d = (1, 0, a1, cy)
                    if d is None: continue
                    dx, dy, ex, ey = d; ln = float(self.prm["len"]); w = float(self.prm["w"])
                    strip = LineString([(cx, cy), (ex + dx * ln, ey + dy * ln)]).buffer(w / 2, cap_style=2)
                    others = unary_union([qg for q, qg in P.padpoly[L] if q["net"] != p["net"] and qg is not None])
                    k = strip.difference(others.buffer(P.clr))
                    if k.is_empty: continue
                    P.keep_clear(p["net"], L, k); rep.append(p["key"])
        self.rep()["pads"] = rep


class GndPair(Rule):
    """Two neighbouring return-net pins of one part with 8+ pads (centres 0.05-max_gap mm apart, pads under 1 mm2)
    are joined pin to pin by a track of pin width (max 0.2 mm) on their layer, drawn before any power copper, so one
    via or exposed-pad strip serves both. Default max_gap 0.55 mm (one 0.4-0.5 mm pitch). Source: portcu round 3
    (a GND pin lost its via site to the neighbouring pin's pinesc reservation)."""
    name = "gndpair"; default = 1; params = {"max_gap": 0.55}
    measured = "with pinesc: 7 of 373 -> 5 of 369"

    def before_loops(self):
        if not self.on: return
        P = self.P; n = 0
        for ref, pads in sorted(P.d.by_ref.items()):
            if len(pads) < 8: continue
            for L in P.outer:
                for net in sorted(P.d.ret):
                    on = [p for p in pads if p["net"] == net and L in p["shapes"] and not p.get("drill") and P.d.area(p) < 1.0]
                    obs = None
                    for i, p in enumerate(on):
                        for q in on[i + 1:]:
                            dd = math.hypot(p["x"] - q["x"], p["y"] - q["y"])
                            if dd > self.prm["max_gap"] or dd < 0.05: continue
                            w = min(0.2, P.short_side(P.d.pad_poly(p, L)), P.short_side(P.d.pad_poly(q, L)))
                            obs = P.obstacles(net, L) if obs is None else obs
                            if P.track_ok(net, L, (p["x"], p["y"]), (q["x"], q["y"]), w, obs=obs):
                                P.draw_track(net, L, (p["x"], p["y"]), (q["x"], q["y"]), w, self.name); n += 1
        self.rep()["tracks"] = n


class EpStrip(Rule):
    """A return-net pin of an IC with 12+ pads (pin short side <= 0.45 mm, within 0.8 mm of the IC's own exposed pad
    of the same net, EP = a pad of 1 mm2 or more) gets a track into that exposed pad, drawn on the first outer layer
    before any power copper: straight (0.25 mm or the pin width, else 0.15 mm) to the nearest legal point at least
    0.08 mm inside the EP within 1.2 mm; else an L (along the pin axis 0.3-1.0 mm, then into the EP); else a 0.15 mm
    track to an already served same-net pin of the IC within 1.3 mm. A served pin is skipped by the return step (no via
    search, no return-join corridor under the neighbour pins). Source: portcu round 3 (0.4 mm QFN GND pins)."""
    name = "epstrip"; default = 1
    measured = "19 of 398 -> 15 of 374"

    def before_loops(self):
        self.served = set()
        if not self.on: return
        P = self.P; L = P.outer[0]
        for ref, pads in sorted(P.d.by_ref.items()):
            if len(pads) < 12: continue
            for net in sorted(P.d.ret):
                on = [p for p in pads if p["net"] == net and L in p["shapes"] and not p.get("drill")]
                eps = [p for p in on if P.d.area(p) >= 1.0]
                if not eps: continue
                ep = unary_union([P.d.pad_poly(p, L) for p in eps]); epnums = {p["num"] for p in eps}
                pins = [p for p in on if p["num"] not in epnums]
                obs = P.obstacles(net, L); done = {}
                for p in sorted(pins, key=lambda p: P.d.pad_poly(p, L).distance(ep)):
                    pg = P.d.pad_poly(p, L); c = pg.centroid; s = P.short_side(pg)
                    if pg.distance(ep) > 0.8 or s > 0.45: continue
                    epi = ep.buffer(-0.08)
                    cand = sorted((math.hypot(x - c.x, y - c.y), x, y) for x in np.arange(c.x - 1.2, c.x + 1.21, 0.05) for y in np.arange(c.y - 1.2, c.y + 1.21, 0.05)
                                  if math.hypot(x - c.x, y - c.y) <= 1.2 and epi.contains(Point(x, y)))
                    hit = None
                    for w in (min(0.25, s), 0.15):
                        for dd, x, y in cand[:400]:
                            if P.track_ok(net, L, (c.x, c.y), (x, y), w, obs=obs): hit = ((x, y), w); break
                        if hit: break
                    if hit: P.draw_track(net, L, (c.x, c.y), hit[0], hit[1], "ep_strip"); done[p["key"]] = (c.x, c.y); continue
                    ec = ep.centroid; best2 = None
                    for ux, uy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        if (ec.x - c.x) * ux + (ec.y - c.y) * uy <= 0: continue
                        for k in np.arange(0.3, 1.01, 0.05):
                            e = (c.x + ux * k, c.y + uy * k)
                            for w in (min(0.25, s), 0.15):
                                if not P.track_ok(net, L, (c.x, c.y), e, w, obs=obs): continue
                                nn = sorted((math.hypot(x - e[0], y - e[1]), x, y) for x in np.arange(e[0] - 0.4, e[0] + 0.41, 0.05) for y in np.arange(e[1] - 0.4, e[1] + 0.41, 0.05) if epi.contains(Point(x, y)))
                                for dd, x, y in nn[:60]:
                                    if P.track_ok(net, L, e, (x, y), w, obs=obs):
                                        if best2 is None or k + dd < best2[0]: best2 = (k + dd, e, (x, y), w)
                                        break
                                break
                    if best2:
                        _, e, b2, w = best2
                        P.draw_track(net, L, (c.x, c.y), e, w, "ep_strip2"); P.draw_track(net, L, e, b2, w, "ep_strip2"); done[p["key"]] = (c.x, c.y)
                for p in pins:
                    if p["key"] in done: continue
                    pg = P.d.pad_poly(p, L); c = pg.centroid
                    if P.short_side(pg) > 0.45 or pg.distance(ep) > 1.5: continue
                    for k, xy in sorted(done.items(), key=lambda kv: math.hypot(kv[1][0] - c.x, kv[1][1] - c.y)):
                        if math.hypot(xy[0] - c.x, xy[1] - c.y) > 1.3: break
                        if P.track_ok(net, L, (c.x, c.y), xy, 0.15, obs=obs):
                            P.draw_track(net, L, (c.x, c.y), xy, 0.15, "ep_neighbour"); done[p["key"]] = (c.x, c.y); break
                self.served |= set(done)
        self.rep()["served"] = sorted(self.served)

    def return_skip(self): return getattr(self, "served", set())


class JoinFix(Rule):
    """When a return pad gets no via, the stock return_join runs a corridor on its own layer to the nearest return
    copper that holds a via, searched with tight=True (clearance only). Under a fine-pitch IC that corridor runs
    beneath the neighbouring signal pins and seals them. With this rule the search keeps the signal escape room
    (tight=False); a join that does not fit is left to the router, except a hot-loop return pad, which falls back to
    the stock tight join (hot_fallback, default 1). Source: ports / final round 3; fallback round 4."""
    name = "joinfix"; default = 1; params = {"hot_fallback": 1}
    measured = "24 of 396 -> 19 of 398"

    def join_tight(self): return False if self.on else None

    def join_fallback(self, net, L, sh):
        """hot_fallback=1: a hot-loop return pad (a switch pin or loop cap pad on the return net) whose join failed
        with the escape room is joined the stock way (clearance only): a loop's return must not be left open.
        Round 4 generality test: on the hand placement the 5 V buck's PGND pin was left open without it."""
        if not (self.on and int(self.prm["hot_fallback"])): return False
        P = self.P
        if getattr(self, "_hot", None) is None:
            keys = set(P.d.switch_pins)
            for hl in P.d.C.get("hot_loops", {}).values():
                for c in hl["caps"]: keys |= {p["key"] for p in P.d.by_ref.get(c, [])}
            self._hot = keys
        return any(p["key"] in self._hot and p["net"] == net and L in p["shapes"] and P.d.pad_poly(p, L).intersects(sh) for p in P.d.pads if p["net"] == net)


class DirectJoin(Rule):
    """A power terminal that the stock tree could not reach ('no path') gets a straight track from one of its pads to
    the nearest copper of its net on the net's main layer (pour or same-net pad), if that copper is within 2 mm and a
    track of 0.5, 0.3 or 0.2 mm (no wider than the pad) fits with the clearance. Source: portcu round 3 (a 1.5 A
    fine-pitch power pin to its own decoupling cap)."""
    name = "directjoin"; default = 1
    measured = "15 of 374 -> 15 of 373 (power pin joined, one router edge gone)"

    def after_net(self, net):
        if not self.on: return
        P = self.P; rep = P.report.get("nets", {}).get(net)
        if not rep or not rep.get("left_to_router"): return
        main = rep.get("main_layer")
        if not main: return
        T = {g["ref"]: g for g in P.d.terminals(net)}; left = []
        for item in rep["left_to_router"]:
            ref = item.split(" ")[0]
            if ref not in T or "no path" not in item: left.append(item); continue
            ok = False; obs = P.obstacles(net, main)
            cu = P.zones.get((net, main), {}).get("geom")
            others = [P.d.pad_poly(q, main) for q in P.d.pads if q["net"] == net and q["ref"] != ref and main in q["shapes"]]
            tgt = unary_union(([cu] if cu is not None else []) + others)
            for p in T[ref]["pads"]:
                if main not in p["shapes"] or ok: continue
                pg = P.d.pad_poly(p, main); c = pg.centroid; s = P.short_side(pg)
                if tgt.is_empty or tgt.distance(pg) > 2.0: continue
                tin = tgt.buffer(-0.12)
                tin = tin if not tin.is_empty else tgt
                q = tin.boundary.interpolate(tin.boundary.project(c)) if not tin.contains(c) else c
                for w in (min(0.5, s), min(0.3, s), 0.2):
                    if P.track_ok(net, main, (c.x, c.y), (q.x, q.y), w, obs=obs):
                        P.draw_track(net, main, (c.x, c.y), (q.x, q.y), w, "direct_join"); ok = True; break
            if ok: rep["joined"].append(ref + " (direct track)")
            else: left.append(item)
        rep["left_to_router"] = left


class GndEsc(Rule):
    """Return-net pads of connectors and of ICs with 8+ pads (pad short side <= 0.65 mm, area <= 1 mm2, not served by
    epstrip) keep the same escape room from other nets' power copper as signal pads do (clearance + the planner's
    escape, 0.4 mm), except within NEAR_TERM_MM of a loose_near shape. Otherwise a small GND pin boxed in by a power
    pour has no room for its own via. Source: portcu round 3 (USB-C GND pad beside the VBUS pins)."""
    name = "gndesc"; default = 1
    measured = "10 -> 9 of 371"

    def pads(self):
        P = self.P
        if getattr(self, "_g", None) is None:
            sv = set().union(*[r.return_skip() for r in P.rules]); out = {L: [] for L in P.outer}
            for p in P.d.pads:
                if p["net"] not in P.d.ret or p["key"] in sv or p.get("drill"): continue
                if not (P.is_class(p["ref"], "connector") or (P.is_class(p["ref"], "ic") and len(P.d.by_ref[p["ref"]]) >= 8)): continue
                for L in P.outer:
                    if L not in p["shapes"]: continue
                    g = P.d.pad_poly(p, L)
                    if P.short_side(g) > 0.65 or g.area > 1.0: continue
                    out[L].append(g)
            self._g = out
            self._r = {L: P.raster(unary_union(v).buffer(0.01)) if v else None for L, v in out.items()}
            self.rep()["pads"] = sum(len(v) for v in out.values())
        return self._g

    def room(self, net, L, r):
        P = self.P
        if not self.on or net in P.d.ret: return r
        self.pads(); m = self._r.get(L)
        if m is None: return r
        ds = ndimage.distance_transform_edt(~m) * pc.RES - P.clr - P.escape
        return np.minimum(r, ds)

    def clip(self, net, L, g, loose_near):
        P = self.P
        if not self.on or net in P.d.ret or g.is_empty: return g
        ps = self.pads().get(L, [])
        cut = [q.buffer(P.clr + P.escape, 4) for q in ps if loose_near is None or q.distance(loose_near) > pc.NEAR_TERM_MM]
        return g.difference(unary_union(cut)) if cut else g


class NogrowDead(Rule):
    """The grow step does not grow a dead piece of a hard outer-layer pour: a piece under 3 mm2 with no via, touching
    no track of its net, whose pads all belong to connectors (a connector's duplicate pin pair, joined only inside the
    plug). Grown 1.5 mm such a pad-only piece covers the escape room of the parts next to the connector. The piece
    keeps the clearance from the grown copper of its own net, so it stays its pad. Source: portcu round 3."""
    name = "nogrow_dead"; default = 1; grows = True
    measured = "15 of 373 -> 10 of 373"

    def grow_prepare(self):
        P = self.P; self.dead = {}
        if not self.on: return
        for (net, L), z in P.zones.items():
            if L in P.outer and not z["soft"]: self.dead[(net, L)] = self.pieces(net, L, z["geom"])
        self.rep()["dead_pieces"] = {f"{n} {L}": [[round(q.centroid.x, 2), round(q.centroid.y, 2), round(q.area, 2)] for q in v] for (n, L), v in self.dead.items() if v}

    def pieces(self, net, L, geom):
        P = self.P; out = []
        trs = [LineString([t["a"], t["b"]]).buffer(t["w"] / 2) for t in P.tracks if t["net"] == net and t["layer"] == L]
        for q in getattr(geom, "geoms", [geom]):
            if q.area >= 3.0: continue
            if any(q.buffer(0.01).contains(Point(v["x"], v["y"])) for v in P.vias if v["net"] == net): continue
            if any(q.intersects(t) for t in trs): continue
            refs = {p["ref"] for p, pg in P.padpoly[L] if pg is not None and p["net"] == net and pg.intersects(q)}
            if not refs or not all(P.is_class(r, "connector") for r in refs): continue
            out.append(q)
        return out

    def grow_base(self, net, L, base):
        dd = getattr(self, "dead", {}).get((net, L))
        return base.difference(unary_union([q.buffer(0.02) for q in dd])) if dd else base

    def grow_cut(self, net, L, z, g):
        dd = getattr(self, "dead", {}).get((net, L))
        return g.difference(unary_union([q.buffer(self.P.clr + 0.02) for q in dd])) if dd else g


class NogrowDetour(Rule):
    """REJECTED. A pour that is only a detour corridor on the other outer layer (zone kinds == {detour}) is not grown.
    Reference board: 15 -> 15 of 373 blocked, loss 1.034 -> 1.082 W (with nogrow_dead 10 -> 10, 1.083 W): no gain, more loss."""
    name = "nogrow_detour"; default = 0; status = "rejected"; grows = True
    measured = "15 -> 15 of 373, +0.05 W (rejected)"

    def grow_prepare(self):
        P = self.P
        self.frozen = {k for k, z in P.zones.items() if self.on and z["kinds"] <= {"detour"}}
        if self.on: self.rep()["frozen"] = sorted(f"{n} {L}" for n, L in self.frozen)

    def grow_frozen(self, net, L, z): return (net, L) in getattr(self, "frozen", set())


class GrowViaroom(Rule):
    """REJECTED. Grown copper (only the new copper, never a corridor) keeps mm clear of the signal pins of fine-pitch
    ICs (8+ pads, pins <= 0.45 mm wide) on the OTHER outer layer, to leave via sites. Reference board with 1.0: 5 -> 5 of 369,
    same loss."""
    name = "grow_viaroom"; default = 0; status = "rejected"; grows = True; params = {"mm": 1.0}
    measured = "5 -> 5 of 369 (rejected)"

    def grow_prepare(self):
        P = self.P; self.vr = {}
        if not self.on: return
        for L in P.outer:
            Lo = [l for l in P.outer if l != L][0]; gs = []
            for p in P.d.pads:
                if not P.is_class(p["ref"], "ic") or len(P.d.by_ref[p["ref"]]) < 8 or Lo not in p["shapes"] or p.get("drill"): continue
                if P.d.role(p["net"]) != "signal": continue
                g = P.d.pad_poly(p, Lo)
                if P.short_side(g) <= 0.45: gs.append(g.buffer(self.prm["mm"], 4))
            self.vr[L] = unary_union(gs) if gs else None

    def grow_cut(self, net, L, z, g):
        v = getattr(self, "vr", {}).get(L)
        return g.difference(v.difference(z["geom"])) if v is not None else g


class MirrorMinW(Rule):
    """REJECTED. A mirror piece (the copy of a pour on the other outer layer) whose mean width 2 x area / perimeter is
    under mm is dropped with its stitching vias. Reference board with 0.5: 10 -> 10 of 373, loss 1.034 -> 1.032 W; neutral."""
    name = "mirror_minw"; default = 0; status = "rejected"; params = {"mm": 0.5}
    measured = "10 -> 10 of 373 (neutral, rejected)"

    def after_mirror(self, n0):
        if not self.on: return
        P = self.P; mw = self.prm["mm"]; new = P.vias[n0:]; drop = []
        for (net, L), z in list(P.zones.items()):
            if z["kinds"] != {"mirror"}: continue
            keep = []
            for q in getattr(z["geom"], "geoms", [z["geom"]]):
                w = 2 * q.area / max(q.length, 1e-6)
                if w >= mw: keep.append(q); continue
                vs = [v for v in new if v["net"] == net and q.buffer(0.05).contains(Point(v["x"], v["y"]))]
                P.unvia(vs); new = [v for v in new if v not in vs]
                P.cu[L][P.raster(q) & (P.cu[L] == P.netid[net])] = -1
                drop.append([net, L, round(q.area, 1), round(w, 2), len(vs)])
            if keep: z["geom"] = unary_union(keep)
            else: del P.zones[(net, L)]
        self.rep()["dropped"] = drop


class Taps(Rule):
    """A small part (4 pads or fewer) with a pad on a switching net that is not one of the net's current terminals
    (a bootstrap cap's switch-node pad), more than far mm from the net's pour on the main layer, gets a MIN_W tap: the
    stock detour (vias at the pad, a corridor on the other outer layer, vias into the pour). Drawn AFTER the grow step,
    so the thin copper does not grow into a switch-node blob. Default far 3.0 mm: the router searches only a window of
    about 6 mm round a DRC end point and misses a pour farther away. Source: stagepwr round 2."""
    name = "taps"; default = 1; params = {"far": 3.0}
    measured = "part of 29 -> 24 of 396 (with gate_escape, sealed)"

    def after_grow(self):
        if not self.on: return
        P = self.P
        for net in sorted(n for n in P.d.power if P.d.power[n]["kind"] == "switching"):
            rep = P.report.setdefault("nets", {}).get(net, {}); main = rep.get("main_layer")
            if not main or (net, main) not in P.zones: continue
            T = {p["key"] for g in P.d.terminals(net) for p in g["pads"]}
            tree = P.cu[main] == P.netid[net]
            for p in P.d.pads:
                if p["net"] != net or p["key"] in T or main not in p["shapes"] or len(P.d.by_ref[p["ref"]]) > 4: continue
                gp = P.d.pad_poly(p, main)
                if P.zones[(net, main)]["geom"].distance(gp) < self.prm["far"]: continue
                ok = P.detour(net, main, gp, pc.MIN_W, 0.5, tree)
                P.report.setdefault("taps", []).append(dict(pad=p["key"], net=net, drawn=bool(ok)))


class PowerFirst(Rule):
    """Hard limits first: a reservation (escape strip, via site or exit strip of any rule with reserves=True) must not
    take the room of a series current path. After the plan, if a series terminal of a power net (roles.py: a part in
    series with the current, e.g. a sense resistor or a switch) is left to the router with 'no path', the planner
    plans once more with every reservation rule off; for each such net that this plan joins, every reservation that
    touches that net's copper (plus the clearance) on the same layer is withheld, and the board is planned again.
    Costs two more planner runs, only on boards where a series terminal is lost; on a board where no series
    terminal is lost the plan is unchanged. Source: round 4 generality test (hand placement: gate-resistor escapes
    walled a 5 A sense-resistor path)."""
    name = "power_first"; default = 1
    measured = "best placement: no change (no series terminal lost); hand placement: see NOTES.md"

    def lost(self):
        P = self.P; out = {}
        for net, r in P.report.get("nets", {}).items():
            T = {g["ref"]: g for g in P.d.terminals(net)}
            for item in r.get("left_to_router", []):
                ref = item.split(" ")[0]
                if ref in T and T[ref]["kind"] == "series" and "no path" in item: out.setdefault(net, []).append(ref)
        return out


# Dispatch order = the order in which hooks of the same kind run. New rules: append at the right point.
RULES = [GateEscape, Sealed, PinEscape, ConnEscape, GndPair, EpStrip, JoinFix, DirectJoin, GndEsc, NogrowDead,
         NogrowDetour, GrowViaroom, MirrorMinW, Taps, PowerFirst]


# ---------------------------------------------------------------------------------------------------------- planner
class RulePlanner(pc.Planner):
    def __init__(self, dump, cons, intent=None, escape=0.4, grow=1.5, mirror=3.0, cfg=None):
        cfg = cfg or {}
        self.classes = dict(CLASSES, **cfg.get("classes", {}))
        self.keep = {}                      # layer -> [(net, geom)]: reservations other nets' power copper keeps clear of
        self._join = False
        self.yield_to = cfg.get("_yield_to", {})     # layer -> geometry that reservations must not touch (power_first)
        super().__init__(dump, cons, intent, escape=escape, grow=grow, mirror=mirror)
        rc = cfg.get("rules", {})
        self.rules = []
        for R in RULES:
            c = rc.get(R.name, {}); c = c if isinstance(c, dict) else {"on": c}
            prm = {k: c.get(k, v) for k, v in R.params.items()}
            self.rules.append(R(self, c.get("on", R.default), prm))
        self.report["rules_on"] = [r.name for r in self.rules if r.on]
        for r in self.rules: r.setup()

    # helpers shared by rules
    def rule_on(self, name): return any(r.on for r in self.rules if r.name == name)
    def rule(self, name): return next(r for r in self.rules if r.name == name)
    def is_class(self, ref, cls): return prefix(ref) in self.classes.get(cls, [])

    def keep_clear(self, net, L, g):
        """Keep g free of every other net's power copper (clip_others) and out of the planner's rasters."""
        y = self.yield_to.get(L)
        if y is not None and g.intersects(y.buffer(self.clr)):
            self.report.setdefault("rules", {}).setdefault("power_first", {}).setdefault("withheld", []).append([net, L, [round(v, 2) for v in g.bounds]])
            return
        self.keep.setdefault(L, []).append((net, g))
        self.block[L] |= self.raster(g.buffer(self.clr))
        self.blockgeom[L].append(g)

    @staticmethod
    def short_side(g):
        r = g.minimum_rotated_rectangle; c = list(r.exterior.coords)
        return min(math.hypot(c[1][0] - c[0][0], c[1][1] - c[0][1]), math.hypot(c[2][0] - c[1][0], c[2][1] - c[1][1]))

    def track_ok(self, net, L, a, b, w, obs=None):
        obs = self.obstacles(net, L) if obs is None else obs
        return LineString([a, b]).buffer(w / 2, 4).distance(obs) >= self.clr - 1e-4

    def draw_track(self, net, L, a, b, w, kind):
        t = dict(net=net, layer=L, a=(round(a[0], 4), round(a[1], 4)), b=(round(b[0], 4), round(b[1], 4)), w=round(w, 3))
        self.tracks.append(t)
        g = LineString([a, b]).buffer(w / 2, 4)
        self.cu[L][self.raster(g) & (self.cu[L] < 0)] = self.netid[net]
        self.keep.setdefault(L, []).append((net, g))
        self.report.setdefault("rule_tracks", {}).setdefault(kind, []).append([net, t["a"], t["b"], t["w"]])
        return t

    # stock methods with hooks (each calls the stock method)
    def run(self):
        if self.rule_on("taps") and self.grow <= 0: self.grow = 1e-9        # grow_step must run for the taps
        return super().run()

    def hot_loops_step(self):
        for r in self.rules: r.before_loops()
        return super().hot_loops_step()

    def net_step(self, net):
        super().net_step(net)
        for r in self.rules: r.after_net(net)

    def return_step(self):
        sv = set().union(*[r.return_skip() for r in self.rules])
        if not sv: return super().return_step()
        keep = self.d.by_ref
        self.d.by_ref = {r: [p for p in ps if p["key"] not in sv] for r, ps in keep.items()}
        try: super().return_step()
        finally: self.d.by_ref = keep
        self.report["return_pads"]["served_by_rules"] = sorted(sv)

    def return_join(self, net, L, sh):
        loose = any(r.join_tight() is False for r in self.rules); self._join = loose
        try: ok = super().return_join(net, L, sh)
        finally: self._join = False
        if not ok and loose and any(r.join_fallback(net, L, sh) for r in self.rules):
            ok = super().return_join(net, L, sh)          # stock (tight) join for a hot-loop return pad
            self.report.setdefault("rules", {}).setdefault("joinfix", {}).setdefault("hot_fallback", []).append([net, L, [round(v, 2) for v in sh.bounds], bool(ok)])
        return ok

    def path(self, net, L, start_mask, goal_mask, w, near_mask, tight=False):
        if self._join: tight = False
        return super().path(net, L, start_mask, goal_mask, w, near_mask, tight=tight)

    def room(self, net, L, loose=False):
        r = super().room(net, L, loose)
        if loose or self.escape <= 0: return r
        for ru in getattr(self, "rules", []): r = ru.room(net, L, r)
        return r

    def clip_others(self, net, L, g, loose_near=None):
        g = super().clip_others(net, L, g, loose_near)
        cut = [k.buffer(self.clr, 4) for n, k in self.keep.get(L, []) if n != net]
        if cut and not g.is_empty: g = g.difference(unary_union(cut))
        for ru in getattr(self, "rules", []): g = ru.clip(net, L, g, loose_near)
        return g

    def mirror_step(self, min_a):
        n0 = len(self.vias)
        super().mirror_step(min_a)
        for r in self.rules: r.after_mirror(n0)

    def grow_step(self, step=0.5):
        gr = [r for r in self.rules if r.grows and r.on]
        if not gr: super().grow_step(step)
        else: self._grow_with_rules(step, gr)
        for r in self.rules: r.after_grow()

    def _grow_with_rules(self, step, gr):
        """Copy of the stock Planner.grow_step loop with three hooks per zone (frozen, base, cut). Proposed upstream as
        hooks in grow_step (upstream.diff); then this copy goes away."""
        for r in gr: r.grow_prepare()
        rep = {}; nets = sorted(self.d.power, key=lambda n: (-self.d.current(n), n)); left = self.grow
        while left > 1e-6:
            d = min(step, left); left -= d
            for net in nets:
                for L in self.outer:
                    z = self.zones.get((net, L))
                    if not z or z["soft"] or "mirror" in z["kinds"] or any(r.grow_frozen(net, L, z) for r in gr): continue
                    base = z["geom"]
                    for r in gr: base = r.grow_base(net, L, base)
                    if base.is_empty: continue
                    g = base.buffer(d, 4).intersection(self.inside)
                    for r in gr: g = r.grow_cut(net, L, z, g)
                    g = self.clip_others(net, L, g)
                    tr = [LineString([t["a"], t["b"]]).buffer(t["w"] / 2 + self.clr, 4) for t in self.tracks if t["layer"] == L and t["net"] != net]
                    bl = [b.buffer(self.clr, 4) for b in self.blockgeom[L]] + self.npth
                    if tr or bl: g = g.difference(unary_union(tr + bl))
                    g = unary_union([q for q in getattr(g, "geoms", [g]) if q.intersects(base) and q.intersection(base).area > 0.05])
                    if g.is_empty: continue
                    a0 = z["geom"].area; z["geom"] = unary_union([z["geom"], g]); self.cu[L][self.raster(g) & (self.cu[L] < 0)] = self.netid[net]
                    rep[f"{net} {L}"] = round(rep.get(f"{net} {L}", 0) + z["geom"].area - a0, 1)
        self.report["grown_mm2"] = rep


# ------------------------------------------------------------------------------------------------------------- CLI
def load_cfg(path=None, cli=None):
    """rules.json (optional) + command-line overrides -> cfg dict {planner, classes, rules}."""
    cfg = json.load(open(path)) if path else {}
    cfg = copy.deepcopy(cfg); rc = cfg.setdefault("rules", {}); pl = cfg.setdefault("planner", {})
    cli = dict(cli or {})
    if int(cli.pop("stock", 0)):
        for R in RULES: rc[R.name] = {"on": 0}
    for k in ("escape", "grow", "mirror"):
        if k in cli: pl[k] = float(cli.pop(k))
    names = {R.name: R for R in RULES}
    for n in list(rc):
        if not isinstance(rc[n], dict): rc[n] = {"on": rc[n]}
        if n not in names and not n.startswith("_"): raise SystemExit(f"plan_rules: unknown rule '{n}' in rules file")
    for k in sorted(cli, key=len):
        v = cli[k]
        if k in names:
            rc.setdefault(k, {})["on"] = int(float(v)); continue
        for n, R in names.items():
            if k.startswith(n + "_") and k[len(n) + 1:] in R.params:
                p = k[len(n) + 1:]; d = R.params[p]
                c = rc.setdefault(n, {})
                c[p] = (v.split(",") if v else []) if isinstance(d, list) else (v if isinstance(d, str) else type(d)(float(v)))
                break
        else:
            raise SystemExit(f"plan_rules: unknown option --{k}")
    return cfg


def plan(dump, cons, cfg, intent=None, log=print):
    """Plan with the rules of cfg. pinesc select 'walled'/'walled_pins' plans twice (first without pinesc); power_first
    plans twice more when a series terminal is lost."""
    pl = cfg.get("planner", {}); kw = dict(escape=float(pl.get("escape", 0.4)), grow=float(pl.get("grow", 1.5)), mirror=float(pl.get("mirror", 3)))
    pe = cfg.get("rules", {}).get("pinesc", {}); pe = pe if isinstance(pe, dict) else {"on": pe}
    walled = None
    if pe.get("on", PinEscape.default) and pe.get("select", PinEscape.params["select"]) in ("walled", "walled_pins"):
        c1 = copy.deepcopy(cfg); c1["rules"]["pinesc"] = dict(pe, on=0)
        P1 = RulePlanner(dump, cons, intent, cfg=c1, **kw); P1.run()
        walled = PinEscape(P1, 1, {k: pe.get(k, v) for k, v in PinEscape.params.items()}).walled()
        log(f"pinesc walled (first pass without pinesc): {json.dumps(walled)}")
        cfg = copy.deepcopy(cfg); cfg["rules"]["pinesc"] = dict(pe, refs=sorted(walled), pins=sorted(k for v in walled.values() for k in v))
    P = RulePlanner(dump, cons, intent, cfg=cfg, **kw)
    spec = P.run()
    if P.rule_on("power_first"):
        lost = P.rule("power_first").lost()
        if lost:
            c0 = copy.deepcopy(cfg)
            for R in RULES:
                if R.reserves: c0["rules"][R.name] = dict(c0["rules"].get(R.name, {}), on=0)
            P0 = RulePlanner(dump, cons, intent, cfg=c0, **kw); P0.run()
            lost0 = P0.rule("power_first").lost(); geo = {}
            for net, refs in lost.items():
                if set(refs) <= set(lost0.get(net, [])): continue          # lost without reservations too: not theirs
                for (n, L), z in P0.zones.items():
                    if n == net and L in P0.outer: geo.setdefault(L, []).append(z["geom"])
            log(f"power_first: series terminals lost {json.dumps(lost)}; without reservations {json.dumps(lost0)}")
            if geo:
                cfg = copy.deepcopy(cfg); cfg["_yield_to"] = {L: unary_union(g) for L, g in geo.items()}
                P = RulePlanner(dump, cons, intent, cfg=cfg, **kw); spec = P.run()
                spec["report"].setdefault("rules", {}).setdefault("power_first", {})["lost_before"] = lost
                spec["report"]["rules"]["power_first"]["lost_after"] = P.rule("power_first").lost()
    if walled is not None: spec["report"].setdefault("rules", {}).setdefault("pinesc", {})["walled"] = walled
    return spec


def rule_table():
    out = []
    for R in RULES:
        doc = " ".join((R.__doc__ or "").split())
        out.append(f"{R.name:14s} default {'on ' if R.default else 'off'} {R.status:8s} params {json.dumps(R.params)}\n    {doc}")
    return "\n".join(out)


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    opt = dict((x[2:].split("=", 1) + ["1"])[:2] for x in sys.argv[1:] if x.startswith("--"))
    if opt.pop("list", None): print(rule_table()); return
    cfg = load_cfg(opt.pop("rules", None), opt)
    intent = json.load(open(a[3])) if len(a) > 3 else None
    spec = plan(a[0], a[1], cfg, intent)
    json.dump(spec, open(a[2], "w"))
    R = spec["report"]
    print("rules on", json.dumps(R.get("rules_on")))
    for n, r in R.get("nets", {}).items():
        print(f"{n}: {r['current_a']} A, {r['terminals']} terminals, span {r['span_mm']} mm, layer {r.get('main_layer')}{' + ' + r['inner_layer'] if 'inner_layer' in r else ''}, vias {r['vias']}, left to router {r['left_to_router']}")
    print("hot loops", json.dumps(R.get("hot_loops")))
    print("return pads", json.dumps({k: (v if not isinstance(v, list) else v[:12]) for k, v in R["return_pads"].items()}))
    print("gate escapes", json.dumps(R.get("gate_escapes")))
    print("taps", json.dumps(R.get("taps")))
    print("rules", json.dumps(R.get("rules")))
    print(f"{len(spec['zones'])} zones, {len(spec['vias'])} vias, {len(spec['tracks'])} tracks, {R['seconds']} s; notes: {R['notes']}")


if __name__ == "__main__":
    main()
