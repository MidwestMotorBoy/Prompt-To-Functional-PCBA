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
  __init__ (stock)  -> setup()        + connesc_big (rejected), gatevia (draws at gate_escape's sites; after them)
  hot_loops_step    -> before_loops() pre-drawn tracks: gndpair, epstrip; after_loops(): ret_band
  net_step(net)     -> detour_args()  sw_detour (inside the net step); after_net(): directjoin
  return_step       -> return_skip()  pads served by rule tracks (epstrip) are skipped; after_return(): gndtie
  return_join       -> join_tight()   joinfix
  room / clip_others-> room()/clip()  gndesc; reservations of every rule are honoured in clip_others
  mirror_step       -> mirror_hide()  mirror_skip_supply; after_mirror(): mirror_minw (rejected), mirror_maxa (+minw2)
  grow_step         -> grow_frozen/grow_base/grow_cut (nogrow_dead, sw/pw/stub_nogrow, nogrow_detour, grow_viaroom),
                       after_grow(): taps (tap_max), padjoin, padpair, capjoin  (README.md: one order for V, Q, B, M)

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
from shapely.strtree import STRtree
import plan_copper as pc

# Part kinds by reference-designator letter prefix (IPC-2612 / common practice). rules.json "classes" overrides.
CLASSES = {"connector": ["J", "CN", "X"], "ic": ["U", "IC"], "transistor": ["Q"]}
OVERRIDES = ["__init__", "run", "hot_loops_step", "net_step", "detour", "return_step", "return_join", "path", "room",
             "clip_others", "mirror_step", "grow_step"]


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
    def after_loops(self): pass
    def after_net(self, net): pass
    def detour_args(self, net, w, I): return w, I
    def return_skip(self): return set()
    def after_return(self): pass
    def join_tight(self): return None
    def join_fallback(self, net, L, sh): return False
    def room(self, net, L, r): return r
    def clip(self, net, L, g, loose_near): return g
    def mirror_hide(self): return {}
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
                    held = not P.keep_clear(p["net"], L, keep)
                    rep.append(dict(loop=name, pad=p["key"], net=p["net"], dir=[dx, dy], len_mm=round(ln, 2), free_mm=round(dmin, 2)))
                    if held: rep[-1]["withheld"] = True
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
    params = {"len": 0.9, "via_room": 0.2, "near": 1, "max_pin": 0.45, "select": "walled", "refs": [], "pins": [], "walled_room": 0.0, "walled_r": 3.0,
              "twins": 0, "twin_d": 3.0, "twin_tol": 0.15, "twin_frac": 1.0}
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
        before = {L: P.block[L].copy() for L in P.outer}; nb = {L: len(P.blockgeom[L]) for L in P.outer}
        tw = self.twins(refs) if int(self.prm["twins"]) and sel in ("refs", "walled", "walled_pins") else []
        if tw:
            self.rep()["twins"] = tw; refs |= set(tw)
            if sel == "walled_pins": sel = "walled"         # a twin takes all its candidate pins
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
        self.mask = {L: P.block[L] & ~before[L] for L in P.outer}            # gndtie relaxes exactly these
        self.geoms = {L: P.blockgeom[L][nb[L]:] for L in P.outer}

    def twins(self, refs):
        """twins=1 (select walled / walled_pins / refs): an IC is added when it is a copy of a selected IC around its
        candidate pins: same footprint, rotation and side, and of the parts on the candidate pins' nets with a pad
        within twin_d mm of those pins at least twin_frac (default 1.0 = all) sit at the same offset (twin_tol mm)
        with the same footprint and rotation round the other IC, counted both ways. Idea: a repeated block whose
        pin cluster is a copy needs the same reservations even where the first plan does not wall it yet (round 4:
        port 1's PD chip needed pinesc once its cluster was made a copy of port 2's). MEASURED (round 5): on the
        r4_port1 / merged placement 4 of 5 neighbours match (the west decoupling cap of the PD chip was not part of
        the cluster copy), on the best / k1 placements 1 of 5; with twin_frac 1.0 it adds nothing, so the reference board keeps
        the second PD chip as board data (select=refs). Returns the added refs."""
        P = self.P; D = float(self.prm["twin_d"]); tol = float(self.prm["twin_tol"]); fr = float(self.prm["twin_frac"]); out = []
        geo = {r: unary_union([P.d.pad_poly(p, L) for p in ps for L in p["shapes"] if not p.get("drill")] or [Polygon()]) for r, ps in P.d.by_ref.items()}
        def pose(r): f = P.d.fp[r]; return (f["fp"], round(f["rot"] % 360), f["layer"])
        def hood(r):
            cp = [p for L in P.outer for p, g, c, d in self.candidates(r, L, P.d.by_ref[r])]
            if not cp: return []
            nets = {p["net"] for p in cp}; a = P.d.fp[r]
            g = unary_union([P.d.pad_poly(p, L) for p in cp for L in p["shapes"]]).buffer(D)
            return [pose(q) + (P.d.fp[q]["x"] - a["x"], P.d.fp[q]["y"] - a["y"]) for q, ps in P.d.by_ref.items()
                    if q != r and any(x["net"] in nets for x in ps) and geo[q].intersects(g)]
        def share(X, Y): return sum(any(x[:3] == y[:3] and math.hypot(x[3] - y[3], x[4] - y[4]) <= tol for y in Y) for x in X) / max(len(X), 1)
        for a in sorted(refs):
            if a not in P.d.by_ref: continue
            ha = hood(a)
            for b in sorted(P.d.by_ref):
                if b in refs or b in out or not P.is_class(b, "ic") or pose(b) != pose(a): continue
                hb = hood(b); s = min(share(ha, hb), share(hb, ha)) if ha and hb else 0.0
                self.rep().setdefault("twin_share", {})[f"{a}-{b}"] = round(s, 2)
                if s >= fr - 1e-9: out.append(b)
        return out

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
        P = self.P; tm = P.rule("tap_max"); old = pc.DETOUR_MAX_MM
        if tm.on: pc.DETOUR_MAX_MM = float(tm.prm["mm"])
        try: self._taps()
        finally: pc.DETOUR_MAX_MM = old

    def _taps(self):
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


# ------------------------------------------------------------------------------------------ round-4 rules (round 5 port)
# Ported from team A round 4: r4_port1 PlannerQ (gatevia, gndtie, padjoin, rejected connesc_big), r4_bcu PlannerB
# (ret_band, tap_max, sw_nogrow, pw_nogrow, stub_nogrow, mirror_skip_supply, mirror_maxa, sw_detour, rejected
# mirror_minw2), r4_vbus PlannerV (padpair) and round-5 r5_merge PlannerM (capjoin, and gatevia's chk). Each is
# spec-identical to its source planner on that worker's board (r5_general/NOTES.md).

class GateVia(Rule):
    """The escape strip and via site that gate_escape / sealed reserve for a discrete switch's (class 'transistor')
    signal pin sealed in its hot-loop hull are drawn as copper: a track of the pin's net (pin width, at most 0.25 mm)
    from the pad centre to the site and a through via there. A reserved site is free only on the planner's layers;
    the router may still run an inner-layer track of an earlier net over it, so the gate has no via left. A placed via
    is an obstacle to every net on every layer and the router starts the gate edge from it. chk=1 (default): each
    via is checked on exact shapes against every other net's pad on both outer layers (copper clearance and
    0.2 mm via-hole-to-pad), the other vias (via pitch) and the board edge; a via that fails slides outward along the
    escape (0.05 mm steps, up to 0.8 mm), else it and its track are dropped (the gate is left to the router).
    Sources: r4_port1 q3 (HG gate of a half-bridge FET: the Kelvin pair routed first took the site on In2), r5_merge
    gatevia_chk (a FET turned 90 degrees put a gate site 0.11 mm from a bottom-side cap pad: 4 DRC errors)."""
    name = "gatevia"; default = 0; params = {"chk": 1, "min_dist": 0.75}
    measured = "r4_port1 v5p (with padjoin, gndtie, pinesc on both PD chips): sub-route 11 -> 4 failed of 128, HG1 routes; merged board without chk 4 DRC errors, with chk 0"

    def setup(self):
        if not self.on: return
        P = self.P; rep = []; n0, t0 = len(P.vias), len(P.tracks)
        for e in P.report.get("gate_escapes", []):
            if e.get("withheld"): continue
            ref, num = e["pad"].split(".", 1)
            if not P.is_class(ref, "transistor"): continue
            p = next((q for q in P.d.by_ref[ref] if q["num"] == num), None)
            if p is None: continue
            L = P.d.fp[ref]["layer"]; g = P.d.pad_poly(p, L); a0, b0, a1, b1 = g.bounds; cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
            dx, dy = e["dir"]; ln = e["len_mm"]
            ex = a0 if dx < 0 else a1 if dx > 0 else cx; ey = b0 if dy < 0 else b1 if dy > 0 else cy
            vx, vy = round(ex + ln * dx, 3), round(ey + ln * dy, 3)
            if any(math.hypot(v["x"] - vx, v["y"] - vy) < float(self.prm["min_dist"]) for v in P.vias): continue
            w = min(0.25, P.short_side(g))
            P.tracks.append(dict(net=p["net"], layer=L, a=(round(cx, 4), round(cy, 4)), b=(vx, vy), w=w))
            P.vias.append(dict(net=p["net"], x=vx, y=vy, size=pc.VIA_D, drill=pc.VIA_DRILL))
            rep.append([e["pad"], vx, vy])
        self.rep()["vias"] = rep
        if int(self.prm["chk"]): self.check(n0, t0)

    def check(self, n0, t0):
        P = self.P; new_v = P.vias[n0:]; new_t = P.tracks[t0:]; keep_v, keep_t = [], []; rep = []
        r = pc.VIA_D / 2; need_cu = r + max(P.clr, pc.MIN_CLR) + 0.02; need_hole = pc.VIA_DRILL / 2 + 0.2 + 0.02
        others = lambda net: [(q, g) for L in P.outer for q, g in P.padpoly[L] if g is not None and q["net"] != net]
        def ok(net, x, y):
            pt = Point(x, y)
            for q, g in others(net):
                d = g.distance(pt)
                if d < need_cu or d < need_hole: return False
            if any(math.hypot(v["x"] - x, v["y"] - y) < pc.VIA_PITCH for v in P.vias[:n0] + keep_v): return False
            if not P.inside.buffer(-r - pc.EDGE_MM).contains(pt): return False
            return True
        for v, t in zip(new_v, new_t):
            net = v["net"]; a, b = t["a"], (v["x"], v["y"]); ux, uy = b[0] - a[0], b[1] - a[1]; ln = math.hypot(ux, uy) or 1; ux, uy = ux / ln, uy / ln
            placed = None
            for k in range(0, 17):
                x, y = round(b[0] + ux * 0.05 * k, 3), round(b[1] + uy * 0.05 * k, 3)
                if not ok(net, x, y): continue
                seg = LineString([a, (x, y)]).buffer(t["w"] / 2)
                if any(seg.distance(g) < P.clr for q, g in P.padpoly[t["layer"]] if g is not None and q["net"] != net): continue
                placed = (x, y, k); break
            if placed is None: rep.append([net, list(b), "dropped"]); continue
            x, y, k = placed; v = dict(v, x=x, y=y); t = dict(t, b=(x, y)); keep_v.append(v); keep_t.append(t)
            if k: rep.append([net, list(b), "moved +%.2f" % (0.05 * k), [x, y]])
        P.vias[n0:] = keep_v; P.tracks[t0:] = keep_t
        self.rep()["chk"] = rep


class ConnEscBig(Rule):
    """REJECTED. A connector signal pad wider than connesc's max_pad and up to max_pad here (a TC2030 / pogo pad) on
    the outer row of its connector (4+ pads) keeps a strip straight out (len mm past the pad, 0.7 mm wide = a 0.2 mm
    track + 2 x 0.25 mm high-current clearance) and a via site (via + via_room) at its end on both outer layers.
    Reference board (r4_port1 v1q, 0.9 mm): the outer-row strips cut the only strip of a 10 A cell-path pour from its
    fuse: a power net opened (CELL_P at F102), blocked 5 -> 4 of 366. Do not use without a power_first-style guard."""
    name = "connesc_big"; default = 0; status = "rejected"; reserves = True; params = {"max_pad": 0.9, "len": 0.8, "via_room": 0.15}
    measured = "r4_port1 v1q: power net opened (rejected)"

    def setup(self):
        if not self.on: return
        P = self.P; rep = []; W = float(self.prm["max_pad"]); ln = float(self.prm["len"]); w = 0.7
        for ref, ps in sorted(P.d.by_ref.items()):
            if not P.is_class(ref, "connector"): continue
            for L in P.outer:
                pp_ = [(p, P.d.pad_poly(p, L)) for p in ps if L in p["shapes"] and not p.get("drill")]
                if len(pp_) < 4: continue
                x0, y0, x1, y1 = unary_union([g for _, g in pp_]).bounds
                for p, g in pp_:
                    s_ = P.short_side(g)
                    if P.d.role(p["net"]) != "signal" or s_ <= 0.35 or s_ > W: continue
                    a0, b0, a1, b1 = g.bounds; cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
                    d = None
                    if b0 - y0 < 0.3: d = (0, -1, cx, b0)
                    elif y1 - b1 < 0.3: d = (0, 1, cx, b1)
                    elif a0 - x0 < 0.3: d = (-1, 0, a0, cy)
                    elif x1 - a1 < 0.3: d = (1, 0, a1, cy)
                    if d is None: continue
                    dx, dy, ex, ey = d; vx, vy = ex + dx * ln, ey + dy * ln
                    strip = LineString([(cx, cy), (vx, vy)]).buffer(w / 2, cap_style=2)
                    vs = Point(vx, vy).buffer(pc.VIA_D / 2 + float(self.prm["via_room"]), 16)
                    for LL in P.outer:
                        others = unary_union([qg for q, qg in P.padpoly[LL] if q["net"] != p["net"] and qg is not None] or [Polygon()])
                        k = (unary_union([strip, vs]) if LL == L else vs).difference(others.buffer(P.clr))
                        if k.is_empty: continue
                        P.keep_clear(p["net"], LL, k)
                    rep.append(p["key"])
        self.rep()["pads"] = rep


class RetBand(Rule):
    """A hot loop whose switch is a discrete transistor and whose return-net switch pins (the return-pin row) have
    fewer than vias (4) return vias within 1.2 mm gets a band of return copper mm deep straight out of that row (away
    from the package centre; as wide as the package + 1.5 mm each side, clipped by other nets with their escape room,
    only the piece touching the row kept, at least 0.5 mm2) and return vias placed in it up to vias in total. The loop
    hull leaves only a thin strip when the row faces outward, so the loop closes through one via. Drawn right after
    the stock hot-loop step. Source: r4_bcu (FET turned beside its inductor: 1 via at the return row instead of 3,
    HL_OUT 0.98 -> 0.83 nH)."""
    name = "ret_band"; default = 0; params = {"mm": 1.6, "vias": 4}
    measured = "r4_bcu v6 -> v6r: 0.857 -> 0.789 W, hot loops 6.62 -> 6.30 nH, blocked 5 -> 5 of 368"

    def after_loops(self):
        if not self.on: return
        from shapely.geometry import box as sbox
        P = self.P; rep = []; NV = int(self.prm["vias"])
        for name, hl in sorted(P.d.C.get("hot_loops", {}).items()):
            ref = hl["switch_pins"][0].split(".")[0]
            if not P.is_class(ref, "transistor") or ref not in P.d.by_ref: continue
            G = P.d.board(hl["ret"]); L = P.d.fp[ref]["layer"]
            pads = [p for p in P.d.by_ref[ref] if L in p["shapes"]]
            row = [p for p in pads if p["net"] == G and p["key"] in P.d.switch_pins]
            if not row: continue
            rg = unary_union([P.d.pad_poly(p, L) for p in row]); pk = unary_union([P.d.pad_poly(p, L) for p in pads])
            c, r = pk.centroid, rg.centroid; dx, dy = r.x - c.x, r.y - c.y
            ux, uy = (1 if dx > 0 else -1, 0) if abs(dx) >= abs(dy) else (0, 1 if dy > 0 else -1)
            near = rg.buffer(1.2)
            have = [v for v in P.vias if v["net"] == G and near.contains(Point(v["x"], v["y"]))]
            if len(have) >= NV: rep.append(dict(loop=name, vias=len(have), added=0)); continue
            a0, b0, a1, b1 = rg.bounds; m = float(self.prm["mm"]); p0, q0, p1, q1 = pk.bounds; e = 1.5
            if ux > 0: band = sbox(a1, q0 - e, a1 + m, q1 + e)
            elif ux < 0: band = sbox(a0 - m, q0 - e, a0, q1 + e)
            elif uy > 0: band = sbox(p0 - e, b1, p1 + e, b1 + m)
            else: band = sbox(p0 - e, b0 - m, p1 + e, b0)
            band = unary_union([band, rg]).intersection(P.inside)
            band = P.clip_others(G, L, band)
            band = unary_union([q for q in getattr(band, "geoms", [band]) if q.intersects(rg)])
            if band.is_empty or band.area < 0.5: rep.append(dict(loop=name, vias=len(have), added=0, why="no room")); continue
            P.add_zone(G, L, band, 25, kind="hot loop " + name)
            vs = P.place_vias(G, rg, NV - len(have), inside=band)
            rep.append(dict(loop=name, vias=len(have), added=len(vs), band_mm2=round(band.area, 1), dir=[ux, uy]))
        self.rep()["bands"] = rep


class SwDetour(Rule):
    """A switch-node net's detour (no path on its main layer: vias + corridor on the other outer layer) is drawn with
    corridor width w mm (0 = the stock width for the net current) and vias vias at each end (0 = stock, 1 A per via).
    Only inside the net step of that switch node (not for taps). Not screened on its own (r4_bcu kept it off)."""
    name = "sw_detour"; default = 0; status = "untested"; params = {"w": 0.0, "vias": 0}
    measured = "not screened"

    def detour_args(self, net, w, I):
        P = self.P
        if self.on and P.d.power.get(net, {}).get("kind") == "switching" and getattr(P, "_in_netstep", None) == net:
            if float(self.prm["w"]) > 0: w = float(self.prm["w"])
            if int(self.prm["vias"]) > 0: I = float(self.prm["vias"])
        return w, I


class TapMax(Rule):
    """taps draws a switch-node tap (bootstrap pad -> switch pour detour) only up to the stock detour limit (10 mm).
    With this rule on, taps may be up to mm long (default 16): a switch node that leaves its transistor on the main
    layer next to the inductor can put the bootstrap cap's switch pad 11-15 mm away, and the router searches only
    about 6 mm round an edge's end points. The tap stays a MIN_W track on the other outer layer, drawn after the grow
    step. Needs taps on. Source: r4_bcu (bootstrap tap to the moved switch node 11 mm)."""
    name = "tap_max"; default = 0; params = {"mm": 16.0}
    measured = "r4_bcu v3/v6: bootstrap tap drawn instead of a blocked edge (part of k1)"


class NogrowKind(Rule):
    """Base: hard outer-layer zones made only by one planner step (kinds) are not grown by the grow step."""
    grows = True; kinds = set(); switching = None

    def grow_prepare(self):
        P = self.P; self.frozen = set()
        if not self.on: return
        for (net, L), z in P.zones.items():
            if z["soft"] or L not in P.outer or not (z["kinds"] <= self.kinds): continue
            if self.switching is not None and (P.d.power.get(net, {}).get("kind") == "switching") != self.switching: continue
            self.frozen.add((net, L))
        self.rep()["frozen"] = sorted(f"{n} {L}" for n, L in self.frozen)

    def grow_frozen(self, net, L, z): return (net, L) in getattr(self, "frozen", set())


class SwNogrow(NogrowKind):
    """A switch-node net's detour corridor on the other outer layer (zone made only by the detour step) is not grown:
    it keeps the width the current needs; the grown margin round it is only dV/dt area facing what is below the
    board. Source: r4_bcu. On the reference placement (switch node forced to detour) it cost +0.028 W for SW B.Cu
    84.9 -> 27.7 mm2, same blocked edges; with the switch node on the main layer it does nothing."""
    name = "sw_nogrow"; default = 0; kinds = {"detour"}; switching = True
    measured = "r4_bcu c1: 0.835 -> 0.863 W, blocked 5 -> 5 of 369, SW B.Cu 84.9 -> 27.7 mm2 (kept off by default)"


class PwNogrow(NogrowKind):
    """A non-switching power net's detour corridor on the other outer layer (zone made only by the detour step: a
    low-current rail crossing under a higher-current stem) is not grown; grown it becomes a blob that takes the
    other outer layer's routing room. Source: r4_bcu (1.5 A rail: 27.8 -> 3.3 mm2 per port)."""
    name = "pw_nogrow"; default = 0; kinds = {"detour"}; switching = False
    measured = "r4_bcu e1 (on v6r): 0.789 -> 0.799 W, blocked 5 -> 5 of 368, B.Cu 381.5 -> 332.8 mm2"


class StubNogrow(NogrowKind):
    """A via stub on the other outer layer (zone made only by the via-stub step: the copper round an other-side
    terminal pad and its via array, e.g. a bottom-side bulk cap) is not grown into a blob; it keeps the pad, the vias
    and their links. Use with mirror_skip_supply (once the mirror corridor is gone the stub would grow alone).
    Source: r4_bcu."""
    name = "stub_nogrow"; default = 0; kinds = {"via stub"}
    measured = "part of r4_bcu k1 (with mirror_skip_supply, mirror_maxa): B.Cu 325.5 -> 156.5 mm2"


class MirrorSkipSupply(Rule):
    """The supply nets of hot loops whose switch is a discrete transistor (a charger stage's input and output) get no
    mirror copy on the other outer layer: the stage's own outer-layer copper and the inner layers carry the current,
    and a copy under the stage is a corridor on the other side. Source: r4_bcu."""
    name = "mirror_skip_supply"; default = 0
    measured = "r4_bcu d1 (on v6r): 0.789 -> 0.820 W, blocked 5 -> 5 of 368, B.Cu 381.5 -> 325.5 mm2"

    def mirror_hide(self):
        if not self.on: return {}
        P = self.P; out = {}
        for name, hl in sorted(P.d.C.get("hot_loops", {}).items()):
            ref = hl["switch_pins"][0].split(".")[0]
            if P.is_class(ref, "transistor"): out[P.d.board(hl["supply"])] = 1
        self.rep()["nets"] = sorted(out)
        return {n: P.d.power.pop(n) for n in sorted(out) if n in P.d.power}


def mirror_drop(P, mw, ma, tag):
    """Shared by mirror_maxa / mirror_minw2: drop pieces the mirror step ADDED (not merged into older copper of the
    zone) that are thinner than mw mm on average (2 area / perimeter) or smaller than ma mm2, with their stitching
    vias."""
    new = P.vias[P._mir_nv0:]; drop = []; before = P._mir_before
    for (net, L), z in list(P.zones.items()):
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
                P.unvia(vs); new = [v for v in new if v not in vs]
                P.cu[L][P.raster(q) & (P.cu[L] == P.netid[net])] = -1
                drop.append([net, L, round(q.area, 1), round(w, 2), len(vs)])
            else: keep_add.append(q)
        g = unary_union(([old] if old is not None else []) + keep_add)
        if g.is_empty: del P.zones[(net, L)]
        else: z["geom"] = g
    P.report.setdefault("rules", {}).setdefault(tag, {})["dropped"] = drop


class MirrorMaxA(Rule):
    """A piece the mirror step added (a copy of a >= 3 A net's outer copper on the other outer layer, not merged into
    older copper there) smaller than mm2 (default 10) is dropped with its stitching vias: such patches carry little
    current and take routing room on the other side; an inner bus carries the net. Source: r4_bcu (mid-board patch of
    the bus net: dropped with no change of that net's loss)."""
    name = "mirror_maxa"; default = 0; params = {"mm2": 10.0}
    measured = "part of r4_bcu k1: bus-net loss 0.1348 -> 0.1335 W, blocked unchanged"

    def after_mirror(self, n0):
        if not self.on: return
        m2 = self.P.rule("mirror_minw2")
        mirror_drop(self.P, float(m2.prm["mm"]) if m2.on else 0.0, float(self.prm["mm2"]), self.name)


class MirrorMinW2(Rule):
    """REJECTED. As mirror_maxa, but drops added mirror pieces thinner than mm (2 area / perimeter) on average; unlike
    the rejected mirror_minw it also judges pieces merged into a zone with via stubs. Reference (r4_bcu d2, 1.5 mm):
    it also dropped the 10 A cell-path mirror: loss 0.789 -> 0.839 W (+0.06 W on the cell path), blocked 5 -> 5."""
    name = "mirror_minw2"; default = 0; status = "rejected"; params = {"mm": 1.5}
    measured = "r4_bcu d2: +0.05 W, blocked 5 -> 5 of 368 (rejected)"

    def after_mirror(self, n0):
        if not self.on or self.P.rule_on("mirror_maxa"): return       # mirror_maxa applies both in one pass
        mirror_drop(self.P, float(self.prm["mm"]), 0.0, self.name)


class PadJoin(Rule):
    """A pad of a 2-pad part on a power net (not the return net; a feedback-divider top, a pull-up to a rail) that its
    net's planned copper on the same outer layer (hard zone + tracks) does not reach, with that copper within mm
    (default 4), gets a thin straight track (0.3/0.25/0.2 mm) into it, else an L (0.25/0.2 mm) to one of the nearest
    points of the copper; drawn after the grow step and checked on exact shapes. The router otherwise has to find a
    3-7 mm stub out of a pad boxed in by small parts and return vias. Source: r4_port1 q2 (5 V buck FB divider top)."""
    name = "padjoin"; default = 0; params = {"mm": 4.0}
    measured = "r4_port1 v5q/v5p: FB-divider rail stub routes on every route (sub-route 7 -> 4 failed of 128 with gatevia)"

    def after_grow(self):
        if not self.on: return
        P = self.P; D = float(self.prm["mm"]); rep = []
        for net in sorted(P.d.power):
            if net in P.d.ret: continue
            for L in P.outer:
                z = P.zones.get((net, L))
                if not z or z["soft"]: continue
                tr = [LineString([t["a"], t["b"]]).buffer(t["w"] / 2) for t in P.tracks if t["net"] == net and t["layer"] == L]
                cu = unary_union([z["geom"]] + tr); tin = cu.buffer(-0.12)
                if tin.is_empty: continue
                obs = None
                for p in P.d.pads:
                    if p["net"] != net or L not in p["shapes"] or p.get("drill") or len(P.d.by_ref[p["ref"]]) != 2: continue
                    pg = P.d.pad_poly(p, L)
                    if pg.intersects(cu.buffer(0.02)) or pg.distance(cu) > D: continue
                    c = pg.centroid; obs = P.obstacles(net, L) if obs is None else obs
                    q = tin.boundary.interpolate(tin.boundary.project(c)); ok = False
                    for w in (0.3, 0.25, 0.2):
                        if P.track_ok(net, L, (c.x, c.y), (q.x, q.y), w, obs=obs):
                            P.draw_track(net, L, (c.x, c.y), (q.x, q.y), w, "pad_join"); ok = True; break
                    if not ok:
                        cands = sorted((c.distance(Point(x, y)), x, y) for x in np.arange(c.x - D, c.x + D + 0.01, 0.1) for y in np.arange(c.y - D, c.y + D + 0.01, 0.1) if tin.contains(Point(x, y)))[:200]
                        for _, x, y in cands:
                            for k in ((c.x, y), (x, c.y)):
                                for w in (0.25, 0.2):
                                    if P.track_ok(net, L, (c.x, c.y), k, w, obs=obs) and P.track_ok(net, L, k, (x, y), w, obs=obs):
                                        P.draw_track(net, L, (c.x, c.y), k, w, "pad_join"); P.draw_track(net, L, k, (x, y), w, "pad_join"); ok = True; break
                                if ok: break
                            if ok: break
                    rep.append([p["key"], net, L, ok])
        self.rep()["joins"] = rep


class PadPair(Rule):
    """A series terminal of a power net (not the return net) with 2+ pads, some of which are on the net's main copper
    piece and some not (a source terminal with several pad groups of which the plan feeds only some: a USB-C
    receptacle's second VBUS pin pair, joined only inside the plug), gets each dead pad joined to the main piece after
    the grow step (so the join is never grown and the dead pad stays a pad). Pieces = the planner's own copper per
    layer (zones, tracks, vias, pads), joined across layers only by vias and plated holes (pads of one part are not
    joined for free); the main piece holds the most terminal parts. mode 1: same-layer link (straight, L, grid path);
    mode 2 (default): vias in/at the dead pad (exact-shape sites, in-pad first) + a straight or L link on the other
    outer layer to the main piece there; mode 3: as 2 with grid paths and free inner layers. live=1: always bridge
    pad to pad (via in the dead pad, via in a live pad of the same part, link on the other layer), so twin ports get
    the same bridge. Link widths w (default 0.8,0.6,0.5,0.4; mode 3: 0.5,0.4,0.3), vias per dead pad, longest link
    len mm, pads narrower than minpad (fine-pitch IC pins) are left to the router. grid_fix=1 orients grid paths from
    the pad (the source planner appended them reversed, so its length check rejected every grid path; modes 1/3)."""
    name = "padpair"; default = 0
    params = {"mode": 2, "w": "", "vias": 1, "len": 8.0, "minpad": 0.45, "live": 0, "grid_fix": 0}
    measured = "r4_vbus v2s (mode 2, live 1): VBUS dead pin pairs joined on both ports, blocked 5 -> 5 of 369, 0.835 -> 0.833 W, PC 352/17 -> 353/16"

    def after_grow(self):
        if not self.on: return
        P = self.P; mode = int(self.prm["mode"]); rep = []
        ws = [float(x) for x in str(self.prm["w"]).split(",") if x] or ([0.5, 0.4, 0.3] if mode == 3 else [0.8, 0.6, 0.5, 0.4])
        for net in sorted(n for n in P.d.power if n not in P.d.ret):
            T = P.d.terminals(net)
            multi = [g for g in T if g["kind"] == "series" and len(g["pads"]) >= 2]
            if not multi: continue
            pieces, f, comps, main = P.net_state(net, T)
            if main is None: continue
            for g in multi:
                on = [p for p in g["pads"] if main in comps(p)]
                if not on: continue
                dead = [p for p in g["pads"] if main not in comps(p)]
                done = set()
                for p in dead:
                    if p["key"] in done: continue
                    Lp = [L for L in p["shapes"] if L in P.outer]
                    if not Lp or P.short_side(P.d.pad_poly(p, Lp[0])) < float(self.prm["minpad"]):
                        rep.append(dict(net=net, pads=[p["key"]], mode=mode, drawn=False, why="fine-pitch pin")); continue
                    mates = [q for q in dead if comps(q) & comps(p)]
                    ok = self.join_dead(net, p, mode, ws, pieces, f, main, live=on)
                    rep.append(dict(net=net, pads=[q["key"] for q in mates], mode=mode, drawn=ok))
                    done |= {q["key"] for q in mates}
                    if ok: pieces, f, comps, main = P.net_state(net, T)
        self.rep()["pairs"] = rep

    def join_dead(self, net, p, mode, ws, pieces, f, main, live=()):
        P = self.P; maxl = float(self.prm["len"]); fix = int(self.prm["grid_fix"])
        L0 = [L for L in p["shapes"] if L in P.outer]
        if not L0: return False
        L0 = L0[0]; pg = P.d.pad_poly(p, L0); c = pg.centroid
        if mode == 1:
            tgt = P.main_on(L0, pieces, f, main)
            return bool(tgt is not None and P.link_to(net, L0, (c.x, c.y), tgt, ws, "padpair_strip", maxl, grid=True, grid_fix=fix))
        vs = P.via_sites_exact(net, pg, int(self.prm["vias"]))
        self.rep().setdefault("via_sites", []).append(dict(pad=p["key"], vias=[[v["x"], v["y"]] for v in vs]))
        if not vs: return False
        for v in vs:
            if not pg.buffer(0.01).contains(Point(v["x"], v["y"])):
                if not P.link_to(net, L0, (v["x"], v["y"]), pg, [min(0.5, P.short_side(pg)), 0.3], "padpair_vialink", maxl, esc=False):
                    P.unvia(vs); return False
        others = [L for L in P.outer if L != L0] + (P.inner_free if mode == 3 else [])
        for Lo in (others if not int(self.prm["live"]) else []):
            tz = P.main_on(Lo, pieces, f, main)
            if tz is None: continue
            for v in vs:
                w = P.link_to(net, Lo, (v["x"], v["y"]), tz, ws, "padpair_link", maxl, grid=(mode == 3), grid_fix=fix)
                if w:
                    self.rep().setdefault("links", []).append(dict(net=net, pad=p["key"], layer=Lo, w=w, via=[v["x"], v["y"]]))
                    return True
        for q in live:
            Lq = [L for L in q["shapes"] if L in P.outer]
            if not Lq or q.get("drill"): continue
            lv = P.via_sites_exact(net, P.d.pad_poly(q, Lq[0]), 1)
            if not lv: continue
            if not P.d.pad_poly(q, Lq[0]).buffer(0.01).contains(Point(lv[0]["x"], lv[0]["y"])): P.unvia(lv); continue
            for Lo in others:
                for v in vs:
                    w = P.link_to(net, Lo, (v["x"], v["y"]), Point(lv[0]["x"], lv[0]["y"]).buffer(pc.VIA_D / 2), ws, "padpair_link", maxl, grid=(mode == 3), grid_fix=fix)
                    if w:
                        self.rep().setdefault("links", []).append(dict(net=net, pad=p["key"], layer=Lo, w=w, via=[v["x"], v["y"]], live_via=[lv[0]["x"], lv[0]["y"], q["key"]]))
                        return True
            P.unvia(lv)
        P.unvia(vs); return False


class CapJoin(Rule):
    """A shunt terminal pad (a power net's capacitor) that is not on its net's main copper piece (padpair's piece
    analysis) gets joined after padpair: (0) a via already on the pad's piece (an other-side cap's via stub) linked on
    another outer layer to the main piece; (1) a same-layer link to the main piece (straight, L, then a grid path that
    keeps the signal escape room, oriented from the pad); (2) vias in/at the pad + a link on another outer layer (or a
    via that lands on main copper there). Widths w (default 0.8,0.6,0.5,0.4,0.3), vias per pad (2), longest link len
    (16 mm; also <= 1.5 x straight + 3 mm), pads narrower than minpad skipped, refs (board data: only these parts; empty
    = all). A failed try is rolled back fully. Source: r5_merge (a bottom-side input bulk cap on a 5 mm2 island)."""
    name = "capjoin"; default = 0; params = {"w": "", "vias": 2, "minpad": 0.45, "len": 16.0, "refs": []}
    measured = "r5_merge m0 -> m1 (with gatevia chk): bulk cap joined by a 12.6 mm strap, blocked 4 -> 4, +0.002 W"

    def after_grow(self):
        if not self.on: return
        P = self.P; rep = []; maxl = float(self.prm["len"])
        ws = [float(x) for x in str(self.prm["w"]).split(",") if x] or [0.8, 0.6, 0.5, 0.4, 0.3]
        refs = [r for r in (self.prm["refs"] or []) if r]
        for net in sorted(n for n in P.d.power if n not in P.d.ret):
            T = P.d.terminals(net)
            caps = [g for g in T if g["kind"] == "shunt" and (not refs or g["ref"] in refs)]
            if not caps: continue
            pieces, f, comps, main = P.net_state(net, T)
            if main is None: continue
            for g in caps:
                for p in g["pads"]:
                    if main in comps(p): continue
                    Lp = [L for L in p["shapes"] if L in P.outer]
                    if not Lp or P.short_side(P.d.pad_poly(p, Lp[0])) < float(self.prm["minpad"]):
                        rep.append(dict(net=net, pad=p["key"], drawn=False, why="small")); continue
                    L0 = Lp[0]; pg = P.d.pad_poly(p, L0); c = pg.centroid
                    snap = P.snap()
                    ok = self.old_via_join(net, p, comps, pieces, f, main, ws, maxl)
                    tgt = P.main_on(L0, pieces, f, main)
                    if not ok and tgt is not None:
                        w = P.link_to(net, L0, (c.x, c.y), tgt, ws, "capjoin_strip", maxl, grid=True, grid_fix=1)
                        if w: ok = f"same-layer {w} mm on {L0}"
                    if not ok: ok = self.via_join(net, p, L0, pg, ws, pieces, f, main, maxl)
                    if not ok: P.restore(snap)
                    rep.append(dict(net=net, pad=p["key"], drawn=bool(ok), how=ok))
                    if ok: pieces, f, comps, main = P.net_state(net, T)
        self.rep()["joins"] = rep

    def old_via_join(self, net, p, comps, pieces, f, main, ws, maxl):
        P = self.P; mine = comps(p)
        if not mine: return None
        Lp = [L for L in p["shapes"] if L in P.outer][0]
        for v in [v for v in P.vias if v["net"] == net]:
            pt = Point(v["x"], v["y"])
            hit = [k for k, q in enumerate(pieces[Lp]) if q.intersects(pt) and f((Lp, k)) in mine]
            if not hit: continue
            for Lo in [L for L in P.outer if L != Lp]:
                tz = P.main_on(Lo, pieces, f, main)
                if tz is None: continue
                w = P.link_to(net, Lo, (v["x"], v["y"]), tz, ws, "capjoin_link", maxl, grid=True, grid_fix=1)
                if w: return f"existing via ({v['x']}, {v['y']}) + {w} mm on {Lo}"
        return None

    def via_join(self, net, p, L0, pg, ws, pieces, f, main, maxl):
        P = self.P
        vs = P.via_sites_exact(net, pg, int(self.prm["vias"]))
        if not vs: return None
        for v in vs:
            if not pg.buffer(0.01).contains(Point(v["x"], v["y"])):
                if not P.link_to(net, L0, (v["x"], v["y"]), pg, [min(0.5, P.short_side(pg)), 0.3], "capjoin_vialink", maxl, esc=False):
                    P.unvia(vs); return None
        for Lo in [L for L in P.outer if L != L0]:
            tz = P.main_on(Lo, pieces, f, main)
            if tz is None: continue
            if any(tz.buffer(-0.05).contains(Point(v["x"], v["y"]).buffer(pc.VIA_D / 2)) for v in vs): return "via onto " + Lo
            for v in vs:
                w = P.link_to(net, Lo, (v["x"], v["y"]), tz, ws, "capjoin_link", maxl, grid=True, grid_fix=1)
                if w: return f"via + {w} mm on {Lo}"
        P.unvia(vs); return None


class GndTie(Rule):
    """A return-net pin of an IC (class 'ic', 8+ pads) that the return step left to the router (no via site within
    reach) gets one via placed with the pinesc reservations relaxed: the via (and its 0.2 mm link) keeps the via size +
    clearance from every pinesc reservation shape, but may sit in their raster margin. pinesc's via sites otherwise
    take the only via room of a return pin pair beside the reserved signal pins, and the pair floats. Needs pinesc.
    Source: r4_port1 q4 (GND pair next to a PD chip's CC pin)."""
    name = "gndtie"; default = 0
    measured = "r4_port1 v1p -> v5p: blocked 7 -> 5 (GND pin pair tied again with pinesc on both PD chips)"

    def after_return(self):
        if not self.on: return
        P = self.P; pe = P.rule("pinesc")
        if not pe.on or not hasattr(pe, "mask"): return
        rep = P.report["return_pads"]; done = []
        for key in list(rep.get("left_to_router", [])):
            ref, num = key.split(".", 1)
            if not P.is_class(ref, "ic") or len(P.d.by_ref.get(ref, [])) < 8: continue
            p = next((q for q in P.d.by_ref[ref] if q["num"] == num), None)
            if p is None or p["net"] not in P.d.ret: continue
            for L in P.outer:
                if L not in p["shapes"]: continue
                sh = P.d.pad_poly(p, L)
                resv = unary_union([g for LL in P.outer for g in pe.geoms[LL]] or [Polygon()])
                keep = {LL: P.block[LL].copy() for LL in P.outer}
                for LL in P.outer: P.block[LL] &= ~pe.mask[LL]
                try:
                    n0 = len(P.vias); vm = P.viamap.copy(); vs = P.place_vias(p["net"], sh, 6, link=(L, sh), link_w=0.2)
                finally:
                    for LL in P.outer: P.block[LL] = keep[LL]
                good = None
                for v in vs:
                    if good is None and Point(v["x"], v["y"]).distance(resv) >= pc.VIA_D / 2 + P.clr and \
                       not (v.get("link") and LineString([v["link"][1:], (v["x"], v["y"])]).buffer(0.1).distance(resv) < P.clr):
                        good = v
                P.vias[:] = [v for v in P.vias[:n0]] + ([good] if good else []); P.viamap = vm
                if good: P.viamap[P.disk(good["x"], good["y"], pc.VIA_D / 2) & (P.viamap < 0)] = P.netid[p["net"]]
                if good is None: continue
                if good.get("link"): P.tracks.append(dict(net=p["net"], layer=good["link"][0], a=good["link"][1:], b=(good["x"], good["y"]), w=0.2))
                done.append([key, good["x"], good["y"]]); rep["left_to_router"].remove(key); break
        self.rep()["ties"] = done


# Dispatch order = the order in which hooks of the same kind run. New rules: append at the right point.
RULES = [GateEscape, Sealed, PinEscape, ConnEscape, ConnEscBig, GateVia, GndPair, EpStrip, RetBand, JoinFix, DirectJoin,
         GndEsc, GndTie, SwDetour, NogrowDead, NogrowDetour, GrowViaroom, SwNogrow, PwNogrow, StubNogrow,
         MirrorSkipSupply, MirrorMinW, MirrorMaxA, MirrorMinW2, Taps, TapMax, PadJoin, PadPair, CapJoin, PowerFirst]


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
            return False
        self.keep.setdefault(L, []).append((net, g))
        self.block[L] |= self.raster(g.buffer(self.clr))
        self.blockgeom[L].append(g)
        return True

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

    # ---- copper pieces and exact-shape links (padpair, capjoin; from r4_vbus PlannerV and r5_merge PlannerM)
    def cu_pieces(self, net):
        """The planner's own copper of net as connected pieces: per layer the union of zones (necks under 0.1 mm
        dropped, as KiCad's fill drops them), tracks, vias and pads; joined across layers only by vias and plated
        holes (pads of one part are not joined for free). Returns (pieces {layer: [geom]}, find(), comps(pad))."""
        geo = {L: [] for L in self.layers}
        for (n, L), z in self.zones.items():
            if n == net and not z["geom"].is_empty: geo[L].append(z["geom"].buffer(-0.05, 4).buffer(0.05, 4))
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

    def net_state(self, net, T):
        """cu_pieces + the main piece (the one holding pads of the most terminal parts of T)."""
        pieces, f, comps = self.cu_pieces(net); score = {}
        for g in T:
            for p in g["pads"]:
                for c in comps(p): score.setdefault(c, set()).add(g["ref"])
        return pieces, f, comps, (max(score, key=lambda c: len(score[c])) if score else None)

    def main_on(self, L, pieces, f, main):
        g = [q for k, q in enumerate(pieces[L]) if f((L, k)) == main]
        return unary_union(g) if g else None

    def link_obs(self, net, L, esc=True):
        """Exact shapes a link of net on L keeps the clearance from: obstacles() + every reservation and rule track
        of other nets + (esc) the escape room round other nets' signal pads."""
        g = [self.obstacles(net, L)] + list(self.blockgeom[L]) + [k for n, k in self.keep.get(L, []) if n != net]
        if esc and self.escape > 0:
            g += [pg.buffer(self.escape, 4) for q, pg in self.padpoly[L] if pg is not None and q["net"] != net and self.d.role(q["net"]) == "signal"]
        return unary_union(g)

    def link_to(self, net, L, a, tgt, ws, kind, maxl, grid=False, esc=True, grid_fix=0):
        """Track(s) of the first width in ws from point a to shape tgt on L: straight, then L-shaped (both only if
        the straight distance is <= maxl), then (grid) a grid path no longer than min(maxl, WIND_MAX x straight +
        WIND_SLACK_MM). grid_fix=0 reproduces r4_vbus (path appended in the router's goal-to-start order, straight =
        distance to the projected point, no grid when too far); grid_fix=1 is r5_merge's corrected form (path oriented
        from a, straight = distance to tgt, grid tried also when the straight link is too long). Width or None."""
        obs = self.link_obs(net, L, esc)
        tin = tgt.buffer(-0.1); tin = tin if not tin.is_empty else tgt
        q = tin.boundary.interpolate(tin.boundary.project(Point(a))) if not tin.contains(Point(a)) else Point(a)
        b = (q.x, q.y); far = math.hypot(b[0] - a[0], b[1] - a[1]) > maxl
        inside = lambda s: self.inside.contains(LineString(s).buffer(1e-3)) if len(s) > 1 else True
        okw = lambda u, v, w: LineString([u, v]).buffer(w / 2, 4).distance(obs) >= self.clr - 1e-4
        if far and not grid_fix: return None
        if not far:
            for w in ws:
                if okw(a, b, w) and inside([a, b]):
                    self.draw_track(net, L, a, b, w, kind); return w
                for c in ((a[0], b[1]), (b[0], a[1])):
                    if okw(a, c, w) and okw(c, b, w) and inside([a, c, b]) and tgt.buffer(0.01).contains(Point(b)):
                        self.draw_track(net, L, a, c, w, kind); self.draw_track(net, L, c, b, w, kind); return w
        if not grid: return None
        start = self.raster(Point(a).buffer(0.15)); goal = self.raster(tgt) & ~start
        if not goal.any(): return None
        st = tgt.distance(Point(a)) if grid_fix else math.hypot(b[0] - a[0], b[1] - a[1])
        for w in ws:
            pth, rr = self.path(net, L, start, goal, w, start, tight=False)
            if pth is None: continue
            pts = [self.xy(i, j) for i, j in pth]
            if grid_fix and math.dist(pts[0], a) > math.dist(pts[-1], a): pts = pts[::-1]
            line = LineString([a] + pts).simplify(0.05)
            if line.length > min(maxl, pc.WIND_MAX * st + pc.WIND_SLACK_MM): continue
            c = list(line.coords)
            if all(okw(u, v, w) for u, v in zip(c, c[1:])) and inside(c):
                for u, v in zip(c, c[1:]): self.draw_track(net, L, u, v, w, kind)
                return w
        return None

    def via_sites_exact(self, net, pg, n):
        """Up to n via sites in pad pg (else within 0.6 mm of it), checked on exact shapes (clearance to every other
        net's copper, pads and reservations on both outer layers, board edge, hole gaps, no-via keep-outs); in-pad
        first, then nearest the pad centre. The vias are added to the plan."""
        r = pc.VIA_D / 2; c = pg.centroid; x0, y0, x1, y1 = pg.buffer(0.6).bounds
        obs = {L: self.link_obs(net, L, esc=False) for L in self.outer}
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

    def snap(self):
        """State a failed try can be rolled back to (tracks, vias, rasters, rule tracks/reservations, report)."""
        return dict(tracks=len(self.tracks), vias=list(self.vias), viamap=self.viamap.copy(), cu={L: a.copy() for L, a in self.cu.items()},
                    keep={L: len(v) for L, v in self.keep.items()}, rep=json.dumps(self.report.get("rule_tracks", {}), default=str))

    def restore(self, s):
        del self.tracks[s["tracks"]:]; self.vias[:] = s["vias"]; self.viamap = s["viamap"]
        for L, a in s["cu"].items(): self.cu[L] = a
        for L in list(self.keep): del self.keep[L][s["keep"].get(L, 0):]
        self.report["rule_tracks"] = json.loads(s["rep"])

    # stock methods with hooks (each calls the stock method)
    def run(self):
        if self.rule_on("taps") and self.grow <= 0: self.grow = 1e-9        # grow_step must run for the taps
        return super().run()

    def hot_loops_step(self):
        for r in self.rules: r.before_loops()
        out = super().hot_loops_step()
        for r in self.rules: r.after_loops()
        return out

    def net_step(self, net):
        self._in_netstep = net
        try: super().net_step(net)
        finally: self._in_netstep = None
        for r in self.rules: r.after_net(net)

    def detour(self, net, L, gp, w, I, tree):
        for r in self.rules: w, I = r.detour_args(net, w, I)
        return super().detour(net, L, gp, w, I, tree)

    def return_step(self):
        sv = set().union(*[r.return_skip() for r in self.rules])
        if not sv: super().return_step()
        else:
            keep = self.d.by_ref
            self.d.by_ref = {r: [p for p in ps if p["key"] not in sv] for r, ps in keep.items()}
            try: super().return_step()
            finally: self.d.by_ref = keep
            self.report["return_pads"]["served_by_rules"] = sorted(sv)
        for r in self.rules: r.after_return()

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
        n0 = len(self.vias); self._mir_nv0 = n0
        hidden = {}
        for r in self.rules: hidden.update(r.mirror_hide())      # nets the mirror step must not see
        self._mir_before = {k: z["geom"] for k, z in self.zones.items()}
        try: super().mirror_step(min_a)
        finally: self.d.power.update(hidden)
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
