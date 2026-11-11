import sys, pcbnew
M = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); x0, y0, x1, y1 = [float(v) for v in sys.argv[2].split(',')]
for f in b.GetFootprints():
    for p in f.Pads():
        q = p.GetPosition()
        if x0 <= M(q.x) <= x1 and y0 <= M(q.y) <= y1:
            bb = p.GetBoundingBox()
            print("%s.%s %-18s %s  x %.3f..%.3f y %.3f..%.3f" % (f.GetReference(), p.GetNumber(), p.GetNetname()[-18:], "F" if p.IsOnLayer(pcbnew.F_Cu) else "B", M(bb.GetLeft()), M(bb.GetRight()), M(bb.GetTop()), M(bb.GetBottom())))
    c = f.GetCourtyard(pcbnew.F_Cu) if not f.IsFlipped() else f.GetCourtyard(pcbnew.B_Cu)
    bb = c.BBox()
    if bb.GetWidth() > 0 and M(bb.GetRight()) >= x0 and M(bb.GetLeft()) <= x1 and M(bb.GetBottom()) >= y0 and M(bb.GetTop()) <= y1:
        print("  cyd %s %s x %.3f..%.3f y %.3f..%.3f" % (f.GetReference(), "B" if f.IsFlipped() else "F", M(bb.GetLeft()), M(bb.GetRight()), M(bb.GetTop()), M(bb.GetBottom())))
