#!/usr/bin/env python3
"""copy_p2.py <routed.kicad_pcb> <out_fix.json> <x0,y0,x1,y1 port-2 window> <dx> <net-regex> [--clip]
Port 1's PD cluster is a +dx copy of port 2's. Takes the router's port-2 tracks and vias of the matching nets inside
the window (both ends inside), moves them by dx, renames the nets to port 1 (/USB Port 2/X -> /USB Port 1/X,
/USB Port 2/LDO_3V3 -> /P1_LDO_3V3) and writes a specfix.py fix file (fixed escape copper for port 1)."""
import sys, json, re
sys.path.insert(0, "/home/claude/repo/tools/copper")
from dc_score import load_copper
pcb, out, win, dx, rx = sys.argv[1:6]
x0, y0, x1, y1 = map(float, win.split(",")); dx = float(dx); rx = re.compile(rx)
Z, T, V = load_copper(pcb)
inw = lambda p: x0 <= p[0] <= x1 and y0 <= p[1] <= y1
def ren(n):
    if n == "/USB Port 2/LDO_3V3": return "/P1_LDO_3V3"
    return n.replace("/USB Port 2/", "/USB Port 1/")
tr, vi = [], []
for t in T:
    if rx.search(t["net"]) and inw(t["a"]) and inw(t["b"]) and t["layer"] in ("F.Cu", "In2.Cu", "In3.Cu", "B.Cu"):
        tr.append({"net": ren(t["net"]), "layer": t["layer"], "a": [round(t["a"][0] + dx, 4), t["a"][1]],
                   "b": [round(t["b"][0] + dx, 4), t["b"][1]], "w": t["w"]})
for v in V:
    if rx.search(v["net"]) and inw((v["x"], v["y"])):
        vi.append({"net": ren(v["net"]), "x": round(v["x"] + dx, 4), "y": v["y"], "size": v["size"], "drill": v.get("drill", 0.3)})
json.dump({"_why": "port-2 router copper of %s in %s copied +%.1f mm to port 1" % (rx.pattern, win, dx), "tracks": tr, "vias": vi},
          open(out, "w"), indent=1)
print("copy_p2: %d tracks, %d vias" % (len(tr), len(vi)), sorted({t["net"] for t in tr} | {v["net"] for v in vi}))
