#!/usr/bin/env python3
"""ripwin.py <cu.kicad_pcb> <routed.kicad_pcb> <out.kicad_pcb> <x0,y0,x1,y1>[;...] [--keep=REGEX] [--only=REGEX]   (KiCad python)
Team A r6_merge regional rip-up: removes the ROUTER-laid tracks and vias (those not on the planned board) of every net
that has router-laid copper inside one of the windows, so router_esc.py can lay those nets again with the rest of
the routed board fixed. Plane nets (GND, PACK_P, 3V3) and --keep nets are never ripped. Refills zones, keeps .kicad_pro."""
import sys, os, re, pcbnew
a = [x for x in sys.argv[1:] if not x.startswith("--")]
o = dict((x[2:].split("=", 1) + ["1"])[:2] for x in sys.argv[1:] if x.startswith("--"))
wins = [[float(v) for v in w.split(",")] for w in a[3].split(";")]
keep = re.compile(o["keep"]) if "keep" in o else None; only = re.compile(o["only"]) if "only" in o else None
TM = pcbnew.ToMM
def key(t):
    if t.GetClass() == "PCB_VIA":
        p = t.GetPosition(); return ("V", t.GetNetname(), round(TM(p.x), 3), round(TM(p.y), 3))
    s, e = t.GetStart(), t.GetEnd(); q = sorted([(round(TM(s.x), 3), round(TM(s.y), 3)), (round(TM(e.x), 3), round(TM(e.y), 3))])
    return ("T", t.GetNetname(), t.GetLayer(), q[0], q[1])
b0 = pcbnew.LoadBoard(a[0]); fixed = {key(t) for t in b0.GetTracks()}
b = pcbnew.LoadBoard(a[1])
def inw(t):
    pts = [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]
    for p in pts:
        x, y = TM(p.x), TM(p.y)
        if any(w[0] <= x <= w[2] and w[1] <= y <= w[3] for w in wins): return True
    return False
laid = [t for t in b.GetTracks() if key(t) not in fixed]
nets = set()
for t in laid:
    n = t.GetNetname()
    if n in ("GND", "PACK_P", "3V3") or (keep and keep.search(n)) or (only and not only.search(n)): continue
    if inw(t): nets.add(n)
k = 0
for t in laid:
    if t.GetNetname() in nets: b.Remove(t); k += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pro = a[2][:-10] + ".kicad_pro"; kp = open(pro, "rb").read() if os.path.exists(pro) else None
b.Save(a[2])
if kp is not None: open(pro, "wb").write(kp)
print("ripwin: %d nets ripped, %d items removed: %s" % (len(nets), k, sorted(nets)))
