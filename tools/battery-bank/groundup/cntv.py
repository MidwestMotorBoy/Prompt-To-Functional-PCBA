import sys, pcbnew, math
M = pcbnew.ToMM
x, y, r = float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
for f in sys.argv[5:]:
    b = pcbnew.LoadBoard(f)
    v = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == sys.argv[1] and math.hypot(M(t.GetPosition().x) - x, M(t.GetPosition().y) - y) < r]
    tot = sum(1 for t in b.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == sys.argv[1])
    print(f.split('/')[-1], 'near', len(v), 'total', tot, sorted(('%.2f,%.2f' % (M(t.GetPosition().x), M(t.GetPosition().y))) for t in v)[:14])
