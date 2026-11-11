"""Rules that read the part knowledge base. Each finding names the datasheet page it rests on.

usage: kb_check.py <build dir> <kb dir> <spike 1 design dir> [--map kbmap.json]
kbmap.json: {"<symbol lib:name>": "<kb file stem>"}.
  symbol   a symbol pin whose name differs from the datasheet's name for that pin number
  ground   a pin the datasheet calls ground that is not on the ground net, or a non-ground pin tied to ground
           when the good design did not tie it (reported by the caller as new findings)
  missing  a datasheet pin the symbol does not have, or the reverse
"""
import json, os, re, sys

def norm(s): return re.sub(r"[^A-Z0-9]", "", re.sub(r"\(.*?\)", "", s.upper()).replace("̅", ""))
def same(a, b):
    a, b = norm(a), norm(b)
    return a == b or (a and b and (a in b or b in a)) or {a, b} <= {"GND", "PGND", "AGND", "VSS", "EP", "PAD", "THERMALPAD"} or {a, b} <= {"NC", "N.C.", "DNC"}
GNDS = {"GND", "PGND", "AGND", "VSS"}

def check(d, kbdir, kbmap, symlib, ground="GND"):
    out = set()
    pn = {(r, p): n for n, nodes in d["nets"].items() for r, p in nodes}
    for r, c in sorted(d["comps"].items()):
        stem = kbmap.get(c["lib"])
        if not stem or not os.path.exists(f"{kbdir}/{stem}.json"): continue
        kb = json.load(open(f"{kbdir}/{stem}.json"))["pins"]
        lib, name = c["lib"].split(":")
        sym = {}
        for p in symlib.pins(lib, name): sym.setdefault(p["num"], p["name"])
        for num, f in kb.items():
            if num not in sym: out.add(f"missing: {c['lib']} has no pin {num} ({f['name']}, p.{f['page']})"); continue
            if not same(sym[num], f["name"]):
                out.add(f"symbol: {c['lib']} pin {num} is '{sym[num]}', datasheet p.{f['page']} says '{f['name']}'")
            net = pn.get((r, num))
            if (norm(f["name"]) in GNDS or f["type"].upper() in ("GND", "GROUND", "G")) and net is not None and net != ground:
                out.add(f"ground: {r}.{num} ({f['name']}, p.{f['page']}) is on {net}")
            elif net == ground and norm(f["name"]) not in GNDS and f["type"].upper() not in ("GND", "GROUND", "G"):
                out.add(f"tied to ground: {r}.{num} ({f['name']}, p.{f['page']})")
        for num in sym:
            if num not in kb: out.add(f"missing: datasheet table has no pin {num} ({c['lib']} calls it '{sym[num]}')")
    return out

if __name__ == "__main__":
    a = sys.argv[1:]; sys.path.insert(0, a[2]); import symlib
    kbmap = json.load(open(a[a.index("--map") + 1])) if "--map" in a else {}
    for f in sorted(check(json.load(open(f"{a[0]}/netlist.json")), a[1], kbmap, symlib)): print(f)
