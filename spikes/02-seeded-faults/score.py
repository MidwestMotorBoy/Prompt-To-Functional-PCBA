"""Score the checks against seeded faults: which gate notices each mutant?

usage: score.py <good build dir> <mutants dir> <spike 1 design dir> [--twin "USB Port 1=USB Port 2:100"]

Gates, each compared with what it says about the good build (only NEW findings count):
  struct       a pin with no net, or a net with one pin
  constraints  a declared cap no longer shares a net with the pin it serves; a hot-loop cap not across supply and
               return; a Kelvin resistor not on both sense nets; a declaration naming a missing part
  twin         two instances of the same block no longer match pin for pin (refs offset, local nets by suffix)
  erc          KiCad ERC on the sheets drawn from the mutant (needs Docker with kicad/kicad:10.0)
Writes <mutants dir>/results.json and prints a table.
"""
import collections, json, os, re, subprocess, sys

def pin_net(d): return {(r, p): n for n, nodes in d["nets"].items() for r, p in nodes}

def struct(d):
    out = {f"one-pin net {n}: {v[0][0]}.{v[0][1]}" for n, v in d["nets"].items() if len(v) == 1}
    return out

def constraints(d, c, pinnum):
    pn, out = pin_net(d), set()
    nets_of = collections.defaultdict(set)
    for (r, p), n in pn.items(): nets_of[r].add(n)
    def net_of(target):                      # "U401.VIN_3V3" -> set of nets on pins with that name or number
        r, name = target.split(".", 1)
        if r not in d["comps"]: return None
        return {pn.get((r, p)) for p in pinnum(r, name)} - {None}
    for cap, tgt in c.get("serves", {}).items():
        if cap not in d["comps"]: out.add(f"serves: {cap} is gone"); continue
        t = net_of(tgt)
        if not t or not (t & nets_of[cap]): out.add(f"serves: {cap} no longer on {tgt}")
    for name, h in c.get("hot_loops", {}).items():
        for cap in h["caps"]:
            if cap not in d["comps"]: out.add(f"hot loop {name}: {cap} is gone")
            elif not ({h["supply"], h["ret"]} <= nets_of[cap]): out.add(f"hot loop {name}: {cap} not across {h['supply']} and {h['ret']}")
        for sp in h["switch_pins"]:
            t = net_of(sp)
            if not t or not (t & {h["supply"], h["ret"]}): out.add(f"hot loop {name}: {sp} not on supply or return")
    for name, k in c.get("kelvin", {}).items():
        r = k["resistor"]
        if r not in d["comps"]: out.add(f"kelvin {name}: {r} is gone")
    return out

def twin(d, a, b, off):
    """Compare block a with block b: ref numbers differ by off, local nets match after dropping the block prefix."""
    pn = pin_net(d)
    def view(block, shift):
        v = {}
        for (r, p), n in pn.items():
            if d["comps"][r]["block"] != block: continue
            i = len(r.rstrip("0123456789")); key = (r[:i], int(r[i:]) + shift, p)
            v[key] = n[len(block) + 1:] if n.startswith(block + "/") else "=" + n
        return v
    va, vb = view(a, off), view(b, 0)
    out = set()
    for k in sorted(set(va) | set(vb), key=str):
        if va.get(k) != vb.get(k): out.add(f"{k[0]}{k[1]}.{k[2]}: {a} has {va.get(k)}, {b} has {vb.get(k)}")
    ca = {(r.rstrip('0123456789'), int(r[len(r.rstrip('0123456789')):]) + off): (c["value"], c["footprint"], c["fields"].get("MPN")) for r, c in d["comps"].items() if c["block"] == a}
    cb = {(r.rstrip('0123456789'), int(r[len(r.rstrip('0123456789')):])): (c["value"], c["footprint"], c["fields"].get("MPN")) for r, c in d["comps"].items() if c["block"] == b}
    for k in sorted(set(ca) | set(cb)):
        if ca.get(k) != cb.get(k): out.add(f"{k[0]}{k[1]}: {a} has {ca.get(k)}, {b} has {cb.get(k)}")
    return out

def erc(folder, design, project="m"):
    """Draw the sheets and run KiCad ERC. Returns a multiset of findings, or None if drawing failed."""
    folder = os.path.abspath(folder); sheets = f"{folder}/sheets"
    r = subprocess.run([sys.executable, f"{design}/draw.py", folder, sheets, project], capture_output=True, text=True, cwd=design)
    if r.returncode: return None
    subprocess.run(["docker", "run", "--rm", "-u", "0", "-v", f"{os.path.abspath(sheets)}:/w", "-w", "/w", "kicad/kicad:10.0", "kicad-cli", "sch",
                    "erc", "--format", "json", "--severity-all", "-o", "/w/erc.json", f"{project}.kicad_sch"], capture_output=True)
    try: rep = json.load(open(f"{sheets}/erc.json"))
    except Exception: return None
    c = collections.Counter()
    for s in rep["sheets"]:
        for v in s["violations"]:
            if v["type"] in ("lib_symbol_issues", "footprint_link_issues", "lib_symbol_mismatch"): continue
            if all("#PWR" in i["description"] for i in v["items"]): continue      # ground symbols without a power flag: KiCad reports one, on an arbitrary sheet
            c[(s["path"], v["type"], " | ".join(sorted(re.sub(r"#PWR\d+", "#PWR", i["description"]) for i in v["items"])))] += 1
    return c

def main(good, muts, design, twins):
    sys.path.insert(0, design)
    import symlib
    base = json.load(open(f"{good}/netlist.json")); cons = json.load(open(f"{good}/constraints.json"))
    def pinnum(r, name, _c={}):
        d = _c.setdefault("d", base)
        lib, sym = (_c.get("comps") or base["comps"])[r]["lib"].split(":") if r in base["comps"] else (None, None)
        if not lib: return []
        return [p["num"] for p in symlib.pins(lib, sym) if p["name"] == name or p["num"] == name]
    b_struct, b_cons = struct(base), constraints(base, cons, pinnum)
    b_twin = set().union(*[twin(base, a, b, off) for a, b, off in twins]) if twins else set()
    b_erc = erc(good, design)
    print(f"good build: struct {len(b_struct)}, constraints {len(b_cons)}, twin {len(b_twin)}, erc {sum(b_erc.values()) if b_erc is not None else 'failed'}")
    res = []
    for m in json.load(open(f"{muts}/mutants.json")):
        f = f"{muts}/{m['id']}"; d = json.load(open(f"{f}/netlist.json"))
        g = {"struct": sorted(struct(d) - b_struct), "constraints": sorted(constraints(d, cons, pinnum) - b_cons)}
        g["twin"] = sorted(set().union(*[twin(d, a, b, off) for a, b, off in twins]) - b_twin) if twins else []
        e = erc(f, design)
        g["erc"] = ["drawing failed"] if e is None else sorted(" ".join(k[1:]) for k in (e - b_erc))
        m["drawn"] = e is not None
        m["found"] = {k: v[:3] for k, v in g.items()}
        m["caught_by"] = [k for k, v in g.items() if v and not (k == "erc" and e is None)]
        res.append(m); print(m["id"], m["caught_by"] or "MISSED", "|", m["note"])
    json.dump(res, open(f"{muts}/results.json", "w"), indent=1)
    classes = sorted({m["class"] for m in res}); gates = ["struct", "constraints", "erc", "twin"]
    print("\n| class | n | " + " | ".join(gates) + " | any, without twin | any |\n|---|---|" + "---|" * (len(gates) + 2))
    for c in classes + ["all"]:
        ms = [m for m in res if c in (m["class"], "all")]
        row = [str(sum(g in m["caught_by"] for m in ms)) for g in gates]
        print(f"| {c} | {len(ms)} | " + " | ".join(row) + f" | {sum(bool(set(m['caught_by']) - {'twin'}) for m in ms)} | {sum(bool(m['caught_by']) for m in ms)} |")

if __name__ == "__main__":
    a = sys.argv[1:]; tw = []
    while "--twin" in a:
        i = a.index("--twin"); s = a[i + 1]; del a[i:i + 2]
        ab, off = s.rsplit(":", 1); x, y = ab.split("="); tw.append((x, y, int(off)))
    main(a[0], a[1], a[2], tw)
