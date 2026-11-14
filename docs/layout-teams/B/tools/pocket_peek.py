"""pocket_peek.py <run or plan dir> [x0,y0,x1,y1]   (round-3 Port 1 helper)
Vias and tracks of the planned copper (spec.json) inside a box (default U401's north pocket 102.5,74.5,109.1,78.1),
by net, plus the planner's return pads left to the router there."""
import sys, json, os
d = sys.argv[1]; bx = [float(v) for v in (sys.argv[2] if len(sys.argv) > 2 else "102.5,74.5,109.1,78.1").split(",")]
s = json.load(open(os.path.join(d, "spec.json"))); inb = lambda x, y: bx[0] <= x <= bx[2] and bx[1] <= y <= bx[3]
for v in s["vias"]:
    if inb(v["x"], v["y"]): print("via", v["net"].split("/")[-1], v["x"], v["y"])
for t in s["tracks"]:
    if inb(*t["a"]) or inb(*t["b"]): print("track", t["layer"], t["net"].split("/")[-1], t["a"], t["b"], t["w"])
print("return pads left to router:", s["report"]["return_pads"].get("left_to_router"))
