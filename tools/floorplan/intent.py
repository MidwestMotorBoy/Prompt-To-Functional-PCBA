"""intent.py: placement intent statements, their compiler, and the check of a placement against them.
  derive <build dir> <design dir> <out intent.json>
        writes every statement that follows by rule from what the circuit code declares (needs SYMBOL_DIRS):
        near       a decoupling capacitor at the pin it serves; hot-loop capacitors at both switch pins
        keepapart  pads of sensitive nets away from pads of switching nets
        kelvin     the sense pair of each shunt (kept for the router; not a placement check)
  validate <intent.json> <build dir>
        the compiler's first half: every part, pad and net named in the file must exist in the netlist.
        An LLM adds statements to this file by hand; this is what stops a wrong reference.
  check <intent.json> <board dump.json> [placement.json]
        measures every statement on a placed board (or on the dump's pad shapes moved to a placement) and
        prints what fails. A `near` distance is from the target pad's centre to the nearest pad edge of the part,
        so a large capacitor is not penalised for its own size; keep-apart is between pad centres.
Statements (all lists, all optional):
  {"near":      [{"part": "C206", "to": ["U204.3"], "max_mm": 2.0, "why": "serves U204.VIN"}],
   "keepapart": [{"a_nets": ["USB Port 1/SW1"], "b_nets": ["USB Port 1/FB"], "min_mm": 2.0, "why": "..."}],
   "order":     [{"path": ["J401", "Q401", "L401", "Q402"], "why": "power flows in this order"}],
   "kelvin":    [{"resistor": "R424", "pos": "net", "neg": "net"}],
   "fixed":     {"J401": [x, y, rot, "F.Cu"]},
   "lanes":     [{"name": "...", "nets": [...], "layer": "In2.Cu", "width_mm": 3}]}
The LLM never writes coordinates except for `fixed`, which comes from the mechanical drawing."""
import json, sys, re, math
from collections import defaultdict

def derive(build, design, out):
    sys.path.insert(0, design); import symlib
    d = json.load(open(f"{build}/netlist.json")); c = json.load(open(f"{build}/constraints.json"))
    def pads(spec):                       # "U204.VIN" or "L201.2" -> ["U204.3", ...]
        r, p = spec.split(".", 1); comp = d["comps"][r]; pins = symlib.pins(*comp["lib"].split(":"))
        nums = [q["num"] for q in pins if q["num"] == p] or [q["num"] for q in pins if re.sub(r"[~{}]", "", q["name"]) == p]
        return [f"{r}.{n}" for n in nums]
    it = dict(near=[], keepapart=[], order=[], kelvin=[], fixed={}, lanes=[])
    hot = {cap for h in c.get("hot_loops", {}).values() for cap in h["caps"]}
    for cap, t in sorted(c.get("serves", {}).items()):
        if cap not in hot and pads(t): it["near"].append(dict(part=cap, to=pads(t), max_mm=2.0, why=f"serves {t}"))
    for name, h in sorted(c.get("hot_loops", {}).items()):
        for i, cap in enumerate(h["caps"]):
            for sp in h["switch_pins"]:
                it["near"].append(dict(part=cap, to=pads(sp), max_mm=1.5 if i == 0 else 4.0, why=f"hot loop {name}: {'first' if i == 0 else 'bulk'} capacitor to {sp}"))
    sw = sorted(n for n, v in c["nets"].items() if v.get("kind") == "switching"); se = sorted(n for n, v in c["nets"].items() if v.get("kind") == "sensitive")
    for a in sw:
        blk = a.split("/")[0] if "/" in a else ""
        b = [n for n in se if (n.split("/")[0] if "/" in n else "") == blk]
        if b: it["keepapart"].append(dict(a_nets=[a], b_nets=b, min_mm=2.0, why="switching node away from sensitive nodes of the same block"))
    for name, k in sorted(c.get("kelvin", {}).items()): it["kelvin"].append(dict(resistor=k["resistor"], pos=k["pos"], neg=k["neg"]))
    json.dump(it, open(out, "w"), indent=1); return it

def validate(intentf, build):
    it = json.load(open(intentf)); d = json.load(open(f"{build}/netlist.json")); bad = []
    padset = {f"{r}.{p}" for nodes in d["nets"].values() for r, p in nodes} | {f"{r}.{p}" for r, p in d.get("nc", [])}
    def part(r, where):
        if r not in d["comps"]: bad.append(f"{where}: no part {r}")
    def net(n, where):
        if n not in d["nets"]: bad.append(f"{where}: no net {n}")
    for i, s in enumerate(it.get("near", [])):
        part(s["part"], f"near[{i}]")
        for t in s["to"]:
            if t not in padset and t not in d["comps"]: bad.append(f"near[{i}]: no pad or part {t}")
        if not (0 < s["max_mm"] < 100): bad.append(f"near[{i}]: max_mm {s['max_mm']}")
    for i, s in enumerate(it.get("keepapart", [])):
        for n in s["a_nets"] + s["b_nets"]: net(n, f"keepapart[{i}]")
    for i, s in enumerate(it.get("order", [])):
        for r in s["path"]: part(r, f"order[{i}]")
    for i, s in enumerate(it.get("kelvin", [])): part(s["resistor"], f"kelvin[{i}]"); net(s["pos"], f"kelvin[{i}]"); net(s["neg"], f"kelvin[{i}]")
    for r in it.get("fixed", {}): part(r, "fixed")
    for i, s in enumerate(it.get("lanes", [])):
        for n in s.get("nets", []): net(n, f"lanes[{i}]")
    return bad

def pad_table(dumpf, placef=None):
    """pad centres by "REF.pad" and by "REF", pads by net, and each part's pad boxes (for edge distances)"""
    d = json.load(open(dumpf)); pos = {f["ref"]: (f["x"], f["y"]) for f in d["fps"]}; P = json.load(open(placef)) if placef else None
    out = {}; bynet = defaultdict(list); boxes = defaultdict(list)
    for p in d["pads"]:
        x, y = p["x"], p["y"]; b = p["box"]
        if P and p["ref"] in P:
            x0, y0 = pos[p["ref"]]; px, py, a = P[p["ref"]]; q = [(x - x0, y - y0), (b[0] - x0, b[1] - y0), (b[2] - x0, b[3] - y0)]
            for _ in range(int(a) // 90 % 4): q = [(-v, u) for u, v in q]
            x, y = px + q[0][0], py + q[0][1]; b = [px + min(q[1][0], q[2][0]), py + min(q[1][1], q[2][1]), px + max(q[1][0], q[2][0]), py + max(q[1][1], q[2][1])]
        out.setdefault(f"{p['ref']}.{p['num']}", []).append((x, y)); bynet[p["net"]].append((x, y, p["ref"])); out.setdefault(p["ref"], []).append((x, y)); boxes[p["ref"]].append(b)
    return out, bynet, boxes

def check(intentf, dumpf, placef=None):
    it = json.load(open(intentf)); pt, bynet, boxes = pad_table(dumpf, placef); fails = []; n = 0
    edge = lambda bs, B: min(math.hypot(max(b[0] - q[0], 0, q[0] - b[2]), max(b[1] - q[1], 0, q[1] - b[3])) for b in bs for q in B)
    dist = lambda A, B: min(math.hypot(a[0] - b[0], a[1] - b[1]) for a in A for b in B)
    worst = []
    for s in it.get("near", []):
        n += 1; A = pt.get(s["part"]); B = [q for t in s["to"] for q in pt.get(t, [])]
        if not A or not B: fails.append(f"near: {s['part']} or its target is not on the board"); continue
        dd = edge(boxes[s["part"]], B); worst.append(dd / s["max_mm"])
        if dd > s["max_mm"]: fails.append(f"near: {s['part']} is {dd:.1f} mm from {', '.join(s['to'])} (limit {s['max_mm']} mm; {s['why']})")
    for s in it.get("keepapart", []):
        n += 1; A = [q for a in s["a_nets"] for q in bynet.get(a, [])]; B = [q for b in s["b_nets"] for q in bynet.get(b, [])]
        pairs = [(math.hypot(a[0] - b[0], a[1] - b[1]), a[2], b[2]) for a in A for b in B if a[2] != b[2]]
        if pairs and min(pairs)[0] < s["min_mm"]:
            m = min(pairs); fails.append(f"keepapart: {m[1]} on {s['a_nets'][0]} is {m[0]:.1f} mm from {m[2]} on a sensitive net (limit {s['min_mm']} mm)")
    for s in it.get("order", []):
        n += 1; c = [(sum(q[0] for q in pt[r]) / len(pt[r]), sum(q[1] for q in pt[r]) / len(pt[r])) for r in s["path"] if r in pt]
        direct = math.hypot(c[-1][0] - c[0][0], c[-1][1] - c[0][1]); walk = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(c, c[1:]))
        if direct > 0 and walk / direct > 1.5: fails.append(f"order: path {' > '.join(s['path'])} doubles back (walk {walk:.0f} mm for {direct:.0f} mm; {s['why']})")
    return n, fails, (sorted(worst)[len(worst) // 2] if worst else 0)

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "derive": it = derive(*a[1:]); print({k: len(v) for k, v in it.items()})
    elif a[0] == "validate":
        bad = validate(*a[1:]); print("\n".join(bad) or "every reference exists in the netlist"); sys.exit(1 if bad else 0)
    else:
        n, fails, med = check(*a[1:]); print("\n".join(fails)); print(f"{n - len(fails)} of {n} statements hold; median near distance is {med * 100:.0f} % of its limit"); sys.exit(1 if fails else 0)
