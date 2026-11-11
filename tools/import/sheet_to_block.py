"""sheet_to_block.py <netlist truth.json> <sheet path, e.g. "/Cells and Gauge/"> <sections.json> <function name>
First draft of a block file from an existing KiCad sheet, for bringing an old design into the pipeline. It writes
parts, values, part-number and note fields and wiring only; intent (volts, expect, serves, hot loops) is added by
hand afterwards. sections.json: {"section title": ["U101", "R101-R104", ...], ...} sets grouping and order.
Nets that leave the sheet become function arguments. Prints the block file."""
import json, re, sys, textwrap
d = json.load(open(sys.argv[1])); sheet = sys.argv[2]; secs = json.load(open(sys.argv[3])); fn = sys.argv[4]
mine = {r for r, c in d["comps"].items() if c["sheet"] == sheet}
def expand(spec):
    m = re.match(r"([A-Z]+)(\d+)-[A-Z]*(\d+)$", spec)
    return [f"{m.group(1)}{i}" for i in range(int(m.group(2)), int(m.group(3)) + 1)] if m else [spec]
order = [(t, [r for s in specs for r in expand(s) if r in mine]) for t, specs in secs.items()]
left = mine - {r for _, rs in order for r in rs}
if left: sys.exit("not in any section: " + " ".join(sorted(left)))
pin_net = {}; ext = []; var = {}
for n, nodes in d["nets"].items():
    here = [x for x in nodes if x[0] in mine]
    if not here: continue
    for r, p, _ in here: pin_net[(r, p)] = n
    if n.startswith("unconnected-"): var[n] = "NC"; continue
    short = n[len(sheet):] if n.startswith(sheet) else n.lstrip("/")
    v = re.sub(r"\W+", "_", short).strip("_").lower(); v = ("n_" + v) if v[0].isdigit() else v
    var[n] = v
    if len(here) < len(nodes) and not n.startswith(sheet): ext.append(n)
SHORT = {"Capacitor_SMD:C_0402_1005Metric": "0402", "Capacitor_SMD:C_0603_1608Metric": "0603", "Capacitor_SMD:C_0805_2012Metric": "0805",
         "Resistor_SMD:R_0402_1005Metric": "0402", "Resistor_SMD:R_0603_1608Metric": "0603", "Resistor_SMD:R_0805_2012Metric": "0805", "Resistor_SMD:R_1206_3216Metric": "1206"}
def fields(c):
    f = {k: v for k, v in c["fields"].items() if k not in ("Footprint", "Datasheet", "Description") and (v or k in ("LCSC",))}
    return [(k, v) for k, v in f.items() if k.isidentifier()]
def emit(head, args, kw, tail=")"):
    """One call, wrapped at argument boundaries; a long text field becomes adjacent string literals on their own lines."""
    lines, cur = [], " " * 8 + head
    for a in args + [f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in kw if len(v) <= 70]:
        if len(cur) + len(a) + 2 > 118: lines.append(cur.rstrip()); cur = " " * 10
        cur += a + ", "
    for k, v in kw:
        if len(v) <= 70: continue
        lines.append(cur.rstrip()); chunks = textwrap.wrap(v, 96, drop_whitespace=False)
        lines += [" " * 10 + (f"{k}=" if i == 0 else " " * (len(k) + 1)) + json.dumps(ch, ensure_ascii=False) for i, ch in enumerate(chunks)]
        lines[-1] += ", "; cur = ""
    if cur: lines.append(cur)
    lines[-1] = lines[-1].rstrip().rstrip(",") + tail
    return lines
def num(p): return p if p.isdigit() else json.dumps(p)
out = [f'"""{sheet.strip("/")}: first draft imported from the KiCad sheet by tools/import/sheet_to_block.py."""', "from kernel import *", "",
       f"def {fn}({', '.join(var[n] for n in sorted(ext))}):", f'    with block("{sheet.strip("/")}"):']
local = sorted(n for n in var if n not in ext and var[n] != "NC")
for n in local:
    name = n[len(sheet):] if n.startswith(sheet) else n
    out.append(f'        {var[n]} = Net({json.dumps(name)})')
for title, refs in order:
    out += ["", f"        section({json.dumps(title)})"]
    for r in refs:
        c = d["comps"][r]; pins = sorted((p for (rr, p) in pin_net if rr == r), key=lambda p: (len(p), p))
        if c["lib"] in ("Device:R", "Device:C") and pins == ["1", "2"]:
            k = c["lib"][-1]; fp = SHORT.get(c["footprint"], None)
            out += emit(f'{k}(', [f'"{r}"', json.dumps(c["value"]), json.dumps(fp or c["footprint"]), var[pin_net[(r, "1")]], var[pin_net[(r, "2")]]], fields(c))
        else:
            lib, sym = c["lib"].split(":"); v = r.lower()
            out += emit(f'{v} = part(', [f'"{lib}"', f'"{sym}"', f'"{r}"', json.dumps(c["value"]), json.dumps(c["footprint"])], fields(c))
            by = {}
            for p in pins: by.setdefault(var[pin_net[(r, p)]], []).append(p)
            for n, ps in by.items(): out.append(" " * 8 + f'{v}[{", ".join(num(p) for p in ps)}] += {n}')
print("\n".join(out))
