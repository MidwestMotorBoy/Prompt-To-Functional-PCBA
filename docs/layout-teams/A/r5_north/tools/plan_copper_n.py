#!/usr/bin/env python3
"""plan_copper_n.py: team A r5_north planner = r4_bcu planner B (all its options, imported unchanged) + small
north-row rules, each behind its own option (0 = off; with no n option the output is identical to plan_copper_b.py).
Same arguments as tools/copper/plan_copper.py.

  --gatevia=1   (rule q3 of r4_port1/tools/plan_copper_q.py, ported onto planner B): the escape strip + via site that
                planner A reserves for a discrete FET's gate pin sealed in its hot-loop hull (--sealed) is drawn as
                copper: a track of the gate net from the pin to the site and a through via there. HG1 Q401.1 -> R444
                failed on every full route of the r4_bcu k1 board ("no way": the Kelvin pair ACP_F, routed first,
                takes the free site on In2). Unlike q3, a site within via radius + 0.2 mm of another net's pad on any
                layer is skipped (with Q402 at rot 90 the LG2 site lands on the bottom-side cap C421's pad: 4 DRC errors).
  --gatevia_q=1 only Q-ref pads (default 1, as r4_port1); 0 also draws them for sealed resistor pads (R454).
"""
import sys, os, json, math
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, '/home/claude/repo/tools/copper')
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/stagepwr/tools')
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/portcu/tools')
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/r4_bcu/tools')
import plan_copper as pc
from shapely.geometry import Point
import plan_copper_b as pb

OPTN = dict(gatevia=0, gatevia_q=1)


class PlannerN(pb.PlannerB):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        if OPTN["gatevia"]: self.gate_vias()

    def gate_vias(self):
        rep = []
        for e in self.report.get("gate_escapes", []):
            ref, num = e["pad"].split(".", 1)
            if OPTN["gatevia_q"] and not ref.startswith("Q"): continue
            p = next((q for q in self.d.by_ref[ref] if q["num"] == num), None)
            if p is None: continue
            L = self.d.fp[ref]["layer"]; g = self.d.pad_poly(p, L); a0, b0, a1, b1 = g.bounds; cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
            dx, dy = e["dir"]; ln = e["len_mm"]
            ex = a0 if dx < 0 else a1 if dx > 0 else cx; ey = b0 if dy < 0 else b1 if dy > 0 else cy
            vx, vy = round(ex + ln * dx, 3), round(ey + ln * dy, 3)
            if any(math.hypot(v["x"] - vx, v["y"] - vy) < 0.75 for v in self.vias): continue
            pt = Point(vx, vy)          # r5_north: never against another net's pad on any layer (LG2's site sits on C421's B.Cu pad)
            if any(q["net"] != p["net"] and g2.distance(pt) < pc.VIA_D / 2 + 0.2 for LL in self.padpoly for q, g2 in self.padpoly[LL]):
                rep.append([e["pad"], "skipped: pad clash"]); continue
            w = min(0.25, self._short_side(g))
            self.tracks.append(dict(net=p["net"], layer=L, a=(round(cx, 4), round(cy, 4)), b=(vx, vy), w=w))
            self.vias.append(dict(net=p["net"], x=vx, y=vy, size=pc.VIA_D, drill=pc.VIA_DRILL))
            rep.append([e["pad"], vx, vy])
        self.report.setdefault("r5_north", {})["gate_vias"] = rep


def main():
    keep = []
    for x in sys.argv[1:]:
        k = x[2:].split("=", 1)[0] if x.startswith("--") else None
        if k in OPTN: OPTN[k] = type(OPTN[k])(float(x.split("=", 1)[1]))
        else: keep.append(x)
    sys.argv[1:] = keep
    print("r5_north options", json.dumps(OPTN))
    orig = pb.PlannerB
    pb.PlannerB = PlannerN          # pb.main() instantiates the module-level PlannerB
    try: pb.main()
    finally: pb.PlannerB = orig
    # report line for the n rules (pb.main printed the r4_bcu / portcu ones)


if __name__ == "__main__":
    main()
