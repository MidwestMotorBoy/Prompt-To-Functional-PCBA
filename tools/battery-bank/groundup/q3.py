import pcbnew,collections
b=pcbnew.LoadBoard('/w/base/Monolith.kicad_pcb')
# zone summary of the old board (non-teardrop copper zones)
for z in b.Zones():
    if z.GetIsRuleArea() or z.IsTeardropArea(): continue
    bb=z.GetBoundingBox()
    print('zone',str(z.GetNetname()).split('/')[-1],[b.GetLayerName(l)[:3] for l in z.GetLayerSet().Seq()],round(bb.GetLeft()/1e6,1),round(bb.GetTop()/1e6,1),round(bb.GetRight()/1e6,1),round(bb.GetBottom()/1e6,1),'prio',z.GetAssignedPriority(),'clr',z.GetLocalClearance()/1e6 if z.GetLocalClearance() else None,'minw',z.GetMinThickness()/1e6,'conn',z.GetPadConnection(),repr(str(z.GetZoneName())))
c=collections.Counter()
for t in b.GetTracks():
    if t.GetClass()=='PCB_VIA': c[('via',t.GetWidth(pcbnew.F_Cu)/1e6,t.GetDrill()/1e6)]+=1
    else: c[(b.GetLayerName(t.GetLayer())[:3],t.GetWidth()/1e6)]+=1
print(sorted(c.items(),key=lambda kv:-kv[1])[:40])
ds=b.GetDesignSettings()
print('stackup')
st=ds.GetStackupDescriptor()
for it in st.GetList():
    print(' ',it.GetTypeName(),it.GetLayerName(),it.GetThickness()/1e6, it.GetMaterial() if hasattr(it,'GetMaterial') else '')
