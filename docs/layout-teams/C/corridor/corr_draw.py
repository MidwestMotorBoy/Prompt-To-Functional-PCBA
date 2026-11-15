"""corr_draw.py <dump.json> <bodies.json> <placement.json> <corridors dbg.json> <out.png> [spec.json of the scorecard run]
Draws a placement with the corridor estimate of ccorr.py (CORR_DEBUG output): part bodies (grey, B side dashed),
corridor strips (core solid, clearance band light) and via fields per net, PD escape bands (red hatch).
With the scorecard's spec.json (the copper plan_copper.py really drew, in <outdir>/spec.json) a second panel shows
that copper on F.Cu with the estimate outlined on top, and the script prints per net:
  hit  = share of the estimated strip centre lines that lie on or within 0.5 mm of real copper of that net (F.Cu),
  cov  = share of the real F.Cu copper of that net (tree + grow + mirror) inside the estimated corridor (with clearance).
"""
import sys, json, math
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon as MPoly

def rotv(x, y, k):
    k %= 4
    return [(x, y), (-y, x), (-x, -y), (y, -x)][k]

def body_boxes(d, B, pl):
    fps = {f["ref"]: f for f in d["fps"]}; ri = {r: i for i, r in enumerate(B["refs"])}; out = []
    for r, f in fps.items():
        if r not in ri: continue
        b = B["bbx"][ri[r]]; s0 = f["side"] == "F.Cu"
        if r in pl:
            v = pl[r]; x, y, k = v[0], v[1], int(round(v[2] / 90)) % 4; s = s0 if len(v) < 4 else v[3] == "F"
            if s != s0: b = (-b[2], b[1], -b[0], b[3])
        else: x, y, k, s = f["x"], f["y"], 0, s0
        a = rotv(b[0], b[1], k); c = rotv(b[2], b[3], k)
        out.append((r, s, (x + min(a[0], c[0]), y + min(a[1], c[1]), x + max(a[0], c[0]), y + max(a[1], c[1]))))
    return out

def strip_poly(g, w):
    ax, ay, bx, by = g[:4]; dx, dy = bx - ax, by - ay; l = math.hypot(dx, dy)
    if l < 1e-6: return [(ax - w, ay - w), (ax + w, ay - w), (ax + w, ay + w), (ax - w, ay + w)]
    nx, ny = -dy / l * w, dx / l * w; ex, ey = dx / l * w, dy / l * w
    return [(ax - ex + nx, ay - ey + ny), (bx + ex + nx, by + ey + ny), (bx + ex - nx, by + ey - ny), (ax - ex - nx, ay - ey - ny)]

def main(dumpf, bodf, plf, dbgf, outf, specf=None):
    d = json.load(open(dumpf)); B = json.load(open(bodf)); pl = json.load(open(plf)); C = json.load(open(dbgf))
    nets = sorted({s["net"] for s in C["shapes"]}); cmap = plt.get_cmap("tab20")
    col = {n: cmap(i % 20) for i, n in enumerate(nets)}
    bx = d["box"]; npan = 2 if specf else 1
    fig, axs = plt.subplots(1, npan, figsize=(7.5 * npan, 12.5)); axs = np.atleast_1d(axs)
    bodies = body_boxes(d, B, pl)
    def base(ax, title):
        ax.set_xlim(bx[0] - 1, bx[2] + 1); ax.set_ylim(bx[3] + 1, bx[1] - 1); ax.set_aspect("equal"); ax.set_title(title, fontsize=9)
        ax.add_patch(Rectangle((bx[0], bx[1]), bx[2] - bx[0], bx[3] - bx[1], fill=False, lw=1, ec="k"))
        for r, s, b in bodies:
            ax.add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1], fill=False, lw=0.4, ec="0.4" if s else "0.7", ls="-" if s else "--"))
            if (b[2] - b[0]) * (b[3] - b[1]) > 6: ax.text((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, r, fontsize=4.5, ha="center", va="center", color="0.25")
    def corr(ax, fill=True):
        for s in C["shapes"]:
            c = col[s["net"]]; g = s["g"]
            if s["kind"] == "strip":
                if "F" not in s["sides"]: continue
                ax.add_patch(MPoly(strip_poly(g, g[5]), closed=True, fc=(*c[:3], 0.25) if fill else "none", ec=c, lw=0.5))
                if fill: ax.add_patch(MPoly(strip_poly(g, g[4]), closed=True, fc=(*c[:3], 0.7), ec="none"))
            elif s["kind"] == "box":
                ax.add_patch(Rectangle((g[0], g[1]), g[2] - g[0], g[3] - g[1], fc=(*c[:3], 0.5) if fill else "none", ec=c, lw=0.8, hatch="xx"))
            else:
                ax.add_patch(Rectangle((g[0], g[1]), g[2] - g[0], g[3] - g[1], fc="none", ec="r", lw=0.8, hatch="////"))
    base(axs[0], "placement + corridor estimate (F side; via fields hatched, PD escape bands red)"); corr(axs[0])
    hs = [plt.Line2D([], [], color=col[n], lw=4) for n in nets]
    axs[0].legend(hs, [n.split("/")[-1] if n.count("/") < 2 else n.split("/")[1][-6:] + " " + n.split("/")[-1] for n in nets], fontsize=5, loc="lower left", ncol=2)
    if specf:
        from shapely.geometry import Polygon, LineString
        from shapely.ops import unary_union
        S = json.load(open(specf)); real = {}
        for z in S["zones"]:
            if z["layer"] != "F.Cu" or z["net"] not in col: continue
            g = unary_union([Polygon(p["ring"], p.get("holes") or []).buffer(0) for p in z["polys"]])
            real[z["net"]] = g
            for gg in getattr(g, "geoms", [g]):
                axs[1].add_patch(MPoly(list(gg.exterior.coords), closed=True, fc=(*col[z["net"]][:3], 0.55), ec="none"))
        base(axs[1], "plan_copper.py copper on F.Cu (filled) vs estimate (outlines)"); corr(axs[1], fill=False)
        print(f"{'net':32s} {'hit':>5s} {'cov':>5s} {'est mm2':>8s} {'real mm2':>8s}")
        HT = []; CV = []
        for n in nets:
            st = [s for s in C["shapes"] if s["net"] == n and s["kind"] == "strip" and "F" in s["sides"]]
            if not st: continue
            est = unary_union([Polygon(strip_poly(s["g"], s["g"][5])) for s in st])
            lines = [LineString([(s["g"][0], s["g"][1]), (s["g"][2], s["g"][3])]) for s in st if math.hypot(s["g"][2] - s["g"][0], s["g"][3] - s["g"][1]) > 0.1]
            rg = real.get(n)
            L = sum(l.length for l in lines)
            hit = sum(l.intersection(rg.buffer(0.5)).length for l in lines) / L if rg is not None and L > 0 else 0.0
            cov = rg.intersection(est).area / rg.area if rg is not None and rg.area > 0 else 0.0
            HT.append((hit, L)); CV.append((cov, rg.area if rg is not None else 0))
            print(f"{n:32s} {hit:5.2f} {cov:5.2f} {est.area:8.1f} {rg.area if rg is not None else 0:8.1f}")
        tl = sum(l for _, l in HT); ta = sum(a for _, a in CV)
        print(f"{'ALL (length / area weighted)':32s} {sum(h * l for h, l in HT) / tl:5.2f} {sum(c * a for c, a in CV) / ta:5.2f}")
    fig.tight_layout(); fig.savefig(outf, dpi=110)

if __name__ == "__main__":
    main(*sys.argv[1:])
