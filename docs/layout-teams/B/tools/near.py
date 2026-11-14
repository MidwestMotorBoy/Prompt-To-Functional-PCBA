"""near.py <fragment> x0,y0,x1,y1 [refs...]: courtyards and pads (num, net, box) of every part (fragment or fixed)
whose courtyard touches the window; with refs, only those. For placing parts by hand round a chip."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blib
B = blib.Board(); F = blib.load_placement(sys.argv[1]); w = [float(v) for v in sys.argv[2].split(",")]
only = set(sys.argv[3:])
L = blib.Layout(B)
for r, v in F.items():
    if r in B.parts and r not in B.fixed: L.put(r, v)
for r in sorted(L.placed if hasattr(L, "placed") else F):
    pass
refs = set(F) | B.fixed
for r in sorted(refs):
    if r not in B.parts: continue
    v = F.get(r)
    c, s = B.court(r, v)
    if only and r not in only: continue
    if not only and (c[2] < w[0] or c[0] > w[2] or c[3] < w[1] or c[1] > w[3]): continue
    print(f"{r} {s} at {v} court ({c[0]:.2f},{c[1]:.2f},{c[2]:.2f},{c[3]:.2f})")
    for p in B.pads(r, v):
        if not p[0]: continue
        b = p[4]; print(f"   {p[0]:>3} {p[1][-22:]:22s} ({b[0]:.2f},{b[1]:.2f},{b[2]:.2f},{b[3]:.2f}) {''.join(sorted(p[5]))}")
