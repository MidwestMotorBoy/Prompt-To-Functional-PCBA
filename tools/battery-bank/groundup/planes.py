"""planes.py board out.json: dump the In2 / In3 plane pieces and tracks for a picture (KiCad python)"""
import sys, json, pcbnew
MM = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); out = dict(z=[], t=[], v=[])
for z in b.Zones():
    if z.GetIsRuleArea(): continue
    for l in (pcbnew.In2_Cu, pcbnew.In3_Cu):
        if not z.IsOnLayer(l): continue
        ps = z.GetFilledPolysList(l)
        for i in range(ps.OutlineCount()):
            o = ps.Outline(i)
            out['z'].append([b.GetLayerName(l)[:3], z.GetNetname(), [[round(MM(o.CPoint(j).x), 3), round(MM(o.CPoint(j).y), 3)] for j in range(o.PointCount())]])
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        out['v'].append([t.GetNetname(), MM(t.GetPosition().x), MM(t.GetPosition().y)])
    elif t.GetLayer() in (pcbnew.In2_Cu, pcbnew.In3_Cu):
        out['t'].append([b.GetLayerName(t.GetLayer())[:3], t.GetNetname(), MM(t.GetStart().x), MM(t.GetStart().y), MM(t.GetEnd().x), MM(t.GetEnd().y), MM(t.GetWidth())])
json.dump(out, open(sys.argv[2], 'w'))
