import sys, json, math, pickle, os
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/r4_general/copper_rules')
import plan_rules as pr
import numpy as np
from scipy import ndimage
pc = pr.pc
C = '/home/claude/repo/tools/floorplan/example/monolith/constraints.json'
cfg = pr.load_cfg(None, {"pinesc": "0"})
P = pr.RulePlanner(sys.argv[1], C, None, cfg=cfg); P.run()
pe = pr.PinEscape(P, 1, dict(pr.PinEscape.params))
RES = pc.RES
from shapely.geometry import LineString
for R, t, ST in ((3.0, 0.1, 1), (3.0, 0.05, 0), (3.0, 0.05, 1), (3.0, 0.0, 0), (3.0, 0.0, 1)):
    out = {}
    for ref, ps in sorted(P.d.by_ref.items()):
        if not P.is_class(ref, "ic"): continue
        for L in P.outer:
            for p, g, (cx, cy), d in pe.candidates(ref, L, ps):
                rm = {LL: P.room(p["net"], LL, loose=True) for LL in P.outer}
                dx, dy, ex, ey = d; strip = LineString([(cx, cy), (ex + dx * 0.9, ey + dy * 0.9)]).buffer(P.short_side(g) / 2, cap_style=2)
                free = (rm[L] >= t) | P.raster(g) | ((P.raster(strip) & (rm[L] >= -P.clr + 0.15)) if ST else False)
                via = np.ones_like(free)
                for LL in P.outer: via &= (rm[LL] >= pc.VIA_D / 2 + pc.RAST_MM) & ~P.block[LL]
                via &= ~P.novia
                seed = P.raster(g)
                lab, _ = ndimage.label(free)
                ids = np.unique(lab[seed]); ids = ids[ids > 0]
                reg = np.isin(lab, ids)
                ii, jj = np.nonzero(reg)
                xs = P.x0 + (jj + 0.5) * RES; ys = P.y0 + (ii + 0.5) * RES
                far = np.hypot(xs - cx, ys - cy).max() if len(xs) else 0
                hasvia = bool((reg & via).any())
                if far < R and not hasvia: out.setdefault(ref, []).append((p["key"], round(far, 2)))
    print("R", R, t, ST, json.dumps(out))
