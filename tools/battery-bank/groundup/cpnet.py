"""cpnet.py in.kicad_pcb out.kicad_pcb ref.kicad_pcb netregex x0,y0,x1,y1 keepu.txt (KiCad python)
Copy the tracks and vias of the matching nets that lie wholly inside the box from the ref board into the board (as fixed copper,
ids appended to keepu.txt). Zones are refilled."""
import sys, re, pcbnew
M = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); r = pcbnew.LoadBoard(sys.argv[3]); rx = re.compile(sys.argv[4]); x0, y0, x1, y1 = [float(v) for v in sys.argv[5].split(',')]
ins = lambda p: x0 <= M(p.x) <= x1 and y0 <= M(p.y) <= y1
ids = []
for t in r.GetTracks():
    if not rx.search(t.GetNetname()): continue
    net = b.FindNet(t.GetNetname())
    if t.GetClass() == "PCB_VIA":
        if not ins(t.GetPosition()): continue
        v = pcbnew.PCB_VIA(b); v.SetPosition(t.GetPosition()); v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetWidth(pcbnew.FromMM(0.45)); v.SetDrill(pcbnew.FromMM(0.3)); v.SetNet(net); b.Add(v); ids.append(v.m_Uuid.AsString())
    else:
        if not (ins(t.GetStart()) and ins(t.GetEnd())): continue
        n = pcbnew.PCB_TRACK(b); n.SetStart(t.GetStart()); n.SetEnd(t.GetEnd()); n.SetWidth(t.GetWidth()); n.SetLayer(t.GetLayer()); n.SetNet(net); b.Add(n); ids.append(n.m_Uuid.AsString())
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
open(sys.argv[6], "a").write("".join(i + "\n" for i in ids)); print("copied", len(ids))
