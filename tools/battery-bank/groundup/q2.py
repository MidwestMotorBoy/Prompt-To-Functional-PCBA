import pcbnew
b=pcbnew.LoadBoard('/w/new/Monolith.kicad_pcb')
for z in b.Zones():
    bb=z.GetBoundingBox()
    fl=[]
    for nm in ('GetDoNotAllowTracks','GetDoNotAllowVias','GetDoNotAllowPads','GetDoNotAllowZoneFills','GetDoNotAllowFootprints','GetDoNotAllowCopperPour'):
        if hasattr(z,nm): fl.append(nm[13:]+'='+str(int(getattr(z,nm)())))
    print(repr(str(z.GetZoneName())),[b.GetLayerName(l) for l in z.GetLayerSet().Seq()],round(bb.GetLeft()/1e6,2),round(bb.GetTop()/1e6,2),round(bb.GetRight()/1e6,2),round(bb.GetBottom()/1e6,2),' '.join(fl),z.m_Uuid.AsString())
