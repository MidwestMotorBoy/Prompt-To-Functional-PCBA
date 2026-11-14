import json, sys, math
sys.path.insert(0, "/home/claude/work/team/w1"); from metrics import pads_at
d = json.load(open(sys.argv[1])); P = json.load(open(sys.argv[2])); it = json.load(open("/home/claude/work/anch/intent_pc.json"))
fill = {r for v in json.load(open("/home/claude/work/hp/q7s2_fz_clusters.json")).values() for r in v}; P = {r: v for r, v in P.items() if r in fill}
pads = pads_at(d, P); num = {}
for p, q in zip(pads, d["pads"]): num.setdefault(p["ref"], []).append((q["num"], p["x"], p["y"]))
tot = 0; rows = []
for st in it["near"]:
    A = [(x, y) for n, x, y in num.get(st["part"], []) if "pad" not in st or f"{st['part']}.{n}" == st["pad"]]
    B = [(x, y) for t in st["to"] for n, x, y in num.get(t.split(".")[0], []) if t == t.split(".")[0] or t == f"{t.split('.')[0]}.{n}"]
    if not A or not B: continue
    dd = min(math.hypot(a[0] - b[0], a[1] - b[1]) for a in A for b in B); ex = max(0, dd - st["max_mm"]) * st.get("weight", 1); tot += ex
    if ex > 0.05: rows.append((round(ex, 1), st["part"], st["to"][0], st["max_mm"], round(dd, 1), st["part"] in fill))
print("intent excess", round(tot, 1)); [print(r) for r in sorted(rows, reverse=True)[:25]]
