"""edump.py <board.kicad_pcb> <out.json>      (KiCad's python: needs pcbnew)
Everything the team E router needs from a board, as exact geometry: outline, pads (polygon per copper layer, net,
drill), keep-outs, zones (name, net, layer, priority, filled polygons with holes), tracks, vias and each net's class."""
import sys, json, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
cu = list(b.GetEnabledLayers().CuStack()); name = {l: pcbnew.BOARD.GetStandardLayerName(l) for l in cu}
R = lambda v: round(mm(v), 4)
def polys(sps):
    out = []
    for i in range(sps.OutlineCount()):
        o = sps.Outline(i); ring = [(R(o.CPoint(k).x), R(o.CPoint(k).y)) for k in range(o.PointCount())]
        holes = []
        for h in range(sps.HoleCount(i)):
            hh = sps.Hole(i, h); holes.append([(R(hh.CPoint(k).x), R(hh.CPoint(k).y)) for k in range(hh.PointCount())])
        out.append(dict(ring=ring, holes=holes))
    return out
edge = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(edge, True)
out = dict(layers=[name[l] for l in cu], outline=polys(edge), pads=[], keepouts=[], zones=[], tracks=[], vias=[], netclass={}, fps=[])
for nm, ni in b.GetNetsByName().items():
    out["netclass"][str(nm)] = str(ni.GetNetClassName())
for f in b.GetFootprints():
    bb = f.GetCourtyard(f.GetLayer()).BBox() if f.GetCourtyard(f.GetLayer()).OutlineCount() else f.GetBoundingBox(False)
    out["fps"].append(dict(ref=f.GetReference(), value=f.GetValue(), layer=name.get(f.GetLayer(), "?"), x=R(f.GetPosition().x), y=R(f.GetPosition().y),
                           rot=f.GetOrientationDegrees(), court=[R(bb.GetLeft()), R(bb.GetTop()), R(bb.GetRight()), R(bb.GetBottom())], npads=len(f.Pads())))
    for p in f.Pads():
        shapes = {}
        for l in cu:
            if not p.IsOnLayer(l): continue
            s = pcbnew.SHAPE_POLY_SET(); p.TransformShapeToPolygon(s, l, 0, pcbnew.FromMM(0.002), pcbnew.ERROR_OUTSIDE); shapes[name[l]] = polys(s)
        dr = p.GetDrillSize(); pth = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        bq = p.GetBoundingBox()
        out["pads"].append(dict(ref=f.GetReference(), num=p.GetNumber(), net=p.GetNetname(), x=R(p.GetPosition().x), y=R(p.GetPosition().y),
                                drill=[R(dr.x), R(dr.y)] if pth else [0, 0], npth=p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH, shapes=shapes,
                                box=[R(bq.GetLeft()), R(bq.GetTop()), R(bq.GetRight()), R(bq.GetBottom())], uuid=p.m_Uuid.AsString()))
for zn in list(b.Zones()) + [z for f in b.GetFootprints() for z in f.Zones()]:
    if zn.GetIsRuleArea():
        out["keepouts"].append(dict(name=zn.GetZoneName(), layers=[name[l] for l in cu if zn.IsOnLayer(l)], poly=polys(zn.Outline()),
                                    no_tracks=bool(zn.GetDoNotAllowTracks()), no_vias=bool(zn.GetDoNotAllowVias()), no_pours=bool(zn.GetDoNotAllowZoneFills())))
        continue
    for l in cu:
        if zn.IsOnLayer(l):
            out["zones"].append(dict(name=zn.GetZoneName(), net=zn.GetNetname(), layer=name[l], prio=zn.GetAssignedPriority(),
                                     fill=polys(zn.GetFilledPolysList(l)), outline=polys(zn.Outline()), uuid=zn.m_Uuid.AsString()))
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        c = t.GetPosition(); out["vias"].append(dict(net=t.GetNetname(), x=R(c.x), y=R(c.y), size=R(t.GetWidth(pcbnew.F_Cu)), drill=R(t.GetDrill()), uuid=t.m_Uuid.AsString()))
    else:
        a, e = t.GetStart(), t.GetEnd()
        out["tracks"].append(dict(net=t.GetNetname(), layer=name.get(t.GetLayer(), "?"), a=[R(a.x), R(a.y)], b=[R(e.x), R(e.y)], w=R(t.GetWidth()), uuid=t.m_Uuid.AsString()))
json.dump(out, open(sys.argv[2], "w"))
print("%s: %d pads, %d zones, %d tracks, %d vias, %d keep-outs" % (sys.argv[2], len(out["pads"]), len(out["zones"]), len(out["tracks"]), len(out["vias"]), len(out["keepouts"])))
