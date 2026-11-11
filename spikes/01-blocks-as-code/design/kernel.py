"""Circuit-as-code kernel. A block is a Python function that makes parts and joins pins to nets.

    u = part("Regulator_Switching", "TPS62177DQC", "U204", value="TPS62177DQCR", fp="...")
    u["VIN"] += pack_p              # by pin name, checked against the real KiCad symbol
    u[7] += NC                      # every pin must be connected or marked NC
    C("C206", "2.2u 50V", "0805", pack_p, gnd, serves="U204.VIN")

Layout facts (which cap serves which pin, switching nets, hot loops, Kelvin pairs, currents) are declared next
to the circuit and written to constraints.json. build() writes netlist.json, which is the source of truth.
"""
import json, os, inspect
import symlib

FP = {"0402": "Capacitor_SMD:C_0402_1005Metric", "0603": "Capacitor_SMD:C_0603_1608Metric",
      "0805": "Capacitor_SMD:C_0805_2012Metric", "1206": "Capacitor_SMD:C_1206_3216Metric",
      "1210": "Capacitor_SMD:C_1210_3225Metric",
      "R0402": "Resistor_SMD:R_0402_1005Metric", "R0603": "Resistor_SMD:R_0603_1608Metric",
      "R0805": "Resistor_SMD:R_0805_2012Metric", "R1206": "Resistor_SMD:R_1206_3216Metric"}

class DesignError(Exception):
    pass

def _where():
    for f in inspect.stack()[2:]:
        if not f.filename.endswith(("kernel.py",)):
            return f"{os.path.basename(f.filename)}:{f.lineno}"
    return "?"

class Net:
    def __init__(self, name):
        self.name, self.nodes = name, []
        if name in CIRCUIT["nets"]:
            raise DesignError(f"{_where()}: net '{name}' already exists; pass the Net object instead of making a second one")
        CIRCUIT["nets"][name] = self

class _NC:
    name = "NC"
NC = _NC()

class Pins:
    def __init__(self, part, pins): self.part, self.pins = part, pins
    def __iadd__(self, net):
        for p in self.pins:
            key = (self.part.ref, p["num"])
            if CIRCUIT["pinnet"].get(key) is net:
                continue                  # same pad drawn in two units of the symbol
            if key in CIRCUIT["pinnet"]:
                raise DesignError(f"{_where()}: {self.part.ref} pin {p['num']} ({p['name']}) is already on net "
                                  f"'{CIRCUIT['pinnet'][key].name}', cannot also join '{net.name}'")
            CIRCUIT["pinnet"][key] = net
            if net is not NC:
                net.nodes.append([self.part.ref, p["num"]])
        return self

class Part:
    def __init__(self, lib, name, ref, value, footprint, fields):
        self.lib, self.name, self.ref, self.value, self.footprint, self.fields = lib, name, ref, value, footprint, fields
        self.pins = symlib.pins(lib, name)
    def __getitem__(self, keys):
        if not isinstance(keys, tuple): keys = (keys,)
        got = []
        for k in keys:
            k = str(k)
            m = [p for p in self.pins if p["num"] == k] or [p for p in self.pins if p["name"] == k]
            if not m:
                names = sorted({f"{p['num']}:{p['name']}" for p in self.pins}, key=lambda s: (len(s.split(':')[0]), s))
                raise DesignError(f"{_where()}: {self.ref} ({self.lib}:{self.name}) has no pin '{k}'. Pins are: {' '.join(names)}")
            got += m
        return Pins(self, got)
    def __setitem__(self, k, v):   # supports  u["VIN"] += net
        pass

CIRCUIT = {"parts": {}, "nets": {}, "pinnet": {}}
CONSTRAINTS = {"nets": {}, "serves": {}, "hot_loops": {}, "kelvin": {}, "draw": {}, "expect": {}}
_block = []

def part(lib, name, ref, value=None, fp=None, **fields):
    if ref in CIRCUIT["parts"]:
        raise DesignError(f"{_where()}: reference {ref} is used twice")
    try:
        p = Part(lib, name, ref, value if value is not None else name, FP.get(fp, fp) or "", fields)
    except KeyError as e:
        raise DesignError(f"{_where()}: {e.args[0]}") from None
    p.block = "/".join(_block)
    p.section = _section[0]
    CIRCUIT["parts"][ref] = p
    return p

def C(ref, value, fp, a, b, serves=None, lib=("Device", "C"), **f):
    """Capacitor from net a (pin 1) to net b (pin 2). serves='U204.VIN' binds it to the pin it decouples."""
    p = part(lib[0], lib[1], ref, value, fp, **f)
    p[1] += a; p[2] += b
    if serves: CONSTRAINTS["serves"][ref] = serves
    return p

def R(ref, value, fp, a, b, serves=None, **f):
    """Resistor from net a (pin 1) to net b (pin 2)."""
    p = part("Device", "R", ref, value, "R" + fp if fp in ("0402", "0603", "0805", "1206") else fp, **f)
    p[1] += a; p[2] += b
    if serves: CONSTRAINTS["serves"][ref] = serves
    return p

def declare(net, **kw):
    """Facts about a net: kind='switching'|'sensitive'|'power', current_a, swing_v, edge_ns, and max_v, the
    highest voltage to ground the net can reach in any state. max_v is what part ratings are checked against."""
    CONSTRAINTS["nets"].setdefault(net.name, {}).update(kw)
    return net

def volts(max_v, *nets, normal=None):
    """Shorthand: the same max_v for several nets. max_v is the highest the net can reach, faults included;
    normal= is the highest it runs at in normal use (checked against recommended operating limits; default max_v)."""
    for n in nets: declare(n, max_v=max_v, **({"normal_v": normal} if normal is not None else {}))

def across(max_v, *refs):
    """The highest voltage across a two-terminal part when neither end is ground (a filter capacitor across a sense
    resistor). Without this the part is rated against the highest net it touches."""
    CONSTRAINTS.setdefault("across", {}).update({"".join(r) if not isinstance(r, str) else r: max_v for r in refs})

def waive(finding_prefix, reason):
    """Accept one gate finding in writing: waive("recmax: U101.DSG", "why this is acceptable"). The build prints every
    waived finding with its reason on every run."""
    CONSTRAINTS.setdefault("waive", {})[finding_prefix] = reason

def expect(name, expr, target, tol, unit="", at=None, **bind):
    """What a set of part values is meant to produce, so a wrong value is a failed check and not a silent change.
        expect("PP5V", "VREF * (1 + Rtop / Rbot)", 5.15, 0.03, "V", VREF="TPS62933.VREF", Rtop="R433", Rbot="R434")
    A binding is a part reference (its value in ohms) or PART.FACT from the part knowledge base.
    at="U404.FB" names the pin the value is for; that pin must touch at least one of the bound parts."""
    CONSTRAINTS["expect"]["/".join(_block + [name])] = dict(expr=expr, target=target, tol=tol, unit=unit, at=at, bind=bind)

def hot_loop(name, supply, ret, switch_pins, caps):
    CONSTRAINTS["hot_loops"][name] = dict(supply=supply.name, ret=ret.name, switch_pins=switch_pins, caps=caps)

def kelvin(name, resistor, pos, neg):
    CONSTRAINTS["kelvin"][name] = dict(resistor=resistor, pos=pos.name, neg=neg.name)

def draw_as(kind, ic, **roles):
    """How to draw the parts around one IC, as a human would. kind "buck": vin, sw (pin names), inductor (ref),
    cin, cout (lists of refs), and either sense (pin on the output) or fb (pin) with div=[top, bottom];
    optional bst (pin) with boot (cap ref)."""
    CONSTRAINTS["draw"][ic] = dict(kind=kind, **roles)

_section = [""]
def section(title):
    """Start a titled section of the current block. Parts made after this call are drawn under this title."""
    _section[0] = title

class block:
    """with block('3V3 Rail'): ...   One block is one schematic sheet and one placement group."""
    def __init__(self, name): self.name = name
    def __enter__(self): _block.append(self.name)
    def __exit__(self, *a): _block.pop(); _section[0] = ""

def build(outdir, partial=False):
    """Check the circuit and write netlist.json (the source of truth) and constraints.json."""
    errs = []
    for p in CIRCUIT["parts"].values():
        for pin in p.pins:
            if (p.ref, pin["num"]) not in CIRCUIT["pinnet"]:
                errs.append(f"{p.ref} pin {pin['num']} ({pin['name']}) is not connected and not marked NC")
    for n in CIRCUIT["nets"].values():
        if len(n.nodes) == 1 and not partial:
            errs.append(f"net '{n.name}' has only one pin: {n.nodes[0][0]}.{n.nodes[0][1]}")
    for ref, tgt in CONSTRAINTS["serves"].items():
        r, pn = tgt.split(".", 1)
        if r not in CIRCUIT["parts"]:
            errs.append(f"{ref} serves '{tgt}' but there is no part {r}")
            continue
        tp = CIRCUIT["parts"][r][pn].pins
        nets_t = {CIRCUIT["pinnet"].get((r, p["num"])) for p in tp}
        nets_c = {CIRCUIT["pinnet"].get((ref, p["num"])) for p in CIRCUIT["parts"][ref].pins}
        if not (nets_t & nets_c):
            errs.append(f"{ref} is declared to serve {tgt} but shares no net with it")
    if errs:
        raise DesignError("design check failed:\n  " + "\n  ".join(errs))
    os.makedirs(outdir, exist_ok=True)
    comps = {p.ref: dict(lib=f"{p.lib}:{p.name}", value=p.value, footprint=p.footprint, fields=p.fields, block=p.block, section=p.section, order=i)
             for i, p in enumerate(CIRCUIT["parts"].values())}
    nets = {n.name: sorted(n.nodes) for n in CIRCUIT["nets"].values() if n.nodes}
    nc = sorted([r, num] for (r, num), n in CIRCUIT["pinnet"].items() if n is NC)
    json.dump(dict(comps=comps, nets=nets, nc=nc), open(f"{outdir}/netlist.json", "w"), indent=1, sort_keys=True)
    json.dump(CONSTRAINTS, open(f"{outdir}/constraints.json", "w"), indent=1, sort_keys=True)
    return comps, nets
