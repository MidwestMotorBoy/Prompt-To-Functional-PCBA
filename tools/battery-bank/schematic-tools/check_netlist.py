"""Check the production netlist against the dev board's (run after make_production.py).

Every pin that survives must sit on the same net as on the dev board, except where a 0 ohm link was replaced by a
wire (those nets merge). The new pads and the TC2030 must land on the nets of the pins they replace.
"""
import collections
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_production as mp  # noqa: E402

CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"


def netlist(sch):
    out = os.path.join(tempfile.gettempdir(), "chk_%s.xml" % os.path.basename(sch))
    subprocess.run([CLI, "sch", "export", "netlist", "--format", "kicadxml", "-o", out, sch], check=True, capture_output=True)
    pin = {}
    for n in ET.parse(out).getroot().iter("net"):
        for x in n.iter("node"):
            pin[(x.get("ref"), x.get("pin"))] = n.get("name")
    return pin


def both_ports(refs, sheet):
    out = set(refs)
    if sheet == "usb_port.kicad_sch":
        out |= {r[:-3] + "5" + r[-2:] for r in refs if r[-3] == "4"}
    return out


old = netlist(os.path.join(mp.DEV, mp.ROOT_DEV))
new = netlist(os.path.join(mp.PROD, mp.ROOT))
gone, links = set(), set()
for sh, refs in mp.REMOVE.items():
    gone |= both_ports(refs, sh)
gone |= both_ports(mp.GD_GONE, "usb_port.kicad_sch")   # R420 -> D410 (9 V gate drive)
for sh, refs in mp.LINKS.items():
    links |= both_ports(refs, sh)

parent = {}


def find(a):
    while parent.get(a, a) != a:
        a = parent[a]
    return a


for r in links:
    a, b = find(old[(r, "1")]), find(old[(r, "2")])
    parent[a] = b

fets = set()
for hs, ls in mp.siz240dt.LEGS:
    fets |= both_ports([hs, ls], "usb_port.kicad_sch")
expect = {}
for (r, p), n in old.items():
    if r not in gone and r not in links and r not in fets:
        expect[(r, p)] = find(n)
for (r, p), (orf, op) in mp.siz240dt.PIN_REMAP.items():  # leg FETs merged into one SiZ240DT per leg
    for a, b in ((r, orf), (r[:-3] + "5" + r[-2:], orf[:-3] + "5" + orf[-2:])):
        expect[(a, p)] = find(old[(b, op)])
for ref, _, _, (oref, opin) in mp.GAUGE_PADS:
    expect[(ref, "1")] = find(old[(oref, opin)])
for (ref, pin), to in mp.NET_MOVES.items():
    for port, r in enumerate(sorted(both_ports([ref], "usb_port.kicad_sch"))):  # a port-1 ref brings its port-2 twin
        if to == "GND":
            expect[(r, pin)] = find(old[("TP109", "1")])
        elif to and ref[-3] == "4":
            expect[(r, pin)] = "%s port %d" % (to, port + 1)   # "new NAME": a net new on production, one per port
        else:
            expect[(r, pin)] = to or "unconnected %s.%s" % (r, pin)
for ref, pins in mp.NEW_PARTS.items():
    for p, src in pins.items():
        expect[(ref, p)] = src if isinstance(src, str) else find(old[src])
for ref, pins in mp.GD_NETS.items():   # 9 V gate drive, both ports
    for p, src in pins.items():
        for port, r in enumerate(sorted(both_ports([ref], "usb_port.kicad_sch"))):
            if src is None:
                expect[(r, p)] = "unconnected %s.%s" % (r, p)
            elif isinstance(src, str):
                expect[(r, p)] = "%s port %d" % (src, port + 1)
            else:
                expect[(r, p)] = find(old[(src[0][:-3] + "45"[port] + src[0][-2:], src[1])] if src[0][-3] == "4"
                                      else old[src])
for p, (oref, opin) in {"1": ("J301", "1"), "2": ("J301", "2"), "3": ("J301", "10"), "4": ("J301", "4"), "5": ("J301", "3")}.items():
    expect[("J301", p)] = find(old[(oref, opin)])

bad = []
missing = sorted(k for k in expect if k not in new)
extra = sorted(k for k in new if k not in expect and not (k[0] == "J301" and k[1] == "6"))
groups = collections.defaultdict(set)
for k, n in expect.items():
    if k in new:
        groups[n].add(new[k])
for n, s in groups.items():
    if len(s) > 1:
        bad.append("old net %s split into %s" % (n, sorted(s)))
inv = collections.defaultdict(set)
for k, n in expect.items():
    if k in new:
        inv[new[k]].add(n)
for n, s in inv.items():
    if len(s) > 1:
        bad.append("new net %s joins old nets %s" % (n, sorted(s)))
print("pins checked: %d   missing: %s   unexpected: %s" % (len(expect), missing or "-", extra or "-"))
print("\n".join(bad) if bad else "net partition matches the dev board (plus link merges)")
print("parts: dev %d -> production %d" % (len({r for r, _ in old}), len({r for r, _ in new})))
