"""stage_bench.py <clusters.json> <board dump.json> <constraints.json> <out placement.json>
A placement that holds only the power stages: each hot loop's switch part and capacitors where their cluster puts
them (the cluster's first part at its position on the dump board), every other movable part parked 400 mm to the
right. Apply it, lay the rule copper and score the loops (apply_placement.py, stage_copper.py, hot_score.py,
power_gate.py) to judge the section placer's stage shapes in minutes, without a full placement run."""
import sys, json
cl, dump, cons, outf = sys.argv[1:5]; CL = json.load(open(cl)); d = json.load(open(dump)); C = json.load(open(cons))
pos = {f["ref"]: (f["x"], f["y"]) for f in d["fps"]}; stage = {r for h in C["hot_loops"].values() for r in [h["switch_pins"][0].split(".")[0]] + h["caps"]}
fixed = {r for r in pos if not any(r in parts for parts in CL.values())}; out = {}
for parts in CL.values():
    a = next(iter(parts)); ax, ay = pos[a]
    for r, (x, y, rot) in parts.items(): out[r] = [round(ax + x, 3), round(ay + y, 3), rot] if r in stage else [pos[r][0] + 400.0, pos[r][1], 0]
json.dump(out, open(outf, "w")); print(f"{len([r for r in out if r in stage])} stage parts placed, {len(out) - len([r for r in out if r in stage])} parked")
