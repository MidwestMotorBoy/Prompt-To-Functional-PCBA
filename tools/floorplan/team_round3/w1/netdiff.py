import json, sys
from collections import defaultdict
sys.path.insert(0, "/home/claude/work/team/w1"); from metrics import pads_at
def per_net(d, P):
    nets = defaultdict(list)
    for p in pads_at(d, P):
        if p["net"]: nets[p["net"]].append(p)
    return {n: (max(p["x"] for p in ps) - min(p["x"] for p in ps) + max(p["y"] for p in ps) - min(p["y"] for p in ps), len(ps), sorted({p["ref"] for p in ps})) for n, ps in nets.items() if 2 <= len(ps) < 12}
d = json.load(open(sys.argv[1])); fill = {r for v in json.load(open("/home/claude/work/hp/q7s2_fz_clusters.json")).values() for r in v}
P = {r: v for r, v in json.load(open(sys.argv[2])).items() if r in fill}
a = per_net(d, P); h = per_net(json.load(open("/home/claude/prompt-to-functional-pcba/tools/floorplan/example/monolith/board_dump.json")), {})
rows = sorted(((a[n][0] - h.get(n, (0,))[0], n, round(a[n][0], 1), round(h.get(n, (0,))[0], 1), a[n][1], [r + ("*" if r not in fill else "") for r in a[n][2]]) for n in a), reverse=True)
print("sum excess", round(sum(r[0] for r in rows))); [print(round(r[0], 1), *r[1:]) for r in rows[:int(sys.argv[3]) if len(sys.argv) > 3 else 30]]
