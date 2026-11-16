"""sheet_flow.py <board.kicad_pcb> <cu.json> <out.png> [--net=PACK_P] [--layer=In2.Cu] [--box=x0,y0,x1,y1] [--px=20]
                 [--terms=J113,R427] [--draw=hand.json]
Team B, phase 2 round 4 (EN_5V1 worker). Current density of one power net on one layer, from dc_score.py's own grid
solver: every named terminal (default: every series terminal) at its own current at once, drawn as a heat map
(white 0, dark red = the 98th percentile or more) with the copper outline, so a signal track can be put where the
sheet carries little current (a cut along the flow, or across a dead corner, costs little). --draw overlays the
tracks of a hand file (black). Prints the solved terminals."""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))
sys.path.insert(0, os.path.join(REPO, "tools/copper"))
import dc_score as dc
from roles import Design
import scipy.sparse as sp, scipy.sparse.linalg as sla
A = [a for a in sys.argv[1:] if not a.startswith("--")]
O = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--"))
pcb, cuj, out = A[:3]; NET = O.get("net", "PACK_P"); LAYER = O.get("layer", "In2.Cu"); PX = float(O.get("px", 20))
D = Design(cuj, os.path.join(REPO, "tools/floorplan/example/monolith/constraints.json")); Z, S, V = dc.load_copper(pcb)
layers = D.D["layers"]; st = {s["layer"]: s for s in D.D["stackup"]}
rs = {L: dc.RHO / (st[L]["t_mm"] * 1e-3) for L in layers}; zpos = {L: st[L]["z_mm"] for L in layers}
res = 0.1
T = [g for g in D.terminals(NET) if g["kind"] == "series"]; T.sort(key=lambda g: (-g["current_a"], -len(g["pads"]), g["ref"])); src = T[0]
B = dc.Grid(D, Z, S, V, NET, res, layers, rs, zpos); sn = B.nodes(src["pads"])
d = np.zeros(B.n); d[sn] = 1e6; lu = sla.splu((B.G + sp.diags(d) + sp.identity(B.n) * 1e-9).tocsc())
want = O.get("terms", "").split(",") if O.get("terms") else [g["ref"] for g in T[1:]]
b = np.zeros(B.n)
for g in T[1:]:
    if g["ref"] not in want: continue
    k = B.nodes(g["pads"])
    if k: b[k] += g["current_a"] / len(k); print("terminal", g["ref"], g["current_a"], "A")
Vv = lu.solve(b)
ids = B.idx[LAYER]; m = ids >= 0; VV = np.full(ids.shape, np.nan); VV[m] = Vv[ids[m]]
jx = np.zeros(ids.shape); jy = np.zeros(ids.shape)
dx = np.diff(VV, axis=1) / rs[LAYER] / res; dy = np.diff(VV, axis=0) / rs[LAYER] / res
jx[:, :-1] = np.nan_to_num(dx); jy[:-1, :] = np.nan_to_num(dy); J = np.hypot(jx, jy)       # A per mm of width
x0, y0, x1, y1 = [float(v) for v in O.get("box", "100,95,122,124").split(",")]
c0, c1 = int((x0 - B.x0) / res), int((x1 - B.x0) / res); r0, r1 = int((y0 - B.y0) / res), int((y1 - B.y0) / res)
Jc = J[max(r0, 0):r1, max(c0, 0):c1]; mc = m[max(r0, 0):r1, max(c0, 0):c1]
top = np.percentile(Jc[mc], 98) if mc.any() else 1
rgb = np.full(Jc.shape + (3,), 235, np.uint8); f = np.clip(Jc / top, 0, 1)
rgb[mc] = np.stack([255 - 75 * f[mc], 255 - 255 * f[mc], 255 - 255 * f[mc]], -1).astype(np.uint8)
im = Image.fromarray(rgb).resize((int(Jc.shape[1] * res * PX), int(Jc.shape[0] * res * PX)), Image.NEAREST); dr = ImageDraw.Draw(im)
P = lambda x, y: ((x - x0) * PX, (y - y0) * PX)
for x in range(int(x0) + 1, int(x1) + 1):
    dr.line([P(x, y0), P(x, y1)], fill=(0, 0, 0, 0) if x % 5 else (90, 90, 90), width=1) if x % 5 == 0 else None; dr.text(P(x, y0 + 0.1), str(x), fill=(0, 0, 160))
for y in range(int(y0) + 1, int(y1) + 1):
    dr.line([P(x0, y), P(x1, y)], fill=(90, 90, 90), width=1) if y % 5 == 0 else None; dr.text(P(x0 + 0.1, y), str(y), fill=(0, 0, 160))
if "draw" in O:
    H = json.load(open(O["draw"]))
    for t in H.get("tracks", []):
        if "points" in t: dr.line([P(*p) for p in t["points"]], fill=(0, 0, 0) if t["layer"] == LAYER else (0, 140, 0), width=2)
dr.text((4, im.size[1] - 14), "%s %s current density, dark = %.1f A/mm or more" % (NET, LAYER, top), fill=(0, 0, 0))
im.save(out); print(out, "98th percentile %.2f A/mm, max %.2f A/mm" % (top, Jc.max()))
