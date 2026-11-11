import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); x0, y0, x1, y1 = [float(v) * 1e6 for v in sys.argv[2].split(',')]
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA': continue
    bb = t.GetBoundingBox()
    if bb.GetLeft() > x1 or bb.GetRight() < x0 or bb.GetTop() > y1 or bb.GetBottom() < y0 or t.GetLayer() == pcbnew.F_Cu: continue
    print(t.GetNetname(), b.GetLayerName(t.GetLayer())[:3], t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, t.GetWidth())
