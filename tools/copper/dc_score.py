"""dc_score.py <board.kicad_pcb, zones filled> <cu_dump.json of that board> <constraints.json> [out.json] [--res=0.1] [--net=substring] [--lossmap=out.npz]
DC resistance, drop, I2R loss, current density and per-via current of every power net and the return net, on the
board's real copper (pads, filled zones, tracks, vias, plated holes), with the terminals roles.py derives.

Per net: the series terminal with the largest current is the source; every other series terminal is solved
against it (1 A in, then scaled to its own current). Reported per terminal: resistance, drop at its current, loss
at its current; per net: the worst drop, the sum of losses (each path alone at its own current: an upper bound,
since paths that share copper do not all peak at once), the peak current density on each layer (A per mm of
width, with where) and the via or plated hole with the most current. A terminal with no copper path to the source
is "open": that net is not finished by power copper (the router has to finish it, or the copper is wrong).

The grid solver is the Battery-Bank one (pcb-copper-resistance skill), checked to 0.2 % on strips (spike 04),
generalised: sheet resistance and layer heights come from the board's stack-up, pads from exact polygons."""
import sys, os, json, math, re, time
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as sla
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from roles import Design
from sx import parse, find, get

RHO = 1.72e-8          # ohm m, copper at 20 C (warm copper is about 0.4 %/K higher)
PLATING_MM = 0.02      # via barrel plating thickness assumed (JLC standard is about 18 to 25 um)

def load_copper(path):
    """Filled zones, tracks and vias of a board file, by net."""
    t = parse(open(path, encoding="utf-8").read()); nets = {}
    for n in find(t, "net"):
        if len(n) > 2: nets[n[1]] = n[2]
    def nn(x):
        q = get(x, "net")
        if q is None: return ""
        v = q[1]; return nets.get(v, v)
    Z, S, V = [], [], []
    for z in find(t, "zone"):
        if get(z, "keepout"): continue
        net = nn(z)
        for fp in find(z, "filled_polygon"):
            L = get(fp, "layer")[1]; pts = [(float(q[1]), float(q[2])) for q in get(fp, "pts")[1:] if q[0] == "xy"]
            Z.append(dict(net=net, layer=L, pts=pts))
    for s in find(t, "segment"):
        a, b = get(s, "start"), get(s, "end"); S.append(dict(net=nn(s), layer=get(s, "layer")[1], w=float(get(s, "width")[1]), a=(float(a[1]), float(a[2])), b=(float(b[1]), float(b[2]))))
    for v in find(t, "via"):
        at = get(v, "at"); L = get(v, "layers")[1:]
        V.append(dict(net=nn(v), x=float(at[1]), y=float(at[2]), size=float(get(v, "size")[1]), drill=float(get(v, "drill")[1]), layers=L))
    return Z, S, V

class Grid:
    def __init__(self, D, Z, S, V, net, res, layers, rs, zpos):
        pts = [q for z in Z if z["net"] == net for q in z["pts"]] + [q for s in S if s["net"] == net for q in (s["a"], s["b"])] + [(v["x"], v["y"]) for v in V if v["net"] == net]
        for p in D.pads:
            if p["net"] == net:
                for recs in p["shapes"].values():
                    for r in recs: pts += r["ring"]
        xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
        self.x0, self.y0 = min(xs) - 1, min(ys) - 1; self.res = res
        W = int((max(xs) + 1 - self.x0) / res) + 1; H = int((max(ys) + 1 - self.y0) / res) + 1
        P = lambda x, y: ((x - self.x0) / res, (y - self.y0) / res); self.P = P
        self.masks = {}
        for L in layers:
            im = Image.new("L", (W, H), 0); d = ImageDraw.Draw(im)
            for z in Z:
                if z["net"] == net and z["layer"] == L and len(z["pts"]) > 2: d.polygon([P(*q) for q in z["pts"]], fill=1)
            for s in S:
                if s["net"] == net and s["layer"] == L:
                    a, b = P(*s["a"]), P(*s["b"]); w = s["w"] / res; d.line([a, b], fill=1, width=max(1, int(round(w))))
                    for q in (a, b): d.ellipse([q[0] - w / 2, q[1] - w / 2, q[0] + w / 2, q[1] + w / 2], fill=1)
            for p in D.pads:
                if p["net"] == net:
                    for r in p["shapes"].get(L, []): d.polygon([P(*q) for q in r["ring"]], fill=1)
            for v in V:
                if v["net"] == net:
                    c = P(v["x"], v["y"]); r = v["size"] / 2 / res; d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=1)
            self.masks[L] = np.array(im, dtype=bool)
        self.idx = {}; n = 0
        for L in layers:
            m = self.masks[L]; ids = -np.ones(m.shape, dtype=np.int64); k = int(m.sum()); ids[m] = np.arange(n, n + k); n += k; self.idx[L] = ids
        self.n = n; rows, cols, vals = [], [], []
        for L in layers:
            ids = self.idx[L]; g = 1.0 / rs[L]
            for a, b in ((ids[:, :-1], ids[:, 1:]), (ids[:-1, :], ids[1:, :])):
                ok = (a >= 0) & (b >= 0); rows.append(a[ok]); cols.append(b[ok]); vals.append(np.full(int(ok.sum()), g))
        self.vias = []
        def barrel(x, y, drill, what):
            c = P(x, y); ci, ri = int(round(c[0])), int(round(c[1]))
            present = [L for L in layers if 0 <= ri < H and 0 <= ci < W and self.idx[L][ri, ci] >= 0]
            for La, Lb in zip(present, present[1:]):
                R = RHO * (abs(zpos[Lb] - zpos[La]) * 1e-3) / (math.pi * (drill + PLATING_MM) * 1e-3 * PLATING_MM * 1e-3)
                a, b = self.idx[La][ri, ci], self.idx[Lb][ri, ci]
                rows.append(np.array([a])); cols.append(np.array([b])); vals.append(np.array([1 / R])); self.vias.append((x, y, La, Lb, a, b, 1 / R, what))
        for v in V:
            if v["net"] == net: barrel(v["x"], v["y"], v["drill"], "via")
        for p in D.pads:
            if p["net"] == net and p.get("drill"): barrel(p["x"], p["y"], p["drill"], p["key"])
        r = np.concatenate(rows); c = np.concatenate(cols); v = np.concatenate(vals)
        self.G = sp.coo_matrix((np.concatenate([-v, -v, v, v]), (np.concatenate([r, c, r, c]), np.concatenate([c, r, r, c]))), shape=(n, n)).tocsr()
        self.layers = layers; self.rs = rs

    def nodes(self, pads):
        out = []
        for p in pads:
            for L, recs in p["shapes"].items():
                if L not in self.idx: continue
                for rec in recs:
                    xs = [q[0] for q in rec["ring"]]; ys = [q[1] for q in rec["ring"]]
                    im = Image.new("L", self.idx[L].shape[::-1], 0); ImageDraw.Draw(im).polygon([self.P(*q) for q in rec["ring"]], fill=1)
                    m = np.array(im, dtype=bool) & (self.idx[L] >= 0); out += list(self.idx[L][m])
        return sorted(set(out))

def score_net(D, Z, S, V, net, res, layers, rs, zpos, acc=None):
    """acc: optional (array, x0, y0, step) to which the net's copper loss is added, W per bin (all terminals at their
    own current at once, the same upper bound as loss_W)."""
    T = [g for g in D.terminals(net) if g["kind"] == "series"]
    if len(T) < 2: return None
    T.sort(key=lambda g: (-g["current_a"], -len(g["pads"]), g["ref"])); src = T[0]
    t0 = time.time(); B = Grid(D, Z, S, V, net, res, layers, rs, zpos)
    sn = B.nodes(src["pads"])
    if not sn: return dict(net=net, error=f"source {src['ref']} has no copper cells")
    # pads of one part on one net are joined inside the part (an IC's two VBUS pins): a terminal counts as connected
    # when any of its pads is on the source's copper, and only those pads carry its current; the rest are listed
    from scipy.sparse.csgraph import connected_components
    cc = connected_components(B.G, directed=False)[1]; c0 = set(np.unique(cc[sn]).tolist())      # every pad of the source is fed
    d = np.zeros(B.n); d[sn] = 1e6
    Gd = (B.G + sp.diags(d) + sp.identity(B.n) * 1e-9).tocsc()
    try: lu = sla.splu(Gd); solve = lu.solve
    except MemoryError:
        import pyamg; ml = pyamg.smoothed_aggregation_solver(Gd.tocsr(), max_coarse=500); solve = lambda b: ml.solve(b, tol=1e-10, accel="cg", maxiter=500)
    out = dict(net=net, source=src["ref"], cells=B.n, res_mm=res, terminals=[], peak_A_per_mm={}, top_vias=[])
    Jmax = {L: (0.0, None) for L in layers}; vmax = {}
    for g in T[1:]:
        I = g["current_a"]; per = {p["num"]: B.nodes([p]) for p in g["pads"]}
        k = sorted({i for v in per.values() for i in v if cc[i] in c0}); loose = sorted(n for n, v in per.items() if not any(cc[i] in c0 for i in v))
        if not k:
            k = sorted({i for v in per.values() for i in v})
            if not k: out["terminals"].append(dict(ref=g["ref"], current_a=I, open=True, why="no copper under the pads")); continue
        b = np.zeros(B.n); b[k] = 1.0 / len(k); Vv = solve(b); R = float(np.mean(Vv[k]))
        if R > 1.0:
            isl = np.isin(cc, cc[k]); bb = []
            for L in layers:
                ids = B.idx[L]; m = (ids >= 0); m[m] = isl[ids[m]]
                if m.any(): w = np.argwhere(m); bb.append(f"{L} x {B.x0 + w[:, 1].min() * res:.1f}-{B.x0 + w[:, 1].max() * res:.1f} y {B.y0 + w[:, 0].min() * res:.1f}-{B.y0 + w[:, 0].max() * res:.1f}")
            out["terminals"].append(dict(ref=g["ref"], current_a=I, open=True, why="no copper path to " + src["ref"] + "; its island: " + "; ".join(bb))); continue
        out["terminals"].append(dict(ref=g["ref"], current_a=I, R_mohm=round(R * 1e3, 3), drop_mV=round(R * I * 1e3, 1), loss_W=round(R * I * I, 4), **({"pads_not_joined": loose} if loose else {})))
        for L in layers:      # current density, A per mm of width, at this terminal's current
            ids = B.idx[L]; m = ids >= 0
            if not m.any(): continue
            VV = np.full(ids.shape, np.nan); VV[m] = Vv[ids[m]] * I
            jx = np.nan_to_num(np.abs(np.diff(VV, axis=1))) / rs[L] / res; jy = np.nan_to_num(np.abs(np.diff(VV, axis=0))) / rs[L] / res
            J = np.zeros(ids.shape); J[:, :-1] = np.maximum(J[:, :-1], jx); J[:-1, :] = np.maximum(J[:-1, :], jy)
            if acc is not None:      # copper loss into the thermal bins: each link's dV^2/R at its cell
                A, ax0, ay0, st = acc; px = np.nan_to_num(np.diff(VV, axis=1)) ** 2 / rs[L]; py = np.nan_to_num(np.diff(VV, axis=0)) ** 2 / rs[L]
                for P_, sh in ((px, (0, 0)), (py, (0, 0))):
                    ii, jj = np.nonzero(P_)
                    if len(ii):
                        bi = ((B.y0 + ii * res - ay0) / st).astype(int).clip(0, A.shape[0] - 1); bj = ((B.x0 + jj * res - ax0) / st).astype(int).clip(0, A.shape[1] - 1)
                        np.add.at(A, (bi, bj), P_[ii, jj])
            f = int(np.argmax(J)); j = float(J.ravel()[f])
            if j > Jmax[L][0]: Jmax[L] = (j, (round(B.x0 + (f % J.shape[1]) * res, 2), round(B.y0 + (f // J.shape[1]) * res, 2), g["ref"]))
        for (x, y, La, Lb, a, bb, gv, what) in B.vias:
            i = abs(Vv[a] - Vv[bb]) * gv * I; key = (round(x, 2), round(y, 2), what)
            if i > vmax.get(key, (0,))[0]: vmax[key] = (i, g["ref"], La + "-" + Lb)
    out["peak_A_per_mm"] = {L: dict(A_per_mm=round(j, 2), at=w) for L, (j, w) in Jmax.items() if j > 0}
    out["top_vias"] = [dict(x=k[0], y=k[1], what=k[2], A=round(v[0], 2), for_terminal=v[1], span=v[2]) for k, v in sorted(vmax.items(), key=lambda kv: -kv[1][0])[:5]]
    ok = [t for t in out["terminals"] if not t.get("open")]
    out["worst_drop_mV"] = max([t["drop_mV"] for t in ok] or [0]); out["loss_W"] = round(sum(t["loss_W"] for t in ok), 4)
    out["open"] = [t["ref"] for t in out["terminals"] if t.get("open")]; out["seconds"] = round(time.time() - t0, 1)
    return out

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
    pcb, dump, cons = a[:3]; outf = a[3] if len(a) > 3 else None; res = float(opt.get("res", 0.1))
    acc = None
    if "lossmap" in opt:      # copper loss per 0.5 mm bin over the board, for thermal.py
        xs = [x for o in json.load(open(dump))["outline"] for x, _ in o["ring"]]; ys = [y for o in json.load(open(dump))["outline"] for _, y in o["ring"]]
        acc = (np.zeros((int((max(ys) - min(ys)) / 0.5) + 1, int((max(xs) - min(xs)) / 0.5) + 1)), min(xs), min(ys), 0.5)
    D = Design(dump, cons); Z, S, V = load_copper(pcb)
    layers = D.D["layers"]; st = {s["layer"]: s for s in D.D["stackup"]}
    rs = {L: RHO / (st[L]["t_mm"] * 1e-3) for L in layers}; zpos = {L: st[L]["z_mm"] for L in layers}
    res_all = {}
    nets = sorted(D.power) + sorted(D.ret)
    if "net" in opt: nets = [n for n in nets if opt["net"] in n]
    for net in nets:
        r = score_net(D, Z, S, V, net, res, layers, rs, zpos, acc)
        if r is None: continue
        res_all[net] = r
        print(f"{net}: from {r.get('source')} worst drop {r.get('worst_drop_mV')} mV, loss {r.get('loss_W')} W, open {r.get('open')}, "
              f"peak {max([v['A_per_mm'] for v in r.get('peak_A_per_mm', {}).values()] or [0])} A/mm, top via {r['top_vias'][0]['A'] if r.get('top_vias') else '-'} A ({r.get('seconds')} s)", flush=True)
        if outf: json.dump(res_all, open(outf, "w"), indent=1)
    if acc is not None: np.savez(opt["lossmap"], loss=acc[0], x0=acc[1], y0=acc[2], step=acc[3]); print(f"copper loss map {acc[0].sum():.2f} W -> {opt['lossmap']}")
