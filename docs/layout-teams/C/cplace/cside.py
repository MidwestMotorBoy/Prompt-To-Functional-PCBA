"""cside.py: two-sided placement hook for cplace.py (package sides). Off unless HOOKS contains cside.

Lets small, low passives go to B.Cu when the top is crowded where they would sit. The flip itself is done by
c_apply.py (KiCad Flip LEFT_RIGHT about the origin, then the same quarter turn as on top); the placer convention is
pad at template-local (lx, ly) -> origin + rotv(-lx, ly, k) on the other side (cplace.set_side does the mirror).

SIDE RULE (who may change side; the board owner may veto it):
  - a part cplace places (in clusters.json), not LOCKed by another hook (power stages are), no through pads;
  - footprint is a chip resistor or capacitor of size SIDE_SIZES (default 0201,0402,0603: no taller than about
    0.9 mm, as low as the bottom already allows; the fixed bottom parts are 1210 MLCCs and 7343 tantalums in the cup
    pockets between the keep-outs, but the cup model is not in the repo, so nothing taller than 0603 is moved);
    SOD-523/SOD-882 diodes only with SIDE_DIODES=1;
  - not a hot-loop capacitor, not in constraints.json draw (cin, cout, inductor, rin, rout, div, boot), not a Kelvin
    sense resistor;
  - no pad on a power net of SIDE_PWR_A amps or more, a switching net, a sensitive net (FB, TS), a Kelvin sense net,
    a current-sense input (max_v <= 0.2 V: gauge SRP/SRN) or a net matching SIDE_EXCL_NETS (default: RF match ANT_IN/RFIO,
    gate drive HIDRV/LODRV/HG/LG, bootstrap BTST/BST, sense SRP*/SRN*/ACP*/ACN*);
  - with SIDE_CHIPS set (comma list of refs), only parts sharing a signal net with one of those chips.
COST of the bottom (mm-equivalent, added by extra_cost when the part is on the other side than the template):
  SIDE_B_MM (base, default 1.0)
  + SIDE_VIA_MM (1.0) per pad on a signal net + SIDE_GVIA_MM (0.4) per GND pad (each needs a via to reach the top
    pin or the inner GND plane; wiring()/near_cost() measure pad-to-pad distance and do not see the side, so the via
    is charged here)
  + SIDE_FREE_MM (6.0) * free fraction of F.Cu within SIDE_RING (2.5 mm) of the spot (prefer B only where the top is
    crowded).
LEGALITY on B (extra_illegal): besides cplace's per-side bodies, B keep-outs and through boxes, no B body within
  SIDE_PWR_KEEP (1.0 mm) of a pad of a power (>= SIDE_PWR_A) or switching net of any placed part on either side
  (the copper planner puts via arrays and outer-layer copper at those terminals).
VIA SITES (off unless set; recommended SIDE_VS_MM=1 SIDE_GVS_MM=0.5 SIDE_VS_PWR=1.0 SIDE_VS_HARD=1 SIDE_VRES=1):
  a via site = 0.25 mm cells free of bodies and reservations on BOTH sides, eroded one cell (about 0.75 mm square),
  not within SIDE_VS_PWR mm of a power/switching pad, and (SIDE_CU=<spec.json of an earlier scorecard run, e.g.
  sides/cu_prior_s4.json>) not on the planner's hard power copper of F.Cu/B.Cu.
  SIDE_VS_MM per mm of detour B pad -> via site -> nearest top pin of the net, over the straight pad-to-pin distance;
  SIDE_VS_NONE (15) when no site lies within SIDE_VS_R (3 mm) of the pin; SIDE_VS_HARD=1 makes that case illegal.
  SIDE_GVS_MM per mm from a GND/plane pad to its nearest site beyond 0.5 mm.
  SIDE_VRES=1 reserves the chosen site of every pad of every bottom part (both sides, +-SIDE_VRES_H 0.4 mm) while
  the placer runs, so later top parts leave the via room free (dropped before the json is written).
  With SIDE_CU a bottom body may not sit on that reference B.Cu power copper either.
POST MODE: SIDE_POST=N keeps the fill one-sided (same placement as without cside, given PYTHONHASHSEED) and then
  moves up to N parts to B within +-SIDE_POST_WIN (1 mm) of where they sit, most crowded top first (top free fraction
  < SIDE_POST_FREE 0.2), when the bottom spot costs at most SIDE_POST_TOL (5 mm) more. Nothing else moves.
SIDE_DEBUG=1 prints each bottom part with its via cost and top free fraction.
SIDE_DENY=refs (comma list) never moves those parts: feed it the bottom parts the ghost router could not reach on an
earlier screen (sides/deny_from_ghost.py ghost.log [...]). SIDE_LATE=1 offers B only in the re-place passes (after the one-sided first fill). SIDE_MAXB caps the number of parts this hook moves to B (default 999).
"""
import os, re, json
from collections import Counter
import numpy as np

E = os.environ
SIZES = [s for s in E.get("SIDE_SIZES", "0201,0402,0603").split(",") if s]
DIODES = int(E.get("SIDE_DIODES", 0))
B_MM = float(E.get("SIDE_B_MM", 1.0)); VIA_MM = float(E.get("SIDE_VIA_MM", 1.0)); GVIA_MM = float(E.get("SIDE_GVIA_MM", 0.4))
FREE_MM = float(E.get("SIDE_FREE_MM", 6.0)); RING = float(E.get("SIDE_RING", 2.5))
PWR_A = float(E.get("SIDE_PWR_A", 1.0)); PWR_KEEP = float(E.get("SIDE_PWR_KEEP", 1.0))
LATE = int(E.get("SIDE_LATE", 0))      # 1: offer B only once every other part is placed (re-place passes), so the first fill is the one-sided one
MAXB = int(E.get("SIDE_MAXB", 999)); CHIPS = [c for c in E.get("SIDE_CHIPS", "").split(",") if c]
VS_MM = float(E.get("SIDE_VS_MM", 0)); VS_R = float(E.get("SIDE_VS_R", 3.0)); VS_NONE = float(E.get("SIDE_VS_NONE", 15.0)); GVS_MM = float(E.get("SIDE_GVS_MM", 0)); VS_PWR = float(E.get("SIDE_VS_PWR", 0)); VS_HARD = int(E.get("SIDE_VS_HARD", 0)); VRES = int(E.get("SIDE_VRES", 0)); VRES_H = float(E.get("SIDE_VRES_H", 0.4)); CU = E.get("SIDE_CU", "")
POST = int(E.get("SIDE_POST", 0)); POST_WIN = float(E.get("SIDE_POST_WIN", 1.0)); POST_TOL = float(E.get("SIDE_POST_TOL", 5.0)); POST_FREE = float(E.get("SIDE_POST_FREE", 0.2))
DENY = {r for r in E.get("SIDE_DENY", "").split(",") if r}   # parts never moved (e.g. from sides/deny_from_ghost.py)
EXCL_NETS = re.compile(E.get("SIDE_EXCL_NETS", r"(^|/)(ANT_IN|RFIO|HIDRV\d*|LODRV\d*|HG\d*|LG\d*|BTST\d*|BST|SRP\w*|SRN\w*|ACP\w*|ACN\w*)$"))
TEMPLATE = E.get("SIDE_TEMPLATE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../../tools/score/template/board.kicad_pcb"))

def _footprints(path):
    t = open(path, encoding="utf-8").read(); out = {}
    for m in re.finditer(r'\n\t\(footprint "([^"]+)".*?\(property "Reference" "([^"]+)"', t, re.S): out.setdefault(m.group(2), m.group(1))
    return out

def _bare(n): return (n or "").lstrip("/")

def setup(ctx):
    c = json.load(open(ctx.env["CONSTRAINTS"])) if ctx.env.get("CONSTRAINTS") else {}
    fpn = _footprints(TEMPLATE)
    nets = {_bare(k): v for k, v in c.get("nets", {}).items()}
    bad_net = set()
    for n, v in nets.items():
        if v.get("kind") == "switching" or v.get("kind") == "sensitive" or (v.get("kind") == "power" and (v.get("current_a") or 0) >= PWR_A): bad_net.add(n)
        if v.get("max_v") is not None and 0 < v["max_v"] <= 0.2: bad_net.add(n)          # current-sense inputs (gauge SRP/SRN)
    for k in c.get("kelvin", {}).values(): bad_net.update(_bare(k[x]) for x in ("pos", "neg"))
    bad_net.update(_bare(p["net"]) for p in ctx.d["pads"] if p["net"] and EXCL_NETS.search(_bare(p["net"])))   # RF match, gate drive, sense
    excl = set()
    for hl in c.get("hot_loops", {}).values(): excl.update(hl.get("caps", []))
    for st in c.get("draw", {}).values():
        for key, v in st.items():
            if key in ("cin", "cout", "div"): excl.update(v)
            elif key in ("inductor", "rin", "rout", "boot"): excl.add(v)
    for k in c.get("kelvin", {}).values(): excl.add(k.get("resistor"))
    chip_nets = set()
    for ch in CHIPS: chip_nets.update(v[2] for v in ctx.lp.get(ch, []) if v[2] in ctx.sig)
    ok = set(); why = Counter()
    for r in ctx.fill:
        name = fpn.get(r, ""); lib, _, fp = name.partition(":")
        rc = re.match(r"(R|C)_(\d{4})_", fp) and lib in ("Resistor_SMD", "Capacitor_SMD")
        if not ((rc and fp.split("_")[1] in SIZES) or (DIODES and fp.startswith(("D_SOD-523", "D_SOD-882")))): why["footprint"] += 1; continue
        if r in excl: why["power stage / kelvin"] += 1; continue
        if r in DENY: why["SIDE_DENY"] += 1; continue
        if ctx.thru[ctx.ri[r]]: why["through pads"] += 1; continue
        if any(_bare(v[2]) in bad_net for v in ctx.lp0[r]): why["power/switching/sensitive/kelvin net"] += 1; continue
        if CHIPS and not any(v[2] in chip_nets for v in ctx.lp0[r]): why["not at SIDE_CHIPS"] += 1; continue
        ok.add(r)
    ctx.side_ok = ok; ctx.side_bad_net = bad_net; ctx.side_cache = {}
    pw = set(); raw = {_bare(n) for n in bad_net}
    for p in ctx.d["pads"]:
        if p["net"] and _bare(p["net"]) in raw and nets.get(_bare(p["net"]), {}).get("kind") in ("power", "switching"): pw.add(p["net"])
    ctx.side_pwr_nets = pw
    print(f"[sides] {len(ok)} parts may go to B (of {len(ctx.fill)}); excluded: {dict(why)}", flush=True)

def _onB(ctx, r): return ctx.sideF[r] != ctx.side0[r]

def _site_for(ctx, r, j):
    """the via site (x, y) the bottom part r's pad j would use now (nearest top pin of its net through the best site;
    GND/plane pad: the site nearest the pad), or None"""
    c = _sites(ctx)
    if len(c["sx"]) == 0: return None
    px, py = ctx.pad_xy(r, j); n = ctx.lp[r][j][2]
    dp = np.hypot(c["sx"] - px, c["sy"] - py)
    if n == "GND" or n not in ctx.sig:
        q = int(np.argmin(dp)); return (c["sx"][q], c["sy"][q]) if dp[q] <= VS_R else None
    tg = [ctx.pad_xy(o, jj) for o in set(ctx.netpads[n]) if o in ctx.P and o != r and ctx.sideF[o] for jj, v in enumerate(ctx.lp[o]) if v[2] == n]
    if not tg: return None
    best = None
    for tx, ty in tg:
        dct = np.hypot(c["sx"] - tx, c["sy"] - ty); tot = np.where(dct <= VS_R, dp + dct, np.inf); q = int(np.argmin(tot))
        if np.isfinite(tot[q]) and (best is None or tot[q] < best[0]): best = (tot[q], c["sx"][q], c["sy"][q])
    return None if best is None else (best[1], best[2])

def _sync_res(ctx):
    """keep one reserved via site (both sides, +-VRES_H mm) per pad of every bottom part, so later top parts leave it free"""
    res = ctx.__dict__.setdefault("side_res", {})
    for o in list(res):
        pose = ctx.P.get(o)
        if pose is None or not _onB(ctx, o) or res[o][0] != pose:
            for key in res[o][1]: ctx.OB.pop(key, None)
            del res[o]
    for o in sorted(ctx.side_ok):
        if o in res or o not in ctx.P or not _onB(ctx, o): continue
        keys = []
        for j, v in enumerate(ctx.lp[o]):
            if not v[2]: continue
            st = _site_for(ctx, o, j)
            if st is None: continue
            key = f"_sidevia_{o}_{j}"; b = (st[0] - VRES_H, st[1] - VRES_H, st[0] + VRES_H, st[1] + VRES_H)
            ctx.OB[key] = [(True, b, "b"), (True, b, "t"), (False, b, "b"), (False, b, "t")]; keys.append(key)
        res[o] = (ctx.P[o], keys)

def _no_site(ctx, r):
    """True when some signal pad of r (on B) has top pins of its net but none of them has a via site within VS_R"""
    c = _sites(ctx)
    for j, (lx, ly, n, num) in enumerate(ctx.lp[r]):
        if not n or n == "GND" or n not in ctx.sig: continue
        tg = [ctx.pad_xy(o, jj) for o in set(ctx.netpads[n]) if o in ctx.P and o != r and ctx.sideF[o] for jj, v in enumerate(ctx.lp[o]) if v[2] == n]
        if tg and not any(len(c["sx"]) and np.min(np.hypot(c["sx"] - tx, c["sy"] - ty)) <= VS_R for tx, ty in tg): return True
    return False

def side_options(ctx, r):
    if VRES: _sync_res(ctx)
    if POST: return None                   # SIDE_POST: one-sided fill (same placement as without cside), flips in post_place
    if r not in ctx.side_ok or r in ctx.LOCK: return None
    if LATE and sum(1 for q in ctx.fill if q not in ctx.P and q != r) > 0: return None
    if not _onB(ctx, r) and sum(1 for q in ctx.side_ok if q in ctx.P and q != r and _onB(ctx, q)) >= MAXB: return None
    return [ctx.side0[r], not ctx.side0[r]]

def _top_free(ctx):
    key = (len(ctx.OB), round(sum(v[0] + 3 * v[1] for v in ctx.P.values()), 3))
    if ctx.side_cache.get("key") != key:
        ctx.side_cache = dict(key=key, I=ctx.integral(ctx.occ_map(True)))
    return ctx.side_cache["I"]

def _cu_masks(ctx):
    """SIDE_CU=<scorecard spec.json of an earlier screen>: the power copper the planner drew there (hard zones, not GND),
    rasterised on the 0.25 mm grid and grown 0.25 mm: (on F, on B). A prior: the stages are the same on every cpower run."""
    c = ctx.side_cache0 if hasattr(ctx, "side_cache0") else ctx.__dict__.setdefault("side_cache0", {})
    if "cuF" not in c:
        from PIL import Image, ImageDraw
        from scipy import ndimage
        RS = 0.25; bx = ctx.box; nx = len(np.arange(bx[0], bx[2], RS)); ny = len(np.arange(bx[1], bx[3], RS))
        im = {L: Image.new("1", (nx, ny), 0) for L in ("F.Cu", "B.Cu")}
        if CU:
            for z in json.load(open(CU))["zones"]:
                if z.get("soft") or z["net"] == "GND" or z["layer"] not in im: continue
                dr = ImageDraw.Draw(im[z["layer"]])
                for pl in z["polys"]:
                    dr.polygon([((x - bx[0]) / RS, (y - bx[1]) / RS) for x, y in pl["ring"]], fill=1)
                    for h in pl.get("holes", []): dr.polygon([((x - bx[0]) / RS, (y - bx[1]) / RS) for x, y in h], fill=0)
        g = lambda a: ndimage.binary_dilation(np.array(a, bool), np.ones((3, 3), bool))
        c["cuF"] = g(im["F.Cu"]); c["cuB"] = g(im["B.Cu"]); c["cuBI"] = ctx.integral(~c["cuB"])   # integral counts cells NOT free = copper
    return c

def _sites(ctx):
    """via sites: 0.25 mm cells free of bodies (and reservations) on BOTH sides, eroded by one cell (a via + clearance
    needs about 0.75 mm); returns (cell centres x, y of the sites, distance-to-nearest-site raster in mm, grid)"""
    key = (len(ctx.OB), round(sum(v[0] + 3 * v[1] for v in ctx.P.values()), 3))
    c = ctx.side_cache
    if c.get("skey") != key:
        from scipy import ndimage
        RS = 0.25; bx = ctx.box; gx = np.arange(bx[0], bx[2], RS) + RS / 2; gy = np.arange(bx[1], bx[3], RS) + RS / 2
        free = ~ctx.occ_map(True) & ~ctx.occ_map(False)
        if CU: m = _cu_masks(ctx); free &= ~m["cuF"] & ~m["cuB"]
        if VS_PWR > 0:                     # the copper planner pours round power/switching pads: no via site there
            for q in ctx.P:
                if q not in ctx.lp: continue
                for jj, v in enumerate(ctx.lp[q]):
                    if v[2] not in ctx.side_pwr_nets: continue
                    o = _pad_box(ctx, q, jj)
                    i0 = max(0, int((o[0] - VS_PWR - bx[0]) / RS)); i1 = int(np.ceil((o[2] + VS_PWR - bx[0]) / RS))
                    j0 = max(0, int((o[1] - VS_PWR - bx[1]) / RS)); j1 = int(np.ceil((o[3] + VS_PWR - bx[1]) / RS))
                    free[j0:j1, i0:i1] = False
        site = ndimage.binary_erosion(free, np.ones((3, 3), bool))
        j, i = np.nonzero(site)
        c.update(skey=key, sx=gx[i], sy=gy[j], edt=ndimage.distance_transform_edt(~site) * RS, gx0=bx[0], gy0=bx[1], RS=RS)
    return c

def _edt_at(c, X, Y):
    e = c["edt"]; i = np.clip(np.round((X - c["gx0"] - c["RS"] / 2) / c["RS"]).astype(int), 0, e.shape[1] - 1)
    j = np.clip(np.round((Y - c["gy0"] - c["RS"] / 2) / c["RS"]).astype(int), 0, e.shape[0] - 1)
    return e[j, i]

def _via_cost(ctx, r, k, xs, ys):
    """per pad of a bottom part: signal pad -> extra length of going B pad -> via site -> nearest top-side pin of the net
    over the straight pad-to-pin distance (wiring() already charges that); no via site within VS_R of the pin -> VS_NONE.
    GND / plane-net pad -> distance from the pad to the nearest via site beyond 0.5 mm."""
    c = _sites(ctx); X = xs[None, :]; Y = ys[:, None]; tot = 0.0
    cx0 = 0.5 * (xs[0] + xs[-1]); cy0 = 0.5 * (ys[0] + ys[-1])
    for j, (lx, ly, n, num) in enumerate(ctx.lp[r]):
        if not n: continue
        ox, oy = ctx.rotv(lx, ly, k); PX = X + ox; PY = Y + oy
        if n == "GND" or n not in ctx.sig:
            if GVS_MM > 0: tot = tot + GVS_MM * np.maximum(0.0, _edt_at(c, PX, PY) - 0.5)
            continue
        if VS_MM <= 0: continue
        tg = [ctx.pad_xy(o, jj) for o in set(ctx.netpads[n]) if o in ctx.P and o != r and ctx.sideF[o] for jj, v in enumerate(ctx.lp[o]) if v[2] == n]
        if not tg: continue
        tg = sorted(tg, key=lambda t: (t[0] - cx0) ** 2 + (t[1] - cy0) ** 2)[:3]
        best = None
        for tx, ty in tg:
            dct = np.hypot(c["sx"] - tx, c["sy"] - ty); sel = np.nonzero(dct <= VS_R)[0]
            if len(sel) == 0: v = np.full(np.broadcast(PX, PY).shape, VS_NONE / max(VS_MM, 1e-9))
            else:
                sel = sel[np.argsort(dct[sel])]; sel = sel[dct[sel] <= dct[sel[0]] + 1.0][:80]
                m = None
                for q in sel:
                    d = np.hypot(PX - c["sx"][q], PY - c["sy"][q]) + dct[q]; m = d if m is None else np.minimum(m, d)
                v = m - np.hypot(PX - tx, PY - ty)
            best = v if best is None else np.minimum(best, v)
        tot = tot + VS_MM * np.maximum(best, 0.0)
    return tot

def extra_cost(ctx, r, k, xs, ys):
    if r not in getattr(ctx, "side_ok", ()) or not _onB(ctx, r): return 0.0
    nsig = sum(1 for v in ctx.lp[r] if v[2] and v[2] != "GND"); ng = sum(1 for v in ctx.lp[r] if v[2] == "GND")
    c = B_MM + VIA_MM * nsig + GVIA_MM * ng
    if FREE_MM > 0:
        I = _top_free(ctx); X = xs[None, :]; Y = ys[:, None]
        fr = ctx.free_in(I, X - RING, Y - RING, X + RING, Y + RING) / (2 * RING) ** 2
        c = c + FREE_MM * np.clip(fr, 0, 1)
    if VS_MM > 0 or GVS_MM > 0:
        own = getattr(ctx, "side_res", {}).get(r)       # r's own reserved via sites must not count against r (cur_cost)
        held = [(key, ctx.OB.pop(key)) for key in own[1] if key in ctx.OB] if own else []
        c = c + _via_cost(ctx, r, k, xs, ys)
        for key, v in held: ctx.OB[key] = v
    return c

def extra_illegal(ctx, r, k, xs, ys):
    if r not in getattr(ctx, "side_ok", ()) or not _onB(ctx, r): return None
    if VS_HARD and _no_site(ctx, r): return np.ones((len(ys), len(xs)), bool)
    cub = None
    if CU:                                 # no bottom body on the reference power copper of B.Cu
        m = _cu_masks(ctx); b0 = ctx.rbox(ctx.bbx[ctx.ri[r]], k); X = xs[None, :]; Y = ys[:, None]
        cub = ctx.free_in(m["cuBI"], X + b0[0], Y + b0[1], X + b0[2], Y + b0[3]) > 0
        if PWR_KEEP <= 0: return cub
    if PWR_KEEP <= 0: return None
    b = ctx.rbox(ctx.bbx[ctx.ri[r]], k); m = PWR_KEEP
    bad = np.zeros((len(ys), len(xs)), bool)
    X0, X1, Y0, Y1 = xs[0] + b[0] - m, xs[-1] + b[2] + m, ys[0] + b[1] - m, ys[-1] + b[3] + m
    for q, (x, y, kq) in ctx.P.items():
        if q == r: continue
        for j, v in enumerate(ctx.lp[q]):
            if v[2] not in ctx.side_pwr_nets: continue
            px, py = ctx.pad_xy(q, j)
            if px < X0 - 3 or px > X1 + 3 or py < Y0 - 3 or py > Y1 + 3: continue
            o = _pad_box(ctx, q, j)
            i0 = np.searchsorted(xs, o[0] - m - b[2], "right"); i1 = np.searchsorted(xs, o[2] + m - b[0], "left")
            j0 = np.searchsorted(ys, o[1] - m - b[3], "right"); j1 = np.searchsorted(ys, o[3] + m - b[1], "left")
            if i1 > i0 and j1 > j0: bad[j0:j1, i0:i1] = True
    return bad if cub is None else (bad | cub)

_PB = {}
def _pad_box(ctx, q, j):
    """pad j of part q as a box in board coordinates at q's current pose (pad size from the dump, turned with the part)"""
    if not _PB:
        pos0 = ctx.pos0; cnt = Counter()
        for p in ctx.d["pads"]:
            i = cnt[p["ref"]]; cnt[p["ref"]] += 1; x0, y0 = pos0[p["ref"]]; bx = p["box"]
            _PB[(p["ref"], i)] = (bx[0] - x0, bx[1] - y0, bx[2] - x0, bx[3] - y0)
    x, y, k = ctx.P[q]; lb = _PB[(q, j)]
    if ctx.sideF[q] != ctx.side0[q]: lb = (-lb[2], lb[1], -lb[0], lb[3])
    b = ctx.rbox(lb, k)
    return (x + b[0], y + b[1], x + b[2], y + b[3])

def _post_flip(ctx):
    """SIDE_POST=N: after the one-sided fill, move up to N parts to B right under where they sit (window +-SIDE_POST_WIN),
    most crowded top first (free fraction of F within SIDE_RING under SIDE_POST_FREE), when the bottom spot costs at most
    SIDE_POST_TOL mm more than the top one. Nothing else moves: the freed top area is left to the router."""
    def fr(r):
        x, y, _ = ctx.P[r]; return float(ctx.free_in(_top_free(ctx), x - RING, y - RING, x + RING, y + RING) / (2 * RING) ** 2)
    cands = sorted((fr(r), r) for r in ctx.side_ok if r in ctx.P and r not in ctx.LOCK and not _onB(ctx, r))
    n = 0
    for f0, r in cands:
        if n >= POST or f0 >= POST_FREE: break
        c_top = ctx.cur_cost(r); x, y, k = ctx.P[r]; del ctx.P[r]; ctx.OB.pop(r)
        if VRES: _sync_res(ctx)
        w = POST_WIN; best = ctx.place(r, (x - w, y - w, x + w, y + w), 0.1, sides=[not ctx.side0[r]])
        if best is not None and best[0] <= c_top + POST_TOL:
            ctx.put(r, best); n += 1
            print(f"[sides] post flip {r}: top cost {c_top:.1f} -> bottom {best[0]:.1f}, top free {f0:.2f}, moved {abs(best[1] - x) + abs(best[2] - y):.2f} mm")
        else: ctx.P[r] = (x, y, k); ctx.add_obstacle(r)
        if VRES: _sync_res(ctx)

def post_place(ctx):
    if POST: _post_flip(ctx)
    if VRES:                               # the reservations are placer-side only: drop them before the json is written
        for o, (pose, keys) in getattr(ctx, "side_res", {}).items():
            for key in keys: ctx.OB.pop(key, None)
        ctx.side_res = {}
    onb = sorted(r for r in ctx.fill if r in ctx.P and _onB(ctx, r))
    ctx.side_moved = onb
    if E.get("SIDE_DEBUG"):
        for r in onb:
            x, y, k = ctx.P[r]; X = np.array([x]); Y = np.array([y])
            ctx.OB.pop(r); vc = float(np.asarray(_via_cost(ctx, r, k, X, Y)).reshape(-1)[0]) if (VS_MM > 0 or GVS_MM > 0) else 0.0; ctx.add_obstacle(r)
            fr = ctx.free_in(_top_free(ctx), x - RING, y - RING, x + RING, y + RING) / (2 * RING) ** 2
            print(f"[sides] B {r} at {x:.2f},{y:.2f} nets {[v[2] for v in ctx.lp[r]]} via_cost {vc:.2f} top_free {float(fr):.2f}")
    print(f"[sides] parts moved to the other side: {len(onb)} (each is a hand-soldered part in a top-only assembly): {' '.join(onb)}", flush=True)
