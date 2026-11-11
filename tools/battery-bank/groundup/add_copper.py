"""add zones / tracks / vias from a copper.json to a placed board, fill, save (run in the KiCad container)
   add_copper.py placed.kicad_pcb copper.json out.kicad_pcb"""
import pcbnew,sys,json
mm=pcbnew.FromMM
b=pcbnew.LoadBoard(sys.argv[1]); C=json.load(open(sys.argv[2]))
LID={b.GetLayerName(l)[:3]:l for l in b.GetEnabledLayers().Seq()}
LID={'F':pcbnew.F_Cu,'B':pcbnew.B_Cu,'In1':pcbnew.In1_Cu,'In2':pcbnew.In2_Cu,'In3':pcbnew.In3_Cu,'In4':pcbnew.In4_Cu}
def net(n):
    o=b.FindNet(n)
    if o is None: raise SystemExit('no net '+n)
    return o
nz=nt=nv=0
for it in C:
    k=it['k']
    if k=='zone':
        z=pcbnew.ZONE(b); ls=pcbnew.LSET()
        for l in it['layers']: ls.AddLayer(LID[l])
        z.SetLayerSet(ls); z.SetNet(net(it['net']))
        ol=z.Outline(); ol.NewOutline()
        for x,y in it['pts']: ol.Append(mm(x),mm(y))
        for h in it.get('holes',[]):
            ol.NewHole()
            for x,y in h: ol.Append(mm(x),mm(y))
        z.SetAssignedPriority(it.get('prio',0)); z.SetLocalClearance(mm(it.get('clr',0.25))); z.SetMinThickness(mm(it.get('minw',0.25)))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); z.SetZoneName(it.get('name',''))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS if it.get('islands','remove')=='remove' else pcbnew.ISLAND_REMOVAL_MODE_NEVER)
        b.Add(z); nz+=1
    elif k=='ko':
        z=pcbnew.ZONE(b); ls=pcbnew.LSET()
        for l in it['layers']: ls.AddLayer(LID[l])
        z.SetLayerSet(ls); z.SetIsRuleArea(True); z.SetDoNotAllowZoneFills(True); z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        ol=z.Outline(); ol.NewOutline()
        for x,y in it['pts']: ol.Append(mm(x),mm(y))
        z.SetZoneName(it.get('name','')); b.Add(z)
    elif k=='track':
        pts=it['pts']
        for a,c in zip(pts,pts[1:]):
            t=pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(a[0]),mm(a[1]))); t.SetEnd(pcbnew.VECTOR2I(mm(c[0]),mm(c[1])))
            t.SetWidth(mm(it['w'])); t.SetLayer(LID[it['layer']]); t.SetNet(net(it['net'])); b.Add(t); nt+=1
    elif k=='via':
        v=pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(mm(it['x']),mm(it['y']))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu); v.SetWidth(pcbnew.F_Cu,mm(it.get('d',0.45))) if False else v.SetWidth(mm(it.get('d',0.45))) if not hasattr(v,'SetWidth') or True else None
        v.SetDrill(mm(it.get('drill',0.3))); v.SetNet(net(it['net']))
        try:
            v.SetRemoveUnconnected(True); v.SetKeepStartEnd(True)
        except Exception as e: pass
        b.Add(v); nv+=1
print('added zones',nz,'tracks',nt,'vias',nv)
b.BuildConnectivity()
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.BuildConnectivity()
print('unconnected',b.GetConnectivity().GetUnconnectedCount(False))
b.Save(sys.argv[3])
