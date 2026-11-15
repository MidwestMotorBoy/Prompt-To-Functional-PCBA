"""zone_islands.py <board.kicad_pcb> [net substring ...]     (KiCad python; team B finishing pass helper)
Lists the filled islands of every zone with more than one island on a layer: area, and the same-net pads, vias and
track ends that touch each island (an island touching nothing carries no current and is safe to drop)."""
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); want = sys.argv[2:]
MM = pcbnew.ToMM
for z in b.Zones():
    n = z.GetNetname()
    if want and not any(w in n for w in want): continue
    for L in z.GetLayerSet().CuStack():
        f = z.GetFilledPolysList(L)
        if f.OutlineCount() < 2 and not want: continue
        print("%s %s %s: %d islands" % (z.GetZoneName(), n, b.GetLayerName(L), f.OutlineCount()))
        for i in range(f.OutlineCount()):
            o = f.Outline(i); bb = o.BBox()
            touch = []
            for p in b.GetPads():
                if p.GetNetname() == n and p.IsOnLayer(L):
                    sh = p.GetEffectivePolygon(L) if hasattr(p, "GetEffectivePolygon") else None
                    if o.PointInside(p.GetPosition()) or (sh is not None and any(o.PointInside(sh.CVertex(k)) for k in range(sh.FullPointCount()))):
                        touch.append("%s.%s" % (p.GetParentFootprint().GetReference(), p.GetNumber()))
            for t in b.GetTracks():
                if t.GetNetname() == n and t.IsOnLayer(L):
                    pts = [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]
                    if any(o.PointInside(q) for q in pts): touch.append(("via" if t.GetClass() == "PCB_VIA" else "trk") + "@%.2f,%.2f" % (MM(pts[0].x), MM(pts[0].y)))
            print("   island %d: area %.3f mm2, bbox %.2f,%.2f-%.2f,%.2f, touches %d: %s" % (i, o.Area() / 1e12, MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()), len(touch), " ".join(touch[:8])))
