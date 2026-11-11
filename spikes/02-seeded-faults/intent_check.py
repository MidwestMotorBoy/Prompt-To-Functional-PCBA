"""Intent checks: part ratings and expected values against what the block declared and what the datasheet says.

usage: intent_check.py check  <build dir> <limits dir> <kbmap.json> <spike 1 design dir>
       intent_check.py verify <limits dir> <datasheet dir>           every quote must be on the page it names
       intent_check.py score  <good build dir> <mutants dir> <limits dir> <kbmap.json> <spike 1 design dir>

Inputs: netlist.json; constraints.json with nets[*].max_v (highest voltage the net can reach) and expect[*]
(kernel.expect); one limits file per part, read by hand from the datasheet, each number with page and quote:
  {"part", "pdf", "abs_max": [{"pins": [...], "max_v", "page", "quote"}], "facts": {name: {"value", "page", "quote"}},
   "standoff": {part number prefix: {"max_v", "page", "quote"}}}
Rules:
  cap      a capacitor's voltage rating (the "25V" in its value) is below the max_v of a net it sits on
  absmax   an IC pin sits on a net whose max_v is above the pin's absolute maximum
  standoff a clamp's working voltage is below the max_v of a net it sits on
  expect   an expected value, computed from part values and datasheet facts, is outside its tolerance
`score` adds an "intent" gate to <mutants dir>/results.json (written by score.py) and prints the table.
"""
import glob, json, os, re, subprocess, sys

def ohms(v):
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([mRkM]?)", v)
    return float(m.group(1)) * {"": 1, "R": 1, "m": 1e-3, "k": 1e3, "M": 1e6}[m.group(2)] if m else None

def load_limits(folder):
    return {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(f"{folder}/*.json")}

def check(d, cons, limits, kbmap, symlib):
    out = set()
    vmax = {n: v["max_v"] for n, v in cons["nets"].items() if "max_v" in v}
    nets_of = {}
    for n, nodes in d["nets"].items():
        for r, p in nodes: nets_of.setdefault(r, {})[p] = n
    standoff = {k: v for L in limits.values() for k, v in L.get("standoff", {}).items()}
    for r, c in d["comps"].items():
        on = nets_of.get(r, {})
        worst = max(((vmax[n], n) for n in on.values() if n in vmax), default=None)
        if c["lib"].startswith("Device:C"):
            m = re.search(r"(\d+(?:\.\d+)?)\s*V\b", c["value"])
            if m and worst and float(m.group(1)) < worst[0]:
                out.add(f"cap: {r} is rated {m.group(1)} V, {worst[1]} reaches {worst[0]:g} V")
        for k, s in standoff.items():
            if c["value"].startswith(k) and worst and s["max_v"] < worst[0]:
                out.add(f"standoff: {r} ({k}) works to {s['max_v']} V (p.{s['page']}), {worst[1]} reaches {worst[0]:g} V")
        L = limits.get(kbmap.get(c["lib"]))
        if L and L.get("abs_max"):
            lim = {p: a for a in L["abs_max"] for p in a["pins"]}
            for pin in symlib.pins(*c["lib"].split(":")):
                a = lim.get(re.sub(r"[~{}]", "", pin["name"])); n = on.get(pin["num"])
                if a and n in vmax and vmax[n] > a["max_v"]:
                    out.add(f"absmax: {r}.{pin['name']} is limited to {a['max_v']} V (p.{a['page']}), {n} reaches {vmax[n]:g} V")
    for name, e in cons.get("expect", {}).items():
        env, missing = {}, None
        for k, b in e["bind"].items():
            if b in d["comps"]: env[k] = ohms(d["comps"][b]["value"])
            elif "." in b and b.split(".")[0] in limits: env[k] = limits[b.split(".")[0]]["facts"][b.split(".")[1]]["value"]
            else: missing = b
            if env.get(k) is None: missing = b
        if missing: out.add(f"expect: {name} cannot be computed, {missing} is missing"); continue
        try: v = eval(e["expr"], {"__builtins__": {}}, env)
        except ZeroDivisionError: v = float("inf")
        if abs(v - e["target"]) > e["tol"] * e["target"]:
            out.add(f"expect: {name} is {v:.4g} {e['unit']}, meant to be {e['target']:g} {e['unit']} within {e['tol'] * 100:g} %")
    return out

def verify(limits, sheets):
    bad = n = 0
    for part, L in sorted(limits.items()):
        text = subprocess.run(["pdftotext", "-layout", f"{sheets}/{L['pdf']}", "-"], capture_output=True, text=True).stdout.split("\f")
        pages = [" ".join(p.split()) for p in text]
        items = [(", ".join(a["pins"][:3]), a, a["max_v"]) for a in L.get("abs_max", [])]
        items += [(k, f, f["value"]) for k, f in L.get("facts", {}).items()] + [(k, s, s["max_v"]) for k, s in L.get("standoff", {}).items()]
        for label, f, value in items:
            n += 1
            ok = f["page"] <= len(pages) and f["quote"] in pages[f["page"] - 1] and any(float(x) == value for x in re.findall(r"\d+(?:\.\d+)?", f["quote"]))
            if not ok: bad += 1; print(f"NOT FOUND  {part} {label}: p.{f['page']} '{f['quote']}'")
    print(f"{n - bad} of {n} facts found on the page they name")
    return bad

def run(build, limits, kbmap, design, cons=None):
    sys.path.insert(0, design); import symlib
    d = json.load(open(f"{build}/netlist.json")); cons = cons or json.load(open(f"{build}/constraints.json"))
    return check(d, cons, limits, kbmap, symlib)

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "verify": sys.exit(1 if verify(load_limits(a[1]), a[2]) else 0)
    if a[0] == "check":
        f = sorted(run(a[1], load_limits(a[2]), json.load(open(a[3])), a[4]))
        print("\n".join(f) or "no findings"); sys.exit(1 if f else 0)
    good, muts, limits, kbmap, design = a[1], a[2], load_limits(a[3]), json.load(open(a[4])), a[5]
    cons = json.load(open(f"{good}/constraints.json")); base = run(good, limits, kbmap, design, cons)
    print("good build:", len(base), "findings"); res = json.load(open(f"{muts}/results.json"))
    for m in res:
        f = sorted(run(f"{muts}/{m['id']}", limits, kbmap, design, cons) - base)
        m["found"]["intent"] = f[:3]; m["caught_by"] = [g for g in m["caught_by"] if g != "intent"] + (["intent"] if f else [])
        print(m["id"], "|", m["note"], "|", f[0] if f else "-")
    json.dump(res, open(f"{muts}/results.json", "w"), indent=1)
    gates = sorted({g for m in res for g in m["found"]} - {"twin"})
    print("\n| class | n | " + " | ".join(gates) + " | any, without intent | any |\n|---|---|" + "---|" * (len(gates) + 2))
    for c in sorted({m["class"] for m in res}) + ["all"]:
        ms = [m for m in res if c in (m["class"], "all")]; cb = lambda m: set(m["caught_by"]) - {"twin"}
        print(f"| {c} | {len(ms)} | " + " | ".join(str(sum(g in cb(m) for m in ms)) for g in gates)
              + f" | {sum(bool(cb(m) - {'intent'}) for m in ms)} | {sum(bool(cb(m)) for m in ms)} |")
