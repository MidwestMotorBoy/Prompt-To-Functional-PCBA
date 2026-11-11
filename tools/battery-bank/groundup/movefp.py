"""movefp.py in.kicad_pcb out.kicad_pcb ref x y rot [ref x y rot ...] (KiCad python): move footprints, drop zero-length tracks, refill."""
import sys, pcbnew
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1]); a = sys.argv[3:]
for i in range(0, len(a), 4):
    f = b.FindFootprintByReference(a[i]); f.SetPosition(pcbnew.VECTOR2I(mm(float(a[i + 1])), mm(float(a[i + 2])))); f.SetOrientationDegrees(float(a[i + 3]))
    print(a[i], [(p.GetNumber(), p.GetNetname().split("/")[-1], round(pcbnew.ToMM(p.GetPosition().x), 3), round(pcbnew.ToMM(p.GetPosition().y), 3)) for p in f.Pads()])
z = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetStart() == t.GetEnd()]
for t in z: b.Remove(t)
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print("zero-length tracks removed", len(z))
