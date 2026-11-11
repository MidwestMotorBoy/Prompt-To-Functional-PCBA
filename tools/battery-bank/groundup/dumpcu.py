"""dump copper of a board: tracks, vias, zone fills (outline+holes per layer), pads (polygon per copper layer) -> json"""
import pcbnew,sys,json
b=pcbnew.LoadBoard(sys.argv[1]); MM=lambda v: round(v/1e6,4)
CU=[pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.In3_Cu,pcbnew.In4_Cu,pcbnew.B_Cu]; LN=['F','In1','In2','In3','In4','B']
out=dict(tracks=[],vias=[],fills=[],pads=[])
def polys(ps):
    r=[]
    for i in range(ps.OutlineCount()):
        o=ps.Outline(i); pts=[(MM(o.CPoint(j).x),MM(o.CPoint(j).y)) for j in range(o.PointCount())]
        hs=[]
        for h in range(ps.HoleCount(i)):
            hh=ps.Hole(i,h); hs.append([(MM(hh.CPoint(j).x),MM(hh.CPoint(j).y)) for j in range(hh.PointCount())])
        r.append([pts,hs])
    return r
for t in b.GetTracks():
    if t.GetClass()=='PCB_VIA':
        p=t.GetPosition(); out['vias'].append(dict(x=MM(p.x),y=MM(p.y),d=MM(t.GetWidth(pcbnew.F_Cu)),drill=MM(t.GetDrill()),net=str(t.GetNetname())))
    else:
        s=t.GetStart(); e=t.GetEnd(); out['tracks'].append(dict(x1=MM(s.x),y1=MM(s.y),x2=MM(e.x),y2=MM(e.y),w=MM(t.GetWidth()),l=LN[CU.index(t.GetLayer())],net=str(t.GetNetname())))
for z in b.Zones():
    if z.GetIsRuleArea(): continue
    for l,n in zip(CU,LN):
        if z.IsOnLayer(l):
            fp=z.GetFilledPolysList(l)
            ps=pcbnew.SHAPE_POLY_SET(fp)
            out['fills'].append(dict(net=str(z.GetNetname()),l=n,name=str(z.GetZoneName()),polys=polys(ps)))
for f in b.GetFootprints():
    for p in f.Pads():
        c=p.GetPosition(); d=dict(ref=str(f.GetReference()),n=str(p.GetNumber()),net=str(p.GetNetname()),x=MM(c.x),y=MM(c.y),hole=MM(p.GetDrillSize().x),L={})
        for l,n in zip(CU,LN):
            if p.IsOnLayer(l):
                ps=pcbnew.SHAPE_POLY_SET(); 
                try:
                    pp=p.GetEffectivePolygon(l,pcbnew.ERROR_INSIDE); ps=pcbnew.SHAPE_POLY_SET(pp)
                    d['L'][n]=polys(ps)[0][0] if ps.OutlineCount() else []
                except Exception as e: d['L'][n]=[]
        out['pads'].append(d)
json.dump(out,open(sys.argv[2],'w'))
print('tracks',len(out['tracks']),'vias',len(out['vias']),'fills',len(out['fills']),'pads',len(out['pads']))
