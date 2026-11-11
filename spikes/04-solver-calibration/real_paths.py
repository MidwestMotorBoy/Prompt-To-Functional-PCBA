"""real_paths.py: the 16 power paths of tools/battery-bank/review-tools/run2.py, old rasteriser against new.
usage: PCB=<board.kicad_pcb> python3 real_paths.py"""
import os, re, sys
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../tools/battery-bank/review-tools"); sys.path.insert(0, T)
from solve import *
src = open(os.path.join(T, "run2.py")).read(); ns = {}
exec(src[src.index("box="):src.index("only=")], ns)
print("| path | old, mOhm | new, mOhm | change |\n|---|---|---|---|"); ch = []
for net, a, an, al, b, bn, bl, I in ns["cases"]:
    r = []
    for aa in (1, 8):
        B = build(net, ns["box"], 0.1, aa=aa)
        an2 = [x for x in an if any(p['num'] == x and p['net'] == net for p in REF[a]['pads'])]; bn2 = [x for x in bn if any(p['num'] == x and p['net'] == net for p in REF[b]['pads'])]
        s, k = padnodes(B, a, an2, al), padnodes(B, b, bn2, bl)
        r.append(solve(B, s, k, I)[1] * 1e3 if s and k else float("nan"))
    ch.append((r[1] / r[0] - 1) * 100)
    print(f"| {net.split('/')[-1]} {a} to {b} | {r[0]:.2f} | {r[1]:.2f} | {ch[-1]:+.1f} % |")
ch = [c for c in ch if c == c]; print(f"\nchange: {min(ch):+.1f} % to {max(ch):+.1f} %, median {sorted(ch)[len(ch) // 2]:+.1f} %")
