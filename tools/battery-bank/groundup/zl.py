import sys, pcbnew
MM = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
for z in b.Zones():
    if z.GetIsRuleArea() or z.GetNetname() not in ('PACK_P', '3V3'): continue
    for l in z.GetLayerSet().CuStack():
        ps = z.GetFilledPolysList(l)
        for i in range(ps.OutlineCount()):
            o = ps.Outline(i); bb = o.BBox(); 
            one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(o)
            print(z.GetNetname(), z.GetZoneName(), b.GetLayerName(l)[:3], 'bbox (%.1f,%.1f)-(%.1f,%.1f) outline area %.1f holes %d' % (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()), one.Area() / 1e12, ps.HoleCount(i)))
