"""Spike: netlist (truth, from SKiDL) -> label-on-pin KiCad schematic via kicad-sch-api -> kicad-cli netlist -> diff."""
import re, sys, json
import kicad_sch_api as ksa
net_txt = open(sys.argv[1]).read()
# parse SKiDL .net (KiCad sexpr netlist) crudely
comps = {}
for m in re.finditer(r'\(comp\s*\(ref "([^"]+)"\)\s*\(value "([^"]*)"\).*?\(libsource\s*\(lib "([^"]+)"\)\s*\(part "([^"]+)"\)', net_txt, re.S):
    comps[m.group(1)] = dict(value=m.group(2), lib=m.group(3)+":"+m.group(4))
nets = {}
for m in re.finditer(r'\(net\s*\(code \d+\)\s*\(name "([^"]+)"\)(.*?)(?=\(net\s*\(code|\Z)', net_txt, re.S):
    nets[m.group(1)] = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(2))
json.dump({"comps": comps, "nets": nets}, open("truth.json", "w"), indent=1)
sch = ksa.create_schematic("buck_hybrid")
x, y = 50.8, 50.8
for i, (ref, c) in enumerate(sorted(comps.items())):
    sch.components.add(c["lib"], ref, c["value"], position=(x + (i % 4) * 50.8, y + (i // 4) * 38.1))
for name, nodes in nets.items():
    for ref, pin in nodes:
        sch.add_label(name, pin=(ref, pin))
sch.save("buck_hybrid.kicad_sch")
print("components", len(comps), "nets", len(nets))
