import pcbnew,sys
b=pcbnew.LoadBoard('/w/base/Monolith.kicad_pcb')
for net in ('/USB Port 1/PD_DRAIN','/USB Port 1/CC1','/USB Port 1/CC2'):
    print(net)
    for t in b.GetTracks():
        if t.GetNetname()==net:
            s=t.GetStart(); e=t.GetEnd()
            print('  ',t.GetClass(),t.GetLayerName(),round(s.x/1e6,3),round(s.y/1e6,3),round(e.x/1e6,3),round(e.y/1e6,3),t.GetWidth()/1e6)
    for z in b.Zones():
        if z.GetNetname()==net: print('  zone',z.GetLayerName(),z.GetBoundingBox().GetLeft()/1e6,z.GetBoundingBox().GetTop()/1e6,z.GetBoundingBox().GetRight()/1e6,z.GetBoundingBox().GetBottom()/1e6)
ds=b.GetDesignSettings()
print('minclr',ds.m_MinClearance/1e6,'mintrack',ds.m_TrackMinWidth/1e6,'minvia',ds.m_ViasMinSize/1e6,'mindrill',ds.m_MinThroughDrill/1e6,'holeclr',ds.m_HoleClearance/1e6,'hole2hole',ds.m_HoleToHoleMin/1e6,'edge',ds.m_CopperEdgeClearance/1e6, 'annular',ds.m_ViasMinAnnularWidth/1e6)
