"""score.py <nets.txt> <name=dump.json,drc.json> ...: the same measures for every routed version of the test board.
dump.json comes from spikes/03-corridor-capacity/dump_board.py, drc.json from `kicad-cli pcb drc --severity-all`.
Only the nets listed in nets.txt (the ones the engine had to route) are counted for length, vias and plane cut."""
import json, sys, math, collections
nets = set(open(sys.argv[1]).read().split("\n")); rows = []
IGNORE = {"lib_footprint_issues", "lib_footprint_mismatch", "silk_over_copper", "silk_overlap", "text_height", "text_thickness", "silk_edge_clearance"}
for arg in sys.argv[2:]:
    name, rest = arg.split("=", 1); dump, drc = rest.split(","); d = json.load(open(dump)); r = json.load(open(drc))
    planes = [l for l in d["layers"] if "GND" in l]; L = collections.Counter(); bends = 0
    for t in d["tracks"]:
        if t["net"] in nets: L[t["l"]] += math.hypot(t["x2"] - t["x1"], t["y2"] - t["y1"])
    vias = sum(v["net"] in nets for v in d["vias"])
    viol = collections.Counter(v["type"] for v in r.get("violations", []) if v["type"] not in IGNORE)
    unc = [u for u in r.get("unconnected_items", [])]
    rows.append((name, len(unc), sum(viol.values()), dict(viol.most_common(4)), sum(L.values()), vias, sum(L[p] for p in planes), {k.split(".")[0]: round(v) for k, v in L.items()}))
print("| board | open connections | DRC violations | track, mm | vias | on a ground plane, mm | per layer, mm | violation types |\n|---|---|---|---|---|---|---|---|")
for n, u, v, vt, l, vi, pl, per in rows: print(f"| {n} | {u} | {v} | {l:.0f} | {vi} | {pl:.0f} | {per} | {vt} |")
