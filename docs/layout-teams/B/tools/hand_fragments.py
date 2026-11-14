"""hand_fragments.py <out dir> : the hand placement (tools/score/template/board.kicad_pcb, same as board_dump.json) written
as team fragments <out dir>/port1.json, port2.json, pack.json, every movable part at turn 0 on its template side.
The reference for round-trip tests and the usual --base for a section worker who replaces one section at a time."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blib import Board, GROUPS
B = Board(); out = sys.argv[1]; os.makedirs(out, exist_ok=True)
for g in GROUPS:
    F = {r: [B.parts[r]["x0"], B.parts[r]["y0"], 0, B.parts[r]["side"]] for r in sorted(B.movable) if B.group_of[r] == g}
    json.dump(F, open(os.path.join(out, g + ".json"), "w"), indent=0)
    print(g, len(F))
