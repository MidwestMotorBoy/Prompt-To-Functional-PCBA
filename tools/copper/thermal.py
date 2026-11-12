"""thermal.py <board.kicad_pcb, filled> <cu_dump.json> <constraints.json> <lossmap.npz from dc_score.py> [out.json] [--h=10] [--png=map.png]
Board temperature rise from the power copper's own loss and the parts' declared heat (constraints["heat"], written
by heat() in the circuit code), spread by the copper. For comparing layouts (tier 3: losses and spreading), not for
absolute temperatures.

Model: the board as one sheet on a 0.5 mm grid. Each cell conducts sideways through its copper (every layer, by
fill fraction and thickness, k = 385 W/m K) and its glass-epoxy (k = 0.3 W/m K, full thickness), and loses heat from
both faces to ambient with a film coefficient h (default 10 W/m2 K, still air: an assumption, the enclosure is not
modelled). Through-thickness temperature differences are ignored (a 1.6 mm board with stitching vias is close to
isothermal across its thickness compared with the sideways spread). A part's heat enters the board through its pads
on its own layer, shared by pad area. Result: the temperature rise over ambient everywhere, the highest, and per part
with declared heat the highest rise under its pads."""
import sys, os, json
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as sla
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dc_score import load_copper

K_CU, K_FR4 = 385.0, 0.3

def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
    pcb, dump, cons, lm = a[:4]; outf = a[4] if len(a) > 4 else None; h = float(opt.get("h", 10.0))
    D = json.load(open(dump)); C = json.load(open(cons)); M = np.load(lm); st = float(M["step"]); x0, y0 = float(M["x0"]), float(M["y0"])
    Hh, Ww = M["loss"].shape; Z, T, V = load_copper(pcb); fine = 5      # fill fractions from a 0.1 mm raster
    P = lambda x, y: ((x - x0) / st * fine, (y - y0) / st * fine)
    thick = {s["layer"]: s["t_mm"] for s in D["stackup"]}; board_t = sum(s["t_mm"] for s in D["stackup"]) + 1.4
    out_im = Image.new("L", (Ww * fine, Hh * fine), 0); ImageDraw.Draw(out_im).polygon([P(*q) for q in D["outline"][0]["ring"]], fill=1)
    inside = np.array(out_im, bool).reshape(Hh, fine, Ww, fine).mean(axis=(1, 3))
    gs = K_FR4 * board_t * 1e-3 * inside      # W/K per square
    for L in D["layers"]:
        im = Image.new("L", (Ww * fine, Hh * fine), 0); d = ImageDraw.Draw(im)
        for z in Z:
            if z["layer"] == L and len(z["pts"]) > 2: d.polygon([P(*q) for q in z["pts"]], fill=1)
        for t in T:
            if t["layer"] == L: d.line([P(*t["a"]), P(*t["b"])], fill=1, width=max(1, int(t["w"] / st * fine)))
        for p in D["pads"]:
            for r in p["shapes"].get(L, []): d.polygon([P(*q) for q in r["ring"]], fill=1)
        frac = np.array(im, float).reshape(Hh, fine, Ww, fine).mean(axis=(1, 3))
        gs = gs + K_CU * thick.get(L, 0.035) * 1e-3 * frac * inside
    # heat sources
    q = M["loss"].copy(); parts = {}
    for ref, hv in C.get("heat", {}).items():
        fp = next((f for f in D["fps"] if f["ref"] == ref), None)
        if fp is None: continue
        pads = [r for p in D["pads"] if p["ref"] == ref for r in p["shapes"].get(fp["layer"], [])]
        im = Image.new("L", (Ww * fine, Hh * fine), 0); d = ImageDraw.Draw(im)
        for r in pads: d.polygon([P(*qq) for qq in r["ring"]], fill=1)
        m = np.array(im, float).reshape(Hh, fine, Ww, fine).mean(axis=(1, 3))
        if m.sum() > 0: q += hv["w"] * m / m.sum(); parts[ref] = m > 0
    n = Hh * Ww; idx = np.arange(n).reshape(Hh, Ww); rows, cols, vals = [], [], []
    for (a1, b1) in ((idx[:, :-1], idx[:, 1:]), (idx[:-1, :], idx[1:, :])):
        ga, gb = gs.ravel()[a1.ravel()], gs.ravel()[b1.ravel()]; g = np.where((ga > 0) & (gb > 0), 2 * ga * gb / (ga + gb + 1e-30), 0.0)
        rows += [a1.ravel(), b1.ravel(), a1.ravel(), b1.ravel()]; cols += [b1.ravel(), a1.ravel(), a1.ravel(), b1.ravel()]; vals += [-g, -g, g, g]
    conv = 2 * h * (st * 1e-3) ** 2 * inside.ravel() + 1e-12
    G = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr() + sp.diags(conv)
    dT = sla.spsolve(G.tocsc(), q.ravel()).reshape(Hh, Ww) * (inside > 0)
    k = int(np.argmax(dT)); res = dict(h_W_per_m2K=h, heat_W=round(float(q.sum()), 2), copper_loss_W=round(float(M["loss"].sum()), 2),
                                        max_rise_K=round(float(dT.max()), 1), at=(round(x0 + (k % Ww + 0.5) * st, 1), round(y0 + (k // Ww + 0.5) * st, 1)),
                                        mean_rise_K=round(float(dT[inside > 0.5].mean()), 1), parts={r: round(float(dT[m].max()), 1) for r, m in sorted(parts.items())})
    print(json.dumps(res))
    if outf: json.dump(res, open(outf, "w"), indent=1)
    if "png" in opt:
        v = np.clip(dT / max(dT.max(), 1e-9), 0, 1); rgb = np.stack([v * 255, (1 - abs(v - 0.5) * 2) * 200, (1 - v) * 255], -1).astype(np.uint8)
        rgb[inside < 0.5] = 250; Image.fromarray(rgb).resize((Ww * 6, Hh * 6), Image.NEAREST).save(opt["png"])

if __name__ == "__main__":
    main()
