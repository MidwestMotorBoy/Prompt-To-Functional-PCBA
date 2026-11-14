"""roles.py: which nets get power copper and which of their pads carry the current, derived from the circuit code.
Shared by plan_copper.py (what to draw) and dc_score.py (what to measure), so both see the same terminals.

Net roles (from constraints.json, which the circuit build writes):
  return  the return net of the declared hot loops (GND on Monolith): planes, and vias at its pads
  power   a net declared with current_a (kind power or switching): pours sized from that current
  signal  everything else: left to the router; power copper keeps clear of its pads (escape room)

A pad of a power net is a terminal (it carries the net's current) when its part is in series with the current:
  - a hot-loop switch pin, a connector or wire pad, an inductor, a fuse, a transistor, a diode not to the return net;
  - a resistor of 0.1 ohm or less (a current-sense shunt) or a resistor the circuit code names in kelvin();
  - an IC pad at least three times the IC's median pad area (a power pin: TPS25751 PPHV is 0.76 mm2 against 0.11).
A capacitor (or a diode) between the net and the return net, or between two power nets, is a shunt terminal: it
needs low-impedance copper but no DC current. Any other pad of the net (dividers, filter resistors, IC sense pins)
is not a terminal: the router connects it later, and a Kelvin tap must not be joined by a pour anyway.
The circuit code can override with constraints["copper"]["terminals"][net] = ["REF.PAD", ...]."""
import json, math, re, statistics
from shapely.geometry import Polygon
from shapely.ops import unary_union

def poly(rec):
    return Polygon(rec["ring"], rec.get("holes") or [])

def value_ohms(v):
    """'1m 1% 1W' -> 0.001, '0R005' -> 0.005, '10k' -> 10000; None if not a resistance."""
    t = (v or "").strip().split()[0] if v else ""
    m = re.fullmatch(r"(\d*)([RrKkMm]?)(\d*)(?:ohm|Ω)?", t)
    if m and m.group(2) and m.group(1) + m.group(3):
        a, u, b = m.groups(); x = float((a or "0") + "." + (b or "0")); mult = {"r": 1, "k": 1e3, "m": 1e-3}[u.lower()]
        if u == "M": mult = 1e6
        return x * mult
    try: return float(t)
    except ValueError: return None

class Design:
    def __init__(self, dump, constraints):
        self.D = json.load(open(dump)) if isinstance(dump, str) else dump
        self.C = json.load(open(constraints)) if isinstance(constraints, str) else constraints
        self.board_nets = sorted({p["net"] for p in self.D["pads"] if p["net"]})
        self.fp = {f["ref"]: f for f in self.D["fps"]}
        self.pads = [p for p in self.D["pads"] if p["net"] and not p.get("npth")]
        for p in self.pads: p["key"] = f'{p["ref"]}.{p["num"]}'
        self.by_ref = {}
        for p in self.pads: self.by_ref.setdefault(p["ref"], []).append(p)
        self.ret = {self.board(hl["ret"]) for hl in self.C.get("hot_loops", {}).values()}
        self.power = {}
        for n, f in self.C.get("nets", {}).items():
            if f.get("current_a") and f.get("kind") in ("power", "switching") and self.board(n, None):
                self.power[self.board(n)] = dict(current_a=float(f["current_a"]), kind=f["kind"], decl=n)
        self.kelvin_res = {k["resistor"] for k in self.C.get("kelvin", {}).values()}
        self.switch_pins = set()
        for hl in self.C.get("hot_loops", {}).values():
            for t in hl["switch_pins"]:
                ref, pin = t.split("."); nums = self.C.get("pin_pads", {}).get(t)
                for p in self.by_ref.get(ref, []):
                    if (p["num"] in nums) if nums else (p["pinfn"].rsplit("_", 1)[0] == pin): self.switch_pins.add(p["key"])

    def board(self, name, default=KeyError):
        """Board net name for a circuit-code net name ('USB Port 1/VBUS' -> '/USB Port 1/VBUS')."""
        for n in self.board_nets:
            if n == name or n == "/" + name or n.endswith("/" + name): return n
        if default is KeyError: raise KeyError(name)
        return default

    def role(self, net):
        if net in self.ret: return "return"
        if net in self.power: return "power"
        return "signal"

    def area(self, p):
        return max((sum(poly(r).area for r in recs) for recs in p["shapes"].values()), default=0.0)

    def kind_of(self, p):
        """'series', 'shunt' or None for one pad of a power or return net."""
        ref = p["ref"]; pre = re.match(r"[A-Z]+", ref).group(0) if re.match(r"[A-Z]+", ref) else ""
        others = {q["net"] for q in self.by_ref[ref] if q["net"] != p["net"]}
        if p["key"] in self.switch_pins: return "series"
        if pre in ("C", "D", "TVS") and others and others <= (self.ret | set(self.power)): return "shunt"
        if pre in ("C",): return None
        if pre in ("J", "L", "F", "Q", "D", "SW", "K"): return "series"
        if pre in ("R", "RS"):
            v = value_ohms(self.fp[ref]["value"])
            return "series" if ref in self.kelvin_res or (v is not None and v <= 0.1) else None
        if pre in ("U", "IC"):
            med = statistics.median([self.area(q) for q in self.by_ref[ref]])
            return "series" if self.area(p) >= 3 * med and self.area(p) >= 0.3 else None
        return None

    def terminals(self, net):
        """Terminal groups of a net: one per part, the part's pads on the net that carry current.
        Each: dict(ref, pads=[pad], kind='series'|'shunt', current_a)."""
        over = self.C.get("copper", {}).get("terminals", {}).get(self.C_name(net))
        groups = {}
        for p in self.pads:
            if p["net"] != net: continue
            k = ("series" if p["key"] in over else None) if over else self.kind_of(p)
            if k is None: continue
            g = groups.setdefault(p["ref"], dict(ref=p["ref"], pads=[], kind=k)); g["pads"].append(p)
            if k == "series": g["kind"] = "series"
        for g in groups.values(): g["current_a"] = self.part_current(g["ref"], net, g["kind"])
        return list(groups.values())

    def part_current(self, ref, net, kind):
        """Current a terminal carries. A shunt part: up to 1 A of ripple. A series part: the net's current, limited by
        the current of the other power nets the part touches (a 3.3 V buck's input pin on a 10 A bus carries what its
        0.5 A output needs, not 10 A). A connector, fuse, inductor, transistor or shunt resistor with no other declared
        net carries the whole net current; an IC with none, 1 A. On the return net the same rule with no net limit,
        except that an IC's return pins count 1 A."""
        I = self.current(net) if net not in self.ret else float("inf")
        if kind == "shunt": return min(I, 1.0)
        others = [self.power[q["net"]]["current_a"] for q in self.by_ref[ref] if q["net"] in self.power and q["net"] != net]
        pre = re.match(r"[A-Z]*", ref).group(0)
        if net in self.ret and pre in ("U", "IC", "D"): return 1.0     # an IC's ground pins: its own supply current
        if others: return min(I, max(others))
        return min(I, 1.0) if pre in ("U", "IC", "D") or I == float("inf") else I

    def C_name(self, net):
        return self.power.get(net, {}).get("decl", net.lstrip("/"))

    def current(self, net):
        return self.power.get(net, {}).get("current_a", 0.0)

    def pad_poly(self, p, layer):
        recs = p["shapes"].get(layer)
        return unary_union([poly(r) for r in recs]) if recs else None

    def layers_of(self, p):
        return [l for l in p["shapes"]]

# Width of an outer-layer path for a current: planning figures for a 10 K rise (pcb-layout skill,
# references/high-current-and-thermal.md, from IPC-2152 via secondary tables; they disagree slightly, so the
# DC solver checks the result). 2 oz (70 um): 2.4 A at 0.5 mm, 4.8 A at 1.27 mm, 6 A at 1.8 mm, 10 A at 3.5 mm.
# 1 oz (35 um): 1 A at 0.3 mm, 3 A at 1.5 mm, 6 A at 4 mm.
WIDTH_2OZ = [(0, 0.3), (2.4, 0.5), (4.8, 1.27), (6, 1.8), (10, 3.5)]
WIDTH_1OZ = [(0, 0.25), (1, 0.3), (3, 1.5), (6, 4.0)]
def width_mm(I, t_mm=0.07):
    tab = WIDTH_2OZ if t_mm >= 0.06 else WIDTH_1OZ
    for (i0, w0), (i1, w1) in zip(tab, tab[1:]):
        if I <= i1: return w0 + (w1 - w0) * (I - i0) / (i1 - i0)
    (i0, w0), (i1, w1) = tab[-2], tab[-1]; return w1 + (w1 - w0) * (I - i1) / (i1 - i0)
AMPS_PER_VIA = 1.0     # TI's TPS25751 layout guidance (1 A per via), the planning figure in the pcb-layout skill
def vias_for(I): return max(1, math.ceil(I / AMPS_PER_VIA - 1e-9))
