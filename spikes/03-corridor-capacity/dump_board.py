"""dump_board.py <board.kicad_pcb> <out.json>   (run with KiCad's python: needs pcbnew)
Footprints with their schematic sheet, rotation and courtyard box, keep-out areas, pads, tracks, vias, and per copper layer a 0.5 mm raster of zone fill by net."""
import json, sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
layers = [l for l in b.GetEnabledLayers().CuStack()]; lname = {l: b.GetLayerName(l) for l in layers}
bb = b.GetBoardEdgesBoundingBox(); x0, y0, x1, y1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
out = dict(box=[x0, y0, x1, y1], layers=[lname[l] for l in layers], fps=[], pads=[], tracks=[], vias=[], zones={})
for f in b.GetFootprints():
    out["fps"].append(dict(ref=f.GetReference(), x=mm(f.GetPosition().x), y=mm(f.GetPosition().y), side=lname.get(f.GetLayer(), "?"),
                           sheet=f.GetSheetname(), value=f.GetValue(), rot=f.GetOrientationDegrees()))
    try:
        cy = f.GetCourtyard(pcbnew.F_CrtYd if f.GetLayer() == pcbnew.F_Cu else pcbnew.B_CrtYd)
        if cy.OutlineCount():
            r = cy.BBox(); out["fps"][-1]["court"] = [mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())]
    except Exception: pass
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
out["keepouts"] = []
# the part of the bounding box that is outside the real outline, as rectangles: placers treat them as keep-outs
edge = pcbnew.SHAPE_POLY_SET(); R = 0.25
if b.GetBoardPolygonOutlines(edge, True):
    rows = []
    for j in range(int((y1 - y0) / R) + 1):
        yy = y0 + (j + 0.5) * R; run = []; start = None
        for i in range(int((x1 - x0) / R) + 2):
            xx = x0 + (i + 0.5) * R; outside = xx < x1 and not edge.Contains(pcbnew.VECTOR2I(pcbnew.FromMM(xx), pcbnew.FromMM(yy)))
            if outside and start is None: start = i
            if not outside and start is not None: run.append((start, i)); start = None
        rows.append(run)
    open_ = {}
    for j, run in enumerate(rows + [[]]):
        for r in list(open_):
            if r not in run:
                j0 = open_.pop(r); w = (r[1] - r[0]) * R; h = (j - j0) * R
                if w > 0.3 and h > 0.3: out["keepouts"].append(dict(name="outside_board", box=[round(x0 + r[0] * R, 3), round(y0 + j0 * R, 3), round(x0 + r[1] * R, 3), round(y0 + j * R, 3)], layers=["F.Cu", "B.Cu"], no_footprints=True, no_tracks=True, no_vias=True, no_pours=True))
        for r in run: open_.setdefault(r, j)
for z in b.Zones():
    if z.GetIsRuleArea():
        r = z.GetBoundingBox()
        out["keepouts"].append(dict(name=z.GetZoneName(), box=[mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())],
                                    layers=[lname[l] for l in layers if z.IsOnLayer(l)], no_footprints=bool(z.GetDoNotAllowFootprints()),
                                    no_tracks=bool(z.GetDoNotAllowTracks()), no_vias=bool(z.GetDoNotAllowVias()), no_pours=bool(z.GetDoNotAllowZoneFills() if hasattr(z, "GetDoNotAllowZoneFills") else z.GetDoNotAllowCopperPour())))
        continue
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
print(sys.argv[1], len(out["fps"]), "footprints", len(out["tracks"]), "tracks", len(out["vias"]), "vias", len(out["zones"]), "zone fills", len(out["keepouts"]), "keep-outs")
