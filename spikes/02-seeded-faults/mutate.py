"""Seeded faults: make wrong copies of a known-good build so the checks can be scored by machine.

usage: mutate.py <build dir with netlist.json, constraints.json> <out dir> [--n 10] [--seed 1] [--extra faults.json]

Writes <out>/<id>/netlist.json (+ the unchanged constraints.json) per mutant, and <out>/mutants.json describing each.
Fault classes (n of each, picked with a fixed seed):
  pin_swap   two pins of one IC exchange nets (the swapped-symbol-pin bug)
  miswire    one IC pin moves to another net of the same block
  open       one IC pin is taken off its net (the deleted-wire bug)
  value      a resistor value is multiplied or divided by 10
  rating     a capacitor's voltage rating drops to 6.3 V
  remove     a resistor or capacitor is deleted
--extra adds hand-written faults: [{"id","class","note","ops":[["move",ref,pin,net] | ["swap",ref,pinA,pinB] |
  ["open",ref,pin] | ["set",ref,key,value] | ["field",ref,key,value] | ["remove",ref]]}]
"""
import copy, json, os, random, re, shutil, sys


def pin_net(d):
    return {(r, p): n for n, nodes in d["nets"].items() for r, p in nodes}

def move(d, ref, pin, net):
    for nodes in d["nets"].values():
        nodes[:] = [x for x in nodes if not (x[0] == ref and x[1] == pin)]
    if net is not None:
        d["nets"].setdefault(net, []).append([ref, pin])
    d["nets"] = {n: v for n, v in d["nets"].items() if v}

def apply(d, op):
    k = op[0]
    if k == "move": move(d, op[1], op[2], op[3])
    elif k == "open": move(d, op[1], op[2], f"open-{op[1]}-{op[2]}")
    elif k == "swap":
        pn = pin_net(d); a, b = pn[(op[1], op[2])], pn[(op[1], op[3])]
        move(d, op[1], op[2], b); move(d, op[1], op[3], a)
    elif k == "set": d["comps"][op[1]][op[2]] = op[3]
    elif k == "field": d["comps"][op[1]]["fields"][op[2]] = op[3]
    elif k == "remove":
        del d["comps"][op[1]]
        for nodes in d["nets"].values(): nodes[:] = [x for x in nodes if x[0] != op[1]]
        d["nets"] = {n: v for n, v in d["nets"].items() if v}
        d["nc"] = [x for x in d.get("nc", []) if x[0] != op[1]]
    else: raise SystemExit(f"unknown op {op}")

def scale(value, f):
    m = re.match(r"^(\d+(?:\.\d+)?)([kMR]?)(.*)$", value)
    if not m: return None
    v = float(m.group(1)) * {"": 1, "R": 1, "k": 1e3, "M": 1e6}[m.group(2)] * f
    if v <= 0: return None
    for s, u in ((1e6, "M"), (1e3, "k"), (1, "R" if m.group(2) == "R" else "")):
        if v >= s: return f"{v / s:g}{u}{m.group(3)}"
    return f"{v:g}{m.group(3)}"

def generate(d, n, rng):
    pn = pin_net(d)
    pins_of = {}
    for (r, p), net in pn.items(): pins_of.setdefault(r, []).append(p)
    ics = sorted(r for r in d["comps"] if len(pins_of.get(r, [])) >= 5)
    rs = sorted(r for r, c in d["comps"].items() if c["lib"] == "Device:R" and scale(c["value"], 10))
    cs = sorted(r for r, c in d["comps"].items() if c["lib"].startswith("Device:C") and re.search(r"\b(16|25|35|50)V", c["value"]))
    two = sorted(r for r, c in d["comps"].items() if c["lib"] in ("Device:R", "Device:C"))
    block_nets = {}
    for (r, p), net in pn.items(): block_nets.setdefault(d["comps"][r]["block"], set()).add(net)
    out = []
    def add(cls, note, ops): out.append({"id": f"{cls}-{len([m for m in out if m['class'] == cls]) + 1:02d}", "class": cls, "note": note, "ops": ops})
    seen = set()
    while len([m for m in out if m["class"] == "pin_swap"]) < n:
        r = rng.choice(ics); a, b = rng.sample(sorted(pins_of[r]), 2)
        if pn[(r, a)] == pn[(r, b)] or (r, frozenset((a, b))) in seen: continue
        seen.add((r, frozenset((a, b))))
        add("pin_swap", f"{r} pins {a} ({pn[(r, a)]}) and {b} ({pn[(r, b)]}) exchanged", [["swap", r, a, b]])
    while len([m for m in out if m["class"] == "miswire"]) < n:
        r = rng.choice(ics); a = rng.choice(sorted(pins_of[r]))
        t = rng.choice(sorted(block_nets[d["comps"][r]["block"]] - {pn[(r, a)]}))
        add("miswire", f"{r} pin {a} moved from {pn[(r, a)]} to {t}", [["move", r, a, t]])
    while len([m for m in out if m["class"] == "open"]) < n:
        r = rng.choice(ics); a = rng.choice(sorted(pins_of[r]))
        if (r, a, "o") in seen: continue
        seen.add((r, a, "o"))
        add("open", f"{r} pin {a} taken off {pn[(r, a)]}", [["open", r, a]])
    for r in rng.sample(rs, n):
        f = rng.choice((10, 0.1)); v = scale(d["comps"][r]["value"], f)
        add("value", f"{r} {d['comps'][r]['value']} becomes {v}", [["set", r, "value", v]])
    for r in rng.sample(cs, n):
        v = re.sub(r"\b(16|25|35|50)V", "6.3V", d["comps"][r]["value"])
        add("rating", f"{r} {d['comps'][r]['value']} becomes {v}", [["set", r, "value", v]])
    for r in rng.sample(two, n):
        add("remove", f"{r} ({d['comps'][r]['value']}) deleted", [["remove", r]])
    return out

def main(build, out, n=10, seed=1, extra=None):
    base = json.load(open(f"{build}/netlist.json"))
    muts = generate(base, n, random.Random(seed))
    if extra: muts = json.load(open(extra)) + muts
    os.makedirs(out, exist_ok=True)
    for m in muts:
        d = copy.deepcopy(base)
        for op in m["ops"]: apply(d, op)
        os.makedirs(f"{out}/{m['id']}", exist_ok=True)
        json.dump(d, open(f"{out}/{m['id']}/netlist.json", "w"), indent=0, sort_keys=True)
        shutil.copy(f"{build}/constraints.json", f"{out}/{m['id']}/constraints.json")
    json.dump(muts, open(f"{out}/mutants.json", "w"), indent=1)
    print(len(muts), "mutants in", out)

if __name__ == "__main__":
    a = sys.argv[1:]
    opt = lambda k, dflt: (a[a.index(k) + 1] if k in a else dflt)
    main(a[0], a[1], int(opt("--n", 10)), int(opt("--seed", 1)), opt("--extra", None))
