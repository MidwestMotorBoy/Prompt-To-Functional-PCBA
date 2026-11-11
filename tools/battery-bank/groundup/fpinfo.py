import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); M = pcbnew.ToMM
for r in sys.argv[2:]:
    f = b.FindFootprintByReference(r); p = f.GetPosition()
    print(r, round(M(p.x), 3), round(M(p.y), 3), f.GetOrientationDegrees(), 'B' if f.GetLayer() == pcbnew.B_Cu else 'F', [(q.GetNumber(), q.GetNetname().split('/')[-1], round(M(q.GetPosition().x), 3), round(M(q.GetPosition().y), 3)) for q in f.Pads()])
