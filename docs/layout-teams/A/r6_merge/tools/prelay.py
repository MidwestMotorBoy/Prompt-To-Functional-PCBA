#!/usr/bin/env python3
"""prelay.py <cu.kicad_pcb> <routed.kicad_pcb> <out fix.json> --net=REGEX [--win=x0,y0,x1,y1] [--why=text]
Team A r6_merge: copy the router's tracks and vias of the chosen nets (those on the routed board that are not on the
planned board, optionally only inside a window) into a specfix file, so they are laid as fixed copper before the next
route. Use it for connections the full route silently leaves open (router.py counts an edge as routed when an escape
stub touches own-net copper; KiCad's DRC on the routed board is the judge)."""
import sys, json, re
sys.path.insert(0, "/home/claude/repo/tools/copper")
from dc_score import load_copper
a = [x for x in sys.argv[1:] if not x.startswith("--")]
o = dict((x[2:].split("=", 1) + ["1"])[:2] for x in sys.argv[1:] if x.startswith("--"))
rx = re.compile(o["net"]); win = [float(v) for v in o["win"].split(",")] if "win" in o else None
inw = lambda p: win is None or (win[0] <= p[0] <= win[2] and win[1] <= p[1] <= win[3])
_, T0, V0 = load_copper(a[0]); _, T1, V1 = load_copper(a[1])
r = lambda p: (round(p[0], 4), round(p[1], 4))
k0 = {(t["net"], t["layer"], r(t["a"]), r(t["b"])) for t in T0}; v0 = {(v["net"], round(v["x"], 4), round(v["y"], 4)) for v in V0}
tr = [{"net": t["net"], "layer": t["layer"], "a": list(r(t["a"])), "b": list(r(t["b"])), "w": t["w"]} for t in T1
      if rx.search(t["net"]) and (t["net"], t["layer"], r(t["a"]), r(t["b"])) not in k0 and inw(t["a"]) and inw(t["b"]) and r(t["a"]) != r(t["b"])]
vs = [{"net": v["net"], "x": round(v["x"], 4), "y": round(v["y"], 4), "size": v["size"], "drill": v["drill"]} for v in V1
      if rx.search(v["net"]) and (v["net"], round(v["x"], 4), round(v["y"], 4)) not in v0 and inw((v["x"], v["y"]))]
json.dump({"_why": o.get("why", ""), "tracks": tr, "vias": vs}, open(a[2], "w"), indent=1)
print("prelay: %d tracks, %d vias -> %s" % (len(tr), len(vs), a[2]))
