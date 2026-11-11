"""hot_convergence.py <loop index> <h mm>: one hot loop of tools/battery-bank/groundup/compare/run_hot2.py at a chosen
cell size. Run with PEEC_CENTRE=0 (old rasteriser) and 1 (new) and several h: the value both approach is the answer.
usage: PCB=<board> PEEC_CENTRE=1 python3 hot_convergence.py 4 0.2"""
import os, sys
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../tools/battery-bank/")
sys.path[:0] = [T + "groundup/compare", T + "review-tools"]
from loops import *
from caps import caps_between, dist
src = open(T + "groundup/compare/run_hot2.py").read(); ns = {}
exec(src[src.index("P1,P2="):src.index("res={}")], ns)
name, pnet, dev, dp, sp_, rad = ns["DEF"][int(sys.argv[1])]; h = float(sys.argv[2])
caps = sorted([c for c in caps_between(pnet) if dist(c, dev) < rad and REF[c]['fp'].split(':')[1] in ESL], key=lambda c: dist(c, dev))
o, m = hot_loop(name, autobox([dev] + caps, 1.5), pnet, caps, dev, dp, sp_, h=h)
print(f"{name} centre={os.environ.get('PEEC_CENTRE', '1')} h={h} nodes={o['nodes']} all caps {o['eff_all'] * 1e9:.3f} nH, best cap board-only {min(o['caps'].values()) * 1e9:.3f} nH ({o['t']:.0f} s)", flush=True)
