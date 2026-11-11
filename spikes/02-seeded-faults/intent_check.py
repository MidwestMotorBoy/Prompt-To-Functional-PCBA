"""Intent checks: part ratings and expected values against what the block declared and what the datasheet says.

usage: intent_check.py check  <build dir> <limits dir> <kbmap.json> <spike 1 design dir>
       intent_check.py verify <limits dir> <datasheet dir>           every quote must be on the page it names
       intent_check.py score  <good build dir> <mutants dir> <limits dir> <kbmap.json> <spike 1 design dir>

Inputs: netlist.json; constraints.json with nets[*].max_v (highest voltage the net can reach) and expect[*]
(kernel.expect); one limits file per part, read by hand from the datasheet, each number with page and quote:
  {"part", "pdf", "abs_max": [{"pins": [...], "max_v", "page", "quote"}], "facts": {name: {"value", "page", "quote"}},
   "standoff": {part number prefix: {"max_v", "page", "quote"}}}
  or {"part", "waiver": "why this part needs no datasheet facts"}, which is printed on every run.
Rules:
  cap      a capacitor's voltage rating (the "25V" in its value) is below the max_v of a net it sits on
  absmax   an IC pin sits on a net whose max_v is above the pin's absolute maximum
  standoff a clamp's working voltage is below the max_v of a net it sits on
  expect   an expected value, computed from part values and datasheet facts, is outside its tolerance, or the
           pin it is meant for (at="U404.FB") no longer touches any of the parts that set it
  ground   a pin the symbol names GND, PGND, AGND or VSS is not on a 0 V net; a supply pin is on a 0 V net
  stage    a declared hot loop's high-side pins are not all on its supply, or its low-side pins not all on its return
  tested   a pin's net can reach (max_v) more than a tested tolerance row, such as a hot-plug short rating, even if the absolute maximum is higher
  recmax   a pin's net runs (normal_v, else max_v) above the part's recommended operating maximum
  clamp    a clamp's clamping voltage is above the absolute maximum of a pin on the net it protects
  bus      a net joins a data pin and a clock pin (names ending SDA, SCL), or such a pin meets no other of its kind
  exclusive  the node at an expectation's pin carries a part that is neither bound to it nor the pin's own part
  A finding whose text starts with a prefix given to kernel.waive(prefix, reason) is printed as waived and does not
  stop the build.
  nofacts  (check only) a part with three or more pins that has no limits file
`score` adds an "intent" gate to <mutants dir>/results.json (written by score.py) and prints the table.
"""
import glob, json, os, re, subprocess, sys

def ohms(v):
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([mRkM]?)", v)
    return float(m.group(1)) * {"": 1, "R": 1, "m": 1e-3, "k": 1e3, "M": 1e6}[m.group(2)] if m else None

GNDS = {"GND", "PGND", "AGND", "VSS"}

def nofacts(d, limits, kbmap, symlib):
    libs = {c["lib"] for c in d["comps"].values() if not c["lib"].startswith("Device:")}
    return sorted(l for l in libs if len(symlib.pins(*l.split(":"))) >= 3 and kbmap.get(l) not in limits)

def load_limits(folder):
    return {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(f"{folder}/*.json")}

def check(d, cons, limits, kbmap, symlib):
    out = set()
    vmax = {n: v["max_v"] for n, v in cons["nets"].items() if "max_v" in v}
    nets_of = {}
    for n, nodes in d["nets"].items():
        for r, p in nodes: nets_of.setdefault(r, {})[p] = n
    vnorm = {n: v.get("normal_v", v["max_v"]) for n, v in cons["nets"].items() if "max_v" in v}; across = cons.get("across", {})
    absmax_on = {}                            # net -> [(limit, "U401.VBUS", page)] for the clamp rule
    for r, c in d["comps"].items():
        L = limits.get(kbmap.get(c["lib"]))
        if not (L and L.get("abs_max")): continue
        lim = {p: a for a in L["abs_max"] for p in a["pins"]}
        for pin in symlib.pins(*c["lib"].split(":")):
            a = lim.get(re.sub(r"[~{}]", "", pin["name"])); n = nets_of.get(r, {}).get(pin["num"])
            if a and n: absmax_on.setdefault(n, []).append((a["max_v"], f"{r}.{pin['name']}", a["page"]))
    standoff = {k: v for L in limits.values() for k, v in L.get("standoff", {}).items()}
    for r, c in d["comps"].items():
        on = nets_of.get(r, {})
        worst = max(((vmax[n], n) for n in on.values() if n in vmax), default=None)
        if c["lib"].startswith("Device:C"):
            m = re.search(r"(\d+(?:\.\d+)?)\s*V\b", c["value"])
            if m and r in across:
                if float(m.group(1)) < across[r]: out.add(f"cap: {r} is rated {m.group(1)} V, declared to see {across[r]:g} V across it")
            elif m and worst and float(m.group(1)) < worst[0]:
                out.add(f"cap: {r} is rated {m.group(1)} V, {worst[1]} reaches {worst[0]:g} V")
        for k, s in standoff.items():
            if c["value"].startswith(k) and worst and s["max_v"] < worst[0]:
                out.add(f"standoff: {r} ({k}) works to {s['max_v']} V (p.{s['page']}), {worst[1]} reaches {worst[0]:g} V")
            if c["value"].startswith(k) and "clamp_v" in s:
                for n in on.values():
                    for lim_v, who, pg in absmax_on.get(n, []):
                        if vmax.get(n) and s["clamp_v"] > lim_v: out.add(f"clamp: {r} ({k}) clamps at {s['clamp_v']} V, {who} on {n} is limited to {lim_v} V (p.{pg})")
        L = limits.get(kbmap.get(c["lib"]))
        if L and L.get("abs_max"):
            lim = {p: a for a in L["abs_max"] for p in a["pins"]}
            for pin in symlib.pins(*c["lib"].split(":")):
                a = lim.get(re.sub(r"[~{}]", "", pin["name"])); n = on.get(pin["num"])
                if a and n in vmax and vmax[n] > a["max_v"]:
                    out.add(f"absmax: {r}.{pin['name']} is limited to {a['max_v']} V (p.{a['page']}), {n} reaches {vmax[n]:g} V")
        if L and L.get("rec_max"):
            lim = {p: a for a in L["rec_max"] for p in a["pins"]}
            for pin in symlib.pins(*c["lib"].split(":")):
                a = lim.get(re.sub(r"[~{}]", "", pin["name"])); n = on.get(pin["num"])
                if a and n in vnorm and vnorm[n] > a["max_v"]:
                    out.add(f"recmax: {r}.{pin['name']} is specified to work up to {a['max_v']} V (p.{a['page']}), {n} runs at {vnorm[n]:g} V")
        if L and L.get("tested_max"):
            lim = {p: a for a in L["tested_max"] for p in a["pins"]}
            for pin in symlib.pins(*c["lib"].split(":")):
                a = lim.get(re.sub(r"[~{}]", "", pin["name"])); n = on.get(pin["num"])
                if a and n in vmax and vmax[n] > a["max_v"]:
                    out.add(f"tested: {r}.{pin['name']} is only tested to survive {a['max_v']} V ({a.get('what', 'tested tolerance')}, p.{a['page']}), {n} reaches {vmax[n]:g} V")
        for pin in symlib.pins(*c["lib"].split(":")):
            n = on.get(pin["num"])
            if n is None: continue
            if re.sub(r"[~{}]", "", pin["name"]) in GNDS:
                if vmax.get(n) != 0: out.add(f"ground: {r}.{pin['num']} ({pin['name']}) is on {n}")
            elif pin["type"] == "power_in" and pin["name"] not in ("PAD", "EP") and vmax.get(n) == 0:
                out.add(f"ground: supply pin {r}.{pin['num']} ({pin['name']}) is on {n}")
    def pin_nets(target):
        r, name = target.split(".", 1)
        if r not in d["comps"]: return set()
        return {nets_of.get(r, {}).get(p["num"]) for p in symlib.pins(*d["comps"][r]["lib"].split(":"))
                if name in (p["name"], re.sub(r"[~{}]", "", p["name"]), p["num"])}
    for name, h in cons.get("hot_loops", {}).items():
        for target, want in zip(h["switch_pins"], (h["supply"], h["ret"])):
            got = pin_nets(target)
            if got != {want}: out.add(f"stage: {name}: {target} should be on {want} only, is on {', '.join(sorted(str(g) for g in got))}")
    bus = {}                                  # net -> {"SDA": [pins], "SCL": [pins]}, from symbol pin names
    for r, c in d["comps"].items():
        for pin in symlib.pins(*c["lib"].split(":")):
            m = re.search(r"(?:^|_)(SDA|SCL)$", pin["name"]); n = nets_of.get(r, {}).get(pin["num"])
            if m and n: bus.setdefault(n, {}).setdefault(m.group(1), []).append(f"{r}.{pin['name']}")
    for n, b in bus.items():
        if len(b) == 2: out.add(f"bus: {n} joins data and clock pins: {', '.join(b['SDA'] + b['SCL'])}")
        for kind, pins in b.items():
            if len(pins) == 1: out.add(f"bus: {pins[0]} on {n} meets no other {kind} pin")
    for name, e in cons.get("expect", {}).items():
        if e.get("at"):
            at_ref = e["at"].split(".")[0]
            touching = {r for n in pin_nets(e["at"]) for r, p in d["nets"].get(n, [])}
            if not (touching & set(e["bind"].values())): out.add(f"expect: {name}: {e['at']} no longer touches the parts that set it")
            extra = touching - set(e["bind"].values()) - {at_ref}
            if extra: out.add(f"exclusive: {name}: the node at {e['at']} also carries {', '.join(sorted(extra))}")
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
    check.waived = {x: r for x in out for p, r in cons.get("waive", {}).items() if x.startswith(p)}   # kernel.waive()
    return out - set(check.waived)

def verify(limits, sheets):
    bad = n = 0
    for part, L in sorted(limits.items()):
        if "waiver" in L:
            print(f"WAIVER  {part}: {L['waiver']}")
            if "pdf" not in L: continue
        text = subprocess.run(["pdftotext", "-layout", f"{sheets}/{L['pdf']}", "-"], capture_output=True, text=True).stdout.split("\f")
        pages = [" ".join(p.split()) for p in text]
        items = [(", ".join(a["pins"][:3]), a, a["max_v"]) for a in L.get("abs_max", []) + L.get("rec_max", []) + L.get("tested_max", [])]
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
        print("\n".join(f) or "no findings")
        for x, r in sorted(check.waived.items()): print(f"waived: {x} | reason: {r}")
        import symlib
        nf = nofacts(json.load(open(f"{a[1]}/netlist.json")), load_limits(a[2]), json.load(open(a[3])), symlib)
        for l in nf: print(f"nofacts: {l} has no limits file")
        for p, L in sorted(load_limits(a[2]).items()):
            if "waiver" in L: print(f"waiver: {p}: {L['waiver']}")
        sys.exit(1 if f or nf else 0)
    good, muts, limits, kbmap, design = a[1], a[2], load_limits(a[3]), json.load(open(a[4])), a[5]
    cons = json.load(open(f"{good}/constraints.json")); base = run(good, limits, kbmap, design, cons)
    print("good build:", len(base), "findings"); res = json.load(open(f"{muts}/results.json"))
    for m in res:
        f = sorted(run(f"{muts}/{m['id']}", limits, kbmap, design, cons) - base)
        m.setdefault("found", {}); m.setdefault("caught_by", []); m["found"]["intent"] = f[:3]; m["caught_by"] = [g for g in m["caught_by"] if g != "intent"] + (["intent"] if f else [])
        print(m["id"], "|", m["note"], "|", f[0] if f else "-")
    json.dump(res, open(f"{muts}/results.json", "w"), indent=1)
    gates = sorted({g for m in res for g in m["found"]} - {"twin"})
    print("\n| class | n | " + " | ".join(gates) + " | any, without intent | any |\n|---|---|" + "---|" * (len(gates) + 2))
    for c in sorted({m["class"] for m in res}) + ["all"]:
        ms = [m for m in res if c in (m["class"], "all")]; cb = lambda m: set(m["caught_by"]) - {"twin"}
        print(f"| {c} | {len(ms)} | " + " | ".join(str(sum(g in cb(m) for m in ms)) for g in gates)
              + f" | {sum(bool(cb(m) - {'intent'}) for m in ms)} | {sum(bool(cb(m)) for m in ms)} |")
