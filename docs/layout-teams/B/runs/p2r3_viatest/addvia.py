import pcbnew
b=pcbnew.LoadBoard('cu.kicad_pcb'); n=b.FindNet('EN_5V1')
for (x,y) in [(100.0,90.0)]:
    v=pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))); v.SetWidth(pcbnew.FromMM(0.45)); v.SetDrill(pcbnew.FromMM(0.3)); v.SetNet(n); b.Add(v)
# a hard track island too
t=pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(100.0),pcbnew.FromMM(95))); t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(100.0),pcbnew.FromMM(97))); t.SetWidth(pcbnew.FromMM(0.15)); t.SetLayer(pcbnew.In3_Cu); t.SetNet(n); b.Add(t)
b.Save('t.kicad_pcb')
