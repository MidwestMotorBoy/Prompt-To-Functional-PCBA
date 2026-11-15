"""cu_dump.py <board.kicad_pcb> <out.json>      (KiCad's python: needs pcbnew)
Everything the power copper planner needs from a placed board, as exact polygons: the board outline (with holes),
every pad's copper shape per layer with its net, drill and part, the keep-out areas with what they forbid, the
copper layers in stack order with their thickness and height, and the board's default clearance."""
import sys, json, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
cu = list(b.GetEnabledLayers().CuStack()); name = {l: pcbnew.BOARD.GetStandardLayerName(l) for l in cu}
def polys(sps):
    out = []
    for i in range(sps.OutlineCount()):
        o = sps.Outline(i); ring = [(round(mm(o.CPoint(k).x), 4), round(mm(o.CPoint(k).y), 4)) for k in range(o.PointCount())]
        holes = []
        for h in range(sps.HoleCount(i)):
            hh = sps.Hole(i, h); holes.append([(round(mm(hh.CPoint(k).x), 4), round(mm(hh.CPoint(k).y), 4)) for k in range(hh.PointCount())])
        out.append(dict(ring=ring, holes=holes))
    return out
edge = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(edge, True)
# stack-up, read from the file's (stackup ...) block: copper thickness and the height of each copper layer from the top
import re
st = []; z = 0.0; txt = open(sys.argv[1], encoding="utf-8").read(); k = txt.find("(stackup")
for m in re.finditer(r'\(layer "([^"]+)"\s*\(type "([^"]+)"\)(.*?)\n\t\t\t\)', txt[k:txt.find("\n\t\t)", k)] if k >= 0 else "", re.S):
    th = re.search(r"\(thickness ([0-9.]+)", m.group(3)); t = float(th.group(1)) if th else 0.0
    if m.group(2) == "copper": st.append(dict(layer=m.group(1), t_mm=t, z_mm=round(z + t / 2, 4)))
    if m.group(2) in ("copper", "core", "prepreg") or m.group(1).startswith("dielectric"): z += t
out = dict(board=sys.argv[1], layers=[name[l] for l in cu], stackup=st, outline=polys(edge),
           clearance_mm=max(0.2, mm(b.GetDesignSettings().m_MinClearance)),   # 0.2 mm unless the board sets more
           fps=[], pads=[], keepouts=[])
for f in b.GetFootprints():
    out["fps"].append(dict(ref=f.GetReference(), value=f.GetValue(), fp=str(f.GetFPID().GetLibItemName()), layer=name.get(f.GetLayer(), "?"),
                           x=mm(f.GetPosition().x), y=mm(f.GetPosition().y), rot=f.GetOrientationDegrees()))
    for p in f.Pads():
        shapes = {}
        for l in cu:
            if not p.IsOnLayer(l): continue
            s = pcbnew.SHAPE_POLY_SET(); p.TransformShapeToPolygon(s, l, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE); shapes[name[l]] = polys(s)
        dr = p.GetDrillSize()
        out["pads"].append(dict(ref=f.GetReference(), num=p.GetNumber(), net=p.GetNetname(), pinfn=p.GetPinFunction(), x=mm(p.GetPosition().x), y=mm(p.GetPosition().y),
                                drill=mm(min(dr.x, dr.y)) if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) else 0,
                                npth=p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH, shapes=shapes))
for zn in list(b.Zones()) + [z for f in b.GetFootprints() for z in f.Zones()]:      # board and footprint keep-outs
    if not zn.GetIsRuleArea(): continue
    out["keepouts"].append(dict(name=zn.GetZoneName(), layers=[name[l] for l in cu if zn.IsOnLayer(l)], poly=polys(zn.Outline()),
                                no_tracks=bool(zn.GetDoNotAllowTracks()), no_vias=bool(zn.GetDoNotAllowVias()), no_pours=bool(zn.GetDoNotAllowZoneFills()),
                                no_footprints=bool(zn.GetDoNotAllowFootprints())))
json.dump(out, open(sys.argv[2], "w"))
print(f"{sys.argv[2]}: {len(out['fps'])} parts, {len(out['pads'])} pads, {len(out['keepouts'])} keep-outs, layers {out['layers']}, stack-up {len(st)} copper layers")
