"""anchors.py <board_dump.json> [constraints.json] [--power]
The parts a person placed by hand, as anchors for the placer: every footprint whose body lies inside the board
outline box, other than the parts that are fixed anyway (prefixes J, H, TP, SW). Prints them comma-separated, to
pass to place_sections.py with the fixed prefixes (they stay exactly where the person put them; their clusters'
other parts are placed round them, pulled to their pins by the intent file's near statements).

Workflow: import the netlist into a board with the outline and the fixed parts, place only the parts that set
the power flow (connectors are already there; PD switches, power FETs, inductors, shunts, fuses, gauge), leave the
rest piled outside the outline, save, dump with dump_board.py, then
    place_sections.py <dump> <netlist> <constraints> clusters.json J,H,TP,SW,$(python3 anchors.py <dump>) <intent>
--power (with constraints.json): instead, list the parts a person should place, from the circuit code: every part
that carries a power net's current (power_chains.py) or switches a hot loop."""
import sys, os, json
FIXED = ("J", "H", "TP", "SW")
a = [x for x in sys.argv[1:] if not x.startswith("--")]; D = json.load(open(a[0])); x0, y0, x1, y1 = D["box"]
if "--power" in sys.argv:
    from power_chains import design, chains
    d, _ = design(a[0], a[1]); refs = set()
    for c in chains(d, 1.0): refs |= {c["part"], c["to"][0].split(".")[0]}
    for hl in d.C.get("hot_loops", {}).values(): refs.add(hl["switch_pins"][0].split(".")[0])
    print(",".join(sorted(r for r in refs if r.rstrip("0123456789") not in FIXED))); sys.exit()
inside = []
for f in D["fps"]:
    if f["ref"].rstrip("0123456789") in FIXED: continue
    c = f.get("court") or [f["x"], f["y"], f["x"], f["y"]]
    if x0 <= c[0] and c[2] <= x1 and y0 <= c[1] and c[3] <= y1: inside.append(f["ref"])
print(",".join(sorted(inside)))
