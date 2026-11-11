"""lift.py in.kicad_pcb out.kicad_pcb keep.kicad_pcb netregex [x0,y0,x1,y1] [--hand] (KiCad python)
Remove the router-laid tracks and vias (those not in the keep board or keepu.txt) of the nets matching netregex, optionally
only inside a box. With --hand the hand-drawn copper of those nets inside the box goes too. Zones are refilled."""
import sys, re, os, pcbnew
MM = pcbnew.ToMM
a = [x for x in sys.argv[1:] if not x.startswith("--")]
b = pcbnew.LoadBoard(a[0]); rx = re.compile(a[3]); box = [float(v) for v in a[4].split(",")] if len(a) > 4 else None
keep = set() if "--hand" in sys.argv else {t.m_Uuid.AsString() for t in pcbnew.LoadBoard(a[2]).GetTracks()}
ku = os.path.join(os.path.dirname(a[2]), "keepu.txt")
if os.path.exists(ku) and "--hand" not in sys.argv: keep |= set(open(ku).read().split())
n = {}
for t in list(b.GetTracks()):
    if t.m_Uuid.AsString() in keep or not rx.search(t.GetNetname()): continue
    if box:
        pts = [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]
        if not all(box[0] <= MM(p.x) <= box[2] and box[1] <= MM(p.y) <= box[3] for p in pts): continue
    n[t.GetNetname()] = n.get(t.GetNetname(), 0) + 1; b.Remove(t)
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(a[1])
print("lifted", n)
