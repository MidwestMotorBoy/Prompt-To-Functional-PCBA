"""dump_board.py <board.kicad_pcb> <out.json>   (run with KiCad's python: needs pcbnew)
Footprints with their schematic sheet, pads, tracks, vias, and per copper layer a 0.5 mm raster of zone fill by net."""
import json, sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
layers = [l for l in b.GetEnabledLayers().CuStack()]; lname = {l: b.GetLayerName(l) for l in layers}
bb = b.GetBoardEdgesBoundingBox(); x0, y0, x1, y1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
out = dict(box=[x0, y0, x1, y1], layers=[lname[l] for l in layers], fps=[], pads=[], tracks=[], vias=[], zones={})
for f in b.GetFootprints():
    out["fps"].append(dict(ref=f.GetReference(), x=mm(f.GetPosition().x), y=mm(f.GetPosition().y), side=lname.get(f.GetLayer(), "?"),
                           sheet=f.GetSheetname(), value=f.GetValue()))
    for p in f.Pads():
        r = p.GetBoundingBox()
        out["pads"].append(dict(ref=f.GetReference(), num=p.GetNumber(), net=p.GetNetname(), x=mm(p.GetPosition().x), y=mm(p.GetPosition().y),
                                box=[mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())],
                                layers=[lname[l] for l in layers if p.IsOnLayer(l)]))
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        out["vias"].append(dict(net=t.GetNetname(), x=mm(t.GetPosition().x), y=mm(t.GetPosition().y), d=mm(t.GetWidth(pcbnew.F_Cu)),
                                layers=[lname[l] for l in layers if t.IsOnLayer(l)]))
    else:
        s, e = t.GetStart(), t.GetEnd()
        out["tracks"].append(dict(net=t.GetNetname(), l=lname[t.GetLayer()], w=mm(t.GetWidth()), x1=mm(s.x), y1=mm(s.y), x2=mm(e.x), y2=mm(e.y)))
STEP = 0.5; nx, ny = int((x1 - x0) / STEP) + 1, int((y1 - y0) / STEP) + 1; out["raster"] = dict(step=STEP, nx=nx, ny=ny)
for z in b.Zones():
    if z.GetIsRuleArea(): continue
    for l in layers:
        if not z.IsOnLayer(l): continue
        poly = z.GetFilledPolysList(l)
        if poly.OutlineCount() == 0: continue
        key = f"{lname[l]}|{z.GetNetname()}"; g = out["zones"].setdefault(key, [])
        pb = poly.BBox()
        for j in range(ny):
            y = y0 + j * STEP
            if not (mm(pb.GetTop()) <= y <= mm(pb.GetBottom())): continue
            for i in range(nx):
                x = x0 + i * STEP
                if mm(pb.GetLeft()) <= x <= mm(pb.GetRight()) and poly.Contains(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))): g.append(j * nx + i)
json.dump(out, open(sys.argv[2], "w"))
print(sys.argv[1], len(out["fps"]), "footprints", len(out["tracks"]), "tracks", len(out["vias"]), "vias", {k: len(v) for k, v in out["zones"].items()})
