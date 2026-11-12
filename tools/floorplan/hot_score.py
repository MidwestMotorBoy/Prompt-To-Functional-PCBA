"""PCB=<board with copper> python3 hot_score.py <constraints.json> [out.json] [loop name substring ...]
Loop inductance of every hot loop the circuit code declares, on the board's copper, with the Battery-Bank PEEC solver
(tools/battery-bank/groundup/compare). Per loop: board inductance through each declared capacitor alone (nH), and all
capacitors in parallel with their package inductance, seen from the switch. Cell 0.2 mm for small loops, 0.3 mm
for large ones (recorded per loop); compare placements loop by loop, on the same cell."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "battery-bank", "groundup", "compare"))
from loops import *
a = sys.argv[1:]; C = json.load(open(a[0])); outf = a[1] if len(a) > 1 and a[1].endswith(".json") else None; only = [x for x in a[1:] if not x.endswith(".json")]
nets = {p["net"] for d in FP for p in d["pads"]}
def netname(s): return next(n for n in nets if n == s or n.endswith("/" + s))
def pinname(p): return p["pinfn"][:-len(p["num"]) - 1] if p["num"] and p["pinfn"].endswith("_" + p["num"]) else p["pinfn"]   # pins are named "<name>_<pad>"
FAR_MM = 15.0
SMALL_MM2 = 80.0      # loops in a box up to this size are solved on a 0.2 mm cell, larger ones on 0.3 mm
res = {}
for name, hl in sorted(C["hot_loops"].items()):
    if only and not any(o in name for o in only): continue
    P = netname(hl["supply"]); G = netname(hl["ret"]); dev = hl["switch_pins"][0].split(".")[0]; fns = {s.split(".")[1] for s in hl["switch_pins"]}
    nums = {n for t in hl["switch_pins"] for n in C.get("pin_pads", {}).get(t, [])}; isw = lambda p: p["num"] in nums if nums else pinname(p) in fns
    dp = sorted({p["num"] for p in REF[dev]["pads"] if isw(p) and p["net"] == P}); sp = sorted({p["num"] for p in REF[dev]["pads"] if isw(p) and p["net"] == G})
    caps = [c for c in hl["caps"] if REF[c]["fp"].split(":")[1] in ESL]
    far = [c for c in caps if math.hypot(REF[c]["x"] - REF[dev]["x"], REF[c]["y"] - REF[dev]["y"]) > FAR_MM]; caps = [c for c in caps if c not in far]
    if caps:
        bx = autobox([dev] + caps, 1.5); cells = (0.2,) if (bx[1] - bx[0]) * (bx[3] - bx[2]) <= SMALL_MM2 else (0.3, 0.2)
        for h in cells:      # a neck of copper thinner than the cell reads as open: an open result is solved again on the finer cell before it counts
            o, m = hot_loop(name, bx, P, caps, dev, dp, sp, h=h, nnet=G); del m
            if max(o["caps"].values()) < 1e-7: break
        res[name] = dict(per_cap_nH={c: round(v * 1e9, 3) for c, v in o["caps"].items()}, all_parallel_with_esl_nH=round(o["eff_all"] * 1e9, 3), branches=o["branches"], vias=o["vias"], cell_mm=h)
    else: res[name] = dict(per_cap_nH={}, all_parallel_with_esl_nH=1e6)
    for c in far: res[name]["per_cap_nH"][c] = 1e6      # too far to be part of the loop: counted as open, and kept out of the solve (memory grows with the box squared)
    print(name, json.dumps(res[name]), flush=True)
    if outf: json.dump(res, open(outf, "w"), indent=1)
