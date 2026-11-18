#!/usr/bin/env python3
"""freeze_fix.py <frozen_in.json> <out.json> : team A r6_merge. Hand finish of the frozen m13e route (fixes/frozen_m13e.json,
made by prelay.py --net=. from runs/m13e) -> fixes/frozen_final.json. Every edit was checked with KiCad DRC (quick.sh):
 1. CELL_1N stubs at U101 pins 9/16/17 (0.4 mm pitch): 0.25 mm 'HighCurrent copper to small signals' rule (the routed-board
    DRC of earlier rounds ran without the .kicad_dru and never saw it): shorter / 0.15 mm stub ends.
 2. PACK_P TP106.1 + its F.Cu pour piece: via to the In2/In4 PACK_P planes.
 3. 3V3 J301.1 island: track + via to the In3 pour / In4 band; R417.2 island (hard r314 track ends on a cut-off F piece): via beside the pad + In4 track to the band.
 4. P2 CHG_INT R504.2 -> U501.18: 0.15 mm F.Cu track through the 0.45 mm gap between the SCL via and R541.2 (0.15 mm each side,
    exactly at the rule), SBU_FLT pin-19 stub straightened to x 86.5 to make room."""
import json, sys
f = json.load(open(sys.argv[1])); T = f["tracks"]; V = f["vias"]
def k(p): return (round(p[0], 3), round(p[1], 3))
def drop(net, a, b):
    n = len(T)
    T[:] = [t for t in T if not (t["net"].endswith(net) and {k(t["a"]), k(t["b"])} == {k(a), k(b)})]
    assert len(T) == n - 1, (net, a, b, n - len(T))
def add(net, layer, pts, w):
    for a, b in zip(pts, pts[1:]): T.append({"net": net, "layer": layer, "a": list(a), "b": list(b), "w": w})
def via(net, x, y): V.append({"net": net, "x": x, "y": y, "size": 0.45, "drill": 0.3})
C = "/Cells and Gauge/"
drop("CELL_1N", (95.375, 122.8745), (95.5, 122.9)); add(C + "CELL_1N", "F.Cu", [(95.375, 122.8745), (95.45, 122.89)], 0.15)
drop("BTP_INT", (97.875, 123.2245), (97.9, 122.9)); add(C + "BTP_INT", "F.Cu", [(97.875, 123.2245), (97.89, 123.15)], 0.2)
drop("CELL_1N", (98.575, 122.5245), (98.8, 122.4)); add(C + "CELL_1N", "F.Cu", [(98.575, 122.5245), (98.6, 122.48)], 0.15)
via("PACK_P", 98.7, 92.9); add("PACK_P", "F.Cu", [(100.3, 92.3), (98.7, 92.9)], 0.3)
via("3V3", 115.74, 116.62); add("3V3", "F.Cu", [(116.33, 116.27), (115.74, 116.62)], 0.2)
drop("SBU_FLT", (86.5, 82.925), (86.475, 83.2245)); drop("SBU_FLT", (86.475, 83.2245), (86.475, 83.6745)); drop("SBU_FLT", (86.475, 83.6745), (86.6, 83.93))
add("/USB Port 2/SBU_FLT", "F.Cu", [(86.5, 82.925), (86.5, 83.65), (86.6, 83.93)], 0.2)
add("/USB Port 2/CHG_INT", "F.Cu", [(86.1, 82.95), (86.175, 83.2), (86.175, 84.2), (86.12, 84.3), (86.12, 84.9), (86.03, 85.47)], 0.15)
via("3V3", 117.75, 112.85); add("3V3", "F.Cu", [(117.32, 112.85), (117.75, 112.85)], 0.2)   # R417.2 island: via beside the pad ...
add("3V3", "In4.Cu", [(117.75, 112.85), (117.75, 115.3), (117.2, 116.0), (117.0, 116.4)], 0.3)       # ... and an In4 track into the In4 3V3 band
f["_why"] += " + hand finish (tools/freeze_fix.py)"
json.dump(f, open(sys.argv[2], "w"), indent=1); print("freeze_fix:", len(T), "tracks", len(V), "vias")
