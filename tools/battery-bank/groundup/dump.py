import pcbnew, json, sys
b=pcbnew.LoadBoard(sys.argv[1])
mm=pcbnew.ToMM
out={'fps':[],'zones':[],'nets':{}}
for f in b.GetFootprints():
    bb=f.GetCourtyard(f.GetLayer()).BBox() if f.GetCourtyard(f.GetLayer()).OutlineCount() else f.GetBoundingBox(False)
    d=dict(ref=f.GetReference(),val=f.GetValue(),fp=str(f.GetFPID().GetUniStringLibId()),layer=f.GetLayerName(),x=mm(f.GetPosition().x),y=mm(f.GetPosition().y),rot=f.GetOrientationDegrees(),locked=f.IsLocked(),
      bb=[mm(bb.GetLeft()),mm(bb.GetTop()),mm(bb.GetRight()),mm(bb.GetBottom())],sheet=f.GetSheetname(),attr=f.GetAttributes(),dnp=f.IsDNP(),bom_ex=f.IsExcludedFromBOM(),pos_ex=f.IsExcludedFromPosFiles(),
      props={k:v for k,v in f.GetFieldsText().items() if k in('LCSC','MPN','Notes')},pads=[])
    for p in f.Pads():
        d['pads'].append(dict(n=p.GetNumber(),net=p.GetNetname(),x=mm(p.GetPosition().x),y=mm(p.GetPosition().y),sx=mm(p.GetSize(pcbnew.F_Cu).x) if hasattr(p,'GetSize') else 0,sy=mm(p.GetSize(pcbnew.F_Cu).y),drill=mm(p.GetDrillSize().x),type=p.GetAttribute(),shape=p.GetShape(pcbnew.F_Cu),rot=p.GetOrientationDegrees(),pinfn=p.GetPinFunction()))
    out['fps'].append(d)
for z in b.Zones():
    o=z.Outline(); bb=z.GetBoundingBox()
    pts=[]
    if o.OutlineCount():
        ol=o.Outline(0); pts=[[mm(ol.CPoint(i).x),mm(ol.CPoint(i).y)] for i in range(ol.PointCount())]
    out['zones'].append(dict(name=z.GetZoneName(),net=z.GetNetname(),layers=[b.GetLayerName(l) for l in z.GetLayerSet().Seq()],rulearea=z.GetIsRuleArea(),td=z.IsTeardropArea() if hasattr(z,'IsTeardropArea') else None,
       no_tracks=z.GetDoNotAllowTracks(),no_vias=z.GetDoNotAllowVias(),no_pads=z.GetDoNotAllowPads(),no_fp=z.GetDoNotAllowFootprints(),no_pour=z.GetDoNotAllowZoneFills() if hasattr(z,'GetDoNotAllowZoneFills') else None,
       bb=[mm(bb.GetLeft()),mm(bb.GetTop()),mm(bb.GetRight()),mm(bb.GetBottom())],pts=pts,prio=z.GetAssignedPriority(),locked=z.IsLocked()))
for n,ni in b.GetNetsByName().items():
    out['nets'][str(n)]=dict(cls=ni.GetNetClassName())
ds=b.GetDesignSettings()
out['rules']=dict(minclr=mm(ds.m_MinClearance),minw=mm(ds.m_TrackMinWidth),viamin=mm(ds.m_ViasMinSize),viadrill=mm(ds.m_MinThroughDrill),h2h=mm(ds.m_HoleToHoleMin),edge=mm(ds.m_CopperEdgeClearance),ann=mm(ds.m_ViasMinAnnularWidth),holeclr=mm(ds.m_HoleClearance))
json.dump(out,open(sys.argv[2],'w'))
print(len(out['fps']),len(out['zones']),len(out['nets']))
