import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); MM = pcbnew.ToMM
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetNetname().split('/')[-1] == sys.argv[2] or p.GetNetname() == sys.argv[2]:
            print(f.GetReference(), p.GetNumber(), f.GetValue(), '%.2f,%.2f' % (MM(p.GetPosition().x), MM(p.GetPosition().y)), b.GetLayerName(f.GetLayer())[:1])
