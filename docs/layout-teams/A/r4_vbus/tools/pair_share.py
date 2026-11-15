#!/usr/bin/env python3
"""pair_share.py <board.kicad_pcb> <cu.json> <constraints.json> [net-substring=VBUS]
For every power net matching the substring whose source terminal (dc_score's rule: largest-current series terminal)
has pads in more than one group of coincident pads (a USB-C connector's VBUS pin pairs): the resistance from each
pad group alone and from all groups together to every other series terminal, on the real copper (dc_score's grid
solver, 0.1 mm), and the current share of each group when all are fed at once (pad currents of the 1 V solve)."""
import sys, json
sys.path.insert(0, '/home/claude/repo/tools/copper')
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as sla
from roles import Design
from dc_score import load_copper, Grid, RHO
opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--")); a = [x for x in sys.argv[1:] if not x.startswith("--")]
pcb, dump, cons = a[:3]; sub = a[3] if len(a) > 3 else "VBUS"; RC = [float(x) * 1e-3 for x in opt.get("rc", "0,10,30").split(",")]
D = Design(dump, cons); Z, S, V = load_copper(pcb); layers = D.D["layers"]; st = {s["layer"]: s for s in D.D["stackup"]}
rs = {L: RHO / (st[L]["t_mm"] * 1e-3) for L in layers}; zpos = {L: st[L]["z_mm"] for L in layers}
out = {}
for net in sorted(n for n in D.power if sub in n):
    T = sorted([g for g in D.terminals(net) if g["kind"] == "series"], key=lambda g: (-g["current_a"], -len(g["pads"]), g["ref"]))
    src = T[0]; grp = {}
    for p in src["pads"]: grp.setdefault((round(p["x"], 2), round(p["y"], 2)), []).append(p)
    if len(grp) < 2: continue
    B = Grid(D, Z, S, V, net, 0.1, layers, rs, zpos); res = {}
    from scipy.sparse.csgraph import connected_components
    cc = connected_components(B.G, directed=False)[1]
    for g in T[1:]:
        k0 = B.nodes(g["pads"])
        if not k0: continue
        row = {}
        for name, pads in [("+".join(p["num"] for p in v), v) for v in grp.values()] + [("all", src["pads"])]:
            sn = B.nodes(pads); c0 = set(cc[sn].tolist()); k = [i for i in k0 if cc[i] in c0]     # a terminal's pads on this copper only
            if not k: row[name] = "open"; continue
            d = np.zeros(B.n); d[sn] = 1e6
            lu = sla.splu((B.G + sp.diags(d) + sp.identity(B.n) * 1e-9).tocsc())
            b = np.zeros(B.n); b[k] = 1.0 / len(k); Vv = lu.solve(b); R = float(np.mean(Vv[k]))
            row[name] = round(R * 1e3, 3) if R < 1 else "open"
            if name == "all" and R < 1:      # share: current leaving each group's pads into the source tie (1e6 S each)
                I = {nm: float(np.sum(Vv[B.nodes(v)] * 1e6)) for nm, v in [("+".join(p["num"] for p in v), v) for v in grp.values()]}
                tot = sum(I.values()) or 1; row["share"] = {nm: round(x / tot, 3) for nm, x in I.items()}
        # with the mated plug: the plug commons every contact; each pad group is fed through its contacts in parallel
        # (rc per contact, n contacts = pads in the group), so a pad-to-pad link also takes current
        gl = [("+".join(p["num"] for p in v), B.nodes(v), len(v)) for v in grp.values()]
        for rc in RC:
            if rc <= 0: continue
            n = B.n; extra = []
            rows, cols, vals = [], [], []
            for nm, cells, nc in gl:
                if not cells: continue
                gpc = (nc / rc) / len(cells)          # group conductance spread over its cells
                for c in cells: rows += [n, c, n, c]; cols += [c, n, n, c]; vals += [-gpc, -gpc, gpc, gpc]
            G2 = sp.csr_matrix(sp.block_diag([B.G, sp.csr_matrix((1, 1))])) + sp.coo_matrix((vals, (rows, cols)), shape=(n + 1, n + 1)).tocsr()
            d = np.zeros(n + 1); d[n] = 1e6
            lu = sla.splu((G2 + sp.diags(d) + sp.identity(n + 1) * 1e-9).tocsc())
            c0 = set(); [c0.update(cc[cells].tolist()) for _, cells, _ in gl if cells]
            k = [i for i in k0 if cc[i] in c0]
            b = np.zeros(n + 1); b[k] = 1.0 / len(k); Vv = lu.solve(b)
            I = {nm: float(sum((Vv[c] - Vv[n]) * (nc / rc) / len(cells) for c in cells)) for nm, cells, nc in gl if cells}
            tot = sum(I.values()) or 1
            row[f"with_plug_rc{rc * 1e3:g}mohm"] = dict(R_total_mohm=round(float(np.mean(Vv[k])) * 1e3, 3), share={nm: round(x / tot, 3) for nm, x in I.items()})
        res[g["ref"]] = row
    out[net] = dict(source=src["ref"], R_mohm=res)
print(json.dumps(out, indent=1))
