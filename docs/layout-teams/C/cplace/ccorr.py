"""ccorr.py: copper-corridor estimate for cplace.py (team C package "corridor"). HOOKS=...,ccorr

Instead of freezing real power copper before the fill (round 3: 93 of 96 failures sat against frozen copper), the
placer keeps a cheap ESTIMATE of where tools/copper/plan_copper.py will later draw each power net, recomputed as
the net's terminals get placed, and uses it three ways:

  corridor   for every power net of CORR_MIN_A amps or more (constraints.json `nets` with current_a, plus the 5 V
             switch nodes SW_5V at 1.5 A), its terminals (tools/copper/roles.py: the pads that carry the current)
             are joined the way plan_copper.py grows its tree: start at the highest-current terminal on the net's
             main outer layer, then join the nearest terminal, one at a time, by a straight strip from its nearest
             pad to the nearest point of the tree so far. Strip width = roles.width_mm(terminal current) + 2 x
             CORR_CLR. A terminal on the other outer layer gets a via field (vias_for(I) vias at 0.75 mm pitch) at
             its pad, on both sides. A net whose placed terminals spread wider than BUS_SPAN_MM (25) with at least 6
             terminals becomes an inner-layer bus in plan_copper.py (the two with most terminals): then only via
             fields at its terminals are reserved, no surface strip. A strip exists once both its ends are placed.
  escape     a band in front of each power pin of an IC with pins on two or more >= 1 A power nets (the PD chips
             U401/U501: PPHV 20, VBUS 23/32, PP5V 34; plan_copper's exits() rule), ESC_MM long outward, pad width
             + 2 x ESC_SIDE wide. This is where the base and the hand board open.
  compact    each terminal pad of the part being placed pays CMPW x amps x mm to the nearest placed terminal pad of
             the same net on another part (power parts pull together, corridors stay short).

A part never pays for (or is blocked by) a corridor or band of a net it has a pad on. Strips and bands live on the
side of the layer they are drawn on; via fields on both sides.

Knobs (environment; defaults = the recommended soft setting):
  CORR_W=4        cost per mm2 of body overlap with a corridor or via field (soft); 0 = off
  CORR_MIN_A=1    nets below this current get no corridor
  CORR_CLR=0.3    clearance added on each side of a strip
  CORR_HARD=0     nets of at least this many amps: their strip CORE (copper width, no clearance) is forbidden to
                  other parts' bodies (hard); 0 = off
  ESC_W=8         cost per mm2 of body overlap with a PD escape band; 0 = no bands
  ESC_MM=2.0      band length outward from the pad edge
  ESC_SIDE=0.25   band widening on each side of the pad
  ESC_HARD=0      1 = escape bands are hard (forbidden), not just paid for
  CROSSW=30       cost per crossing of a part's prospective corridor (its terminal pad -> nearest placed terminal pad of
                  the net) with a placed corridor of another net, or of two of its own nets with each other (a PD
                  chip whose PPHV path crosses its VBUS path): plan_copper.py draws nets one at a time, so at a
                  crossing on one layer the later net is walled off
  ESC_J=1         escape bands also at the SMD power pads of fixed connectors (USB-C VBUS), pointing into the board
  CMP_TVS=5       a diode shunt (TVS) on a net with a connector terminal is pulled to the connector's pads at this
                  cost per mm (applies even with CMPW=0), not to the nearest terminal (else D401 sat at the PD chip's far VBUS pin and the VBUS copper wrapped the chip)
  CMPW=0.5        compactness weight (mm-equivalent per mm per A); 0 = off
  CORR_PRE=0      1 = after_big hook (one tagged line in cplace.py): right after a large part with power pins is
                  placed, place the series power parts chained to it (PD chip -> PPHV shunt, PP5V inductor -> 5 V
                  buck), before its support parts take the room; not locked. CORR_PRE=2: also the shunt
                  terminals (VBUS TVS and caps, PP5V output caps, ...) of the nets that chain went through, and
                  (only when cpower has not placed them) the caps of each hot loop whose switch parts are placed,
                  each pad next to the switch pin of its net
  CORR_PRE_WAIT=0 1: the chains start only once every large power part (PD chips, all FET pairs) is placed, so the 5 V
                  buck and the caps do not take the room the four-switch stages need (with cpower those are
                  placed first anyway); 0 = chain right after each large part
  CORR_BOXW=0     cost per mm a power-path part (series terminal) lies outside its floorplan box + CORR_BOXM (1 mm);
                  the base runs BOXW=0, so without this the 5 V bucks drift to wherever room is left
  CORR_DEBUG=path write the final corridors (strips, via fields, bands) as JSON for corr_draw.py
Writes nothing else; prints one summary line in post_place."""
import os, sys, json, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "floorplan")); sys.path.insert(0, os.path.join(REPO, "tools", "copper"))

E = os.environ
CORR_W = float(E.get("CORR_W", 4.0)); CORR_MIN_A = float(E.get("CORR_MIN_A", 1.0)); CORR_CLR = float(E.get("CORR_CLR", 0.3))
CORR_HARD = float(E.get("CORR_HARD", 0)); ESC_W = float(E.get("ESC_W", 8.0)); ESC_MM = float(E.get("ESC_MM", 2.0))
ESC_SIDE = float(E.get("ESC_SIDE", 0.25)); ESC_HARD = int(E.get("ESC_HARD", 0)); CMPW = float(E.get("CMPW", 0.5))
CROSSW = float(E.get("CROSSW", 30)); CMP_TVS = float(E.get("CMP_TVS", 5.0)); CORR_PRE_WAIT = int(E.get("CORR_PRE_WAIT", 0)); CORR_PRE = int(E.get("CORR_PRE", 0)); CORR_BOXW = float(E.get("CORR_BOXW", 0)); CORR_BOXM = float(E.get("CORR_BOXM", 1.0)); DEBUG = E.get("CORR_DEBUG", "")
RS = 0.25                       # raster, mm
BUS_SPAN_MM, BUS_MIN_T, N_INNER = 25.0, 6, 2      # plan_copper.py: BUS_SPAN_MM, BUS_MIN_TERMINALS, free inner layers
VIA_PITCH = 0.75

S = {}                          # module state

def _lay(l):
    l = l.split()[0]
    return l

def setup(ctx):
    from roles import Design, width_mm, vias_for
    S["width"] = width_mm; S["vias"] = vias_for
    # the same pad model as tools/floorplan/power_chains.py design() (pad boxes as rings), built from ctx.d; it gives
    # the same terminals as roles.py on the scorecard's cu_dump (checked for all 20 power nets)
    side = {f["ref"]: f.get("side", "F.Cu") for f in ctx.d["fps"]}; pads = []
    for p in ctx.d["pads"]:
        x0, y0, x1, y1 = p["box"]; ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        L = [l for l in p["layers"] if l.endswith(".Cu") and "*" not in l] or [side[p["ref"]]]
        pads.append(dict(ref=p["ref"], num=p["num"], net=p["net"], x=p["x"], y=p["y"], pinfn=p.get("pinfn", ""), npth=False,
                         shapes={l: [dict(ring=ring)] for l in L}))
    dz = Design(dict(pads=pads, fps=[dict(ref=f["ref"], value=f.get("value", ""), layer=side[f["ref"]]) for f in ctx.d["fps"]]),
                os.environ.get("CONSTRAINTS", "/home/claude/work/C/in/constraints.json"))
    # pad index j in ctx.lp per (ref, num, net)
    padj = {}
    for r, L in ctx.lp.items():
        for j, v in enumerate(L): padj.setdefault((r, v[3], v[2]), []).append(j)
    play = {}                   # (ref, j) -> set of layers 'F'/'B' in the dump pose
    cnt = {}
    for p in ctx.d["pads"]:
        k = (p["ref"], p["num"], p["net"]); i = cnt.get(k, 0); cnt[k] = i + 1
        js = padj.get(k, [])
        if i < len(js):
            ls = {_lay(l) for l in p["layers"]}
            s = set()
            if "F.Cu" in ls or "*.Cu" in ls: s.add("F")
            if "B.Cu" in ls or "*.Cu" in ls: s.add("B")
            if not s: s.add("F" if ctx.side0[p["ref"]] else "B")
            play[(p["ref"], js[i])] = s
    nets = {}                   # net -> dict(I, kind, T=[(ref, [j], I_term, kind)])
    for n, f in dz.power.items():
        if f["current_a"] < CORR_MIN_A: continue
        T = []
        for g in dz.terminals(n):
            js = sorted({j for p in g["pads"] for j in padj.get((g["ref"], p["num"], n), [])})
            if js: T.append((g["ref"], js, g["current_a"], g["kind"]))
        if len(T) >= 2: nets[n] = dict(I=f["current_a"], kind=f["kind"], T=T)
    if int(E.get("CORR_SW5V", 1)):
        for n in {v[2] for L in ctx.lp.values() for v in L if v[2] and v[2].endswith("SW_5V")}:
            T = []
            for r in sorted(set(ctx.netpads[n])):
                if r[0] in "UL":
                    js = [j for j, v in enumerate(ctx.lp[r]) if v[2] == n]
                    if js: T.append((r, js, 1.5, "series"))
            if len(T) >= 2 and 1.5 >= CORR_MIN_A: nets[n] = dict(I=1.5, kind="switching", T=T)
    S["nets"] = nets; S["play"] = play
    S["tparts"] = sorted({t[0] for v in nets.values() for t in v["T"]})
    S["term"] = {}              # ref -> [(net, j list, I)]
    for n, v in nets.items():
        for r, js, I, k in v["T"]: S["term"].setdefault(r, []).append((n, js, I))
    # escape pins: series terminal pads of U parts with pads on >= 2 power nets of >= 1 A
    esc = []
    for r in {t[0] for v in nets.values() for t in v["T"] if t[0].startswith("U")}:
        pn = {v[2] for v in ctx.lp[r] if v[2] in dz.power and dz.power[v[2]]["current_a"] >= 1.0}
        if len(pn) < 2: continue
        for n in pn:
            if n not in nets: continue
            for rr, js, I, k in nets[n]["T"]:
                if rr == r and k == "series":
                    for j in js: esc.append((r, j, n))
    if int(E.get("ESC_J", 1)):
        for n, v in nets.items():
            for rr, js, I, k in v["T"]:
                if rr.startswith("J") and rr not in ctx.fill and k == "series":
                    for j in js:
                        if play.get((rr, j)) in ({"F"}, {"B"}): esc.append((rr, j, n))
    S["esc"] = esc
    S["C"] = json.load(open(os.environ.get("CONSTRAINTS", "/home/claude/work/C/in/constraints.json")))
    S["hlcaps"] = {c for hl in S["C"].get("hot_loops", {}).values() for c in hl["caps"]}
    S["chain"] = {t[0] for v in nets.values() for t in v["T"] if t[3] == "series" and t[0] in ctx.fill}   # power-path parts to place
    # pad box half sizes in the dump pose (local), per (ref, j)
    hb = {}; cnt = {}
    for p in ctx.d["pads"]:
        k = (p["ref"], p["num"], p["net"]); i = cnt.get(k, 0); cnt[k] = i + 1; js = padj.get(k, [])
        if i < len(js): hb[(p["ref"], js[i])] = ((p["box"][2] - p["box"][0]) / 2, (p["box"][3] - p["box"][1]) / 2)
    S["hb"] = hb
    box = ctx.box
    S["gx"] = np.arange(box[0], box[2], RS) + RS / 2; S["gy"] = np.arange(box[1], box[3], RS) + RS / 2
    S["names"] = sorted(nets) + sorted({n for _, _, n in esc} - set(nets))
    S["nid"] = {n: i for i, n in enumerate(S["names"])}
    S["nparts"] = {n: sorted({t[0] for t in nets[n]["T"]} if n in nets else set()) for n in S["names"]}
    print(f"ccorr: {len(nets)} corridor nets, {len(S['tparts'])} terminal parts, {len(esc)} escape pins; CORR_W {CORR_W} ESC_W {ESC_W} "
          f"CMPW {CMPW} CORR_HARD {CORR_HARD} ESC_HARD {ESC_HARD}", flush=True)

def _pads(ctx, r, js):
    """placed pad centres and layers ('F'/'B' after the part's side) of r"""
    out = []
    flip = ctx.sideF[r] != ctx.side0[r]
    for j in js:
        x, y = ctx.pad_xy(r, j); L = S["play"].get((r, j), {"F"})
        if flip: L = {{"F": "B", "B": "F"}[l] for l in L}
        out.append((x, y, L, j))
    return out

def _seg_point(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay; l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return ax + t * dx, ay + t * dy

def _buses(ctx):
    """nets plan_copper.py will make inner-layer buses, from the placed terminals (its run() rule)"""
    cand = []
    for n, v in S["nets"].items():
        if v["kind"] != "power": continue
        T = [t for t in v["T"] if t[0] in ctx.P]
        if len(T) < BUS_MIN_T: continue
        xy = np.array([ctx.pad_xy(r, j) for r, js, _, _ in T for j in js])
        if len(xy) > 1 and math.hypot(*np.ptp(xy, axis=0)) > BUS_SPAN_MM: cand.append((-len(T), -v["I"], n))
    return {n for _, _, n in sorted(cand)[:N_INNER]}

def build_net(ctx, n, bus):
    """corridor shapes of one net from its placed terminals: list of (net, kind, side set, geometry, hard?)
    kind 'strip': (ax, ay, bx, by, half width core, half width with clearance); 'box' (via field) and 'esc' (escape
    band): (x0, y0, x1, y1)"""
    P = ctx.P; shapes = []
    v = S["nets"].get(n)
    T = [(r, _pads(ctx, r, js), I, k) for r, js, I, k in v["T"] if r in P] if v else []
    Inet = v["I"] if v else 0.0; hard = CORR_HARD > 0 and Inet >= CORR_HARD
    def vfield(ps, I):
        nv = S["vias"](I); a = VIA_PITCH * math.ceil(math.sqrt(nv)) / 2 + 0.3
        x = float(np.mean([p[0] for p in ps])); y = float(np.mean([p[1] for p in ps]))
        shapes.append((n, "box", {"F", "B"}, (x - a, y - a, x + a, y + a), False))
        return x, y
    if bus:
        for r, ps, I, k in T:
            if any(L >= {"F", "B"} for _, _, L, _ in ps): continue      # a plated hole reaches the bus itself
            vfield(ps, I)
    elif len(T) >= 2:
        lI = {"F": 0.0, "B": 0.0}       # main layer: the outer layer with most terminal current
        for r, ps, I, k in T:
            for l in {l for _, _, L, _ in ps for l in L}: lI[l] += I
        main = "F" if lI["F"] >= lI["B"] else "B"
        T = sorted(T, key=lambda t: (-t[2], t[0]))
        first = next((t for t in T if any(main in L for _, _, L, _ in t[1])), T[0])
        todo = [t for t in T if t is not first]
        pts = [(x, y) for x, y, L, _ in first[1]]; segs = []
        while todo:                     # nearest terminal to the tree first, joined to the nearest point of the tree
            best = None
            for t in todo:
                for x, y, L, _ in t[1]:
                    for (qx, qy) in pts:
                        dd = math.hypot(x - qx, y - qy)
                        if best is None or dd < best[0]: best = (dd, t, x, y, qx, qy, L)
                    for (ax, ay, bx, by) in segs:
                        qx, qy = _seg_point(x, y, ax, ay, bx, by); dd = math.hypot(x - qx, y - qy)
                        if best is None or dd < best[0]: best = (dd, t, x, y, qx, qy, L)
            dd, t, x, y, qx, qy, L = best; todo.remove(t)
            if main not in L: x, y = vfield([p for p in t[1] if main not in p[2]] or t[1], t[2])
            w = max(0.3, S["width"](t[2])) / 2
            shapes.append((n, "strip", {main}, (x, y, qx, qy, w, w + CORR_CLR), hard))
            segs.append((x, y, qx, qy)); pts += [(px, py) for px, py, _, _ in t[1]]
    if ESC_W > 0 or ESC_HARD:
        for r, j, n2 in S["esc"]:
            if n2 != n or r not in P: continue
            x, y = ctx.pad_xy(r, j); hx, hy = S["hb"][(r, j)]
            if P[r][2] % 2: hx, hy = hy, hx
            allp = [ctx.pad_xy(r, i) for i in range(len(ctx.lp[r]))]
            X0 = min(p[0] for p in allp); X1 = max(p[0] for p in allp); Y0 = min(p[1] for p in allp); Y1 = max(p[1] for p in allp)
            dl = {"l": x - X0, "r": X1 - x, "t": y - Y0, "b": Y1 - y}; e = min(dl, key=dl.get)   # package edge the pad sits on
            if r.startswith("J"):       # a connector: into the board
                vx = (ctx.box[0] + ctx.box[2]) / 2 - x; vy = (ctx.box[1] + ctx.box[3]) / 2 - y
                e = ("r" if vx > 0 else "l") if abs(vx) > abs(vy) else ("b" if vy > 0 else "t")
            s = ESC_SIDE
            if e == "l": b = (x - hx - ESC_MM, y - hy - s, x - hx, y + hy + s)
            elif e == "r": b = (x + hx, y - hy - s, x + hx + ESC_MM, y + hy + s)
            elif e == "t": b = (x - hx - s, y - hy - ESC_MM, x + hx + s, y - hy)
            else: b = (x - hx - s, y + hy, x + hx + s, y + hy + ESC_MM)
            shapes.append((n, "esc", {"F" if ctx.sideF[r] else "B"}, b, bool(ESC_HARD)))
    return shapes

def _integ(a):
    I = np.zeros((a.shape[0] + 1, a.shape[1] + 1), np.float64); I[1:, 1:] = a.cumsum(0).cumsum(1); return I

def _raster_net(shapes):
    """per side: (soft integral, hard integral or None)"""
    gx, gy = S["gx"], S["gy"]
    soft = {s: np.zeros((len(gy), len(gx)), np.float32) for s in ("F", "B")}
    hard = {s: np.zeros((len(gy), len(gx)), np.float32) for s in ("F", "B")}
    for n, kind, sides, g, hd in shapes:
        if kind == "strip":
            ax, ay, bx, by, wc, ws = g
            x0 = min(ax, bx) - ws; x1 = max(ax, bx) + ws; y0 = min(ay, by) - ws; y1 = max(ay, by) + ws
            i0, i1 = np.searchsorted(gx, x0), np.searchsorted(gx, x1); j0, j1 = np.searchsorted(gy, y0), np.searchsorted(gy, y1)
            if i1 <= i0 or j1 <= j0: continue
            X = gx[None, i0:i1]; Y = gy[j0:j1, None]; dx, dy = bx - ax, by - ay; l2 = dx * dx + dy * dy
            t = np.zeros_like(X * Y) if l2 == 0 else np.clip(((X - ax) * dx + (Y - ay) * dy) / l2, 0, 1)
            D = np.hypot(X - (ax + t * dx), Y - (ay + t * dy))
            for s in sides:
                soft[s][j0:j1, i0:i1] = np.maximum(soft[s][j0:j1, i0:i1], (D <= ws) * CORR_W)
                if hd: hard[s][j0:j1, i0:i1] = np.maximum(hard[s][j0:j1, i0:i1], (D <= wc))
        else:
            x0, y0, x1, y1 = g; w = ESC_W if kind == "esc" else CORR_W
            i0, i1 = np.searchsorted(gx, x0), np.searchsorted(gx, x1); j0, j1 = np.searchsorted(gy, y0), np.searchsorted(gy, y1)
            for s in sides:
                soft[s][j0:j1, i0:i1] = np.maximum(soft[s][j0:j1, i0:i1], w)
                if hd: hard[s][j0:j1, i0:i1] = 1
    return {s: (_integ(soft[s]) if soft[s].any() else None, _integ(hard[s]) if hard[s].any() else None) for s in ("F", "B")}

def _state(ctx, r):
    """per-net shapes and integrals valid for evaluating part r. A net is rebuilt when the pose of one of its placed
    terminal parts changed, except the nets r itself is on (r never pays for those, so they can wait)."""
    cache = S.setdefault("cache", {}); changed = False
    if S.get("pkey") != (len(ctx.P), r):
        buses = _buses(ctx); S["pkey"] = (len(ctx.P), r); S["bus"] = buses
    buses = S["bus"]
    mine = {v[2] for v in ctx.lp[r]} if r is not None else set()
    for n in S["names"]:
        if n in mine and n in cache: continue
        key = (n in buses,) + tuple((t, ctx.P[t], ctx.sideF[t]) for t in S["nparts"][n] if t in ctx.P)
        c = cache.get(n)
        if c is not None and c[0] == key: continue
        sh = build_net(ctx, n, n in buses); cache[n] = (key, sh, _raster_net(sh)); changed = True
    if changed or "tot" not in S:
        tot = {}
        for s in ("F", "B"):
            for w in (0, 1):
                arrs = [c[2][s][w] for c in cache.values() if c[2][s][w] is not None]
                tot[(s, w)] = sum(arrs) if arrs else None
        S["tot"] = tot
    return cache

def _overlap(ctx, r, k, xs, ys, which):
    """body overlap of r with the corridors of the nets r is not on, mm2 x weight (which 0 soft, 1 hard)"""
    cache = _state(ctx, r); s = "F" if ctx.sideF[r] else "B"
    It = S["tot"][(s, which)]
    if It is None: return None
    gx, gy = S["gx"], S["gy"]; nx, ny = len(gx), len(gy)
    b = ctx.rbox(ctx.bbx[ctx.ri[r]], k)
    i0 = np.minimum(np.searchsorted(gx, xs + b[0]), nx)[None, :]; i1 = np.minimum(np.searchsorted(gx, xs + b[2]), nx)[None, :]
    j0 = np.minimum(np.searchsorted(gy, ys + b[1]), ny)[:, None]; j1 = np.minimum(np.searchsorted(gy, ys + b[3]), ny)[:, None]
    def q(A): return A[j1, i1] - A[j0, i1] - A[j1, i0] + A[j0, i0]
    o = q(It)
    for n in {v[2] for v in ctx.lp[r]}:
        c = cache.get(n)
        if c is not None and c[2][s][which] is not None: o = o - q(c[2][s][which])
    return o * RS * RS

def extra_cost(ctx, r, k, xs, ys):
    c = 0.0
    if CORR_W > 0 or ESC_W > 0:
        o = _overlap(ctx, r, k, xs, ys, 0)
        if o is not None: c = c + o
    if (CMPW > 0 or CMP_TVS > 0) and r in S["term"]:
        X = xs[None, :]; Y = ys[:, None]
        for n, js, I in S["term"][r]:
            T = S["nets"][n]["T"]
            w = CMPW * I
            if CMP_TVS > 0 and r[0] == "D" and any(o.startswith("J") for o, _, _, k2 in T if k2 == "series"):
                T = [t for t in T if t[0].startswith("J")]; w = CMP_TVS     # a TVS on a connector net belongs at the connector
            q = [ctx.pad_xy(o, j) for o, js2, _, _ in T if o in ctx.P and o != r for j in js2]
            if not q: continue
            q = np.array(q); dmin = None
            for j in js:
                ox, oy = ctx.rotv(ctx.lp[r][j][0], ctx.lp[r][j][1], k)
                for tx, ty in q:
                    dd = np.hypot(X + ox - tx, Y + oy - ty); dmin = dd if dmin is None else np.minimum(dmin, dd)
            c = c + w * dmin
    if CROSSW > 0 and r in S["term"]: c = c + CROSSW * _crossings(ctx, r, k, xs, ys)
    if CORR_BOXW > 0 and r in S["chain"]: c = c + _boxcost(ctx, r, k, xs, ys)
    return c

def _crossings(ctx, r, k, xs, ys):
    """number of crossings of r's prospective corridor segments (one per corridor net of r that has other placed
    terminals: the mean of r's pads on it -> the nearest placed terminal pad) with the placed strips of the nets r
    is not on, on r's side, and with each other"""
    cache = _state(ctx, r); side = "F" if ctx.sideF[r] else "B"; mine = {v[2] for v in ctx.lp[r]}
    X = xs[None, :]; Y = ys[:, None]; segs = []
    for n, js, I in S["term"][r]:
        if n in S["bus"]: continue
        q = np.array([ctx.pad_xy(o, j) for o, js2, _, _ in S["nets"][n]["T"] if o in ctx.P and o != r for j in js2])
        if not len(q): continue
        off = [ctx.rotv(ctx.lp[r][j][0], ctx.lp[r][j][1], k) for j in js]
        ox = float(np.mean([a for a, _ in off])); oy = float(np.mean([b for _, b in off]))
        PX = X + ox + 0 * Y; PY = Y + oy + 0 * X
        D = np.stack([np.hypot(PX - qx, PY - qy) for qx, qy in q]); a = np.argmin(D, axis=0)
        segs.append((n, PX, PY, q[a, 0], q[a, 1]))
    if not segs: return 0.0
    def cr(ux, uy, vx, vy): return ux * vy - uy * vx
    cnt = 0.0
    x0 = min(float(np.min(np.minimum(s[1], s[3]))) for s in segs); x1 = max(float(np.max(np.maximum(s[1], s[3]))) for s in segs)
    y0 = min(float(np.min(np.minimum(s[2], s[4]))) for s in segs); y1 = max(float(np.max(np.maximum(s[2], s[4]))) for s in segs)
    for n2, c in cache.items():
        if n2 in mine: continue
        for _, kind, sides, g, _ in c[1]:
            if kind != "strip" or side not in sides: continue
            ax, ay, bx, by = g[:4]
            if max(ax, bx) < x0 or min(ax, bx) > x1 or max(ay, by) < y0 or min(ay, by) > y1: continue
            for n, PX, PY, QX, QY in segs:
                d1 = cr(bx - ax, by - ay, PX - ax, PY - ay); d2 = cr(bx - ax, by - ay, QX - ax, QY - ay)
                d3 = cr(QX - PX, QY - PY, ax - PX, ay - PY); d4 = cr(QX - PX, QY - PY, bx - PX, by - PY)
                cnt = cnt + ((d1 * d2 < 0) & (d3 * d4 < 0))
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            _, PX, PY, QX, QY = segs[i]; _, AX, AY, BX, BY = segs[j]
            d1 = cr(BX - AX, BY - AY, PX - AX, PY - AY); d2 = cr(BX - AX, BY - AY, QX - AX, QY - AY)
            d3 = cr(QX - PX, QY - PY, AX - PX, AY - PY); d4 = cr(QX - PX, QY - PY, BX - PX, BY - PY)
            cnt = cnt + ((d1 * d2 < 0) & (d3 * d4 < 0))
    return cnt

def extra_illegal(ctx, r, k, xs, ys):
    if not (CORR_HARD > 0 or ESC_HARD): return None
    o = _overlap(ctx, r, k, xs, ys, 1)
    if o is None: return None
    return o > 0.02

def _boxcost(ctx, r, k, xs, ys):
    bx = ctx.boxof.get(r)
    if not bx: return 0.0
    b = ctx.rbox(ctx.bbx[ctx.ri[r]], k); X = xs[None, :]; Y = ys[:, None]; m = CORR_BOXM
    return CORR_BOXW * (np.maximum(0, bx[0] - m - (X + b[0])) + np.maximum(0, X + b[2] - bx[2] - m) + np.maximum(0, bx[1] - m - (Y + b[1])) + np.maximum(0, Y + b[3] - bx[3] - m))

def _place_chain(ctx, q):
    """place one chain part: search window = its pin targets and its floorplan box, grown until a legal spot exists"""
    pts = []
    for n, js, I in S["term"].get(q, []):
        pts += [ctx.pad_xy(o, j) for o, js2, _, _ in S["nets"][n]["T"] if o in ctx.P and o != q for j in js2]
    bx = ctx.boxof.get(q)
    if bx and CORR_BOXW > 0: pts += [(bx[0], bx[1]), (bx[2], bx[3])]
    if not pts: ctx.place_small(q); return
    c0 = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
    for g in (3.0, 6.0, 12.0):
        best = ctx.place(q, (c0[0] - g, c0[1] - g, c0[2] + g, c0[3] + g), 0.1 if g < 6 else 0.2)
        if best is not None: ctx.put(q, best); return
    ctx.place_small(q)

def _place_hlcap(ctx, cap, hl):
    nets = {}
    for t in hl["switch_pins"]:
        ref, pin = t.split("."); nums = S["C"].get("pin_pads", {}).get(t, [])
        for j, v in enumerate(ctx.lp[ref]):
            if v[3] in nums: nets.setdefault(v[2], []).append(ctx.pad_xy(ref, j))
    sw = [p for ps in nets.values() for p in ps]
    if not sw: ctx.place_small(cap); return
    def ex(r_, k, xs, ys):
        X = xs[None, :]; Y = ys[:, None]; c = 0.0
        for j, v in enumerate(ctx.lp[r_]):
            tg = nets.get(v[2])
            if not tg: continue
            ox, oy = ctx.rotv(v[0], v[1], k)
            c = c + 10.0 * np.min([np.hypot(X + ox - tx, Y + oy - ty) for tx, ty in tg], axis=0)
        return c
    cx = float(np.mean([p[0] for p in sw])); cy = float(np.mean([p[1] for p in sw]))
    for g in (5.0, 9.0, 15.0):
        best = ctx.place(cap, (cx - g, cy - g, cx + g, cy + g), 0.1 if g < 9 else 0.2, ex)
        if best is not None: ctx.put(cap, best); return
    ctx.place_small(cap)

def after_big(ctx, r):
    """CORR_PRE=1: right after a large part with power pins (a PD chip, a FET pair) is placed, place the power-path
    parts (series terminals that are not large parts themselves) chained to it through its power nets, nearest link
    first, before its support parts fill the room round it. Chains stop at bus nets (PACK_P), at fixed parts and at
    large parts (the main loop places those with its room rule). Not locked: the passes may still move them."""
    if not CORR_PRE: return
    big = {q for q in ctx.fill if ctx.npads[q] >= int(os.environ.get("BIG_PADS", 12))}
    if CORR_PRE_WAIT:       # wait until every large power part (PD chips, FET pairs) is placed, then chain from each
        if S.get("fired") or not all(q in ctx.P for q in big if q in S["term"]): return
        S["fired"] = True
        for q in sorted((q for q in big if q in S["term"]), key=lambda q: ctx.npads[q], reverse=True): _chain(ctx, q, big)
        return
    if r not in S["term"]: return
    _chain(ctx, r, big)

def _chain(ctx, r, big):
    buses = _buses(ctx) | {n for n, v in S["nets"].items() if sum(t[3] == "series" for t in v["T"]) >= BUS_MIN_T}   # PACK_P
    front = [r]; done = []; seen = []
    while front:
        a = front.pop(0)
        for n, js, I in S["term"].get(a, []):
            if n in buses or I < CORR_MIN_A: continue
            if n not in seen: seen.append(n)
            for q, js2, I2, kind in S["nets"][n]["T"]:
                if kind != "series" or q in ctx.P or q in big or q not in ctx.fill: continue
                _place_chain(ctx, q); done.append(q); front.append(q)
    if CORR_PRE >= 2:       # then the shunt terminals (TVS, bulk and input caps) of the nets the chain went through
        for n in seen:
            if any(k2 == "series" and q not in ctx.P for q, _, _, k2 in S["nets"][n]["T"]): continue   # path not defined yet
            for q, js2, I2, kind in sorted(S["nets"][n]["T"], key=lambda t: t[0]):
                if kind != "shunt" or q in ctx.P or q in big or q not in ctx.fill or q in S["hlcaps"]: continue
                _place_chain(ctx, q); done.append(q)
    if CORR_PRE >= 2:       # alone (no cpower): the remaining caps of every hot loop whose switch parts are all placed now,
        C = S["C"]          # each at its loop: supply pad to the switch's supply pins, return pad to its return pins
        for name, hl in C.get("hot_loops", {}).items():
            sw = {t.split(".")[0] for t in hl["switch_pins"]}
            if not all(q in ctx.P for q in sw): continue
            for cap in hl["caps"]:
                if cap in ctx.P or cap not in ctx.fill: continue
                _place_hlcap(ctx, cap, hl); done.append(cap)
    if done: print(f"  ccorr after {r}: placed {[(q, tuple(round(v, 1) for v in ctx.P[q])) for q in done if q in ctx.P]}", flush=True)

def post_place(ctx):
    S.pop("pkey", None); cache = _state(ctx, None); sh = [x for c in cache.values() for x in c[1]]
    tot = 0.0; bad = {}
    for r in ctx.fill:
        if r not in ctx.P: continue
        x, y, k = ctx.P[r]
        o = _overlap(ctx, r, k, np.array([x]), np.array([y]), 0)
        if o is not None and float(o[0, 0]) > 0: bad[r] = round(float(o[0, 0]), 1); tot += float(o[0, 0])
    st = [x for x in sh if x[1] == "strip"]; xings = []
    def cr(ux, uy, vx, vy): return ux * vy - uy * vx
    for i in range(len(st)):
        for j in range(i + 1, len(st)):
            (na, _, sa, (ax, ay, bx, by, *_), _), (nb, _, sb, (px, py, qx, qy, *_), _) = st[i], st[j]
            if na == nb or not (sa & sb): continue
            if (cr(bx - ax, by - ay, px - ax, py - ay) * cr(bx - ax, by - ay, qx - ax, qy - ay) < 0 and
                    cr(qx - px, qy - py, ax - px, ay - py) * cr(qx - px, qy - py, bx - px, by - py) < 0): xings.append((na.split("/")[-2:], nb.split("/")[-2:]))
    print(f"ccorr: {len(xings)} corridor crossings: {[a[-1] + 'x' + b[-1] + ('' if a[0] == b[0] else ' ' + a[0][-6:] + '/' + b[0][-6:]) for a, b in xings]}", flush=True)
    print(f"ccorr: {len(sh)} corridor shapes; weighted overlap left {tot:.1f} over {len(bad)} parts: "
          f"{dict(sorted(bad.items(), key=lambda kv: -kv[1])[:12])}", flush=True)
    if DEBUG:
        json.dump(dict(shapes=[dict(net=n, kind=k, sides=sorted(s), g=list(g), hard=h) for n, k, s, g, h in sh],
                       buses=sorted(S["bus"])), open(DEBUG, "w"))
